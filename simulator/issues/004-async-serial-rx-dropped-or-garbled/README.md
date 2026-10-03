# Issue 004 — ucSim serial inter-byte timing exceeds the firmware's RX timeout (no live socket/pty command round-trip)

**Component:** `src/sims/s51.src/serial.cc` (`cl_serial`), the MCS-51 UART
receive bit-timing — specifically how many machine cycles elapse between
consecutive received bytes under the `rxd`-driven auto-baud lock.
**ucSim:** 0.9.9
**Type:** timing-fidelity mismatch (NOT a dropped/garbled-byte bug, NOT a crash)
**Status:** **ROOT CAUSE FOUND** (below). ucSim is unmodified. The reliable
contract remains pre-staged `-S in=<file>` (`test_sim_roundtrip.py`).

## ROOT CAUSE (confirmed [SIM] + arithmetic)

A live socket/pty command frame (e.g. the all-axis query `0x4F 0x03`) does not
dispatch — the firmware replies `0xF1` — **because ucSim delivers the two bytes
~1.84M machine-cycles apart, which is longer than the firmware's 20-tick serial
RX timeout. The timeout fires between the header and the ETX, resets the RX
state machine, and stages the `0xF1` reset-ACK; the ETX then arrives as a fresh
(invalid) "header".**

### The bytes are NOT dropped or garbled

Instrumenting the ucSim RX path (`fprintf` in `proc_not_in_menu`, `get_input`,
and `cl_serial::received`) under a **normal** invocation
(`ucsim_51 -S port=N,raw ... -e run`, *not* a scripted pty command console):

```
DBG RI set for 0x4f (SCON=0x51, RI_was_already=0) tick=46353864
DBG RI set for 0x03 (SCON=0x51, RI_was_already=0) tick=48192420
```

Both bytes reach `SBUF` with a clean RI edge (RI was 0 before each — the ISR
serviced and cleared byte 1 before byte 2). The UART-over-socket is **correct**.
(The earlier "dropped/garbled" observations were a **test-harness artifact** —
driving the sim through a scripted pty command console bypassed the normal
`cl_app::run_go` → `cl_commander::proc_input` input-polling loop, so the socket
was never pumped. Run ucSim ordinarily and it is.)

### The timing numbers

- Inter-byte gap measured: **48192420 − 46353864 = 1,838,556 machine cycles**
  (constant, independent of how the host sends — it is the UART model's framing
  time at the `rxd`-locked baud, ~128 cycles/bit).
- Firmware serial timeout: Timer 0 reloads `TH0:TL0 = 0xE811` → overflow every
  `0x10000−0xE811 = 6127` cycles → tick period **6127 × 12 = 73,524** cycles.
  `main.asm` reloads `SER_TIMEOUT` (IRAM `0x18`) to `0x14` (20) per received
  byte and does `djnz 0x18` once per serial tick (`0x23.7`). Expiry after
  **20 × 73,524 = 1,470,480** cycles.
- **1,470,480 (timeout) < 1,838,556 (inter-byte gap)** → the timeout always
  expires first.

### The firmware path that fires (`main.asm`, [BYTE])

```
ml_no_serial:
  jnb  0x23.7, ml_poll_gate     ; only on a serial-timer tick
  clr  0x23.7
  jnb  0x24.2, ml_poll_gate     ; only if a byte has been seen (RX in progress)
  djnz 0x18,  ml_poll_gate      ; SER_TIMEOUT--; not expired -> skip
  anl  0x24, #0xF0              ; EXPIRED: wipe RX frame flags (0x24.0..3)
  mov  R4,  #0xF1              ; stage 0xF1 reset-ACK
  setb 0x25.3                  ; arm TX
```

Confirmed by trace: after the header, `0x24 = 0x07` (frame in progress +
complete-armed + byte-seen); by the time the ETX arrives the timeout has wiped
`0x24.0`, so the ISR's `jb 0x24.0, rx_payload` (0x0311) is not taken and ETX is
mis-decoded as a new header. Breakpoint at `rx_payload` (0x0354) and at
`rx_dispatch` (0x03A9) are never hit for the ETX.

### Why the `-S in=<file>` path works

It is driven under `step`, so the firmware advances only a bounded number of
cycles between bytes — fewer than the timeout — and the frame completes. On
**real hardware** the true baud puts the two bytes well within 1.47M cycles, so
the timeout never expires. The problem is purely the `rxd` model's cycles/bit
being far slower than real serial (a modelling artifact already noted in
issue 003 / lessons-learned: the auto-baud lock lands at ~128 cycles/bit, not a
real baud).

### Fix options (none applied yet)

1. **Make the `rxd` auto-baud lock land at a realistic bit-time** so the modeled
   inter-byte gap is < ~1.47M cycles (i.e. drive the training byte so the
   firmware derives a faster TH1 / the UART clocks bytes faster). Cleanest —
   keeps the firmware honest, no core change.
2. Drive command bytes under `step` (as `test_sim_roundtrip.py` does) rather
   than a free `run`, so few firmware cycles pass between bytes.
3. (Not recommended) patch the firmware timeout — it is correct for real HW.

---

## (original, WRONG premise — kept for history) Summary

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
