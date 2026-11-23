#!/usr/bin/env python3
"""M4 evaluation for the clinical speech-to-structured-report prototype.

This evaluator deliberately separates:
1) four-state field agreement against structured reference forms;
2) numeric field error for explicitly mapped measurements;
3) entity/assertion performance against independently completed annotations.

It never treats UNKNOWN as ABSENT. Ground-truth UNKNOWN values are excluded from
classification metrics; a model prediction of UNKNOWN for a known gold label is
counted as an abstention (not as a negative).
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

LABELS = ("PRESENT", "ABSENT", "POSSIBLE", "UNKNOWN")


@dataclass(frozen=True)
class AssertionField:
    gold_key: str
    section: str
    field: str
    label: str
    parser: str = "binary_or_text"


ASSERTION_FIELDS: Tuple[AssertionField, ...] = (
    AssertionField("family_history_cancer", "history", "family_history_of_cancer", "Family history of cancer", "family_history"),
    AssertionField("tobacco_or_alcohol", "history", "consumed_tobacco_or_alcohol", "Past tobacco or alcohol use"),
    AssertionField("current_tobacco", "risk_factors", "current_tobacco_use", "Current tobacco use"),
    AssertionField("unexplained_weight_loss", "general_cancer_symptoms", "unexplained_weight_loss", "Unexplained weight loss"),
    AssertionField("persistent_fever_fatigue", "general_cancer_symptoms", "persistent_fever_or_fatigue", "Persistent fever or fatigue"),
    AssertionField("non_healing_ulcer", "general_cancer_symptoms", "non_healing_ulcer_or_wound", "Non-healing ulcer or wound"),
    AssertionField("lump_swelling", "general_cancer_symptoms", "lump_or_swelling_anywhere", "Lump or swelling"),
    AssertionField("persistent_pain", "general_cancer_symptoms", "persistent_pain_without_known_cause", "Persistent pain"),
    AssertionField("bleeding", "general_cancer_symptoms", "bleeding_from_any_site", "Bleeding from any site"),
    AssertionField("chronic_illness", "general_cancer_symptoms", "known_chronic_illness_dm_htn_tb", "Known chronic illness"),
    AssertionField("oral_difficulty_opening_mouth", "oral_cancer_screening", "difficulty_in_opening_mouth", "Difficulty opening mouth"),
    AssertionField("oral_patch", "oral_cancer_screening", "white_or_red_patch_in_mouth", "White or red oral patch"),
    AssertionField("oral_ulcer_gt_2w", "oral_cancer_screening", "ulcer_in_mouth_lasting_gt_2_weeks", "Oral ulcer over two weeks"),
    AssertionField("oral_difficulty_chewing_swallowing", "oral_cancer_screening", "difficulty_in_chewing_or_swallowing", "Difficulty chewing or swallowing"),
)

NUMERIC_FIELDS = (
    {"gold_key": "age", "section": "demographics", "field": "age", "label": "Age", "tolerance": 0.0},
    {"gold_key": "weight_kg", "section": "clinical_indicators", "field": "weight_kg", "label": "Weight (kg)", "tolerance": 2.0},
)

UNKNOWN_TERMS = {
    "", "none", "null", "nan", "n/a", "na", "unknown", "not known",
    "not stated", "not reported", "not mentioned", "not available", "unclear",
    "not assessed", "not answered", "missing", "-", "--",
}
POSSIBLE_RE = re.compile(r"\b(maybe|may be|possibly|possible|might|suspected|suspect|uncertain|not sure|cannot say|can't say|could be)\b", re.I)
NEGATIVE_RE = re.compile(r"\b(no|not|never|none|nil|absent|negative|denies|denied|without|doesn't|does not|didn't|did not)\b", re.I)
POSITIVE_RE = re.compile(r"\b(yes|present|positive|reported|reports|complains of|complaint of|has|have|had|suffers from|diagnosed with|history of)\b", re.I)


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def normalize_assertion(value: Any, parser: str = "binary_or_text") -> str:
    """Map a reference value to a four-state assertion conservatively."""
    if isinstance(value, bool):
        return "PRESENT" if value else "ABSENT"
    if value is None:
        return "UNKNOWN"
    if isinstance(value, (int, float)):
        return "UNKNOWN"

    raw = str(value).strip()
    s = re.sub(r"\s+", " ", raw.lower()).strip()
    if s in UNKNOWN_TERMS:
        return "UNKNOWN"
    if s in {"yes", "y", "true", "1", "present", "positive"}:
        return "PRESENT"
    if s in {"no", "n", "false", "0", "absent", "negative", "nil", "none"}:
        return "ABSENT"
    if POSSIBLE_RE.search(s):
        return "POSSIBLE"
    # Explicit negation takes precedence over a generic positive keyword.
    if NEGATIVE_RE.search(s):
        return "ABSENT"
    if POSITIVE_RE.search(s):
        return "PRESENT"
    if parser == "family_history" and s not in UNKNOWN_TERMS:
        # The source field is free text. A non-empty non-negative entry is treated
        # as family-history evidence; reviewer confirmation remains necessary.
        return "PRESENT"
    return "UNKNOWN"


def normalize_prediction(value: Any) -> str:
    s = str(value or "UNKNOWN").strip().upper()
    return s if s in LABELS else "UNKNOWN"


def get_prediction(form: Dict[str, Any], spec: AssertionField) -> str:
    value = form.get(spec.section, {}).get(spec.field)
    if isinstance(value, dict):
        if "assertion" in value:
            return normalize_prediction(value.get("assertion"))
        # Backward-compatible interpretation for older schema outputs.
        for key in ("reported", "present", "current_user", "screened"):
            if isinstance(value.get(key), bool):
                return "PRESENT" if value[key] else "ABSENT"
    if isinstance(value, bool):
        return "PRESENT" if value else "ABSENT"
    return "UNKNOWN"


def _safe_div(n: float, d: float) -> Optional[float]:
    return (n / d) if d else None


def classification_metrics(pairs: Sequence[Tuple[str, str]]) -> Dict[str, Any]:
    """Metrics over known gold labels; predicted UNKNOWN is an abstention."""
    scorable = [(normalize_prediction(g), normalize_prediction(p)) for g, p in pairs
                if normalize_prediction(g) != "UNKNOWN"]
    matrix = {g: {p: 0 for p in LABELS} for g in LABELS}
    for gold, pred in scorable:
        matrix[gold][pred] += 1
    n = len(scorable)
    correct = sum(matrix[label][label] for label in LABELS)
    covered = sum(1 for _, pred in scorable if pred != "UNKNOWN")
    covered_correct = sum(1 for gold, pred in scorable if pred != "UNKNOWN" and gold == pred)
    per_class: Dict[str, Any] = {}
    supported_f1: List[float] = []
    for label in LABELS:
        tp = matrix[label][label]
        fp = sum(matrix[g][label] for g in LABELS if g != label)
        fn = sum(matrix[label][p] for p in LABELS if p != label)
        support = tp + fn
        predicted = tp + fp
        precision = _safe_div(tp, predicted)
        recall = _safe_div(tp, support)
        f1_den = 2 * tp + fp + fn
        f1 = (2 * tp / f1_den) if f1_den else None
        per_class[label] = {
            "support": support,
            "predicted_count": predicted,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
        if support > 0 and f1 is not None:
            supported_f1.append(f1)
    gold_support = Counter(g for g, _ in scorable)
    return {
        "n_scorable": n,
        "excluded_unknown_gold": len(pairs) - n,
        "correct": correct,
        "exact_accuracy": _safe_div(correct, n),
        "prediction_coverage": _safe_div(covered, n),
        "selective_accuracy": _safe_div(covered_correct, covered),
        "abstentions": n - covered,
        "gold_class_support": dict(gold_support),
        "per_class": per_class,
        "confusion_matrix": matrix,
        "macro_f1_over_supported_gold_classes": statistics.mean(supported_f1) if supported_f1 else None,
        "present_sensitivity": per_class["PRESENT"]["recall"],
        "present_sensitivity_available": per_class["PRESENT"]["support"] > 0,
    }


def field_value(form: Dict[str, Any], section: str, key: str) -> Any:
    value = form.get(section, {}).get(key)
    if isinstance(value, dict):
        for candidate in ("value", "reported", "present", "current_user", "screened"):
            if candidate in value and value[candidate] is not None:
                return value[candidate]
    return value


def numeric_metrics(records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    by_field: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in records:
        by_field[row["field"]].append(row)
    result: Dict[str, Any] = {}
    for label, rows in by_field.items():
        errors = [abs(r["prediction"] - r["gold"]) for r in rows]
        tol = rows[0]["tolerance"]
        result[label] = {
            "support": len(rows),
            "mae": statistics.mean(errors) if errors else None,
            "exact_matches": sum(err == 0 for err in errors),
            "exact_agreement": _safe_div(sum(err == 0 for err in errors), len(errors)),
            "within_tolerance_count": sum(err <= tol for err in errors),
            "within_tolerance_rate": _safe_div(sum(err <= tol for err in errors), len(errors)),
            "tolerance": tol,
        }
    return result


class M4Evaluator:
    def __init__(self, ground_truth_dir: str = "outputs/ground_truth",
                 forms_dir: str = "outputs/forms", ner_dir: str = "outputs/ner",
                 annotations_dir: str = "outputs/annotations",
                 output_dir: str = "outputs/eval/m4",
                 baseline_forms_dir: Optional[str] = None):
        self.gt_dir = ground_truth_dir
        self.forms_dir = forms_dir
        self.ner_dir = ner_dir
        self.annotations_dir = annotations_dir
        self.output_dir = output_dir
        self.baseline_forms_dir = baseline_forms_dir

    def evaluate_fields(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
        gt_files = sorted(glob.glob(os.path.join(self.gt_dir, "*.json")))
        pred_files = sorted(glob.glob(os.path.join(self.forms_dir, "*_form.json")))
        gt_by_id = {os.path.splitext(os.path.basename(p))[0]: p for p in gt_files}
        pred_by_id = {os.path.basename(p)[:-10]: p for p in pred_files}  # remove _form.json
        common_ids = sorted(set(gt_by_id) & set(pred_by_id))
        unmatched_gt = len(set(gt_by_id) - set(pred_by_id))
        unmatched_pred = len(set(pred_by_id) - set(gt_by_id))

        status_pairs: List[Tuple[str, str]] = []
        field_rows: List[Dict[str, Any]] = []
        numeric_rows: List[Dict[str, Any]] = []
        per_field_pairs: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

        for index, case_id in enumerate(common_ids, start=1):
            gt = load_json(gt_by_id[case_id])
            pred = load_json(pred_by_id[case_id])
            case_label = f"case_{index:03d}"
            for spec in ASSERTION_FIELDS:
                gold = normalize_assertion(gt.get(spec.gold_key), parser=spec.parser)
                predicted = get_prediction(pred, spec)
                evidence = pred.get("extraction_evidence", {}).get(f"{spec.section}.{spec.field}", {})
                has_question = bool(evidence.get("question"))
                has_answer = bool(evidence.get("answer"))
                status_pairs.append((gold, predicted))
                per_field_pairs[spec.label].append((gold, predicted))
                field_rows.append({
                    "case": case_label,
                    "field": spec.label,
                    "gold": gold,
                    "prediction": predicted,
                    "match": (gold == predicted) if gold != "UNKNOWN" else None,
                    "evidence_question_present": has_question,
                    "evidence_answer_present": has_answer,
                })
            for spec in NUMERIC_FIELDS:
                gold_value = gt.get(spec["gold_key"])
                pred_value = field_value(pred, spec["section"], spec["field"])
                try:
                    if gold_value is not None and pred_value is not None:
                        gold_num, pred_num = float(gold_value), float(pred_value)
                        if math.isfinite(gold_num) and math.isfinite(pred_num):
                            numeric_rows.append({
                                "case": case_label,
                                "field": spec["label"],
                                "gold": gold_num,
                                "prediction": pred_num,
                                "tolerance": spec["tolerance"],
                            })
                except (TypeError, ValueError):
                    pass

        metrics = classification_metrics(status_pairs)
        per_field = {}
        for label, pairs in per_field_pairs.items():
            m = classification_metrics(pairs)
            per_field[label] = {
                "gold_support": m["gold_class_support"],
                "n_scorable": m["n_scorable"],
                "correct": m["correct"],
                "exact_accuracy": m["exact_accuracy"],
                "prediction_coverage": m["prediction_coverage"],
                "abstentions": m["abstentions"],
            }
        evidence_profile = Counter()
        for row in field_rows:
            if row["evidence_question_present"] and row["evidence_answer_present"]:
                evidence_profile["question_and_answer_present"] += 1
            elif row["evidence_question_present"]:
                evidence_profile["question_without_answer"] += 1
            elif row["evidence_answer_present"]:
                evidence_profile["answer_without_question"] += 1
            else:
                evidence_profile["no_matched_question_or_answer"] += 1
        present_gold_support_by_field = dict(Counter(
            row["field"] for row in field_rows if row["gold"] == "PRESENT"
        ))
        unknown_predictions_with_evidence = sum(
            row["prediction"] == "UNKNOWN" and
            (row["evidence_question_present"] or row["evidence_answer_present"])
            for row in field_rows
        )
        result = {
            "matched_case_count": len(common_ids),
            "ground_truth_case_count": len(gt_files),
            "generated_form_case_count": len(pred_files),
            "unmatched_ground_truth_count": unmatched_gt,
            "unmatched_generated_form_count": unmatched_pred,
            "assertion_field_count_per_case": len(ASSERTION_FIELDS),
            "assertion_metrics": metrics,
            "present_gold_support_by_field": present_gold_support_by_field,
            "evidence_profile": dict(evidence_profile),
            "unknown_predictions_with_evidence": unknown_predictions_with_evidence,
            "per_field": per_field,
            "numeric_metrics": numeric_metrics(numeric_rows),
            "numeric_comparison_count": len(numeric_rows),
        }
        return result, field_rows, numeric_rows

    def evaluate_ner(self) -> Dict[str, Any]:
        """Score only manually completed independent gold annotations."""
        completed = []
        pending_count = 0
        invalid_count = 0
        for ner_path in sorted(glob.glob(os.path.join(self.ner_dir, "*_ner.json"))):
            case_id = os.path.basename(ner_path)[:-9]  # remove _ner.json
            gold_path = os.path.join(self.annotations_dir, f"{case_id}_gold.json")
            if not os.path.exists(gold_path):
                pending_count += 1
                continue
            gold_doc = load_json(gold_path)
            if gold_doc.get("annotation_status") != "complete":
                pending_count += 1
                continue
            try:
                pred_doc = load_json(ner_path)
                text = str(gold_doc.get("transcript_text", ""))
                gold_ents = set()
                for item in gold_doc.get("annotations", []):
                    start, end = int(item["start"]), int(item["end"])
                    etype = str(item["entity_type"]).upper()
                    assertion = normalize_prediction(item.get("assertion", "UNKNOWN"))
                    if start < 0 or end <= start or end > len(text):
                        raise ValueError("Annotation span is out of bounds")
                    if item.get("text") and text[start:end] != item["text"]:
                        raise ValueError("Annotation text does not match transcript offsets")
                    gold_ents.add((start, end, etype, assertion))
                pred_ents = set()
                for item in pred_doc.get("entities", []):
                    try:
                        start, end = int(item["start"]), int(item["end"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    pred_ents.add((start, end, str(item.get("entity_type", "")).upper(),
                                   normalize_prediction(item.get("assertion", "UNKNOWN"))))
                completed.append((gold_ents, pred_ents))
            except (ValueError, KeyError, TypeError):
                invalid_count += 1

        if not completed:
            return {
                "available": False,
                "reason": "No independently annotated case is marked annotation_status='complete'. NER and assertion performance metrics cannot yet be calculated.",
                "completed_annotation_cases": 0,
                "pending_or_missing_annotation_cases": pending_count,
                "invalid_annotation_cases": invalid_count,
            }

        # Entity identification is scored without assertion in the entity key.
        tp = fp = fn = 0
        assertion_pairs: List[Tuple[str, str]] = []
        for gold, pred in completed:
            gold_keys = {(s, e, t) for s, e, t, _ in gold}
            pred_keys = {(s, e, t) for s, e, t, _ in pred}
            tp += len(gold_keys & pred_keys)
            fp += len(pred_keys - gold_keys)
            fn += len(gold_keys - pred_keys)
            pred_assertions = {(s, e, t): a for s, e, t, a in pred}
            for s, e, t, gold_assert in gold:
                if (s, e, t) in pred_assertions:
                    assertion_pairs.append((gold_assert, pred_assertions[(s, e, t)]))
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        f1 = _safe_div(2 * tp, 2 * tp + fp + fn)
        return {
            "available": True,
            "completed_annotation_cases": len(completed),
            "pending_or_missing_annotation_cases": pending_count,
            "invalid_annotation_cases": invalid_count,
            "entity_exact_span_type": {
                "true_positive": tp, "false_positive": fp, "false_negative": fn,
                "precision": precision, "recall": recall, "f1": f1,
            },
            "assertion_on_exact_entity_matches": classification_metrics(assertion_pairs),
            "note": "Exact span-and-type evaluation against human annotations; assertion scores only matched entities.",
        }

    def state_distribution(self, forms_dir: str) -> Dict[str, Any]:
        counts = Counter()
        cases = 0
        for path in sorted(glob.glob(os.path.join(forms_dir, "*_form.json"))):
            try:
                form = load_json(path)
            except (OSError, ValueError):
                continue
            cases += 1
            for spec in ASSERTION_FIELDS:
                counts[get_prediction(form, spec)] += 1
        return {"case_count": cases, "field_slots": sum(counts.values()), "state_counts": dict(counts)}

    def run(self) -> Dict[str, Any]:
        os.makedirs(self.output_dir, exist_ok=True)
        field_metrics, field_rows, numeric_rows = self.evaluate_fields()
        ner_metrics = self.evaluate_ner()
        summary: Dict[str, Any] = {
            "evaluation_version": "M4-1.0",
            "metric_scope": "four-state clinical-field agreement plus independently annotated NER",
            "not_a_clinical_validation": True,
            "field_evaluation": field_metrics,
            "ner_evaluation": ner_metrics,
            "baseline_output_state_audit": None,
            "limitations": [
                "The supplied reference set is small and only matching case IDs are compared.",
                "The 11 symptom fields in the supplied reference records are all ABSENT; positive-case sensitivity cannot be estimated from this set.",
                "NER precision/recall/F1 are unavailable until independent gold annotations are completed.",
                "Structured-form agreement does not establish clinical safety or diagnostic performance.",
                "Every generated clinical record requires qualified human review.",
            ],
        }
        if self.baseline_forms_dir and os.path.isdir(self.baseline_forms_dir):
            summary["baseline_output_state_audit"] = {
                "baseline": self.state_distribution(self.baseline_forms_dir),
                "current": self.state_distribution(self.forms_dir),
                "interpretation": "Descriptive output-state distribution only; not an accuracy comparison. A shift from ABSENT to UNKNOWN reflects abstention behavior and must be reviewed against source evidence.",
            }

        report_path = os.path.join(self.output_dir, "M4_EVALUATION_REPORT.md")
        json_path = os.path.join(self.output_dir, "m4_evaluation_summary.json")
        errors_path = os.path.join(self.output_dir, "field_level_comparisons.json")
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)
        with open(errors_path, "w", encoding="utf-8") as handle:
            json.dump({"assertion_fields": field_rows, "numeric_fields": numeric_rows}, handle, indent=2)
        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write(self.render_report(summary, field_rows, numeric_rows))
        summary["report_path"] = report_path
        summary["summary_path"] = json_path
        return summary

    @staticmethod
    def _pct(value: Optional[float]) -> str:
        return "N/A" if value is None else f"{value * 100:.1f}%"

    def render_report(self, summary: Dict[str, Any], field_rows: List[Dict[str, Any]],
                      numeric_rows: List[Dict[str, Any]]) -> str:
        f = summary["field_evaluation"]
        m = f["assertion_metrics"]
        lines = [
            "# M4 Evaluation & Optimization Report",
            "",
            "> **Scope warning:** This is a preliminary academic evaluation of structured field agreement, not clinical validation or diagnostic accuracy. Do not use it for clinical decisions.",
            "",
            "## 1. Dataset coverage",
            "",
            f"- Ground-truth records: **{f['ground_truth_case_count']}**",
            f"- Generated forms: **{f['generated_form_case_count']}**",
            f"- Matching case pairs: **{f['matched_case_count']}**",
            f"- Unmatched reference records: **{f['unmatched_ground_truth_count']}**",
            f"- Unmatched generated forms: **{f['unmatched_generated_form_count']}**",
            f"- Assertion fields mapped per matched case: **{f['assertion_field_count_per_case']}**",
            "",
            "## 2. Four-state assertion agreement",
            "",
            f"- Scorable fields (gold not UNKNOWN): **{m['n_scorable']}**",
            f"- Exact matches: **{m['correct']}**",
            f"- Exact four-state accuracy: **{self._pct(m['exact_accuracy'])}**",
            f"- Prediction coverage (non-UNKNOWN predictions): **{self._pct(m['prediction_coverage'])}**",
            f"- Accuracy among non-abstained predictions: **{self._pct(m['selective_accuracy'])}**",
            f"- Model abstentions on scorable fields: **{m['abstentions']}**",
            f"- Gold class support: `{json.dumps(m['gold_class_support'], sort_keys=True)}`",
            f"- PRESENT gold support by field: `{json.dumps(f['present_gold_support_by_field'], sort_keys=True)}`",
            f"- PRESENT sensitivity: **{self._pct(m['present_sensitivity'])}** on {m['per_class']['PRESENT']['support']} PRESENT reference fields" if m["present_sensitivity_available"] else "- PRESENT sensitivity: **Not estimable** (no PRESENT gold examples).",
            "- Important: the PRESENT examples are not positive symptom examples; all 11 symptom reference fields are ABSENT in this dataset.",
            "",
            "### Per-class precision, recall and F1",
            "",
            "| Class | Gold support | Predicted count | Precision | Recall | F1 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for label in LABELS:
            v = m["per_class"][label]
            lines.append(f"| {label} | {v['support']} | {v['predicted_count']} | {self._pct(v['precision'])} | {self._pct(v['recall'])} | {self._pct(v['f1'])} |")
        lines += [
            f"- Macro F1 over classes represented in the reference set: **{self._pct(m['macro_f1_over_supported_gold_classes'])}** (class support is highly imbalanced).",
            "",
            "### Confusion matrix (rows = reference, columns = prediction)",
            "",
            "| Gold \\ Predicted | PRESENT | ABSENT | POSSIBLE | UNKNOWN |",
            "|---|---:|---:|---:|---:|",
        ]
        for label in LABELS:
            row = m["confusion_matrix"][label]
            lines.append(f"| {label} | {row['PRESENT']} | {row['ABSENT']} | {row['POSSIBLE']} | {row['UNKNOWN']} |")
        lines += ["", "### Per-field results", "", "| Field | Scorable support | Exact matches | Exact agreement | Prediction coverage | Abstentions |", "|---|---:|---:|---:|---:|---:|"]
        for label, values in f["per_field"].items():
            lines.append(f"| {label} | {values['n_scorable']} | {values['correct']} | {self._pct(values['exact_accuracy'])} | {self._pct(values['prediction_coverage'])} | {values['abstentions']} |")
        provenance = f["evidence_profile"]
        lines += [
            "",
            "### Evidence / abstention audit",
            "",
            f"- Fields with both matched question and non-empty answer evidence: **{provenance.get('question_and_answer_present', 0)}**",
            f"- Fields with neither matched question nor answer evidence: **{provenance.get('no_matched_question_or_answer', 0)}**",
            f"- UNKNOWN predictions that nevertheless had question/answer evidence: **{f['unknown_predictions_with_evidence']}**",
            "- In this run, an UNKNOWN prediction is therefore distinguishable from an explicit negative: it is an abstention where the form-population step did not identify a usable answer.",
            "",
            "## 3. Numeric field evaluation",
            "",
        ]
        if f["numeric_metrics"]:
            lines += ["| Field | Support | MAE | Exact agreement | Within tolerance | Tolerance |", "|---|---:|---:|---:|---:|---:|"]
            for label, v in f["numeric_metrics"].items():
                lines.append(f"| {label} | {v['support']} | {v['mae']:.3f} | {self._pct(v['exact_agreement'])} | {self._pct(v['within_tolerance_rate'])} ({v['within_tolerance_count']}/{v['support']}) | {v['tolerance']} |")
        else:
            lines.append("No numeric fields had both reference and prediction values.")
        lines += ["", "## 4. NER and assertion evaluation", ""]
        ner = summary["ner_evaluation"]
        if ner.get("available"):
            e = ner["entity_exact_span_type"]
            lines += [
                f"- Completed independently annotated cases: **{ner['completed_annotation_cases']}**",
                f"- Entity exact-span/type precision: **{self._pct(e['precision'])}**",
                f"- Entity exact-span/type recall: **{self._pct(e['recall'])}**",
                f"- Entity exact-span/type F1: **{self._pct(e['f1'])}**",
                f"- Assertion evaluation on exact matched entities: **{self._pct(ner['assertion_on_exact_entity_matches']['exact_accuracy'])}**",
            ]
        else:
            lines.append(f"**Not yet available.** {ner['reason']}")
        lines += ["", "## 5. Baseline versus M3 output audit", ""]
        audit = summary.get("baseline_output_state_audit")
        if audit:
            for name in ("baseline", "current"):
                item = audit[name]
                lines.append(f"- {name.capitalize()} output: {item['case_count']} cases, {item['field_slots']} assertion slots, state counts `{json.dumps(item['state_counts'], sort_keys=True)}`.")
            lines.append("")
            lines.append(audit["interpretation"])
        else:
            lines.append("No baseline forms directory supplied; run with --baseline-forms-dir to add a descriptive state-distribution audit.")
        lines += ["", "## 6. Failure analysis and interpretation", "", "- UNKNOWN reference labels are excluded from classification denominators.", "- A predicted UNKNOWN for a known reference label is counted as an abstention and as a non-match; it is never converted to ABSENT.", "- The supplied symptom reference fields contain only ABSENT labels. This set cannot estimate positive symptom recall/sensitivity or performance on POSSIBLE cases.", "- Field-level errors are saved separately in `field_level_comparisons.json` using anonymized case labels and assertion states only.", "- NER metrics require independent span/type/assertion annotation; model-generated entities must not be reused as gold labels.", "", "## 7. Limitations and next steps", ""]
        for item in summary["limitations"]:
            lines.append(f"- {item}")
        lines += ["", "### Required next steps", "", "1. Resolve unmatched reference/form IDs before expanding the benchmark.", "2. Have two reviewers independently annotate a representative set of transcript entity spans and assertions; adjudicate disagreements.", "3. Add positive and uncertain examples, not only negative symptom examples.", "4. Inspect every field mismatch against the source audio and transcript.", "5. Run the same fixed test set before and after each optimization, and report support alongside all metrics.", ""]
        return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run M4 evaluation for the clinical report-generation pipeline.")
    parser.add_argument("--ground-truth-dir", default="outputs/ground_truth")
    parser.add_argument("--forms-dir", default="outputs/forms")
    parser.add_argument("--ner-dir", default="outputs/ner")
    parser.add_argument("--annotations-dir", default="outputs/annotations")
    parser.add_argument("--output-dir", default="outputs/eval/m4")
    parser.add_argument("--baseline-forms-dir", default=None)
    args = parser.parse_args()
    summary = M4Evaluator(args.ground_truth_dir, args.forms_dir, args.ner_dir,
                          args.annotations_dir, args.output_dir,
                          args.baseline_forms_dir).run()
    metrics = summary["field_evaluation"]["assertion_metrics"]
    print("M4 evaluation complete.")
    print(f"Matched case pairs: {summary['field_evaluation']['matched_case_count']}")
    print(f"Four-state field exact agreement: {M4Evaluator._pct(metrics['exact_accuracy'])}")
    print(f"Prediction coverage: {M4Evaluator._pct(metrics['prediction_coverage'])}")
    print(f"NER metrics available: {summary['ner_evaluation'].get('available', False)}")
    print(f"Report: {summary['report_path']}")


if __name__ == "__main__":
    main()
