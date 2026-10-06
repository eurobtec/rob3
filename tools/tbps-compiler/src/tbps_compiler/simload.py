"""Helpers to load a compiled TBPS program into a running ucSim session.

Two paths, matching the two ways the real robot receives a program:

* :func:`load_program` -- write the program straight into external SRAM (the
  "direct load": label table at 0x8000, body at 0x8100), and set the firmware
  page registers.
* :func:`upload_program` -- stream the program over the firmware's RS-232
  ``0x81`` block protocol (header, pointer, count, bytes + ``0x83`` sentinel),
  so the *firmware itself* stores it to SRAM and marks it program-loaded.

Both take an ``engine`` that is duck-typed: any object with a
``command(str) -> str`` method and (for upload) ``run()``/breakpoint commands,
e.g. :class:`rob3_ucsim.UCSimEngine` or :class:`pyucsim.UCSimEngine`.  This keeps
``tbps_compiler`` free of a hard simulator dependency.

Firmware landmarks (firmware/src/annotated/program.asm, rs232.asm):
"""

from __future__ import annotations

from typing import Protocol

from . import isa
from .codegen import CompiledProgram

# IRAM / code landmarks
IRAM_LABEL_PAGE = 0x3E       # = 0x80
IRAM_BODY_PAGE = 0x3F        # = 0x81
IRAM_PROG_PC_LO = 0x66
IRAM_PROG_PC_HI = 0x67
IRAM_STATE = 0x28            # .1 loaded, .2 running, .3 motion
RX_AFTER_SBUF = 0x030C       # RX handler entry just after MOV A,SBUF
SERIAL_EXIT = 0x0525
PROG_EXEC = 0x0941
PC_ADVANCE_RET = 0x0A0B
SYS_DISPATCH = 0x03B2        # system-class dispatch staging (MOV R5,A)
SYS_READPROG = 0x03C9        # program readback: TX "stream from SRAM"


class Engine(Protocol):
    def command(self, line: str, timeout: float = ...) -> str: ...
    def run(self, timeout: float = ...) -> str: ...


# --- direct SRAM load --------------------------------------------------------
def load_program(engine: Engine, prog: CompiledProgram, *, set_pages: bool = True) -> None:
    """Write ``prog`` straight into the simulator's external SRAM (xram).

    Writes the full body (incl. zero padding, so no stale xram leaks into a
    slot), zero-fills + writes the label table (so a label's zero bytes can't be
    left as stale xram), then sets the page registers.
    """
    body = prog.body_bytes()
    for i, b in enumerate(body):
        engine.command("set mem xram 0x%04x 0x%02x" % (isa.SRAM_BODY_BASE + i, b))
    # Write the full label table (incl. zeros) so a label whose PC has a 0x00
    # byte, or an undefined slot, is not left as stale xram (which would make
    # prog_goto resolve to garbage).
    table = prog.label_table_bytes()
    highest = max((2 * lbl + 1 for lbl in prog.labels), default=-1)
    for i in range(highest + 1):
        engine.command("set mem xram 0x%04x 0x%02x" % (isa.SRAM_LABEL_BASE + i, table[i]))
    if set_pages:
        engine.command("set mem iram 0x%02x 0x%02x" % (IRAM_LABEL_PAGE, isa.SRAM_LABEL_PAGE))
        engine.command("set mem iram 0x%02x 0x%02x" % (IRAM_BODY_PAGE, isa.SRAM_BODY_PAGE))


def set_program_pc(engine: Engine, addr: int) -> None:
    """Point the interpreter's program counter (IRAM 0x66:0x67) at ``addr``."""
    engine.command("set mem iram 0x%02x 0x%02x" % (IRAM_PROG_PC_LO, addr & 0xFF))
    engine.command("set mem iram 0x%02x 0x%02x" % (IRAM_PROG_PC_HI, (addr >> 8) & 0xFF))

PROG_GOTO_RET = 0x0A41    # prog_goto's own RET (branch instructions exit here,
                          # not via PC_ADVANCE_RET)


def run_one_instruction(engine: Engine, timeout: float = 15.0) -> str:
    """Enter prog_exec and run until the instruction completes.

    Most instructions exit at the PC-advance RET (0x0A0B); a GOTO/IF that
    *branches* resolves the label in prog_goto and exits at its RET (0x0A41).
    Break at both so a branch doesn't free-run past into the jumped-to code.
    """
    engine.command("pc 0x%04x" % PROG_EXEC)
    engine.command("break 0x%04x" % PC_ADVANCE_RET)
    engine.command("break 0x%04x" % PROG_GOTO_RET)
    out = engine.run(timeout=timeout)
    engine.command("clear 0x%04x" % PC_ADVANCE_RET)
    engine.command("clear 0x%04x" % PROG_GOTO_RET)
    return out


