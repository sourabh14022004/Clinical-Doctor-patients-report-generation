# Project Guide: Start Here

This guide is for someone who has never seen this project. It explains what the project does, the NLP ideas behind it, how the code is organised, and how to run it. For deeper technical detail, see [README.md](README.md) and [PIPELINE_DOCUMENTATION.md](PIPELINE_DOCUMENTATION.md).

---

## 1. The project in one paragraph

A doctor and a patient have a conversation in **Hindi** (or Hindi mixed with English) during a **cancer screening check-up**. The conversation is recorded as audio. The project takes that audio and **fills in the hospital's cancer screening form automatically**. The form is based on the *GIMS (Government Institute of Medical Sciences, Greater Noida) Cancer Health Check-up form*. To fill it, the code turns speech into text, translates it to English, finds the medically important words (symptoms, diseases, tobacco/alcohol use, family history and so on), decides whether each one was said **yes**, **no** or **maybe**, and writes the result as a structured report. A doctor still has to check every report: the output is a **draft**, not a diagnosis.

**Title used in the report/slides:** *Clinical Speech-to-Text and Structured Report Generation*

---

## 2. A real example from this repo

**Input:** `audio/Uday.mp3`, a recorded consultation.

**Step 1: speech to English text** (`outputs/transcripts/Uday_en.json`):

```text
What is your name? Odai Singh.
What is your age?
32 years old.
What do you do?
I do jobs.
Are you married?
Yes.
What is your father's name?
Master's degree.
```

**Step 2: extracted information** (`outputs/ner/Uday_ner.json`):

```json
{ "span": "32 years old", "entity_type": "AGE",            "assertion": "PRESENT" }
{ "span": "married",      "entity_type": "MARITAL_STATUS", "assertion": "UNKNOWN",
  "assertion_reason": "MENTION_IN_QUESTION" }
```

**Step 3: final filled form** (`outputs/forms/Uday_report.md`):

| Field | Extracted |
|---|---|
| Patient name | Odai Singh |
| Age | 32 |
| Marital status | Married |
| Alcohol consumption | Never |
| Family history of cancer | NO (explicitly denied) |
| Oral ulcer > 2 weeks | UNKNOWN (not answered) |

The example also shows the system's weaknesses. Whisper misheard "Uday" as "Odai". "Father's name" was filled with "Master's degree" because the answers in the audio were out of order. Errors like these are why a human reviewer is required.

---

## 3. The pipeline, step by step

```text
 🎤 Hindi consultation audio (audio/*.mp3)
        │
        ▼
 ① SPEECH RECOGNITION + TRANSLATION   ── whisper-cli (OpenAI Whisper "small" model)
        │                                 produces BOTH a Hindi transcript and an English translation
        ▼
 ② QUESTION / ANSWER SPLITTING        ── groups lines into (doctor question, patient answer) pairs
        │
        ▼
 ③ MEDICAL NER                        ── finds medical terms: symptoms, diseases, tobacco, relatives…
        │
        ▼
 ④ ASSERTION DETECTION                ── was it PRESENT, ABSENT, POSSIBLE, or UNKNOWN?
        │
        ▼
 ⑤ RELATION EXTRACTION                ── links things together (e.g. "mother" ↔ "cancer")
        │
        ▼
 ⑥ ONTOLOGY GROUNDING                 ── maps words to standard medical codes (SNOMED-CT / UMLS)
        │
        ▼
 ⑦ FORM POPULATION                    ── fills the screening form (JSON + readable Markdown)
        │
        ▼
 ⑧ EVALUATION                         ── compares generated forms to hand-made "correct" forms
        │
        ▼
 ⑨ WEB DASHBOARD                      ── shows transcript, highlighted entities, and the form side by side
```

---

## 4. NLP concepts used (exam/viva prep)

These are the NLP topics the project covers. You will probably be asked about them.

