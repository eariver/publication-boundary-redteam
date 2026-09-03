"""Tests for the PublicationScanner engine, claimboundary block parsing, context tracking, and report generation."""

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
from publication_boundary.semantic_gate import DeterministicGate


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
    res = scanner.scan_text(sample, "test.tex")

    assert res.status == GateStatus.NEEDS_REVIEW
    assert res.passed is False  # Fail-closed before semantic resolution
    assert res.review_required_count == 1
    assert res.hard_fail_count == 0


# ===========================================================================
# Finding 1 Tests: claimboundary content must not bypass generic rules
# ===========================================================================

def test_claimboundary_same_line_internal_term_fails():
    """Same-line claimboundary containing Core v2 contract must trigger HARD_FAIL."""
    scanner = PublicationScanner()
    text = r"\begin{claimboundary} Core v2 contract \end{claimboundary}"
    res = scanner.scan_text(text, "test.tex")
    assert res.passed is False
    assert res.status == GateStatus.FAIL
    assert any(f.rule_id == "RULE-TERM-CORE-V2" for f in res.findings)


def test_claimboundary_multiline_opening_trailing_token_fails():
    """Multiline opening line with trailing internal token must trigger HARD_FAIL."""
    scanner = PublicationScanner()
    text = (
        r"\begin{claimboundary} Core v2 contract" + "\n"
        r"Legitimate claim limits described here." + "\n"
        r"\end{claimboundary}"
    )
    res = scanner.scan_text(text, "test.tex")
    assert res.passed is False
    assert res.status == GateStatus.FAIL
    assert any(f.rule_id == "RULE-TERM-CORE-V2" for f in res.findings)


def test_claimboundary_multiline_closing_preceding_token_fails():
    """Multiline closing line with preceding internal token must trigger HARD_FAIL."""
    scanner = PublicationScanner()
    text = (
        r"\begin{claimboundary}" + "\n"
        r"Legitimate claim limits described here." + "\n"
        r"Core v2 contract \end{claimboundary}"
    )
    res = scanner.scan_text(text, "test.tex")
    assert res.passed is False
    assert res.status == GateStatus.FAIL
    assert any(f.rule_id == "RULE-TERM-CORE-V2" for f in res.findings)


def test_claimboundary_unknown_source_class_internal_term_fails():
    """claimboundary with UNKNOWN source class still triggers HARD_FAIL for internal terms."""
    scanner = PublicationScanner()
    text = (
        r"\section{Generic Section}" + "\n"
        r"\begin{claimboundary}" + "\n"
        r"HOLD_OUT and Evidence Card appear in boundary." + "\n"
        r"\end{claimboundary}"
    )
    res = scanner.scan_text(text, "test.tex")
    assert res.passed is False
    assert res.status == GateStatus.FAIL
    rule_ids = {f.rule_id for f in res.findings}
    assert "RULE-TERM-HOLD-OUT" in rule_ids
    assert "RULE-TERM-EVIDENCE-CARD" in rule_ids


def test_claimboundary_clean_reader_prose_preserved():
    """Clean claimboundary reader prose without leaks passes as before."""
    scanner = PublicationScanner()
    text = (
        r"\section{Research Paper Watch}" + "\n"
        r"\begin{claimboundary}" + "\n"
        r"Statements reflect author-reported claims from arXiv preprints." + "\n"
        r"\end{claimboundary}"
    )
    res = scanner.scan_text(text, "test.tex", DocumentProfile.WEEKLY_MAGAZINE)
    assert res.passed is True
    assert res.status == GateStatus.PASS
    assert len(res.findings) == 0


# ===========================================================================
# Finding 2 Tests: Complete claimboundary token sequence parsing
# ===========================================================================

def test_claimboundary_two_valid_same_line_blocks_both_evaluated():
    """Two same-line claimboundary blocks must both be evaluated."""
    scanner = PublicationScanner()
    text = (
        r"\section{Research Paper Watch}" + "\n"
        r"\begin{claimboundary} Statements reflect author-reported claims. \end{claimboundary} "
        r"\begin{claimboundary} Second block with author-reported claims. \end{claimboundary}"
    )
    res = scanner.scan_text(text, "test.tex", DocumentProfile.WEEKLY_MAGAZINE)
    assert res.passed is True
    assert res.status == GateStatus.PASS
    assert len(res.findings) == 0


