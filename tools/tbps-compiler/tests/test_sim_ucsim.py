"""ucSim verification: run compiled TBPS bytes through the real ROB3 ROM.

Uses the project's ROB3-aware ucSim harness (``rob3_ucsim``, built on
``pyucsim``) to boot the firmware, load a compiled program, and confirm the
firmware's own interpreter (``prog_exec`` at 0x0941) decodes the compiler's
bytes correctly.

Two load paths are exercised, per the project's two documented ways to get a
program into the robot:

1. ``test_direct_load_*`` -- write the program straight into external SRAM
   (xram) with ``set mem`` and run the interpreter on it.
2. ``test_rs232_upload`` -- push the program over the serial ``0x81`` block
   command so the *firmware* writes SRAM, then run it.

The tests SKIP (not fail) when the ucSim binary or ROM image is unavailable, so
the pure-Python unit tests still run in a bare environment.  Point them at your
build with::

    export UCSIM_51=/home/.../ucsim/src/sims/s51.src/ucsim_51
    export ROB3_HEX=/home/.../rob3/firmware/hex/M2764A@DIP28.HEX
"""

from __future__ import annotations

import os
import re

import pytest

from tbps_compiler import compile_source
from tbps_compiler import isa

rob3_ucsim = pytest.importorskip("rob3_ucsim")

# Firmware landmarks (firmware/src/annotated/program.asm) ---------------------
PROG_EXEC = 0x0941        # instruction executor entry
PORTB_WRITE_LCALL = 0x09D9  # LCALL 0x07D3 inside the OUT branch
TIM_STORE = 0x09E6        # MOV 0x1A,A inside the TIM branch
PC_ADVANCE_RET = 0x0A0B   # RET after PC += 8
IRAM_PROG_PC_LO = 0x66
IRAM_PROG_PC_HI = 0x67
IRAM_LABEL_PAGE = 0x3E    # = 0x80
IRAM_BODY_PAGE = 0x3F     # = 0x81


def _default_rom() -> str | None:
    """Resolve the ROB3 ROM: ROB3_HEX, else the in-repo firmware/hex image."""
    env = rob3_ucsim.default_hex()
    if env:
        return env
    here = os.path.dirname(__file__)
    cand = os.path.abspath(
        os.path.join(here, "..", "..", "..", "firmware", "hex", "M2764A@DIP28.HEX")
    )
    return cand if os.path.exists(cand) else None


@pytest.fixture()
def engine():
    """A booted ROB3 ucSim engine, or skip if the sim/ROM isn't available."""
    try:
        binary = rob3_ucsim.find_ucsim()
    except FileNotFoundError:
        pytest.skip("no ucsim_51/s51 binary (set UCSIM_51)")
    rom = _default_rom()
    if not rom:
        pytest.skip("no ROB3 ROM image (set ROB3_HEX)")
    eng = rob3_ucsim.UCSimEngine(hex_path=rom, binary=binary)
    yield eng
    eng.close()


def _load_program(eng, prog) -> None:
    """Fill xram with the compiled program (label table + body).

    Writes every slot byte (including zeros) so no stale xram leaks into a
    slot, then sets the interpreter's page registers.  One ``set mem`` per byte,
    never pipelined -- the discipline the engine enforces.
    """
    # Clear the slot span first, then write the full image (incl. zeros).
    body = prog.body_bytes()
    for addr, b in prog.sram_writes(include_zero=True):
        if isa.SRAM_BODY_BASE <= addr < isa.SRAM_BODY_BASE + len(body):
            eng.command("set mem xram 0x%04x 0x%02x" % (addr, b))
        elif b:  # label table: only non-zero entries
            eng.command("set mem xram 0x%04x 0x%02x" % (addr, b))
    eng.command("set mem iram 0x%02x 0x%02x" % (IRAM_LABEL_PAGE, isa.SRAM_LABEL_PAGE))
    eng.command("set mem iram 0x%02x 0x%02x" % (IRAM_BODY_PAGE, isa.SRAM_BODY_PAGE))
    # Program state: 0x28 = running/motion/conditional, 0x26 = step flag clear
    # (matches simulator/tests/demo_hello_program.sh).
    eng.command("set mem iram 0x28 0x0e")
    eng.command("set mem iram 0x26 0x00")


