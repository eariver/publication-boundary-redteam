"""Tests for publication_boundary.cli."""

import json
from pathlib import Path
import pytest
from publication_boundary.cli import main


def test_cli_success(tmp_path: Path, capsys):
    sample = tmp_path / "clean.tex"
    sample.write_text(
        r"\section{Overview} Clean technical content discussing software architecture.",
        encoding="utf-8",
    )
    code = main([str(sample), "--format", "text"])
    assert code == 0
    captured = capsys.readouterr()
    assert "PUBLICATION BOUNDARY SCAN REPORT" in captured.out
    assert "1/1 files passed" in captured.out


def test_cli_hard_fail(tmp_path: Path, capsys):
    sample = tmp_path / "leaked.tex"
    sample.write_text(
        r"\section{Leak} Core v2 contract and Evidence Card here.",
        encoding="utf-8",
    )
    code = main([str(sample), "--format", "json"])
    assert code == 1
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["passed"] is False
    assert data["summary"]["hard_fails"] >= 2


def test_cli_directory_scan(tmp_path: Path, capsys):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "f1.tex").write_text(r"Clean text", encoding="utf-8")
    (sub / "f2.tex").write_text(r"D017 leaked", encoding="utf-8")

    code = main([str(sub), "--format", "markdown"])
    assert code == 1
    captured = capsys.readouterr()
    assert "| `Target File` |" not in captured.out  # markdown header is `Target File`
    assert "❌ FAIL" in captured.out
    assert "✅ PASS" in captured.out


def test_cli_nonexistent_path(capsys):
    code = main(["nonexistent_file_path_abc123.tex"])
    assert code == 2
    captured = capsys.readouterr()
    assert "Error: Target path does not exist" in captured.err
