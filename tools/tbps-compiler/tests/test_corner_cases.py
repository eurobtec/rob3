"""Corner-case and boundary tests for the TBPS compiler.

Covers value-range edges (label 0/118/119, axis 1/6/7, position 255/256,
gripper 100/101, delay 0/65535/65536, ports 1/8/9, counter 0/255/256) and
structural edge cases (empty program, label-table layout at the top index,
duplicate/undefined labels).
"""

from __future__ import annotations

import pytest

from tbps_compiler import compile_source
from tbps_compiler import isa


def ok(src: str) -> bool:
    return compile_source(src).ok


# --- MARK label boundaries ---------------------------------------------------
def test_mark_label_boundaries():
    assert ok("MARK 0")           # low bound
    assert ok("MARK 118")         # high bound (manual: m = 0..118)
    assert not ok("MARK 119")     # one past -> error
    assert not ok("MARK 255")
    assert not ok("MARK -1")


def test_label_118_table_offset_is_last_safe_slot():
    """Label 118 lands at table offset 2*118 = 236 (0xEC), just below the
    page-0x80 header area at 0x80EE -- which is exactly why the manual caps m at
    118.  Label 119 would be 0xEE and collide with the header."""
    prog = compile_source("MARK 118\nINS .", raise_on_error=True)
    table = prog.label_table_bytes()
    off = 2 * 118
    assert off == 0xEC
    # PC of the MARK slot is stored little-endian at 0xEC/0xED.
    assert table[off] == (isa.SRAM_BODY_BASE & 0xFF)
    assert table[off + 1] == (isa.SRAM_BODY_BASE >> 8) & 0xFF
    # The header/end area at 0x80EE.. is NOT overwritten by the compiler.
    assert table[0xEE] == 0x00


# --- axis / position boundaries ---------------------------------------------
def test_axis_boundaries():
    assert ok("POS 1 . 0")
    assert ok("POS 6 . 0")        # gripper
    assert not ok("POS 0 . 0")    # axis 0 invalid (user axes are 1..6)
    assert not ok("POS 7 . 0")    # axis 7 invalid


def test_position_boundaries():
    assert ok("POS 1 . 255")      # 8-bit max
    assert not ok("POS 1 . 256")  # over 8-bit
    assert not ok("POS 1 . -1")


def test_gripper_position_boundaries():
    assert ok("POS 6 . 100")      # electric gripper max
    assert not ok("POS 6 . 101")  # over gripper range
    assert ok("POS 6 . 0")


# --- delay / counter / port boundaries --------------------------------------
def test_delay_boundaries():
    assert ok("TIM 0")
    assert ok("TIM 65535")
    assert not ok("TIM 65536")


def test_goto_counter_boundaries():
    assert ok("MARK 0\nGOTO 0 . 0")
    assert ok("MARK 0\nGOTO 0 . 255")
    assert not ok("MARK 0\nGOTO 0 . 256")


def test_input_output_port_boundaries():
    assert ok("MARK 0\nIF 1 . 0")
    assert ok("MARK 0\nIF 8 . 0")
    assert not ok("MARK 0\nIF 9 . 0")
    assert not ok("MARK 0\nIF 0 . 0")
    assert ok("OUT 1 +")
    assert ok("OUT 8 -")
    assert not ok("OUT 9 +")
    assert not ok("OUT 0 +")


# --- structural edge cases ---------------------------------------------------
def test_empty_program_is_ok_and_emits_nothing():
    prog = compile_source("", raise_on_error=True)
    assert prog.body_bytes() == b""
    assert prog.slots == []


def test_only_comments_emits_nothing():
    prog = compile_source("; just a comment\n# another\n", raise_on_error=True)
    assert prog.body_bytes() == b""


def test_header_only_emits_nothing():
    # STOP 0 and CLR are header/mode-change commands, not stored instructions.
    prog = compile_source("STOP 0\nCLR", raise_on_error=True)
    assert prog.body_bytes() == b""


def test_multiple_errors_are_all_collected():
    prog = compile_source("MARK 200\nPOS 9 . 999\nIF 0")
    assert not prog.ok
    assert len(prog.diagnostics) >= 2


def test_forward_reference_resolves():
    # GOTO a label defined later in the program.
    prog = compile_source("MARK 0\nGOTO 5\nMARK 5\nINS .", raise_on_error=True)
    assert prog.pc_of_label(5) == isa.SRAM_BODY_BASE + 2 * isa.SLOT_SIZE


