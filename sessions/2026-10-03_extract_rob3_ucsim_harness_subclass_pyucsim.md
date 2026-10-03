# 2026-10-03 — Extract the simulation harness into rob3_ucsim (subclass of pyucsim)

Follow-on to the `rob3_py` extraction earlier the same day. The reusable Python
simulation harness (`UCSimEngine` + `Plant` + `UCSimBatch`) was lifted out of
`simulator/harness/` into its own repo and rebuilt on `pyucsim`. Unlike the
`rob3_py` work, this one **does** change this firmware repo (the harness library
left; the behavioral tests, GUI/CLI, and `cl_hw` modules stayed and now consume
the external package).

## New sibling repository

- **[eurobtec/rob3_ucsim](https://github.com/eurobtec/rob3_ucsim)** — the
  ROB3-specific ucSim simulation harness, pip-installable, `src/` layout, MIT.
  - **`UCSimEngine` subclasses `pyucsim.UCSimEngine`.** The generic
    ucSim-over-pty transport (process lifecycle, `command`/`step`/`run`/
    `load_hw`/`close`, context manager, the `@`-filename and `run`-vs-`step`
    gotchas) is **inherited**; the subclass adds only the ROB3 layer: firmware
    landmarks (`MAIN_LOOP`, per-axis target/pos/feedback IRAM, 8255 ports),
    `reset(fixed_baud=)`, `run_to`, `run_cycles`, `press`/`release`,
    `push_pot`/`push_pots`, `read_positions`/`read_targets`/`read_ports`,
    `set_iram`, and a `cmd` alias. This removes the hand-rolled pty/prompt loop
    that duplicated `pyucsim` (the duplication flagged in
    `simulator/USING_UCSIM_MCP.md`).
  - Also ships `UCSimBatch` (one-shot batch driver) and `Plant` (the motor/pot
    physics model, no ucSim dependency).
  - Depends on `pyucsim` (git; not on PyPI), Python ≥ 3.10. `tests/test_plant.py`
    (5 pass). The ROM and `cl_hw` `.so` modules are supplied by the firmware repo
    via `ROB3_HEX` / `load_hw=` (pyucsim's `safe_image` handles the `@`).

## Changes in THIS repo

- **Harness library removed from `simulator/`.** It had briefly lived in-repo as
  `simulator/src/rob3_ucsim/` (commit `dbf5a18`); that in-repo copy and
  `simulator/pyproject.toml` are removed — the package is external now.
- **GUI/CLI + the teachbox test consume the external package.**
  `harness/gui/{cli,gui}.py` and `tests/test_teachbox_axis_select.py` import
  `rob3_ucsim`; the test **skips cleanly** if it is not installed.
- **Makefile:** `sim-teachbox-axis` now passes `ROB3_HEX=$(SAFEHEX)` (the engine
  no longer defaults the ROM to a firmware-relative path).
- **Docs:** `simulator/README.md`, `simulator/harness/README.md`, and the
  top-level `README.md` point at `eurobtec/rob3_ucsim` with install
  instructions; `.gitignore` trimmed to build + Python tooling artifacts.

## Design note: why a subclass (not a wrapper)

`rob3_ucsim`'s engine *is* a ucSim engine with extra knowledge, so subclassing
`pyucsim.UCSimEngine` is the right relationship: the transport is inherited
unchanged and only ROB3 behaviour is added/overridden (`reset` takes a
`fixed_baud` flag; `run_to`/`run_cycles` are thin wrappers over inherited
`run`/`step`). The constructor resolves ROB3 defaults (binary via `find_ucsim`,
ROM via `ROB3_HEX`, `-t 51`, optional `-z/-b` console, auto-`loadhw`) then calls
`super().__init__(...)`.

## Verification [SIM]

- `UCSimEngine` is confirmed a subclass of `pyucsim.UCSimEngine`; `pip install`
  pulls `pyucsim` from git; the 5 `Plant` tests pass.
- The engine drives the **real ROM** to `MAIN_LOOP` through the inherited
  `pyucsim` transport, loads the ROB3 `cl_hw` modules (`has_modules=True`), and
  interops with `rob3` (sim counts → `Calibration` joints → `protocol`
  set-all-positions frame).
- **This repo's `tests/test_teachbox_axis_select.py` passes against the real ROM
  using the external `rob3_ucsim`** — the full chain `rob3` test → `rob3_ucsim`
  (subclass) → `pyucsim` (transport) → ucSim → ROM.

## Provenance
- Subclass/interop/behaviour verified by running the real ROM in ucSim — [SIM].
- `Plant` physics — unit tests ([no-HW]).
- The firmware ROM and its golden byte-match are untouched; only the harness
  packaging and the tests/docs that call it changed.
