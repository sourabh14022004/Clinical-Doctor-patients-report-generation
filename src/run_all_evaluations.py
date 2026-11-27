#!/usr/bin/env python3
"""Re-run every evaluation and print a one-screen summary.

    python src/run_all_evaluations.py

Runs, in order: M4 field evaluation (+ NER if gold annotations are complete),
ablation study, ASR quality, error-propagation analysis and the NER system
comparison. Each writes its own report under outputs/eval/.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    ("M4 field + NER evaluation", "src/evaluate_m4.py"),
    ("Ablation study", "src/ablation.py"),
    ("ASR / translation quality", "src/asr_eval.py"),
    ("Error-propagation analysis", "src/error_analysis.py"),
    ("NER system comparison", "src/compare_ner_systems.py"),
]


def main() -> None:
    failed = []
    for name, script in STEPS:
        print(f"[*] {name} ...", end=" ", flush=True)
        result = subprocess.run([sys.executable, script], cwd=ROOT, capture_output=True, text=True)
        print("ok" if result.returncode == 0 else "FAILED")
        if result.returncode != 0:
            failed.append(name)
            print(result.stderr[-2000:])

    m4 = json.loads((ROOT / "outputs/eval/m4/m4_evaluation_summary.json").read_text())
    fields = m4["field_evaluation"]["assertion_metrics"]
    ablation = json.loads((ROOT / "outputs/eval/ablation/ablation_summary.json").read_text())
    errors = json.loads((ROOT / "outputs/eval/error_analysis/error_analysis.json").read_text())
    pct = lambda v: "N/A" if v is None else f"{v * 100:.1f}%"
    print("\n================ SUMMARY ================")
    print(f"Form fields: exact {pct(fields['exact_accuracy'])}, coverage {pct(fields['prediction_coverage'])}, "
          f"selective {pct(fields['selective_accuracy'])} (n={fields['n_scorable']})")
    ner = m4["ner_evaluation"]
    if ner.get("available"):
        e, l = ner["entity_exact_span_type"], ner["entity_lenient_overlap_type"]
        print(f"NER: strict F1 {pct(e['f1'])}, lenient F1 {pct(l['f1'])} on {ner['completed_annotation_cases']} gold case(s)")
    else:
        print("NER: no completed gold annotations yet")
    for row in ablation["question_mentions"]:
        print(f"Question-mention errors [{row['configuration']}]: {row['present_inside_question']}")
    for row in ablation["alignment"]:
        print(f"Hindi span alignment [{row['configuration']}]: {pct(row['lexical_rate'])}")
    counts, total = errors["counts"], sum(errors["counts"].values())
    print("Where missing answers were lost: " + ", ".join(f"{k} {counts.get(k, 0)}/{total}" for k in "ABCD")
          + "  (A=ASR, B=translation, C=question matching, D=answer parsing)")
    if failed:
        print(f"\nFAILED steps: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
