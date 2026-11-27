#!/usr/bin/env python3
"""Ablation study: what does each NLP component contribute?

Runs the pipeline on the existing transcripts under several configurations (each
with one component switched off, plus two trivial baselines) and scores every
configuration with the same M4 evaluator. Nothing in outputs/forms or outputs/ner
is modified; temporary forms are written to a scratch directory.

    python src/ablation.py

Writes outputs/eval/ablation/ablation_report.md and ablation_summary.json.
"""
from __future__ import annotations

import copy
import glob
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

try:
    from src.evaluate_m4 import ASSERTION_FIELDS, M4Evaluator
    from src.form_populator import CancerScreeningFormPopulator
    from src.medical_ner import ClinicalNEREngine
except ImportError:
    from evaluate_m4 import ASSERTION_FIELDS, M4Evaluator
    from form_populator import CancerScreeningFormPopulator
    from medical_ner import ClinicalNEREngine

TRANSCRIPTS = ROOT / "outputs" / "transcripts"
GROUND_TRUTH = ROOT / "outputs" / "ground_truth"
OUT_DIR = ROOT / "outputs" / "eval" / "ablation"

CLINICAL_TYPES = {"SIGN_SYMPTOM", "DIAGNOSIS", "CANCER_TYPE", "ORAL_SIGN",
                  "RISK_FACTOR_TOBACCO", "RISK_FACTOR_ALCOHOL", "FAMILY_MEMBER"}


def case_ids() -> List[str]:
    return sorted(Path(p).name[:-8] for p in glob.glob(str(TRANSCRIPTS / "*_en.json")))


def load(case_id: str, lang: str) -> Dict[str, Any]:
    path = TRANSCRIPTS / f"{case_id}_{lang}.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8", errors="replace") as handle:
        return json.load(handle)


def set_all(form: Dict[str, Any], state: Optional[str], only_unknown: bool = False) -> Dict[str, Any]:
    """Overwrite the 14 scored assertion fields (used for the trivial baselines)."""
    form = copy.deepcopy(form)
    for spec in ASSERTION_FIELDS:
        item = form.get(spec.section, {}).get(spec.field)
        if not isinstance(item, dict):
            continue
        if only_unknown and item.get("assertion") not in (None, "UNKNOWN"):
            continue
        item["assertion"] = state
    return form