def _set_prog_pc(eng, addr: int) -> None:
    eng.command("set mem iram 0x%02x 0x%02x" % (IRAM_PROG_PC_LO, addr & 0xFF))
    eng.command("set mem iram 0x%02x 0x%02x" % (IRAM_PROG_PC_HI, (addr >> 8) & 0xFF))


def _prog_pc(eng) -> int:
    lo = eng._dump_byte("iram", IRAM_PROG_PC_LO)
    hi = eng._dump_byte("iram", IRAM_PROG_PC_HI)
    return (hi << 8) | lo


def _run_one_instruction(eng) -> str:
    """Set CPU PC to prog_exec and run until the end-of-instruction RET."""
    eng.command("pc 0x%04x" % PROG_EXEC)
    eng.command("break 0x%04x" % PC_ADVANCE_RET)
    out = eng.run(timeout=20.0)
    eng.command("clear 0x%04x" % PC_ADVANCE_RET)
    return out


# --- direct-load path --------------------------------------------------------
def test_direct_load_out_decodes_and_advances_slot(engine):
    """A compiled OUT reaches the Port-B writer and advances PC by one 8-byte slot."""
    prog = compile_source("MARK 0\nOUT 1 +\nINS .", raise_on_error=True)
    _load_program(engine, prog)

    # Point the interpreter at the OUT slot (slot 1 -> 0x8108).
    out_slot = isa.SRAM_BODY_BASE + 1 * isa.SLOT_SIZE
    _set_prog_pc(engine, out_slot)

    # Run to just before the Port-B write to prove the OUT branch is taken.
    engine.command("pc 0x%04x" % PROG_EXEC)
    engine.command("break 0x%04x" % PORTB_WRITE_LCALL)
    out = engine.run(timeout=20.0)
    engine.command("clear 0x%04x" % PORTB_WRITE_LCALL)
    assert ("0x%04x" % PORTB_WRITE_LCALL) in out.lower() or \
           ("0x0009d9" in out.lower()), f"OUT did not reach portb_write: {out!r}"

    # Finish the instruction and confirm PC += 8.
    engine.command("break 0x%04x" % PC_ADVANCE_RET)
    engine.run(timeout=20.0)
    engine.command("clear 0x%04x" % PC_ADVANCE_RET)
    assert _prog_pc(engine) == out_slot + isa.SLOT_SIZE


def test_direct_load_tim_operand(engine):
    """A compiled TIM delivers its operand byte to the delay-store handler."""
    prog = compile_source("MARK 0\nTIM 50\nINS .", raise_on_error=True)
    _load_program(engine, prog)

    tim_slot = isa.SRAM_BODY_BASE + 1 * isa.SLOT_SIZE   # slot 1 -> 0x8108
    _set_prog_pc(engine, tim_slot)

    engine.command("pc 0x%04x" % PROG_EXEC)
    engine.command("break 0x%04x" % TIM_STORE)
    out = engine.run(timeout=20.0)
    engine.command("clear 0x%04x" % TIM_STORE)

    # ACC should hold our TIM operand (50 = 0x32) at the delay-store.
    m = re.search(r"ACC=\s*0x([0-9a-fA-F]{2})", out)
    assert m, f"did not reach TIM store (no ACC in output): {out!r}"
    assert int(m.group(1), 16) == 50


def test_direct_load_pos_moves_axis(engine):
    """A compiled POS a.n writes the axis target slot (0x40+axis) in IRAM."""
    # POS 1 . 200  -> move axis 0 to target 200.
    prog = compile_source("MARK 0\nPOS 1 . 200\nINS .", raise_on_error=True)
    _load_program(engine, prog)

    pos_slot = isa.SRAM_BODY_BASE + 1 * isa.SLOT_SIZE
    _set_prog_pc(engine, pos_slot)
    # Clear the target table so we observe the write.
    engine.command("set mem iram 0x40 0 0 0 0 0 0")
    _run_one_instruction(engine)

    # target[axis 0] lives at IRAM 0x40.
    assert engine._dump_byte("iram", 0x40) == 200


