"""Compiler diagnostics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Diagnostic:
    """A single compile-time error or warning tied to a source location."""

    message: str
    line: int
    column: int = 1
    source: str = ""

    def __str__(self) -> str:
        loc = f"line {self.line}:{self.column}"
        out = f"[{loc}] {self.message}"
        if self.source:
            out += f"\n    {self.source.strip()}"
        return out


class TbpsError(Exception):
    """Base class for TBPS compiler failures."""


class LexError(TbpsError):
    """Raised for an unrecoverable lexing failure."""

    def __init__(self, diagnostic: Diagnostic):
        super().__init__(str(diagnostic))
        self.diagnostic = diagnostic


class ParseError(TbpsError):
    """Raised for a single parse failure (caught and collected by the parser)."""

    def __init__(self, diagnostic: Diagnostic):
        super().__init__(str(diagnostic))
        self.diagnostic = diagnostic


class CompileError(TbpsError):
    """Raised when compilation finishes with one or more diagnostics."""

    def __init__(self, diagnostics: list[Diagnostic]):
        self.diagnostics = diagnostics
        joined = "\n".join(str(d) for d in diagnostics)
        super().__init__(f"{len(diagnostics)} error(s):\n{joined}")
