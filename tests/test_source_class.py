"""Tests for source class boundary validation."""

from publication_boundary.models import Severity, SourceClass
from publication_boundary.source_class import (
    infer_source_class_from_header,
    validate_boundary_prose,
)


def test_infer_source_class():
    assert infer_source_class_from_header(r"\section{Research Paper Watch}") == SourceClass.RESEARCH_PAPER
    assert infer_source_class_from_header(r"\sectionkicker{OSS Watch}") == SourceClass.OSS_RELEASE
    assert infer_source_class_from_header(r"\section{Community Pulse}") == SourceClass.COMMUNITY_OBSERVATION
    assert infer_source_class_from_header(r"\section{Feature 1: Daybreak}") == SourceClass.VENDOR_ANNOUNCEMENT


def test_research_paper_boundary_mismatch():
    # Upstream W33 bug: academic research paper stamped with vendor claim boundary
    bad_boundary = "Capability and performance statements are first-party vendor claims unless separately supported."
    findings = validate_boundary_prose(SourceClass.RESEARCH_PAPER, bad_boundary, 10, "survey.tex")
    assert len(findings) > 0
    assert any(f.severity == Severity.HARD_FAIL for f in findings)
    assert findings[0].rule_id == "RULE-BOUNDARY-SOURCE-CLASS-MISMATCH"


def test_research_paper_boundary_correct():
    good_boundary = "Statements represent author-reported findings and benchmark claims from pre-print papers."
    findings = validate_boundary_prose(SourceClass.RESEARCH_PAPER, good_boundary, 10, "survey.tex")
    # No HARD_FAIL
    assert not any(f.severity == Severity.HARD_FAIL for f in findings)


def test_community_observation_boundary_mismatch():
    bad_boundary = "Community sentiment establishes a verified fact and first-party specification."
    findings = validate_boundary_prose(SourceClass.COMMUNITY_OBSERVATION, bad_boundary, 10, "survey.tex")
    assert len(findings) > 0
    assert any(f.severity == Severity.HARD_FAIL for f in findings)


def test_community_observation_boundary_correct():
    good_boundary = "Discussion reflects context-only observation from developer forums and social media."
    findings = validate_boundary_prose(SourceClass.COMMUNITY_OBSERVATION, good_boundary, 10, "survey.tex")
    assert not any(f.severity == Severity.HARD_FAIL for f in findings)