def test_claimboundary_second_same_line_block_leak_detected():
    """If first block is clean and second leaks internal term, finding is detected."""
    scanner = PublicationScanner()
    text = (
        r"\section{Research Paper Watch}" + "\n"
        r"\begin{claimboundary} Statements reflect author-reported claims. \end{claimboundary} "
        r"\begin{claimboundary} Core v2 contract \end{claimboundary}"
    )
    res = scanner.scan_text(text, "test.tex", DocumentProfile.WEEKLY_MAGAZINE)
    assert res.passed is False
    assert res.status == GateStatus.FAIL
    assert any(f.rule_id == "RULE-TERM-CORE-V2" for f in res.findings)


def test_claimboundary_same_line_nested_fails_closed():
    """Same-line nested claimboundary must trigger HARD_FAIL for malformed structure."""
    scanner = PublicationScanner()
    text = r"\begin{claimboundary} outer \begin{claimboundary} inner \end{claimboundary} \end{claimboundary}"
    res = scanner.scan_text(text, "test.tex")
    assert res.passed is False
    assert res.status == GateStatus.FAIL
    assert any(f.rule_id == "RULE-BOUNDARY-SYNTAX-MALFORMED" for f in res.findings)


def test_claimboundary_unparsed_trailing_content_evaluated():
    """Multiple begin/end tokens cannot leave unparsed trailing content outside blocks."""
    scanner = PublicationScanner()
    text = (
        r"\begin{claimboundary} clean prose \end{claimboundary} "
        r"\begin{claimboundary} clean prose \end{claimboundary} "
        r"Evidence Card leaked after blocks."
    )
    res = scanner.scan_text(text, "test.tex")
    assert res.passed is False
    assert res.status == GateStatus.FAIL
    assert any(f.rule_id == "RULE-TERM-EVIDENCE-CARD" for f in res.findings)


def test_claimboundary_orphan_end_after_same_line_block_fails():
    """Orphan \\end{claimboundary} after a valid same-line block must trigger HARD_FAIL."""
    scanner = PublicationScanner()
    text = r"\begin{claimboundary} clean prose \end{claimboundary} \end{claimboundary}"
    res = scanner.scan_text(text, "test.tex")
    assert res.passed is False
    assert res.status == GateStatus.FAIL
    assert any(f.rule_id == "RULE-BOUNDARY-SYNTAX-MALFORMED" for f in res.findings)


def test_claimboundary_same_line_source_class_mismatch():
    """Same-line block violating source-class boundary must trigger mismatch."""
    scanner = PublicationScanner()
    text = (
        r"\section{Research Watch}" + "\n"
        r"\begin{claimboundary} Statements are first-party vendor claims without verification. \end{claimboundary}"
    )
    res = scanner.scan_text(text, "test.tex", DocumentProfile.WEEKLY_MAGAZINE)
    assert res.passed is False
    assert any(f.rule_id == "RULE-BOUNDARY-SOURCE-CLASS-MISMATCH" for f in res.findings)


def test_claimboundary_nested_multiline_fails_closed():
    """Nested claimboundary environments across multiple lines fail closed."""
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


# ===========================================================================
# Finding 3 Tests: Cross-line location-local context preservation
# ===========================================================================

def test_cross_line_preserves_originating_section_context():
    """Cross-line findings must retain location-local semantic context, not subsequent sections."""
    scanner = PublicationScanner()
    text = (
        r"\section{Research Paper Watch}" + "\n"
        r"今週の動向は三つのFeature" + "\n"
        r"だけではない。" + "\n"
        r"\section{Community Pulse}" + "\n"
        r"Subsequent community commentary."
    )
    res = scanner.scan_text(text, "test.tex", DocumentProfile.WEEKLY_MAGAZINE)
    assert res.passed is False

    cross_findings = [f for f in res.findings if "三つのFeature" in f.matched_text]
    assert len(cross_findings) >= 1
    finding = cross_findings[0]

    # Must preserve originating section context (Research Paper Watch), NOT subsequent (Community Pulse)
    assert finding.section_role == "Research Paper Watch"
    assert finding.source_class == "RESEARCH_PAPER"
    assert finding.line_number == 2

    # Verify that SemanticPacket generated by DeterministicGate also retains originating context
    gate = DeterministicGate()
    status, packets = gate.evaluate(res)
    # Finding is HARD_FAIL, but let's test with a REVIEW_REQUIRED cross-line finding as well
    assert res.hard_fail_count >= 1