# --- RS-232 0x81 block upload ------------------------------------------------
def upload_frame(prog: CompiledProgram) -> bytes:
    """Build the RS-232 ``0x81`` upload frame for ``prog``.

    Frame = ``0x81``, pointer = payload length, count = ``0``, program body,
    then the ``0x83`` stream sentinel.  (rx_setcount does ``inc R2`` so count 0
    means one run; the pointer streams the whole payload; the final ``0x83``
    passes the firmware's readback check and sets program-loaded.)
    """
    body = prog.body_bytes()
    payload = body + bytes([isa.END_SENTINEL])
    return bytes([0x81, len(payload) & 0xFF, 0x00]) + payload


def _rx_feed(engine: Engine, byte: int) -> None:
    """Feed one byte into the firmware RX handler (post-SBUF entry)."""
    engine.command("set mem sfr 0xe0 0x%02x" % (byte & 0xFF))
    engine.command("pc 0x%04x" % RX_AFTER_SBUF)
    engine.command("break 0x%04x" % SERIAL_EXIT)
    engine.run(timeout=10.0)
    engine.command("clear 0x%04x" % SERIAL_EXIT)


def upload_program(engine: Engine, prog: CompiledProgram, *, set_pages: bool = True) -> None:
    """Upload ``prog`` over the firmware's RS-232 ``0x81`` block protocol.

    Drives the real RX handler byte-by-byte; the firmware stores the program to
    SRAM via MOVX and (on the valid ``0x83``-terminated frame) sets
    program-loaded (``0x28.1``).  ucSim's UART is byte-level, so bytes are
    injected at the post-SBUF entry (0x030C) exactly as the firmware's own
    serial tests do.
    """
    if set_pages:
        engine.command("set mem iram 0x%02x 0x%02x" % (IRAM_LABEL_PAGE, isa.SRAM_LABEL_PAGE))
        engine.command("set mem iram 0x%02x 0x%02x" % (IRAM_BODY_PAGE, isa.SRAM_BODY_PAGE))
    engine.command("set mem iram 0x24 0x00")       # clear RX frame state
    engine.command("set mem iram 0x28 0x00")       # clear program state
    for b in upload_frame(prog):
        _rx_feed(engine, b)


# --- RS-232 program readback (download to host) ------------------------------
def _dump_byte(engine: Engine, space: str, addr: int) -> int:
    import re
    out = engine.command("dump %s 0x%04x 0x%04x" % (space, addr, addr))
    m = re.search(r"0x0*%x\b[^\n]*?\s([0-9a-fA-F]{2})\b" % addr, out, re.I)
    return int(m.group(1), 16) if m else -1


def trigger_readback(engine: Engine) -> None:
    """Drive the firmware's program-readback (``0x80`` system command).

    Requires a program to be loaded (``0x28.1``).  Runs ``sys_readprog``
    (0x03C9), which sets TX mode ``0x25.6`` and the SRAM stream pointer
    (0x30:0x31 = 0x80FD); the UART TX helper then streams ``header + program
    bytes`` framed with ETX to the host.
    """
    engine.command("set mem sfr 0xe0 0x80")         # system command 0x80, sub-code 0
    engine.command("pc 0x%04x" % SYS_DISPATCH)
    engine.command("break 0x%04x" % SERIAL_EXIT)
    engine.run(timeout=10.0)
    engine.command("clear 0x%04x" % SERIAL_EXIT)


def read_program(engine: Engine, max_bytes: int = 256) -> bytes:
    """Read the stored program back from the robot over RS-232 (``0x80``).

    Returns the program **body** bytes (0x8100..), reconstructed from the SRAM
    stream the firmware would transmit.  ucSim's MCS-51 UART is byte-level and
    does not drive the TXD pin, so instead of sniffing the wire we trigger the
    readback (to exercise the real ``sys_readprog`` setup) and read the bytes
    from the SRAM stream region the firmware streams from -- i.e. the exact
    bytes that would go on the wire.

    The byte-count header is at 0x80FE; the body follows at 0x8100.
    """
    trigger_readback(engine)
    count = _dump_byte(engine, "xram", 0x80FE)
    n = count if 0 <= count <= max_bytes else max_bytes
    body = bytearray()
    for i in range(n):
        body.append(_dump_byte(engine, "xram", isa.SRAM_BODY_BASE + i) & 0xFF)
    return bytes(body)
