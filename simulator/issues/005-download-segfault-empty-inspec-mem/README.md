# `download` command segfaults — empty `cl_inspec` leaves `mem` uninitialized

**Component:** interactive hex loader (`core/sim.src/uc.cc`, `cl_inspec` + `cl_uc::set_rom` / `read_hex_file`)
**Version:** ucSim 0.9.9 (`s51` / `ucsim_51`)
**Severity:** high — crash (wild-pointer deref) on the documented `download` command
**Status:** **confirmed bug + repro + patch** (fixed in this project's ucSim checkout)
**Upstream:** reported as ucSim issue
[#16](https://github.com/danieldrotos/ucsim/issues/16).

## Summary

The console **`download`** command (load Intel-HEX records typed/piped into the
console) **segfaults** as soon as a data record is parsed. Minimal reproduction:

```
download
:1080000000810000000000000000000000000000EF
:00000001FF
```

→ `Segmentation fault` (the process dies; symptom seen from a driver: "ucSim
process is not running" right after a `download …` block).

## Root cause

`download` loads via `cl_uc::read_hex_file(con)`, which builds an **empty**
inspec:

```c
// uc.cc, cl_uc::read_hex_file(cl_console_base *con)
class cl_inspec is("", this);
long l= read_hex_file(&is, f, false);
```

`cl_inspec` never initializes its `mem` member in the constructor, **and**
`cl_inspec::init()` returns early for an empty spec — *before* the line that
would set it:

```c
// uc.cc, cl_inspec::init()
if (ispec.empty())
  {
    return 0;        // <-- early return: `mem` is never assigned
  }
...
mem = uc->rom;       // (only reached for a non-empty spec)
```

So `is->mem` is an **uninitialized/garbage pointer**. When the first data
record is written, `cl_uc::set_rom` fetches it and dereferences it:

```c
// uc.cc, cl_uc::set_rom()
class cl_memory *mem= is->get_mem();   // garbage, but non-NULL
if (mem == NULL) return false;          // guard passes
...
if (mem->is_chip())                     // <-- SIGSEGV (uc.cc:1489)
```

gdb backtrace (before the fix):

```
cl_uc::set_rom (addr=32768, val=0) at uc.cc:1489      ; mem->is_chip()
cl_uc::read_hex_file (is=..., check=false) at uc.cc:1652
cl_uc::read_hex_file (con=...) at uc.cc:1576
cl_dl_cmd::do_work (...) at cmd_uc.cc:177             ; the "download" command
cl_console_base::proc_input (...) at newcmd.cc:713
```

(The `file "NAME"` path does not crash because it uses a *non-empty* inspec, so
`init()` reaches `mem = uc->rom`. Only the empty-spec `download` path is
affected.)

## Fix

Initialize `mem` so it is never a wild pointer, defaulting an empty inspec to
the ROM/code space (the historical meaning of `download`). Two small edits in
`src/core/sim.src/uc.cc` (see `download-crash.patch`):

```c
// cl_inspec::cl_inspec(...)
uc= auc;
mem= (auc != NULL) ? auc->rom : NULL;   // default target: ROM/code space

// cl_inspec::init()
if (ispec.empty())
  {
    mem= uc->rom;      // empty spec => default to the ROM/code space
    inited= true;
    return 0;
  }
```

## After the fix

The same `download` block loads cleanly (exit 0, no crash) and the bytes land in
the ROM/code space:

```
$ printf 'download\n:1080000000810000000000000000000000000000EF\n:108100001F...49\n:00000001FF\ndump rom 0x8100 0x8110\nquit\n' \
    | ucsim_51 -t 8031 -X 11.0592M /tmp/rob3.hex
...
0x8100  1f ...        ; loaded, no segfault
```

## Notes / scope

- `download` targets the **ROM/code** space (not xram). For the ROB3 external
  SRAM **program store** (xram 0x8000+), use `set mem xram <addr> b0 b1 …`
  (immediate, reliable) — see
  `.kiro/steering/rob3-lessons-learned.md` ("Loading a program into xram").
- Independent of issue [001] (pipelined-after-run/step `resUSER` drain): this is
  a pure NULL/garbage-pointer bug in the hex loader, reproducible even with the
  records sent as separate writes.
