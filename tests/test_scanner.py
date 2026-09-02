"""Tests for the PublicationScanner engine and report generation."""

import json
from publication_boundary.models import DocumentProfile, FindingCategory, Severity
from publication_boundary.report import (
    format_json_report,
    format_markdown_summary,
    format_text_report,
)
from publication_boundary.scanner import PublicationScanner, strip_tex_comments


def test_strip_tex_comments():
    assert strip_tex_comments("Normal text % comment") == "Normal text "
    assert strip_tex_comments(r"Escaped 100\% preserved % comment") == r"Escaped 100\% preserved "
    assert strip_tex_comments("% full comment") == ""


def test_scanner_exempt_marker():
    scanner = PublicationScanner()
    text = "% reader-facing-prose-lint: allow-internal-metadata\nCore v2 contract and Evidence Card."
    res = scanner.scan_text(text, "test.tex", DocumentProfile.WEEKLY_MAGAZINE)
    assert res.passed is True
    assert len(res.findings) == 0
    assert res.metrics.get("exempted") is True


def test_scanner_commented_leak_ignored():
    scanner = PublicationScanner()
    text = "Normal visible text.\n% Core v2 contract in comment should be ignored."
    res = scanner.scan_text(text, "test.tex", DocumentProfile.WEEKLY_MAGAZINE)
    assert res.passed is True
    assert len(res.findings) == 0


def test_scanner_deterministic_output():
    scanner = PublicationScanner()
    sample = "今週の動向は三つのFeatureだけではない。\nVerify expected_pdf_sha256\n"
    res1 = scanner.scan_text(sample, "test.tex", DocumentProfile.WEEKLY_MAGAZINE)
    res2 = scanner.scan_text(sample, "test.tex", DocumentProfile.WEEKLY_MAGAZINE)

    assert res1.passed == res2.passed
    assert len(res1.findings) == len(res2.findings)
    assert res1.to_dict() == res2.to_dict()


def test_scanner_strict_mode():
    scanner = PublicationScanner()
    # A review required line
    sample = "前回のレビュー指摘事項を踏まえて範囲を決定した。"
    normal_res = scanner.scan_text(sample, "test.tex", strict=False)
    strict_res = scanner.scan_text(sample, "test.tex", strict=True)

    assert normal_res.passed is True  # Only REVIEW_REQUIRED, no HARD_FAIL
    assert strict_res.passed is False  # Strict fails on REVIEW_REQUIRED


def test_report_formats():
    scanner = PublicationScanner()
    sample = "HOLD_OUT candidate in text.\n"
    res = scanner.scan_text(sample, "file.tex", DocumentProfile.GENERIC)

    # Text report
    text_out = format_text_report([res])
    assert "PUBLICATION BOUNDARY SCAN REPORT" in text_out
    assert "HOLD_OUT" in text_out

    # JSON report
    json_out = format_json_report([res])
    data = json.loads(json_out)
    assert data["schema_version"] == "1.0"
    assert data["passed"] is False
    assert data["summary"]["hard_fails"] >= 1

    # Markdown table
    md_out = format_markdown_summary([res])
    assert "| `file.tex` |" in md_out
    assert "❌ FAIL" in md_out
