# TBPS compiler — moved to its own repository

The ROB3 **Teach Box Programming System (TBPS)** compiler, disassembler,
debugger, and native-8051 backend now lives in its own repository:

> **https://github.com/eurobtec/tbps_compiler**

It was extracted from this tree (`tools/tbps-compiler/`) following the project
convention for self-contained, pip-installable tools (like
[`rob3_py`](https://github.com/eurobtec/rob3_py),
[`rob3_ucsim`](https://github.com/eurobtec/rob3_ucsim),
[`pyucsim`](https://github.com/eurobtec/pyucsim)).

```bash
pip install git+https://github.com/eurobtec/tbps_compiler.git
tbpsc program.tbps --hex          # compile
tbpsc program.tbps --trace        # single-step through the ROM in ucSim
tbpsc program.tbps --native       # emit native 8051 asm
```

What stays in **this** (firmware) repo:

- the authoritative TBPS/interpreter equates — `firmware/src/annotated/inc/program.inc`
  (the compiler's `asm/tbps_isa.inc` mirrors it);
- the keypad-typing behavioral test — `simulator/tests/test_teachbox_typing.py`;
- the firmware annotations and the `rob3-firmware-map` skill that document the
  stored-program interpreter the compiler targets.

The `tbps_compiler` repo's ucSim-verification tests depend on
[`eurobtec/rob3_ucsim`](https://github.com/eurobtec/rob3_ucsim) and this repo's
ROM; they skip cleanly when the simulator isn't available.
