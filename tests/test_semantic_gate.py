"""Tests for the two-tier publication gate architecture."""

from publication_boundary.models import (
    DocumentProfile,
    Finding,
    FindingCategory,
    SemanticPacket,
    Severity,
    ValidationResult,
)
from publication_boundary.semantic_gate import (
    DeterministicGate,
    SemanticReviewGate,
    generate_semantic_review_prompt,
)


def test_deterministic_gate_passes_clean():
    gate = DeterministicGate()
    result = ValidationResult("clean.tex", DocumentProfile.WEEKLY_MAGAZINE, True, [])
    passed, packets = gate.evaluate(result)
    assert passed is True
    assert len(packets) == 0


def test_deterministic_gate_halts_on_hard_fail():
    gate = DeterministicGate()
    finding = Finding(
        "RULE-TERM-CORE-V2",
        FindingCategory.INTERNAL_TERMINOLOGY,
        Severity.HARD_FAIL,
        "Core v2 leaked",
        "file.tex",
        1,
    )
    result = ValidationResult("file.tex", DocumentProfile.WEEKLY_MAGAZINE, False, [finding])
    passed, packets = gate.evaluate(result)
    assert passed is False
    assert len(packets) == 0


def test_deterministic_gate_creates_packets_for_review_required():
    gate = DeterministicGate()
    finding = Finding(
        "RULE-REVIEW-SUSPICIOUS",
        FindingCategory.REVIEW_RESPONSE_PROSE,
        Severity.REVIEW_REQUIRED,
        "Check rebuttal",
        "file.tex",
        5,
        context_snippet="今週の動向はこれだけではない。",
    )
    result = ValidationResult("file.tex", DocumentProfile.WEEKLY_MAGAZINE, True, [finding])
    passed, packets = gate.evaluate(result)
    assert passed is True
    assert len(packets) == 1
    assert packets[0].document_profile == "WEEKLY_MAGAZINE"
    assert "これだけではない" in packets[0].text


def test_semantic_review_gate_mock_evaluates_debate():
    review_gate = SemanticReviewGate()
    packet = SemanticPacket(
        packet_id="PKT-001",
        document_profile="WEEKLY_MAGAZINE",
        section_role="prose_block",
        source_class="unknown",
        text="動向は三つのFeatureだけではない。",
        deterministic_findings=[],
    )
    passed, responses = review_gate.review_packets([packet])
    assert passed is False
    assert len(responses) == 1
    assert responses[0].verdict == "REVISE_PROSE"
    assert "EDITORIAL_DEBATE_PROSE" in responses[0].flags


def test_generate_semantic_review_prompt():
    packet = SemanticPacket(
        packet_id="PKT-TEST",
        document_profile="LONGFORM_SPECIAL",
        section_role="frontier_synthesis",
        source_class="RESEARCH_PAPER",
        text="Sample paragraph",
        deterministic_findings=[],
    )
    prompt = generate_semantic_review_prompt(packet)
    assert "PKT-TEST" in prompt
    assert "LONGFORM_SPECIAL" in prompt
    assert "Sample paragraph" in prompt
