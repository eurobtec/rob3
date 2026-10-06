"""Command-line interface: ``tbpsc`` compiles a TBPS source file.

Usage::

    tbpsc SOURCE [-o OUTPUT.bin] [--label-table] [--hex]

By default it writes the program *body* (8-byte slots) as raw bytes.  With
``--label-table`` it prepends the 256-byte page-0x80 label table, producing the
two SRAM pages (0x80 + 0x81) back to back -- the image a loader would push into
the robot's SRAM.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .compiler import compile_source


def _format_hex(data: bytes, base: int) -> str:
    out = []
    for i in range(0, len(data), 8):
        chunk = data[i : i + 8]
        hexs = " ".join(f"{b:02X}" for b in chunk)
        out.append(f"{base + i:04X}:  {hexs}")
    return "\n".join(out)


def _trace(prog) -> int:
    """Single-step a compiled program through the ROB3 ROM in ucSim."""
    try:
        import rob3_ucsim
    except ImportError:
        print("error: --trace needs the 'rob3_ucsim' package "
              "(pip install rob3_ucsim)", file=sys.stderr)
        return 2
    from . import isa
    from .simload import load_program
    from .debug import TbpsDebugger

    try:
        binary = rob3_ucsim.find_ucsim()
    except FileNotFoundError:
        print("error: no ucsim_51/s51 binary (set UCSIM_51)", file=sys.stderr)
        return 2
    rom = rob3_ucsim.default_hex()
    if not rom:
        print("error: no ROB3 ROM image (set ROB3_HEX)", file=sys.stderr)
        return 2

    eng = rob3_ucsim.UCSimEngine(hex_path=rom, binary=binary)
    try:
        load_program(eng, prog)
        dbg = TbpsDebugger(eng, prog)
        dbg.reset_to(isa.SRAM_BODY_BASE)
        print("TBPS single-step trace (via ucSim):")
        for f in dbg.run(max_steps=256):
            print("  " + str(f))
            if f.ended:
                break
    finally:
        eng.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="tbpsc",
        description="Compile a ROB3 Teach Box (TBPS) source file to its "
        "ROM-faithful program image.",
    )
    ap.add_argument("--version", action="version", version=f"tbpsc {__version__}")
    ap.add_argument("source", nargs="?",
                    help="TBPS source file (.tbps primary; .dat/.tb/.txt accepted)")
    ap.add_argument("-o", "--output", help="output binary (default: stdout hex)")
    ap.add_argument(
        "--label-table",
        action="store_true",
        help="prepend the 256-byte page-0x80 label table (full SRAM image)",
    )
    ap.add_argument("--hex", action="store_true", help="print an annotated hex dump")
    ap.add_argument(
        "--disasm",
        action="store_true",
        help="disassemble SOURCE (a program-body .bin) back to TBPS instead of compiling",
    )
    ap.add_argument(
        "--trace",
        action="store_true",
        help="compile SOURCE and single-step it through the ROB3 ROM in ucSim "
        "(TBPS source-level debugger; needs UCSIM_51 + ROB3_HEX)",
    )
    ap.add_argument(
        "--native",
        action="store_true",
        help="emit native MCS-51 (sdas8051) assembly instead of bytecode "
        "(AOT backend; reuses the firmware RAM map + dout_write 0x07D0)",
    )
    ap.add_argument(
        "--org", default="0x2000",
        help="origin address for --native output (default 0x2000)",
    )
    args = ap.parse_args(argv)

    if not args.source:
        ap.error("the following arguments are required: source")

    if args.disasm:
        from .disasm import disassemble_text
        try:
            with open(args.source, "rb") as f:
                body = f.read()
        except OSError as e:
            print(f"error: cannot read {args.source}: {e}", file=sys.stderr)
            return 2
        print(disassemble_text(body))
        return 0

    try:
        with open(args.source, "r", encoding="utf-8") as f:
            src = f.read()
    except OSError as e:
        print(f"error: cannot read {args.source}: {e}", file=sys.stderr)
        return 2

    if args.native:
        from .native import generate_asm
        from .errors import CompileError
        try:
            org = int(args.org, 0)
            asm = generate_asm(src, org=org)
        except CompileError as e:
            print(f"compilation failed:\n{e}", file=sys.stderr)
            return 1
        if args.output:
            with open(args.output, "w") as f:
                f.write(asm)
            print(f"wrote native asm to {args.output}")
        else:
            print(asm)
        return 0

    prog = compile_source(src)
    if not prog.ok:
        print(f"compilation failed: {len(prog.diagnostics)} error(s)\n", file=sys.stderr)
        for d in prog.diagnostics:
            print(d, file=sys.stderr)
        return 1

    if args.trace:
        return _trace(prog)

    body = prog.body_bytes()
    if args.label_table:
        image = prog.label_table_bytes() + body
        base = 0x8000
    else:
        image = body
        base = 0x8100

    if args.output:
        with open(args.output, "wb") as f:
            f.write(image)
        print(f"wrote {len(image)} bytes to {args.output}")
    if args.hex or not args.output:
        print(_format_hex(image, base))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
