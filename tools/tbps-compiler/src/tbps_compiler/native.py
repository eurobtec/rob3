"""Native 8051 backend — compile TBPS to MCS-51 assembly (sdas8051).

An *ahead-of-time* alternative to the bytecode interpreter: instead of emitting
8-byte interpreter slots run by ``prog_exec``, this emits 8051 instructions that
perform each TBPS instruction's effect directly, reusing the firmware's own
state layout and the ``dout_write`` helper.

Mode: **hosted / subroutine** — the emitted code reuses the running ROM's RAM
map and routines (place it in the code-fetch space in ucSim and ``ljmp`` to it,
or assemble it into a larger image). It mirrors exactly what ``prog_exec`` does
per instruction, so native and interpreted runs leave the same firmware state.

The generated assembly ``.include``s **tbps_isa.inc** (shipped in this package's
``asm/`` dir) so it uses SYMBOLIC equates — ``TARGET_BASE``, ``NEED_MOVE``,
``DOUT_WRITE``, etc. — rather than magic literals. See that header for the full
ISA + firmware map.
"""

from __future__ import annotations

import os

from . import isa
from . import parser as P
from .errors import CompileError
from .lexer import tokenize
from .parser import parse

# Path to the shipped equates header (asm/tbps_isa.inc).
ISA_INC = os.path.join(os.path.dirname(__file__), "asm", "tbps_isa.inc")
ISA_INC_NAME = "tbps_isa.inc"


def _label(m: int) -> str:
    return f"Lmark_{m}"


def _emit_pos(node: P.PosAxis, out: list[str]) -> None:
    axis = isa.axis_user_to_fw(node.axis)
    bit = 1 << axis
    if node.speed is None:
        out.append(f"    ; POS {node.axis} . {node.position}  (move axis {axis})")
        out.append(f"    mov  TARGET_BASE+{axis},#0x{node.position & 0xff:02x}")
    else:
        out.append(f"    ; POS {node.axis} . {node.position} , {node.speed}"
                   f"  (move+speed axis {axis})")
        out.append(f"    mov  TARGET_BASE+{axis},#0x{node.position & 0xff:02x}")
        out.append(f"    mov  SPEED_BASE+{axis},#0x{node.speed & 0xff:02x}")
    out.append(f"    orl  NEED_MOVE,#0x{bit:02x}")
    out.append(f"    orl  MOVING,#0x{bit:02x}")


def _emit_pos_store(node: P.PosStore, out: list[str]) -> None:
    out.append("    ; POS  (store current position, all axes)")
    for a in range(6):
        out.append(f"    mov  TARGET_BASE+{a},FEEDBACK_BASE+{a}")
    out.append("    mov  NEED_MOVE,#0x3f")
    out.append("    mov  MOVING,#0x3f")


def _emit_out(node: P.Out, out: list[str]) -> None:
    # Mirror the interpreter EXACTLY (prog_exec 0x09D4): dout_write with
    #   A  = opcode & 3   (op selector: 0=MOV/load, 1=ORL, 2=ANL, 3=XRL)
    #   R0 = operand byte (0x00 for '+', 0x01 for '-')
    op = (node.port - 1) & 0x03
    operand = 0x00 if node.set_low else 0x01
    out.append(f"    ; OUT {node.port} {'+' if node.set_low else '-'}"
               f"  (dout_write A=0x{op:02x}, R0=0x{operand:02x})")
    out.append(f"    mov  r0,#0x{operand:02x}")
    out.append(f"    mov  a,#0x{op:02x}")
    out.append("    lcall DOUT_WRITE")


