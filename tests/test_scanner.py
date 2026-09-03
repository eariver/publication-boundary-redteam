"""Tests for the PublicationScanner engine, claimboundary block parsing, and report generation."""

import json
from publication_boundary.models import (
    DocumentProfile,
    ExemptionPolicy,
    FindingCategory,
    GateStatus,
    Severity,
    SourceClass,
)
from publication_boundary.report import (
    format_json_report,
    format_markdown_summary,
    format_text_report,
)
from publication_boundary.scanner import (
    PublicationScanner,
    mask_md_comments,
    strip_tex_comments,
)


def test_strip_tex_comments():
    assert strip_tex_comments("Normal text % comment") == "Normal text "
    assert strip_tex_comments(r"Escaped 100\% preserved % comment") == r"Escaped 100\% preserved "
    assert strip_tex_comments("% full comment") == ""


def test_scanner_no_self_bypass_via_inline_magic_marker():
    """Inline magic markers in content must NOT grant self-exemption."""
    scanner = PublicationScanner()
    text = "% reader-facing-prose-lint: allow-internal-metadata\nCore v2 contract and Evidence Card."
    res = scanner.scan_text(text, "test.tex", DocumentProfile.WEEKLY_MAGAZINE)
    assert res.passed is False
    assert res.status == GateStatus.FAIL
    assert res.hard_fail_count >= 1
    assert any(f.rule_id == "RULE-TERM-CORE-V2" for f in res.findings)


def test_scanner_trusted_external_exemption_policy():
    """Trusted external ExemptionPolicy successfully exempts designated files."""
    policy = ExemptionPolicy(exempt_paths={"test.tex"}, exempt_globs=["provenance/*"])
    scanner = PublicationScanner(exemption_policy=policy)

    text = "Core v2 contract and Evidence Card."
    res = scanner.scan_text(text, "test.tex", DocumentProfile.WEEKLY_MAGAZINE)
    assert res.passed is True
    assert len(res.findings) == 0
    assert res.metrics.get("exempted") is True

    res_glob = scanner.scan_text(text, "provenance/notes.tex", DocumentProfile.WEEKLY_MAGAZINE)
    assert res_glob.passed is True
    assert len(res_glob.findings) == 0


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


def test_scanner_review_required_fail_closed():
    """REVIEW_REQUIRED findings result in NEEDS_REVIEW status and fail-closed gate."""
    scanner = PublicationScanner()
    sample = "前回のレビュー指摘事項を踏まえて範囲を決定した。"
    res = scanner.scan_text(sample, "test.tex", strict=False)

    assert res.status == GateStatus.NEEDS_REVIEW
    assert res.passed is False  # Fail-closed before semantic resolution
    assert res.review_required_count == 1
    assert res.hard_fail_count == 0


def test_claimboundary_same_line_detection():
    """Same-line \\begin{claimboundary}...\\end{claimboundary} must be evaluated."""
    scanner = PublicationScanner()
    text = (
        r"\section{Research Watch}" + "\n"
        r"\begin{claimboundary} Statements are first-party vendor claims without verification. \end{claimboundary}"
    )
    res = scanner.scan_text(text, "test.tex", DocumentProfile.WEEKLY_MAGAZINE)
    assert res.passed is False
    assert any(f.rule_id == "RULE-BOUNDARY-SOURCE-CLASS-MISMATCH" for f in res.findings)


def test_claimboundary_nested_fails_closed():
    """Nested claimboundary environments must fail closed with malformed structure finding."""
    scanner = PublicationScanner()
    text = (
        r"\section{Section}" + "\n"
        r"\begin{claimboundary}" + "\n"
        r"Outer prose." + "\n"
        r"\begin{claimboundary}" + "\n"
        r"Inner prose." + "\n"
        r"\end{claimboundary}" + "\n"
        r"\end{claimboundary}"
    )
    res = scanner.scan_text(text, "test.tex")
    assert res.passed is False
    assert any(f.rule_id == "RULE-BOUNDARY-SYNTAX-MALFORMED" for f in res.findings)


def test_claimboundary_unclosed_at_eof_fails_closed():
    """Unclosed claimboundary at EOF must fail closed."""
    scanner = PublicationScanner()
    text = (
        r"\section{Section}" + "\n"
        r"\begin{claimboundary}" + "\n"
        r"Prose that is never closed."
    )
    res = scanner.scan_text(text, "test.tex")
    assert res.passed is False
    assert any(f.rule_id == "RULE-BOUNDARY-SYNTAX-MALFORMED" for f in res.findings)


def test_claimboundary_unmatched_end_fails_closed():
    """Orphan \\end{claimboundary} without \\begin must fail closed."""
    scanner = PublicationScanner()
    text = r"Normal text." + "\n" + r"\end{claimboundary}"
    res = scanner.scan_text(text, "test.tex")
    assert res.passed is False
    assert any(f.rule_id == "RULE-BOUNDARY-SYNTAX-MALFORMED" for f in res.findings)


def test_markdown_comment_masking_and_line_preservation():
    """Markdown comments must be masked without shifting subsequent line numbers."""
    scanner = PublicationScanner()
    md_text = (
        "# Title\n"
        "<!--\n"
        "HOLD_OUT in comment\n"
        "Core v2 contract in comment\n"
        "-->\n"
        "D017 on line 6."
    )
    res = scanner.scan_text(md_text, "report.md")
    assert res.passed is False
    # Only D017 on line 6 should be found; comments on lines 3-4 must be masked
    assert len(res.findings) == 1
    assert res.findings[0].rule_id == "RULE-TERM-INTERNAL-ID"
    assert res.findings[0].line_number == 6


def test_cross_line_token_splitting_buffering():
    """Phrases split across line breaks must be detected via consecutive line buffering."""
    scanner = PublicationScanner()
    text = (
        r"\section{Synthesis}" + "\n"
        r"今週の動向は三つのFeature" + "\n"
        r"だけではない。"
    )
    res = scanner.scan_text(text, "test.tex", DocumentProfile.WEEKLY_MAGAZINE)
    assert res.passed is False
    assert any("三つのFeature だけではない" in f.matched_text for f in res.findings)


def test_report_formats():
    scanner = PublicationScanner()
    sample = "HOLD_OUT candidate in text.\n"
    res = scanner.scan_text(sample, "test.tex", DocumentProfile.WEEKLY_MAGAZINE)

    txt = format_text_report(res)
    assert "PUBLICATION BOUNDARY SCAN REPORT" in txt
    assert "FAIL" in txt

    js = format_json_report(res)
    d = json.loads(js)
    assert d["passed"] is False
    assert d["status"] == "FAIL"

    md = format_markdown_summary([res])
    assert "| Target File | Profile | Status | Hard Fails | Review Required | Info |" in md
    assert "❌ FAIL" in md
