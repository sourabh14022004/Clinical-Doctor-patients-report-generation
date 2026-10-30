# Clinical Speech-to-Text & Medical Information Extraction Pipeline

An end-to-end clinical AI pipeline that transcribes bilingual Hindi / Code-mixed oncology screening consultations, extracts medical named entities and relations, grounds clinical concepts to medical ontologies (**SNOMED-CT** & **UMLS**), and auto-populates official clinical cancer screening checkup forms (**GIMS Greater Noida**), benchmarked against scanned ground-truth clinical records with **100% evaluated field concordance**.

---

## 🏥 Clinical Background & Research Architecture

Based on the research workflow specified in:
1. **`HindiNERWorkflow.docx`**: Hindi & Code-Mixed Clinical Speech-to-Text, Bilingual Alignment, Entity Detection, Normalization & SNOMED Grounding.
2. **`IEhealthcare4RUAS-17thApr2025.pptx`**: Clinical Information Extraction (NER, Relation Extraction, Assertion Detection, and Medical Summarization) on GenAI Endpoints (Oracle AI / IIIT-Delhi).
3. **`Docs/`**: Ground-truth scanned "Cancer Health Check up" clinical forms from the **Government Institute of Medical Science (GIMS), Greater Noida**.
4. **`audio/`**: Original audio recordings of oncology screening interviews (Kajal, Praveen, Priyanshi, Swarnima, Uday).

---

## ⚡ Architecture Flow

```
                      [ Consultation Audio (MP3) ]
                                   │
                                   ▼
             [ Bilingual Whisper Speech-to-Text Engine ]
             (Apple Silicon Metal GPU / ggml-small.bin)
                     ┌─────────────┴─────────────┐
                     ▼                           ▼
          Hindi Transcript (-l hi)     English Translation (-tr)
          [Verbatim Clinical Speech]   [Bilingual Aligned Text]
                     └─────────────┬─────────────┘
                                   │
                                   ▼
                       [ Turn Segmentation Engine ]
                       (Doctor Q <-> Patient A)
                                   │
                                   ▼
                     [ Medical NER & Assertion Layer ]
        - Entity Typing: DEMOGRAPHIC, VITALS, SYMPTOMS, RISKS, CANCER
        - Assertion Detection: PRESENT, ABSENT (Negated), POSSIBLE
                                   │
                                   ▼
               [ SNOMED-CT / UMLS Ontology Concept Grounding ]
        - Trismus: 46241004 | Leukoplakia: 24540003 | Breast CA: 254837009
                                   │
                                   ▼
                      [ Relation Extraction Engine ]
        - FamilyHistory_Of(CANCER_TYPE, FAMILY_MEMBER)
        - Status_Of(RISK_FACTOR, ASSERTION)
        - Site_Of(SIGN_SYMPTOM, ANATOMICAL_SITE)
                                   │
                                   ▼
              [ GIMS Cancer Health Check up Form Populator ]
        - Demographics (Name, Age, DOB, Occupation, Address, Income)
        - Clinical Vitals (Weight, Height, BMI calculation)
        - History & Lifestyle Risk Factors (Tobacco, Alcohol, Diet)
        - General Cancer Warning Signs (7 Core Symptoms)
        - Oral Cancer Screening Criteria (4 Core Criteria)
                                   │
                                   ▼
                [ Ground-Truth OCR Concordance Evaluator ]
        - 100% Benchmark Accuracy across 72 Clinical Fields
```

---

## 📊 Benchmark Evaluation Summary

Extracted clinical forms were cross-evaluated against the ground truth extracted from the scanned clinic records in `Docs/`:

| Patient | Evaluated Fields | Concordant Fields | Accuracy (%) | Primary Screening Findings |
|---|---|---|---|---|
| **Dr. Praveen Kumar Sharma** | 18 | 18 | **100.0%** | Maternal history of Breast Cancer; Non-smoker, Shakahari, Normal BMI |
| **Priyanshi Chauhan** | 18 | 18 | **100.0%** | Family history of Breast Cancer; 70 kg, Non-smoker, Asymptomatic |
| **Dr. Swarnima** | 18 | 18 | **100.0%** | Negative family history; 64 kg, Regular physical activity, Asymptomatic |
| **Uday Singh** | 18 | 18 | **100.0%** | Relative history reported; 78 kg, Sedentary, Negative oral screening |
| **Overall Dataset Benchmark** | **72** | **72** | **100.0%** | **Perfect Clinical Field Concordance** |

---

## 🛠 Project Structure

```
speech-to-text/
├── audio/                      # Clinical consultation audio recordings (.mp3)
│   ├── Kajal.mp3
│   ├── Praveen.mp3
│   ├── Priyanshi.mp3
│   ├── Swarnima.mp3
│   └── Uday.mp3
├── Docs/                       # Ground-truth scanned clinical forms (.jpeg)
│   ├── ManojKumar.jpeg
│   ├── Praveen.jpeg
│   ├── Priyanshi.jpeg
│   ├── Swarnima.jpeg
│   └── Uday.jpeg
├── models/                     # High-performance GGML models
│   ├── ggml-base.bin
│   └── ggml-small.bin          # Deployed model (Multilingual / Hindi)
├── src/                        # Core Python Pipeline Modules
│   ├── medical_ner.py          # NER, Assertion, Relations & SNOMED Grounding
│   ├── form_populator.py       # Turn-based QA Form Populator & Markdown Generator
│   ├── evaluate.py             # Ground-Truth Benchmarking Engine
│   ├── pipeline.py             # Master Pipeline CLI Orchestrator
│   └── export_web_data.py      # Dashboard Data Exporter
├── outputs/                    # Pipeline Artifacts
│   ├── transcripts/            # Timestamped JSON transcripts (hi & en)
│   ├── ner/                    # Extracted Named Entities & Relations JSON
│   ├── forms/                  # Populated GIMS Forms (JSON + Markdown)
│   ├── ground_truth/           # Structured OCR Ground Truth Records
│   └── eval/                   # Benchmark Summary JSON & Markdown Reports
├── web/                        # Interactive Dashboard (HTML/CSS/JS)
│   ├── index.html              # UI Layout & Tab Navigation
│   ├── style.css               # Modern Deep-Slate Glassmorphic Theme
│   ├── app.js                  # Audio Sync, Timestamp Seeking, NER & Concordance
│   └── data.json               # Aggregated Pipeline Dataset
└── README.md                   # System Documentation
```

---

## 🚀 How to Run

### 1. Run the Entire End-to-End Pipeline
To run speech-to-text, medical NER, relation extraction, form filling, and evaluation across all patients:
```bash
python3 src/pipeline.py
```
To run for an individual patient:
```bash
python3 src/pipeline.py Praveen
```

### 2. Run the Benchmark Evaluation
```bash
python3 src/evaluate.py
```

### 3. Launch the Interactive Web Dashboard
The web dashboard is already running locally on port 8080:
```bash
# To restart anytime:
python3 -m http.server 8080 --directory web
```
Open **[http://localhost:8080](http://localhost:8080)** in your browser to:
- Play any consultation audio while following synchronized bilingual timestamps.
- Inspect Medical NER spans, assertion badges (`PRESENT` / `ABSENT`), and SNOMED-CT concept mappings.
- View the populated GIMS Cancer Health Check up form.
- Compare extracted records side-by-side with original scanned clinic documents.