def _emit_tim(node: P.Tim, out: list[str]) -> None:
    t = node.delay & 0xFFFF
    out.append(f"    ; TIM {node.delay}  (delay x100ms)")
    out.append(f"    mov  WAIT_CTR_LO,#0x{t & 0xff:02x}")
    out.append(f"    mov  WAIT_CTR_HI,#0x{((t >> 8) + 1) & 0xff:02x}")
    lbl = f"Ltim_{node.line}"
    out.append(f"{lbl}:")
    out.append("    mov  a,WAIT_CTR_LO")
    out.append("    orl  a,WAIT_CTR_HI")
    out.append(f"    jz   {lbl}_done")
    out.append(f"    djnz WAIT_CTR_LO,{lbl}")
    out.append(f"    djnz WAIT_CTR_HI,{lbl}")
    out.append(f"{lbl}_done:")


def _emit_goto(node: P.Goto, out: list[str], counters: dict) -> None:
    if node.count is None or node.count == 0:
        out.append(f"    ; GOTO {node.label}  (unconditional)")
        out.append(f"    ljmp {_label(node.label)}")
    else:
        cvar = 0x78 + (len(counters) & 0x07)   # scratch workspace region
        counters[id(node)] = cvar
        out.append(f"    ; GOTO {node.label} . {node.count}  (loop)")
        out.append(f"    djnz 0x{cvar:02x},{_label(node.label)}")
        out.append(f"Lgoto_{node.line}:  ; fall through when loop exhausted")


def _emit_if(node: P.If, out: list[str]) -> None:
    # Active-low inputs: P1.N bit address = SFR_P1 + N (sdas8051 numeric bit).
    bitaddr = 0x90 + ((node.inp - 1) & 0x07)
    if node.label is None:
        out.append(f"    ; IF {node.inp}  (wait until input low)")
        out.append(f"Lif_{node.line}:")
        out.append(f"    jb   0x{bitaddr:02x},Lif_{node.line}")   # high -> keep waiting
    else:
        out.append(f"    ; IF {node.inp} . {node.label}  (branch if low)")
        out.append(f"    jnb  0x{bitaddr:02x},{_label(node.label)}")  # low -> jump


def generate_asm(source: str, *, org: int = 0x2000, name: str = "tbps_native",
                 include_isa: bool = True) -> str:
    """Compile TBPS source to sdas8051 assembly (hosted/subroutine mode).

    The output ``.include``s ``tbps_isa.inc`` (symbolic equates) unless
    ``include_isa=False``.  Assemble with the header on the include path, e.g.
    ``sdas8051 -I <this package>/asm prog.asm``.
    """
    lines = tokenize(source)
    parsed = parse(lines)
    if parsed.diagnostics:
        raise CompileError(parsed.diagnostics)

    out: list[str] = []
    out.append(f";;; {name} -- native 8051 from TBPS (hosted mode)")
    out.append(";;; Generated by tbps_compiler.native. Symbolic equates from")
    out.append(f";;; {ISA_INC_NAME}. Reuses the firmware RAM map + DOUT_WRITE.")
    if include_isa:
        out.append(f'    .include "{ISA_INC_NAME}"')
    out.append("    .area TBPS (ABS)")
    out.append(f"    .org 0x{org:04x}")
    out.append(f"{name}:")

    counters: dict = {}
    for node in parsed.nodes:
        if isinstance(node, P.ProgramStart):
            continue
        if isinstance(node, P.Mark):
            out.append(f"{_label(node.label)}:")
        elif isinstance(node, P.PosAxis):
            _emit_pos(node, out)
        elif isinstance(node, P.PosStore):
            _emit_pos_store(node, out)
        elif isinstance(node, P.Out):
            _emit_out(node, out)
        elif isinstance(node, P.Tim):
            _emit_tim(node, out)
        elif isinstance(node, P.Goto):
            _emit_goto(node, out, counters)
        elif isinstance(node, P.If):
            _emit_if(node, out)
        elif isinstance(node, P.Nop):
            out.append("    nop")
        elif isinstance(node, (P.ProgramEnd, P.Halt)):
            out.append("    ; INS. / DEL.  (program end / halt)")
            out.append("    ret")
    out.append("    ret")
    out.append("")
    return "\n".join(out)
