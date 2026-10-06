"""Authoritative TBPS instruction encoding, derived from the ROB3 8031 ROM.

Every constant here is traceable to the annotated firmware. Provenance tags
follow the project convention:

* ``[BYTE]`` -- decoded directly from the ROM bytes (byte-exact).
* ``[SIM]``  -- confirmed by running the ROM in ucSim and observing state.
* ``[INFER]`` -- inferred from context; a hypothesis, not yet proven.

Ground truth (``firmware/src/annotated/program.asm`` + ``rs232.asm`` +
``hardware/host/command.md``):

The stored-program instruction stream reuses the *same* command-byte bit
fields the RS-232 handler decodes (``cmd_class0`` at 0x0440).  The executor
``prog_exec`` (0x0941) fetches one opcode into IRAM ``0x27`` and branches on
``ACC`` bits .7/.6/.5/.4/.3 and the low-3 axis field.  Most instructions
occupy a FIXED 8-byte slot (``PC += 8`` at 0x0A01/0x0A03).  [BYTE][SIM]

Opcode bit-field decode in ``prog_exec`` [BYTE]:

====================  ===========================  =========================
ACC bits              Class                        Handler
====================  ===========================  =========================
.7 = 1                END / program halt           0x094D (anl 0x28,#0x03)
.6=1 .5=1             POS + speed (target)         0x0957.. -> 0x40.., 0x70..
.6=1 .5=0             NOP-ish (clear state bits)   0x099A (anl 0x28,#0x07)
.6=0 .5=0 .4=0        POS set-position             0x09B0.. -> 0x50..
.6=0 .5=0 .4=1 .3=0   OUT (digital out)            0x09D4 (portb_write 0x07D3)
.6=0 .5=0 .4=1 .3=1   TIM (delay)                  0x09E1 -> 0x1A/0x1B
.6=0 .5=1             GOTO / IF (branch)           0x09F1 -> prog_goto 0x0A33
====================  ===========================  =========================

``MARK`` (opcode ``0x1F``) is NOT executed by ``prog_exec``; it is consumed by
the label-table PREPROCESSOR ``prog_prepare`` (0x0803): it records the current
PC into the page-0x80 label table at index ``rl(m)`` (2 bytes per label).
[BYTE][SIM]

Within class-0, the low 3 bits are the axis (0..5) or ``7`` = all-axes, and
bit3 is the RS-232 acknowledge-request ``R`` bit (0x23.1).  For the *stored*
program the ``R`` bit is unused by movement opcodes, but TIM/OUT/GOTO/IF
repurpose bit4/bit3 as shown above.
"""

from __future__ import annotations

from enum import Enum


# --- SRAM program-store layout (firmware/src/annotated/program.asm) ----------
# Page 0x80 = 0x8000 holds the 2-byte-per-label table + header/end sentinels;
# the program body starts at page 0x81 = 0x8100.  [BYTE][SIM]
SRAM_LABEL_PAGE = 0x80          # IRAM 0x3E = PROG_PAGE   [SIM: =0x80]
SRAM_BODY_PAGE = 0x81           # IRAM 0x3F = PROG_PAGE1   [SIM: =0x81]
SRAM_LABEL_BASE = SRAM_LABEL_PAGE << 8      # 0x8000
# Program body spans 0x8100..0x9FFF in the 8 KB HM6264 (command.md "Program
# memory map"); that is the capacity a compiled body must fit within.  [BYTE]
SRAM_BODY_END = 0x9FFF
SRAM_BODY_CAPACITY = SRAM_BODY_END - (SRAM_BODY_PAGE << 8) + 1   # 0x1F00 = 7936 B
SRAM_BODY_BASE = SRAM_BODY_PAGE << 8        # 0x8100

# Fixed instruction slot size: prog_exec advances PC by 8 (0x0A01/0x0A03). [BYTE][SIM]
SLOT_SIZE = 8

