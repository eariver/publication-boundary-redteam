"""Tests for data models and schemas."""

import json
from publication_boundary.models import (
    DocumentProfile,
    Finding,
    FindingCategory,
    SemanticPacket,
    SemanticReviewResponse,
    Severity,
    SourceClass,
    ValidationResult,
)


def test_severity_ranks():
    assert Severity.HARD_FAIL.rank > Severity.REVIEW_REQUIRED.rank
    assert Severity.REVIEW_REQUIRED.rank > Severity.INFO.rank


def test_source_class_from_string():
    assert SourceClass.from_string("research_paper") == SourceClass.RESEARCH_PAPER
    assert SourceClass.from_string("VENDOR-ANNOUNCEMENT") == SourceClass.VENDOR_ANNOUNCEMENT
    assert SourceClass.from_string("nonexistent") == SourceClass.UNKNOWN


def test_finding_serialization():
    f = Finding(
        rule_id="RULE-TEST",
        category=FindingCategory.INTERNAL_TERMINOLOGY,
        severity=Severity.HARD_FAIL,
        message="Test message",
        file_path="sample.tex",
        line_number=10,
        column=5,
        matched_text="Evidence Card",
        context_snippet="Sample Evidence Card here",
        suggestion="Remove it",
    )
    d = f.to_dict()
    assert d["rule_id"] == "RULE-TEST"
    assert d["severity"] == "HARD_FAIL"
    f2 = Finding.from_dict(d)
    assert f == f2


def test_validation_result_deterministic_ordering():
    f_info = Finding("R-INFO", FindingCategory.INTERNAL_TERMINOLOGY, Severity.INFO, "msg", "f", 20)
    f_hard2 = Finding("R-HARD2", FindingCategory.INTERNAL_TERMINOLOGY, Severity.HARD_FAIL, "msg", "f", 15)
    f_hard1 = Finding("R-HARD1", FindingCategory.INTERNAL_TERMINOLOGY, Severity.HARD_FAIL, "msg", "f", 10)
    f_rev = Finding("R-REV", FindingCategory.INTERNAL_TERMINOLOGY, Severity.REVIEW_REQUIRED, "msg", "f", 5)

    res = ValidationResult("f", DocumentProfile.WEEKLY_MAGAZINE, False, [f_info, f_hard2, f_hard1, f_rev])
    d = res.to_dict()

    # Hard fails must come first, sorted by line
    assert d["findings"][0]["rule_id"] == "R-HARD1"
    assert d["findings"][1]["rule_id"] == "R-HARD2"
    assert d["findings"][2]["rule_id"] == "R-REV"
    assert d["findings"][3]["rule_id"] == "R-INFO"


def test_semantic_packet_roundtrip():
    packet = SemanticPacket(
        packet_id="PKT-001",
        document_profile="WEEKLY_MAGAZINE",
        section_role="editorial_brief",
        source_class="COMMUNITY_OBSERVATION",
        text="Sample text for review",
        deterministic_findings=[{"rule_id": "RULE-REVIEW"}],
    )
    json_str = packet.to_json()
    data = json.loads(json_str)
    packet2 = SemanticPacket.from_dict(data)
    assert packet.packet_id == packet2.packet_id
    assert packet.text == packet2.text


def test_semantic_review_response_roundtrip():
    resp = SemanticReviewResponse(
        packet_id="PKT-001",
        verdict="PASS",
        reviewer="gpt-auditor",
        confidence=0.95,
        rationale="Looks good",
        flags=["CLEAN"],
    )
    json_str = resp.to_json()
    data = json.loads(json_str)
    resp2 = SemanticReviewResponse.from_dict(data)
    assert resp.verdict == resp2.verdict
    assert resp.confidence == resp2.confidence
