# M4 Implementation Record — Evaluation & Optimization

**Project:** Clinical Speech-to-Text and Structured Report Generation  
**Track:** Industry Track  
**Milestone:** M4 — Evaluation & Optimization  
**Status:** Evaluator implemented; preliminary benchmark completed; independent NER annotations pending.

## 1. Work completed

- Added `src/evaluate_m4.py` for four-state field agreement, confusion matrices, per-class precision/recall/F1, per-field support, prediction coverage, abstention rate, evidence provenance, and numeric error metrics.
- Added an independent NER annotation workflow: `src/prepare_annotations.py` generates local templates; `evaluate_m4.py` computes exact span/type metrics only for templates marked complete.
- Updated `src/pipeline.py` to run M4 evaluation after form generation while retaining the legacy comparator with an explicit warning.
- Added targeted M3 question-mapping improvements based on error analysis: ASR phrasing "cancer at home" is recognized as a family-history prompt; the explicit diabetes/BP/sugar history response is reused for the known-chronic-illness screening field with evidence retained.
- Added automated tests for four-state metric semantics, UNKNOWN abstention handling, normalization, exact-span NER scoring, and the two question-mapping improvements.
- Updated README and pipeline documentation with reproducible commands, data limitations and privacy requirements.

## 2. Verification

| Check | Result |
|---|---|
| Full Python unit test suite | 23 passed |
| Python source compilation | Passed |
| NER annotation template generation | 5 local templates created in a smoke test |
| M4 structured-field evaluation | 4 matching case pairs evaluated |
| M4 NER evaluation | Correctly reports unavailable until independent gold annotations are complete |
| Evidence audit | 34 / 34 UNKNOWN predictions had no matched question-and-answer evidence |

## 3. Preliminary evaluation result

- Ground-truth records: 5.
- Generated forms: 5.
- Matching case pairs: 4; one reference and one generated form remain unmatched.
- Assertion fields mapped per pair: 14.
- Scorable assertion fields: 56.
- Exact four-state matches after optimization: 22 / 56 (39.3%).
- Prediction coverage: 22 / 56 (39.3%).
- Abstentions: 34 / 56 (60.7%).
- Selective accuracy among the 22 non-UNKNOWN predictions: 22 / 22 (100.0%) on this small sample.
- Both PRESENT gold examples are family-history fields. The 11 symptom fields in the reference data are all ABSENT; positive symptom sensitivity is not estimable.
- Age exact agreement: 4 / 4. Weight exact agreement: 3 / 3 available values.
- NER metrics: unavailable until independent annotations are completed.

See `docs/M4_PRELIMINARY_EVALUATION_RESULTS.md` for per-field results and caveats.

## 4. Baseline output-state audit

Across the five forms (70 mapped assertion slots), the original outputs had 68 ABSENT and 2 PRESENT states. The M3/M4 outputs have 23 ABSENT, 2 PRESENT and 45 UNKNOWN states. This is a descriptive audit, not an accuracy comparison. It shows the conservative change from default negative labels to UNKNOWN when no answer evidence is found.

## 5. Reproduction

Run the tests:

```bash
python -m unittest discover -s tests -v
```

Run the complete pipeline and M4 evaluation:

```bash
python src/pipeline.py
```

Run M4 evaluation separately:

```bash
python src/evaluate_m4.py
```

Prepare local NER annotation templates:

```bash
python src/prepare_annotations.py
```

Annotation templates contain transcript text and may contain personal or sensitive clinical information. Keep them local, do not commit them, and use only with the appropriate consent and institutional approval. Use two independent reviewers and adjudicate disagreements before setting `annotation_status` to `complete`.

## 6. Limitations and next work

1. Resolve the unmatched reference/form IDs; do not pair cases based only on filename order or similar names.
2. Expand the dataset with independently reviewed positive, negative and uncertain symptom examples.
3. Complete entity span/type/assertion annotations before reporting NER precision, recall or F1.
4. Inspect ASR transcription quality and every Q/A-linked form value against source audio.
5. Continue optimizing field coverage, but do not replace UNKNOWN with ABSENT merely to increase agreement.
6. Treat generated clinical forms as drafts requiring qualified human review; this prototype is not a diagnostic or treatment system.
