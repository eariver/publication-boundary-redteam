# Upstream Authority & Provenance Snapshot

This document records the exact upstream repository state and historical issue authorities used for the independent Publication Boundary analysis and red-team investigation.

## 1. Upstream Authority Coordinates

- **Repository**: `eariver/japanese-generative-ai-survey`
- **Repository URL**: `https://github.com/eariver/japanese-generative-ai-survey`
- **Default Branch**: `main`
- **Pinned HEAD Commit SHA**: `c7a898889463b049dea4ee7337ee16ad5fbf3191`
- **Snapshot Pinned Timestamp**: `2026-09-03T01:25:00+09:00` (`2026-09-02T16:25:00Z`)
- **Authority Rule**: All research, failure analysis, and fixture derivations in this repository bind strictly to this fixed snapshot SHA and the issue authorities documented below. Any subsequent changes to upstream `main` do not alter the baseline authority of this study.

---

## 2. Core Issue Authorities (Chronological & Functional Roles)

### Issue #9 — Foundational Editorial Boundary
- **Title**: `[Editorial] 創刊号の読者向け体裁を整理する — 内部編集メモの分離・週次性・Late Breaking重複`
- **URL**: `https://github.com/eariver/japanese-generative-ai-survey/issues/9`
- **Created**: 2026-08-10T13:44:43Z
- **State**: `OPEN` (Retained as living editorial policy checkpoint)
- **Role**: Established the initial three-layer separation model:
  1. **Published prose**: Reader-facing text presenting developments cleanly without editorial meta-language.
  2. **Claim Boundary / Source Notes**: Explicit statements of claim strength, attribution, and source limitations.
  3. **Repository provenance**: Full internal audit trail, acquisition records, and verification state.
- **Initial Upstream Implementation**: PR #10 created `scripts/editorial_prose_guard.py` with 10 static patterns (`Candidate Inventory`, `Reaction Pass`, `Evidence Task`, etc.).

---

### Issue #400 — SP001 Longform Regression
- **Title**: `[Publication][SP001] Previewがmixed layoutから回帰し、LONGFORM_SPECIALとして著しく内容不足`
- **URL**: `https://github.com/eariver/japanese-generative-ai-survey/issues/400`
- **Created**: 2026-08-23T03:14:55Z
- **Updated**: 2026-08-28T23:46:09Z
- **State**: `OPEN`
- **Profile**: `THEMATIC / LONGFORM_SPECIAL`
- **Observed Failures**:
  - Layout collapsed from 2-column balanced narrative + full-width notes into 1-column layout;
  - Severe content compression (down to 7 pages from target 18–34 pages);
  - Internal Evidence IDs in reader prose: `D017`, `D021`;
  - Core v2 pipeline state in prose and bibliography: `Verify ...`, `Core v2 Evidence: VERIFIED; materiality: MATERIAL`, `accepted Evidence`, `受理されたEvidence`;
  - Internal pipeline workflow phrases: `本 package`, `一次資料として昇格させない`, `coverage を広げる`;
  - Editorial meta-vocabulary: `reader-facing technical surface`, `reader-facing に答える`.

---

