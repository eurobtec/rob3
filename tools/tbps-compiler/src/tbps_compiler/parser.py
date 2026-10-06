"""TBPS parser: tokens -> a list of validated AST instructions.

Grammar (hardware/teachbox/README.md section 6, "Summary of all Instructions
and Commands"):

    STOP 0            program start / header       (no body byte emitted)
    MARK m            label definition             m = 0..118
    POS               store current position (all axes)
    POS a . n         move axis a to position n    a = 1..6, n = 0..255 (gripper 0..100)
    TIM t             delay t x 100 ms             t = 0..65535
    GOTO m            unconditional jump
    GOTO m . n        loop to m, n times           n = 0..255
    IF i              wait until input i is low     i = 1..8
    IF i . m          if input i low, jump to m
    OUT k +           set   output k (drive LOW)    k = 1..8
    OUT k -           clear output k (drive HIGH)
    .                 NOP
    INS .             program end
    DEL .             halt / program separator

The parser collects diagnostics instead of raising on the first error, so a
whole file is checked in one pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import isa
from .errors import Diagnostic
from .lexer import Line


# --- AST nodes ----------------------------------------------------------------
@dataclass
class Node:
    line: int
    source: str = ""


@dataclass
class ProgramStart(Node):
    pass


@dataclass
class ProgramEnd(Node):
    pass


@dataclass
class Halt(Node):
    pass


@dataclass
class Nop(Node):
    pass


@dataclass
class Mark(Node):
    label: int = 0


@dataclass
class PosStore(Node):
    pass


@dataclass
class PosAxis(Node):
    axis: int = 1          # user axis 1..6
    position: int = 0
    speed: int | None = None   # optional travel speed 1..5 (None = plain move)


@dataclass
class Tim(Node):
    delay: int = 0


@dataclass
class Goto(Node):
    label: int = 0
    count: int | None = None   # None = unconditional (endless)


@dataclass
class If(Node):
    inp: int = 1
    label: int | None = None   # None = wait-until-low form


@dataclass
class Out(Node):
    port: int = 1
    set_low: bool = True       # '+' = set (drive LOW); '-' = clear (drive HIGH)


@dataclass
class ParseResult:
    nodes: list[Node] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.diagnostics


class _Parser:
    def __init__(self) -> None:
        self.nodes: list[Node] = []
        self.diags: list[Diagnostic] = []

    def err(self, msg: str, line: Line, token_index: int = 0) -> None:
        self.diags.append(
            Diagnostic(msg, line.number, line.column_of(token_index), line.raw)
        )

    def _int(self, line: Line, idx: int, what: str) -> int | None:
        if idx >= len(line.tokens):
            self.err(f"{what}: missing value", line, idx)
            return None
        tok = line.tokens[idx]
        try:
            return int(tok, 0)
        except ValueError:
            self.err(f"{what}: '{tok}' is not an integer", line, idx)
            return None

    def _range(self, val: int, lo: int, hi: int, line: Line, idx: int, what: str) -> bool:
        if not (lo <= val <= hi):
            self.err(f"{what}: {val} out of range {lo}..{hi}", line, idx)
            return False
        return True

    def parse_line(self, line: Line) -> None:
        head = line.head
        toks = line.tokens
        src = line.raw

        if head == isa.Mnemonic.STOP:
            # STOP 0  -> program header. Optional trailing 0.
            if len(toks) > 1:
                val = self._int(line, 1, "STOP")
                if val is not None and val != 0:
                    self.err("STOP header parameter must be 0", line, 1)
            self.nodes.append(ProgramStart(line.number, src))

        elif head == isa.Mnemonic.MARK:
            val = self._int(line, 1, "MARK label")
            if val is not None and self._range(val, isa.LABEL_MIN, isa.LABEL_MAX, line, 1, "MARK label"):
                self.nodes.append(Mark(line.number, src, label=val))

        elif head == isa.Mnemonic.POS:
            if len(toks) == 1:
                self.nodes.append(PosStore(line.number, src))
            else:
                axis = self._int(line, 1, "POS axis")
                pos = self._int(line, 2, "POS position")
                if axis is None or pos is None:
                    return
                if not self._range(axis, isa.AXIS_MIN, isa.AXIS_MAX, line, 1, "POS axis"):
                    return
                hi = isa.GRIPPER_MAX if axis == 6 else isa.POS_MAX
                if not self._range(pos, isa.POS_MIN, hi, line, 2, f"POS axis {axis} position"):
                    return
                # Optional travel speed (1..5): `POS a . n , s` / `POS a . n s`.
                speed = None
                if len(toks) > 3:
                    speed = self._int(line, 3, "POS speed")
                    if speed is None or not self._range(speed, isa.SPEED_MIN, isa.SPEED_MAX, line, 3, "POS speed"):
                        return
                self.nodes.append(PosAxis(line.number, src, axis=axis, position=pos, speed=speed))

        elif head == isa.Mnemonic.TIM:
            val = self._int(line, 1, "TIM delay")
            if val is not None and self._range(val, isa.DELAY_MIN, isa.DELAY_MAX, line, 1, "TIM delay"):
                self.nodes.append(Tim(line.number, src, delay=val))

        elif head == isa.Mnemonic.GOTO:
            label = self._int(line, 1, "GOTO label")
            if label is None or not self._range(label, isa.LABEL_MIN, isa.LABEL_MAX, line, 1, "GOTO label"):
                return
            count = None
            if len(toks) > 2:
                count = self._int(line, 2, "GOTO count")
                if count is None or not self._range(count, isa.COUNTER_MIN, isa.COUNTER_MAX, line, 2, "GOTO count"):
                    return
            self.nodes.append(Goto(line.number, src, label=label, count=count))

        elif head == isa.Mnemonic.IF:
            inp = self._int(line, 1, "IF input")
            if inp is None or not self._range(inp, isa.PORT_MIN, isa.PORT_MAX, line, 1, "IF input"):
                return
            label = None
            if len(toks) > 2:
                label = self._int(line, 2, "IF label")
                if label is None or not self._range(label, isa.LABEL_MIN, isa.LABEL_MAX, line, 2, "IF label"):
                    return
            self.nodes.append(If(line.number, src, inp=inp, label=label))

        elif head == isa.Mnemonic.OUT:
            port = self._int(line, 1, "OUT port")
            if port is None or not self._range(port, isa.PORT_MIN, isa.PORT_MAX, line, 1, "OUT port"):
                return
            sign_idx = 2
            if sign_idx >= len(toks) or toks[sign_idx] not in ("+", "-"):
                self.err("OUT requires a '+' (set) or '-' (clear) operator", line, sign_idx)
                return
            self.nodes.append(Out(line.number, src, port=port, set_low=(toks[sign_idx] == "+")))

        elif head == isa.Mnemonic.INS:
            self.nodes.append(ProgramEnd(line.number, src))

        elif head == isa.Mnemonic.DEL:
            self.nodes.append(Halt(line.number, src))

        elif head == isa.Mnemonic.NOP:
            self.nodes.append(Nop(line.number, src))

        elif head == isa.Mnemonic.CLR:
            # CLR is a mode-change key; it emits no stored program byte.
            return

        else:
            self.err(f"unknown instruction '{toks[0]}'", line, 0)


def parse(lines: list[Line]) -> ParseResult:
    p = _Parser()
    for line in lines:
        p.parse_line(line)
    return ParseResult(nodes=p.nodes, diagnostics=p.diags)
