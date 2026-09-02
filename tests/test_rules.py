"""Tests for context-aware publication boundary rules."""

from publication_boundary.models import DocumentProfile, Severity
from publication_boundary.rules import (
    check_bibliography_boundary,
    check_coverage_substitute,
    check_internal_terminology,
    check_raw_provenance_paths,
    check_review_response_prose,
)


def test_internal_terminology_detection():
    # Targets that MUST trigger
    samples = [
        ("We operate under the Core v2 contract for this issue.", "RULE-TERM-CORE-V2"),
        ("Each Evidence Card contains primary findings.", "RULE-TERM-EVIDENCE-CARD"),
        ("Classified as SOCIAL_OBSERVATION in the matrix.", "RULE-TERM-SOCIAL-OBSERVATION"),
        ("The item remains in HOLD_OUT status.", "RULE-TERM-HOLD-OUT"),
        ("ScreeningでDROPとなった候補を整理する。", "RULE-TERM-SCREENING-STATE"),
        ("note = {materiality: MATERIAL}", "RULE-TERM-MATERIALITY-FIELD"),
        ("note = {Core v2 Evidence: VERIFIED}", "RULE-TERM-CORE-EVIDENCE-NOTE"),
        ("During Candidate Selection, 5 models were chosen.", "RULE-TERM-CANDIDATE-SELECTION"),
        ("Grok Reaction Pass was initiated.", "RULE-TERM-REACTION-PASS"),
        ("本 package の執筆範囲を定める。", "RULE-TERM-DRAFT-PACKAGE"),
        ("Discovery sources indicate widespread adoption.", "RULE-TERM-DISCOVERY-SOURCES"),
        ("SP001 accepted Evidence source confirmed MLA efficiency.", "RULE-TERM-ACCEPTED-EVIDENCE"),
        ("この証言を一次資料として昇格させない方針をとる。", "RULE-TERM-PROMOTION-COVERAGE-METAS"),
        ("reader-facing technical surface を定義する。", "RULE-TERM-READER-FACING-META"),
        ("Verify expected_pdf_sha256 before release.", "RULE-TERM-VERIFY-OBLIGATION"),
        ("MLA cache reduction was noted in D017.", "RULE-TERM-INTERNAL-ID"),
        ("EVD-042 demonstrates throughput improvement.", "RULE-TERM-INTERNAL-ID"),
    ]
    for text, expected_rule in samples:
        findings = check_internal_terminology(text, 1, "test.tex", DocumentProfile.GENERIC)
        assert len(findings) > 0, f"Failed to detect internal term in: {text!r}"
        assert any(f.rule_id == expected_rule for f in findings), f"Expected rule {expected_rule} for {text!r}"


def test_raw_provenance_path_detection():
    samples = [
        "url = {Grok_X_SourseIntake/Weekly/2026-W33/run/data.md}",
        "See sources/2026-W33/drafting/package.json for details",
        "Path: sources/SP001/evidence/results.json",
        "Path: runs/159e03f0589f1521f7ced0f7a19ace606fe0c9f3f10628e2384312fd6f4dfd9b/results/item.json",
    ]
    for text in samples:
        findings = check_raw_provenance_paths(text, 1, "test.tex", DocumentProfile.GENERIC)
        assert len(findings) > 0, f"Failed to detect raw path in: {text!r}"
        assert findings[0].rule_id == "RULE-PATH-RAW-PROVENANCE"


def test_review_response_rebuttal_detection():
    # Hard fails
    hard_samples = [
        "今週の動向は三つのFeatureだけではない。",
        "W33は三つのFeatureだけで説明できる週ではなかった。",
        "承認済みArchitectureは多層的な展開を指示している。",
        "Approved Architecture specifies that four benchmarks be included.",
        "Architecture requires that all models be tested on local GPUs.",
    ]
    for text in hard_samples:
        findings = check_review_response_prose(text, 1, "test.tex", DocumentProfile.GENERIC)
        assert any(f.severity == Severity.HARD_FAIL for f in findings), f"Expected HARD_FAIL in: {text!r}"

    # Review required
    rev_samples = [
        "前回のレビュー指摘事項を踏まえ、対象を拡大した。",
        "Human Reviewでの指摘に応答し、構成を見直した。",
        "After review, we expanded the scope of observation.",
    ]
    for text in rev_samples:
        findings = check_review_response_prose(text, 1, "test.tex", DocumentProfile.GENERIC)
        assert any(f.severity == Severity.REVIEW_REQUIRED for f in findings), f"Expected REVIEW_REQUIRED in: {text!r}"


def test_coverage_substitute_detection():
    text = "承認済みArchitectureは、スケーリング則、コスト効率、ローカル実行性を観察軸としているため、重要な動きである。"
    findings = check_coverage_substitute(text, 1, "test.tex", DocumentProfile.GENERIC)
    assert len(findings) > 0
    assert findings[0].rule_id == "RULE-ARCH-COVERAGE-SUBSTITUTE"
    assert findings[0].severity == Severity.HARD_FAIL


def test_bibliography_boundary_detection():
    samples = [
        "@online{test, title = {Release [V/M]}, author = {Org}}",
        "@online{test, note = {Core v2 Evidence: VERIFIED; materiality: MATERIAL}}",
        "Evidence tags: V = VERIFIED, P = PARTIAL; M = MATERIAL, C = CONTEXT",
    ]
    for text in samples:
        findings = check_bibliography_boundary(text, 1, "refs.bib", DocumentProfile.GENERIC)
        assert len(findings) > 0, f"Failed to detect bib leak in: {text!r}"
        assert findings[0].rule_id == "RULE-BIB-INTERNAL-TAG-LEAK"
