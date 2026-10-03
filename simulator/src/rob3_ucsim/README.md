# rob3_ucsim

ROB3-specific **ucSim simulation harness** (pure Python). Drives the ROB3 8031
firmware in Daniel Drotos' µCsim (`ucsim_51` / `s51`) and exposes the firmware's
state through a small, ROB3-aware API — it knows this firmware's memory
landmarks (per-axis targets/positions/feedback, the 8255 motor ports, the
main-loop entry) and its `cl_hw` peripherals (teachbox, adc).

It is meant to be used **alongside** the
[`rob3`](https://github.com/eurobtec/rob3_py) RS-232 protocol library: bring the
ROM up in ucSim with `UCSimEngine`, then drive/inspect it with `rob3`'s codec,
calibration, and `Rob3Client`.

> This package lives inside the ROB3 firmware repo (`simulator/`) on purpose:
> it drives *this* ROM and its `cl_hw` modules, which sit next to it in
> `../firmware/` and `../ucsim-modules/`. The behavioral `tests/*.sh`, the GUI/
> CLI app (`harness/gui/`), and the compiled `.so` modules stay in the repo; this
> package is just the reusable Python harness library extracted from them.

## Install

```bash
pip install -e simulator        # from the firmware repo root
# or:  cd simulator && pip install -e ".[dev]"
```

Pure standard library — no runtime dependencies. You need a `ucsim_51` / `s51`
binary on `PATH` (or via the `UCSIM_51` env var); the interactive engine also
wants the ROB3 `cl_hw` `.so` modules (`../ucsim-modules/`) for the
teachbox/adc commands.

## API

| Symbol | What it is |
| :----- | :--------- |
| `UCSimEngine` | Persistent `ucsim_51`-over-pty driver with ROB3 landmarks: `reset()`, `run_to(addr)`, `run_cycles(n)`, `press(row,group)`/`release()`, `push_pot(ch,v)`, `read_positions()`/`read_targets()`/`read_ports()`, `set_iram()`. |
| `UCSimBatch` | One-shot batch driver: run a script of ucSim commands, parse the output. Deterministic (re-seed state each call). |
| `Plant` | The motor/pot physics that live *outside* ucSim (no ucSim dependency): decode the 8255 Port A/C motor bits and integrate pot positions. Unit-testable; reusable behind a socket bridge to ROS 2 / Gazebo. |
| `MAIN_LOOP`, `IRAM_TARGET`, `IRAM_CURPOS`, `IRAM_FEEDBK`, `XRAM_PORT_A`, `XRAM_PORT_C` | Verified firmware landmarks. |
| `find_ucsim()`, `default_hex()` | Locate the simulator binary / the ROM image. |

## Usage

### Drive the firmware in ucSim

```python
from rob3_ucsim import UCSimEngine, MAIN_LOOP

eng = UCSimEngine()                 # finds ucsim_51/s51 + the ROM
eng.reset()
eng.run_to(MAIN_LOOP)               # run past the init gates to the main loop
print("positions:", eng.read_positions())
print("targets  :", eng.read_targets())
eng.close()
```

### Together with the `rob3` protocol library

```python
from rob3_ucsim import UCSimEngine, MAIN_LOOP
from rob3 import protocol as P, Calibration

eng = UCSimEngine(); eng.reset(); eng.run_to(MAIN_LOOP)
counts = [c & 0xFF for c in eng.read_positions()]
joints = Calibration().counts_to_joints(counts)         # counts -> rad/m
frame  = P.set_all_positions(counts)                    # the RS-232 frame
eng.close()
```

### Environment variables

| Var | Meaning | Default |
| :-- | :------ | :------ |
| `UCSIM_51` | path to a loader-enabled `ucsim_51` | PATH lookup, then stock `s51` |
| `ROB3_HEX` | ROB3 ROM image | `../firmware/hex/M2764A@DIP28.HEX` |

## Relationship to the other repos

- **`rob3` firmware repo (this one):** the ROM, annotated source, `cl_hw`
  modules, and the behavioral `tests/*.sh` this harness supports.
- **[rob3_py](https://github.com/eurobtec/rob3_py):** the RS-232 protocol
  library — use it with this harness.
- **[pyucsim](https://github.com/eurobtec/pyucsim):** the *generic*,
  firmware-agnostic ucSim Python client. `rob3_ucsim` is the ROB3-specialized
  counterpart (it knows this firmware's addresses); a future version may build
  on `pyucsim` instead of its own pty driver.

## License

MIT.
