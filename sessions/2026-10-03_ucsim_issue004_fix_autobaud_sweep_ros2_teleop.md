# 2026-10-03 — ucSim issue 004 FIXED (check_often), auto-baud precision sweep, and live ROS 2 teleop against the firmware in ucSim

Follow-on to the earlier same-day issue-004 root-cause session. This one
**fixes** issue 004 in ucSim, measures the firmware's software auto-baud across
host speeds (finding a structural standard-baud error), and proves a **live**
ROS 2 teleop round-trip (JointJog → driver → firmware in free-running ucSim) —
the hardware-style serial path that the root-cause bug had blocked. All three
repos (ucSim fork, this repo, the ROS 2 driver) were committed and pushed.

## ucSim issue 004 — FIXED via the existing `check_often` flag [SIM]

The root cause (from the prior session) is a **host-fd poll-cadence** mismatch:
during a free `run`, ucSim drains the serial input fd only ~1.84M machine-cycles
apart, which is longer than the firmware's ~1.47M-cycle serial RX timeout, so a
multi-byte command frame times out between the header and the ETX and the
firmware idle-replies `0xF1`.

ucSim already had the right mechanism — a per-UART `serconf_check_often` flag
that makes `cl_serial::tick()` drain the fd on **every** serial tick — but it
was default-false with **no console/CLI way to enable it**. The fix adds one
handler to `cl_serial_hw::set_cmd` (mirroring the existing `raw` sub-command):

```
set hardware uart check_often 1
```

> **UPDATE 2026-10-07 — this `set_cmd` patch was REVERTED.** The ucSim
> maintainer pointed out the flag is already a named **configuration-memory**
> variable (`uc->vars->add(pn+"check_often", …)`), so it is settable on a stock
> 0.9.9+ build with **no source change and no rebuild**:
> `expr uart0_check_often=1` (equivalently a direct `uart_0_cfg[0x1]` write).
> Commit `02b7ec79` was reverted (`c927fcaa`) and the eurobtec ucSim rebuilt;
> the tests now use `expr uart0_check_often=1`. Patch kept for history at
> `simulator/issues/004-*/REVERTED-fix-check_often-set_cmd.patch`. The behaviour
> below is identical either way — only the toggle mechanism changed.

- **ucSim commit** `02b7ec79` on `razr/ucsim` branch `feature/loadable-hw-plugins`
  (pushed). Patch mirrored at
  `simulator/issues/004-*/fix-check_often-set_cmd.patch`.
- **Verified [SIM]:** a live `-S port=` TCP round-trip of the all-axis query
  `0x4F 0x03` now returns a dispatched frame (`… 4f 8c 93 b1 … 40 03`) instead
  of the timeout `0xF1`. Without the flag the bug reproduces (F1-only).
- Default stays false; stock behaviour unchanged unless explicitly enabled.

### Why nobody hit it before (recorded, since it was confusing)
Three escape hatches must ALL be defeated at once: (1) impossible on real
hardware — at the locked baud two bytes are ~ms apart, ~50× inside the firmware
timeout (which exists to recover from a host that *stops* mid-frame); (2) the
normal `-S in=<file>` path is baud-paced so bytes are always ready; (3) you must
do a **live, async, multi-byte round-trip under a free `run`** — exactly what a
hardware-style ROS driver does and almost nothing else does. So it's a ucSim
run-loop artifact, never a firmware/HW bug.

## Firmware auto-baud across host speeds — a structural standard-baud error [BYTE]

New reusable sweep `simulator/tests/sim_autobaud_sweep.sh` (`sim-autobaud-sweep`)
drives the training byte on P3.0 (via `rxd`) at a range of bit times and
asserts whether the firmware auto-detect LOCKS (reaches `init_finish` 0x073C
with TH1=0xFC, TR1, IE=0x17).

- **This ucSim model locks for cyc/bit ∈ [104,152]** (always deriving TH1=0xFC),
  refusing at 96 and 160; none of the standard wire bauds (1200→768 … 9600→96
  cyc/bit) land in the window — a modelling artifact of representing the
  Timer-0 edge measurement in machine cycles. [SIM]
- **Structural finding [BYTE]:** the derivation `TH1 = ~(R7−1)` with `R7` a
  power of two (the normalize loop only `<<`s) forces the Timer-1 reload
  `(256−TH1)` onto `{1,2,4,8,16,…}` → achievable bauds are the ladder
  `XTAL/(384·2^n)` = 28800/14400/**7200**/3600/… So standard rates can only be
  **approximated to the nearest 2^n rung**, never generated exactly.
