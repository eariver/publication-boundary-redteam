"""Context-aware publication boundary rule definitions and evaluators."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Pattern

from publication_boundary.models import (
    DocumentProfile,
    Finding,
    FindingCategory,
    Severity,
)

# Exempt marker to skip linting in files whose published purpose is internal provenance
EXEMPT_MARKER_TEX = "% reader-facing-prose-lint: allow-internal-metadata"
EXEMPT_MARKER_MD = "<!-- publication-boundary-lint: allow-internal-metadata -->"

# Legitimate technical phrases that MUST NOT trigger false positives
LEGITIMATE_ARCHITECTURE_CONTEXTS = re.compile(
    r"\b(?:software|system|model|network|hardware|transformer|neural|pipeline|cpu|gpu|chip|compute|cluster|micro|"
    r"reference|client-server|distributed|storage|cache|memory)\s+architecture\b",
    re.IGNORECASE,
)
LEGITIMATE_EVIDENCE_CONTEXTS = re.compile(
    r"\b(?:empirical|experimental|scientific|statistical|anecdotal|forensic|benchmark|evaluative|concrete|measurable|field|"
    r"observable|supportive|compelling|preliminary|direct)\s+evidence\b|"
    r"\bevidence\s+(?:of|for|from|supporting|showing|demonstrating|suggesting|indicating)\b",
    re.IGNORECASE,
)
LEGITIMATE_CANDIDATE_CONTEXTS = re.compile(
    r"\b(?:candidate\s+(?:model|architecture|tokens?|solution|hypothesis|configuration|weight|parameter|checkpoint|sequence|sample|patch)|"
    r"top\s+candidate|lead\s+candidate|promising\s+candidate)\b",
    re.IGNORECASE,
)
LEGITIMATE_DROP_CONTEXTS = re.compile(
    r"\b(?:packet\s+drop|voltage\s+drop|accuracy\s+drop|performance\s+drop|loss\s+drop|rate\s+drop|price\s+drop|drop\s+out|drop\s+in|drop\s+to|drop\s+below)\b",
    re.IGNORECASE,
)


@dataclass
class Rule:
    """Detection rule definition."""

    rule_id: str
    category: FindingCategory
    severity: Severity
    description: str
    check_fn: Callable[[str, int, str, DocumentProfile], list[Finding]]
    profiles: tuple[DocumentProfile, ...] = (
        DocumentProfile.WEEKLY_MAGAZINE,
        DocumentProfile.LONGFORM_SPECIAL,
        DocumentProfile.GENERIC,
    )


# ---------------------------------------------------------------------------
# 1. Internal Production Terminology Rules (Context-Aware)
# ---------------------------------------------------------------------------

INTERNAL_EXACT_PATTERNS: tuple[tuple[str, Pattern[str], str, Severity], ...] = (
    (
        "RULE-TERM-CORE-V2",
        re.compile(r"\bCore\s+v2(?:\s+contract)?\b", re.IGNORECASE),
        "Core v2 pipeline contract terminology must not appear in reader publication",
        Severity.HARD_FAIL,
    ),
    (
        "RULE-TERM-EVIDENCE-CARD",
        re.compile(r"\bEvidence\s+Cards?\b", re.IGNORECASE),
        "Internal Evidence Card data structure leaked into reader prose",
        Severity.HARD_FAIL,
    ),
    (
        "RULE-TERM-SOCIAL-OBSERVATION",
        re.compile(r"\bSOCIAL_OBSERVATION\b"),
        "Raw internal source class enum SOCIAL_OBSERVATION leaked into publication",
        Severity.HARD_FAIL,
    ),
    (
        "RULE-TERM-HOLD-OUT",
        re.compile(r"\bHOLD_OUT\b"),
        "Pipeline screening disposition HOLD_OUT leaked into reader prose",
        Severity.HARD_FAIL,
    ),
    (
        "RULE-TERM-SCREENING-STATE",
        re.compile(r"(?:Fresh\s+\w+\s+)?Screeningで(?:DROP|昇格|保留|通過)|Screening\s+Index|Screening\s+result", re.IGNORECASE),
        "Pipeline screening stage or state leaked into publication",
        Severity.HARD_FAIL,
    ),
    (
        "RULE-TERM-MATERIALITY-FIELD",
        re.compile(r"\bmateriality\s*:\s*(?:MATERIAL|CONTEXT|UNKNOWN)\b", re.IGNORECASE),
        "Internal materiality ledger field leaked into publication",
        Severity.HARD_FAIL,
    ),
    (
        "RULE-TERM-CORE-EVIDENCE-NOTE",
        re.compile(r"\bCore\s+v2\s+Evidence\s*:\s*(?:VERIFIED|PARTIAL|UNKNOWN)\b", re.IGNORECASE),
        "Internal Core v2 Evidence classification note leaked into publication",
        Severity.HARD_FAIL,
    ),
    (
        "RULE-TERM-CANDIDATE-SELECTION",
        re.compile(r"\bCandidate\s+(?:Selection|Inventory)\b", re.IGNORECASE),
        "Internal candidate selection/inventory workflow term leaked",
        Severity.HARD_FAIL,
    ),
    (
        "RULE-TERM-REACTION-PASS",
        re.compile(r"\b(?:Grok\s+)?Reaction\s+Pass\b", re.IGNORECASE),
        "Internal Grok Reaction Pass workflow term leaked",
        Severity.HARD_FAIL,
    ),
    (
        "RULE-TERM-DRAFT-PACKAGE",
        re.compile(r"\bDraft\s+Packages?\b|\b本\s*package\b", re.IGNORECASE),
        "Internal Draft Package container concept leaked into reader prose",
        Severity.HARD_FAIL,
    ),
    (
        "RULE-TERM-DISCOVERY-SOURCES",
        re.compile(r"\bDiscovery\s+sources?\b|\baccepted\s+Discovery\b", re.IGNORECASE),
        "Internal Discovery intake terminology leaked into reader prose",
        Severity.HARD_FAIL,
    ),
    (
        "RULE-TERM-ACCEPTED-EVIDENCE",
        re.compile(
            r"\baccepted\s+Evidence(?:\s+source)?\b|受理された\s*Evidence|Evidence上の未解決境界|accepted\s+capture",
            re.IGNORECASE,
        ),
        "Internal evidence runner acceptance status leaked into reader prose",
        Severity.HARD_FAIL,
    ),
    (
        "RULE-TERM-PROMOTION-COVERAGE-METAS",
        re.compile(r"一次資料として昇格させない|coverage\s*を広げる|未解決境界を次号へ持ち越す"),
        "Internal pipeline evidence promotion/coverage operations leaked into prose",
        Severity.HARD_FAIL,
    ),
    (
        "RULE-TERM-READER-FACING-META",
        re.compile(r"reader-facing\s*(?:technical\s+surface|に答える|prose)", re.IGNORECASE),
        "Editorial meta-vocabulary 'reader-facing' leaked into publication prose",
        Severity.HARD_FAIL,
    ),
    (
        "RULE-TERM-VERIFY-OBLIGATION",
        re.compile(r"\bVerify\s+[a-zA-Z0-9_-]+\b|The\s+publisher\s+must\s+(?:re)?verify\b", re.IGNORECASE),
        "Internal verification obligation note leaked into reader prose",
        Severity.HARD_FAIL,
    ),
    (
        "RULE-TERM-INTERNAL-ID",
        re.compile(r"\b(?:D017|D021|EVD-\d{3,})\b"),
        "Raw internal Evidence / Discovery identifier leaked into reader prose",
        Severity.HARD_FAIL,
    ),
)


def check_internal_terminology(
    line: str,
    line_no: int,
    file_path: str,
    profile: DocumentProfile,
) -> list[Finding]:
    findings: list[Finding] = []
    for rule_id, pattern, msg, severity in INTERNAL_EXACT_PATTERNS:
        for match in pattern.finditer(line):
            matched_text = match.group(0)
            findings.append(
                Finding(
                    rule_id=rule_id,
                    category=FindingCategory.INTERNAL_TERMINOLOGY,
                    severity=severity,
                    message=f"{msg}: {matched_text!r}",
                    file_path=file_path,
                    line_number=line_no,
                    column=match.start() + 1,
                    matched_text=matched_text,
                    context_snippet=line.strip()[:140],
                    suggestion="Replace with reader-facing factual formulation or move to repository provenance",
                )
            )
    return findings


# ---------------------------------------------------------------------------
# 2. Raw Provenance Path Leakage Rules
# ---------------------------------------------------------------------------

PROVENANCE_PATH_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"""Grok_X_Sours?eIntake/[^\s}"'\\]+""", re.IGNORECASE),
    re.compile(r"""sources/(?:2026-W\d+|SP-\d+-[A-Z0-9]+|SP\d+)/(?:drafting|screening|evidence|execution|collectors|grok|gates)/[^\s}"'\\]+""", re.IGNORECASE),
    re.compile(r"""sources/[^/\s}"'\\]+/(?:candidate-matrix|materiality-ledger|discovery-accepted)[^\s}"'\\]*""", re.IGNORECASE),
    re.compile(r"""runs/[a-f0-9]{16,64}/results/[^\s}"'\\]+""", re.IGNORECASE),
    re.compile(r"""(?:[a-zA-Z]:\\(?:Users|Git|workspace)|\/(?:home|Users)\/[a-zA-Z0-9_-]+\/)[^\s}"'\\]+""", re.IGNORECASE),
)


