# M3 Implementation Record — Industry Track

**Project:** Clinical Speech-to-Text and Structured Report Generation  
**Milestone:** M3 — Model Development  
**Implementation status:** Core changes implemented; clinical review and annotation are still required.

## Objective

Improve the existing consultation-processing pipeline so it maps transcript answers into a screening form without turning missing information into negative findings or inventing patient information.

## Changes completed

### 1. Question-and-answer segmentation

- Improved segment grouping when automatic speech recognition omits a question mark.
- Added support for inline question-and-answer segments.
- Kept the source question and answer for every mapped field.
- Tightened question detection to rely on question punctuation or question-start wording, reducing accidental treatment of an answer as a new question.

### 2. Four-state clinical assertion handling

The form schema now supports:

| State | Interpretation | JSON `reported` |
|---|---|---|
| `PRESENT` | Explicitly affirmed | `true` |
| `ABSENT` | Explicitly denied | `false` |
| `POSSIBLE` | Uncertain / suspected | `null` |
| `UNKNOWN` | Unanswered, unclear, or not established | `null` |

Downstream code must preserve null rather than convert it to false.

### 3. Removal of unsupported defaults

The previous implementation could derive name and sex from case identifiers, insert patient-specific weight and height values, default height to a fixed value, and fill unmeasured pulse, respiratory rate and blood pressure as "Normal". These fallbacks were removed. Missing fields remain null or UNKNOWN.

BMI is calculated only when the available height includes a supported unit. A bare number is preserved without assigning an unverified unit.

### 4. Assertion scope improvements

- Entity assertion context is bounded by sentence/clause separators.
- Nearby unrelated negation is less likely to transfer to another entity.
- Contrastive conjunctions such as "but" reset the local negation scope.
- Mentions inside question wording are classified as UNKNOWN rather than automatically PRESENT.
- Uncertainty cues can produce POSSIBLE.

### 5. Dashboard and data export

- Form rendering now distinguishes explicit negative answers from unknown answers.
- Unreported vitals display as not reported, not normal.
- The validation view uses the actual field match value and actual per-case agreement percentage rather than hardcoded 100% labels.
- The exporter discovers generated case IDs from output files and no longer substitutes a different scanned form when a matching image is unavailable.

### 6. Data protection

`.gitignore` now excludes local audio, scanned clinical documents, generated outputs, notebook files and aggregated dashboard data. These assets can contain personal or sensitive clinical information and should not be pushed to a public repository.

## Verification

The following checks were completed:

| Verification | Result |
|---|---|
| Python compile check for project modules | Passed |
| JavaScript syntax check for dashboard | Passed |
| Python unit tests | 11 passed |
| End-to-end pipeline using existing local transcripts | Completed for 5 cases |
| Generated form schema | 5 schema-v2 forms |
| Extraction evidence map | Present in all 5 generated forms |
| Dashboard data export | 5 cases exported |

The regression tests cover question segmentation, four-state assertions, missing-value handling, removal of case-ID-based values, BMI unit handling, family-history relative answers, local negation scope and question-mention handling.

A local execution audit of the five supplied transcript cases showed 55 general/oral symptom fields represented as 17 ABSENT and 38 UNKNOWN, with no PRESENT or POSSIBLE labels in those fields. This is an output audit only, not a model-performance result; the UNKNOWN count indicates that question coverage and answer linking must be checked manually and improved in M4.

## Benchmark caveat

The repository's old evaluator is retained only as a legacy comparator. It currently reports 43.1% binary field agreement (31 of 72 compared fields) on the cases where the reference and generated form IDs match. This must **not** be described as clinical accuracy or model accuracy because:

1. The comparator does not model all four assertion states and can interpret UNKNOWN as a negative.
2. It evaluates only four matched case IDs; the supplied folders contain a ground-truth record without a corresponding generated form and a generated case without a corresponding ground-truth record.
3. It does not measure entity-level precision, recall or F1, and it is not an independently adjudicated clinical evaluation.

The pipeline and report now display a warning for this legacy result. M4 must replace it with a tri-state-aware evaluation and resolve or explicitly document the unmatched case pair.

## Remaining M3 review tasks

- Manually inspect at least one full consultation end to end with an authorized reviewer.
- Verify that each field is linked to the correct question and answer.
- Confirm that local ontology IDs and preferred terms are valid for the intended terminology release.
- Review code-mixed and low-confidence ASR examples.
- Confirm consent, de-identification and institutional approval for any data used in a demo or submission.

## Reproduction commands

```bash
python -m unittest discover -s tests -v
python src/pipeline.py
python src/export_web_data.py
python -m http.server 8080 --directory web
```

This system is a research prototype. All generated forms require qualified human review and must not be used for diagnosis or treatment decisions.
