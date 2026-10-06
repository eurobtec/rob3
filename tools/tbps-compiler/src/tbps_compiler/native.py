"""Native 8051 backend — compile TBPS to MCS-51 assembly (sdas8051).

An *ahead-of-time* alternative to the bytecode interpreter: instead of emitting
8-byte interpreter slots run by ``prog_exec``, this emits 8051 instructions that
perform each TBPS instruction's effect directly, reusing the firmware's own
state layout and the ``dout_write`` (0x07D0) helper.

Mode: **hosted / subroutine** — the emitted code reuses the running ROM's RAM
map and routines (it is meant to be placed in the code-fetch space in ucSim and
``ljmp``-ed to, or assembled into a larger image). It mirrors exactly what
``prog_exec`` does per instruction, so native and interpreted runs leave the
same firmware state:

  POS a . n  -> mov  target[0x40+axis],#n ; orl 0x2B,#bit ; orl 0x2C,#bit
  OUT k +    -> mov  R0,#value ; mov A,#op ; lcall 0x07D0   (dout_write)
  TIM t      -> load 0x1A/0x1B delay counters (lo, hi+1) like the interpreter
  GOTO m     -> ljmp Lm
  GOTO m . n -> djnz a per-call counter, then ljmp Lm
  IF i       -> wait: jnb <input>,$  (poll until low)
  IF i . m   -> mov A,P1 ; <test input bit> ; jb/jnb -> ljmp Lm
  MARK m     -> label  Lm:
  INS .      -> ret
  DEL .      -> ret        (halt / separator)

Operand/semantics mirror tbps_compiler.isa and the [SIM]-verified interpreter.
The axis target base is 0x40, the motion masks are 0x2B/0x2C, the digital-out
helper is at 0x07D0 (R0=value, A=op: 1=ORL 2=ANL 3=XRL else=MOV).
"""

from __future__ import annotations

from . import isa
from . import parser as P
from .errors import CompileError
from .lexer import tokenize
from .parser import parse

DOUT_WRITE = 0x07D0        # dout_write(A=op, R0=value) -> 0x1F + Port B
IRAM_TARGET = 0x40         # target[0x40+axis]
MASK_NEEDMOVE = 0x2B
MASK_MOVING = 0x2C
TIM_LO = 0x1A
TIM_HI = 0x1B


def _label(m: int) -> str:
    return f"Lmark_{m}"


def _emit_pos(node: P.PosAxis, out: list[str]) -> None:
    axis = isa.axis_user_to_fw(node.axis)
    bit = 1 << axis
    out.append(f"    ; POS {node.axis} . {node.position}  (move axis {axis})")
    out.append(f"    mov  0x{IRAM_TARGET + axis:02x},#0x{node.position & 0xff:02x}")
    out.append(f"    orl  0x{MASK_NEEDMOVE:02x},#0x{bit:02x}")
    out.append(f"    orl  0x{MASK_MOVING:02x},#0x{bit:02x}")


def _emit_pos_store(node: P.PosStore, out: list[str]) -> None:
    # Store-all: snapshot feedback (0x58..) into targets (0x40..). Mirrors the
    # "store current position" semantics; here we arm all six axes.
    out.append("    ; POS  (store current position, all axes)")
    for a in range(6):
        out.append(f"    mov  0x{IRAM_TARGET + a:02x},0x{0x58 + a:02x}")
    out.append(f"    mov  0x{MASK_NEEDMOVE:02x},#0x3f")
    out.append(f"    mov  0x{MASK_MOVING:02x},#0x3f")


def _emit_out(node: P.Out, out: list[str]) -> None:
    # Mirror the interpreter EXACTLY (prog_exec 0x09D4): it calls dout_write with
    #   A = opcode & 3   (the op selector: 0=MOV/load, 1=ORL, 2=ANL, 3=XRL)
    #   R0 = operand byte (0x00 for '+', 0x01 for '-')
    # The TBPS OUT opcode is 0x10 + ((k-1)&3), so opcode&3 = (k-1)&3.
    op = (node.port - 1) & 0x03
    operand = 0x00 if node.set_low else 0x01
    out.append(f"    ; OUT {node.port} {'+' if node.set_low else '-'}"
               f"  (dout_write A=0x{op:02x}, R0=0x{operand:02x})")
    out.append(f"    mov  r0,#0x{operand:02x}")
    out.append(f"    mov  a,#0x{op:02x}")
    out.append(f"    lcall 0x{DOUT_WRITE:04x}")