def check_raw_provenance_paths(
    line: str,
    line_no: int,
    file_path: str,
    profile: DocumentProfile,
) -> list[Finding]:
    findings: list[Finding] = []
    for pattern in PROVENANCE_PATH_PATTERNS:
        for match in pattern.finditer(line):
            matched_text = match.group(0)
            findings.append(
                Finding(
                    rule_id="RULE-PATH-RAW-PROVENANCE",
                    category=FindingCategory.RAW_PROVENANCE_PATH,
                    severity=Severity.HARD_FAIL,
                    message=f"Raw repository or intake provenance path leaked into publication: {matched_text!r}",
                    file_path=file_path,
                    line_number=line_no,
                    column=match.start() + 1,
                    matched_text=matched_text,
                    context_snippet=line.strip()[:140],
                    suggestion="Replace with canonical public URL or reader-facing source title",
                )
            )
    return findings


# ---------------------------------------------------------------------------
# 3. Review-Response Prose Heuristics (Multi-Level Severity)
# ---------------------------------------------------------------------------

REBUTTAL_HARD_FAIL = re.compile(
    r"(?:三つ|3つ)のFeature(?:だけで(?:は)?(?:説明できる|終わる|閉じる|ない)|だけではない)|"
    r"承認済み\s*Architecture(?:は|が|に)|"
    r"\bapproved\s+Architecture\s+(?:says|requires|defines|specifies)\b|"
    r"\bArchitecture\s+requires\s+(?:concrete|that|all)\b",
    re.IGNORECASE,
)

