"""Native 8051 backend tests: generation, assembly, and ucSim equivalence."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

import pytest

from tbps_compiler import compile_source
from tbps_compiler.native import generate_asm


# --- generation (no tools needed) -------------------------------------------
def test_generate_asm_basic():
    asm = generate_asm("MARK 0\nPOS 1 . 128\nOUT 1 +\nINS .", org=0x2000)
    assert ".org 0x2000" in asm
    assert "mov  0x40,#0x80" in asm        # POS 1 . 128 -> target[0] = 128
    assert "Lmark_0:" in asm               # MARK label
    assert "lcall 0x07d0" in asm           # OUT -> dout_write
    assert asm.rstrip().endswith("ret")


def test_generate_asm_goto_if():
    asm = generate_asm("MARK 0\nIF 2 . 0\nGOTO 0\nINS .", org=0x2000)
    assert "ljmp Lmark_0" in asm
    assert "jnb  0x91" in asm               # IF 2 -> P1.1 bit addr 0x91


def test_generate_asm_rejects_bad_source():
    from tbps_compiler.errors import CompileError
    with pytest.raises(CompileError):
        generate_asm("MARK 200")            # label out of range


# --- assembly with sdas8051 (skip if toolchain absent) ----------------------
def _have_sdas():
    return shutil.which("sdas8051") is not None and shutil.which("sdld") is not None


@pytest.mark.skipif(not _have_sdas(), reason="sdas8051/sdld not installed")
def test_native_assembles():
    asm = generate_asm("MARK 0\nPOS 1 . 128\nTIM 3\nOUT 1 +\nIF 2 . 0\nGOTO 0\nINS .",
                       org=0x2000, name="prog")
    d = tempfile.mkdtemp()
    a = os.path.join(d, "p.asm")
    open(a, "w").write(asm)
    r = subprocess.run(["sdas8051", "-l", "-o", a], cwd=d, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert os.path.exists(os.path.join(d, "p.rel"))


# --- ucSim equivalence: native run == interpreter run -----------------------
rob3_ucsim = pytest.importorskip("rob3_ucsim")


def _default_rom():
    env = rob3_ucsim.default_hex()
    if env:
        return env
    here = os.path.dirname(__file__)
    cand = os.path.abspath(os.path.join(here, "..", "..", "..", "firmware", "hex",
                                        "M2764A@DIP28.HEX"))
    return cand if os.path.exists(cand) else None


@pytest.mark.skipif(not _have_sdas(), reason="sdas8051/sdld not installed")
def test_native_equivalent_to_interpreter():
    try:
        binary = rob3_ucsim.find_ucsim()
    except FileNotFoundError:
        pytest.skip("no ucsim_51/s51 binary")
    rom = _default_rom()
    if not rom:
        pytest.skip("no ROB3 ROM image")

    from tbps_compiler.simload import load_program
    from tbps_compiler.debug import TbpsDebugger
    from tbps_compiler import isa

    SRC = "MARK 0\nPOS 1 . 128\nPOS 2 . 64\nPOS 3 . 200\nOUT 1 +\nINS ."

    # interpreter result
    prog = compile_source(SRC, raise_on_error=True)
    e = rob3_ucsim.UCSimEngine(hex_path=rom, binary=binary)
    load_program(e, prog)
    e.command("set mem iram 0x40 0 0 0 0 0 0")
    e.command("set mem iram 0x1f 0x00")
    dbg = TbpsDebugger(e, prog); dbg.reset_to(isa.SRAM_BODY_BASE); dbg.run(max_steps=10)
    it_t = [e._dump_byte("iram", 0x40 + k) for k in range(3)]
    it_do = e._dump_byte("iram", 0x1f)
    e.close()

    # native: assemble, load into code space, step, read state
    asm = generate_asm(SRC, org=0x2000, name="prog")
    d = tempfile.mkdtemp()
    a = os.path.join(d, "p.asm"); open(a, "w").write(asm)
    subprocess.run(["sdas8051", "-l", "-o", a], cwd=d, check=True, capture_output=True)
    subprocess.run(["sdld", "-i", "-x", "-m", os.path.join(d, "p.ihx"),
                    os.path.join(d, "p.rel")], cwd=d, check=True, capture_output=True)
    writes = []
    for ln in open(os.path.join(d, "p.ihx")):
        if not ln.startswith(":"):
            continue
        n = int(ln[1:3], 16); addr = int(ln[3:7], 16); typ = int(ln[7:9], 16)
        if typ:
            continue
        for i in range(n):
            writes.append((addr + i, int(ln[9 + 2 * i:11 + 2 * i], 16)))
    e = rob3_ucsim.UCSimEngine(hex_path=rom, binary=binary)
    for addr, b in writes:
        e.command("set mem rom 0x%04x 0x%02x" % (addr, b))
    e.command("set mem iram 0x40 0 0 0 0 0 0")
    e.command("set mem iram 0x1f 0x00")
    e.command("pc 0x2000")
    e.command("step 60", timeout=10)
    nt_t = [e._dump_byte("iram", 0x40 + k) for k in range(3)]
    nt_do = e._dump_byte("iram", 0x1f)
    e.close()

    assert nt_t == it_t, f"targets differ: native={nt_t} interp={it_t}"
    assert nt_do == it_do, f"dout differs: native=0x{nt_do:02x} interp=0x{it_do:02x}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