# --- RS-232 upload path ------------------------------------------------------
# The firmware's 0x81 block-upload protocol (rs232.asm, RX handler at 0x0305):
#   byte 0: 0x81            -> block mode (sets 0x24.3), frame in progress
#   byte 1: <run pointer>   -> rx_setptr (0x037B): R0 = run length, sets 0x24.4
#   byte 2: <count>         -> rx_setcount (0x0380): R2 = count; stream pointer
#                              0x30:0x31 = SRAM body page (0x3F -> 0x8100); writes
#                              the count to the SRAM header at 0x80FE
#   bytes 3..: <program>    -> streamed to SRAM via MOVX at the stream pointer
#
# ucSim's UART is byte-level and `MOV A,SBUF` returns the model's internal input
# (you cannot inject via `set mem sfr 0x99`), so -- exactly as the firmware's own
# serial tests do -- we enter the RX handler just AFTER the SBUF read (0x030C)
# with the byte seeded in ACC, and run to serial_exit (0x0525) once per byte.
RX_AFTER_SBUF = 0x030C
SERIAL_EXIT = 0x0525


def _rx_feed(eng, byte: int) -> None:
    """Feed one byte into the firmware RX handler (post-SBUF entry)."""
    eng.command("set mem sfr 0xe0 0x%02x" % (byte & 0xFF))
    eng.command("pc 0x%04x" % RX_AFTER_SBUF)
    eng.command("break 0x%04x" % SERIAL_EXIT)
    eng.run(timeout=10.0)
    eng.command("clear 0x%04x" % SERIAL_EXIT)


def test_rs232_upload_streams_program_into_sram(engine):
    """A compiled program uploaded over the 0x81 block path lands in SRAM.

    Drives the real firmware RX handler byte-by-byte with the 0x81 upload frame
    and asserts the compiler's program bytes are stored at the SRAM body base
    (0x8100) by the firmware's own MOVX stream path -- a true end-to-end upload,
    not a Python-side frame check.
    """
    prog = compile_source("MARK 0\nPOS 1 . 128\nINS .", raise_on_error=True)
    body = prog.body_bytes()

    # Set the SRAM page registers the uploader uses (0x3E=0x80, 0x3F=0x81) and
    # clear the RX frame-state byte.
    engine.command("set mem iram 0x3e 0x%02x" % isa.SRAM_LABEL_PAGE)
    engine.command("set mem iram 0x3f 0x%02x" % isa.SRAM_BODY_PAGE)
    engine.command("set mem iram 0x24 0x00")
    # Clear the destination so the assertion is meaningful.
    engine.command("set mem xram 0x8100 0x00 0x00 0x00")

    # Frame: 0x81, run-pointer, count, then the program bytes.
    _rx_feed(engine, 0x81)
    # After the header, 0x24.3 (block mode) must be set.
    assert engine._dump_byte("iram", 0x24) & 0x08, "0x81 did not enter block mode"

    _rx_feed(engine, 0x01)            # run pointer (one run)
    _rx_feed(engine, len(body))        # count = program length
    # The stream pointer (0x30:0x31) must now point at the SRAM body base.
    lo = engine._dump_byte("iram", 0x30)
    hi = engine._dump_byte("iram", 0x31)
    assert (hi << 8) | lo == isa.SRAM_BODY_BASE, "stream pointer not at 0x8100"

    # Stream the first few program bytes and confirm they land in SRAM.
    for b in body[:3]:
        _rx_feed(engine, b)
    assert engine._dump_byte("xram", isa.SRAM_BODY_BASE) == body[0]
    assert engine._dump_byte("xram", isa.SRAM_BODY_BASE + 1) == body[1]


