"""Data models and schemas for publication boundary validation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(str, Enum):
    """Finding severity level."""

    HARD_FAIL = "HARD_FAIL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    INFO = "INFO"

    @property
    def rank(self) -> int:
        return {"HARD_FAIL": 3, "REVIEW_REQUIRED": 2, "INFO": 1}[self.value]


class GateStatus(str, Enum):
    """Final status of a publication gate evaluation."""

    PASS = "PASS"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAIL = "FAIL"

    @property
    def is_passed(self) -> bool:
        """Return True only when the gate is fully cleared without blocking findings or pending review."""
        return self == GateStatus.PASS

    def __bool__(self) -> bool:
        return self == GateStatus.PASS


class FindingCategory(str, Enum):
    """Classification of publication boundary violations."""

    INTERNAL_TERMINOLOGY = "INTERNAL_TERMINOLOGY"
    RAW_PROVENANCE_PATH = "RAW_PROVENANCE_PATH"
    REVIEW_RESPONSE_PROSE = "REVIEW_RESPONSE_PROSE"
    ARCHITECTURE_COVERAGE_SUBSTITUTE = "ARCHITECTURE_COVERAGE_SUBSTITUTE"
    SOURCE_CLASS_BOUNDARY_MISMATCH = "SOURCE_CLASS_BOUNDARY_MISMATCH"
    BIBLIOGRAPHY_BOUNDARY = "BIBLIOGRAPHY_BOUNDARY"
    INTERNAL_IDENTIFIER = "INTERNAL_IDENTIFIER"
    MALFORMED_STRUCTURE = "MALFORMED_STRUCTURE"


class DocumentProfile(str, Enum):
    """Publication document profiles."""

    WEEKLY_MAGAZINE = "WEEKLY_MAGAZINE"
    LONGFORM_SPECIAL = "LONGFORM_SPECIAL"
    GENERIC = "GENERIC"


class SourceClass(str, Enum):
    """Taxonomy of evidence source classes for boundary alignment."""

    VENDOR_ANNOUNCEMENT = "VENDOR_ANNOUNCEMENT"
    RESEARCH_PAPER = "RESEARCH_PAPER"
    OSS_RELEASE = "OSS_RELEASE"
    COMMUNITY_OBSERVATION = "COMMUNITY_OBSERVATION"
    INDEPENDENT_EVALUATION = "INDEPENDENT_EVALUATION"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_string(cls, value: str) -> SourceClass:
        normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
        for member in cls:
            if member.value == normalized:
                return member
        return cls.UNKNOWN


@dataclass
class ExemptionPolicy:
    """Trusted external policy for exempting specific files or path patterns."""

    exempt_paths: set[str] = field(default_factory=set)
    exempt_globs: list[str] = field(default_factory=list)

    def is_exempt(self, file_path: str | Path) -> bool:
        from fnmatch import fnmatch
        path_str = str(file_path).replace("\\", "/")
        if path_str in self.exempt_paths:
            return True
        for glob_pat in self.exempt_globs:
            if fnmatch(path_str, glob_pat) or fnmatch(Path(path_str).name, glob_pat):
                return True
        return False


@dataclass
class Finding:
    """Individual publication boundary finding."""

    rule_id: str
    category: FindingCategory
    severity: Severity
    message: str
    file_path: str
    line_number: int
    column: int = 1
    matched_text: str = ""
    context_snippet: str = ""
    suggestion: str = ""
    section_role: str = ""
    source_class: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "column": self.column,
            "matched_text": self.matched_text,
            "context_snippet": self.context_snippet,
            "suggestion": self.suggestion,
            "section_role": self.section_role,
            "source_class": self.source_class,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Finding:
        return cls(
            rule_id=data["rule_id"],
            category=FindingCategory(data["category"]),
            severity=Severity(data["severity"]),
            message=data["message"],
            file_path=data["file_path"],
            line_number=data["line_number"],
            column=data.get("column", 1),
            matched_text=data.get("matched_text", ""),
            context_snippet=data.get("context_snippet", ""),
            suggestion=data.get("suggestion", ""),
            section_role=data.get("section_role", ""),
            source_class=data.get("source_class", ""),
        )


@dataclass
class ValidationResult:
    """Aggregated validation output for a file or artifact."""

    target_file: str
    profile: DocumentProfile
    passed: bool = False
    findings: list[Finding] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    status: GateStatus = GateStatus.PASS

    def __post_init__(self) -> None:
        if self.hard_fail_count > 0:
            self.status = GateStatus.FAIL
            self.passed = False
        elif self.review_required_count > 0:
            self.status = GateStatus.NEEDS_REVIEW
            self.passed = False  # Fail-closed: REVIEW_REQUIRED must not be a final PASS before semantic resolution
        else:
            self.status = GateStatus.PASS
            self.passed = True

    @property
    def hard_fail_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.HARD_FAIL)

    @property
    def review_required_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.REVIEW_REQUIRED)

    @property
    def info_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.INFO)

    def to_dict(self) -> dict[str, Any]:
        # Stable deterministic ordering: severity rank descending, line ascending, rule_id ascending
        sorted_findings = sorted(
            self.findings,
            key=lambda f: (-f.severity.rank, f.line_number, f.column, f.rule_id),
        )
        return {
            "schema_version": "1.0",
            "target_file": self.target_file,
            "profile": self.profile.value,
            "status": self.status.value,
            "passed": self.passed,
            "summary": {
                "total_findings": len(self.findings),
                "hard_fails": self.hard_fail_count,
                "review_required": self.review_required_count,
                "info": self.info_count,
            },
            "metrics": self.metrics,
            "findings": [f.to_dict() for f in sorted_findings],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


@dataclass
class SemanticPacket:
    """Standardized payload envelope dispatched to the optional semantic review layer."""

    packet_id: str
    document_profile: str
    section_role: str
    source_class: str
    text: str
    deterministic_findings: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticPacket:
        return cls(
            packet_id=data["packet_id"],
            document_profile=data["document_profile"],
            section_role=data.get("section_role", "unknown"),
            source_class=data.get("source_class", "unknown"),
            text=data["text"],
            deterministic_findings=data.get("deterministic_findings", []),
            context=data.get("context", {}),
            schema_version=data.get("schema_version", "1.0"),
        )


@dataclass
class SemanticReviewResponse:
    """Standardized evaluation returned by the semantic review layer."""

    packet_id: str
    verdict: str  # "PASS", "REVISE_PROSE", "HARD_FAIL"
    reviewer: str
    confidence: float
    rationale: str
    suggested_replacement: str | None = None
    flags: list[str] = field(default_factory=list)
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticReviewResponse:
        return cls(
            packet_id=data["packet_id"],
            verdict=data["verdict"],
            reviewer=data["reviewer"],
            confidence=float(data["confidence"]),
            rationale=data["rationale"],
            suggested_replacement=data.get("suggested_replacement"),
            flags=data.get("flags", []),
            schema_version=data.get("schema_version", "1.0"),
        )
