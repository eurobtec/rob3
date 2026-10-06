"""High-level TBPS compile pipeline: source text -> CompiledProgram."""

from __future__ import annotations

from .codegen import CompiledProgram, generate
from .errors import CompileError
from .lexer import tokenize
from .parser import parse


def compile_source(source: str, *, raise_on_error: bool = False) -> CompiledProgram:
    """Compile TBPS source text into a :class:`CompiledProgram`.

    Diagnostics from lexing/parsing/codegen are collected on the result.  Pass
    ``raise_on_error=True`` to raise :class:`CompileError` instead when any
    diagnostic is present.
    """
    lines = tokenize(source)
    parsed = parse(lines)

    if parsed.diagnostics:
        prog = CompiledProgram(diagnostics=list(parsed.diagnostics))
    else:
        prog = generate(parsed.nodes)

    if raise_on_error and prog.diagnostics:
        raise CompileError(prog.diagnostics)
    return prog