def test_rs232_upload_then_run(engine):
    """Upload a compiled program over RS-232 (0x81), then RUN it. End-to-end.

    The complete chain the real host performs:
      1. upload the program via the firmware's 0x81 block protocol
         (header, pointer = payload length, count = 0, program bytes + the
         0x83 stream sentinel) -- the firmware stores it to SRAM with MOVX and
         sets its own program-loaded flag (0x28.1);
      2. point the interpreter at the uploaded program and run it;
      3. assert the uploaded instruction took effect.

    Frame counts: ``rx_setcount`` does ``inc R2`` (so count 0 -> one run) and
    ``R0`` = the pointer byte streams the whole payload; the final 0x83 byte
    triggers the readback sentinel check that sets 0x28.1.
    """
    prog = compile_source("MARK 0\nPOS 1 . 128\nINS .", raise_on_error=True)
    body = prog.body_bytes()
    payload = list(body) + [0x83]        # firmware stream sentinel

    engine.command("set mem iram 0x3e 0x%02x" % isa.SRAM_LABEL_PAGE)
    engine.command("set mem iram 0x3f 0x%02x" % isa.SRAM_BODY_PAGE)
    engine.command("set mem iram 0x24 0x00")
    engine.command("set mem iram 0x28 0x00")
    for i in range(len(body)):
        engine.command("set mem xram 0x%04x 0x00" % (isa.SRAM_BODY_BASE + i))

    # --- upload ---
    _rx_feed(engine, 0x81)                # block header
    _rx_feed(engine, len(payload))         # run pointer = payload length
    _rx_feed(engine, 0x00)                 # count = 0 (-> one run)
    for b in payload:
        _rx_feed(engine, b)

    # The firmware set program-loaded (0x28.1) on the valid 0x83-terminated frame.
    assert engine._dump_byte("iram", 0x28) & 0x02, "firmware did not mark program loaded"
    # SRAM holds exactly the compiler's bytes.
    stored = [engine._dump_byte("xram", isa.SRAM_BODY_BASE + i) for i in range(len(body))]
    assert stored == list(body)

    # --- run the uploaded program ---
    move_slot = isa.SRAM_BODY_BASE + 1 * isa.SLOT_SIZE    # the POS slot
    engine.command("set mem iram 0x66 0x%02x" % (move_slot & 0xFF))
    engine.command("set mem iram 0x67 0x%02x" % ((move_slot >> 8) & 0xFF))
    engine.command("set mem iram 0x40 0 0 0 0 0 0")
    engine.command("set mem iram 0x28 0x0e")
    engine.command("set mem iram 0x26 0x00")
    engine.command("pc 0x%04x" % PROG_EXEC)
    engine.command("break 0x%04x" % PC_ADVANCE_RET)
    engine.run(timeout=15.0)
    engine.command("clear 0x%04x" % PC_ADVANCE_RET)

    # The uploaded POS 1 . 128 executed: axis-0 target (IRAM 0x40) = 128.
    assert engine._dump_byte("iram", 0x40) == 128


# --- firmware robustness against bad input -----------------------------------
def test_garbage_upload_is_not_marked_loaded_and_runs_safely(engine):
    """Garbage uploaded over 0x81 WITHOUT a valid 0x83 sentinel is not marked
    program-loaded, and running it stops safely (no runaway)."""
    engine.command("set mem iram 0x3e 0x%02x" % isa.SRAM_LABEL_PAGE)
    engine.command("set mem iram 0x3f 0x%02x" % isa.SRAM_BODY_PAGE)
    engine.command("set mem iram 0x24 0x00")
    engine.command("set mem iram 0x28 0x00")
    for i in range(16):
        engine.command("set mem xram 0x%04x 0x00" % (isa.SRAM_BODY_BASE + i))

    garbage = [0xAA, 0x55, 0x3C, 0x99, 0xC7, 0x12, 0x7E, 0x01]
    _rx_feed(engine, 0x81)
    _rx_feed(engine, len(garbage))
    _rx_feed(engine, 0x00)
    for b in garbage:
        _rx_feed(engine, b)

    # No valid 0x83 terminator -> firmware did NOT set program-loaded (0x28.1).
    assert not (engine._dump_byte("iram", 0x28) & 0x02)

    # Try to run it anyway: the first byte 0xAA has bit7 set -> END branch.
    engine.command("set mem iram 0x66 0x00")
    engine.command("set mem iram 0x67 0x%02x" % isa.SRAM_BODY_PAGE)
    engine.command("set mem iram 0x28 0x0e")
    engine.command("set mem iram 0x26 0x00")
    engine.command("pc 0x%04x" % PROG_EXEC)
    engine.command("break 0x0950")          # the END branch (anl 0x28,#0x03)
    engine.command("break 0x%04x" % PC_ADVANCE_RET)
    out = engine.run(timeout=15.0)
    engine.command("clear 0x0950")
    engine.command("clear 0x%04x" % PC_ADVANCE_RET)
    # It stopped at one of the two safe exits (END branch or PC-advance), not runaway.
    assert "0x000950" in out.lower() or "0x000a0b" in out.lower()


def test_malformed_header_is_rejected_by_preprocessor(engine):
    """A program whose SRAM header has nonzero low-3 bits is rejected: the
    preprocessor (prog_prepare) bails to prog_end (0x0880) without building the
    label table."""
    engine.command("set mem iram 0x3e 0x%02x" % isa.SRAM_LABEL_PAGE)
    engine.command("set mem iram 0x3f 0x%02x" % isa.SRAM_BODY_PAGE)
    engine.command("set mem xram 0x80fe 0x05")   # low-3 bits nonzero -> malformed
    engine.command("set mem iram 0x28 0x02")     # pretend loaded so entry proceeds
    engine.command("pc 0x0803")                   # prog_prepare entry
    engine.command("break 0x0880")                # prog_end (bail/finalize)
    out = engine.run(timeout=10.0)
    engine.command("clear 0x0880")
    assert "0x000880" in out.lower()


