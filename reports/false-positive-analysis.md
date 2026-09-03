# False Positive Analysis & Context-Aware Disambiguation

This report addresses Research Question **RQ-4**, examining how to protect publication boundaries without naively banning legitimate computer science and technical terminology.

---

## 1. The Naive Blacklist Pitfall

In early iterations of upstream survey tooling (e.g. Issue #9's `editorial_prose_guard.py`), authors attempted to stop leakage using global substring blacklists. However, AI and software engineering literature naturally relies on words that overlap with production pipeline terms:
- `evidence`
- `architecture`
- `candidate`
- `drop`
- `screening`

A naive blacklist creates two failure modes:
1. **False Positives**: Genuine technical prose (`software architecture`, `empirical evidence`, `candidate model`) is blocked, frustrating authors and causing editors to disable the linter entirely.
2. **False Negatives**: Authors or LLMs bypass the naive string check through code-switching, synonyms, or rephrasing (`本 package`, `受理されたEvidence`, `D017`), while the underlying process leakage persists.

---

## 2. In-Depth Term Analysis & Disambiguation Matrix

### 2.1 "Evidence"

| Context Type | Example Phrases | Verdict | Rationale & Handling |
|---|---|---|---|
| **Legitimate Technical Prose** | `empirical evidence`, `experimental evidence`, `concrete evidence of scaling`, `evidence from benchmarks`, `statistical evidence` | **PASS** | Refers to scientific or empirical proof supporting an author's technical claim. Allowed unconditionally. |
| **Pipeline Metadata Leak** | `Evidence Card`, `Core v2 Evidence: VERIFIED`, `accepted Evidence source`, `受理されたEvidence`, `Evidence上の未解決境界` | **HARD_FAIL** | Refers to internal data records (`Evidence Card`), pipeline status, or verification tags. |

#### Disambiguation Strategy:
- Match `Evidence` only when collocated with pipeline terms (`Card`, `Core v2 Evidence:`, `accepted Evidence`, `受理された`, `未解決境界`).
- Never match standalone `evidence` when accompanied by prepositions (`evidence of`, `evidence for`, `evidence from`) or adjectives (`empirical`, `experimental`, `concrete`).

---

### 2.2 "Architecture"

| Context Type | Example Phrases | Verdict | Rationale & Handling |
|---|---|---|---|
| **Legitimate Technical Prose** | `software architecture`, `system architecture`, `transformer architecture`, `MoE architecture`, `model architecture`, `hardware architecture` | **PASS** | Describes the technical design of neural networks, software frameworks, or distributed compute systems. |
| **Pipeline Metadata Leak** | `承認済みArchitecture`, `approved Architecture says`, `Architecture requires that`, `Architectureは...を観察軸としている` | **HARD_FAIL** | Refers to the internal issue planning document (`architecture-v2.json`) or quotes editorial directives. |

#### Disambiguation Strategy:
- Collocation lookaheads identify imperative verbs (`requires`, `specifies`, `defines`) or Japanese honorific/management prefixes (`承認済みArchitecture`, `Architectureの指示`).
- Compound terms ending in `architecture` (`software architecture`, `neural architecture`) are explicitly preserved.

---

### 2.3 "Candidate"

| Context Type | Example Phrases | Verdict | Rationale & Handling |
|---|---|---|---|
| **Legitimate Technical Prose** | `candidate model`, `candidate tokens`, `top candidate solution`, `candidate architecture`, `candidate configuration` | **PASS** | Standard machine learning terminology for beam search, speculative decoding, model evaluation, or hyperparameter selection. |
| **Pipeline Metadata Leak** | `Candidate Selection`, `Candidate Inventory`, `candidate queue`, `一次資料として昇格させない` | **HARD_FAIL** | Refers to the editorial pipeline's candidate tracking matrix (`candidate-matrix-v2.json`) or evidence promotion. |

#### Disambiguation Strategy:
- Target specific pipeline compound nouns: `Candidate Selection`, `Candidate Inventory`.
- Permit all engineering uses modifying nouns (`candidate model`, `candidate tokens`).

---

### 2.4 "Drop"

| Context Type | Example Phrases | Verdict | Rationale & Handling |
|---|---|---|---|
| **Legitimate Technical Prose** | `packet drop`, `voltage drop`, `accuracy drop`, `performance drop`, `drop out`, `drop in loss` | **PASS** | Standard computer systems, networking, and machine learning terminology. |
| **Pipeline Metadata Leak** | `ScreeningでDROP`, `Fresh W33 ScreeningでDROPとなった` | **HARD_FAIL** | Refers to the pipeline intake disposition discarding an evidence candidate. |

#### Disambiguation Strategy:
- Match `DROP` only when collocated with pipeline stages (`ScreeningでDROP`, `DROP disposition`).
- Physical/metric drops (`packet drop`, `accuracy drop`) are never matched.

---

### 2.5 "Screening"

| Context Type | Example Phrases | Verdict | Rationale & Handling |
|---|---|---|---|
| **Legitimate Technical Prose** | `medical screening test`, `screening compound`, `initial screening of participants` | **PASS** | Domain applications of machine learning models in healthcare, chemistry, or user studies. |
| **Pipeline Metadata Leak** | `Fresh W33 Screening`, `Screening Index`, `Screening result`, `Screening stage` | **HARD_FAIL** | Refers to the internal Core v2 candidate screening phase (`screening-result.json`). |

#### Disambiguation Strategy:
- Require pipeline stage qualifiers (`Fresh <Edition> Screening`, `Screening Index`).

---

## 3. Linguistic & Boundary Engineering in Mixed Japanese/English

A critical discovery during this study was the interaction between Python's regex engine (`\b`) and mixed Japanese-English text.

### The ASCII Boundary Problem
In Python 3's Unicode regex:
- ASCII alphanumeric characters (`[a-zA-Z0-9]`) are `\w`.
- Japanese Kanji, Hiragana, and Katakana characters (e.g., `あ`, `漢`, `ア`) are **also** classified as `\w`.

Consequently:
- In `D017および`, between `7` (`\w`) and `お` (`\w`), **there is no word boundary `\b`**.
- In `HOLD_OUTとして`, between `T` (`\w`) and `と` (`\w`), **`\b` fails**.

A naive pattern `r"\bHOLD_OUT\b"` completely misses `HOLD_OUTとして` in Japanese sentences.

### Solution: ASCII Lookaround Boundaries
By replacing `\b` with negative lookarounds targeting ASCII identifiers:
```python
(?<![a-zA-Z0-9_])HOLD_OUT(?![a-zA-Z0-9_])
(?<![a-zA-Z0-9_])D017(?![a-zA-Z0-9_])
```
The regex correctly matches when the token is directly adjacent to Japanese particles (`として`, `の`, `で`, `から`), while preventing false matches on longer identifiers (e.g. `HOLD_OUT_REVISED` or `D0178`).

---

## 4. Empirical Validation

All 8 ambiguous fixtures in `fixtures/ambiguous/` were tested against the validator prototype:
1. `amb_01_software_architecture.tex` -> **PASS (0 findings)**
2. `amb_02_empirical_evidence.tex` -> **PASS (0 findings)**
3. `amb_03_candidate_models.tex` -> **PASS (0 findings)**
4. `amb_04_packet_drop.tex` -> **PASS (0 findings)**
5. `amb_05_transformer_architecture.tex` -> **PASS (0 findings)**
6. `amb_06_concrete_evidence_of_scaling.tex` -> **PASS (0 findings)**
7. `amb_07_top_candidate_evaluation.tex` -> **PASS (0 findings)**
8. `amb_08_medical_screening_test.tex` -> **PASS (0 findings)**

This confirms that the context-aware rules achieve zero false positives across the tested ambiguous technical corpus and fixture suite.
