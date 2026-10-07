# Firmware consistency tests

Guard that the **assembled annotated source equals the ROM**, byte for byte.
These test the *source transcription*, not runtime behavior — the behavioral
ucSim tests live in the separate [eurobtec/rob3_ucsim](https://github.com/eurobtec/rob3_ucsim)
repo.

What is checked (`test_firmware_consistency.py`):

1. **Golden byte-match** — `make verify`: the whole 8 KB assembled image is
   byte-identical to the ROM.
2. **Per-region match** — `make status`: every one of the 10 regions assembles
   byte-identical to its ROM slice.
3. **Golden SHA pin** — the built image *and* the reference ROM both hash to the
   recorded SHA-256 (`1e94419d…`), so an accidental ROM-image swap is caught,
   not just source drift.

## Run

```bash
pytest firmware/tests            # from the repo root
# or
make -C firmware/src test        # single entry point
```

Needs only the firmware toolchain (`make` + `sdas8051` + `sdld` + `objcopy`) and
`python3`/`pytest` — no ucSim, no ROM execution. Tests **skip** cleanly if the
toolchain is absent.
