"""Publication Boundary Scanner Engine."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Sequence

from publication_boundary.models import (
    DocumentProfile,
    ExemptionPolicy,
    Finding,
    FindingCategory,
    GateStatus,
    Severity,
    SourceClass,
    ValidationResult,
)
from publication_boundary.rules import ALL_RULES, Rule
from publication_boundary.source_class import (
    infer_source_class_from_header,
    validate_boundary_prose,
)

CLAIMBOUNDARY_TOKEN_RE = re.compile(
    r"(?P<MAL_BEGIN>\\begin\{claimboundary(?!\})[^\s\}]*)"
    r"|(?P<BEGIN>\\begin\{claimboundary\}(?:\[[^\]]*\])?)"
    r"|(?P<MAL_END>\\end\{claimboundary(?!\})[^\s\}]*)"
    r"|(?P<END>\\end\{claimboundary\})"
)


def strip_tex_comments(line: str) -> str:
    """Remove unescaped TeX comments from a single line while preserving whitespace."""
    parts = re.split(r"(?<!\\)%", line, maxsplit=1)
    return parts[0]


def mask_md_comments(text: str) -> str:
    """Mask HTML/Markdown comment blocks with spaces while preserving line numbers."""
    def replacer(match: re.Match[str]) -> str:
        content = match.group(0)
        return "".join("\n" if c == "\n" else " " for c in content)

    return re.sub(r"<!--.*?-->", replacer, text, flags=re.DOTALL)


def strip_md_comments(text: str) -> str:
    """Convenience function returning markdown with comments masked."""
    return mask_md_comments(text)


class PublicationScanner:
    """Core scanner that runs context-aware rules on publication manuscripts."""

    def __init__(
        self,
        rules: Sequence[Rule] | None = None,
        exemption_policy: ExemptionPolicy | None = None,
    ):
        self.rules: list[Rule] = list(rules) if rules is not None else list(ALL_RULES)
        self.exemption_policy: ExemptionPolicy | None = exemption_policy

    def scan_text(
        self,
        text: str,
        file_path: str = "<memory>",
        profile: DocumentProfile = DocumentProfile.GENERIC,
        source_class: SourceClass | None = None,
    ) -> ValidationResult:
        # Check trusted external exemption policy (inline magic markers do NOT grant exemption)
        if self.exemption_policy and self.exemption_policy.is_exempt(file_path):
            return ValidationResult(
                target_file=file_path,
                profile=profile,
                findings=[],
                metrics={"exempted": True, "lines_scanned": 0, "rules_evaluated": 0},
            )

        findings: list[Finding] = []

        # Apply markdown comment masking if file is markdown or text has markdown comments
        is_markdown = file_path.lower().endswith((".md", ".markdown")) or "<!--" in text
        processed_text = mask_md_comments(text) if is_markdown else text
        lines = processed_text.splitlines()

        # Contextual tracking
        current_section_role = "frontmatter"
        current_inferred_source_class = source_class or SourceClass.UNKNOWN

        # Block state tracking for claimboundary token state machine
        in_claim_boundary = False
        claim_start_line = 0
        claim_source_class = current_inferred_source_class
        current_claim_prose: list[str] = []

        # Line-by-line scanning with cross-line lookahead buffer preserving line-local context
        cleaned_lines: list[tuple[int, str, str, SourceClass]] = []

        for line_no, raw_line in enumerate(lines, start=1):
            # Comment stripping
            visible_line = strip_tex_comments(raw_line) if not is_markdown else raw_line
            stripped = visible_line.strip()
            if not stripped:
                continue

            # Section header and kicker extraction for contextual role & source class
            sec_match = re.search(r"\\(?:sub)?section(?:\[[^\]]*\])?\{([^}]+)\}", stripped)
            kicker_match = re.search(r"\\sectionkicker\{([^}]+)\}", stripped)
            md_header_match = re.match(r"^#{1,3}\s+(.+)$", stripped)

            if kicker_match:
                current_section_role = kicker_match.group(1).strip()
            elif sec_match:
                current_section_role = sec_match.group(1).strip()
            elif md_header_match:
                current_section_role = md_header_match.group(1).strip()

            inferred = infer_source_class_from_header(current_section_role)
            if inferred != SourceClass.UNKNOWN:
                current_inferred_source_class = inferred

            # Record line with its location-local context for cross-line buffering
            cleaned_lines.append(
                (line_no, visible_line, current_section_role, current_inferred_source_class)
            )

            # Left-to-right claimboundary token sequence processing
            cursor = 0
            for match in CLAIMBOUNDARY_TOKEN_RE.finditer(stripped):
                # Text segment preceding this token
                text_segment = stripped[cursor:match.start()].strip()
                if text_segment and in_claim_boundary:
                    current_claim_prose.append(text_segment)

                token_group = match.lastgroup
                if token_group == "MAL_BEGIN":
                    findings.append(
                        Finding(
                            rule_id="RULE-BOUNDARY-SYNTAX-MALFORMED",
                            category=FindingCategory.MALFORMED_STRUCTURE,
                            severity=Severity.HARD_FAIL,
                            message=f"Malformed \\begin{{claimboundary}} syntax at line {line_no} (missing closing brace)",
                            file_path=file_path,
                            line_number=line_no,
                            section_role=current_section_role,
                            source_class=current_inferred_source_class.value,
                        )
                    )
                elif token_group == "MAL_END":
                    findings.append(
                        Finding(
                            rule_id="RULE-BOUNDARY-SYNTAX-MALFORMED",
                            category=FindingCategory.MALFORMED_STRUCTURE,
                            severity=Severity.HARD_FAIL,
                            message=f"Malformed \\end{{claimboundary}} syntax at line {line_no} (missing closing brace)",
                            file_path=file_path,
                            line_number=line_no,
                            section_role=current_section_role,
                            source_class=current_inferred_source_class.value,
                        )
                    )
                elif token_group == "BEGIN":
                    if in_claim_boundary:
                        # Nested claimboundary environment is strictly forbidden (fail-closed)
                        findings.append(
                            Finding(
                                rule_id="RULE-BOUNDARY-SYNTAX-MALFORMED",
                                category=FindingCategory.MALFORMED_STRUCTURE,
                                severity=Severity.HARD_FAIL,
                                message=(
                                    f"Nested claimboundary starting at line {line_no} "
                                    f"inside active block from line {claim_start_line}"
                                ),
                                file_path=file_path,
                                line_number=line_no,
                                section_role=current_section_role,
                                source_class=current_inferred_source_class.value,
                            )
                        )
                    else:
                        in_claim_boundary = True
                        claim_start_line = line_no
                        claim_source_class = current_inferred_source_class
                        current_claim_prose = []
                elif token_group == "END":
                    if not in_claim_boundary:
                        # Orphan / unmatched \end{claimboundary} (fail-closed)
                        findings.append(
                            Finding(
                                rule_id="RULE-BOUNDARY-SYNTAX-MALFORMED",
                                category=FindingCategory.MALFORMED_STRUCTURE,
                                severity=Severity.HARD_FAIL,
                                message=f"Unmatched \\end{{claimboundary}} at line {line_no} without preceding \\begin{{claimboundary}}",
                                file_path=file_path,
                                line_number=line_no,
                                section_role=current_section_role,
                                source_class=current_inferred_source_class.value,
                            )
                        )
                    else:
                        full_boundary_text = " ".join(current_claim_prose).strip()
                        boundary_findings = validate_boundary_prose(
                            declared_class=claim_source_class,
                            prose=full_boundary_text,
                            line_no=claim_start_line,
                            file_path=file_path,
                        )
                        for f in boundary_findings:
                            f.section_role = current_section_role
                            f.source_class = (
                                claim_source_class.value
                                if claim_source_class != SourceClass.UNKNOWN
                                else "GENERIC"
                            )
                        findings.extend(boundary_findings)
                        in_claim_boundary = False
                        current_claim_prose = []

                cursor = match.end()

            # Trailing segment on this line
            trailing_segment = stripped[cursor:].strip()
            if trailing_segment and in_claim_boundary:
                current_claim_prose.append(trailing_segment)

            # Invariant: Being inside claimboundary != exemption from generic Publication Boundary rules.
            # Every visible line runs through all active generic rules unconditionally.
            for rule in self.rules:
                if profile in rule.profiles:
                    line_findings = rule.check_fn(visible_line, line_no, file_path, profile)
                    for f in line_findings:
                        f.section_role = current_section_role
                        f.source_class = (
                            current_inferred_source_class.value
                            if current_inferred_source_class != SourceClass.UNKNOWN
                            else "GENERIC"
                        )
                    findings.extend(line_findings)

        # Fail-closed check: unclosed claimboundary block at EOF
        if in_claim_boundary:
            findings.append(
                Finding(
                    rule_id="RULE-BOUNDARY-SYNTAX-MALFORMED",
                    category=FindingCategory.MALFORMED_STRUCTURE,
                    severity=Severity.HARD_FAIL,
                    message=f"Unclosed claimboundary environment starting at line {claim_start_line}; reached EOF without \\end{{claimboundary}}",
                    file_path=file_path,
                    line_number=claim_start_line,
                    section_role=current_section_role,
                    source_class=(
                        claim_source_class.value
                        if claim_source_class != SourceClass.UNKNOWN
                        else "GENERIC"
                    ),
                )
            )

        # Cross-line token splitting buffering: check consecutive non-empty lines
        # Preserves location-local semantic context from the originating line
        for idx in range(len(cleaned_lines) - 1):
            prev_line_no, prev_text, prev_role, prev_sclass = cleaned_lines[idx]
            curr_line_no, curr_text, curr_role, curr_sclass = cleaned_lines[idx + 1]

            candidate_variants = [
                (f"{prev_text.strip()} {curr_text.strip()}", len(prev_text.strip())),
                (f"{prev_text.strip()}{curr_text.strip()}", len(prev_text.strip())),
            ]
            seen_cross_rules: set[str] = set()

            for joined, boundary_offset in candidate_variants:
                for rule in self.rules:
                    if profile in rule.profiles and rule.rule_id not in seen_cross_rules:
                        cross_findings = rule.check_fn(joined, prev_line_no, file_path, profile)
                        for f in cross_findings:
                            if f.matched_text:
                                m_start = joined.find(f.matched_text)
                                if m_start != -1:
                                    m_end = m_start + len(f.matched_text)
                                    if m_start < boundary_offset and m_end > boundary_offset:
                                        f.line_number = prev_line_no
                                        # Location-local context strictly preserved
                                        f.section_role = prev_role
                                        f.source_class = (
                                            prev_sclass.value
                                            if prev_sclass != SourceClass.UNKNOWN
                                            else "GENERIC"
                                        )
                                        f.message = f"[Cross-Line] {f.message}"
                                        findings.append(f)
                                        seen_cross_rules.add(rule.rule_id)

        # Check standalone Claim Boundary prose if passed at document level without TeX tags
        if source_class and source_class != SourceClass.UNKNOWN and not in_claim_boundary:
            for line_no, line in enumerate(lines, start=1):
                if any(kw in line.lower() for kw in ["boundary", "claim", "limitations", "制限事項"]):
                    b_findings = validate_boundary_prose(
                        declared_class=source_class,
                        prose=line,
                        line_no=line_no,
                        file_path=file_path,
                    )
                    for f in b_findings:
                        f.section_role = current_section_role
                        f.source_class = source_class.value
                    findings.extend(b_findings)

        # Pass determination: ValidationResult.__post_init__ computes status and passed fail-closed
        return ValidationResult(
            target_file=file_path,
            profile=profile,
            findings=findings,
            metrics={
                "lines_scanned": len(lines),
                "rules_evaluated": len(self.rules),
            },
        )

    def scan_file(
        self,
        file_path: Path | str,
        profile: DocumentProfile = DocumentProfile.GENERIC,
        source_class: SourceClass | None = None,
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
        )
