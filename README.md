# Clinical Speech-to-Text and Structured Report Generation

An academic **prototype** for processing Hindi / code-mixed clinical consultation audio, generating Hindi transcription and English translation, extracting selected clinical concepts from the English transcript, and mapping question-and-answer responses into a structured screening form.

> **Safety boundary:** This is a research and demonstration prototype, not a diagnostic system or a production electronic health record. Generated content must be reviewed and corrected by a qualified clinician before any clinical use. Do not use it to make diagnosis or treatment decisions.

## Current implementation

1. **Speech processing:** `whisper-cli` generates a Hindi transcript and an English translation from the source audio.
2. **Question/answer alignment:** Transcript segments are grouped into question-and-answer turns using question wording and punctuation heuristics.
3. **Clinical information extraction:** `src/medical_ner.py` uses curated regular expressions and a terminology dictionary to identify selected symptoms, diagnoses, risk factors, family relationships and duration mentions. It is a **rule/lexicon-based extractor**, not a separately trained neural NER model.
4. **Assertion detection:** Local context rules classify entity mentions as `PRESENT`, `ABSENT`, `POSSIBLE` or `UNKNOWN`. Mentions inside clinician questions are not automatically treated as positive findings.
5. **Concept mapping:** Selected English terms are mapped to locally defined SNOMED-CT / UMLS identifiers. The mappings are a prototype dictionary and must be clinically and terminologically validated before deployment.
6. **Form generation:** `src/form_populator.py` maps aligned answers into a structured JSON form and Markdown summary. Missing answers stay `null` / `UNKNOWN`; the software does not infer sex, measurements or other demographics from case IDs.
7. **Hindi↔English span alignment:** `src/alignment.py` projects every English entity back to the Hindi transcript (cross-lingual entity projection). It anchors on Whisper timestamps to find the matching Hindi segment, then finds the Hindi word span with a phonetic consonant-skeleton matcher that tolerates noisy ASR spellings (कैंसर / कानसर / खंसर). It also detects and skips Whisper hallucination loops.
8. **Dashboard:** `web/` renders local transcripts, extracted entities (with their Hindi spans), relations and generated forms. `web/annotate.html` is a click-to-annotate tool for building NER gold data.
9. **Evaluation suite:** four-state form evaluation, NER P/R/F1 (strict and lenient) with inter-annotator agreement, an ablation study, ASR/translation quality, and error-propagation analysis. Run everything with `python src/run_all_evaluations.py`.

## Architecture

```text
Consultation audio
       |
       v
whisper-cli (Hindi transcription + English translation)
       |
       +-------------------------------+
       |                               |
       v                               v
Hindi transcript                 English transcript
                                       |
                                       v
                            Heuristic Q/A segmentation
                                       |
                                       v
                     Rule/lexicon-based clinical extraction
                                       |
                                       v
             Hindi span projection (timestamps + phonetic lexicon)
                                       |
                       +---------------+---------------+
                       |               |               |
                       v               v               v
                   Entities        Assertions       Relations
                       |               |               |
                       +---------------+---------------+
                                       |
                                       v
                           Local concept dictionary
                                       |
                                       v
                        Structured form + evidence map
                                       |
                                       v
                          Human review / correction
```

**Important architecture clarification:** NER and form population run on the English translation, and each English entity is then projected back to a Hindi span. About 23% of entities (28% of clinical entities) are linked to a specific Hindi word span. The rest are linked to the time-aligned Hindi segment only, or are unaligned where the Hindi ASR hallucinated. Native Hindi NER (running NER on the Hindi text itself) is not implemented.

## Repository structure