def test_goto_undefined_label_lands_at_pc_zero(engine):
    """GOTO to an in-range but undefined label reads a zeroed table entry, so
    prog_goto sets the program PC to 0x0000 (why the compiler link-checks)."""
    engine.command("set mem iram 0x3e 0x%02x" % isa.SRAM_LABEL_PAGE)
    engine.command("set mem xram 0x80c8 0x00 0x00")   # label 100 table slot = 0
    engine.command("set mem iram 0x00 0x64")           # R0 = 100
    engine.command("set mem sfr 0xd0 0x00")            # PSW -> bank 0
    engine.command("pc 0x0a33")                         # prog_goto
    engine.command("break 0x0a41")                      # its RET
    engine.run(timeout=10.0)
    engine.command("clear 0x0a41")
    assert engine._dump_byte("iram", 0x66) == 0x00
    assert engine._dump_byte("iram", 0x67) == 0x00


# --- TBPS source-level debugger ---------------------------------------------
def test_tbps_debugger_single_steps_program(engine):
    """The TBPS debugger steps a stored program one TBPS instruction at a time,
    decoding each and capturing state, and detects the END."""
    from tbps_compiler.simload import load_program
    from tbps_compiler.debug import TbpsDebugger

    src = "MARK 0\nPOS 1 . 128\nPOS 2 . 64\nTIM 50\nOUT 1 +\nINS ."
    prog = compile_source(src, raise_on_error=True)
    load_program(engine, prog)
    dbg = TbpsDebugger(engine, prog)
    dbg.reset_to(isa.SRAM_BODY_BASE)

    frames = dbg.run(max_steps=10)
    texts = [f.text for f in frames]
    assert texts[:6] == [
        "MARK 0", "POS 1 . 128", "POS 2 . 64", "TIM 50", "OUT 1 +", "INS .",
    ]
    # Each step advances the PC by one 8-byte slot (until END).
    assert frames[1].pc_after == frames[1].pc_before + isa.SLOT_SIZE
    # The POS moves took effect in the axis target table.
    pos1 = next(f for f in frames if f.text == "POS 1 . 128")
    assert pos1.targets[0] == 128
    pos2 = next(f for f in frames if f.text == "POS 2 . 64")
    assert pos2.targets[1] == 64
    # The last frame is the END.
    assert frames[-1].ended and frames[-1].text == "INS ."


# --- full self-run from the main loop ---------------------------------------
def _adc_module() -> str | None:
    here = os.path.dirname(__file__)
    cand = os.path.abspath(
        os.path.join(here, "..", "..", "..", "simulator", "ucsim-modules", "adc", "adc.so")
    )
    return cand if os.path.exists(cand) else None


def _loopback_module() -> str | None:
    here = os.path.dirname(__file__)
    cand = os.path.abspath(
        os.path.join(here, "..", "..", "..", "simulator", "ucsim-modules", "loopback", "loopback.so")
    )
    return cand if os.path.exists(cand) else None


