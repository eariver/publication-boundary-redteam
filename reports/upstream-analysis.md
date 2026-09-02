# Upstream Root Cause & Architectural Analysis

This report documents the architectural root causes of Publication Boundary regressions observed across `eariver/japanese-generative-ai-survey`, tracing from initial editorial principles to concrete code mechanisms and independently proposed detection strategies.

---

## 1. Trace Matrix: Issues #9, #400, #433, #434

| Issue | Role / Domain | Issue Requirement | Actual Failure Mode | Current Implementation Behavior | Independently Proposed Detection Mechanism |
|---|---|---|---|---|---|
| **#9** | Foundational Editorial Separation | Strict separation of (1) reader prose, (2) claim boundary / source notes, (3) repository provenance. | Workflow tracking terms (`Candidate Inventory`, `Reaction Pass`) leaked into published prose. | Added `scripts/editorial_prose_guard.py` with 10 static regex patterns. Hardcoded in preflight. | Tier 1 AST/lexical scanner with category-based taxonomy; TeX-aware comment stripping; structured finding reports. |
| **#400** | Thematic Longform (`SP001`) | Preserve balanced 2-column mixed layout; prevent extreme compression; ensure deep technical synthesis without leaking internal review notes. | Output regressed to 1-column layout; text compressed to 7p/14p; internal IDs (`D017`, `D021`), `Verify ...` obligations, and `materiality` / `Core v2 Evidence` leaked into prose and `.bib`. | Fragmented post-hoc audits (`publication-boundary-audit-r4.json`) using 16 ad-hoc strings; PR #473 added parser for numbered section headers but left prose vocabulary unguarded. | Context-aware internal identifier detector; verification obligation regex; BibTeX schema linter for `@online` notes and URLs. |
| **#433** | Weekly Magazine (`2026-W33`) | Deliver 18p-depth weekly survey; eliminate editorial debate prose; prevent internal state tags in references; correct Claim Boundary per source class. | 6p preview; Executive Brief opened with editorial rebuttal (`三つのFeatureだけではない`); internal states (`HOLD_OUT`, `Screening`, `DROP`) in prose; `[V/M]` tags and raw `Grok_X_SourseIntake/...` paths in `.bib`; research paper given vendor claim boundary. | `scripts/survey_weekly_semantic_publication_v2.py` enforced verbatim copying of `current_interpretation` into publication summary (L117, L387) and formatted `Core v2 Evidence` into BibTeX (L74). | Review-response prose heuristic (HARD_FAIL/REVIEW_REQUIRED); raw path regex detector; source-class Claim Boundary consistency validator. |
| **#434** | Shared Pipeline / Workflow Authority | Create an explicit Publication Boundary contract; prevent review rationale serialization; require non-empty publication payload; reject coverage-by-mention. | Same structural leakage across both `WEEKLY` and `LONGFORM` profiles: internal selection rationale substituted for reader content; mechanical topic presence counted as depth. | Core v2 lacked an isolated reader-manuscript stage; fallback to internal rationale occurred by design; preflight prose guard was outdated. | Two-tier gate (Deterministic Invariant Gate + Optional Semantic Review Packet); explicit payload contract; anti-mention heuristic. |

---

## 2. In-Depth Analysis of Failure Mechanics

### 2.1 The Forced-Rebuttal Mechanism (`survey_weekly_semantic_publication_v2.py`)
In upstream `scripts/survey_weekly_semantic_publication_v2.py`, lines 117–118 and 387–388:
```python
if weekly.get("source") != "profile_synthesis.current_interpretation":
    raise ValueError("Weekly closing summary must be sourced from profile_synthesis.current_interpretation")
...
if current_interpretation not in data["final_summary"]["paragraphs"]:
    raise SystemExit("Weekly final summary must preserve exact profile_synthesis.current_interpretation as an approved source paragraph")
```
When Human Reviewers provided feedback during Architecture Review (e.g., *"Three features are not enough to represent the entire week"*), the internal synthesis agent recorded the editorial rationale:
> *"W33は三つのFeatureだけで説明できる週ではなかった。Community PulseやPaper Watchを含めた多層展開が必要..."*

Because the script enforced exact verbatim inclusion of `current_interpretation` into the final summary paragraphs of `main.tex`, the internal editorial debate became reader-facing text by algorithmic requirement.

### 2.2 Bibliography Provenance Injection
In `survey_weekly_semantic_publication_v2.py`, line 74:
```python
note = f"Core v2 Evidence: {status}; materiality: {materiality}"
```
and lines 228–234:
```python
locator = discovery_row.get("source_locator")
records[did] = {
    "entity": {
        "canonical_name": title.strip(),
        "canonical_url": locator.strip(),
        "organization": None,
    },
    "status": matrix_status,
    "materiality": matrix_materiality,
}
```
For community/X sources, `source_locator` was the internal filesystem intake path:
`Grok_X_SourseIntake/Weekly/2026-W33/.../grok-x-result.md`.
The assembler dumped internal repository paths into `canonical_url` and injected internal classification tags (`[V/M]`, `[P/C]`, `Core v2 Evidence: VERIFIED`) directly into the reader-facing bibliography.

### 2.3 Mechanical Architecture Coverage vs Substantive Depth
In W33 Community Pulse, the Architecture specified 6 observation axes:
- `release wave`, `cost per successful run`, `local/open-weight`, `harness/IDE integration`, `practitioner testing`, `correction signals`.

Rather than synthesizing observations from actual community evidence, the generated text stated:
> *"承認済みArchitectureは、release wave、cost per successful run、local/open-weight、harness/IDE integration、practitioner testing、correction signalsを観察軸としている。"*

The existing validation passed this because the keywords were present. The prose merely described the Architecture's instructions rather than fulfilling them.

### 2.4 Stagnant Prose Guard
Upstream's sole deterministic prose check, `scripts/editorial_prose_guard.py`, only checked 10 patterns established in Issue #9:
- `Candidate Inventory`, `Candidate Selection`, `Reaction Pass`, `primary verification`, `Issue Architecture`, `Evidence Task`, `Draft Package`.

It was completely blind to Core v2 terminology introduced in subsequent redesigns:
- `Core v2 contract`, `Evidence Card`, `SOCIAL_OBSERVATION`, `HOLD_OUT`, `Screening`, `DROP`, `materiality:`, `Core v2 Evidence:`, `Verify ...`, internal IDs (`D017`, `D021`), and review rebuttal phrasing.

---

## 3. Independent Detection Strategy

To prevent these failure modes without brittle monkey-patching, the validator prototype must implement:
1. **Context-Aware Token Detection**: Match internal terms in context while allowing legitimate technical usage (`evidence from experiments`, `software architecture`).
2. **Path Syntax & Repository Structure Scanner**: Regex recognition of internal intake structures (`Grok_X_SourseIntake`, `sources/...`, `drafting/...`).
3. **Review-Response Prose Heuristics**: Multi-level scoring (`HARD_FAIL`, `REVIEW_REQUIRED`, `INFO`) for debate phrasing (`Xだけではない`, `approved Architecture says`).
4. **Source-Class Boundary Rules**: Strict validation ensuring Claim Boundaries match declared source provenance (e.g. academic papers must use author-reported claims, not vendor claims).
5. **Bibliography Record Validation**: Structured parsing of BibTeX entries to block internal status notes and invalid URL locators.
