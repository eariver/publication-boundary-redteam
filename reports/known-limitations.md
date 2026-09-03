# Validator Red-Team Evaluation & Known Limitations

This document presents an adversarial self-evaluation of the standalone Publication Boundary Validator prototype, documenting deliberate attack vectors, observed limitations, edge cases, and architectural boundaries.

---

## 1. Adversarial Red-Team Attack Vectors

To evaluate the resilience of the validator prototype beyond the standard test suite, we subjected it to eight adversarial testing vectors designed to provoke false negatives or false positives.

```
+-------------------------------------------------------------------------------+
|                       ADVERSARIAL RED-TEAM STRESS TEST                        |
+-------------------------------------------------------------------------------+
| Attack Vector                 | Result        | Detection Failure Mechanism   |
|-------------------------------|---------------|-------------------------------|
| 1. Euphemistic wording        | Partial Blind | Paraphrased internal concepts |
| 2. Disguised path as URL      | Bypassable    | Valid domain wrapper prefix   |
| 3. Renamed internal enums     | Blind         | Schema drift beyond ontology  |
| 4. Indirect review rebuttal   | Escapes Lint  | Subtle argumentative posture  |
| 5. Macro-obfuscated TeX       | Bypassable    | TeX token macro concatenation |
| 6. Code-switching edge cases  | Protected          | Handled via ASCII lookarounds |
| 7. Innocent technical usage   | Protected (Corpus) | Zero false positives observed across 40-fixture suite |
| 8. Cross-line boundary splits | Protected (Buffer) | Consecutive line buffering catches split phrases; hyphenation edge case |
+-------------------------------------------------------------------------------+
```

---

## 2. In-Depth Vulnerability Analysis

### 2.1 Euphemistic & Circumlocutory Internal Wording (False Negatives)
**Adversarial Excerpt:**
> *"本号の編集単位では、初期スクリーニングにて脱落した項目を除外し、公式発表に準ずる扱いへ留めた。"*

- **Observed Behavior**: The deterministic scanner passes this sentence.
- **Root Cause**:
  - `本 package` was paraphrased as `本号の編集単位`.
  - `ScreeningでDROP` was paraphrased as `初期スクリーニングにて脱落した`.
  - `一次資料として昇格させない` was paraphrased as `公式発表に準ずる扱いへ留めた`.
- **Mitigation**: Pure deterministic regex cannot maintain an exhaustive list of all Japanese stylistic variations for process operations. This requires the **Tier 2 Semantic Review Gate** via LLM analysis of paragraph subject and intent.

---

### 2.2 Disguised Raw Paths & Protocol Wrappers
**Adversarial Excerpt:**
```latex
@online{sample-leak,
  title = {Observation},
  url = {https://raw.githubusercontent.com/eariver/japanese-generative-ai-survey/main/sources/2026-W33/collectors/grok-x.json}
}
```
- **Observed Behavior**: Current `PROVENANCE_PATH_PATTERNS` matches `sources/2026-W33/collectors/grok-x.json` and flags `RULE-PATH-RAW-PROVENANCE`.
- **Bypass Variant**:
```latex
@online{encoded-leak,
  title = {Observation},
  url = {https://internal-proxy.local/view?path=Grok%5FX%5FSourseIntake%2FWeekly}
}
```
- **Observed Behavior**: URL-encoded path characters (`%5F` instead of `_`, `%2F` instead of `/`) escape raw string pattern matching.
- **Mitigation**: URL unquoting / normalization (`urllib.parse.unquote`) should precede pattern evaluation in future production hardening.

---

### 2.3 Schema Drift & Renamed Enums
**Adversarial Excerpt:**
> *"今回の報告は COMMUNITY_SIGNAL および EXPLORATORY_PROPOSAL として分類される。"*

- **Observed Behavior**: The scanner flags neither term.
- **Root Cause**: The scanner checks for known Core v2 enum literals (`SOCIAL_OBSERVATION`, `HOLD_OUT`, `PRIMARY_FACT`). If the upstream pipeline alters its schema nomenclature (e.g. Core v3 or edition-local renaming), lexical rules experience silent decay.
- **Mitigation**: Upstream schema files (`schemas/*.schema.json`) should be parsed at build time to dynamically generate forbidden token sets from the living schema definition.

---

### 2.4 Implicit Review Rebuttal & Editorial Stance
**Adversarial Excerpt:**
> *"先週まで議論されていた狭い枠組みにとらわれず、今回の紙面では全体的な波及効果を中心に据える。"*

- **Observed Behavior**: Classified as PASS by deterministic rules (unless strict mode flags `REVIEW_REQUIRED`).
- **Root Cause**: The prose adopts an argumentative rebuttal posture against previous editorial choices without using the explicit phrase `三つのFeatureだけではない` or `Architecture Review`.
- **Mitigation**: Must be handled by the **Optional Semantic Review Layer** (`SemanticPacket`) with the prompt instructing the model to evaluate whether the text contrasts against past editorial drafts.

---

### 2.5 LaTeX Macro Obfuscation
**Adversarial Excerpt:**
```latex
\def\evidenceid{D017}
この分析は \evidenceid に基づく。
```
- **Observed Behavior**: The scanner checks visible lines after stripping comments, but does not execute a full LaTeX macro expansion engine. Line 2 contains `\evidenceid` instead of `D017`, escaping lexical detection.
- **Mitigation**: For mission-critical gatekeeping, validation should run on the parsed TeX AST or preflight text extraction, or inspect rendered PDF text streams (as upstream does with `pypdf`).

---

### 2.6 Cross-Line Token Buffering vs Intra-Token Hyphenation
**Cross-Line Phrase Splitting (Protected)**:
```latex
今週の動向は三つのFeature
だけではない。
```
- **Current Behavior**: Protected. `PublicationScanner` implements consecutive-line lookahead buffering testing both spaced and unspaced joins, detecting phrases spanning across newlines.

**Intra-Token Hyphenation Edge Case (Known Limitation)**:
```latex
The candidates were assigned to HOLD-
OUT for subsequent validation.
```
- **Observed Behavior**: If an internal identifier itself is severed with an intra-token hyphen across a line break (`HOLD-\nOUT`), lexical token matchers fail unless preceded by a de-hyphenation pass.
- **Mitigation**: Add a de-hyphenation pre-pass (`re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)`) prior to lexical matching.

---

## 3. Residual Edge Cases & Planned Mitigations

| Vulnerability ID | Vulnerability Description | Current Status | Recommended Remediation |
|---|---|---|---|
| **VULN-001** | URL-encoded internal paths | Unmitigated in regex | Add `urllib.parse.unquote` URL normalization step in scanner |
| **VULN-002** | Circumlocutory Japanese editorial descriptions | Handled via Tier 2 Gate | Enforce Tier 2 Semantic Review Gate on all Synthesis sections |
| **VULN-003** | Upstream enum renaming (schema drift) | Manual rule updates | Bind rule patterns directly to `schemas/` enum definitions |
| **VULN-004** | Split TeX macros across token boundaries | Unmitigated without AST | Scan extracted text from compiled PDF in addition to `.tex` |
| **VULN-005** | Markdown table cell formatting | Partially mitigated | Ensure multiline Markdown table parsers normalize whitespace |
| **VULN-006** | Intra-token hyphenation across line breaks (`HOLD-\nOUT`) | Edge case | Add de-hyphenation normalization pass for hyphenated line breaks |
