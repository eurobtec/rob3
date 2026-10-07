# ROB3 Teach Box — hardware & TBPS language docs

This directory documents the ROB3 **Teach Box** (the 25-key programming pendant)
and the **TBPS** teach-box programming language, plus board-level references.

- `teachbox.md` — Teach Box user manual (keypad, modes, instruction set, worked programs).
- `tbps.md` — the DOS **TBPS** PC-software manual.
- `language.md` — TBPS language description (grammar + semantics).
- `board.md`, `led.md`, `pb86-button.md`, `test.md` — board / key-matrix / LED references.
- `hello_world.tbps` — an example TBPS program (compile with
  [eurobtec/tbps_compiler](https://github.com/eurobtec/tbps_compiler)).
- `arduino/`, `program_loader.py` *(see history)* — bench bring-up helpers.

The ROM-faithful TBPS compiler/disassembler/debugger lives in its own repo:
**[eurobtec/tbps_compiler](https://github.com/eurobtec/tbps_compiler)**.

## Source material — READ ONLY (do not let tooling/agents edit)

The following are **author/owner-maintained documents**. They must **not be
modified by agents or automated tooling** — treat them as read-only. Corrections
and reverse-engineering findings belong in derived docs (e.g.
`../host/command.md`, or the TBPS compiler's spec in
[eurobtec/tbps_compiler](https://github.com/eurobtec/tbps_compiler)), never in
these files.

| File | Source | Status |
|:-----|:-------|:-------|
| `tbps.md` | ROB3i **TBPS** PC-software manual (PDF) | **READ ONLY** — verbatim extraction |
| `teachbox.md` | ROB3i **Teachbox** user manual (PDF), **renamed from `README.md` and extended by the owner** | **READ ONLY** — owner-maintained |

Derived / editable material in this directory:

| File | Status |
|:-----|:-------|
| `language.md` | owner-authored TBPS language (source-syntax) spec — editable |
| `hello_world.tbps` | hand-written example TBPS program (editable) |

> The former `tbps_compiler.py` / `program_loader.py` here used **fabricated
> opcodes** and have been **removed** — the real, ROM-verified compiler is its
> own repo: [eurobtec/tbps_compiler](https://github.com/eurobtec/tbps_compiler).

> If a manual needs correcting, record the correction in a derived doc and cite
> the manual — do not alter these files, so they stay a faithful copy of (or the
> owner's curated version of) the source PDF.

