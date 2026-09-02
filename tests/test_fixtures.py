"""Automated validation of all regression fixtures against their metadata."""

import json
from pathlib import Path
import pytest
from publication_boundary.models import DocumentProfile, Severity
from publication_boundary.scanner import PublicationScanner

FIXTURES_ROOT = Path(__file__).parent.parent / "fixtures"


def get_all_fixture_metas() -> list[Path]:
    return sorted(FIXTURES_ROOT.rglob("*.meta.json"))


def test_fixture_counts():
    """Verify that we have created at least the minimum required fixture pairs."""
    weekly_bad = list((FIXTURES_ROOT / "weekly" / "bad").glob("*.meta.json"))
    weekly_good = list((FIXTURES_ROOT / "weekly" / "good").glob("*.meta.json"))
    longform_bad = list((FIXTURES_ROOT / "longform" / "bad").glob("*.meta.json"))
    longform_good = list((FIXTURES_ROOT / "longform" / "good").glob("*.meta.json"))
    ambiguous = list((FIXTURES_ROOT / "ambiguous").glob("*.meta.json"))

    assert len(weekly_bad) >= 8, f"Expected >= 8 weekly bad fixtures, got {len(weekly_bad)}"
    assert len(weekly_good) >= 8, f"Expected >= 8 weekly good fixtures, got {len(weekly_good)}"
    assert len(longform_bad) >= 8, f"Expected >= 8 longform bad fixtures, got {len(longform_bad)}"
    assert len(longform_good) >= 8, f"Expected >= 8 longform good fixtures, got {len(longform_good)}"
    assert len(ambiguous) >= 8, f"Expected >= 8 ambiguous fixtures, got {len(ambiguous)}"
    assert (
        len(weekly_bad) + len(weekly_good) + len(longform_bad) + len(longform_good) + len(ambiguous)
    ) >= 40


@pytest.mark.parametrize(
    "meta_path",
    get_all_fixture_metas(),
    ids=lambda p: p.stem.replace(".meta", ""),
)
def test_fixture_verdict(meta_path: Path):
    """Verify each fixture produces its exact machine-readable expected verdict and rule."""
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    fixture_file = meta_path.with_name(meta_path.name.replace(".meta.json", ""))
    assert fixture_file.is_file(), f"Missing content file for {meta_path}"

    profile_map = {
        "WEEKLY_MAGAZINE": DocumentProfile.WEEKLY_MAGAZINE,
        "LONGFORM_SPECIAL": DocumentProfile.LONGFORM_SPECIAL,
        "GENERIC": DocumentProfile.GENERIC,
    }
    profile = profile_map.get(meta.get("profile", "GENERIC"), DocumentProfile.GENERIC)

    scanner = PublicationScanner()
    res = scanner.scan_file(fixture_file, profile=profile)

    expected_verdict = meta["expected_verdict"]
    expected_rule = meta.get("expected_rule")
    expected_severity = meta.get("severity")

    if expected_verdict == "FAIL":
        assert not res.passed, (
            f"Fixture {meta['fixture_id']} was expected to FAIL, but PASSED! "
            f"Findings: {[f.rule_id for f in res.findings]}"
        )
        if expected_rule:
            rule_ids = [f.rule_id for f in res.findings]
            assert expected_rule in rule_ids, (
                f"Fixture {meta['fixture_id']} did not trigger expected rule {expected_rule}. "
                f"Triggered rules: {rule_ids}"
            )
        if expected_severity:
            severities = [f.severity.value for f in res.findings]
            assert expected_severity in severities, (
                f"Fixture {meta['fixture_id']} did not contain expected severity {expected_severity}. "
                f"Actual severities: {severities}"
            )
    elif expected_verdict == "PASS":
        # Must not have any HARD_FAIL
        hard_fails = [f for f in res.findings if f.severity == Severity.HARD_FAIL]
        assert len(hard_fails) == 0, (
            f"Fixture {meta['fixture_id']} was expected to PASS, but triggered HARD_FAIL: "
            f"{[(f.rule_id, f.message) for f in hard_fails]}"
        )
        assert res.passed is True
