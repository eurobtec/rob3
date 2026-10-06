"""TBPS disassembler: program body bytes -> TBPS source lines.

The inverse of :mod:`tbps_compiler.codegen`.  Decodes the fixed 8-byte-slot
program body (as stored at SRAM 0x8100) back into readable TBPS instructions,
using the same ROM-verified opcode map as the compiler (see :mod:`tbps_compiler.isa`).

Opcodes whose exact operand ordering is ``[INFER]`` (GOTO/IF) are decoded on a
best-effort basis and annotated.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import isa


@dataclass
class DecodedInstr:
    """One decoded instruction."""

    addr: int               # SRAM address of the slot
    opcode: int
    text: str               # reconstructed TBPS source
    note: str = ""          # optional provenance / caveat

    def __str__(self) -> str:
        s = f"0x{self.addr:04X}: {self.text}"
        if self.note:
            s += f"    ; {self.note}"
        return s


def _axis_fw(opcode: int) -> int:
    return opcode & 0x07


def decode_slot(opcode: int, operands: bytes, addr: int) -> DecodedInstr:
    """Decode a single opcode + its (up to 7) operand bytes."""
    # END: any bit7-set opcode.
    if opcode & isa.BIT7_END:
        return DecodedInstr(addr, opcode, "INS .", "program end (bit7 set)")

    if opcode == isa.OP_MARK:
        return DecodedInstr(addr, opcode, f"MARK {operands[0]}")

    if opcode == isa.OP_HALT_3BYTE:
        return DecodedInstr(addr, opcode, "DEL .", "halt / separator")

    if opcode == isa.BIT6:   # 0x40 = NOP class
        return DecodedInstr(addr, opcode, ".", "NOP")

    # POS move + speed: 0x70..0x76 (bit6=1,bit5=1,bit4=1), low3 = axis.
    if (opcode & 0xF8) == isa.OP_POS_SPEED:
        axis = _axis_fw(opcode)
        if axis == isa.AXIS_ALL:
            return DecodedInstr(addr, opcode, "POS", "move+speed all axes")
        return DecodedInstr(addr, opcode, f"POS {axis + 1} . {operands[0]} , {operands[1]}",
                            "move+speed")

    # POS move: 0x60..0x66 (bit6=1,bit5=1,bit4=0), low3 = axis.
    if (opcode & 0xF8) == isa.OP_POS_MOVE:
        axis = _axis_fw(opcode)
        if axis == isa.AXIS_ALL:
            return DecodedInstr(addr, opcode, "POS", "store all axes")
        return DecodedInstr(addr, opcode, f"POS {axis + 1} . {operands[0]}")

    # POS set-position all axes: 0x07.
    if opcode == (isa.OP_POS_SET | isa.AXIS_ALL):
        return DecodedInstr(addr, opcode, "POS", "store all axes (set-position)")

    # POS set-position single: 0x00..0x05.
    if (opcode & 0xF8) == isa.OP_POS_SET and _axis_fw(opcode) <= 5:
        axis = _axis_fw(opcode)
        return DecodedInstr(addr, opcode, f"POS {axis + 1} . {operands[0]}", "set-position")

    # TIM: 0x18.
    if opcode == isa.OP_TIM:
        t = operands[0] | (operands[1] << 8)
        return DecodedInstr(addr, opcode, f"TIM {t}")

    # OUT: 0x10..0x13 (bit4 set, bit3 clear).
    if (opcode & 0xF8) == isa.OP_OUT and not (opcode & isa.BIT3):
        port = (opcode & 0x03) + 1
        sign = "+" if operands[0] == 0x00 else "-"
        return DecodedInstr(addr, opcode, f"OUT {port} {sign}")

    # GOTO unconditional (0x34): operand[0] = label.  [SIM]
    if opcode == isa.OP_GOTO:
        return DecodedInstr(addr, opcode, f"GOTO {operands[0]}")

    # GOTO counted (0x36): operand[0]=label, operand[1]=count.  [SIM]
    if opcode == isa.OP_GOTO_COUNTED:
        return DecodedInstr(addr, opcode, f"GOTO {operands[0]} . {operands[1]}")

    # IF (0x32): operand[0]=label, operand[1]=input mask; jump when input low. [BYTE]
    if opcode == isa.OP_IF:
        label, mask = operands[0], operands[1]
        pin = mask.bit_length() if mask else 0          # one-hot mask -> pin
        if label:
            return DecodedInstr(addr, opcode, f"IF {pin} . {label}")
        return DecodedInstr(addr, opcode, f"IF {pin}")

    return DecodedInstr(addr, opcode, f"??? (0x{opcode:02X})", "unknown opcode")


def disassemble(body: bytes, base: int = isa.SRAM_BODY_BASE) -> list[DecodedInstr]:
    """Disassemble a program body (8-byte slots) into instructions.

    Stops after an END (bit7-set) opcode, or at the end of the byte string.
    """
    out: list[DecodedInstr] = []
    for off in range(0, len(body), isa.SLOT_SIZE):
        slot = body[off : off + isa.SLOT_SIZE]
        if not slot:
            break
        opcode = slot[0]
        operands = slot[1:] + bytes(max(0, 8 - len(slot)))
        instr = decode_slot(opcode, operands, base + off)
        out.append(instr)
        if opcode & isa.BIT7_END:
            break
    return out


def disassemble_text(body: bytes, base: int = isa.SRAM_BODY_BASE) -> str:
    """Disassemble and format as TBPS source text (one instruction per line)."""
    return "\n".join(str(i) for i in disassemble(body, base))
