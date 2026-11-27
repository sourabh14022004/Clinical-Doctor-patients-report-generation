#!/usr/bin/env python3
"""
Master End-to-End Pipeline
Speech-to-Text -> Clinical Medical NER & Relation Extraction -> Clinical Form Population -> Ground Truth Validation

Usage:
    python3 src/pipeline.py                # Run on all patients in audio/
    python3 src/pipeline.py Praveen        # Run on specific patient
"""

import sys
import os
import glob
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from src.medical_ner import ClinicalNEREngine
    from src.form_populator import CancerScreeningFormPopulator
    from src.evaluate import PipelineEvaluator
    from src.evaluate_m4 import M4Evaluator
except ImportError:
    from medical_ner import ClinicalNEREngine
    from form_populator import CancerScreeningFormPopulator
    from evaluate import PipelineEvaluator
    from evaluate_m4 import M4Evaluator


def run_transcription(audio_path: str, model_path: str = "models/ggml-small.bin") -> Dict[str, str]:
    """
    Runs whisper-cli to produce both Hindi and English transcripts if not already present.
    """
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    os.makedirs("outputs/transcripts", exist_ok=True)
    out_hi = f"outputs/transcripts/{base_name}_hi"
    out_en = f"outputs/transcripts/{base_name}_en"

    # Hindi transcription
    if not os.path.exists(out_hi + ".json"):
        print(f"[*] Transcribing Hindi speech for {base_name}...")
        cmd_hi = ["whisper-cli", "-m", model_path, "-f", audio_path, "-l", "hi", "-oj", "-of", out_hi]
        subprocess.run(cmd_hi, check=True)

    # English translation
    if not os.path.exists(out_en + ".json"):
        print(f"[*] Translating & Transcribing English for {base_name}...")
        cmd_en = ["whisper-cli", "-m", model_path, "-f", audio_path, "-tr", "-oj", "-of", out_en]
        subprocess.run(cmd_en, check=True)

    return {
        "hi_json": out_hi + ".json",
        "en_json": out_en + ".json"
    }


def process_patient(patient_id: str, ner_engine: ClinicalNEREngine, form_populator: CancerScreeningFormPopulator):
    """
    Executes the end-to-end NLP and form population for a patient.
    """
    print(f"\n==================================================")
    print(f"  PROCESSING PATIENT: {patient_id}")
    print(f"==================================================")

    en_path = f"outputs/transcripts/{patient_id}_en.json"
    hi_path = f"outputs/transcripts/{patient_id}_hi.json"

    # If transcript does not exist, transcribe from audio
    if not os.path.exists(en_path):
        audio_file = f"audio/{patient_id}.mp3"
        if not os.path.exists(audio_file):
            print(f"[!] Audio file {audio_file} not found. Skipping.")
            return None
        run_transcription(audio_file)

    # 1. Clinical Medical NER & Assertion Detection & Relations
    print(f"[*] Running Medical NER & Relation Extraction...")
    ner_result = ner_engine.process_consultation(hi_path, en_path)
    os.makedirs("outputs/ner", exist_ok=True)
    with open(f"outputs/ner/{patient_id}_ner.json", "w", encoding="utf-8") as f:
        json.dump(ner_result, f, indent=2)
    print(f"    -> Extracted {len(ner_result['entities'])} entities ({ner_result['ontology_grounded_count']} ontology-grounded)")
    print(f"    -> Extracted {len(ner_result['relations'])} clinical relations")

    # 2. Form Population
    print(f"[*] Populating GIMS Cancer Health Check up Clinical Form...")
    with open(en_path, "r", encoding="utf-8", errors="replace") as f:
        en_data = json.load(f)
    hi_data = None
    if os.path.exists(hi_path):
        with open(hi_path, "r", encoding="utf-8", errors="replace") as f:
            hi_data = json.load(f)

    form = form_populator.populate_form(en_data, hi_data, ner_result, patient_id=patient_id)

    # Align family-history relations with the form's answer-level decision so the
    # dashboard never shows two different answers for the same question.
    ner_engine.reconcile_family_history(ner_result, form)
    with open(f"outputs/ner/{patient_id}_ner.json", "w", encoding="utf-8") as f:
        json.dump(ner_result, f, indent=2)

    os.makedirs("outputs/forms", exist_ok=True)
    with open(f"outputs/forms/{patient_id}_form.json", "w", encoding="utf-8") as f:
        json.dump(form, f, indent=2)

    # Generate Markdown Clinical Summary
    report_md = form_populator.generate_markdown_report(form)
    with open(f"outputs/forms/{patient_id}_report.md", "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"    -> Saved JSON form to outputs/forms/{patient_id}_form.json")
    print(f"    -> Saved Markdown report to outputs/forms/{patient_id}_report.md")

    return form


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None

    ner_engine = ClinicalNEREngine()
    form_populator = CancerScreeningFormPopulator()

    if target:
        patients = [target]
    else:
        # Discover all patients in audio
        audio_files = sorted(glob.glob("audio/*.mp3"))
        patients = [os.path.splitext(os.path.basename(f))[0] for f in audio_files]

    print(f"[*] Pipeline initialized for {len(patients)} patients: {', '.join(patients)}")

    for p in patients:
        process_patient(p, ner_engine, form_populator)

    # 3. Evaluation against Ground Truth
    print(f"\n==================================================")
    print(f"  RUNNING BENCHMARK EVALUATION AGAINST GROUND TRUTH")
    print(f"==================================================")
    evaluator = PipelineEvaluator()
    summary = evaluator.evaluate_all()
    print(f"[!] Legacy binary field agreement: {summary.get('overall_accuracy_percent')}%")
    print(f"[!] Compared {summary.get('total_evaluated_fields')} fields ({summary.get('total_matched_fields')} matched).")
    print("[!] This legacy metric is NOT clinical accuracy and does not yet handle UNKNOWN/POSSIBLE correctly.")
    print(f"[✓] Legacy comparison output: outputs/eval/evaluation_report.md")

    print(f"\n==================================================")
    print(f"  RUNNING M4 FOUR-STATE EVALUATION")
    print(f"==================================================")
    m4_summary = M4Evaluator().run()
    m4_fields = m4_summary["field_evaluation"]["assertion_metrics"]
    print(f"[✓] M4 exact four-state agreement: {M4Evaluator._pct(m4_fields['exact_accuracy'])}")
    print(f"[✓] M4 prediction coverage: {M4Evaluator._pct(m4_fields['prediction_coverage'])}")
    print(f"[!] NER metrics available: {m4_summary['ner_evaluation'].get('available', False)}")
    print(f"[✓] M4 report: outputs/eval/m4/M4_EVALUATION_REPORT.md")
    print(f"\nPipeline successfully completed!")


if __name__ == "__main__":
    main()
