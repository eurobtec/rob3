"""Unit tests for the TBPS compiler encoding, derived from the ROB3 ROM."""

from __future__ import annotations

import pytest

from tbps_compiler import compile_source
from tbps_compiler import isa


def _slots(src):
    prog = compile_source(src, raise_on_error=True)
    return prog


# --- slot sizing -------------------------------------------------------------
def test_every_slot_is_eight_bytes():
    prog = _slots(
        """
        STOP 0
        MARK 0
        POS 1 . 255
        TIM 50
        OUT 1 +
        GOTO 0
        INS .
        """
    )
    body = prog.body_bytes()
    # STOP emits no slot; the rest are one 8-byte slot each.
    assert len(body) % isa.SLOT_SIZE == 0
    for i, s in enumerate(prog.slots):
        assert len(s.to_bytes()) == isa.SLOT_SIZE, f"slot {i} not 8 bytes"


# --- opcode correctness (vs ROM) --------------------------------------------
def test_mark_opcode_is_0x1f():
    prog = _slots("MARK 7")
    assert prog.slots[0].opcode == 0x1F
    assert prog.slots[0].operands[0] == 7


def test_pos_axis_is_move_target_class_opcode():
    # POS a . n = "move axis a to position n" -> target class 0x60 + (axis-1).
    # axis 1 -> fw 0 -> 0x60
    prog = _slots("POS 1 . 255")
    assert prog.slots[0].opcode == 0x60
    assert prog.slots[0].operands == [255]
    # axis 3 -> fw 2 -> opcode 0x62
    prog = _slots("POS 3 . 100")
    assert prog.slots[0].opcode == 0x62
    assert prog.slots[0].operands == [100]


def test_pos_axis_with_speed_is_speed_class():
    # POS a . n , s -> move+speed class 0x70+(axis-1), operands [pos, speed].
    prog = _slots("POS 1 . 128 , 3")
    assert prog.slots[0].opcode == 0x70        # axis 1 -> fw 0
    assert prog.slots[0].operands == [128, 3]
    prog = _slots("POS 2 . 200 , 5")
    assert prog.slots[0].opcode == 0x71        # axis 2 -> fw 1
    assert prog.slots[0].operands == [200, 5]


def test_pos_speed_out_of_range_rejected():
    from tbps_compiler import compile_source
    assert not compile_source("POS 1 . 10 , 0").ok   # speed < 1
    assert not compile_source("POS 1 . 10 , 6").ok   # speed > 5


def test_pos_store_is_all_axes_opcode():
    prog = _slots("POS")
    assert prog.slots[0].opcode == (isa.OP_POS_SET | isa.AXIS_ALL)  # 0x07
    assert len(prog.slots[0].operands) == 6


def test_tim_opcode_and_little_endian_operands():
    prog = _slots("TIM 50")      # 50 = 0x32
    assert prog.slots[0].opcode == isa.OP_TIM
    assert prog.slots[0].operands == [0x32, 0x00]
    prog = _slots("TIM 65535")   # 0xFFFF
    assert prog.slots[0].operands == [0xFF, 0xFF]


def test_out_opcode_sign_and_port():
    prog = _slots("OUT 1 +")     # port 1 -> fw 0; '+' = set LOW = 0x00
    assert prog.slots[0].opcode == (isa.OP_OUT | 0x00)
    assert prog.slots[0].operands == [0x00]
    prog = _slots("OUT 1 -")     # '-' = clear HIGH = 0x01
    assert prog.slots[0].operands == [0x01]


def test_end_opcode_has_bit7_set():
    prog = _slots("INS .")
    assert prog.slots[0].opcode & 0x80


def test_goto_class_bits():
    prog = _slots(
        """
        MARK 0
        GOTO 0
        """
    )
    goto = prog.slots[1]
    assert goto.opcode == 0x34             # GOTO unconditional (verified [SIM])
    assert goto.operands[0] == 0           # operand[0] = label
    assert goto.opcode & isa.BIT5          # bit5 set (branch class)
    assert not (goto.opcode & isa.BIT6)    # bit6 clear
    assert not (goto.opcode & isa.BIT7_END)


def test_goto_counted_opcode():
    prog = _slots("MARK 0\nGOTO 0 . 5")
    g = prog.slots[1]
    assert g.opcode == 0x36                # counted GOTO
    assert g.operands == [0, 5]            # [label, count]


def test_if_input_mask():
    prog = _slots(
        """
        MARK 5
        IF 3 . 5
        """
    )
    node = prog.slots[1]
    assert node.opcode == 0x32             # IF (verified [SIM])
    assert node.operands[0] == 5           # operand[0] = label
    assert node.operands[1] == (1 << 2)    # operand[1] = input 3 -> bit 2 mask


# --- label table (vs prog_goto 0x0A33) --------------------------------------
def test_label_table_stores_slot_pc_little_endian():
    prog = _slots(
        """
        MARK 0
        TIM 10
        MARK 2
        INS .
        """
    )
    # MARK 0 is slot 0 -> PC 0x8100; MARK 2 is slot 2 -> PC 0x8110
    table = prog.label_table_bytes()
    assert table[0] == 0x00 and table[1] == 0x81      # label 0 -> 0x8100
    assert table[4] == 0x10 and table[5] == 0x81      # label 2 -> 0x8110 (2*2=offset 4)
    assert prog.pc_of_label(0) == 0x8100
    assert prog.pc_of_label(2) == 0x8110


# --- diagnostics -------------------------------------------------------------
def test_undefined_label_is_error():
    prog = compile_source("GOTO 42")
    assert not prog.ok
    assert any("undefined label 42" in str(d) for d in prog.diagnostics)


def test_duplicate_label_is_error():
    prog = compile_source("MARK 1\nMARK 1")
    assert not prog.ok
    assert any("duplicate label 1" in str(d) for d in prog.diagnostics)


def test_out_of_range_values():
    assert not compile_source("MARK 200").ok        # label > 118
    assert not compile_source("POS 7 . 10").ok       # axis > 6
    assert not compile_source("POS 1 . 999").ok      # position > 255
    assert not compile_source("TIM 70000").ok        # delay > 65535
    assert not compile_source("IF 9").ok             # input > 8
    assert not compile_source("OUT 9 +").ok          # port > 8


def test_out_requires_sign():
    assert not compile_source("OUT 1").ok


def test_comments_and_blank_lines_ignored():
    prog = _slots(
        """
        ; a comment
        MARK 0    ; trailing comment
        # another comment

        INS .
        """
    )
    assert len(prog.slots) == 2  # MARK + END


def test_hello_world_compiles():
    # The documented hello_world program should compile cleanly.
    src = """
    STOP 0 ENT
    MARK 0 ENT
    CLR
    POS ENT
    OUT 1 + ENT
    TIM 50 ENT
    OUT 1 - ENT
    TIM 50 ENT
    POS 1 . 255 ENT
    GOTO 0 ENT
    INS . ENT
    """
    prog = compile_source(src, raise_on_error=True)
    # STOP + CLR emit nothing; MARK,POS,OUT,TIM,OUT,TIM,POS,GOTO,INS = 9 slots
    assert len(prog.slots) == 9
    assert prog.slots[0].opcode == 0x1F         # MARK 0
    assert prog.slots[-1].opcode & 0x80         # INS . -> END
    assert 0 in prog.labels


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