```text
src/
  medical_ner.py          # Rule-based entity detection, assertions, relations, concept lookup
  alignment.py            # Hindi<->English entity span projection + hallucination detection
  form_populator.py       # Q/A alignment and structured form generation
  evaluate.py             # Historical binary comparator (legacy only)
  evaluate_m4.py          # Four-state field + human-annotated NER evaluator
  prepare_annotations.py  # Creates local blank NER gold-annotation templates
  annotation_agreement.py # Inter-annotator agreement (pairwise F1, Cohen's kappa) + adjudication
  ablation.py             # Ablation study: contribution of each component vs trivial baselines
  asr_eval.py             # Whisper hallucination rate, Hindi WER/CER, English chrF
  error_analysis.py       # Error propagation: which stage lost each missing answer
  compare_ner_systems.py  # Rule system vs neural baseline (GLiNER)
  run_all_evaluations.py  # Runs every evaluation and prints a summary
  pipeline.py             # End-to-end command-line orchestration
  serve.py                # Local-only dashboard server
  export_web_data.py      # Local dashboard-data export
baselines/
  gliner_baseline.py      # Zero-shot neural NER baseline (run on Kaggle/Colab)
tests/                    # 62 automated tests (standard library unittest)
web/
  index.html, app.js, style.css   # Dashboard
  annotate.html                   # NER annotation tool
```

Clinical audio, scanned forms, raw transcripts, generated patient records and the aggregated dashboard data are intentionally excluded from version control. Obtain the necessary permissions before processing or sharing any real patient data. If any such files were already committed, `.gitignore` will not remove them from Git history; untrack them with `git rm -r --cached audio Docs outputs` after checking the paths and repository status.

## Setup and execution

### 1. Python

Use Python 3.9 or later. The core pipeline and all evaluations use only the Python standard library: there is nothing to `pip install`. Only the optional GLiNER baseline needs PyTorch (run it on Kaggle/Colab).

### 2. Whisper CLI and model

Install `whisper-cli` separately and place a compatible multilingual GGML model at:

```text
models/ggml-small.bin
```

The model binary is not included in this repository. Follow the installation and model licensing instructions from the Whisper implementation you choose.

### 3. Input data layout

Place authorized, de-identified or locally controlled data in the following paths:

```text
audio/<case_id>.mp3
outputs/transcripts/<case_id>_hi.json
outputs/transcripts/<case_id>_en.json
```

If transcripts are not already present, the pipeline attempts to generate them using `whisper-cli`.

### 4. Run the pipeline

From the repository root:

```bash
python src/pipeline.py                 # all audio cases
python src/pipeline.py <case_id>       # one case
```

### 5. Run the regression tests

```bash
python -m unittest discover -s tests -v
```

The suite contains 62 automated tests.

### 6. Run M4 evaluation separately

The end-to-end pipeline runs the M4 evaluator automatically after forms are generated. To rerun it separately:

```bash
python src/evaluate_m4.py
```

The report and JSON outputs are written under `outputs/eval/m4/`. To add a descriptive output-state comparison with saved pre-M3 forms:

```bash
python src/evaluate_m4.py --baseline-forms-dir outputs/baseline_forms
```

To prepare local, blank NER annotation files:

```bash
python src/prepare_annotations.py
```

Review and complete the annotation templates independently from the model predictions. Do not mark a template `complete` until two reviewers have reviewed/adjudicated it. Then rerun `python src/evaluate_m4.py` to calculate NER precision, recall and F1.

### 7. Export and run the dashboard

```bash
python src/export_web_data.py
python -m http.server 8080 --directory web
```

Open `http://localhost:8080` in a browser. The generated `web/data.json` may contain sensitive patient information; keep it local and never commit it to a public repository.

## Evaluation status and limitations

The pre-existing benchmark summary is a small legacy field-agreement check, not evidence of general clinical accuracy. The evaluator compares a limited set of structured fields only where both a ground-truth JSON file and a generated form exist. In the supplied folder layout, one ground-truth case has no matching generated form, while one generated case has no matching ground-truth record. The legacy script therefore reports four matched cases (72 fields), not the complete five-case set. It uses tolerant numeric comparison for weight and binary labels for multiple screening fields. It does not provide token-level NER precision/recall/F1, independent clinical adjudication, robust missing-data handling or evidence of generalization to unseen patients.

