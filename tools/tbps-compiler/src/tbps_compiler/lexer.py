"""TBPS lexer.

TBPS source is a sequence of instruction lines terminated by ``ENT`` (the
Teach Box ``ENTER`` key).  Tokens are whitespace- or ``.``-separated.  Comments
begin with ``;`` or ``#`` (compiler extension -- the Teach Box has no comment
glyph, but ``COMMENT`` exists in TBPS so we also strip a leading ``COM``/
``COMMENT`` word form).

The lexer is line-oriented: it returns a list of :class:`Line`, each a list of
string tokens plus the raw text and line number, so the parser can report
precise diagnostics.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


_COMMENT_RE = re.compile(r"(;.*|#.*)", re.IGNORECASE)
_FULL_COMMENT_RE = re.compile(r"^\s*COM(?:MENT)?\b.*$", re.IGNORECASE)


@dataclass(frozen=True)
class Line:
    """A single logical source line reduced to tokens."""

    number: int
    raw: str
    tokens: list[str] = field(default_factory=list)

    @property
    def head(self) -> str:
        """Upper-cased first token (the mnemonic), or '' for a blank line."""
        return self.tokens[0].upper() if self.tokens else ""

    def column_of(self, token_index: int) -> int:
        """1-based column where ``tokens[token_index]`` starts in ``raw``."""
        if token_index >= len(self.tokens):
            return len(self.raw) + 1
        idx = self.raw.find(self.tokens[token_index])
        return (idx + 1) if idx >= 0 else 1


def _strip_comment(text: str) -> str:
    if _FULL_COMMENT_RE.match(text):
        return ""
    return _COMMENT_RE.sub("", text)


def tokenize_line(raw: str, number: int) -> Line:
    """Tokenize one raw source line.

    ``ENT`` (the terminator) and the parameter separator ``.`` are dropped as
    structural tokens -- ``.`` becomes whitespace so ``POS 1 . 255`` and
    ``GOTO 20 . 5`` split cleanly.  ``+``/``-`` are kept as standalone tokens.
    """
    text = _strip_comment(raw).strip()
    # Ignore Markdown code-fence lines (```), so TBPS examples embedded in docs
    # or fenced .txt files compile unchanged.
    if text.startswith("```"):
        return Line(number=number, raw=raw, tokens=[])
    # Separate +/- so "OUT 1+" and "OUT 1 +" both tokenize to [..., '+'].
    text = re.sub(r"([+\-])", r" \1 ", text)
    # '.' is a visual separator; turn it into whitespace.
    text = text.replace(".", " ")
    tokens = [t for t in text.split() if t]
    # Drop the ENT terminator (case-insensitive) -- it carries no bytes.
    tokens = [t for t in tokens if t.upper() != "ENT"]
    return Line(number=number, raw=raw, tokens=tokens)


def tokenize(source: str) -> list[Line]:
    """Tokenize an entire TBPS source string into non-empty :class:`Line`\\ s."""
    lines: list[Line] = []
    for i, raw in enumerate(source.splitlines(), start=1):
        line = tokenize_line(raw, i)
        if line.tokens:
            lines.append(line)
    return lines
