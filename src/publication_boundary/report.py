"""Report generator for publication boundary validation results."""

from __future__ import annotations

import json
from typing import Sequence

from publication_boundary.models import Severity, ValidationResult


def format_text_report(results: Sequence[ValidationResult]) -> str:
    """Render a human-readable text report suitable for CLI terminal display."""
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("PUBLICATION BOUNDARY SCAN REPORT")
    lines.append("=" * 78)

    total_files = len(results)
    passed_files = sum(1 for r in results if r.passed)
    total_hard_fails = sum(r.hard_fail_count for r in results)
    total_reviews = sum(r.review_required_count for r in results)
    total_info = sum(r.info_count for r in results)

    for res in results:
        status_str = "PASS" if res.passed else "FAIL"
        lines.append(f"\nTarget:  {res.target_file}")
        lines.append(f"Profile: {res.profile.value} | Status: [{status_str}]")
        lines.append(
            f"Counts:  {res.hard_fail_count} HARD_FAIL, "
            f"{res.review_required_count} REVIEW_REQUIRED, "
            f"{res.info_count} INFO"
        )

        if not res.findings:
            lines.append("  (No boundary findings detected)")
            continue

        lines.append("-" * 78)
        # Sort findings deterministically
        sorted_findings = sorted(
            res.findings,
            key=lambda f: (-f.severity.rank, f.line_number, f.column, f.rule_id),
        )

        for f in sorted_findings:
            prefix = f"[{f.severity.value}]"
            loc = f"L{f.line_number}:{f.column}"
            lines.append(f"  {prefix:<17} {loc:<8} {f.rule_id}")
            lines.append(f"    Message:    {f.message}")
            if f.matched_text:
                lines.append(f"    Match:      {f.matched_text!r}")
            if f.context_snippet:
                lines.append(f"    Context:    {f.context_snippet}")
            if f.suggestion:
                lines.append(f"    Suggestion: {f.suggestion}")
            lines.append("")

    lines.append("=" * 78)
    lines.append(
        f"SUMMARY: {passed_files}/{total_files} files passed. "
        f"Total: {total_hard_fails} HARD_FAIL, {total_reviews} REVIEW_REQUIRED, {total_info} INFO"
    )
    lines.append("=" * 78)

    return "\n".join(lines)


def format_json_report(results: Sequence[ValidationResult], indent: int = 2) -> str:
    """Render a structured JSON report conforming to the shared schema."""
    payload = {
        "schema_version": "1.0",
        "passed": all(r.passed for r in results),
        "total_targets": len(results),
        "targets_passed": sum(1 for r in results if r.passed),
        "total_findings": sum(len(r.findings) for r in results),
        "summary": {
            "hard_fails": sum(r.hard_fail_count for r in results),
            "review_required": sum(r.review_required_count for r in results),
            "info": sum(r.info_count for r in results),
        },
        "results": [r.to_dict() for r in results],
    }
    return json.dumps(payload, ensure_ascii=False, indent=indent)


def format_markdown_summary(results: Sequence[ValidationResult]) -> str:
    """Render a markdown summary table for PR comments or audit logs."""
    lines: list[str] = [
        "| Target File | Profile | Status | Hard Fails | Review Required | Info |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        status = "✅ PASS" if r.passed else "❌ FAIL"
        lines.append(
            f"| `{r.target_file}` | `{r.profile.value}` | {status} | "
            f"{r.hard_fail_count} | {r.review_required_count} | {r.info_count} |"
        )
    return "\n".join(lines)
