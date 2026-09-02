# Publication Boundary Failure Taxonomy & Detection Matrix

This report addresses Research Questions **RQ-1**, **RQ-2**, and **RQ-3**, establishing a rigorous taxonomy of internal production leakages and defining the architectural boundary between deterministic linting and semantic validation.

---

## 1. RQ-1: Leakage Taxonomy

When complex survey production workflows (such as Survey Production Core v2) automate research, evidence collection, synthesis, and publication assembly, internal orchestration metadata frequently bleeds across into reader-facing prose. 

The table below classifies these leakages into distinct semantic categories, detailing why they are internal, what their legitimate reader-facing equivalents look like, how to detect them, and their associated false-positive risks.

| Semantic Category | Why It Is Internal | Legitimate Reader-Facing Equivalent | Detection Strategy | False-Positive Risk & Mitigation |
|---|---|---|---|---|
| **1. Architecture Rationale** | Reflects editorial scoping decisions and planner instructions made during the planning phase. Readers care about what occurred, not why editors assigned topics. | Natural topical synthesis explaining why developments are interconnected. | Regex detection of `承認済みArchitecture`, `Architecture says`, `Architecture requires`. | High if `architecture` is banned naively. Mitigated by checking preceding/following tokens (`software architecture` is allowed). |
| **2. Review-Resolution Language** | Preserves debate between human reviewers and drafting agents (e.g. arguing against prior drafts). A published edition should describe the final state of the world, not its editorial evolution. | Direct affirmative statements describing the week's multi-faceted events directly. | Pattern matching on rebuttal syntax (`三つのFeatureだけではない`, `〜だけではない`, `after review`). | Moderate for general usage of `だけではない`. Classified as `REVIEW_REQUIRED` for escalation to semantic gate. |
| **3. Screening / HOLD / DROP State** | Represents intermediate pipeline intake triage. Items dropped or held out have no verified standing in the current issue's factual payload. | Reader-facing Watchlist explaining ongoing monitoring of unverified items (`現状 / 未確認 / 注視点`). | Token matching for `HOLD_OUT`, `ScreeningでDROP`, `Screening Index`. | Low risk if `DROP` is checked with context (`packet drop` or `voltage drop` allowed). |
| **4. Evidence / Materiality Class** | Internal schema classifications (`VERIFIED`, `PARTIAL`, `MATERIAL`, `CONTEXT`) used by orchestrators to budget page layout. | Descriptive attribution notes (`Primary official source`, `Vendor release notes`). | Exact matching of enum tags (`[V/M]`, `[P/C]`) and key-value pairs (`Core v2 Evidence:`, `materiality:`). | Minimal risk; tags use distinct structured syntax. |
| **5. Candidate / Selection Metadata** | Reflects candidate queue management (`Candidate Selection`, `Candidate Inventory`, `昇格`). | Editorial framing explaining scope selection based on technical significance. | Matching workflow phrases (`Candidate Selection`, `Candidate Inventory`, `一次資料として昇格させない`). | Low risk if `candidate model` or `candidate solution` is permitted. |
| **6. Internal Provenance Paths** | Filesystem paths to local intake runs (`Grok_X_SourseIntake/...`, `sources/...`, `runs/...`). Inaccessible to external readers and exposes internal build environments. | Canonical public URLs (`https://x.com/...`, `https://github.com/...`) or stable DOI/arXiv links. | Regex recognition of repository directory structures and non-URL paths in bibliography/prose. | Extremely low risk; local filesystem paths have distinct path separators. |
| **7. Internal Source-Class Enums** | Raw programming enums (`SOCIAL_OBSERVATION`, `PRIMARY_FACT`, `VENDOR_CLAIM`) leaking into text. | Natural descriptions (`community observation`, `practitioner reports`, `official vendor statement`). | Exact matching of upper-case enum tokens. | Very low risk; uppercase enum tokens are distinct from general English prose. |
| **8. Core v2 Contract Language** | Meta-language referencing the production system itself (`Core v2 contract`, `Evidence Card`, `Draft Package`). | Omit entirely; the article speaks directly from primary technical facts. | Exact phrase matching for system identifiers. | Zero risk; legitimate articles have no need to reference internal pipeline names. |
| **9. Verification Obligations** | Editorial TODOs and build directives (`Verify expected_pdf_sha256`, `The publisher must verify...`). | Concrete statements of verified fact or explicit notes of limitation. | Regex matching for `Verify <symbol>` and imperative verification phrases. | Low risk when targeting imperative directive syntax. |

---

## 2. RQ-2: Lexical Detection vs Semantic Detection

A core defect of upstream Core v2 prior to this study was the assumption that a static substring blacklist could enforce publication boundaries. Certain failures are mathematically reducible to deterministic invariant patterns, while others require contextual and semantic comprehension.

```
+-----------------------------------------------------------------------------+
|                          PUBLICATION BOUNDARY ENFORCEMENT                   |
+-----------------------------------------------------------------------------+
|                                                                             |
|  [ TIER 1: DETERMINISTIC LINTING GATE ]                                      |
|  - Fast, zero external dependencies, 100% reproducible                      |
|  - Strictly rejects:                                                        |
|    * Category A: Prohibited internal tokens (Core v2, Evidence Card, etc.)  |
|    * Category B: Raw filesystem and intake paths (Grok_X_..., sources/...)   |
|    * Category F: Bibliography tag exposure ([V/M], Core v2 Evidence:)       |
|    * Category D: Explicit Architecture mention directives                   |
|    * Category E: Blatant Source-Class mismatch (Research paper with vendor) |
|                                                                             |
|                               |                                             |
|                     Suspicious Phrasing /                                   |
|                     REVIEW_REQUIRED                                         |
|                               v                                             |
|  [ TIER 2: OPTIONAL SEMANTIC REVIEW LAYER ]                                 |
|  - Deep context evaluation via LLM reviewer or editorial human-gate         |
|  - Dispatched via standardized SemanticPacket JSON schema                   |
|  - Resolves:                                                                |
|    * Category C: Subtle editorial review rebuttals vs genuine comparisons   |
|    * Category D: Substantive technical depth vs disguised topic lists       |
|    * Category E: Nuanced epistemic attribution boundary strength            |
|                                                                             |
+-----------------------------------------------------------------------------+
```