# End-of-program sentinel the preprocessor validates/writes.  [BYTE]
#   header low-3 bits must be 0 (0x0821 anl A,#0x07 / jnz prog_end)
#   end sentinel byte = 0x83 (0x0837 cjne A,#0x83 ; 0x0897 mov A,#0x83)
HEADER_SENTINEL_LOW3_MASK = 0x07
END_SENTINEL = 0x83


# --- Opcode / bit-field constants (all [BYTE] from prog_exec/cmd_class0) ------
BIT7_END = 0x80          # ACC.7 set -> END / program halt
BIT6 = 0x40
BIT5 = 0x20
BIT4 = 0x10
BIT3 = 0x08              # RS-232 "R" ack bit; TIM selector in the 0x1x class
AXIS_ALL = 0x07          # low-3 field == 7 means "all axes"

# Base opcodes (axis OR'd into the low 3 bits where applicable).
OP_POS_SET = 0x00        # set-position (write position[0x50+axis], no motion)
                         #   RS-232 0x00/0x07 class; used by POS (store all).
OP_POS_MOVE = 0x60       # POS a . n  "move axis a to position n": writes
                         #   target[0x40+axis] and arms motion.  prog_exec
                         #   bit6=1,bit5=1 path.  [SIM] (demo_hello_program.sh:
                         #   0x60|axis -> target[0x40+axis]; confirmed live).
OP_POS_SPEED = 0x70      # move + speed (target+speed)      -> 0x70+axis, 0x7F=all
OP_OUT = 0x10            # OUT: bit4 set, bit3 clear
OP_TIM = 0x18            # TIM: bit4 set, bit3 set
OP_GOTO = 0x20           # GOTO/IF class: bit5 set (bit6=0)
OP_IF = 0x20             # same class as GOTO; discriminated by operands [INFER]
OP_MARK = 0x1F           # MARK -- preprocessor opcode (label definition) [BYTE][SIM]
OP_END = 0x80            # program end / INS. -> any bit7-set byte [BYTE]
OP_HALT_3BYTE = 0x36     # DEL. -- the special 3-byte instruction [BYTE][INFER meaning]


# --- Value ranges (hardware/teachbox/README.md "Summary of all Instructions") -
LABEL_MIN, LABEL_MAX = 0, 118          # MARK m / GOTO m
AXIS_MIN, AXIS_MAX = 1, 6              # user-facing axis is 1..6 (firmware 0..5)
POS_MIN, POS_MAX = 0, 255             # firmware positions are 8-bit [HW]
GRIPPER_MAX = 100                      # electric gripper 0..100
DELAY_MIN, DELAY_MAX = 0, 65535        # TIM t (x100 ms)
COUNTER_MIN, COUNTER_MAX = 0, 255      # GOTO m . n
PORT_MIN, PORT_MAX = 1, 8             # IF i / OUT k


class Mnemonic(str, Enum):
    """TBPS source mnemonics (hardware/teachbox/README.md section 6)."""

    STOP = "STOP"
    MARK = "MARK"
    POS = "POS"
    TIM = "TIM"
    GOTO = "GOTO"
    IF = "IF"
    OUT = "OUT"
    INS = "INS"      # INS .  -> program end
    DEL = "DEL"      # DEL .  -> halt / program separator
    CLR = "CLR"      # mode change (no stored byte)
    NOP = "NOP"      # . ENT  -> no-op


def axis_user_to_fw(axis: int) -> int:
    """Convert a user axis (1..6) to the firmware axis field (0..5)."""
    return axis - 1


def pos_set_opcode(axis_fw: int) -> int:
    """Opcode for the set-position class (write position[0x50+axis]).  [BYTE]"""
    return OP_POS_SET | (axis_fw & AXIS_ALL)


def pos_move_opcode(axis_fw: int) -> int:
    """Opcode for ``POS a . n`` -- move axis to a target.  [SIM]

    Writes ``target[0x40+axis]`` and arms motion (prog_exec bit6=1,bit5=1).
    """
    return OP_POS_MOVE | (axis_fw & AXIS_ALL)


def pos_speed_opcode(axis_fw: int) -> int:
    """Opcode for a single-axis position+speed move.  [BYTE]"""
    return OP_POS_SPEED | (axis_fw & AXIS_ALL)
