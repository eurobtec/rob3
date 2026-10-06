"""CLI tests for the `tbpsc` entry point."""

from __future__ import annotations

import pytest

from tbps_compiler import __version__
from tbps_compiler.cli import main


def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert __version__ in out


def test_help(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "tbpsc" in out
    assert "--label-table" in out


def test_missing_source_errors(capsys):
    with pytest.raises(SystemExit) as e:
        main([])
    assert e.value.code == 2


def test_compile_file_to_hex(tmp_path, capsys):
    src = tmp_path / "p.tbps"
    src.write_text("MARK 0\nPOS 1 . 128\nINS .\n")
    rc = main([str(src), "--hex"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "8100:" in out          # body base in the hex dump
    assert "1F" in out             # MARK opcode


def test_compile_error_reports_and_returns_1(tmp_path, capsys):
    src = tmp_path / "bad.tbps"
    src.write_text("MARK 119\n")    # label out of range
    rc = main([str(src)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "out of range" in err


def test_output_binary(tmp_path, capsys):
    src = tmp_path / "p.tbps"
    src.write_text("MARK 0\nPOS 1 . 128\nINS .\n")
    out_bin = tmp_path / "p.bin"
    rc = main([str(src), "-o", str(out_bin)])
    assert rc == 0
    data = out_bin.read_bytes()
    assert len(data) % 8 == 0       # whole 8-byte slots
    assert data[0] == 0x1F          # MARK


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