- **Why the error is a CONSTANT RATIO (not a shrinking rounding error):** both
  the standard series (`9600·2^k`) and the ladder (`7200·2^k`) are geometric
  ratio-2, so the mismatch is a fixed multiplicative offset identical at every
  rate. At 11.0592 MHz the exact std reloads are `3·2^k` (24/12/6/3); the
  nearest 2^k is `4·2^k` → 4/3 too large → 3/4 the baud → uniform **−25%**. The
  magnitude is crystal-dependent (−16.7% at 12.288 MHz, ~0% where std reloads
  are powers of two).
- **Both sides consistent [SIM]:** measured the firmware's own TX frame of the
  `0x15` ACK = 18408 clocks SBUF-write→TI ≈ 12 bit-times at 1536 clk/bit
  (7200 baud) — detect→TX share the one Timer-1 clock; the `rxd` module sends at
  exactly the cyc/bit it is given (no hidden bias). The core RX path is
  Timer-1-clocked too (`serial.cc` mode-1 `_divby=32`).

Full write-up in `simulator/issues/004-*/README.md`.

## Live ROS 2 teleop against the firmware in ucSim [SIM]

With the fix in place, the **real** `rob3_driver` talks to the firmware over a
live serial link — the same path it uses for the real robot — and a teleop jog
moves the simulated arm:

- `simulator/tests/verify_ros2_driver_live.py` (`sim-ros2-live`): the driver's
  own protocol codec + `SerialTransport` round-trip the all-axis query over a
  live pty (socat or a Python pty-relay). Parses 6 positions.
- `rob3_ros2_driver/.../test/test_teleop_ucsim.py` + host runner
  `simulator/tests/sim_teleop_ros2.sh` (`sim-teleop-ros2`): launches the real
  node inside the `rob3-ros2:lyrical` image, ucSim (host binary) **free-running**
  on a pty-relay, publishes `control_msgs/JointJog`, and asserts the jog reaches
  the firmware — **+jog moved ONLY the jogged axis to the calibrated count
  (147→103) and the firmware ACKed; −jog reversed direction** (respecting the
  axis's inverse count↔angle calibration); the live link stayed healthy.
  Runs in ~20 s with a global watchdog; skips cleanly without the image/binary.

Harness lessons re-learned here: ucSim on a pipe does **not** re-emit its prompt
per command (read on output-idle, not a prompt token — this cut bring-up from
~75 s to ~3 s); pty relays must put the slaves in **raw** mode (else TX echoes
back and frames garble); and the jog callback is async (poll `_last_counts`
until it changes, don't fixed-sleep).

## Docs synced to the fix
Removed the now-obsolete "socket drops frames / live pty not reliable" notes
across the driver repo (`transport.py`, `scripts/sim_bringup.py`, `README.md`,
`docs/SIMULATION.md`, `test/test_sim_roundtrip.py`); `sim_bringup.py` now issues
`set hardware uart check_often 1` after lock. Fixed the `make help` regex so
digit-named targets (`sim-issue004-fix`, `sim-ros2-live`, `sim-teleop-ros2`,
`sim-serial-e2e`) are listed.

## Commits pushed
- **ucSim** (`razr/ucsim`, `feature/loadable-hw-plugins`): `02b7ec79` — the
  `check_often` runtime command.
- **This repo** (`razr/rob3`, `main`): `0945639` — issue-004 fix patch +
  README, auto-baud sweep, issue-004 live-socket test, ROS2 live/teleop tests,
  Makefile targets + help fix.
- **ROS 2 driver** (`eurobtec/rob3_ros2_driver`, `master`): `e0586d0` — teleop
  test, `sim_bringup.py` check_often, corrected sim docs.

## Provenance
- `check_often` fix behaviour + live socket/pty/teleop round-trips — [SIM] on
  the rebuilt `ucsim_51`.
- Power-of-two reload ladder and the constant-ratio standard-baud error —
  [BYTE] (`init.asm` derivation) + arithmetic; the specific lock window / 7200
  rung is [SIM] (machine-cycle modelling of the Timer-0 edge measurement).
- TX frame timing (18408 clk ≈ 12 bit-times) — [SIM].