| Concept | Plain-English meaning | Where in this project |
|---|---|---|
| **ASR (Automatic Speech Recognition)** | Converting spoken audio into text. | `whisper-cli` with `models/ggml-small.bin` (Whisper small, multilingual). |
| **Machine Translation** | Converting text from one language to another. | Whisper's built-in `--translate` mode turns Hindi speech directly into English text. |
| **Code-mixing** | Mixing two languages in one sentence, e.g. "Mujhe *fever* hai". Common in India and hard for NLP models. | The input audio is Hindi/English code-mixed. |
| **Dialogue segmentation** | Splitting a conversation into turns (who said what). | `form_populator.py → extract_qa_turns()` uses "?" and question words (what/how/do you…) to find questions. |
| **NER (Named Entity Recognition)** | Finding and labelling important phrases in text, e.g. "fever" → `SYMPTOM`. | `medical_ner.py → detect_entities()`. It is **rule-based** (regular expressions and a word list), **not** a trained ML model. |
| **Assertion / Negation detection** | Working out whether an entity is affirmed, denied or uncertain. "I have no pain" means pain is **ABSENT**. This is the idea behind the NegEx algorithm. | `medical_ner.py → detect_assertions()` and `form_populator.py → _binary_assertion()`. |
| **Relation Extraction** | Finding links between entities, e.g. *(mother, HAS_CONDITION, cancer)*. | `medical_ner.py → extract_relations()`. It uses word proximity, so it is a simple heuristic. |
| **Ontology grounding / Entity linking** | Mapping a word to a standard ID so that "high BP" and "hypertension" both become one code. | `ONTOLOGY_MAPPINGS` dict at the top of `medical_ner.py` (SNOMED-CT concept IDs and UMLS CUIs). |
| **Information Extraction → Slot filling** | Turning free text into a fixed set of fields. | `form_populator.py → populate_form()`. |
| **Evaluation metrics** | Precision, Recall, F1, Accuracy, Confusion matrix. | `evaluate_m4.py`. |

### The four assertion states

The project labels every yes/no field with one of four states:

| State | Meaning | Example answer |
|---|---|---|
| `PRESENT` | Patient said yes | "Yes, I chew gutkha" |
| `ABSENT` | Patient clearly said no | "No", "never" |
| `POSSIBLE` | Patient was unsure | "Maybe", "not sure" |
| `UNKNOWN` | Never asked, or the answer was unclear | *(no matching question found)* |

An earlier version filled every missing answer with "NO". That is dangerous in medicine, because "we didn't ask" is not the same as "the patient doesn't have it". The project's milestone M3 fixed this, and the fix is something you can present as a deliberate design decision.

---

## 5. Folder map

```text
Clinical-Doctor-patients-report-generation/
│
├── src/                        ← ALL THE CODE
│   ├── pipeline.py             ← MAIN ENTRY POINT. Runs everything end to end.
│   ├── medical_ner.py          ← NER + assertion + relations + SNOMED codes  (the "NLP core")
│   ├── alignment.py            ← Links each English entity back to its Hindi words (cross-lingual projection)
│   ├── ablation.py, asr_eval.py, error_analysis.py, annotation_agreement.py, compare_ner_systems.py
│   │                           ← Evaluation scripts; run them all with run_all_evaluations.py
│   ├── form_populator.py       ← Q/A splitting + fills the cancer screening form
│   ├── evaluate_m4.py          ← Current evaluation (4-state precision/recall/F1)
│   ├── evaluate.py             ← Old yes/no evaluator (kept only for history)
│   ├── prepare_annotations.py  ← Creates blank templates for humans to label entities
│   ├── export_web_data.py      ← Bundles all outputs into web/data.json for the dashboard
│   ├── serve.py                ← Local web server (localhost only) for the dashboard
│   └── conceptnotedatacollector.ipynb  ← early exploration notebook
│
├── audio/                      ← 5 recorded consultations (Uday, Praveen, Priyanshi, Kajal, Swarnima)
├── outputs/
│   ├── transcripts/            ← Whisper output: <name>_hi.json (Hindi) and <name>_en.json (English)
│   ├── ner/                    ← Extracted entities per patient
│   ├── forms/                  ← FINAL OUTPUT: <name>_form.json and <name>_report.md
│   ├── ground_truth/           ← Hand-filled "correct" forms, used for evaluation
│   ├── annotations/            ← Templates for human entity labelling (not finished yet)
│   └── eval/                   ← Evaluation reports (m4/M4_EVALUATION_REPORT.md is the current one)
│
├── web/                        ← Dashboard ("Clinical Documentation Workbench"): index.html, app.js, style.css
├── tests/                      ← 62 automated tests (all passing)
├── Docs/                       ← Milestone records (M3, M4) and scanned paper forms (.jpeg)
├── report/                     ← Final project report (.pdf / .docx)
├── preasentation/              ← Final presentation slides (.pdf / .pptx)
├── models/                     ← Put the Whisper model here (not included, too large)
│
├── HindiNERWorkflow.docx       ← Original problem statement / workflow given to the team
├── IEhealthcare4RUAS-17thApr2025.pptx  ← Reference slides (Oracle AI / IIIT-Delhi clinical NLP)
├── README.md                   ← Technical README
└── PIPELINE_DOCUMENTATION.md   ← Detailed module-by-module documentation
```

**If you only read three code files, read them in this order:**
1. `src/pipeline.py` (160 lines): shows how everything connects.
2. `src/medical_ner.py` (390 lines): the core NLP.
3. `src/form_populator.py` (630 lines): how the form gets filled.

---

## 6. How to run it

The transcripts are already in `outputs/transcripts/`, so **you do not need Whisper** to run the rest of the pipeline. The pipeline skips transcription when the transcript files exist.

