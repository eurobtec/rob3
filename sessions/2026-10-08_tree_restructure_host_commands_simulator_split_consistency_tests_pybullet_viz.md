# 2026-10-08 — Firmware tree restructure, host-command language + symbolization, simulator → rob3_ucsim, consistency tests, PyBullet/text visualization

A multi-repo session touching `eurobtec/rob3`, `eurobtec/rob3_ucsim`, and
`eurobtec/tbps_compiler`. Themes: tidy the firmware source tree and its include
files, give the RS-232 host command set a symbolic definition the interpreter
and tests actually use, relocate the behavioral simulator to its own repo, add
firmware-consistency tests, and build a visualization layer (PyBullet + terminal)
driven by the live firmware.

## tbps_compiler — arch/board split + shared ISA + provenance upgrades

- Split the AOT backend into layers: `arch.py` (`MCS51`/8031 CPU idioms, TIM
  djnz wait, P1 bits, scratch) + `board.py` (`ROB3`: POS/OUT/POS-store bindings),
  orchestrated by `backend.py` (renamed from `native.py`). Emitted code is
  byte-identical to before. CLI drops `--native`; compiled output is selected by
  `--arch` (default = bytecode). A future CPU is a new `Arch`, no new flag.
- `tbps_isa.inc` holds ONLY the TBPS instruction set; the firmware RAM map /
  routines / SRAM store moved to `rob3_firmware.inc` / `rob3_sram.inc` /
  `mcs51_scratch.inc` (TIM counters are generic 8031 scratch, not firmware).
- Upgraded TIM/OUT/GOTO operand-ordering tags `[INFER] → [SIM]`, verified by
  running each through the real ROM (`tests/test_sim_ucsim.py`). POS-store
  pot-capture semantic + DEL. meaning stay `[INFER]`.
- Stripped cross-repo `firmware/src/annotated/...` paths and hardcoded home
  paths from docs/tests (`<path-to-...>` placeholders).

## rob3 firmware — shared ISA, interpreter-only file, host command set

- The firmware now shares a VERBATIM copy of `tbps_isa.inc` with the compiler
  (single source of truth); the internal interpreter uses its symbols.
- `program.asm` → `tbps_interpreter.asm` (interpreter only); the main-loop motion
  gate (0x0900–0x0940) split out to `motion_exec.asm`; `inc/program.inc` →
  `inc/tbps_interpreter.inc` (workspace + routine entries).
- New `inc/host_commands.inc` — the ROB3 **host command set** (bit fields,
  class-0 keywords, composed/all-axes bytes, system class, digital-input
  selectors, ETX, the 0xFx status/ACK family). RS-232 is only the transport.
  `serial.inc` trimmed to workspace.
- Symbolized the command processor (`rs232.asm`/`init.asm`/`main.asm`) to use
  `CMD_ETX`/`ACK_*` — byte-identical (ACC bit-addresses + coincidental masks
  left as literals).
- `inc2sh.py` — converts an sdas `.inc` to a bash-sourceable file; `sim_serial.sh`
  sources the generated `host_commands.sh` and sends symbolic commands.
- Golden byte-match holds throughout (SHA `1e94419d…`).

## rob3 firmware — tree restructure

- `firmware/src/annotated/` → `firmware/src/` (the assembling source is now the
  main tree). Originals quarantined under `firmware/legacy/`: `legacy/src/main.asm`
  (raw disasm51), `legacy/bin/`, `legacy/hex/`. All build/test/doc paths repathed;
  golden match verified at the new location.

## simulator → eurobtec/rob3_ucsim

- Moved the entire `simulator/` tree (tests, cl_hw module sources, harness,
  issues) out of `rob3` into the standalone `rob3_ucsim` repo, **decoupled from
  the firmware source**: the ROM is an input via `ROB3_HEX` (any image, no
  `../firmware`); `host_commands.sh` is a vendored copy; the golden-`verify`
  delegate dropped (it stays a firmware-repo concern). `make test` → ALL TESTS
  PASSED against the ROM.

## rob3 firmware — consistency test suite

- New `firmware/tests/test_firmware_consistency.py` (`make -C firmware/src test`):
  golden byte-match (`make verify`), per-region match (`make status`), and a
  golden SHA pin on both the built image and the reference ROM (catches an
  accidental ROM swap). Toolchain-only, no ucSim; 4 passed.

## rob3_ucsim — visualization (PyBullet + terminal) + keyboard-teachbox

- URDF `rob3.urdf` (+ `.xacro`) imported and packaged; `urdf/meshes/` + a README
  document the STL/CAD swap (`<mesh>` refs, mm→m scale) for later CAD.
- Viewer frontends behind a `Viewer` protocol, `rob3-viz --backend <name>`:
  - `text` — terminal: per-axis byte, joint value (deg/mm), min..max, ASCII bar.
  - `pybullet` — 3D URDF window, native orbit camera (`[viz]` extra).
  - shared `axes.py` byte→joint mapping; loads adc+loopback so the servo runs.
- `rob3-teachbox` — keyboard input driver using the authoritative keypad mapping
  + debounce from the `rob3-firmware-sim` skill (`index = row+1+(group-1)*8`;
  axis-select = group 1 rows 1..6; release→hold→release). Verified vs the ROM:
  axis-select → POSITION (`0x29=0x40`); jog → `0x50+N` moves (via `kh_jog`).
  Own-engine or attach-to-shared-ucSim (`--console-port`) modes. Full POS value
  entry is the documented open follow-up.

## Housekeeping

- Standardized tooling paths to the `$HOME/github/eurobtec/<repo>` convention in
  scripts/tests/docs (no hardcoded personal paths; `github.com` URLs preserved).
  `.kiro/settings/mcp.json` is machine-local (left; stale `razr`→`eurobtec` fixed).

## Verification

- Firmware golden byte-match: PASS (SHA unchanged) across all restructures.
- `firmware/tests`: 4 passed. `rob3_ucsim` behavioral suite: ALL TESTS PASSED.
- `tbps_compiler`: 70 passed, 1 skipped (ROM-dependent) against the real ROM.
- Visualization: both viewers render live firmware positions; keyboard-teachbox
  axis-select + jog verified against the ROM.

Pushed: `rob3` (main), `rob3_ucsim` (master), `tbps_compiler` (main).
