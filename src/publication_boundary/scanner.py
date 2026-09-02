"""Publication Boundary Scanner Engine."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Sequence

from publication_boundary.models import (
    DocumentProfile,
    Finding,
    FindingCategory,
    Severity,
    SourceClass,
    ValidationResult,
)
from publication_boundary.rules import (
    ALL_RULES,
    EXEMPT_MARKER_MD,
    EXEMPT_MARKER_TEX,
    Rule,
)
from publication_boundary.source_class import (
    infer_source_class_from_header,
    validate_boundary_prose,
)


def strip_tex_comments(line: str) -> str:
    """Remove unescaped TeX comments from a single line while preserving whitespace."""
    # Split by unescaped %
    parts = re.split(r"(?<!\\)%", line, maxsplit=1)
    return parts[0]


def strip_md_comments(text: str) -> str:
    """Remove HTML/Markdown comment blocks."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


class PublicationScanner:
    """Core scanner that runs context-aware rules on publication manuscripts."""

    def __init__(self, rules: Sequence[Rule] | None = None):
        self.rules: list[Rule] = list(rules) if rules is not None else list(ALL_RULES)

    def scan_text(
        self,
        text: str,
        file_path: str = "<memory>",
        profile: DocumentProfile = DocumentProfile.GENERIC,
        source_class: SourceClass | None = None,
        strict: bool = False,
    ) -> ValidationResult:
        start_time = time.perf_counter()

        # Check for explicit exemption markers
        if EXEMPT_MARKER_TEX in text or EXEMPT_MARKER_MD in text:
            return ValidationResult(
                target_file=file_path,
                profile=profile,
                passed=True,
                findings=[],
                metrics={"exempted": True, "scan_time_ms": 0.0, "lines_scanned": 0},
            )

        findings: list[Finding] = []
        lines = text.splitlines()

        # Track active block states for TeX files
        in_claim_boundary = False
        current_claim_prose: list[str] = []
        claim_start_line = 0
        current_inferred_source_class = source_class or SourceClass.UNKNOWN

        for line_no, raw_line in enumerate(lines, start=1):
            # TeX comment stripping
            visible_line = strip_tex_comments(raw_line)
            stripped = visible_line.strip()
            if not stripped:
                continue

            # Check for section header to infer source class if not explicitly passed
            if "\\section" in stripped or "\\sectionkicker" in stripped:
                inferred = infer_source_class_from_header(stripped)
                if inferred != SourceClass.UNKNOWN:
                    current_inferred_source_class = inferred

            # Track \begin{claimboundary} and \end{claimboundary}
            if "\\begin{claimboundary}" in stripped:
                in_claim_boundary = True
                current_claim_prose = []
                claim_start_line = line_no
                continue
            elif "\\end{claimboundary}" in stripped:
                if in_claim_boundary and current_inferred_source_class != SourceClass.UNKNOWN:
                    full_boundary_text = " ".join(current_claim_prose)
                    findings.extend(
                        validate_boundary_prose(
                            declared_class=current_inferred_source_class,
                            prose=full_boundary_text,
                            line_no=claim_start_line,
                            file_path=file_path,
                        )
                    )
                in_claim_boundary = False
                current_claim_prose = []
                continue

            if in_claim_boundary:
                current_claim_prose.append(stripped)

            # Evaluate each active rule on the line
            for rule in self.rules:
                if profile in rule.profiles:
                    line_findings = rule.check_fn(visible_line, line_no, file_path, profile)
                    findings.extend(line_findings)

        # Check standalone Claim Boundary prose if passed at document level without TeX tags
        if source_class and source_class != SourceClass.UNKNOWN and not in_claim_boundary:
            # Check lines that look like boundary declarations in markdown or plain text
            for line_no, line in enumerate(lines, start=1):
                if any(kw in line.lower() for kw in ["boundary", "claim", "limitations", "制限事項"]):
                    findings.extend(
                        validate_boundary_prose(
                            declared_class=source_class,
                            prose=line,
                            line_no=line_no,
                            file_path=file_path,
                        )
                    )

        # Determine pass status: Fail on HARD_FAIL, or also fail on REVIEW_REQUIRED if strict
        hard_fails = [f for f in findings if f.severity == Severity.HARD_FAIL]
        reviews_required = [f for f in findings if f.severity == Severity.REVIEW_REQUIRED]
        passed = (len(hard_fails) == 0) and (not strict or len(reviews_required) == 0)

        return ValidationResult(
            target_file=file_path,
            profile=profile,
            passed=passed,
            findings=findings,
            metrics={
                "lines_scanned": len(lines),
                "strict_mode": strict,
                "rules_evaluated": len(self.rules),
            },
        )

    def scan_file(
        self,
        file_path: Path | str,
        profile: DocumentProfile = DocumentProfile.GENERIC,
        source_class: SourceClass | None = None,
        strict: bool = False,
    ) -> ValidationResult:
        path = Path(file_path)
        if not path.is_file():
            return ValidationResult(
                target_file=str(path),
                profile=profile,
                passed=False,
                findings=[
                    Finding(
                        rule_id="RULE-FILE-MISSING",
                        category=FindingCategory.INTERNAL_TERMINOLOGY,
                        severity=Severity.HARD_FAIL,
                        message=f"Target publication file not found: {path}",
                        file_path=str(path),
                        line_number=1,
                    )
                ],
                metrics={"error": "file_not_found"},
            )

        text = path.read_text(encoding="utf-8", errors="replace")
        return self.scan_text(
            text=text,
            file_path=str(path),
            profile=profile,
            source_class=source_class,
            strict=strict,
        )
