# M4 Preliminary Evaluation Results

**Evaluation version:** M4-1.0  
**Dataset:** Supplied local project records  
**Status:** Preliminary; not clinical validation

## Coverage and agreement

| Measure | Result |
|---|---:|
| Ground-truth records | 5 |
| Generated forms | 5 |
| Matching case pairs | 4 |
| Assertion fields per matched case | 14 |
| Scorable assertion fields | 56 |
| Exact four-state matches | 22 / 56 |
| Exact four-state agreement | 39.3% |
| Prediction coverage | 39.3% |
| Abstentions (predicted UNKNOWN) | 34 |
| Selective accuracy among non-UNKNOWN predictions | 100.0% (22 / 22) |

All 34 UNKNOWN predictions had no matched question-and-answer evidence in the generated evidence map. They were counted as abstentions/non-matches, not as ABSENT.

## Class distribution

| Reference class | Support |
|---|---:|
| PRESENT | 2 |
| ABSENT | 54 |
| POSSIBLE | 0 |
| UNKNOWN | 0 |

Both PRESENT reference fields were family-history fields. All 11 symptom reference fields were ABSENT. Consequently, these data cannot estimate positive symptom recall/sensitivity or performance on POSSIBLE cases.

## Per-field overview

| Field | Support | Exact matches | Agreement |
|---|---:|---:|---:|
| Family history of cancer | 4 | 4 | 100.0% |
| Past tobacco or alcohol use | 4 | 2 | 50.0% |
| Current tobacco use | 4 | 0 | 0.0% |
| Unexplained weight loss | 4 | 3 | 75.0% |
| Persistent fever or fatigue | 4 | 3 | 75.0% |
| Non-healing ulcer or wound | 4 | 1 | 25.0% |
| Lump or swelling | 4 | 1 | 25.0% |
| Persistent pain | 4 | 1 | 25.0% |
| Bleeding from any site | 4 | 1 | 25.0% |
| Known chronic illness | 4 | 3 | 75.0% |
| Difficulty opening mouth | 4 | 1 | 25.0% |
| White or red oral patch | 4 | 1 | 25.0% |
| Oral ulcer over two weeks | 4 | 1 | 25.0% |
| Difficulty chewing or swallowing | 4 | 0 | 0.0% |

## Numeric fields

| Field | Support | MAE | Exact agreement |
|---|---:|---:|---:|
| Age | 4 | 0 | 4 / 4 |
| Weight (kg) | 3 | 0 | 3 / 3 |

Weight comparison additionally records a 2 kg tolerance, inherited from the prior comparator. Exact agreement was already observed in the three available matched cases.

## Optimization implemented after error analysis

Two evidence-backed question-mapping issues were fixed:

1. Family-history questions phrased by ASR as whether anyone got cancer "at home" are now recognized as family-history prompts.
2. The explicit diabetes / blood-pressure / sugar medical-history answer is reused for the screening field "known chronic illness (DM/HTN/TB)", with its question and answer evidence retained.

The combined result improved from **19/56 (33.9%)** exact field matches before these two changes to **22/56 (39.3%)** afterwards. This is a result on the same four matched cases and the same reference files; it is not a generalization claim. The regression suite increased from 20 to **22 passing tests**.

## Baseline output-state audit

Across the five generated forms (70 assertion slots):

| Version | ABSENT | PRESENT | UNKNOWN |
|---|---:|---:|---:|
| Earlier baseline outputs | 68 | 2 | 0 |
| M3/M4 optimized outputs | 23 | 2 | 45 |

This is descriptive, not an accuracy comparison. The optimized pipeline preserves UNKNOWN when it cannot find a matched question and answer rather than forcing a negative.

## NER metrics not yet available

The reference JSON files provide structured form values, not annotated entity spans. Entity precision, recall and F1 must not be calculated by treating the model's own outputs as gold labels. The repository now includes a local annotation-template generator and an evaluator for exact span/type matching; independent review and adjudication are still required.

## Interpretation

The main failure mode on this dataset is **coverage**, not incorrect polarity among answers the pipeline actually extracted. It found 22 fields with explicit question/answer evidence and matched those 22 reference states, while 34 fields remained unfilled. The supplied reference set is small and the symptom labels are all negative, so further evaluation requires additional cases with independently confirmed PRESENT, ABSENT and POSSIBLE examples.
