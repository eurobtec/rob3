"""Firmware consistency tests — the assembled source must equal the ROM.

These guard the *source transcription*, not runtime behavior (behavioral ucSim
tests live in eurobtec/rob3_ucsim). They need only ``make`` + ``sdas8051`` +
``sdld`` + ``objcopy`` (the firmware toolchain) — no ucSim, no ROM execution.

What is checked:

1. ``make verify`` — the whole 8 KB assembled image is byte-identical to the ROM.
2. ``make status`` — every region also assembles byte-identical to its ROM slice.
3. **Golden SHA pin** — the built image and the reference ROM both hash to the
   recorded SHA-256, so an accidental ROM-image swap (not just source drift) is
   caught.

Run: ``pytest firmware/tests`` (from the repo root) or ``make -C firmware/src test``.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess

import pytest

# firmware/tests/ -> firmware/
_FW_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(_FW_DIR, "src")
ROM = os.path.join(_FW_DIR, "legacy", "bin", "M2764A@DIP28.BIN")
BUILT = os.path.join(SRC_DIR, "_build", "rob3.bin")

# The authoritative 8 KB ROM image hash (whole image). Pinning it means a
# swapped/edited ROM or a non-byte-exact build fails loudly.
GOLDEN_SHA256 = "1e94419d1c65b6b0110734848e0b7f93b225c52c65e4c68b35e0ce962a24d62f"


def _have_toolchain() -> bool:
    return all(shutil.which(t) for t in ("make", "sdas8051", "sdld")) and (
        shutil.which("objcopy") or shutil.which("gobjcopy")
    )


pytestmark = pytest.mark.skipif(
    not _have_toolchain(),
    reason="firmware toolchain not installed (need make + sdas8051 + sdld + objcopy)",
)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _make(*targets: str) -> subprocess.CompletedProcess:
    objcopy = "gobjcopy" if (not shutil.which("objcopy") and shutil.which("gobjcopy")) else None
    args = ["make", "-C", SRC_DIR, *targets]
    if objcopy:
        args.append(f"OBJCOPY={objcopy}")
    return subprocess.run(args, capture_output=True, text=True)


def test_reference_rom_matches_golden_sha():
    """The reference ROM image is the one we pinned (no accidental swap)."""
    assert os.path.exists(ROM), f"ROM image missing: {ROM}"
    assert _sha256(ROM) == GOLDEN_SHA256, "reference ROM hash changed"


def test_golden_byte_match():
    """`make verify`: the assembled image is byte-identical to the ROM."""
    r = _make("clean")
    r = _make("verify")
    assert r.returncode == 0, f"make verify failed:\n{r.stdout}\n{r.stderr}"
    assert "PASS" in r.stdout, r.stdout


def test_built_image_matches_golden_sha():
    """The freshly assembled image hashes to the recorded golden SHA-256."""
    _make("build")
    assert os.path.exists(BUILT), "build did not produce _build/rob3.bin"
    assert _sha256(BUILT) == GOLDEN_SHA256, "assembled image hash != golden"


def test_all_regions_match():
    """`make status`: every region assembles byte-identical to its ROM slice."""
    r = _make("status")
    assert r.returncode == 0, f"make status failed:\n{r.stdout}\n{r.stderr}"
    assert "FAIL" not in r.stdout, f"a region failed:\n{r.stdout}"
    # Every region line should report PASS.
    assert r.stdout.count("PASS") >= 10, f"expected >=10 region PASSes:\n{r.stdout}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
