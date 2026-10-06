"""ROM-faithful compiler for the ROB3 Teach Box Programming System (TBPS).

The byte encoding emitted here is derived from the ROB3 8031 firmware
(``firmware/src/annotated/program.asm`` + ``rs232.asm``) and is intended to be
verified against the real ROM in ucSim.  See :mod:`tbps_compiler.isa` for the
provenance-tagged encoding reference.
"""

from __future__ import annotations

from .compiler import compile_source
from .codegen import CompiledProgram, Slot
from .errors import CompileError, Diagnostic
from .disasm import disassemble, disassemble_text, DecodedInstr

__all__ = [
    "compile_source",
    "CompiledProgram",
    "Slot",
    "CompileError",
    "Diagnostic",
    "disassemble",
    "disassemble_text",
    "DecodedInstr",
]
__version__ = "0.1.0"


def __getattr__(name):
    # Lazily expose the sim-driven helpers (debugger / loader) without importing
    # them — and their modules — at package import time.
    if name in ("TbpsDebugger", "StepFrame"):
        from . import debug
        return getattr(debug, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