REBUTTAL_REVIEW_REQUIRED = re.compile(
    r"(?:前回の(?:案|指摘|指摘理由|指摘事項|レビュー|Architecture)|Human\s+Review(?:er)?(?:の指摘|で修正された|への反論|への応答)|"
    r"after\s+review\s*,\s*we|in\s+response\s+to\s+review(?:er)?|review-resolution)\b|"
    r"(?:の|が|は)(?:三つのFeature|3つのFeature|単一の話題)だけではない",
    re.IGNORECASE,
)

REBUTTAL_INFO = re.compile(
    r"\b(?:reviewer\s+noted|as\s+clarified\s+during\s+review)\b",
    re.IGNORECASE,
)


def check_review_response_prose(
    line: str,
    line_no: int,
    file_path: str,
    profile: DocumentProfile,
) -> list[Finding]:
    findings: list[Finding] = []

    # HARD_FAIL checks
    for match in REBUTTAL_HARD_FAIL.finditer(line):
        findings.append(
            Finding(
                rule_id="RULE-REVIEW-REBUTTAL-HARD-FAIL",
                category=FindingCategory.REVIEW_RESPONSE_PROSE,
                severity=Severity.HARD_FAIL,
                message=f"Review-reactive rebuttal or Architecture directive serialized directly into publication prose: {match.group(0)!r}",
                file_path=file_path,
                line_number=line_no,
                column=match.start() + 1,
                matched_text=match.group(0),
                context_snippet=line.strip()[:140],
                suggestion="State the final technical reality directly without framing it as a reply to prior review",
            )
        )

    # REVIEW_REQUIRED checks
    for match in REBUTTAL_REVIEW_REQUIRED.finditer(line):
        findings.append(
            Finding(
                rule_id="RULE-REVIEW-REBUTTAL-SUSPICIOUS",
                category=FindingCategory.REVIEW_RESPONSE_PROSE,
                severity=Severity.REVIEW_REQUIRED,
                message=f"Suspicious review-response phrasing detected in reader prose: {match.group(0)!r}",
                file_path=file_path,
                line_number=line_no,
                column=match.start() + 1,
                matched_text=match.group(0),
                context_snippet=line.strip()[:140],
                suggestion="Verify that prose introduces facts rather than explaining editorial review changes",
            )
        )

    # INFO checks
    for match in REBUTTAL_INFO.finditer(line):
        findings.append(
            Finding(
                rule_id="RULE-REVIEW-REBUTTAL-INFO",
                category=FindingCategory.REVIEW_RESPONSE_PROSE,
                severity=Severity.INFO,
                message=f"Possible editorial reference found: {match.group(0)!r}",
                file_path=file_path,
                line_number=line_no,
                column=match.start() + 1,
                matched_text=match.group(0),
                context_snippet=line.strip()[:140],
                suggestion="Confirm reader relevance",
            )
        )

    return findings


