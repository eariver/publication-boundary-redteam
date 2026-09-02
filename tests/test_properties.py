"""Property-based testing for scanner invariants and determinism."""

from hypothesis import given, strategies as st
from publication_boundary.models import DocumentProfile, Finding, FindingCategory, Severity, ValidationResult
from publication_boundary.scanner import PublicationScanner, strip_tex_comments


@given(st.text())
def test_scanner_never_crashes_on_arbitrary_input(text: str):
    scanner = PublicationScanner()
    result = scanner.scan_text(text, profile=DocumentProfile.GENERIC)
    assert isinstance(result, ValidationResult)
    assert isinstance(result.passed, bool)
    assert isinstance(result.findings, list)


@given(st.text())
def test_scanner_determinism_property(text: str):
    scanner = PublicationScanner()
    res1 = scanner.scan_text(text, profile=DocumentProfile.WEEKLY_MAGAZINE)
    res2 = scanner.scan_text(text, profile=DocumentProfile.WEEKLY_MAGAZINE)
    assert res1.to_json() == res2.to_json()


@given(st.text(alphabet=st.characters(blacklist_characters="%\n\r")))
def test_strip_tex_comments_noop_without_percent(line: str):
    assert strip_tex_comments(line) == line


@given(
    st.lists(
        st.sampled_from([Severity.HARD_FAIL, Severity.REVIEW_REQUIRED, Severity.INFO]),
        min_size=1,
        max_size=20,
    )
)
def test_finding_sort_order_property(severities: list[Severity]):
    findings = [
        Finding(f"R-{i}", FindingCategory.INTERNAL_TERMINOLOGY, sev, "msg", "f", i)
        for i, sev in enumerate(severities)
    ]
    res = ValidationResult("file.tex", DocumentProfile.GENERIC, False, findings)
    d = res.to_dict()
    ranks = [Severity(f["severity"]).rank for f in d["findings"]]
    # Must be monotonically non-increasing
    for i in range(len(ranks) - 1):
        assert ranks[i] >= ranks[i + 1]
