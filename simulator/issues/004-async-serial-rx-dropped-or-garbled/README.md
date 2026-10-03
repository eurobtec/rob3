# Issue 004 — Asynchronously-delivered serial RX bytes are dropped/garbled (`-S port=` socket and live `in=` pty)

**Component:** `src/core/sim.src/serial_hw.cc` (`cl_serial_hw`), the serial
input buffering; and `src/sims/s51.src/serial.cc` (`cl_serial::tick`), the RX
clocking.
**ucSim:** 0.9.9
**Type:** modeling limitation (frames dropped / corrupted — not a crash)
**Status:** limitation + repro; worked around by using **pre-staged file input**
(`-S in=<file>`), which is clocked deterministically. **To investigate later:**
a FIFO/queued RX path so live sockets/ptys round-trip.

## ⚠️ CORRECTION (re-investigated) — the original premise above is WRONG

A careful re-investigation **overturns** the "ucSim drops/garbles RX bytes"
diagnosis. The earlier `skip`/garble observations were an **artifact of the test
harness**, not a ucSim UART defect.

### What actually happens (instrumented, normal invocation)

Driving ucSim *normally* (`ucsim_51 -S port=N,raw ... -e run`, i.e. NOT through a
scripted `pty.fork()` command console) and tracing the RX path with `fprintf`s
in `cl_serial_hw::proc_not_in_menu` and `get_input`:

```
DBG rx accept 0x4f           # byte 1 read from the socket, cleanly
DBG get_input -> SBUF 0x4f   # clocked into SBUF
DBG rx accept 0x03           # byte 2 (ETX), cleanly
DBG get_input -> SBUF 0x03   # clocked into SBUF
```

**Both bytes arrive in order and reach SBUF correctly** — no drop, no garble,
no overrun — *even with a 1.5 s gap between them, and even sent back-to-back in
one write*. ucSim's UART-over-socket is **fine**.

The earlier failures were because the tests drove the sim through a captured
pty **command console** running a scripted `run`; in that mode the normal
`cl_app::run_go` → `cl_commander::proc_input` → `update_active` input-polling
loop did not pump the serial socket/pty (the `DBG upd`/`DBG serial_hw::proc_input`
traces never fired). Run ucSim the ordinary way and the serial fd IS polled and
delivered.

### The REAL problem is firmware-side, not ucSim

With both bytes correctly in SBUF, the ROB3 firmware **still** replies `0xF1`
(idle / "already initialized") instead of dispatching the frame. The startup
`0x20` also gets `0xF1` rather than `0x15`. So after the `rxd` auto-baud lock,
received command bytes reach SBUF but the firmware's serial command path does
**not** engage — it sits in the idle-reply state.

Ruled out by experiment:
- single-byte RX-slot overflow (bytes are not dropped);
- bit-clock misalignment / garble (SBUF values are exact);
- inter-byte serial-timeout reset (fails identically back-to-back and with gaps);
- missing startup handshake (sending `0x20` first still yields `0xF1`, not `0x15`).

### Where to look next (firmware, not simulator)

This is now a **firmware RE question** in `firmware/src/annotated/rs232.asm`:
why, after the auto-baud path completes (IE=0x17, ES on, TR1 running), do bytes
clocked into SBUF land on the `0xF1` idle-reply path instead of advancing the
RX state machine (`0x24` flags) into `rx_dispatch` (0x03A9)? Candidate areas:
the auto-baud *lock produced by the `rxd` model* may leave the UART in a state
the firmware treats as not-yet-synchronized; or the `0x20`-handshake state
(the `0x15` vs `0xF1` decision) gates all later command dispatch and never
reaches "init OK" under the `rxd`-driven lock. Trace from the RX ISR (0x0300)
with a PC/flag log and compare against the `-S in=<file>` path that DOES
dispatch (`test_sim_roundtrip.py`) — the delta between the two is the key.

### Net

- **No ucSim change is warranted** for this (the FIFO attempt below was based on
  the wrong premise and was reverted; ucSim is unmodified).
- The `-S in=<file>` round-trip works because of *how that path is driven*, not
  because the socket is broken. The open question is a firmware-state one.

---

## (original, now-superseded) Summary

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

## Attempt log (what was tried and why it was NOT enough)

A FIFO was prototyped and **reverted** — recording the dead ends so the next
attempt starts informed:

1. **Host-side pacing (byte-by-byte with a gap)** — does NOT help. Writing the
   two frame bytes to the pty with 20–400 ms gaps still produced a corrupted
   reply (`4f 5e 43`). The pacing authority must be the simulator, not the host.

2. **RX FIFO in `cl_serial_hw`** (push every received byte into a
   `std::deque` in `proc_not_in_menu`; pop one per frame-time in `get_input`;
   start receiving in `cl_serial::tick` when the FIFO is non-empty). It compiles
   and links, but on the live **pty** and **socket** paths the FIFO was **never
   filled** (debug `fprintf`s in `proc_not_in_menu`/`get_input` never fired)
   while the sim was free-running from the pty command console. Conclusion: the
   fix was on the wrong code path.

3. **Open question for the next attempt — the real blocker:** *when, during a
   free `run`, is a serial input fd (socket/pty) actually polled?*
   `cl_commander::proc_input` (`core/cmd.src/newcmdposix.cc`) iterates
   **consoles** and calls `proc_input` only when `input_avail()`; the
   `-S port=` listener registers as a console, but driving the sim via a
   *scripted pty command console* (as the harness does) did not pump the serial
   socket/pty in these tests. The `-S in=<file>` path works because it is read
   on a different schedule entirely. **Resolve this first** (map the exact
   run-loop → serial-RX input dispatch) before re-attempting the FIFO; patching
   `proc_not_in_menu`/`get_input` is pointless if they aren't called during
   `run`.

Until then the reliable contract remains the pre-staged `-S in=<file>` path
(`rob3_ros2_driver` `test/test_sim_roundtrip.py`).

## Impact / current workaround

Not blocking: the driver uses **serial** against the real robot, and the ucSim
integration contract is the **pre-staged file path** (reliable, repeatable). The
`rob3_driver/scripts/sim_bringup.py` helper brings the ROM up on a pty for
interactive poking, with this limitation documented.
