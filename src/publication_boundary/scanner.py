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
        strict: bool = False,
    ) -> ValidationResult:
        # Check trusted external exemption policy (inline magic markers do NOT grant exemption)
        if self.exemption_policy and self.exemption_policy.is_exempt(file_path):
            return ValidationResult(
                target_file=file_path,
                profile=profile,
                passed=True,
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

        # Block state tracking for claimboundary
        in_claim_boundary = False
        claim_start_line = 0
        current_claim_prose: list[str] = []

        # Line-by-line scanning with cross-line lookahead buffer
        cleaned_lines: list[tuple[int, str]] = []

        for line_no, raw_line in enumerate(lines, start=1):
            # Comment stripping
            visible_line = strip_tex_comments(raw_line) if not is_markdown else raw_line
            stripped = visible_line.strip()
            if not stripped:
                continue

            cleaned_lines.append((line_no, visible_line))

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

            # Malformed tag checks (missing closing brace)
            if re.search(r"\\begin\{claimboundary(?!\})", stripped):
                findings.append(
                    Finding(
                        rule_id="RULE-BOUNDARY-SYNTAX-MALFORMED",
                        category=FindingCategory.MALFORMED_STRUCTURE,
                        severity=Severity.HARD_FAIL,
                        message="Malformed \\begin{claimboundary} syntax (missing closing brace)",
                        file_path=file_path,
                        line_number=line_no,
                        section_role=current_section_role,
                        source_class=current_inferred_source_class.value,
                    )
                )
                continue

            if re.search(r"\\end\{claimboundary(?!\})", stripped):
                findings.append(
                    Finding(
                        rule_id="RULE-BOUNDARY-SYNTAX-MALFORMED",
                        category=FindingCategory.MALFORMED_STRUCTURE,
                        severity=Severity.HARD_FAIL,
                        message="Malformed \\end{claimboundary} syntax (missing closing brace)",
                        file_path=file_path,
                        line_number=line_no,
                        section_role=current_section_role,
                        source_class=current_inferred_source_class.value,
                    )
                )
                continue

            # Check for same-line begin and end: \begin{claimboundary}... \end{claimboundary}
            same_line_match = re.search(
                r"\\begin\{claimboundary\}(?:\[[^\]]*\])?(.*?)\\end\{claimboundary\}",
                stripped,
            )
            if same_line_match:
                if in_claim_boundary:
                    findings.append(
                        Finding(
                            rule_id="RULE-BOUNDARY-SYNTAX-MALFORMED",
                            category=FindingCategory.MALFORMED_STRUCTURE,
                            severity=Severity.HARD_FAIL,
                            message="Nested claimboundary environment is forbidden",
                            file_path=file_path,
                            line_number=line_no,
                            section_role=current_section_role,
                            source_class=current_inferred_source_class.value,
                        )
                    )
                else:
                    inner_prose = same_line_match.group(1).strip()
                    boundary_findings = validate_boundary_prose(
                        declared_class=current_inferred_source_class,
                        prose=inner_prose,
                        line_no=line_no,
                        file_path=file_path,
                    )
                    for f in boundary_findings:
                        f.section_role = current_section_role
                        f.source_class = current_inferred_source_class.value
                    findings.extend(boundary_findings)
                continue

            # Check for \begin{claimboundary} opening multiline block
            if "\\begin{claimboundary}" in stripped:
                if in_claim_boundary:
                    findings.append(
                        Finding(
                            rule_id="RULE-BOUNDARY-SYNTAX-MALFORMED",
                            category=FindingCategory.MALFORMED_STRUCTURE,
                            severity=Severity.HARD_FAIL,
                            message=f"Nested claimboundary starting at line {line_no} inside active block from line {claim_start_line}",
                            file_path=file_path,
                            line_number=line_no,
                            section_role=current_section_role,
                            source_class=current_inferred_source_class.value,
                        )
                    )
                else:
                    in_claim_boundary = True
                    claim_start_line = line_no
                    current_claim_prose = []
                    # Capture any trailing text after \begin{claimboundary}[...]
                    post_begin = re.sub(r"^.*?\\begin\{claimboundary\}(?:\[[^\]]*\])?", "", stripped).strip()
                    if post_begin:
                        current_claim_prose.append(post_begin)
                continue

            # Check for \end{claimboundary} closing multiline block
            if "\\end{claimboundary}" in stripped:
                if not in_claim_boundary:
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
                    pre_end = re.sub(r"\\end\{claimboundary\}.*$", "", stripped).strip()
                    if pre_end:
                        current_claim_prose.append(pre_end)
                    full_boundary_text = " ".join(current_claim_prose)
                    boundary_findings = validate_boundary_prose(
                        declared_class=current_inferred_source_class,
                        prose=full_boundary_text,
                        line_no=claim_start_line,
                        file_path=file_path,
                    )
                    for f in boundary_findings:
                        f.section_role = current_section_role
                        f.source_class = current_inferred_source_class.value
                    findings.extend(boundary_findings)
                    in_claim_boundary = False
                    current_claim_prose = []
                continue

            if in_claim_boundary:
                current_claim_prose.append(stripped)

            # Evaluate each active rule on the current visible line
            for rule in self.rules:
                if profile in rule.profiles:
                    line_findings = rule.check_fn(visible_line, line_no, file_path, profile)
                    for f in line_findings:
                        f.section_role = current_section_role
                        f.source_class = current_inferred_source_class.value
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
                    source_class=current_inferred_source_class.value,
                )
            )

        # Cross-line token splitting buffering: check consecutive non-empty lines
        for idx in range(len(cleaned_lines) - 1):
            prev_line_no, prev_text = cleaned_lines[idx]
            curr_line_no, curr_text = cleaned_lines[idx + 1]

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
                                        f.section_role = current_section_role
                                        f.source_class = current_inferred_source_class.value
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
