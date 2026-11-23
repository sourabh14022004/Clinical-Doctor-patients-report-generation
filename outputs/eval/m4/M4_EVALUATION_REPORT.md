# M4 Evaluation & Optimization Report

> **Scope warning:** This is a preliminary academic evaluation of structured field agreement, not clinical validation or diagnostic accuracy. Do not use it for clinical decisions.

## 1. Dataset coverage

- Ground-truth records: **5**
- Generated forms: **5**
- Matching case pairs: **4**
- Unmatched reference records: **1**
- Unmatched generated forms: **1**
- Assertion fields mapped per matched case: **14**

## 2. Four-state assertion agreement

- Scorable fields (gold not UNKNOWN): **56**
- Exact matches: **22**
- Exact four-state accuracy: **39.3%**
- Prediction coverage (non-UNKNOWN predictions): **39.3%**
- Accuracy among non-abstained predictions: **100.0%**
- Model abstentions on scorable fields: **34**
- Gold class support: `{"ABSENT": 54, "PRESENT": 2}`
- PRESENT gold support by field: `{"Family history of cancer": 2}`
- PRESENT sensitivity: **100.0%** on 2 PRESENT reference fields
- Important: the PRESENT examples are not positive symptom examples; all 11 symptom reference fields are ABSENT in this dataset.

### Per-class precision, recall and F1

| Class | Gold support | Predicted count | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| PRESENT | 2 | 2 | 100.0% | 100.0% | 100.0% |
| ABSENT | 54 | 20 | 100.0% | 37.0% | 54.1% |
| POSSIBLE | 0 | 0 | N/A | N/A | N/A |
| UNKNOWN | 0 | 34 | 0.0% | N/A | 0.0% |
- Macro F1 over classes represented in the reference set: **77.0%** (class support is highly imbalanced).

### Confusion matrix (rows = reference, columns = prediction)

| Gold \ Predicted | PRESENT | ABSENT | POSSIBLE | UNKNOWN |
|---|---:|---:|---:|---:|
| PRESENT | 2 | 0 | 0 | 0 |
| ABSENT | 0 | 20 | 0 | 34 |
| POSSIBLE | 0 | 0 | 0 | 0 |
| UNKNOWN | 0 | 0 | 0 | 0 |

### Per-field results

| Field | Scorable support | Exact matches | Exact agreement | Prediction coverage | Abstentions |
|---|---:|---:|---:|---:|---:|
| Family history of cancer | 4 | 4 | 100.0% | 100.0% | 0 |
| Past tobacco or alcohol use | 4 | 2 | 50.0% | 50.0% | 2 |
| Current tobacco use | 4 | 0 | 0.0% | 0.0% | 4 |
| Unexplained weight loss | 4 | 3 | 75.0% | 75.0% | 1 |
| Persistent fever or fatigue | 4 | 3 | 75.0% | 75.0% | 1 |
| Non-healing ulcer or wound | 4 | 1 | 25.0% | 25.0% | 3 |
| Lump or swelling | 4 | 1 | 25.0% | 25.0% | 3 |
| Persistent pain | 4 | 1 | 25.0% | 25.0% | 3 |
| Bleeding from any site | 4 | 1 | 25.0% | 25.0% | 3 |
| Known chronic illness | 4 | 3 | 75.0% | 75.0% | 1 |
| Difficulty opening mouth | 4 | 1 | 25.0% | 25.0% | 3 |
| White or red oral patch | 4 | 1 | 25.0% | 25.0% | 3 |
| Oral ulcer over two weeks | 4 | 1 | 25.0% | 25.0% | 3 |
| Difficulty chewing or swallowing | 4 | 0 | 0.0% | 0.0% | 4 |

### Evidence / abstention audit

- Fields with both matched question and non-empty answer evidence: **22**
- Fields with neither matched question nor answer evidence: **34**
- UNKNOWN predictions that nevertheless had question/answer evidence: **0**
- In this run, an UNKNOWN prediction is therefore distinguishable from an explicit negative: it is an abstention where the form-population step did not identify a usable answer.

## 3. Numeric field evaluation

| Field | Support | MAE | Exact agreement | Within tolerance | Tolerance |
|---|---:|---:|---:|---:|---:|
| Age | 4 | 0.000 | 100.0% | 100.0% (4/4) | 0.0 |
| Weight (kg) | 3 | 0.000 | 100.0% | 100.0% (3/3) | 2.0 |

## 4. NER and assertion evaluation

**Not yet available.** No independently annotated case is marked annotation_status='complete'. NER and assertion performance metrics cannot yet be calculated.

## 5. Baseline versus M3 output audit

No baseline forms directory supplied; run with --baseline-forms-dir to add a descriptive state-distribution audit.

## 6. Failure analysis and interpretation

- UNKNOWN reference labels are excluded from classification denominators.
- A predicted UNKNOWN for a known reference label is counted as an abstention and as a non-match; it is never converted to ABSENT.
- The supplied symptom reference fields contain only ABSENT labels. This set cannot estimate positive symptom recall/sensitivity or performance on POSSIBLE cases.
- Field-level errors are saved separately in `field_level_comparisons.json` using anonymized case labels and assertion states only.
- NER metrics require independent span/type/assertion annotation; model-generated entities must not be reused as gold labels.

## 7. Limitations and next steps

- The supplied reference set is small and only matching case IDs are compared.
- The 11 symptom fields in the supplied reference records are all ABSENT; positive-case sensitivity cannot be estimated from this set.
- NER precision/recall/F1 are unavailable until independent gold annotations are completed.
- Structured-form agreement does not establish clinical safety or diagnostic performance.
- Every generated clinical record requires qualified human review.

### Required next steps

1. Resolve unmatched reference/form IDs before expanding the benchmark.
2. Have two reviewers independently annotate a representative set of transcript entity spans and assertions; adjudicate disagreements.
3. Add positive and uncertain examples, not only negative symptom examples.
4. Inspect every field mismatch against the source audio and transcript.
5. Run the same fixed test set before and after each optimization, and report support alongside all metrics.
