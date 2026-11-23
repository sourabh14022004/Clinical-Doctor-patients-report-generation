# Clinical Speech-to-Text and Report Generation Pipeline

This document describes the current M3 prototype implementation. Earlier versions of this document contained stronger benchmark and clinical-performance claims than the implementation supports; those claims are superseded by this version.

## 1. Scope

The project is an academic prototype that converts consultation audio into bilingual transcripts, extracts a limited set of clinical concepts from the English translation, and maps aligned answers into a structured screening form. It is not a diagnostic tool and is not cleared for clinical deployment.

## 2. Processing architecture

```text
Audio input
  -> whisper-cli
       -> Hindi transcription
       -> English translation
  -> English transcript question/answer segmentation
  -> Rule/lexicon clinical entity extraction
  -> Local-context assertion classification
  -> Heuristic relation extraction
  -> Local concept dictionary lookup
  -> Structured screening form + extraction evidence
  -> Human review
```

Hindi transcript is retained for bilingual display. In the current pipeline, clinical entity detection and form population primarily operate on the English translation; Hindi entity recognition and bilingual span alignment are incomplete.

## 3. Module responsibilities

### `src/pipeline.py`

- Discovers audio cases in `audio/` or accepts a single case ID.
- Uses existing transcript JSON where available; otherwise invokes `whisper-cli`.
- Runs clinical entity and relation extraction.
- Populates the structured form and generates a Markdown summary.
- Invokes the legacy comparator as a historical reference and the M4 four-state evaluator after form generation. Neither output is clinical validation.

### `src/medical_ner.py`

- Applies curated regular-expression patterns to selected demographic, symptom, diagnosis, risk-factor, family-member and duration concepts.
- Performs a local dictionary lookup for a limited set of SNOMED-CT / UMLS concepts.
- Assigns `PRESENT`, `ABSENT`, `POSSIBLE` or `UNKNOWN` assertions using local clause context.
- Marks entity mentions occurring in question wording as `UNKNOWN` rather than automatically positive.
- Uses proximity heuristics for selected relations. Relation extraction remains experimental and can generate incorrect links.

This is a rule/lexicon-based extractor. It is not a separately trained contextual NER model.

### `src/form_populator.py`

- Groups transcript segments into question-and-answer turns using punctuation and question-start cues.
- Uses the answer to a matching question for selected form fields.
- Preserves missing or unclear values as JSON `null` and assertion `UNKNOWN`.
- Distinguishes explicit negative answers (`ABSENT`) from unanswered fields (`UNKNOWN`) and uncertain answers (`POSSIBLE`).
- Does not infer sex or measurements from a patient identifier.
- Does not fill unobserved pulse, respiratory rate or blood pressure with "Normal".
- Stores `extraction_evidence` with the matched question and answer for review.

### `src/evaluate.py`

This is a legacy binary field comparator. It evaluates a limited group of fields and does not properly handle the four-state output. It is retained only for historical comparison; never present its result as clinical accuracy.

### `src/evaluate_m4.py`

This is the M4 evaluator. It compares 14 assertion fields using PRESENT / ABSENT / POSSIBLE / UNKNOWN, counts a model UNKNOWN on a known reference as an abstention, excludes unknown reference labels, reports per-class precision/recall/F1 and confusion matrices, and calculates age/weight error separately. It reports NER exact-span/type and assertion metrics only when independent human annotation files are complete.

### `src/prepare_annotations.py`

Creates local NER annotation templates containing transcript text and a blank gold-annotation list. These templates may contain identifiable information; keep them local and do not commit them. Reviewers must annotate independently of model predictions and mark the template complete only after adjudication.

### `src/export_web_data.py` and `web/`

The exporter discovers generated form files instead of hardcoding case names. It does not substitute another case's scanned document when an image is missing. The dashboard distinguishes UNKNOWN from explicit negative answers and displays validation results dynamically rather than hardcoding a perfect match.

## 4. Assertion schema

| Assertion | Meaning | Typical evidence |
|---|---|---|
| `PRESENT` | Explicitly affirmed or supported in the answer | "Yes", "I do", or a positive family-relative answer to a direct family-history question |
| `ABSENT` | Explicitly denied | "No", "never", "I do not", or "not present" |
| `POSSIBLE` | Uncertain / suspected | "Maybe", "possibly", "might", "not sure" |
| `UNKNOWN` | Not answered, unclear, or mentioned only in a question | Empty answer or an entity found in clinician question wording |

`reported` is `true` for PRESENT, `false` for ABSENT, and `null` for POSSIBLE / UNKNOWN. Downstream code must not coerce null to false.

## 5. Generated form schema

Each form JSON contains:

- `schema_version`: current schema identifier (`2.0`).
- `demographics`: transcript-supported demographic responses; unreported values are null.
- `clinical_indicators`: measurements and calculated BMI only when the input includes usable data and units.
- `history`: medical history, prior screening, family history and prior exposure.
- `risk_factors`: tobacco, alcohol, diet, fast-food and physical-activity responses.
- `general_cancer_symptoms` and `oral_cancer_screening`: four-state screening fields.
- `extraction_evidence`: source question and answer used for each mapped field.
- `processing_notes`: limitations and human-review notice.

## 6. Validation performed for M3

The standard-library regression suite is located in `tests/test_m3_pipeline.py`. It covers:

- Q/A alignment where ASR omits a question mark.
- Four-state answer classification.
- No patient-ID-based demographic or vital inference.
- Explicit negative versus unknown values.
- No BMI from a height value with no unit.
- Family history answered using a relative-only response.
- Local assertion scope, question mentions and uncertainty cues.

Run it with:

```bash
python -m unittest discover -s tests -v
```

The end-to-end smoke test can run using the pre-existing local transcript files without re-running Whisper, provided the data and required paths are present:

```bash
python src/pipeline.py
python src/export_web_data.py
```

Local smoke testing confirms code execution and output generation; it is not an accuracy study.

## 7. M4 evaluation status and remaining limitations

- The English translation may alter or omit clinical meaning; Hindi-to-English span alignment is not implemented.
- ASR question segmentation can be wrong, especially for code-mixed or noisy speech.
- Pattern-based NER has limited coverage and can miss synonyms or produce false positives.
- Assertion scope is heuristic and should be clinically adjudicated.
- Relation extraction uses proximity rather than a validated relation model.
- The concept dictionary is limited and must be checked against authoritative terminology releases.
- The supplied benchmark set has five ground-truth JSON records and five generated forms, but only four matching case IDs.
- The preliminary M4 run covers 56 mapped assertion fields across four matching case pairs: 22 exact matches (39.3%) and 34 UNKNOWN abstentions. All 11 symptom reference fields are ABSENT.
- The 22 non-UNKNOWN predictions agree with their reference labels in this small matched subset (100% selective accuracy); this must not be interpreted as generalization or clinical accuracy.
- NER precision/recall/F1 remain unavailable until independent entity annotations are completed and adjudicated.
- The annotation workflow and M4 evaluator are implemented; the dataset still needs more positive/possible cases and resolution of mismatched case IDs.

## 8. Data protection

Audio, scanned forms, transcripts, generated patient records and `web/data.json` may contain personal or sensitive clinical information. They are ignored by `.gitignore` and must not be pushed to a public repository. Confirm consent, de-identification and institutional authorization before using or sharing any clinical data. Use synthetic or approved de-identified samples for public demonstrations.

## 9. Human review

Every generated form is a draft. A qualified human reviewer must check source audio, transcript accuracy, clinical meaning and form values before any real-world use.