The legacy report remains explicitly labelled **not clinical accuracy**. The new `evaluate_m4.py` replaces it for M4 reporting: it uses four-state assertion labels, treats predicted UNKNOWN as an abstention rather than ABSENT, excludes UNKNOWN reference labels, reports per-class precision/recall/F1, confusion matrices, evidence coverage, per-field support and numeric errors.

### Preliminary M4 result on the supplied local data

- Five ground-truth records and five generated forms were present; only **four case IDs matched**.
- **56** mapped assertion fields were scorable: **22/56 exact four-state matches (39.3%)**.
- Prediction coverage was **39.3%**; the remaining **34 fields were UNKNOWN**. The evidence audit found no matched question-and-answer evidence for those 34 abstentions.
- The 22 non-UNKNOWN predictions agreed with the reference on this small matched subset (100% selective accuracy). This does not establish generalization or clinical accuracy.
- The only two PRESENT reference fields were family-history fields. All 11 symptom fields were ABSENT in the reference set, so positive symptom sensitivity cannot be estimated.
- Age matched 4/4; weight was available for 3/4 and matched 3/3.
- Independent NER span annotations have not yet been completed; NER precision, recall and F1 are therefore **not available**.

A descriptive baseline audit across all five generated forms found 68 ABSENT / 2 PRESENT slots in the old output versus 23 ABSENT / 2 PRESENT / 45 UNKNOWN slots after M3. This is an output-state audit, not an accuracy comparison; it demonstrates a shift away from unsupported negative defaults, while also showing that extraction coverage remains limited.

Do not present the legacy `100%` result as “100% clinical accuracy.” The current M4 measurements are preliminary, class-imbalanced, based on only four matched case pairs, and require independent clinical review. Patient data and test splits must be governed by consent, de-identification and institutional approval.

### Additional analyses (`python src/run_all_evaluations.py`)

- **Trivial baselines (ablation):** "always ABSENT" reaches 96.4% exact agreement with 0% PRESENT recall, because 54 of the 56 reference labels are ABSENT. The reference set cannot separate careful extraction from guessing "no". Coverage, selective accuracy and PRESENT recall are therefore reported separately. See `outputs/eval/ablation/`.
- **Question-mention errors:** clause-level question detection reduces clinical entities wrongly labelled PRESENT inside a clinician question from 16 to 0 (out of 113).
- **Alignment:** phonetic matching links 23.3% of entities to a Hindi word span, against 14.8% for exact string matching.
- **ASR quality:** Whisper hallucinated 71% of one recording's Hindi audio, and 0–49% of English translation segments sit inside repetition loops. See `outputs/eval/asr/`.
- **Error propagation:** of the 34 answers the system missed, 20 were absent from both transcripts (ASR), 5 were present in Hindi but lost in the English translation, and 9 were present in English but not matched by the question rules. See `outputs/eval/error_analysis/`.

## M3 changes in this version

- Four-state assertion handling: `PRESENT`, `ABSENT`, `POSSIBLE`, `UNKNOWN`.
- Improved Q/A turn grouping when ASR omits question marks.
- Conservative defaults: unanswered fields remain null/unknown.
- Removed case-ID-specific demographic and measurement fallbacks.
- Removed unobserved “Normal” defaults for pulse, respiratory rate and blood pressure.
- Added field-level extraction evidence (source question and answer).
- Scoped NER assertion cues to local clauses and prevented question mentions from becoming automatic positive findings.
- Added automated regression tests for these behaviors.

## Known limitations

- Q/A segmentation and assertion detection are heuristic and can fail on code-mixed, noisy or poorly translated speech.
- Clinical NER is rule/lexicon based; it is not a trained contextual model.
- Native Hindi NER is not implemented; Hindi spans are obtained by projection from English, and only about a quarter of entities reach word-level alignment.
- The local concept dictionary is limited and has not been independently clinically validated.
- There is no speaker diarization or robust dialogue-turn attribution.
- The dashboard is a local prototype, not a secure clinical deployment.
- No claim of diagnostic performance or clinical readiness is made.
