# Using `ucsim-mcp` / `pyucsim` with ROB3

Two related tools for driving the ROB3 8031 firmware in ucSim from outside the
shell test scripts:

- **[`pyucsim`](https://github.com/eurobtec/pyucsim)** — a plain Python library
  that drives a `ucsim_*` process over a pty (load / reset / step / run /
  memory / `loadhw` + `set hardware`). This is the generic engine.
- **[`ucsim-mcp`](https://github.com/eurobtec/ucsim-mcp)** — an MCP server built
  on `pyucsim` that exposes those operations as tools, so an AI agent (Kiro
  CLI) can poke the firmware directly.

Both are **verified against this ROM** (reset vector `LJMP 0x0600`, the
`adc`/`teachbox` cl_hw modules, bounded `step`).

---

## 1. MCP server (agent-driven)

A ready config lives at `.kiro/settings/mcp.json`. It pins `UCSIM_BINARY` to the
**custom** build (`$HOME/github/eurobtec/ucsim/.../ucsim_51`) because the ROB3 cl_hw
`.so` modules only `loadhw` into the binary they were built against (C++ ABI
must match — the stock `/usr/bin/ucsim_51` will reject them).

Restart the Kiro CLI session in this repo so it loads the server, then check
`/mcp` — you should see `ucsim` with its tools. After that you can just ask, e.g.:

- "Load the ROB3 ROM and run to the main loop at 0x074D."
- "Load the teachbox + adc cl_hw modules, press row 1 group 1, step 5000 cycles,
  and show IRAM 0x29 (mode) and 0x50–0x55 (positions)."
- "Disassemble from 0x0600; what's at the INT0 vector?"

The tool sequence behind that:

```
start_session(image=".../M2764A@DIP28.HEX",
              load_hw=[".../adc/adc.so", ".../teachbox/teachbox.so",
                       ".../loopback/loopback.so"])
reset()
set_breakpoint(0x074d); run()
set_hardware("teachbox 1 1"); step(5000)
read_memory(space="iram", start=0x29, end=0x29)
read_memory(space="iram", start=0x50, end=0x55)
```

ROB3 gotchas the server already respects: use `step N` (not `run N`) for bounded
advance; drive the emergency-off / poll gates with the `loopback` module (else
the ROM traps in the INT0 handler and never polls the keypad).

---

## 2. `pyucsim` in the Python tests

`simulator/harness/gui/engine.py` currently hand-rolls the pty + prompt plumbing
that `pyucsim.UCSimEngine` now provides generically. You can use `pyucsim`
directly in a test:

```python
import os
from pyucsim import UCSimEngine

BIN = os.environ["UCSIM_51"]        # custom build with the cl_hw modules
ROM = ".../firmware/legacy/hex/M2764A@DIP28.HEX"   # @ handled automatically
MODS = ".../simulator/ucsim-modules"

with UCSimEngine(BIN, cpu="51", xtal="11.0592M", image=ROM,
                 load_hw=[f"{MODS}/loopback/loopback.so",
                          f"{MODS}/teachbox/teachbox.so"]) as eng:
    eng.reset()
    eng.command("break 0x074d"); eng.run(timeout=15)   # reach the poll
    eng.command("set hardware teachbox 1 1")           # press row1 grp1
    eng.step(8000)
    assert "40" in eng.command("dump iram 0x29 0x29")  # POSITION mode
```

### Recommended: make the ROB3 engine a thin subclass

Rather than duplicate the pty code, let the ROB3-specific engine *extend*
`pyucsim` and keep only the domain helpers (`press`/`release`/`run_to`,
landmark constants, module probing):

```python
from pyucsim import UCSimEngine as _Base

MAIN_LOOP = 0x074D

class Rob3Engine(_Base):
    def press(self, row, group):   self.command(f"set hardware teachbox {row} {group}")
    def release(self):             self.command("set hardware teachbox 0")
    def push_pot(self, ch, val):   self.command(f"set hardware adc {ch} 0x{val & 0xFF:02x}")
    def run_to(self, addr, timeout=30):
        self.command(f"break 0x{addr:04x}")
        out = self.run(timeout=timeout)
        self.command(f"clear 0x{addr:04x}")
        return f"0x{addr:06x}" in out.lower()
```

This removes the duplicated prompt/pty logic from `harness/gui/engine.py` while
preserving every ROB3-specific convenience the GUI and tests rely on. (The GUI's
`cmd()` method maps to `pyucsim`'s `command()`; `run_cycles()` to `step()`.)

### Install for tests

```bash
pip install -e $HOME/github/eurobtec/pyucsim        # until published to an index
# then: UCSIM_51=.../ucsim_51 python3 -m pytest simulator/tests
```

> Note: `pyucsim` is the generic ucSim driver; it has **no** ROB3 knowledge.
> All firmware landmarks (0x0600, 0x074D, IRAM slots, the loopback/emergency-off
> gate) stay in the ROB3 layer, tagged with the usual `[BYTE]`/`[SIM]`
> provenance.
