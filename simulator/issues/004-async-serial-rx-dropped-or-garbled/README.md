# Issue 004 — Asynchronously-delivered serial RX bytes are dropped/garbled (`-S port=` socket and live `in=` pty)

**Component:** `src/core/sim.src/serial_hw.cc` (`cl_serial_hw`), the serial
input buffering; and `src/sims/s51.src/serial.cc` (`cl_serial::tick`), the RX
clocking.
**ucSim:** 0.9.9
**Type:** modeling limitation (frames dropped / corrupted — not a crash)
**Status:** limitation + repro; worked around by using **pre-staged file input**
(`-S in=<file>`), which is clocked deterministically. **To investigate later:**
a FIFO/queued RX path so live sockets/ptys round-trip.

## Summary

ucSim's serial RX has a **single-byte** host-input slot (`input` /
`input_avail` in `cl_serial_hw`). A new byte is only accepted when
`input_avail` is false, i.e. after the previous byte has been clocked into
`SBUF` at the modeled baud. When the host delivers bytes **asynchronously**
(faster than the modeled baud, or not aligned to the sim's run/clock), the
behaviour differs sharply by input source:

- **Pre-staged `-S in=<file>`** — the file is drained one byte per
  receive-complete at the modeled baud. Multi-byte command frames arrive
  intact; a full command→response round-trip works. **(reliable)**
- **`-S port=<n>` TCP socket** — bytes written back-to-back by a host overflow
  the single `input` slot; the extra ones are discarded with
  `"<name>[<id>] Character <n> queued for RX, skip <m>"`
  (`serial_hw.cc` `proc_not_in_menu`). A 2-byte frame like `0x4F 0x03` loses the
  ETX, the firmware frame never completes, and the ROB3 serial-timeout stages a
  `0xF1` idle reply instead of dispatching. **(frames dropped)**
- **Live `-S in=<pty>` pty** — bytes arrive intact-ish but the RX clocking vs.
  the asynchronously-arriving data misaligns, so the firmware decodes a
  **corrupted header** (observed: query `0x4F 0x03` came back as a reply to
  header `0x5E`/garbage; raw PTY reply `15 5e 43` instead of `15 4f …40 03`).
  **(frames garbled)**

The common cause: **host RX delivery is not paced to the modeled baud** except
for the pre-staged file path.

## Where it bites (ROB3 / rob3_ros2_driver)

The ROB3 ROS 2 driver speaks the binary protocol over RS-232. We wanted it to
drive the firmware live in ucSim (socket or pty) the same way it drives the real
robot. Result:

- `-S port=` socket + driver `TcpTransport`: every command returned `0xF1`
  (idle), never real data — the ETX was dropped (the `skip` path above). The
  driver's `TcpTransport` was consequently **removed**; serial is the only
  transport.
- Live pty + driver `SerialTransport`: handshake intermittently `no_reply` /
  corrupted replies.
- **Pre-staged `-S in=<file>`**: the driver's exact query bytes round-trip
  cleanly — reply `15 4f 00 00 00 3b 4f 00 03`, parsed by the driver codec as a
  valid all-axis position frame. This is the path the driver's ucSim
  integration test uses, and it mirrors `simulator/tests/sim_serial_e2e.sh`.

## Root cause (source)

`cl_serial_hw` (`core/sim.src/serial_hw.cc`):

- `char input; bool input_avail;` — a **one-byte** host input buffer (protected).
- `proc_not_in_menu()` reads one char from `fin` only `if (!input_avail)`;
  otherwise it prints `"... queued for RX, skip ..."` and **drops** the char.
- `get_input()` hands `input` to the MCS-51 `cl_serial::tick()` RX path, which
  sets `s_in`/`SBUF` and `RI` once per modeled frame-time.

With a pre-staged file, `fin->read` naturally supplies the next byte only after
`input_avail` clears (paced by the sim). With an async socket/pty, the host can
present bytes while `input_avail` is still true → drop; or present them at an
instant that misaligns with the RX bit clock → corruption.

## Reproduction

See `repro.sh` — it brings the ROM up to the serial auto-baud lock (via the
`rxd` cl_hw module), then sends the same query frame three ways:

1. pre-staged `-S in=<file>` → clean reply frame (`…4f…03`);
2. `-S port=` socket, bytes back-to-back → `0xF1` + a `skip` line on stderr;
3. live pty, stepped → corrupted reply.

Only (1) yields a valid dispatched reply.

## Proposed direction (not yet implemented)

Give the serial RX a small **FIFO** instead of the single `input`/`input_avail`
slot, and feed it to the UART **paced at the modeled baud** regardless of how
fast the host delivers. That would make the socket and pty paths behave like the
file path and let an external driver do a live round-trip. Alternatively, add a
public "inject one received byte" entry that an input source (or a `cl_hw`
plugin) can call, clocked by the UART.

## Impact / current workaround

Not blocking: the driver uses **serial** against the real robot, and the ucSim
integration contract is the **pre-staged file path** (reliable, repeatable). The
`rob3_driver/scripts/sim_bringup.py` helper brings the ROM up on a pty for
interactive poking, with this limitation documented.
