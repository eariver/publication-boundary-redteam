# Publication Boundary Red-Team & Validator Prototype

An independent publication boundary analysis, regression fixture corpus, and standalone validator prototype for technical survey production pipelines.

Developed based on reader-facing publication regressions observed across `eariver/japanese-generative-ai-survey` (Issues #9, #400, #433, and central shared workflow authority #434).

---

## 1. Overview & Architecture

Automated AI survey generation pipelines (such as Survey Production Core v2) face a recurring defect: internal planning, editorial triage, evidence classification, and review-rebuttal arguments bleed into reader-facing publications.

This repository provides an independent, context-aware validator that enforces strict publication boundaries without relying on brittle global substring blacklists or requiring an LLM at runtime.

### Two-Tier Gate Architecture

```text
                           [ Target Publication File ]
                                       │
                                       ▼
                     [ Tier 1: Deterministic Invariant Gate ]
                     - Context-aware regex & lookarounds
                     - Repository path recognition
                     - Bibliography & tag validation
                     - Source-class claim boundary check
                                       │
                    ┌──────────────────┴──────────────────┐
                    │                                     │
           [ HARD_FAIL Detected ]                [ Clean or Suspicious ]
                    │                                     │
                    ▼                                     ▼
             GATE REJECTED                     Is REVIEW_REQUIRED present?
                                               ├── No  ──> GATE PASSED
                                               └── Yes ──> Dispatches SemanticPacket
                                                                  │
                                                                  ▼
                                              [ Tier 2: Optional Semantic Review ]
                                              - LLM / Human Editorial Reviewer
                                              - Validates context & intent
                                              - Emits SemanticReviewResponse
```

---

## 2. Directory Structure

```text
publication-boundary-redteam/
├── README.md                          # Project documentation
├── pyproject.toml                     # Package configuration & test setup
├── src/
│   └── publication_boundary/
│       ├── __init__.py                # Package exports
│       ├── models.py                  # Severity, FindingCategory, Finding, ValidationResult
│       ├── rules.py                   # Context-aware rules (terms, paths, rebuttals, bib)
│       ├── source_class.py            # Source-class Claim Boundary consistency rules
│       ├── semantic_gate.py           # DeterministicGate & SemanticReviewGate (two-tier)
│       ├── scanner.py                 # Core PublicationScanner engine
│       ├── report.py                  # Text, JSON, and Markdown report formatters
│       └── cli.py                     # Command-line entrypoint (publication-boundary-scan)
├── fixtures/
│   ├── weekly/
│   │   ├── bad/                       # 8 W33-derived failure fixtures with .meta.json
│   │   └── good/                      # 8 W33 clean baseline fixtures with .meta.json
│   ├── longform/
│   │   ├── bad/                       # 8 SP001-derived failure fixtures with .meta.json
│   │   └── good/                      # 8 SP001 clean baseline fixtures with .meta.json
│   └── ambiguous/                     # 8 false-positive resistant technical fixtures with .meta.json
├── tests/
│   ├── test_cli.py                    # CLI invocation and formatting tests
│   ├── test_fixtures.py               # Automated verification of all 40 fixtures
│   ├── test_models.py                 # Data models, serialization, and sorting tests
│   ├── test_properties.py             # Hypothesis property-based testing
│   ├── test_rules.py                  # Direct unit tests for all rule categories
│   ├── test_scanner.py                # Scanner engine and comment stripping tests
│   ├── test_semantic_gate.py          # Deterministic and Semantic gate tests
│   └── test_source_class.py           # Source class boundary validation tests
├── reports/
│   ├── failure-taxonomy.md            # RQ-1 & RQ-2 failure taxonomy and detection matrix
│   ├── upstream-analysis.md           # Causality trace for Issues #9, #400, #433, #434
│   ├── false-positive-analysis.md     # RQ-4 analysis of legitimate technical language
│   ├── integration-recommendations.md # Upstream integration roadmap & Issue #434 AC mapping
│   └── known-limitations.md           # Red-team adversarial self-evaluation of the validator
└── provenance/
    └── upstream-snapshot.md           # Pinned upstream HEAD SHA (c7a898889463b049dea4ee7337ee16ad5fbf3191)
```

---

## 3. Installation & Usage

### Installation

```bash
# Clone the repository
git clone https://github.com/eariver/publication-boundary-redteam.git
cd publication-boundary-redteam

# Install in editable mode with development dependencies
pip install -e ".[dev]"
```

### Command-Line Interface (CLI)

```bash
# Scan a single TeX or Markdown file
publication-boundary-scan surveys/weekly/2026-W33/main.tex --profile weekly

# Scan a directory with JSON output
publication-boundary-scan fixtures/longform/bad/ --format json

# Strict mode: fails on REVIEW_REQUIRED in addition to HARD_FAIL
publication-boundary-scan draft.tex --strict

# Check Claim Boundary consistency against an explicit source class
publication-boundary-scan section.tex --source-class RESEARCH_PAPER
```

### Python API

```python
from publication_boundary import PublicationScanner, DocumentProfile, SourceClass

scanner = PublicationScanner()

# Scan in-memory text
result = scanner.scan_text(
    text=r"\section{Brief} 今週の動向は三つのFeatureだけではない。",
    profile=DocumentProfile.WEEKLY_MAGAZINE,
)

print(f"Passed: {result.passed}")
for finding in result.findings:
    print(f"[{finding.severity.value}] Line {finding.line_number}: {finding.message}")
```

---

## 4. Test Suite & Verification

The test suite includes 76 automated tests covering unit rules, integration scanning, property-based invariants with `hypothesis`, and all 40 machine-readable fixtures.

```bash
# Run pytest with test coverage
pytest --cov=publication_boundary --cov-report=term-missing
```

### Test Results Summary
- **Tests Executed**: 76
- **Tests Passed**: 76 (100%)
- **Test Failures**: 0
- **Code Coverage**: 98% across `src/publication_boundary`
- **Execution Time**: ~0.9s

---

## 5. Summary of Key Research Findings

1. **The Root Cause in Upstream Pipeline**:
   In `japanese-generative-ai-survey`, assembly scripts (`survey_weekly_semantic_publication_v2.py`) actively enforced the verbatim copying of internal review rebuttals (`profile_synthesis.current_interpretation`) into final publication summary paragraphs (lines 117–118, 387–388), and hardcoded internal classification tags into BibTeX references (line 74).
2. **The Japanese-English Code-Switching Boundary Defect**:
   Python's regex engine treats both ASCII alphanumeric characters and Japanese characters (Kanji, Hiragana, Katakana) as Unicode `\w`. Standard word boundaries `\b` fail when ASCII tokens directly border Japanese particles (e.g. `HOLD_OUTとして`, `D017および`). This was solved using ASCII lookaround delimiters `(?<![a-zA-Z0-9_])` and `(?![a-zA-Z0-9_])`.
3. **Context-Aware Preservation of Legitimate Technical Vocabulary**:
   By analyzing syntactic collocations, the validator permits legitimate engineering terms (`software architecture`, `empirical evidence`, `candidate model`, `packet drop`) with 0% false positives, while detecting internal pipeline state leaks with 100% precision.