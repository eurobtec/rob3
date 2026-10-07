# simulator

Behavioral simulation and verification assets for the ROB3 firmware. Driven by
the `Makefile` in this directory (`simulator/Makefile`). It reads the ROM image
and annotated sources from `../firmware/`.

For prerequisites see `../firmware/INSTALL.md`; for the full build/test workflow
and the rationale behind the tests see `BUILD.md` (in this directory). This file
just documents what lives in this directory.

> **Golden byte-match moved.** The assembled-source-vs-ROM check now lives with
> the annotated source at `../firmware/src/` (its `make verify` builds
> the whole 8 KB image and `cmp`s it against the ROM). This directory's
> `make verify` delegates there; the per-region `.a51` transcriptions and
> `gen_init.py` were removed.

## Contents

| Path | Kind | Description |
| :--- | :--- | :---------- |
| `tests/*.sh`, `tests/*.py` | tests | Behavioral: run the real ROM in ucSim and assert runtime state matches the annotated `.asm`. |
| `tests/README.md` | doc | Per-test detail: assertions, injected stimuli, standalone run, reading failures. |
| `ucsim-modules/` | sources | Loadable `cl_hw` peripherals (teachbox / adc / loopback / rxd) for the opt-in tests. |
| `harness/gui/` | tools | Interactive GUI + CLI apps (use the external `rob3_ucsim` package). |
| `build/` | generated | Shell-safe HEX copy (`rob3.hex`) and sim scratch. Created by `make`; removed by `make clean`. |

## Python harness package (`rob3_ucsim`) — now a separate project

The reusable Python harness (`UCSimEngine`, `UCSimBatch`, `Plant` + firmware
landmarks) lives in its own repository,
[**eurobtec/rob3_ucsim**](https://github.com/eurobtec/rob3_ucsim). It is built
on [`pyucsim`](https://github.com/eurobtec/pyucsim) (its `UCSimEngine` subclasses
`pyucsim.UCSimEngine`) and is designed to be used together with the
[`rob3`](https://github.com/eurobtec/rob3_py) RS-232 protocol library.

The GUI/CLI under `harness/gui/` and the `tests/test_teachbox_axis_select.py`
black-box test import it; install it first:

```bash
pip install git+https://github.com/eurobtec/rob3_ucsim.git
# point it at this repo's ROM:
export ROB3_HEX="$PWD/../firmware/legacy/hex/M2764A@DIP28.HEX"
```

The behavioral `tests/*.sh`, the GUI/CLI apps, and the `cl_hw` `.so` modules stay
in this repo (they verify this ROM in place).

## How it fits together

```
../firmware/src/  --(make -C ... verify)-->  8 KB image  ==  ../firmware/legacy/bin/M2764A@DIP28.BIN   <- golden (make verify, delegated)

../firmware/legacy/hex/M2764A@DIP28.HEX --(copied)--> build/rob3.hex --(s51)--> tests/*.sh   <- behavioral (make sim-*)
```

## Quick use

From the `simulator/` directory:

```bash
make verify     # golden byte-match (delegates to ../firmware/src)
make sim-init   # behavioral: the ADC-gated stall
make sim-run    # behavioral: run past the gates into the main loop
make test       # golden + all behavioral tests
make help       # list every target
```

## Notes / gotchas

- **Shell-safe HEX.** The shipped image `../firmware/legacy/hex/M2764A@DIP28.HEX` has
  an `@` in its name. The Makefile copies it to `build/rob3.hex`; simulator
  commands use that copy. Don't pass the `@` path directly to `s51`.
- **ucSim models the CPU core only** — no 8255 / ADC / SRAM / 74LS138 on stock
  `s51`. That is why `sim_run.sh` injects stimuli (an ADC-EOC/INT1 toggle and
  forcing `P3.0=0`) to get past the hardware-dependent gates; those injections
  are test scaffolding, documented inline in the script. The opt-in tests use
  the compiled `cl_hw` modules (`ucsim-modules/`) instead of injection.
