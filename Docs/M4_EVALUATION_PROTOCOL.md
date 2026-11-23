# M4 Evaluation & Optimization Protocol

**Project:** Clinical Speech-to-Text and Structured Report Generation  
**Track:** Industry Track  
**Milestone:** M4 — Evaluation & Optimization

## 1. Evaluation goals

M4 separates three different questions that must not be conflated:

1. **Clinical form agreement:** Do generated four-state form fields agree with structured reference records?
2. **NER performance:** Are clinically relevant entity spans and entity types extracted correctly against independent human annotations?
3. **Assertion performance:** Are PRESENT, ABSENT, POSSIBLE and UNKNOWN labels correct, both at the form-field level and for matched entity mentions?

The supplied records currently support only a preliminary form-field comparison. NER precision/recall/F1 cannot be calculated until independent span annotations are completed.

## 2. Four-state label definitions

| Label | Definition | Example |
|---|---|---|
| PRESENT | Explicitly affirmed in the answer | "Yes, I have persistent pain" |
| ABSENT | Explicitly denied | "No, I do not have persistent pain" |
| POSSIBLE | Uncertain or suspected | "It may be a symptom" |
| UNKNOWN | Not answered, unclear, or not established | No answer was captured |

A missing or UNKNOWN prediction is never converted to ABSENT. Gold UNKNOWN values are excluded from the classification denominator because they do not establish a reference class. A model prediction of UNKNOWN when the gold label is known is counted as an abstention and as a non-match. Both coverage and selective accuracy are reported so abstention cannot hide extraction failures.

## 3. Structured reference fields

The evaluation currently maps 14 assertion fields:

- Family history of cancer.
- Past tobacco or alcohol use.
- Current tobacco use.
- Seven general cancer screening fields.
- Four oral cancer screening fields.

It additionally compares age by exact agreement and weight using mean absolute error and a declared 2 kg tolerance. The tolerance is a reporting convention inherited from the legacy comparison, not a clinical guideline.

The evaluator reports:

- Number of reference files, generated forms and matching case pairs.
- Explicitly scorable field support.
- Exact four-state agreement.
- Prediction coverage and abstention count.
- Per-class precision, recall and F1.
- Four-by-four confusion matrix.
- Per-field support and agreement.
- Numeric MAE, exact agreement and tolerance agreement.

## 4. NER human-annotation protocol

The model's own predictions must never be copied into the gold annotation file as ground truth.

### Entity taxonomy

Use the current code taxonomy as a starting point:

`PATIENT_NAME`, `AGE`, `DOB`, `EDUCATION`, `OCCUPATION`, `MARITAL_STATUS`, `ADDRESS`, `CONTACT_PHONE`, `FAMILY_INCOME`, `HEALTH_INSURANCE`, `WEIGHT`, `HEIGHT`, `SIGN_SYMPTOM`, `DIAGNOSIS`, `CANCER_TYPE`, `ORAL_SIGN`, `RISK_FACTOR_TOBACCO`, `RISK_FACTOR_ALCOHOL`, `DIETARY_HABIT`, `PHYSICAL_ACTIVITY`, `FAMILY_MEMBER`, `DURATION`.

Reviewers may propose a taxonomy change, but document it and use the same version for all evaluated systems.

### Annotation format

Run:

```bash
python src/prepare_annotations.py
```

This creates one local file per NER output in `outputs/annotations/`. Each template has `annotation_status: "pending"` and an empty `annotations` list. Complete the fields from the transcript and source recording, not by copying model predictions:

```json
{
  "start": 120,
  "end": 134,
  "text": "persistent pain",
  "entity_type": "SIGN_SYMPTOM",
  "assertion": "PRESENT"
}
```

Offsets are zero-based and end-exclusive character offsets into `transcript_text`. The `text` must equal the transcript slice at `[start:end]`. Use one reviewer to annotate, a second reviewer to independently review, and adjudicate disagreements. Only after adjudication set `annotation_status` to `complete`.

Then run:

```bash
python src/evaluate_m4.py
```

Entity extraction uses exact span-and-type matching. Assertion metrics are calculated only on exact entity matches. This is intentionally strict; partial/overlapping span scoring can be added as a separately labelled secondary metric.

## 5. Controlled optimization experiments

Keep the test set and annotation version fixed when comparing baseline and optimized implementations. Recommended experiments:

| Experiment | Baseline | Optimized | Primary measure |
|---|---|---|---|
| E1: Question-answer linking | Original Q/A segmentation | M3 turn grouping and source evidence | Field assertion agreement and coverage |
| E2: Assertion scope | Previous assertion heuristic | Clause-bounded four-state handling | Four-state confusion matrix |
| E3: Missing data | Legacy false/default values | UNKNOWN-preserving form schema | Abstention rate and unsupported-default audit |
| E4: Entity extraction | Existing pattern/lexicon rules | Curated pattern improvements | NER exact-span/type P/R/F1 after annotation |

Do not claim an improvement in accuracy unless measured against the same independently reviewed gold set. The baseline output-state audit is descriptive only.

## 6. Current dataset limitations

The current package has five reference records and five generated forms, but only four file-ID pairs match. Do not silently pair records based on name similarity or order. Resolve the mismatched identifiers with the project supervisor or document the exclusion.

All 11 symptom labels in the supplied reference records are ABSENT. Therefore this set cannot estimate recall/sensitivity for PRESENT symptom cases or evaluate POSSIBLE examples. A larger, balanced, independently reviewed sample is required.

The source reference records are structured forms, not independent transcript-span annotations. They can support field agreement but cannot be used as gold entity spans.

## 7. Data protection and human review

Audio, transcripts, forms and annotation templates may contain personal or sensitive clinical information. They are excluded from version control by `.gitignore`. Do not push them to a public repository. Confirm institutional authorization, consent and de-identification before sharing or evaluating these records.

This project is an academic prototype. All outputs require qualified human review and must not be used for diagnosis, treatment or autonomous clinical decisions.