### In-Depth Failure Modes Matrix (A through F)

#### Failure A: Prohibited Internal Token Leakage
- **Nature**: Lexical / Structural.
- **Mechanism**: Pipeline identifiers (`Evidence Card`, `Core v2`, `SOCIAL_OBSERVATION`, `HOLD_OUT`, `D017`) appear verbatim in LaTeX or Markdown source.
- **Handling**: **Deterministic Hard Fail**. Regex lookaround patterns detect these tokens even when directly conjoined with Japanese particles (e.g. `HOLD_OUTとして`).

#### Failure B: Raw Repository / Provenance Path Leakage
- **Nature**: Lexical / Syntactic.
- **Mechanism**: Relative paths (`Grok_X_SourseIntake/...`) or absolute filesystem paths (`sources/2026-W33/.../data.json`) leak into `url = {...}` or footnote prose.
- **Handling**: **Deterministic Hard Fail**. Any URL or citation path matching repository directories is rejected unconditionally.

#### Failure C: Review Rebuttal Becoming Publication Thesis
- **Nature**: Semantic with lexical indicators.
- **Mechanism**: The publication thesis opens by arguing against rejected earlier drafts or reviewer criticism (e.g. *"This week is not just about three features"*).
- **Handling**: **Hybrid**.
  - Direct literal markers (`三つのFeatureだけではない`, `Architecture Reviewへの応答`) trigger **HARD_FAIL**.
  - Softer contrastive phrasing (`〜だけではない`, `after review`) triggers **REVIEW_REQUIRED** and generates a `SemanticPacket` for Tier 2 evaluation.

#### Failure D: "Architecture Requires X" as Substantive Coverage Substitute
- **Nature**: Semantic.
- **Mechanism**: The drafting agent satisfies must-cover requirements by writing: *"Approved Architecture defines cost efficiency, local execution, and IDE integration as observation axes."* It quotes the instructions instead of reporting facts.
- **Handling**: **Hybrid**.
  - If prose matches `Architectureは...を観察軸としている` -> **HARD_FAIL**.
  - If prose mentions required topics without concrete metrics or source observations -> **REVIEW_REQUIRED** in Tier 2 semantic depth audit.

#### Failure E: Source-Class Claim Boundary Mismatch
- **Nature**: Contextual / Semantic.
- **Mechanism**: A package or section focusing on academic research papers has a Claim Boundary stating: *"Statements are first-party vendor claims..."*.
- **Handling**: **Deterministic Invariant**. The scanner infers or accepts declared section class and verifies that the claim boundary contains expected framing (`author-reported`) and excludes incompatible framing (`vendor claims`).

#### Failure F: Bibliography Internal Disposition Exposure
- **Nature**: Lexical / Format.
- **Mechanism**: References contain internal tags `[V/M]`, `[P/C]`, or BibTeX notes stating `Core v2 Evidence: VERIFIED; materiality: MATERIAL`.
- **Handling**: **Deterministic Hard Fail**. Clean BibTeX parsing identifies illegal fields and rejects compilation before rendering.

---

## 3. RQ-3: Cross-Profile Portability

Upstream maintains two primary publication profiles:
1. `WEEKLY_MAGAZINE` (e.g. `2026-W33`): Fast-paced weekly survey covering breaking releases, community observations, and papers within a rolling 7-day window.
2. `LONGFORM_SPECIAL` (e.g. `SP001`): Thematic, multi-month retrospective or foundations report requiring extensive multi-page depth, balanced 2-column narrative, and cross-family comparative synthesis.

### Generic Rules (Enforced across ALL Profiles)
- Prohibited Core v2 production tokens (`Core v2`, `Evidence Card`, `HOLD_OUT`, `Screening`, `D017/D021`).
- Raw filesystem path detection in URLs and prose.
- Bibliography internal tag exclusion (`[V/M]`, `materiality:`).
- Source-class Claim Boundary consistency.
- Rejection of explicit Architecture directive citations.

### Profile-Specific Rules

#### `WEEKLY_MAGAZINE` Specific:
- **Weekly Rebuttal Syntax**: Rejection of `三つのFeatureだけではない` and related weekly architecture debate phrasing.
- **Watchlist Formatting**: Enforce reader-facing observation format (`現状 / 未確認 / 注視点`), forbidding candidate queue or carry-over management terms.
- **Community Pulse Restrictions**: Reject raw social intake file paths (`Grok_X_SourseIntake/...`) and ensure community sentiment is framed as contextual observation.

#### `LONGFORM_SPECIAL` Specific:
- **Evidence Promotion / Curation Terminology**: Reject phrases explaining internal evidence curation (e.g., `一次資料として昇格させない`, `coverage を広げる`, `本 package`).
- **Editorial Meta-Vocabulary**: Block terms like `reader-facing technical surface` and `reader-facing に答える` in concluding chapters.
- **Multi-Family Attribution Independence**: Ensure technical specification claims and licensing claims cite distinct primary sources without citing internal evidence IDs.
