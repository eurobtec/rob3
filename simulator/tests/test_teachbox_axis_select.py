#!/usr/bin/env python3
"""Black-box teachbox axis-select test (Layer C, partial).

Drives the REAL firmware keypad path end-to-end in ucSim — no hand-seeded
scanner state — and asserts the manufacturer-documented behaviour that a
numeric axis key selects an axis and enters POSITION mode.

Requires the custom ucsim_51 built with BOTH the teachbox and loopback cl_hw
modules (simulator/ucsim-modules/). Without the loopback module the ROM traps
in the EMERGENCY-OFF handler and never polls the keypad (see the annotated
main-loop "THREE GATES" note). SKIPS cleanly if the modules aren't present.

What it proves [SIM]:
  * With loopback present, from reset the ROM reaches the teachbox poll.
  * The release-then-hold debounce cadence dispatches a key to kbd_handle.
  * Axis-select keys (group 1, rows 1..6 = key index 0x02..0x07) set mode
    0x29 = 0x40 (POSITION), i.e. "press numeric key -> select axis".

Run:
  UCSIM_51=/path/to/ucsim_51 python3 test_teachbox_axis_select.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

try:
    from rob3_ucsim import UCSimEngine, MAIN_LOOP  # pip install rob3_ucsim
except ImportError:
    print("SKIP  test_teachbox_axis_select: rob3_ucsim not installed "
          "(pip install git+https://github.com/eurobtec/rob3_ucsim.git)")
    print("test_teachbox_axis_select: SKIPPED")
    sys.exit(0)


def _reg(eng, name):
    m = re.search(name + r"=\s*0x([0-9a-fA-F]+)", eng.cmd("info registers"))
    return m.group(1) if m else None


def _mode(eng):
    o = eng.cmd("dump iram 0x29 0x29")
    m = re.search(r"0x29\s+([0-9a-f]{2})", o, re.I)
    return m.group(1) if m else "??"


def _settle(eng, n):
    for _ in range(n):
        eng.cmd("step 8000", timeout=15)


def _tap(eng, row, group, hold=6):
    """Release-then-hold-then-release one matrix key; wait for kbd_handle."""
    eng.release(); _settle(eng, 3)              # release sets flag 0x20.6
    eng.press(row, group)
    eng.cmd("break 0x0c80")
    dispatched = False
    for _ in range(30):
        out = eng.cmd("step 8000", timeout=15)
        if "0x0c80" in out.lower():
            dispatched = True
            break
    eng.cmd("clear 0x0c80")
    _settle(eng, hold)
    eng.release(); _settle(eng, 2)
    return dispatched


def _load_runtime_modules(eng):
    """Load the cl_hw plugins as runtime .so's (loadhw) and flip has_modules.

    The modules are built as runtime shared objects under
    ../ucsim-modules/<name>/<name>.so (not compiled into ucsim_51), so the
    harness engine — which doesn't loadhw on its own — needs them loaded here.
    Returns the set of id_strings that loaded successfully.
    """
    moddir = os.path.normpath(os.path.join(HERE, "..", "ucsim-modules"))
    loaded = set()
    for name in ("loopback", "teachbox", "adc", "rxd"):
        so = os.path.join(moddir, name, f"{name}.so")
        if not os.path.isfile(so):
            continue
        out = eng.cmd(f'loadhw "{so}"')
        if "loaded" in out.lower():
            loaded.add(name)
    if {"teachbox", "adc"} <= loaded:
        eng.has_modules = True
    return loaded


def main():
    eng = UCSimEngine()
    loaded = _load_runtime_modules(eng)
    if not eng.has_modules:
        print("SKIP  test_teachbox_axis_select: teachbox/adc cl_hw plugins not loadable")
        eng.close()
        return 0
    # The loopback module de-asserts the emergency-off gate so the poll runs.
    if "loopback" not in loaded:
        print("SKIP  test_teachbox_axis_select: 'loopback' plugin not loadable")
        print("      build it per simulator/ucsim-modules/loopback/README.md")
        eng.close()
        return 0

    eng.reset()
    eng.cmd("set memory sfr 0xb0 0x00")
    eng.run_to(MAIN_LOOP)

    fails = 0
    # axis-select keys: group 1, rows 1..6 -> index 0x02..0x07 -> axis 0..5
    for axis, row in enumerate(range(1, 7)):
        disp = _tap(eng, row, 1)
        mode = _mode(eng)
        if disp and mode == "40":
            print(f"PASS  axis-select key row{row} grp1 (idx 0x{row+1:02x}) "
                  f"-> POSITION mode (0x29=0x40) [axis {axis}]")
        else:
            print(f"FAIL  axis-select key row{row} grp1: dispatched={disp} "
                  f"mode 0x29=0x{mode} (expected dispatched=True, 0x40)")
            fails += 1

    eng.close()
    if fails:
        print(f"test_teachbox_axis_select: {fails} FAIL")
        return 1
    print("test_teachbox_axis_select: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