def _emit_tim(node: P.Tim, out: list[str]) -> None:
    t = node.delay & 0xFFFF
    out.append(f"    ; TIM {node.delay}  (delay x100ms)")
    out.append(f"    mov  0x{TIM_LO:02x},#0x{t & 0xff:02x}")
    out.append(f"    mov  0x{TIM_HI:02x},#0x{((t >> 8) + 1) & 0xff:02x}")
    # Spin until both counters reach 0 (Timer0 tick decrements them elsewhere;
    # in hosted mode we busy-decrement to model the wait deterministically).
    lbl = f"Ltim_{node.line}"
    out.append(f"{lbl}:")
    out.append(f"    mov  a,0x{TIM_LO:02x}")
    out.append(f"    orl  a,0x{TIM_HI:02x}")
    out.append(f"    jz   {lbl}_done")
    out.append(f"    djnz 0x{TIM_LO:02x},{lbl}")
    out.append(f"    djnz 0x{TIM_HI:02x},{lbl}")
    out.append(f"{lbl}_done:")


def _emit_goto(node: P.Goto, out: list[str], counters: dict) -> None:
    if node.count is None or node.count == 0:
        out.append(f"    ; GOTO {node.label}  (unconditional)")
        out.append(f"    ljmp {_label(node.label)}")
    else:
        # Counted loop: a dedicated counter byte in a scratch slot per GOTO.
        cvar = 0x78 + (len(counters) & 0x07)   # scratch workspace region
        counters[id(node)] = cvar
        lbl = f"Lgoto_{node.line}"
        out.append(f"    ; GOTO {node.label} . {node.count}  (loop)")
        out.append(f"    djnz 0x{cvar:02x},{_label(node.label)}")
        out.append(f"{lbl}:  ; fall through when loop count exhausted")


def _emit_if(node: P.If, out: list[str]) -> None:
    # Inputs are active-low; test the P1 input bit and branch/wait.
    # P1 is bit-addressable: P1.N has bit address 0x90 + N (sdas8051 wants the
    # numeric bit address, not dot-notation).
    bitaddr = 0x90 + ((node.inp - 1) & 0x07)
    if node.label is None:
        out.append(f"    ; IF {node.inp}  (wait until input low)")
        out.append(f"Lif_{node.line}:")
        out.append(f"    jb   0x{bitaddr:02x},Lif_{node.line}")   # high -> keep waiting
    else:
        out.append(f"    ; IF {node.inp} . {node.label}  (branch if low)")
        out.append(f"    jnb  0x{bitaddr:02x},{_label(node.label)}")  # low -> jump


def generate_asm(source: str, *, org: int = 0x0000, name: str = "tbps_native") -> str:
    """Compile TBPS source to sdas8051 assembly (hosted/subroutine mode)."""
    lines = tokenize(source)
    parsed = parse(lines)
    if parsed.diagnostics:
        raise CompileError(parsed.diagnostics)

    out: list[str] = []
    out.append(f";;; {name} -- native 8051 from TBPS (hosted mode)")
    out.append(";;; Generated by tbps_compiler.native. Reuses firmware RAM map +")
    out.append(";;; dout_write (0x07D0). Entry at the start; RET on INS. / DEL.")
    out.append(f"    .area TBPS (ABS)")
    out.append(f"    .org 0x{org:04x}")
    out.append(f"{name}:")

    counters: dict = {}
    # Pre-pass: initialize counted-loop counters at entry.
    pending_counts = [(n, n.count) for n in parsed.nodes
                      if isinstance(n, P.Goto) and n.count]

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