def test_whitespace_and_dot_separators_equivalent():
    a = compile_source("POS 1 . 100", raise_on_error=True).body_bytes()
    b = compile_source("POS 1.100", raise_on_error=True).body_bytes()
    assert a == b


# --- "larger than 118" cases -------------------------------------------------
def test_more_than_118_labels_rejected():
    """A program using a label beyond 118 is rejected at compile time (the
    firmware label table only has room for 0..118 before the page-0x80 header)."""
    # 118 is fine; 119 collides with the SRAM header slot (0x80EE) -> rejected.
    assert ok("MARK 118\nINS .")
    assert not ok("MARK 119\nINS .")
    # Using many distinct valid labels (0..118) is allowed.
    many = "\n".join(f"MARK {m}" for m in range(0, 119)) + "\nINS ."
    assert ok(many)


def test_program_body_larger_than_sram_rejected():
    """A program whose body exceeds the SRAM program store (~7936 B / ~992
    8-byte slots) is rejected rather than silently wrapping past 0x9FFF."""
    max_slots = isa.SRAM_BODY_CAPACITY // isa.SLOT_SIZE
    # Build a program with one more slot than fits (TIM has no label limit).
    too_big = "\n".join(["TIM 1"] * (max_slots + 1))
    prog = compile_source(too_big)
    assert not prog.ok
    assert any("too large" in str(d) for d in prog.diagnostics)
    # Exactly at capacity is still OK.
    at_cap = "\n".join(["TIM 1"] * max_slots)
    assert compile_source(at_cap).ok


# --- multiple programs in one image (separated by DEL . = HALT) --------------
def test_two_programs_separated_by_halt_ok():
    """TBPS allows several programs in one memory image, separated by `DEL .`
    (HALT).  Each uses distinct labels; a jump reaches the second program."""
    src = """
    MARK 0
    POS 1 . 100
    DEL .
    MARK 1
    POS 2 . 50
    INS .
    """
    prog = compile_source(src, raise_on_error=True)
    assert 0 in prog.labels and 1 in prog.labels
    # The HALT separator occupies a slot between the two programs.
    opcodes = [s.opcode for s in prog.slots]
    assert isa.OP_HALT_3BYTE in opcodes


def test_two_pasted_programs_reusing_label_is_error():
    """Naively pasting two programs that both start `MARK 0` is a duplicate-label
    error (the Teach Box forbids reusing a label across the image)."""
    src = """
    MARK 0
    POS 1 . 100
    DEL .
    MARK 0
    POS 2 . 50
    INS .
    """
    prog = compile_source(src)
    assert not prog.ok
    assert any("duplicate label 0" in str(d) for d in prog.diagnostics)


def test_jump_from_first_program_into_second():
    """A GOTO in program A can target a label in program B (chaining)."""
    src = """
    MARK 0
    GOTO 10
    DEL .
    MARK 10
    POS 1 . 200
    INS .
    """
    prog = compile_source(src, raise_on_error=True)
    assert prog.pc_of_label(10) > prog.pc_of_label(0)


# --- bad jump targets --------------------------------------------------------
def test_goto_label_out_of_range_rejected():
    """GOTO/IF to a label > 118 is rejected (would alias into the SRAM header:
    prog_goto does rl A, so label 255 -> table offset 0xFE = the header slot)."""
    assert not ok("GOTO 255")
    assert not ok("GOTO 119")
    assert not ok("MARK 0\nIF 1 . 255")
    assert not ok("MARK 0\nGOTO 119 . 5")


def test_goto_undefined_in_range_label_rejected():
    """GOTO/IF to an in-range but UNDEFINED label (e.g. 100 with no MARK 100) is
    rejected by the link check -- at runtime the firmware would read a zeroed
    table entry and jump to PC 0x0000 (undefined execution)."""
    assert not ok("MARK 0\nGOTO 100\nINS .")
    assert not ok("MARK 0\nIF 1 . 100\nINS .")
    assert not ok("MARK 0\nGOTO 100 . 3\nINS .")
    # Defining the label makes it valid.
    assert ok("MARK 0\nGOTO 100\nMARK 100\nINS .")


def test_out_port_out_of_range_rejected():
    """OUT k with k outside 1..8 is rejected (the firmware masks the port with
    anl A,#0x03, so a bad port would silently alias -- better to reject)."""
    assert not ok("OUT 9 +")
    assert not ok("OUT 0 +")
    assert ok("OUT 8 -")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
