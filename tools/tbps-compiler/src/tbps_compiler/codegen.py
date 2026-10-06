"""TBPS code generation: AST -> ROM-faithful SRAM program image.

Target layout (firmware/src/annotated/program.asm, [BYTE][SIM]):

* The program BODY is a stream of fixed **8-byte slots** starting at SRAM
  ``0x8100`` (page 0x81).  ``prog_exec`` fetches one opcode per slot and
  advances the PC by 8 (``PC += 8`` at 0x0A01/0x0A03).
* Each slot is ``[opcode, operand bytes..., 0x00 padding...]`` to 8 bytes.
  Trailing bytes in a slot are ignored by the executor (it reads only the
  operands it needs, then jumps straight to ``PC += 8``), so we zero-pad.
* ``MARK m`` is NOT a runtime instruction: the preprocessor ``prog_prepare``
  (0x0803) scans the body, and for each MARK (opcode 0x1F) records the slot's
  PC into the page-0x80 label table at ``2*m`` (``rl A`` doubles the index).
  We model MARK as an in-stream marker that still occupies a slot (the
  preprocessor walks the body in 8-byte steps), and we emit the resolved
  2-byte label table on page 0x80.
* Program END is any opcode with bit7 set (``prog_exec`` 0x094D).  The source
  ``INS .`` maps to a single END slot (0x80).
* The preprocessor also validates a header at ``0x80FE`` (low-3 bits must be 0)
  and an end sentinel ``0x83``; those live in the page-0x80 header area and are
  normally written by the firmware itself (``prog_end`` 0x0880).  We expose a
  helper to build the full page-0x80 image for simulator round-trips.

PROVENANCE: the 8-byte slot, MARK=0x1F label-table mechanism, END=bit7, and the
header/0x83 sentinel are [BYTE]/[SIM].  The exact *operand ordering* inside a
slot for TIM/OUT/GOTO/IF is tagged [INFER] in the firmware annotations; the
layouts below follow the decoded ``movx``/``inc DPTR`` sequences in
``prog_exec`` and are marked accordingly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import isa
from . import parser as P
from .errors import Diagnostic


@dataclass
class Slot:
    """One 8-byte program slot plus the source line that produced it."""

    opcode: int
    operands: list[int] = field(default_factory=list)
    line: int = 0
    is_mark: bool = False
    mark_label: int = 0

    def to_bytes(self) -> bytes:
        raw = bytes([self.opcode, *self.operands])
        if len(raw) > isa.SLOT_SIZE:
            raise ValueError(f"slot overflow on line {self.line}: {len(raw)} > {isa.SLOT_SIZE}")
        return raw + bytes(isa.SLOT_SIZE - len(raw))


@dataclass
class CompiledProgram:
    """The result of code generation."""

    slots: list[Slot] = field(default_factory=list)
    labels: dict[int, int] = field(default_factory=dict)   # label -> slot index
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.diagnostics

    # --- byte images ---------------------------------------------------------
    def body_bytes(self) -> bytes:
        """The program body: concatenated 8-byte slots (loads at 0x8100)."""
        return b"".join(s.to_bytes() for s in self.slots)

    def label_table_bytes(self, size: int = 256) -> bytes:
        """Page-0x80 label table: 2 bytes (little-endian PC) per label index.

        The PC stored for ``MARK m`` is the absolute SRAM address of that slot
        (``0x8100 + slot_index*8``), matching ``prog_goto`` (0x0A33) which reads
        a 2-byte PC from ``label_table[2*m]`` into ``0x66:0x67``.  [BYTE]
        """
        table = bytearray(size)
        for label, slot_index in self.labels.items():
            pc = isa.SRAM_BODY_BASE + slot_index * isa.SLOT_SIZE
            off = 2 * label
            table[off] = pc & 0xFF
            table[off + 1] = (pc >> 8) & 0xFF
        return bytes(table)

    def pc_of_label(self, label: int) -> int:
        return isa.SRAM_BODY_BASE + self.labels[label] * isa.SLOT_SIZE

    def sram_writes(self, *, include_zero: bool = False) -> list[tuple[int, int]]:
        """Yield ``(xram_address, byte)`` pairs for loading into the simulator.

        Covers the page-0x80 label table and the body at 0x8100.  By default
        only non-zero bytes are returned (the simulator can be pre-cleared), so
        a sparse program loads with few ``set mem`` commands.
        """
        writes: list[tuple[int, int]] = []
        for i, b in enumerate(self.label_table_bytes()):
            if b or include_zero:
                writes.append((isa.SRAM_LABEL_BASE + i, b))
        for i, b in enumerate(self.body_bytes()):
            if b or include_zero:
                writes.append((isa.SRAM_BODY_BASE + i, b))
        return writes


# --- per-instruction slot builders -------------------------------------------
# Operand orderings follow prog_exec's decoded movx/inc-DPTR reads.  [BYTE] for
# the reads; the mapping of a given source instruction to the class is [INFER]
# where the firmware annotations say so.

def _slot_pos_axis(node: P.PosAxis) -> Slot:
    """POS a . n  ->  move axis a to target n (class 0x60+axis).  [SIM]

    prog_exec bit6=1,bit5=1 single-axis path: ``add A,#0x40`` -> ``target[0x40+axis]``
    = the operand byte, arming the motion mask (0x2B/0x2C).  Verified live and in
    simulator/tests/demo_hello_program.sh (``0x60|axis`` moves the axis).  One
    operand byte: the target position.  [SIM]
    """
    axis_fw = isa.axis_user_to_fw(node.axis)
    return Slot(isa.pos_move_opcode(axis_fw), [node.position & 0xFF], node.line)


def _slot_pos_store(node: P.PosStore) -> Slot:
    """POS (store all axes).  All-axes set-position: opcode 0x07, 6 bytes.  [INFER]

    The Teach Box ``POS ENT`` captures the *current* arm position; in the stored
    stream that is the all-axes set-position opcode (low-3 == 7).  The 6 operand
    bytes are the taught positions; a bare ``POS`` with no known positions emits
    zeros (placeholder, as the real Teach Box fills these from the live pots).
    """
    return Slot(isa.OP_POS_SET | isa.AXIS_ALL, [0] * 6, node.line)


def _slot_tim(node: P.Tim) -> Slot:
    """TIM t  ->  bit4 set, bit3 set (0x18 class).  [BYTE] reads / [INFER] mapping

    prog_exec 0x09E5: ``movx -> 0x1A`` (lo), ``inc DPTR``, ``movx; inc A -> 0x1B``
    (hi).  Firmware stores hi+1 (``inc A``), so to produce an effective delay of
    ``t`` the stored high byte is ``(t>>8)`` and the firmware adds 1 as a loop
    pre-decrement convention.  We store the raw lo/hi; the +1 is the executor's.
    Two operand bytes: lo, hi.  [BYTE]
    """
    t = node.delay & 0xFFFF
    return Slot(isa.OP_TIM, [t & 0xFF, (t >> 8) & 0xFF], node.line)


def _slot_out(node: P.Out) -> Slot:
    """OUT k +/-  ->  bit4 set, bit3 clear (0x10 class).  [BYTE] reads / [INFER]

    prog_exec 0x09D4: ``anl A,#0x03`` (R2 = opcode low 2 bits), then ``movx -> R0``
    and ``lcall 0x07D3`` (portb_write).  So the port selection is carried in the
    opcode low bits and the state in one operand byte.  Teach Box with the pendant
    exposes outputs 1..3; over serial up to 8.  We encode ``(k-1)`` into the low
    2 bits (firmware masks ``#0x03``) and the +/- state in the operand byte:
    '+' = set LOW = 0x00, '-' = clear HIGH = 0x01.  [INFER]
    """
    port_fw = (node.port - 1) & 0x03
    state = 0x00 if node.set_low else 0x01
    return Slot(isa.OP_OUT | port_fw, [state], node.line)


def _slot_goto(node: P.Goto) -> Slot:
    """GOTO m [. n]  ->  bit5 set, bit4 set, bit3 clear branch (0x09F1).  [INFER]

    prog_exec 0x0A0C: ``movx -> R0`` (label m), ``inc DPTR``; for the counted form
    (``jb 0x39``) it reads a count byte and decrements it in place.  Operands:
    [label, count] -- count 0 marks the endless form.  [INFER]
    """
    operands = [node.label & 0xFF, (node.count or 0) & 0xFF]
    return Slot(isa.OP_GOTO | isa.BIT4, operands, node.line)


def _slot_if(node: P.If) -> Slot:
    """IF i [. m]  ->  bit5 set branch (0x09F1 / 0x0A0C input-test path).  [INFER]

    prog_exec 0x0A12/0x0A1C: reads an input-mask operand, ANDs/ORs against P1
    (0x90), and on match resolves a label via prog_goto.  Operands:
    [input_mask, label]; the wait form (``IF i``) has no label (loops in place),
    which we encode with label 0.  [INFER]
    """
    input_mask = (1 << (node.inp - 1)) & 0xFF
    label = (node.label or 0) & 0xFF
    return Slot(isa.OP_IF, [input_mask, label], node.line)


def _slot_mark(node: P.Mark) -> Slot:
    """MARK m  ->  opcode 0x1F; label resolved into the page-0x80 table.  [BYTE]"""
    return Slot(isa.OP_MARK, [node.label & 0xFF], node.line, is_mark=True, mark_label=node.label)


def _slot_end(node: P.ProgramEnd) -> Slot:
    """INS .  ->  program end (any bit7-set opcode).  [BYTE]"""
    return Slot(isa.OP_END, [], node.line)


def _slot_halt(node: P.Halt) -> Slot:
    """DEL .  ->  the 3-byte halt/separator opcode 0x36.  [BYTE][INFER meaning]"""
    return Slot(isa.OP_HALT_3BYTE, [0, 0], node.line)


def _slot_nop(node: P.Nop) -> Slot:
    """. (NOP)  ->  bit6 set, bit5 clear class (0x099A clears state bits).  [BYTE]"""
    return Slot(isa.BIT6, [], node.line)


_BUILDERS = {
    P.PosAxis: _slot_pos_axis,
    P.PosStore: _slot_pos_store,
    P.Tim: _slot_tim,
    P.Out: _slot_out,
    P.Goto: _slot_goto,
    P.If: _slot_if,
    P.Mark: _slot_mark,
    P.ProgramEnd: _slot_end,
    P.Halt: _slot_halt,
    P.Nop: _slot_nop,
}


def generate(nodes: list[P.Node]) -> CompiledProgram:
    """Turn parsed AST nodes into a :class:`CompiledProgram`.

    ``STOP`` (ProgramStart) and ``CLR`` emit no body slot: ``STOP 0`` is the
    "clear memory / make header" command the Teach Box issues once, not a stored
    instruction.  All other instructions occupy one 8-byte slot.
    """
    prog = CompiledProgram()
    referenced: list[tuple[int, int]] = []   # (label, source line)

    for node in nodes:
        if isinstance(node, P.ProgramStart):
            continue  # header command; no body byte
        builder = _BUILDERS.get(type(node))
        if builder is None:
            prog.diagnostics.append(
                Diagnostic(f"no codegen for {type(node).__name__}", node.line, 1, node.source)
            )
            continue
        slot = builder(node)
        slot_index = len(prog.slots)
        prog.slots.append(slot)
        if slot.is_mark:
            if slot.mark_label in prog.labels:
                prog.diagnostics.append(
                    Diagnostic(f"duplicate label {slot.mark_label}", node.line, 1, node.source)
                )
            else:
                prog.labels[slot.mark_label] = slot_index
        if isinstance(node, P.Goto):
            referenced.append((node.label, node.line))
        if isinstance(node, P.If) and node.label is not None:
            referenced.append((node.label, node.line))

    # Link check: every referenced label must be defined.
    for label, line in referenced:
        if label not in prog.labels:
            prog.diagnostics.append(
                Diagnostic(f"undefined label {label} referenced", line, 1)
            )

    # Capacity check: the body must fit in the SRAM program region
    # (0x8100..0x9FFF ~= 7936 bytes).  A program larger than this would wrap
    # past the SRAM body and corrupt memory on the real robot.
    body_size = len(prog.slots) * isa.SLOT_SIZE
    if body_size > isa.SRAM_BODY_CAPACITY:
        prog.diagnostics.append(
            Diagnostic(
                f"program too large: {body_size} bytes "
                f"({len(prog.slots)} instructions) exceeds the "
                f"{isa.SRAM_BODY_CAPACITY}-byte SRAM program store",
                line=prog.slots[-1].line if prog.slots else 1,
            )
        )

    return prog