def score_forms(forms: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        for case_id, form in forms.items():
            with open(os.path.join(tmp, f"{case_id}_form.json"), "w", encoding="utf-8") as handle:
                json.dump(form, handle)
        evaluator = M4Evaluator(ground_truth_dir=str(GROUND_TRUTH), forms_dir=tmp,
                                ner_dir=os.path.join(tmp, "none"), output_dir=os.path.join(tmp, "eval"))
        metrics, _, _ = evaluator.evaluate_fields()
    m = metrics["assertion_metrics"]
    return {
        "n": m["n_scorable"],
        "exact_accuracy": m["exact_accuracy"],
        "coverage": m["prediction_coverage"],
        "selective_accuracy": m["selective_accuracy"],
        "present_recall": m["per_class"]["PRESENT"]["recall"],
        "absent_recall": m["per_class"]["ABSENT"]["recall"],
        "macro_f1": m["macro_f1_over_supported_gold_classes"],
    }


def build_forms(populator: CancerScreeningFormPopulator, engine: ClinicalNEREngine,
                post: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
    forms = {}
    for case_id in case_ids():
        en, hi = load(case_id, "en"), load(case_id, "hi")
        ner = engine.process_consultation(str(TRANSCRIPTS / f"{case_id}_hi.json"), str(TRANSCRIPTS / f"{case_id}_en.json"))
        form = populator.populate_form(en, hi or None, ner, patient_id=case_id)
        forms[case_id] = post(form) if post else form
    return forms


def question_mention_errors(engine: ClinicalNEREngine) -> Dict[str, int]:
    """Clinical entities labelled PRESENT although their clause ends with '?'.

    The '?' comes from the ASR output itself, so this is an objective count of
    clinician-question mentions wrongly reported as patient findings.
    """
    errors = clinical = 0
    for case_id in case_ids():
        result = engine.process_consultation(str(TRANSCRIPTS / f"{case_id}_hi.json"), str(TRANSCRIPTS / f"{case_id}_en.json"))
        text = result["english_text"]
        for ent in result["entities"]:
            if ent["entity_type"] not in CLINICAL_TYPES:
                continue
            clinical += 1
            match = re.search(r"[.?!;\n]", text[ent["end"]:])
            in_question = bool(match) and match.group(0) == "?"
            if in_question and ent["assertion"] == "PRESENT":
                errors += 1
    return {"clinical_entities": clinical, "present_inside_question": errors}


def alignment_rate(engine: ClinicalNEREngine) -> Dict[str, Any]:
    totals = {"entities": 0, "lexical": 0, "clinical": 0, "clinical_lexical": 0}
    for case_id in case_ids():
        result = engine.process_consultation(str(TRANSCRIPTS / f"{case_id}_hi.json"), str(TRANSCRIPTS / f"{case_id}_en.json"))
        for ent in result["entities"]:
            lexical = ent["hindi_alignment"]["method"] == "lexical"
            totals["entities"] += 1
            totals["lexical"] += lexical
            if ent["entity_type"] in CLINICAL_TYPES:
                totals["clinical"] += 1
                totals["clinical_lexical"] += lexical
    totals["lexical_rate"] = totals["lexical"] / totals["entities"] if totals["entities"] else None
    totals["clinical_lexical_rate"] = totals["clinical_lexical"] / totals["clinical"] if totals["clinical"] else None
    return totals


def pct(value: Optional[float]) -> str:
    return "N/A" if value is None else f"{value * 100:.1f}%"


def main() -> None:
    full_engine = ClinicalNEREngine()
    full_populator = CancerScreeningFormPopulator()
    full_forms = build_forms(full_populator, full_engine)

    form_rows = [
        ("Trivial baseline: always ABSENT", "No NLP. Predicts 'no' for every field.",
         score_forms({k: set_all(v, "ABSENT") for k, v in full_forms.items()})),
        ("Trivial baseline: always UNKNOWN", "No NLP. Abstains on every field.",
         score_forms({k: set_all(v, "UNKNOWN") for k, v in full_forms.items()})),
        ("Full system", "All components on.", score_forms(full_forms)),
        ("- question-start cues", "Questions detected by '?' only; ASR often drops '?'.",
         score_forms(build_forms(CancerScreeningFormPopulator(question_start_cues=False), full_engine))),
        ("+ pre-M3 default (UNKNOWN -> ABSENT)", "Unanswered fields silently become 'no' (old behaviour).",
         score_forms({k: set_all(v, "ABSENT", only_unknown=True) for k, v in full_forms.items()})),
    ]

    ner_rows = [
        ("Full system", question_mention_errors(full_engine)),
        ("- clause-level question detection", question_mention_errors(ClinicalNEREngine(clause_question_detection=False))),
    ]
    align_rows = [
        ("Phonetic skeleton matching (full)", alignment_rate(full_engine)),
        ("Exact string matching only", alignment_rate(ClinicalNEREngine(phonetic_alignment=False))),
    ]

    lines = [
        "# Ablation study", "",
        "Each row switches one component off (or replaces the system with a trivial baseline) and is scored with the same M4 evaluator on the same matched cases. Reproduce with `python src/ablation.py`.", "",
        "## 1. Form filling (14 assertion fields x matched cases)", "",
        "| Configuration | Description | Exact agreement | Coverage | Selective accuracy | PRESENT recall | ABSENT recall |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for name, desc, m in form_rows:
        lines.append(f"| {name} | {desc} | {pct(m['exact_accuracy'])} | {pct(m['coverage'])} | {pct(m['selective_accuracy'])} | {pct(m['present_recall'])} | {pct(m['absent_recall'])} |")
    full, cues_off, default_absent = form_rows[2][2], form_rows[3][2], form_rows[4][2]
    support = full["n"]
    lines += [
        "",
        f"**How to read this.** The reference set has {support} scorable fields and almost all of them are ABSENT. "
        "A system that answers 'no' to everything therefore scores very high exact agreement while having **0% PRESENT recall**: "
        "it would miss every patient who actually has a symptom or family history. "
        f"The pre-M3 default (turn every UNKNOWN into ABSENT) reaches {pct(default_absent['exact_accuracy'])} for the same reason: "
        "it guesses 'no' wherever the system found no answer, and on this data the guess happens to be right. "
        "**This does not show that guessing is better; it shows that this reference set cannot distinguish careful extraction from guessing.** "
        "That is why the project reports coverage, selective accuracy and PRESENT recall separately, and why positive and uncertain cases are needed before any accuracy claim.",
        "",
        (f"Question-start cues had **no measurable effect** on these transcripts ({pct(cues_off['exact_accuracy'])} vs {pct(full['exact_accuracy'])}): "
         "Whisper kept the '?' on these recordings. The cues remain as a safeguard for ASR output without punctuation, which the unit tests cover.")
        if cues_off["exact_accuracy"] == full["exact_accuracy"] else
        f"Removing question-start cues changes exact agreement from {pct(full['exact_accuracy'])} to {pct(cues_off['exact_accuracy'])}.",
        "",
        "## 2. Assertion detection: question mentions", "",
        "Clinical entity mentions labelled PRESENT although the clause ends with '?' (i.e. the clinician asked about it; it is not a patient finding).", "",
        "| Configuration | Clinical entities | PRESENT inside a question (errors) |", "|---|---:|---:|",
    ]
    for name, m in ner_rows:
        lines.append(f"| {name} | {m['clinical_entities']} | {m['present_inside_question']} |")
    lines += [
        "", "## 3. Hindi <-> English alignment", "",
        "Share of English entities projected to a specific Hindi word span (not just a time-aligned segment).", "",
        "| Configuration | All entities aligned to a Hindi span | Clinical entities aligned |", "|---|---:|---:|",
    ]
    for name, m in align_rows:
        lines.append(f"| {name} | {m['lexical']}/{m['entities']} ({pct(m['lexical_rate'])}) | {m['clinical_lexical']}/{m['clinical']} ({pct(m['clinical_lexical_rate'])}) |")
    lines += ["", "Hindi ASR spells the same word many ways (कैंसर / कानसर / कंसर / खंसर / खणसर); exact matching misses most of them.", ""]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "ablation_report.md").write_text("\n".join(lines), encoding="utf-8")
    with open(OUT_DIR / "ablation_summary.json", "w", encoding="utf-8") as handle:
        json.dump({"form_filling": [{"configuration": n_, "description": d, **m} for n_, d, m in form_rows],
                   "question_mentions": [{"configuration": n_, **m} for n_, m in ner_rows],
                   "alignment": [{"configuration": n_, **m} for n_, m in align_rows]}, handle, indent=2)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
