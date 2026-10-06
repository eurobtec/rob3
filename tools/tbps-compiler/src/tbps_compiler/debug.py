"""TBPS source-level debugger — single-step a stored program in ucSim.

Steps the *stored TBPS program* one instruction at a time (MARK/POS/TIM/…),
not one 8051 machine instruction. Each step re-enters the firmware interpreter
``prog_exec`` (0x0941), runs exactly one program instruction (to the
end-of-instruction PC advance at 0x0A0B, or the program-end branch at 0x0950),
then reports:

  * the program PC (IRAM 0x66:0x67) before/after,
  * the decoded TBPS instruction at that PC (via the disassembler),
  * a snapshot of the relevant firmware state (axis targets/positions, the
    program state byte 0x28, the digital-out shadow).

Duck-typed on the ucSim engine (``command``/``run``), like :mod:`simload`, so
``tbps_compiler`` keeps no hard simulator dependency. Use with
``rob3_ucsim.UCSimEngine`` / ``pyucsim.UCSimEngine``.

Typical use::

    from tbps_compiler import compile_source
    from tbps_compiler.simload import load_program, set_program_pc
    from tbps_compiler.debug import TbpsDebugger

    prog = compile_source(src, raise_on_error=True)
    load_program(eng, prog)
    dbg = TbpsDebugger(eng, prog)
    dbg.reset_to(prog.pc_of_label(0))     # start at MARK 0
    for _ in range(20):
        frame = dbg.step()
        print(frame)
        if frame.ended:
            break
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import isa
from .codegen import CompiledProgram
from .disasm import decode_slot
from . import simload

PROG_EXEC = 0x0941
PC_ADVANCE_RET = 0x0A0B
END_BRANCH = 0x0950        # anl 0x28,#0x03 (program end)


@dataclass
class StepFrame:
    """State captured for one TBPS single-step."""

    index: int                      # step counter
    pc_before: int                  # program PC before the step
    pc_after: int                   # program PC after the step
    text: str                       # decoded TBPS instruction executed
    opcode: int
    ended: bool = False             # True if the END branch was hit
    targets: list[int] = field(default_factory=list)   # IRAM 0x40..0x45
    positions: list[int] = field(default_factory=list)  # IRAM 0x50..0x55
    state28: int = 0                # program state byte 0x28
    note: str = ""

    def __str__(self) -> str:
        tag = " [END]" if self.ended else ""
        return (f"#{self.index:<3} 0x{self.pc_before:04X}: {self.text:<16}"
                f"-> PC 0x{self.pc_after:04X}  targets={_hx(self.targets)}"
                f"  0x28=0x{self.state28:02x}{tag}")


def _hx(xs):
    return "[" + " ".join("%02x" % x for x in xs) + "]"


class TbpsDebugger:
    """Single-step a stored TBPS program through the firmware interpreter."""

    def __init__(self, engine, prog: CompiledProgram | None = None):
        self.eng = engine
        self.prog = prog
        self._i = 0

    # -- helpers --------------------------------------------------------------
    def _byte(self, space: str, addr: int) -> int:
        return simload._dump_byte(self.eng, space, addr)

    def prog_pc(self) -> int:
        lo = self._byte("iram", simload.IRAM_PROG_PC_LO)
        hi = self._byte("iram", simload.IRAM_PROG_PC_HI)
        return (hi << 8) | lo

    def _slot_at(self, pc: int) -> tuple[int, bytes]:
        """Read the opcode + 7 operand bytes of the slot at SRAM ``pc``."""
        b = [self._byte("xram", pc + k) for k in range(isa.SLOT_SIZE)]
        return b[0], bytes(b[1:])

    # -- control --------------------------------------------------------------
    def reset_to(self, pc: int, *, set_run_state: bool = True) -> None:
        """Point the interpreter PC at ``pc`` and arm the run state."""
        simload.set_program_pc(self.eng, pc)
        if set_run_state:
            # 0x28 = running/motion/conditional; 0x26 = step flag clear
            # (matches the interpreter's expectations; see demo_hello_program).
            self.eng.command("set mem iram 0x28 0x0e")
            self.eng.command("set mem iram 0x26 0x00")
        self._i = 0

    def step(self, timeout: float = 15.0) -> StepFrame:
        """Execute exactly one TBPS instruction and return a :class:`StepFrame`."""
        pc_before = self.prog_pc()
        opcode, operands = self._slot_at(pc_before)
        decoded = decode_slot(opcode, operands, pc_before)

        # Run the interpreter for one instruction: enter prog_exec, stop at
        # either the normal PC-advance RET or the program-end branch.
        self.eng.command("pc 0x%04x" % PROG_EXEC)
        self.eng.command("break 0x%04x" % PC_ADVANCE_RET)
        self.eng.command("break 0x%04x" % END_BRANCH)
        out = self.eng.run(timeout=timeout)
        self.eng.command("clear 0x%04x" % PC_ADVANCE_RET)
        self.eng.command("clear 0x%04x" % END_BRANCH)

        ended = ("0x%06x" % END_BRANCH) in out.lower() or \
                ("0x%04x" % END_BRANCH) in out.lower()
        pc_after = pc_before if ended else self.prog_pc()

        targets = [self._byte("iram", 0x40 + k) for k in range(6)]
        positions = [self._byte("iram", 0x50 + k) for k in range(6)]
        state28 = self._byte("iram", 0x28)

        self._i += 1
        return StepFrame(
            index=self._i, pc_before=pc_before, pc_after=pc_after,
            text=decoded.text, opcode=opcode, ended=ended,
            targets=targets, positions=positions, state28=state28,
            note=decoded.note,
        )

    def run(self, max_steps: int = 256, timeout: float = 15.0) -> list[StepFrame]:
        """Step until an END instruction or ``max_steps``; return all frames."""
        frames = []
        for _ in range(max_steps):
            f = self.step(timeout=timeout)
            frames.append(f)
            if f.ended:
                break
        return frames
