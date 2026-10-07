# Issue 004 — ucSim polls the serial fd too rarely during `run`; the gap exceeds the firmware's RX timeout (no live socket/pty command round-trip)

**Component:** `src/core/utils.src/app.cc` (`cl_app::run_go`) — the run-loop
cadence at which `cl_commander::proc_input` is called to read the serial input
fd. (NOT the UART bit-timing in `serial.cc`, and NOT the single-byte RX slot in
`serial_hw.cc` — both are fine.)
**ucSim:** 0.9.9
**Type:** host-input poll-cadence vs. firmware-timeout mismatch (NOT a
dropped/garbled-byte bug, NOT a crash)
**Status:** **ROOT CAUSE FOUND + RESOLVED (no patch needed).** The existing
per-UART `serconf_check_often` flag can be toggled at runtime through ucSim's
**configuration memory** on a stock 0.9.9+ build — `expr uart0_check_often=1`
(or a direct `uart_0_cfg[0x1]` write) — so the live socket/pty round-trip
dispatches. **No ucSim source change or rebuild is required.** (An earlier
attempt added a `set hardware uart check_often` sub-command to
`cl_serial_hw::set_cmd`; that was **reverted** — see the note below — because
the config-memory variable already provides the identical effect.) Verified by
`simulator/tests/test_issue004_fix.py` (Makefile `sim-issue004-fix`). The
pre-staged `-S in=<file>` path (`test_sim_roundtrip.py`) remains the
zero-config default.
**Upstream:** reported as ucSim issue
[#17](https://github.com/danieldrotos/ucsim/issues/17) (the maintainer's reply
confirmed the `uart0_check_often` configuration-memory route, so no `set` /
source change is needed).

## Auto-baud response across host speeds [SIM]

To characterise the receiver bring-up that precedes any command round-trip,
`simulator/tests/sim_autobaud_sweep.sh` (Makefile `sim-autobaud-sweep`) drives
the training byte `0x20` on P3.0 (via the `rxd` cl_hw pin driver) at a range of
bit times and reports whether the firmware software auto-detect LOCKS (reaches
`init_finish` 0x073C with `TH1=0xFC`, `TR1` set, `IE=0x17`).

Standard wire bauds (`cyc/bit = 11059200 / baud / 12`) — none land in this
model's window:

| baud | cyc/bit | result |
| ---: | ------: | :----- |
| 1200 | 768 | NO-LOCK |
| 2400 | 384 | NO-LOCK |
| 4800 | 192 | NO-LOCK |
| 9600 |  96 | NO-LOCK |

The model's actual accepted window (literal cyc/bit, `SWEEP_CYC="…"`): locks
**104..152 cyc/bit** (always deriving `TH1=0xFC`), refuses at 96 and 160:

| cyc/bit | result |
| ------: | :----- |
| 88, 96 | NO-LOCK |
| 104, 128, 152 | LOCK TH1=0xFC |
| 160, 168, 192 | NO-LOCK |

The absolute-baud vs machine-cycle/bit offset (nominal 9600 → 96 cyc/bit, just
below the ~128-centred window) is a **modelling artifact** of representing the
training edges in machine cycles — the firmware times them with Timer 0. The
meaningful, verified result is the *shape* of the auto-detect: a single narrow
accept window and one derived `TH1`. This is consistent with issue 003 (115200
≈ 8 cyc/bit is far outside the window and cannot lock). The lock point itself is
also asserted by `sim_serial_autobaud.sh` (128 cyc/bit).

### How precisely does the firmware reproduce standard bauds? [BYTE]

**It cannot hit them exactly, and — counter-intuitively — the error does NOT
shrink at lower baud rates.** The derivation at the end of the measure block
(`init.asm`, `baud_check`) is:

```
mov  A,R7      ; R7 = normalization multiplier
dec  A         ; A = R7 - 1
cpl  A         ; A = ~(R7-1)
mov  TH1,A     ; Timer-1 reload
```

`R7` starts at `1` and the normalize loop only ever does `R7 <<= 1` (`rlc A`),
so **R7 is always a power of two**. Therefore `TH1 = ~(2^n − 1)` and the Timer-1
reload `(256 − TH1)` is restricted to `{1, 2, 4, 8, 16, 32, …}`. With SMOD=0,
mode-1 UART (`baud = XTAL / (384 × (256−TH1))`) the only achievable bauds are a
**power-of-two ladder** `XTAL / (384 · 2^n)`:

| 256−TH1 | TH1 | baud (11.0592 MHz) |
| ------: | :-- | -----------------: |
| 1 | 0xFF | 28800 |
| 2 | 0xFE | 14400 |
| 4 | 0xFC | **7200** |
| 8 | 0xF8 | 3600 |
| 16 | 0xF0 | 1800 |
| 32 | 0xE0 | 900 |

#### Why the error is a CONSTANT RATIO, not a shrinking rounding error

For a *normal* UART you round the reload to the nearest integer, so a bigger
reload (lower baud) has finer resolution and **smaller** error — that is the
usual intuition. This firmware is different: it does not round the reload, it
**forces it to a power of two**. Both grids are then geometric with ratio 2:

```
standard series : 1200 2400 4800 9600 19200 38400   = 9600 · 2^k
firmware ladder :  900 1800 3600 7200 14400 28800   = 7200 · 2^k
```

The ladder is a *fixed multiple* of the standard series
(`7200/9600 = 3600/4800 = … = 0.75`). A fixed multiplicative offset stays
multiplicatively constant at every rate — it can never decay as the rate drops.
Hence the error is identical everywhere:

| standard | nearest reachable | TH1 | rel. error |
| -------: | ----------------: | :-- | ---------: |
| 1200 | 900 | 0xE0 | −25% |
| 2400 | 1800 | 0xF0 | −25% |
| 4800 | 3600 | 0xF8 | −25% |
| 9600 | 7200 | 0xFC | −25% |
| 19200 | 14400 | 0xFE | −25% |
| 38400 | 28800 | 0xFF | −25% |

#### Where the 0.75 comes from (it is CRYSTAL-dependent)

At 11.0592 MHz the *exact* reloads for the standard rates are **24, 12, 6, 3** —
i.e. `3 · 2^k`. The power-of-two ladder is missing the **factor 3**. The nearest
power of two to `3·2^k` is `4·2^k`, and a reload that is `4/3` too large yields
`3/4` the baud → a uniform **−25%**. So the magnitude of the offset is set by the
fractional part of `log2(exact_reload)`, which depends on the **crystal**, not on
the baud:

| crystal | exact std reloads | offset (all rates) |
| :------ | :---------------- | :----------------- |
| 11.0592 MHz (ROB3) | 24/12/6/3 = `3·2^k` | **−25%** |
| 12.288 MHz | 26.7/13.3/6.7/3.3 | −16.7% |
| (a crystal where std reloads are `2^k`) | … | ~0% |

For contrast, a *correct* fixed-baud setup at 11.0592 MHz uses `256−TH1` =
24/12/6/3 (`TH1` 0xE8/0xF4/0xFA/0xFD) to hit 1200/2400/4800/9600 **exactly** —
divisors the auto-detect's power-of-two normalization can never produce.

#### Provenance / caveat

- **[BYTE]** The reload is forced to a power of two (`TH1 = ~(2^n−1)`), so
  achievable bauds form the ladder `XTAL/(384·2^n)`.
- **Arithmetic** The error vs any standard rate is a *constant ratio* fixed by
  the crystal (−25% at 11.0592 MHz, because the exact reloads are `3·2^k`); it
  does **not** diminish at lower rates, because both grids scale by 2 together.
- **[SIM]** In this ucSim model every in-window training byte derives `TH1=0xFC`
  (div 4 → 7200), verified across the whole 104..152 cyc/bit window by
  `sim_autobaud_sweep.sh`. The firmware's own TX frame matches that TH1: the
  `0x15` ACK takes ~18408 clocks SBUF-write→TI ≈ 12 bit-times at 1536 clk/bit
  (7200 baud), so detect→TX are on one consistent clock.
- **Not established** that a *real* 9600 host lands specifically on the 7200
  rung — the sim represents the Timer-0 edge measurement in machine cycles, not
  true wire time. The power-of-two reload constraint (and therefore the
  constant-ratio error) holds regardless; which rung a given crystal/host
  selects is the part that needs a bench measurement.

## ROOT CAUSE (confirmed [SIM] + arithmetic)

A live socket/pty command frame (e.g. the all-axis query `0x4F 0x03`) does not
dispatch — the firmware replies `0xF1` — **because ucSim reads the two bytes
from the serial fd ~1.84M machine-cycles apart (it polls the fd only rarely
during a free `run`), which is longer than the firmware's 20-tick (~1.47M-cycle)
serial RX timeout. The timeout fires between the header and the ETX, resets the
RX state machine, and stages the `0xF1` reset-ACK; the ETX then arrives after
the frame flags are cleared and is mis-decoded as a fresh (invalid) "header".**

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

