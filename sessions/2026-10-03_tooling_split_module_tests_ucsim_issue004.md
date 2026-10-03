# 2026-10-03 — Tooling split (pyucsim / ucsim-mcp / rob3_ros2_driver), teachbox-module test fixes, and ucSim serial issue 004 root cause

A tooling + packaging session (mostly outside this repo) plus two concrete
changes here: fixing the module-dependent sim tests to `loadhw` the runtime
plugins, and a deep investigation of why the ROS 2 driver can't do a live serial
command round-trip against ucSim — which ended in a confirmed, correctly-scoped
root cause (ucSim issue 004).

## New sibling repositories (extracted from this project)

- **[eurobtec/pyucsim](https://github.com/eurobtec/pyucsim)** — a zero-dependency
  Python client library for µCsim (persistent `ucsim_*` process over a pty,
  `@`-filename workaround, `step`-vs-`run`, `loadhw`). Generalised from the
  ROB3 harness engine.
- **[eurobtec/ucsim-mcp](https://github.com/eurobtec/ucsim-mcp)** — a FastMCP
  MCP server built on `pyucsim` (20 tools: sessions, memory, step/run,
  breakpoints, `loadhw`, raw command). Verified end-to-end against this ROM.
- **[eurobtec/rob3_ros2_driver](https://github.com/eurobtec/rob3_ros2_driver)** —
  the ROS 2 driver, lifted out of this repo's `ros2/` tree (now removed here).
  Serial-only (TCP transport dropped), + a `JointJog` teleop interface and
  keyboard jog node, a reproducible `rob3-ros2:lyrical` Docker image, and a
  self-contained fake-robot teleop demo. See `simulator/USING_UCSIM_MCP.md`.

## Changes in THIS repo

### Module tests now `loadhw` the runtime `.so` plugins [SIM]
`sim_adc.sh`, `sim_teachbox_module.sh`, and `test_teachbox_axis_select.py`
assumed the teachbox/adc models were *compiled into* `ucsim_51`; they are
runtime plugins now. They resolve `../ucsim-modules/<name>/<name>.so` and
`loadhw` it in the probe + every script. With the custom `ucsim_51` all three
pass (teachbox strobe decode, ADC EOC→servo feedback, axis-select → POSITION
mode); on stock `s51` they skip cleanly. `make test` stays green either way.

### `ros2/` removed; driver lives in its own repo
`git rm -r ros2/` (20 files). README (status bullet + layout tree) and the
`rob3-ros2-driver` skill updated to point at `eurobtec/rob3_ros2_driver`, note
the serial-only transport + `JointJog` teleop, and fix test-path references.
Session logs keep their historical `ros2/` paths.

## ucSim issue 004 — live serial command round-trip (ROOT CAUSE FOUND) [SIM]

**Symptom:** with the ROM auto-baud-locked via the `rxd` plugin and a driver
connected over `-S port=`/pty, a command frame (query `0x4F 0x03`) never
dispatches — the firmware always replies `0xF1` (idle reset-ACK).

**Three successive diagnoses — the first two were WRONG; recorded so the dead
ends aren't repeated:**

1. *"ucSim drops/garbles RX bytes over sockets."* **Wrong — test-harness
   artifact.** Driving the sim through a *scripted pty command console* bypassed
   the normal `cl_app::run_go → cl_commander::proc_input` input-polling loop, so
   the serial fd was never pumped. A FIFO patch to `cl_serial_hw` was prototyped
   and **reverted**.
2. *"The firmware RX path is broken after auto-baud."* **Wrong.** Instrumenting
   `cl_serial::received` under a *normal* invocation shows **both** bytes reach
   `SBUF` with clean RI edges — the UART-over-socket is correct.
3. **Correct, confirmed [SIM] + arithmetic:** it's a **timing** mismatch, and
   specifically a **host-fd poll-cadence** one — NOT the UART baud and NOT the
   one-byte RX slot.
   - Tracing `cl_serial_hw::proc_input` (the only place the socket fd is read):
     it is called only ~3× for the whole exchange, and the two command bytes are
     *read from the socket* **~1,838,484 cycles apart** — with the input slot
     FREE both times. So ucSim simply polls the serial fd that rarely during a
     free `run`; the byte waits in the OS buffer.
   - The firmware's serial RX timeout is `SER_TIMEOUT(0x18)=0x14` ticks ×
     Timer-0 period `(0x10000−0xE811)×12 = 73,524` cyc = **1,470,480 cyc**.
   - **1,470,480 (timeout) < 1,838,484 (fd-poll gap)** → the timeout fires
     between the header and the ETX. `main.asm` then `anl 0x24,#0xF0` (wipes the
     RX frame flags) + stages `0xF1`; the ETX arrives with `0x24.0` cleared and
     is mis-decoded as a new header. `rx_payload` (0x0354) / `rx_dispatch`
     (0x03A9) are never reached. (The detected sim baud is ~7200 /
     TH1=0xFC → ~15,360 cyc/byte, far under the timeout — so the UART is not the
     limiter.)

**Why `-S in=<file>` works:** it is driven under `step` (few firmware cycles
between bytes), so the timeout never expires. Real hardware works at the true
baud for the same reason. The reliable ucSim contract is therefore the
pre-staged file round-trip (`rob3_ros2_driver` `test/test_sim_roundtrip.py`).

**Fix direction (not applied):** poll the serial input fd more often in
`cl_app::run_go` (the `commander->proc_input()` cadence), or drive command bytes
under `step`. ucSim is left **unmodified**.

Full write-up + numbers: `simulator/issues/004-async-serial-rx-dropped-or-garbled/`.

## Provenance
- Module behaviours re-verified in ucSim with the plugins loaded — [SIM].
- Issue-004 byte/RI/tick measurements from instrumented ucSim runs — [SIM];
  firmware timeout path is [BYTE] (`main.asm`). ucSim debug instrumentation was
  reverted; the binary is the stock build.
