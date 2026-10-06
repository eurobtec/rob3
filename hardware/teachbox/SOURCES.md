# Source material — READ ONLY (do not let tooling/agents edit)

The following files are **manual documents maintained by the project owner**.
They must **not be modified by agents or automated tooling** — treat them as
read-only. Corrections and reverse-engineering findings belong in derived docs
(e.g. `language.md`, `../host/command.md`,
`../../tools/tbps-compiler/docs/TBPS_LANGUAGE.md`), never in these files.

| File | Source | Status |
|:-----|:-------|:-------|
| `tbps.md` | ROB3i **TBPS** PC-software manual (PDF) | **READ ONLY** — verbatim extraction |
| `teachbox.md` | ROB3i **Teachbox** user manual (PDF), **renamed from `README.md` and extended by the owner** | **READ ONLY** — owner-maintained |

Derived / editable material in this directory:

| File | Status |
|:-----|:-------|
| `language.md` | derived grammar sketch (points to the verified spec) |
| `hello_world.tbps` | hand-written example TBPS program (editable) |

> The former `tbps_compiler.py` / `program_loader.py` here used **fabricated
> opcodes** and have been **removed** — use `../../tools/tbps-compiler`
> (ROM-verified) instead.

> If a manual needs correcting, record the correction in a derived doc and cite
> the manual — do not alter these files, so they stay a faithful copy of (or the
> owner's curated version of) the source PDF.

