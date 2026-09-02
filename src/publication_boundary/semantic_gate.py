"""Two-tier publication gate: Deterministic Invariant Gate + Optional Semantic Review Layer."""

from __future__ import annotations

import json
import uuid
from typing import Callable, Sequence

from publication_boundary.models import (
    Finding,
    FindingCategory,
    SemanticPacket,
    SemanticReviewResponse,
    Severity,
    ValidationResult,
)


class DeterministicGate:
    """Tier 1: Deterministic invariant validation gate.

    Operates with zero external network or model dependencies.
    Executes lexical, path, boundary, and bibliographic invariant checks.
    """

    def __init__(self, fail_on_review_required: bool = False):
        self.fail_on_review_required = fail_on_review_required

    def evaluate(self, result: ValidationResult) -> tuple[bool, list[SemanticPacket]]:
        """Evaluate deterministic result.

        Returns:
            (gate_passed, packets_for_semantic_review)
        """
        hard_fails = [f for f in result.findings if f.severity == Severity.HARD_FAIL]
        reviews_needed = [f for f in result.findings if f.severity == Severity.REVIEW_REQUIRED]

        if hard_fails:
            # Deterministic hard fail halts the gate
            return False, []

        if reviews_needed:
            # Build semantic review packets for items requiring deeper analysis
            packets: list[SemanticPacket] = []
            for idx, finding in enumerate(reviews_needed, start=1):
                packet = SemanticPacket(
                    packet_id=f"PKT-{uuid.uuid4().hex[:8]}-{idx}",
                    document_profile=result.profile.value,
                    section_role="prose_block",
                    source_class="unknown",
                    text=finding.context_snippet or finding.matched_text,
                    deterministic_findings=[finding.to_dict()],
                    context={
                        "target_file": result.target_file,
                        "line_number": finding.line_number,
                        "rule_id": finding.rule_id,
                    },
                )
                packets.append(packet)

            if self.fail_on_review_required:
                return False, packets
            return True, packets

        return True, []


# Protocol for pluggable semantic reviewers
SemanticReviewerCallable = Callable[[SemanticPacket], SemanticReviewResponse]


class SemanticReviewGate:
    """Tier 2: Optional semantic review evaluation gate."""

    def __init__(self, reviewer: SemanticReviewerCallable | None = None):
        self.reviewer = reviewer or self._default_mock_reviewer

    @staticmethod
    def _default_mock_reviewer(packet: SemanticPacket) -> SemanticReviewResponse:
        """Default conservative mock reviewer when no external LLM is configured."""
        # If any finding is tagged REVIEW_RESPONSE_PROSE and contains debate words, flag it
        text = packet.text
        if "だけではない" in text or "after review" in text.lower():
            return SemanticReviewResponse(
                packet_id=packet.packet_id,
                verdict="REVISE_PROSE",
                reviewer="mock-semantic-gate-v1",
                confidence=0.85,
                rationale="Prose presents editorial review debate structure rather than primary reader thesis.",
                suggested_replacement="Restructure paragraph to describe current developments directly.",
                flags=["EDITORIAL_DEBATE_PROSE"],
            )

        return SemanticReviewResponse(
            packet_id=packet.packet_id,
            verdict="PASS",
            reviewer="mock-semantic-gate-v1",
            confidence=0.90,
            rationale="Context represents legitimate technical prose or appropriate limitation notice.",
        )

    def review_packets(
        self, packets: Sequence[SemanticPacket]
    ) -> tuple[bool, list[SemanticReviewResponse]]:
        """Review a batch of semantic packets.

        Returns:
            (all_passed, list of review responses)
        """
        responses: list[SemanticReviewResponse] = []
        all_passed = True

        for packet in packets:
            resp = self.reviewer(packet)
            responses.append(resp)
            if resp.verdict != "PASS":
                all_passed = False

        return all_passed, responses


def generate_semantic_review_prompt(packet: SemanticPacket) -> str:
    """Generate a prompt for an LLM reviewer evaluating a suspicious publication snippet."""
    return f"""You are an independent Publication Boundary Auditor for a technical survey publication.
Review the following text excerpt to determine whether it leaks internal production metadata,
describes internal editorial review debates (e.g. arguing against prior drafts or reviewer critiques),
or uses internal pipeline terminology instead of reader-facing factual prose.

Document Profile: {packet.document_profile}
Section Role: {packet.section_role}
Source Class: {packet.source_class}

Excerpt under review:
\"\"\"
{packet.text}
\"\"\"

Deterministic Findings identified:
{json.dumps(packet.deterministic_findings, indent=2, ensure_ascii=False)}

Instructions:
1. Determine if the excerpt contains internal pipeline workflow language or debate rebuttal framing.
2. If legitimate technical prose (e.g. discussing software architecture or empirical evidence), return verdict "PASS".
3. If internal process language or debate rebuttal is present, return verdict "REVISE_PROSE" and provide a reader-facing alternative.
4. If raw pipeline state, internal tags, or unredacted paths are leaked, return "HARD_FAIL".

Respond strictly with valid JSON conforming to the following schema:
{{
  "packet_id": "{packet.packet_id}",
  "verdict": "PASS" | "REVISE_PROSE" | "HARD_FAIL",
  "reviewer": "your-model-id",
  "confidence": 0.0 - 1.0,
  "rationale": "Clear technical explanation",
  "suggested_replacement": "Reader-facing alternative prose if needed",
  "flags": ["LIST_OF_APPLICABLE_FLAGS"]
}}
"""
