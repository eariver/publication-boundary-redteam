"""Publication Boundary Red-Team & Validator Prototype.

Independent validation tools to prevent internal production terminology,
raw repository paths, review-response prose, and bibliography provenance
leakage from appearing in reader-facing technical publications.
"""

from publication_boundary.models import (
    DocumentProfile,
    Finding,
    FindingCategory,
    SemanticPacket,
    SemanticReviewResponse,
    Severity,
    SourceClass,
    ValidationResult,
)
from publication_boundary.scanner import PublicationScanner

__all__ = [
    "DocumentProfile",
    "Finding",
    "FindingCategory",
    "PublicationScanner",
    "SemanticPacket",
    "SemanticReviewResponse",
    "Severity",
    "SourceClass",
    "ValidationResult",
]

__version__ = "0.1.0"