### Issue #433 — 2026-W33 Weekly Regression
- **Title**: `[Publication][2026-W33] Reader-facing本文にArchitecture/Screening等の内部編集メタが再露出し、記事内容も過圧縮されている`
- **URL**: `https://github.com/eariver/japanese-generative-ai-survey/issues/433`
- **Created**: 2026-08-23T05:46:50Z
- **Closed**: 2026-09-02T00:12:55Z (via canonical Release & PR #482)
- **State**: `CLOSED`
- **Profile**: `WEEKLY / WEEKLY_MAGAZINE`
- **Observed Failures**:
  - Extreme page collapse: Preview rendered at 6 pages against target 18 pages;
  - Direct serialization of Human Review rebuttal into Executive Brief & Weekly Synthesis: `W33は三つのFeatureだけではない`, `三つのFeatureだけで説明できる週ではなかった`;
  - Direct leakage of internal selection states: `承認済みArchitecture`, `Evidence Card`, `SOCIAL_OBSERVATION`, `Core v2 contract`, `Discovery`, `Screening`, `HOLD_OUT六件はFresh W33 ScreeningでDROP`;
  - Bibliography publication boundary failure: References rendered with internal Core v2 disposition tags `[V/M]`, `[P/C]`, `[V/C]` and tag index explanation `Evidence tags: V = VERIFIED, P = PARTIAL; M = MATERIAL, C = CONTEXT`;
  - Raw provenance path leakage: X/Grok observation bibliography rendered internal repository path `Grok_X_SourseIntake/Weekly/2026-W33/.../grok-x-result.md` as public URL;
  - Claim Boundary mismatch: Research Paper Watch applied generic vendor claim boundary (`Capability/performance statements are first-party vendor claims...`) to academic research papers.

---

### Issue #434 — Central Shared Workflow Authority
- **Title**: `[Pipeline][Core v2][Publication] Architecture/Review/Selection内部状態をreader-facing proseへ直結させないPublication Boundaryを必須化する`
- **URL**: `https://github.com/eariver/japanese-generative-ai-survey/issues/434`
- **Created**: 2026-08-23T05:48:12Z
- **Updated**: 2026-08-28T17:12:07Z
- **State**: `OPEN`
- **Role**: Primary authority governing the cross-profile failure mechanism. Established that the regressions in #400 and #433 were not isolated editorial typos, but systematic defects in the Core v2 pipeline flow:
  - Architecture -> Draft/Synthesis -> Publication Assembly -> Validation.
- **Root Cause Findings in Upstream Code**:
  - `scripts/survey_weekly_semantic_publication_v2.py:117-118`: Explicitly required closing summary to originate from `profile_synthesis.current_interpretation`.
  - `scripts/survey_weekly_semantic_publication_v2.py:387-388`: Hard error thrown if the exact string from `profile_synthesis.current_interpretation` was not present verbatim in the published final summary paragraphs!
  - `scripts/survey_weekly_semantic_publication_v2.py:74`: Hardcoded injection of internal states into BibTeX notes: `note = {Core v2 Evidence: {status}; materiality: {materiality}}`.
  - `scripts/survey_weekly_semantic_publication_v2.py:228-234`: Passed internal `source_locator` (e.g. `Grok_X_SourseIntake/...`) directly into reader bibliography `canonical_url`.
  - `scripts/editorial_prose_guard.py`: Stagnant since Issue #9; completely lacked rules for Core v2 enums, state labels, review rebuttal phrasing, or path detection.

---

## 3. Related Historical & Cross-Cutting Upstream Issues

- **Issue #54**: `[Editorial][Special] Technical Notesの種別・時系列に内部enumが露出している` (Historical enum leakage in special editions).
- **Issue #139**: `[Editorial][Pipeline][Special] Technical Notesにsource-specificでないfallback要約が露出している` (Fallback summary leakage when specific notes missing).

---

## 4. Key Upstream Pull Requests & Milestones

| PR Number | Branch | Merged Timestamp | Scope / Significance |
|-----------|--------|------------------|----------------------|
| **#10** | `fix/editorial-prose-guard` | 2026-08-10 | Created initial `scripts/editorial_prose_guard.py` for Issue #9. |
| **#446** | `refactor/survey-production-core-v2` | 2026-08-23T08:52:28Z | Core v2 redesign after W33/SP001 production validation. |
| **#473** | `fix/core-v2-reader-substantive-fidelity-434` | 2026-08-26T23:29:31Z | Enforced reader substantive Architecture fidelity; created `scripts/survey_reader_fidelity_v2.py`. |
| **#475** | `fix/core-v2-longform-mixed-layout-review-400` | 2026-08-28T12:39:17Z | Enforced mixed-layout exact PDF verification. |
| **#482** | `provenance/w33-release` | 2026-09-02T00:12:09Z | Recorded canonical W33 release provenance (PDF SHA-256 `1885762325c33b575dd6e789dc53f7ed1c30483a9928b6dbf9537ad0e05661f5`). |

---

## 5. Audit of Key Upstream Files at Snapshot

1. `scripts/editorial_prose_guard.py` (Lines 18–35):
   Only contains 10 legacy patterns: `Candidate Inventory`, `Candidate Selection`, `Reaction Pass`, `primary verification`, `Issue Architecture`, `Evidence Task`, `Draft Package`, and 3 Japanese phrases. It misses all Core v2 terminology.
2. `scripts/survey_weekly_semantic_publication_v2.py`:
   - Line 74: `note = {Core v2 Evidence: {status}; materiality: {materiality}}`
   - Line 117-118: `if weekly.get("source") != "profile_synthesis.current_interpretation": raise ValueError(...)`
   - Line 228-234: `locator = discovery_row.get("source_locator") ... "canonical_url": locator.strip()`
   - Line 387-388: `if current_interpretation not in data["final_summary"]["paragraphs"]: raise SystemExit(...)`
3. `sources/SP001/publication/v2/publication-boundary-audit-r4.json`:
   Ad-hoc list of 16 static phrases used for manual/edition-local checks (`D017`, `D021`, `accepted Evidence`, `受理されたEvidence`, `本 package`, `一次資料として昇格させない`, etc.), confirming the lack of a standardized shared validator.
4. `sources/2026-W33/execution/reviews/w33-publication-preview-r2-single-boundary-cleanup-sol-review-20260901-r1.md`:
   Records single boundary manual finding (`accepted capture` in bibliography note) requiring custom repair authorization before publication.