- Inter-byte gap measured: **~1,838,500 machine cycles** between the two bytes
  reaching SBUF (consistent across runs; e.g. 48192420 − 46353864 = 1,838,556).
- **This gap is NOT the UART baud timing.** The firmware's detected baud (after
  the `rxd` lock) is mode-1 with Timer-1 mode-2, TH1=0xFC → Timer-1 overflows
  every `(256−252)×12 = 48` cycles; mode-1 RX = 32 overflows/bit × 10 bits =
  **~15,360 cycles per byte**. So the UART, once a byte is in its one-byte input
  slot, clocks it to SBUF in ~15K cycles — 120× faster than the measured gap.
- **The gap is the host-fd POLL cadence.** Tracing `cl_serial_hw::proc_input`
  (the only place the socket fd is read) shows it is called only ~3 times for
  the whole exchange, and the two command bytes are *read from the socket*
  1,838,484 cycles apart — with the input slot FREE (`avail=0`) both times. So
  neither the UART nor the single-byte slot is the limiter: **ucSim simply polls
  the serial fd that rarely during a free `run`.** The byte sits in the OS
  socket buffer until the next poll.
- Firmware serial timeout: Timer 0 reloads `TH0:TL0 = 0xE811` → overflow every
  `0x10000−0xE811 = 6127` cycles → tick period **6127 × 12 = 73,524** cycles.
  `main.asm` reloads `SER_TIMEOUT` (IRAM `0x18`) to `0x14` (20) per received
  byte and does `djnz 0x18` once per serial tick (`0x23.7`). Expiry after
  **20 × 73,524 = 1,470,480** cycles.
- **1,470,480 (timeout) < 1,838,484 (fd-poll gap)** → the timeout always
  expires between the two polled bytes.

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
the timeout never expires. The problem is purely that ucSim's run-loop polls the
serial input fd far too infrequently during a free `run` (the ~1.84M-cycle gap
measured in `cl_serial_hw::proc_input`), so queued socket/pty bytes are picked
up slower than the firmware's RX timeout.

### Fix options

1. **Poll the serial input fd more often during `run`** — **THIS IS THE
   RESOLUTION.** ucSim already has a per-UART flag `serconf_check_often`
   (`core/sim.src/serial_hw.cc`): when set, `cl_serial::tick()` drains the host
   input fd (`io->input_avail()` → `io->proc_input(0)`) on **every serial tick**
   instead of waiting for the coarse `cl_app::run_go` poll, so queued socket/pty
   bytes are picked up well inside the firmware's ~1.47M-cycle RX timeout.

   The flag is registered as a named **configuration-memory** variable
   (`serial_hw.cc` does `uc->vars->add(pn+"check_often", …, serconf_check_often, …)`),
   so it is **toggleable at runtime on a stock ucSim 0.9.9+ with no source change
   and no rebuild**:

   ```
   expr uart0_check_often=1          # named variable (preferred)
   # or inspect/confirm:
   info variable often               # -> uart0_check_often  uart_0_cfg[0x1] = …
   info hardware uart[0]             # cfg cell 0x01 "Check input file at every cycle"
   ```

   > **Note — the `set hardware uart check_often` patch was REVERTED.** An
   > earlier attempt added a `set_cmd` sub-command (mirroring `raw`) to expose
   > this flag; it is unnecessary because the config-memory variable above
   > already provides the identical effect on a stock build. The patch file
   > `REVERTED-fix-check_often-set_cmd.patch` is kept only for historical
   > reference and is **not applied**. ucSim maintainer confirmation (upstream
   > issue [#17](https://github.com/danieldrotos/ucsim/issues/17)): *"You don't
   > have to
   > modify the `set` command as this function can be set via configuration
   > memory … `expr uart0_check_often=1`."*

   Verified: a live `-S port=` round-trip of `0x4F 0x03` returns a dispatched
   all-axis frame (`… 4f 8c 93 b1 8a 87 40 03`) once `uart0_check_often=1`,
   instead of the timeout `0xF1` — see `simulator/tests/test_issue004_fix.py`.
   **No UART-timing or firmware change.**

2. **Drive command bytes under `step`** (what `test_sim_roundtrip.py` does), so
   few firmware cycles pass between bytes — reliable with a **stock** ucSim, no
   rebuild. This stays the default for `make test`.
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
