"""Source-class Claim Boundary consistency validator."""

from __future__ import annotations

import re
from typing import NamedTuple

from publication_boundary.models import (
    Finding,
    FindingCategory,
    Severity,
    SourceClass,
)


class BoundaryDescriptor(NamedTuple):
    expected_pattern: re.Pattern[str]
    incompatible_pattern: re.Pattern[str]
    expected_desc: str
    incompatible_desc: str


SOURCE_CLASS_BOUNDARIES: dict[SourceClass, BoundaryDescriptor] = {
    SourceClass.RESEARCH_PAPER: BoundaryDescriptor(
        expected_pattern=re.compile(
            r"author-reported|author\s+claims?|abstract-level|paper\s+(?:metadata|claims?)|"
            r"著者報告|論文の主張|著者による発表|アブストラクト記載",
            re.IGNORECASE,
        ),
        incompatible_pattern=re.compile(
            r"first-party\s+vendor\s+claims?|vendor\s+claims?|vendor-stated|ベンダー(?:の)?(?:主張|公表|発表)",
            re.IGNORECASE,
        ),
        expected_desc="author-reported / abstract-level author claim",
        incompatible_desc="vendor-claimed capability statements",
    ),
    SourceClass.VENDOR_ANNOUNCEMENT: BoundaryDescriptor(
        expected_pattern=re.compile(
            r"vendor-stated|provider-described|first-party\s+vendor|vendor\s+announcement|"
            r"ベンダー発表|提供元(?:の)?(?:発表|説明)|一次公式発表",
            re.IGNORECASE,
        ),
        incompatible_pattern=re.compile(
            r"peer-reviewed\s+finding|independently\s+proven\s+truth|客観的実証データ",
            re.IGNORECASE,
        ),
        expected_desc="vendor-stated / provider-described announcement",
        incompatible_desc="peer-reviewed or independently proven truth without qualification",
    ),
    SourceClass.OSS_RELEASE: BoundaryDescriptor(
        expected_pattern=re.compile(
            r"project-reported|release\s+notes?|repository\s+(?:metadata|release)|first-party\s+repository|"
            r"プロジェクト報告|リリースメタデータ|リポジトリ公開情報",
            re.IGNORECASE,
        ),
        incompatible_pattern=re.compile(
            r"peer-reviewed\s+benchmark|independent\s+lab\s+audit",
            re.IGNORECASE,
        ),
        expected_desc="project-reported / repository release note",
        incompatible_desc="peer-reviewed or lab-audited benchmark",
    ),
    SourceClass.COMMUNITY_OBSERVATION: BoundaryDescriptor(
        expected_pattern=re.compile(
            r"context-only|community\s+observation|practitioner\s+discussion|social\s+observation|"
            r"コミュニティ観測|X上の議論|文脈限定の観測|未検証の議論",
            re.IGNORECASE,
        ),
        incompatible_pattern=re.compile(
            r"first-party\s+specification|verified\s+fact|確立された事実|公式仕様",
            re.IGNORECASE,
        ),
        expected_desc="context-only community observation",
        incompatible_desc="established primary fact or official specification",
    ),
}


def validate_boundary_prose(
    source_class: SourceClass | None = None,
    prose: str = "",
    line_no: int = 1,
    file_path: str = "",
    declared_class: SourceClass | None = None,
) -> list[Finding]:
    """Validate that a Claim Boundary text block matches the declared source class."""
    target_class = declared_class or source_class
    if target_class is None or target_class not in SOURCE_CLASS_BOUNDARIES:
        return []

    descriptor = SOURCE_CLASS_BOUNDARIES[target_class]
    findings: list[Finding] = []

    # Check for direct incompatibility
    incompat_match = descriptor.incompatible_pattern.search(prose)
    if incompat_match:
        findings.append(
            Finding(
                rule_id="RULE-BOUNDARY-SOURCE-CLASS-MISMATCH",
                category=FindingCategory.SOURCE_CLASS_BOUNDARY_MISMATCH,
                severity=Severity.HARD_FAIL,
                message=(
                    f"Claim boundary mismatch for source class {target_class.value}: "
                    f"prose uses {descriptor.incompatible_desc} ({incompat_match.group(0)!r}) "
                    f"instead of {descriptor.expected_desc}"
                ),
                file_path=file_path,
                line_number=line_no,
                column=incompat_match.start() + 1,
                matched_text=incompat_match.group(0),
                context_snippet=prose.strip()[:140],
                suggestion=f"Align boundary language to match {descriptor.expected_desc}",
            )
        )

    # If the boundary text has substantive length but completely lacks expected framing
    if len(prose.strip()) > 30 and not descriptor.expected_pattern.search(prose):
        findings.append(
            Finding(
                rule_id="RULE-BOUNDARY-MISSING-EXPECTED-FRAMING",
                category=FindingCategory.SOURCE_CLASS_BOUNDARY_MISMATCH,
                severity=Severity.REVIEW_REQUIRED,
                message=(
                    f"Claim boundary for {target_class.value} does not clearly state {descriptor.expected_desc}"
                ),
                file_path=file_path,
                line_number=line_no,
                column=1,
                matched_text="",
                context_snippet=prose.strip()[:140],
                suggestion=f"Explicitly frame claim limits as {descriptor.expected_desc}",
            )
        )

    return findings


# Heuristic section-title mapping to source class
SECTION_HEADER_SOURCE_MAP: list[tuple[re.Pattern[str], SourceClass]] = [
    (re.compile(r"Research\s+(?:Paper\s+)?Watch|Paper\s+Watch|研究論文ウォッチ|研究論文", re.IGNORECASE), SourceClass.RESEARCH_PAPER),
    (re.compile(r"OSS\s+Watch|オープンソースウォッチ|OSS動向", re.IGNORECASE), SourceClass.OSS_RELEASE),
    (re.compile(r"Community\s+Pulse|コミュニティパルス|X\s+Trend\s+Watch", re.IGNORECASE), SourceClass.COMMUNITY_OBSERVATION),
    (re.compile(r"Feature|新モデル発表|公式リリース", re.IGNORECASE), SourceClass.VENDOR_ANNOUNCEMENT),
]


def infer_source_class_from_header(header: str) -> SourceClass:
    """Infer likely source class from a section header or kicker."""
    for pattern, sclass in SECTION_HEADER_SOURCE_MAP:
        if pattern.search(header):
            return sclass
    return SourceClass.UNKNOWN