def test_program_self_runs_from_main_loop():
    """A compiled program loaded into SRAM runs via the firmware's main loop.

    This is the true "load and run": init reaches the main loop, and the
    main-loop motion executor (0x08FF) fetches and runs the program with no
    manual ``prog_exec`` entry.  Needs the loader ucsim_51 + adc cl_hw module
    (so init completes); skips otherwise.
    """
    try:
        binary = rob3_ucsim.find_ucsim()
    except FileNotFoundError:
        pytest.skip("no ucsim_51/s51 binary (set UCSIM_51)")
    rom = _default_rom()
    if not rom:
        pytest.skip("no ROB3 ROM image (set ROB3_HEX)")
    adc = _adc_module()
    if not adc:
        pytest.skip("no adc.so cl_hw module (needed to reach the main loop)")

    # A minimal program: move axis 0 to 0x80, then END.
    prog = compile_source("MARK 0\nPOS 1 . 128\nINS .", raise_on_error=True)

    hw = [adc]
    lb = _loopback_module()
    if lb:
        hw.append(lb)   # satisfies the P3.2/P3.4 pin gates so init reaches main loop
    eng = rob3_ucsim.UCSimEngine(hex_path=rom, binary=binary, load_hw=hw)
    try:
        if not eng.has_modules:
            pytest.skip("adc module did not load (no 'set hardware adc')")
        eng.reset(fixed_baud=False)          # auto-baud path reaches main loop
        if not eng.run_to(rob3_ucsim.MAIN_LOOP):
            # Reaching the main loop needs the P3.2/P3.4 pin gates satisfied
            # (the loopback cl_hw module); without it init sits in the
            # emergency-off handler.  That is firmware-init territory, covered
            # by the firmware repo's own tests -- out of scope for compiler
            # verification, so skip rather than fail.
            pytest.skip("firmware did not reach main loop (needs loopback module)")
        eng.command("set mem sfr 0xb0 0xfe")  # de-assert emergency-off (P3.2 high)

        # Load the compiled program body into SRAM (POS slot is slot 1).
        body = prog.body_bytes()
        for addr, b in prog.sram_writes(include_zero=True):
            if isa.SRAM_BODY_BASE <= addr < isa.SRAM_BODY_BASE + len(body):
                eng.command("set mem xram 0x%04x 0x%02x" % (addr, b))
            elif b:
                eng.command("set mem xram 0x%04x 0x%02x" % (addr, b))
        # Point the PC at the move slot (skip MARK) and set run state.
        move_slot = isa.SRAM_BODY_BASE + 1 * isa.SLOT_SIZE
        eng.command("set mem iram 0x66 0x%02x" % (move_slot & 0xFF))
        eng.command("set mem iram 0x67 0x%02x" % ((move_slot >> 8) & 0xFF))
        eng.command("set mem iram 0x40 0 0 0 0 0 0")
        eng.command("set mem iram 0x28 0x0e")
        eng.command("set mem iram 0x26 0x00")

        # Let the main loop's motion executor run the instruction.
        eng.command("break 0x0a0b")
        eng.command("step 200000", timeout=30.0)
        eng.command("clear 0x0a0b")
        assert eng._dump_byte("iram", 0x40) == 128
    finally:
        eng.close()


def test_goto_branches_to_label(engine):
    """A compiled GOTO (opcode 0x34) resolves its label and sets the program PC
    to that label's slot (verified correction: GOTO is 0x34, not 0x30)."""
    # MARK 0, GOTO 5, POS (skipped), MARK 5 @ slot 3 (0x8118), POS, INS.
    prog = compile_source(
        "MARK 0\nGOTO 5\nPOS 1 . 99\nMARK 5\nPOS 2 . 123\nINS .",
        raise_on_error=True,
    )
    from tbps_compiler.simload import load_program, set_program_pc, run_one_instruction
    load_program(engine, prog)
    assert prog.slots[1].opcode == 0x34          # GOTO unconditional
    target = prog.pc_of_label(5)

    # Start at the GOTO slot (preprocessor already built the label table via
    # load_program) and run it; the program PC must become label 5's slot.
    set_program_pc(engine, isa.SRAM_BODY_BASE + 1 * isa.SLOT_SIZE)
    engine.command("set mem iram 0x28 0x0e")
    engine.command("set mem iram 0x26 0x00")
    run_one_instruction(engine)
    lo = engine._dump_byte("iram", 0x66)
    hi = engine._dump_byte("iram", 0x67)
    assert (hi << 8 | lo) == target


def test_pos_with_speed_writes_target_and_speed(engine):
    """A compiled POS a.n,s (move+speed, 0x70+axis) writes target[0x40+axis]
    and speed[0x70+axis] (verified firmware class)."""
    from tbps_compiler.simload import load_program, set_program_pc, run_one_instruction
    prog = compile_source("MARK 0\nPOS 2 . 128 , 3\nINS .", raise_on_error=True)
    assert prog.slots[1].opcode == 0x71          # axis 2 -> fw 1 -> 0x70|1
    load_program(engine, prog)
    set_program_pc(engine, isa.SRAM_BODY_BASE + 1 * isa.SLOT_SIZE)
    engine.command("set mem iram 0x41 0x00")
    engine.command("set mem iram 0x71 0x00")
    engine.command("set mem iram 0x28 0x0e")
    engine.command("set mem iram 0x26 0x00")
    run_one_instruction(engine)
    assert engine._dump_byte("iram", 0x41) == 128     # target[axis1]
    assert engine._dump_byte("iram", 0x71) == 3       # speed[axis1]