def test_cross_line_review_required_packet_context():
    """Cross-line REVIEW_REQUIRED finding preserves section role in SemanticPacket."""
    scanner = PublicationScanner()
    text = (
        r"\section{Research Paper Watch}" + "\n"
        r"前回のレビュー" + "\n"
        r"指摘事項を踏まえて範囲を決定した。" + "\n"
        r"\section{Community Pulse}" + "\n"
        r"Subsequent community commentary."
    )
    res = scanner.scan_text(text, "test.tex", DocumentProfile.WEEKLY_MAGAZINE)
    assert res.status == GateStatus.NEEDS_REVIEW

    gate = DeterministicGate()
    status, packets = gate.evaluate(res)
    assert status == GateStatus.NEEDS_REVIEW
    assert len(packets) >= 1

    rev_packet = next(p for p in packets if "前回のレビュー" in p.text)
    assert rev_packet.section_role == "Research Paper Watch"
    assert rev_packet.source_class == "RESEARCH_PAPER"


# ===========================================================================
# Directly related cleanup Tests: NEEDS_REVIEW reporting
# ===========================================================================

def test_reports_preserve_needs_review_status():
    """Text, JSON, and Markdown reports must preserve 3-state NEEDS_REVIEW status."""
    scanner = PublicationScanner()
    sample = "前回のレビュー指摘事項を踏まえて範囲を決定した。\n"
    res = scanner.scan_text(sample, "pending.tex", DocumentProfile.WEEKLY_MAGAZINE)
    assert res.status == GateStatus.NEEDS_REVIEW

    # Text report
    txt = format_text_report(res)
    assert "Status: [NEEDS_REVIEW]" in txt
    assert "1 needs review" in txt

    # JSON report
    js = format_json_report(res)
    d = json.loads(js)
    assert d["status"] == "NEEDS_REVIEW"
    assert d["passed"] is False
    assert d["targets_needs_review"] == 1
    assert d["results"][0]["status"] == "NEEDS_REVIEW"

    # Markdown report
    md = format_markdown_summary([res])
    assert "⚠️ NEEDS_REVIEW" in md


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
    assert len(res.findings) == 1
    assert res.findings[0].rule_id == "RULE-TERM-INTERNAL-ID"
    assert res.findings[0].line_number == 6


def test_report_formats_fail():
    scanner = PublicationScanner()
    sample = "HOLD_OUT candidate in text.\n"
    res = scanner.scan_text(sample, "test.tex", DocumentProfile.WEEKLY_MAGAZINE)

    txt = format_text_report(res)
    assert "PUBLICATION BOUNDARY SCAN REPORT" in txt
    assert "Status: [FAIL]" in txt

    js = format_json_report(res)
    d = json.loads(js)
    assert d["passed"] is False
    assert d["status"] == "FAIL"

    md = format_markdown_summary([res])
    assert "| Target File | Profile | Status | Hard Fails | Review Required | Info |" in md
    assert "❌ FAIL" in md


def test_claimboundary_malformed_syntax_braces():
    """Missing closing brace on begin or end tags fails closed."""
    scanner = PublicationScanner()
    res1 = scanner.scan_text(r"\begin{claimboundary missing brace", "test.tex")
    assert res1.passed is False
    assert any("Malformed \\begin{claimboundary}" in f.message for f in res1.findings)

    res2 = scanner.scan_text(r"\end{claimboundary missing brace", "test.tex")
    assert res2.passed is False
    assert any("Malformed \\end{claimboundary}" in f.message for f in res2.findings)


def test_report_formats_pass():
    """Passing results format with PASS status in text, json, and markdown."""
    scanner = PublicationScanner()
    res = scanner.scan_text("Clean publication prose.", "clean.tex")
    assert res.status == GateStatus.PASS

    txt = format_text_report(res)
    assert "Status: [PASS]" in txt
    assert "1/1 files passed" in txt

    js = format_json_report(res)
    d = json.loads(js)
    assert d["status"] == "PASS"
    assert d["passed"] is True
    assert d["targets_passed"] == 1

    md = format_markdown_summary([res])
    assert "✅ PASS" in md
