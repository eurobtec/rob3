#!/usr/bin/env python3
"""inc2sh.py — convert an sdas8051 equate .inc into a bash-sourceable file.

The firmware's symbolic equates (e.g. inc/host_commands.inc) are the single
source of truth for the ROB3 host command set. ucSim behavioral tests are bash
and cannot `.include` an sdas header, so this script emits an equivalent
`NAME=0xNN` shell file they can `source`, keeping the two in sync automatically.

Only plain scalar equates are converted:  ``NAME = <value>  ; comment``
where <value> is a C/sdas integer literal (0x.., decimal, or 0b..). Lines that
are section banners, comments, or non-scalar directives are passed through as
shell comments so the output stays readable and diffable.

Usage:
    inc2sh.py <input.inc> [-o output.sh]
    inc2sh.py inc/host_commands.inc -o inc/host_commands.sh
If -o is omitted, writes to stdout.
"""

from __future__ import annotations

import argparse
import re
import sys

# NAME = VALUE [; comment]   — VALUE is 0xNN / decimal / 0bNN
_EQUATE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"(0[xX][0-9A-Fa-f]+|0[bB][01]+|\d+)\s*"
    r"(?:;\s*(.*))?\s*$"
)


def _normalize(value: str) -> str:
    """Return a bash-safe numeric literal (bash understands 0x.. and decimal;
    convert 0b.. to its hex form since older bash in `set mem` contexts is
    happier with 0x)."""
    v = value.strip()
    if v[:2] in ("0b", "0B"):
        return "0x%02x" % int(v, 2)
    return v


def convert(text: str) -> str:
    out: list[str] = [
        "# Auto-generated from the sdas .inc by inc2sh.py — DO NOT EDIT.",
        "# Edit the source .inc and regenerate (see the simulator Makefile).",
        "",
    ]
    for line in text.splitlines():
        m = _EQUATE.match(line)
        if m:
            name, value, comment = m.group(1), m.group(2), m.group(3)
            val = _normalize(value)
            out.append(f"{name}={val}" + (f"  # {comment.strip()}" if comment else ""))
        else:
            # Preserve banners/comments/blank lines as shell comments for
            # readability; strip a leading sdas ';' if present.
            stripped = line.strip()
            if not stripped:
                out.append("")
            elif stripped.startswith(";"):
                out.append("#" + stripped[1:])
            # Non-scalar directives (.area/.org/etc.) are simply dropped.
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="input .inc file")
    ap.add_argument("-o", "--output", help="output .sh file (default: stdout)")
    args = ap.parse_args(argv)

    with open(args.input, "r", encoding="utf-8") as f:
        text = f.read()
    result = convert(text)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
    else:
        sys.stdout.write(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