```bash
cd Clinical-Doctor-patients-report-generation

# 1. Run the tests (no extra libraries needed, pure Python standard library)
python3 -m unittest discover -s tests -v

# 2. Re-run the whole pipeline on all 5 patients
python3 src/pipeline.py

#    …or on one patient
python3 src/pipeline.py Uday

# 3. Open the dashboard
python3 src/export_web_data.py
python3 src/serve.py           # then open http://127.0.0.1:8080
```

**Only needed for new audio:** install `whisper-cli` (from the whisper.cpp project) and download the multilingual `ggml-small.bin` model into `models/`. Neither is installed on this machine at the moment.

> Works on Python 3.9+ (this Mac has 3.9.6). No packages to install.
>
> To re-run every evaluation: `python3 src/run_all_evaluations.py`

---

## 7. Results so far (what to say honestly)

From `outputs/eval/m4/M4_EVALUATION_REPORT.md`:

- **Dataset:** 5 consultations. Only **4** have both a generated form and a hand-made "correct" form with matching names.
- **56** yes/no fields were compared:
  - **22 / 56 (39.3%)** exactly correct.
  - The other **34** were left as `UNKNOWN` because the system could not find the question in the transcript.
  - Of the 22 fields where the system did give an answer, **all 22 were correct** (100% *selective* accuracy).
- Age was correct for 4/4 patients. Weight was correct for 3/3 where it was available.
- **NER precision, recall and F1 have not been measured yet**, because nobody has finished hand-labelling the entities.

**How to read this:** the system is **careful but incomplete**. When it answers, it is right, but it often doesn't answer. With only 4 patients, none of these numbers prove the system works in general.

---

## 8. Known weaknesses

These are useful for the "limitations / future work" part of a presentation:

1. **The NER is rule-based**, made of regex patterns and a fixed word list. It misses synonyms and spelling variants. *Future work:* a trained model such as BioBERT, scispaCy or a fine-tuned multilingual model (e.g. IndicBERT / MuRIL).
2. **All NLP runs on the English translation.** Hindi NER isn't done, so meaning lost in translation is lost for good.
3. **No speaker diarization.** The system guesses doctor vs patient from question marks only.
4. **ASR errors.** "Uday" became "Odai", and answers can get mismatched to questions.
5. **Tiny dataset.** 5 recordings, with no positive symptom cases in the ground truth.
6. **Relation extraction is proximity-based** and can link the wrong things.
7. **The SNOMED/UMLS mapping is a hand-written dictionary** of 39 terms, and no clinician has validated it.

---

## 9. Things I noticed while reading the repo

- ⚠️ **Privacy:** `.gitignore` and the README both say that patient audio, transcripts and forms must **not** be in Git, but 55 such files (in `audio/`, `outputs/`, `Docs/`) are committed. If this repository is public on GitHub, real patient voices and details are exposed. Check this with your team.
- The folder `preasentation/` is misspelled (should be `presentation/`). This is cosmetic.
- There is a ground-truth file for `ManojKumar` but no audio, and audio for `Kajal` but no ground truth. That mismatch is why only 4 cases can be evaluated.

---

## 10. Glossary

| Term | Meaning |
|---|---|
| **Whisper** | OpenAI's open-source speech recognition model. `whisper-cli` is the C++ (whisper.cpp) version used here. |
| **GGML** | The model file format used by whisper.cpp. |
| **SNOMED-CT** | The world's largest standard dictionary of medical terms, where every concept has a numeric ID. |
| **UMLS / CUI** | Unified Medical Language System. A CUI (Concept Unique Identifier) like `C0015967` = "fever". |
| **Ground truth / Gold standard** | The correct answers, filled in by a human, that the system is compared against. |
| **Selective accuracy** | Accuracy counted only over the cases where the system gave an answer. |
| **Prediction coverage** | The percentage of fields where the system gave any answer at all. |
| **M3 / M4** | Course milestones: M3 = model development, M4 = evaluation. |
| **GIMS** | Government Institute of Medical Sciences, Greater Noida. The source of the screening form. |

---

## 11. What's new since this guide was first written

- **Hindi↔English alignment** (`src/alignment.py`): the main thing the brief asked for. See the "Hindi span" column in the dashboard's Medical entities tab.
- **Family-history fix:** the doctor's questions are no longer counted as findings (16 → 0 errors), and conflicting answers are flagged for review.
- **Evaluation suite:** ablation study, ASR hallucination rate, error-propagation analysis, NER agreement tools. All reports are in `outputs/eval/`.
- **Annotation tool:** `http://127.0.0.1:8080/annotate.html`.
- **What the team still has to do:** see [TEAM_TASKS.md](TEAM_TASKS.md).
- **How to present it:** see [PRESENTATION_GUIDE.md](PRESENTATION_GUIDE.md).
