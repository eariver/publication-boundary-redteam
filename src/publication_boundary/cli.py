"""Command-line interface for the Publication Boundary Scanner."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from publication_boundary.models import DocumentProfile, SourceClass
from publication_boundary.report import (
    format_json_report,
    format_markdown_summary,
    format_text_report,
)
from publication_boundary.scanner import PublicationScanner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="publication-boundary-scan",
        description="Scan publication manuscripts for internal production leakage and boundary regressions.",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="One or more files to scan (TeX, BibTeX, Markdown, text).",
    )
    parser.add_argument(
        "--profile",
        choices=["weekly", "longform", "generic"],
        default="generic",
        help="Publication profile context (default: generic).",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output report format (default: text).",
    )
    parser.add_argument(
        "--source-class",
        choices=[
            "VENDOR_ANNOUNCEMENT",
            "RESEARCH_PAPER",
            "OSS_RELEASE",
            "COMMUNITY_OBSERVATION",
            "INDEPENDENT_EVALUATION",
        ],
        default=None,
        help="Explicit source class context for Claim Boundary checking.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    profile_map = {
        "weekly": DocumentProfile.WEEKLY_MAGAZINE,
        "longform": DocumentProfile.LONGFORM_SPECIAL,
        "generic": DocumentProfile.GENERIC,
    }
    profile = profile_map[args.profile]
    source_class = SourceClass.from_string(args.source_class) if args.source_class else None

    scanner = PublicationScanner()
    results = []

    for raw_path in args.paths:
        path = Path(raw_path)
        if not path.exists():
            print(f"Error: Target path does not exist: {raw_path}", file=sys.stderr)
            return 2

        if path.is_file():
            results.append(
                scanner.scan_file(
                    path,
                    profile=profile,
                    source_class=source_class,
                )
            )
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and child.suffix in {".tex", ".bib", ".md", ".txt"}:
                    results.append(
                        scanner.scan_file(
                            child,
                            profile=profile,
                            source_class=source_class,
                        )
                    )

    if args.format == "json":
        print(format_json_report(results))
    elif args.format == "markdown":
        print(format_markdown_summary(results))
    else:
        print(format_text_report(results))

    all_passed = all(r.passed for r in results)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
