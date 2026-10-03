"""rob3_ucsim — ROB3-specific ucSim simulation harness (pure Python).

Drives the ROB3 8031 firmware in Daniel Drotos' µCsim (``ucsim_51`` / ``s51``)
and exposes the firmware's state through a small, ROB3-aware API. It knows this
firmware's memory landmarks (per-axis targets/positions/feedback, the 8255
motor ports, the main-loop entry) and its ``cl_hw`` peripherals (teachbox, adc),
so you can press keys, push pot values, run a bounded number of cycles, and read
back the servo state — all from Python.

Designed to be used *alongside* :mod:`rob3` (the RS-232 protocol library): e.g.
seed the firmware in ucSim with :class:`UCSimEngine`, then exercise the serial
command path with ``rob3.Rob3Client`` over the same simulated controller.

Components:
  * :class:`UCSimEngine` — persistent ``ucsim_51``-over-pty driver with ROB3
    landmarks (interactive: press/run/read, uses the compiled cl_hw modules).
  * :class:`UCSimBatch`  — one-shot batch driver (run a script, parse output).
  * :class:`Plant`       — the motor/pot physics that live outside ucSim
    (no ucSim dependency; unit-testable, reusable behind a socket bridge).

The ROM image and the ``cl_hw`` ``.so`` modules live in the firmware repo
(``../firmware`` and ``../ucsim-modules`` relative to this package); the engine
locates them by default and honours the ``ROB3_HEX`` / ``UCSIM_51`` env vars.

Typical use::

    from rob3_ucsim import UCSimEngine, MAIN_LOOP

    eng = UCSimEngine()
    eng.reset()
    eng.run_to(MAIN_LOOP)
    print(eng.read_positions())
    eng.close()
"""
from __future__ import annotations

from .batch import UCSimBatch
from .engine import (
    IRAM_CURPOS,
    IRAM_FEEDBK,
    IRAM_TARGET,
    MAIN_LOOP,
    XRAM_PORT_A,
    XRAM_PORT_C,
    UCSimEngine,
    default_hex,
    find_ucsim,
)
from .plant import N_AXES, MotorCommand, Plant

__all__ = [
    "UCSimEngine",
    "UCSimBatch",
    "Plant",
    "MotorCommand",
    "N_AXES",
    "find_ucsim",
    "default_hex",
    "MAIN_LOOP",
    "IRAM_TARGET",
    "IRAM_CURPOS",
    "IRAM_FEEDBK",
    "XRAM_PORT_A",
    "XRAM_PORT_C",
]

__version__ = "0.1.0"