# ---------------------------------------------------------------------------
# 4. Architecture Coverage Substitute Heuristic
# ---------------------------------------------------------------------------

COVERAGE_SUBSTITUTE_PATTERN = re.compile(
    r"(?:Architecture|承認済みArchitecture)(?:は|が)[^。]{0,80}(?:を観察軸として|を要求して|をmust-coverとして|を定義して)(?:いる|おり|ため)",
    re.IGNORECASE,
)


def check_coverage_substitute(
    line: str,
    line_no: int,
    file_path: str,
    profile: DocumentProfile,
) -> list[Finding]:
    findings: list[Finding] = []
    for match in COVERAGE_SUBSTITUTE_PATTERN.finditer(line):
        findings.append(
            Finding(
                rule_id="RULE-ARCH-COVERAGE-SUBSTITUTE",
                category=FindingCategory.ARCHITECTURE_COVERAGE_SUBSTITUTE,
                severity=Severity.HARD_FAIL,
                message=f"Prose describes Architecture requirements instead of providing substantive coverage: {match.group(0)!r}",
                file_path=file_path,
                line_number=line_no,
                column=match.start() + 1,
                matched_text=match.group(0),
                context_snippet=line.strip()[:140],
                suggestion="Replace description of Architecture axes with concrete technical findings from the sources",
            )
        )
    return findings


# ---------------------------------------------------------------------------
# 5. Bibliography Publication Boundary Rules
# ---------------------------------------------------------------------------

BIB_STATUS_TAGS = re.compile(
    r"\[(?:V|P)/(?:M|C)\]|Evidence\s+tags\s*:\s*V\s*=\s*VERIFIED|\bnote\s*=\s*\{[^}]*Core\s+v2\s+Evidence[^}]*\}|\bnote\s*=\s*\{[^}]*materiality\s*:[^}]*\}",
    re.IGNORECASE,
)


def check_bibliography_boundary(
    line: str,
    line_no: int,
    file_path: str,
    profile: DocumentProfile,
) -> list[Finding]:
    findings: list[Finding] = []
    for match in BIB_STATUS_TAGS.finditer(line):
        findings.append(
            Finding(
                rule_id="RULE-BIB-INTERNAL-TAG-LEAK",
                category=FindingCategory.BIBLIOGRAPHY_BOUNDARY,
                severity=Severity.HARD_FAIL,
                message=f"Bibliography entry leaks internal disposition tags or Core v2 metadata: {match.group(0)!r}",
                file_path=file_path,
                line_number=line_no,
                column=match.start() + 1,
                matched_text=match.group(0),
                context_snippet=line.strip()[:140],
                suggestion="Retain disposition and status in source repository manifests; bibliography note must be reader-facing",
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Active Rule Registry
# ---------------------------------------------------------------------------

ALL_RULES: list[Rule] = [
    Rule(
        rule_id="RULE-INTERNAL-TERMINOLOGY",
        category=FindingCategory.INTERNAL_TERMINOLOGY,
        severity=Severity.HARD_FAIL,
        description="Scans for internal Core v2 production tokens, workflow stages, and evidence metadata",
        check_fn=check_internal_terminology,
    ),
    Rule(
        rule_id="RULE-RAW-PROVENANCE-PATHS",
        category=FindingCategory.RAW_PROVENANCE_PATH,
        severity=Severity.HARD_FAIL,
        description="Scans for raw intake, collector, and filesystem paths in visible text and URLs",
        check_fn=check_raw_provenance_paths,
    ),
    Rule(
        rule_id="RULE-REVIEW-RESPONSE-PROSE",
        category=FindingCategory.REVIEW_RESPONSE_PROSE,
        severity=Severity.HARD_FAIL,
        description="Identifies editorial review debate and rebuttal framing in reader-facing prose",
        check_fn=check_review_response_prose,
    ),
    Rule(
        rule_id="RULE-ARCHITECTURE-COVERAGE-SUBSTITUTE",
        category=FindingCategory.ARCHITECTURE_COVERAGE_SUBSTITUTE,
        severity=Severity.HARD_FAIL,
        description="Flags paragraphs that describe Architecture obligations rather than fulfilling them",
        check_fn=check_coverage_substitute,
    ),
    Rule(
        rule_id="RULE-BIBLIOGRAPHY-BOUNDARY",
        category=FindingCategory.BIBLIOGRAPHY_BOUNDARY,
        severity=Severity.HARD_FAIL,
        description="Blocks internal disposition tags and classification notes from bibliography output",
        check_fn=check_bibliography_boundary,
    ),
]
