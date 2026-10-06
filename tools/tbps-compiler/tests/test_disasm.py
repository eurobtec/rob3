"""Disassembler tests: compile -> disassemble round-trips to the source."""

from __future__ import annotations

import pytest

from tbps_compiler import compile_source, disassemble, disassemble_text
from tbps_compiler import isa


def _texts(instrs):
    return [i.text for i in instrs]


def test_roundtrip_basic():
    src = "MARK 0\nPOS 1 . 128\nOUT 1 +\nTIM 50\nGOTO 0\nINS ."
    prog = compile_source(src, raise_on_error=True)
    instrs = disassemble(prog.body_bytes())
    assert _texts(instrs) == [
        "MARK 0",
        "POS 1 . 128",
        "OUT 1 +",
        "TIM 50",
        "GOTO 0",
        "INS .",
    ]


def test_roundtrip_out_minus_and_axes():
    prog = compile_source("POS 3 . 200\nOUT 2 -\nINS .", raise_on_error=True)
    assert _texts(disassemble(prog.body_bytes()))[:2] == ["POS 3 . 200", "OUT 2 -"]


def test_tim_value_decoded():
    prog = compile_source("TIM 65535\nINS .", raise_on_error=True)
    assert disassemble(prog.body_bytes())[0].text == "TIM 65535"


def test_if_decoded():
    prog = compile_source("MARK 5\nIF 3 . 5\nINS .", raise_on_error=True)
    texts = _texts(disassemble(prog.body_bytes()))
    assert "IF 3 . 5" in texts


def test_disassemble_stops_at_end():
    # Bytes after an END (bit7) opcode are not decoded.
    prog = compile_source("MARK 0\nINS .\nTIM 10", raise_on_error=True)
    instrs = disassemble(prog.body_bytes())
    assert instrs[-1].text == "INS ."
    assert len(instrs) == 2        # MARK, INS . (TIM after END not decoded)


def test_addresses_are_slot_aligned():
    prog = compile_source("MARK 0\nTIM 1\nINS .", raise_on_error=True)
    instrs = disassemble(prog.body_bytes())
    assert instrs[0].addr == isa.SRAM_BODY_BASE
    assert instrs[1].addr == isa.SRAM_BODY_BASE + isa.SLOT_SIZE


def test_disassemble_text_formats_lines():
    prog = compile_source("MARK 0\nINS .", raise_on_error=True)
    txt = disassemble_text(prog.body_bytes())
    assert "0x8100: MARK 0" in txt


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
