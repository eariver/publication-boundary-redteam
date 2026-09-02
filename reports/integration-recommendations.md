# Upstream Integration Recommendations & Issue #434 AC Mapping

This report provides an independent engineering roadmap for integrating publication boundary validation into `eariver/japanese-generative-ai-survey` without disrupting upstream workflows or introducing brittle constraints.

---

## 1. Issue #434 Acceptance Criteria Mapping Table

Each Acceptance Criteria (AC) item from Issue #434 is mapped below to its implementation feasibility status:
- `COVERED_BY_PROTOTYPE`: Fully enforced by the standalone validator prototype in this repository.
- `PARTIALLY_COVERED`: Detected by prototype rules, but requires upstream pipeline/schema cooperation for full enforcement.
- `REQUIRES_UPSTREAM_CHANGE`: Requires modifications to upstream Core v2 renderers, synthesizers, or schema files.
- `NOT_ADDRESSABLE_BY_LINT`: Inherent to human editorial gates or generative agent reasoning; cannot be solved by static linting alone.

| # | Issue #434 Acceptance Criteria Description | Status | Prototype Coverage & Implementation Notes |
|---|---|---|---|
| **AC-01** | Core v2 has explicit contract separating internal editorial/provenance layer and reader-facing publication layer. | `REQUIRES_UPSTREAM_CHANGE` | Prototype models the contract (`FindingCategory`, `SourceClass`, `SemanticPacket`), but upstream must isolate reader artifacts from internal execution runs. |
| **AC-02** | Human Architecture Review feedback / rebuttal structure is not directly serialized into reader prose. | `COVERED_BY_PROTOTYPE` | Enforced by `RULE-REVIEW-REBUTTAL-HARD-FAIL` and `RULE-REVIEW-REBUTTAL-SUSPICIOUS` (detects `三つのFeatureだけではない` and related rebuttal markers). |
| **AC-03** | Publication thesis explains the final structure directly even if Architecture has review-reactive rationale. | `PARTIALLY_COVERED` | Prototype catches direct review phrasing; nuanced indirect framing is escalated to Tier 2 Semantic Review via `SemanticPacket`. |
| **AC-04** | Weekly/Profile Synthesis requires non-empty `publication_payload` when reader text is needed. | `REQUIRES_UPSTREAM_CHANGE` | Upstream synthesizer (`survey_weekly_semantic_publication_v2.py`) must require `publication_payload` schema and fail closed if empty. |
| **AC-05** | Publication renderer does not fall back directly to internal `profile_payload` or Architecture rationale. | `REQUIRES_UPSTREAM_CHANGE` | Upstream rendering scripts must remove fallback lines (specifically deleting lines 117–118 and 387–388 from `survey_weekly_semantic_publication_v2.py`). |
| **AC-06** | Verify that each must-cover requirement reaches an Evidence-backed reader-facing content block. | `PARTIALLY_COVERED` | Upstream PR #473 introduced section block matching (`survey_reader_fidelity_v2.py`); prototype complements this by verifying text content quality. |
| **AC-07** | Paragraphs merely explaining Architecture directives are not treated as must-cover fulfillment. | `COVERED_BY_PROTOTYPE` | Enforced by `RULE-ARCH-COVERAGE-SUBSTITUTE` (rejects `Architectureは...を観察軸としている`). |
| **AC-08** | Claim Boundary is converted to reader-facing prose matching the declared source class. | `COVERED_BY_PROTOTYPE` | Enforced by `RULE-BOUNDARY-SOURCE-CLASS-MISMATCH` in `source_class.py` (rejects vendor claims in research papers, etc.). |
| **AC-09** | Raw Architecture boundary and Core v2 contract wording is not output to PDF. | `COVERED_BY_PROTOTYPE` | Enforced by `RULE-TERM-CORE-V2`, `RULE-TERM-DRAFT-PACKAGE`, and exact pattern matchers in `rules.py`. |
| **AC-10** | References default-exclude internal Evidence, materiality, and disposition tags. | `COVERED_BY_PROTOTYPE` | Enforced by `RULE-BIB-INTERNAL-TAG-LEAK` (detects `[V/M]`, `materiality:`, `Core v2 Evidence:` in `.bib` and text). |
| **AC-11** | Raw internal Grok intake or repository source paths are not output as reader URLs. | `COVERED_BY_PROTOTYPE` | Enforced by `RULE-PATH-RAW-PROVENANCE` (detects `Grok_X_SourseIntake/...`, `sources/...`, `runs/...`). |
| **AC-12** | Detect W33 (#433) leakage (`Architecture`, `Evidence Card`, `SOCIAL_OBSERVATION`, `HOLD_OUT`, `Screening`, `DROP`, `materiality`) in pre-Publication Gate. | `COVERED_BY_PROTOTYPE` | Enforced by `check_internal_terminology` in `rules.py`. Verified against all W33 bad fixtures. |
| **AC-13** | Detect SP001 (#400) leakage (`Verify ...`, `Evidence pass`, `Core v2 Evidence`, `materiality`, `D017/D021`) in the same generic gate. | `COVERED_BY_PROTOTYPE` | Enforced by the same generic ruleset in `rules.py`. Verified against all SP001 longform fixtures. |
| **AC-14** | Add regression tests across both `WEEKLY_MAGAZINE` and `LONGFORM_SPECIAL`. | `COVERED_BY_PROTOTYPE` | Verified in `tests/test_fixtures.py` across 16 weekly and 16 longform fixtures (plus 8 ambiguous fixtures). |
| **AC-15** | Regenerate SP001 and 2026-W33 after fix and confirm workflow-level acceptance outside edition issues. | `NOT_ADDRESSABLE_BY_LINT` | Requires upstream pipeline execution, LaTeX compilation, and Human Publication Preview Gate review. |

---

## 2. Upstream Rule Categorization & Merging Strategy

When upstream considers adopting rules from this prototype, they should be partitioned according to stability and implementation layer:

```
+-----------------------------------------------------------------------------+
|                     UPSTREAM ADOPTION STRATEGY LAYERS                       |
+-----------------------------------------------------------------------------+
|                                                                             |
|  [ LAYER 1: IMMEDIATELY USEFUL (DROP-IN DETERMINISTIC RULES) ]               |
|  - Drop directly into scripts/editorial_prose_guard.py                      |
|  * RULE-TERM-CORE-V2, RULE-TERM-EVIDENCE-CARD, RULE-TERM-SOCIAL-OBSERVATION |
|  * RULE-TERM-HOLD-OUT, RULE-TERM-SCREENING-STATE                            |
|  * RULE-TERM-INTERNAL-ID (D017, D021, EVD-xxx)                              |
|  * RULE-PATH-RAW-PROVENANCE (Grok_X_SourseIntake/..., sources/...)          |
|  * RULE-BIB-INTERNAL-TAG-LEAK ([V/M], [P/C])                                |
|                                                                             |
|  [ LAYER 2: RULES NEEDING CORE V2 PIPELINE / SCHEMA CHANGES ]               |
|  - Requires modifying upstream assembler scripts                            |
|  * Delete L117-118 and L387-388 in survey_weekly_semantic_publication_v2.py  |
|  * Remove line 74 "note = {Core v2 Evidence:...}" in .bib generation        |
|  * Enforce non-empty publication_payload in Profile Synthesis               |
|                                                                             |
|  [ LAYER 3: PROFILE-SPECIFIC CHECKS ]                                       |
|  - Configured per profile (Weekly vs Special)                               |
|  * RULE-REVIEW-REBUTTAL-HARD-FAIL (三つのFeatureだけではない - Weekly)      |
|  * RULE-TERM-PROMOTION-COVERAGE-METAS (昇格させない/本 package - Longform)  |
|  * RULE-TERM-READER-FACING-META (reader-facing technical surface - Longform) |
|                                                                             |
|  [ LAYER 4: SEMANTIC-ONLY CHECKS (TIER 2 GATE) ]                            |
|  - Dispatched via SemanticPacket to LLM or Human Gate                       |
|  * RULE-REVIEW-REBUTTAL-SUSPICIOUS (subtle contrastive prose)               |
|  * Substantive technical depth validation (beyond keyword presence)         |
|                                                                             |
|  [ LAYER 5: RULES TOO FRAGILE TO MERGE NAIVELY ]                            |
|  - Do NOT merge without contextual boundaries:                              |
|  * Naive substring matching on "Evidence", "Architecture", or "Candidate"   |
|                                                                             |
+-----------------------------------------------------------------------------+
```

---

## 3. Minimal Step-by-Step Upstream Integration Plan

If the upstream maintainer chooses to integrate these findings into `japanese-generative-ai-survey`, the recommended minimal path is:

1. **Step 1: Upgrade `scripts/editorial_prose_guard.py`**:
   - Replace the 10 legacy patterns with the context-aware `INTERNAL_EXACT_PATTERNS`, `PROVENANCE_PATH_PATTERNS`, and `BIB_STATUS_TAGS` from `publication_boundary/rules.py`.
   - Adopt ASCII lookarounds (`(?<![a-zA-Z0-9_])` and `(?![a-zA-Z0-9_])`) to protect mixed Japanese-English text.
   - Run in existing preflight CI checks (`scripts/preflight_final_issue.py`).

2. **Step 2: Clean Assembler BibTeX & Final Summary Logic**:
   - In `scripts/survey_weekly_semantic_publication_v2.py`:
     - Delete line 74 (`note = {Core v2 Evidence...}`).
     - In line 234, ensure `canonical_url` falls back to official repository or provider URLs, refusing to serialize `Grok_X_SourseIntake/...`.
     - Remove the check enforcing `profile_synthesis.current_interpretation` into `final_summary`.

3. **Step 3: Integrate Source-Class Claim Boundary Validation**:
   - Incorporate `source_class.py` into `survey_reader_fidelity_v2.py` so that TeX Claim Boundary blocks are checked against package metadata before rendering.

4. **Step 4: Optional Semantic Gate Hook**:
   - In `survey_publication_v2.py`, add an optional inspection hook using `SemanticPacket` schema to serialize suspicious paragraphs for LLM editorial review before reaching the Human Gate.
