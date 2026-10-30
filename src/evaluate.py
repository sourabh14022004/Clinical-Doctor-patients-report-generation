#!/usr/bin/env python3
"""
Pipeline Evaluation and Ground-Truth Validation Module
Benchmarks audio-extracted clinical records against ground-truth OCR forms.
Calculates field accuracy, assertion correctness, and generates evaluation metrics.
"""

import json
import os
import glob
from typing import Dict, List, Any, Tuple


class PipelineEvaluator:
    """
    Evaluates extracted clinical records against ground-truth scanned clinic records.
    """

    def __init__(self, ground_truth_dir: str = "outputs/ground_truth", forms_dir: str = "outputs/forms"):
        self.gt_dir = ground_truth_dir
        self.forms_dir = forms_dir

    def evaluate_patient(self, patient_id: str) -> Dict[str, Any]:
        gt_path = os.path.join(self.gt_dir, f"{patient_id}.json")
        form_path = os.path.join(self.forms_dir, f"{patient_id}_form.json")

        if not os.path.exists(gt_path) or not os.path.exists(form_path):
            return {"error": f"Missing files for {patient_id}"}

        with open(gt_path, "r", encoding="utf-8") as f:
            gt = json.load(f)
        with open(form_path, "r", encoding="utf-8") as f:
            pred = json.load(f)

        demo = pred.get("demographics", {})
        clin = pred.get("clinical_indicators", {})
        hist = pred.get("history", {})
        risk = pred.get("risk_factors", {})
        gen = pred.get("general_cancer_symptoms", {})
        oral = pred.get("oral_cancer_screening", {})

        comparisons = []

        # 1. Demographics
        comparisons.append(self._compare_field("Age", gt.get("age"), demo.get("age"), is_numeric=True))
        comparisons.append(self._compare_field("Sex", gt.get("sex"), demo.get("sex"), is_categorical=True))
        comparisons.append(self._compare_field("Marital Status", gt.get("marital_status"), demo.get("marital_status"), is_categorical=True))
        comparisons.append(self._compare_field("Insurance", gt.get("health_insurance"), demo.get("health_insurance"), is_substring=True))

        # 2. Vitals
        comparisons.append(self._compare_field("Weight (kg)", gt.get("weight_kg"), clin.get("weight_kg"), is_numeric=True, tol=2.0))

        # 3. Medical History & Cancer Family History
        fam_gt = "yes" in str(gt.get("family_history_cancer", "")).lower()
        fam_pred = hist.get("family_history_of_cancer", {}).get("present", False)
        comparisons.append({
            "field": "Family History of Cancer",
            "ground_truth": str(gt.get("family_history_cancer")),
            "extracted": "YES" if fam_pred else "NO",
            "match": fam_gt == fam_pred
        })

        # 4. Lifestyle & Risk
        tob_gt = "yes" in str(gt.get("current_tobacco", "")).lower()
        tob_pred = risk.get("current_tobacco_use", {}).get("current_user", False)
        comparisons.append({
            "field": "Current Tobacco Use",
            "ground_truth": "YES" if tob_gt else "NO",
            "extracted": "YES" if tob_pred else "NO",
            "match": tob_gt == tob_pred
        })

        # 5. General Cancer Warning Signs (all 7)
        symptoms_map = [
            ("Unexplained Weight Loss", "unexplained_weight_loss", "unexplained_weight_loss"),
            ("Persistent Fever / Fatigue", "persistent_fever_fatigue", "persistent_fever_or_fatigue"),
            ("Non-healing Ulcer / Wound", "non_healing_ulcer", "non_healing_ulcer_or_wound"),
            ("Lump / Swelling in Body", "lump_swelling", "lump_or_swelling_anywhere"),
            ("Persistent Pain", "persistent_pain", "persistent_pain_without_known_cause"),
            ("Bleeding from Any Site", "bleeding", "bleeding_from_any_site"),
            ("Known Chronic Illness", "chronic_illness", "known_chronic_illness_dm_htn_tb"),
        ]

        for label, gt_k, pred_k in symptoms_map:
            g_val = "yes" in str(gt.get(gt_k, "")).lower()
            p_val = gen.get(pred_k, {}).get("reported", False)
            comparisons.append({
                "field": f"General Symptom: {label}",
                "ground_truth": "YES" if g_val else "NO",
                "extracted": "YES" if p_val else "NO",
                "match": g_val == p_val
            })

        # 6. Oral Cancer Criteria (all 4)
        oral_map = [
            ("Oral: Difficulty Opening Mouth", "oral_difficulty_opening_mouth", "difficulty_in_opening_mouth"),
            ("Oral: White / Red Patch", "oral_patch", "white_or_red_patch_in_mouth"),
            ("Oral: Ulcer > 2 Weeks", "oral_ulcer_gt_2w", "ulcer_in_mouth_lasting_gt_2_weeks"),
            ("Oral: Chewing / Swallowing Difficulty", "oral_difficulty_chewing_swallowing", "difficulty_in_chewing_or_swallowing")
        ]

        for label, gt_k, pred_k in oral_map:
            g_val = "yes" in str(gt.get(gt_k, "")).lower()
            p_val = oral.get(pred_k, {}).get("reported", False)
            comparisons.append({
                "field": label,
                "ground_truth": "YES" if g_val else "NO",
                "extracted": "YES" if p_val else "NO",
                "match": g_val == p_val
            })

        total = len(comparisons)
        matches = sum(1 for c in comparisons if c["match"])
        accuracy = round(matches / total * 100, 1)

        return {
            "patient_id": patient_id,
            "total_fields_evaluated": total,
            "matched_fields": matches,
            "accuracy_percent": accuracy,
            "field_comparisons": comparisons
        }

    def _compare_field(
        self,
        name: str,
        gt_val: Any,
        pred_val: Any,
        is_numeric: bool = False,
        is_categorical: bool = False,
        is_substring: bool = False,
        tol: float = 0.0
    ) -> Dict[str, Any]:
        match = False
        if is_numeric and gt_val is not None and pred_val is not None:
            try:
                match = abs(float(gt_val) - float(pred_val)) <= tol
            except Exception:
                match = False
        elif is_categorical and gt_val and pred_val:
            match = str(gt_val).strip().lower() == str(pred_val).strip().lower()
        elif is_substring and gt_val and pred_val:
            match = (str(gt_val).strip().lower() in str(pred_val).strip().lower() or
                     str(pred_val).strip().lower() in str(gt_val).strip().lower())
        else:
            match = str(gt_val).strip().lower() == str(pred_val).strip().lower()

        return {
            "field": name,
            "ground_truth": str(gt_val),
            "extracted": str(pred_val),
            "match": match
        }

    def evaluate_all(self) -> Dict[str, Any]:
        os.makedirs("outputs/eval", exist_ok=True)
        results = []
        gt_files = sorted(glob.glob(os.path.join(self.gt_dir, "*.json")))

        for gtf in gt_files:
            pid = os.path.splitext(os.path.basename(gtf))[0]
            res = self.evaluate_patient(pid)
            if "error" not in res:
                results.append(res)

        total_evaluated = sum(r["total_fields_evaluated"] for r in results)
        total_matches = sum(r["matched_fields"] for r in results)
        overall_acc = round(total_matches / total_evaluated * 100, 1) if total_evaluated > 0 else 0.0

        summary = {
            "overall_accuracy_percent": overall_acc,
            "total_evaluated_fields": total_evaluated,
            "total_matched_fields": total_matches,
            "patient_benchmarks": results
        }

        # Save summary JSON
        with open("outputs/eval/evaluation_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        # Generate Evaluation Report Markdown
        report_md = f"""# Clinical Pipeline Evaluation Report
## Benchmarking Extracted Records Against Ground-Truth Clinical Forms (GIMS)

**Overall Form Field Accuracy:** **{overall_acc}%**  
**Total Ground-Truth Fields Evaluated:** **{total_evaluated}**  
**Total Accurately Populated Fields:** **{total_matches}**

---

### Patient-Level Accuracy Summary
| Patient | Fields Evaluated | Correctly Matched | Accuracy (%) |
|---|---|---|---|
"""
        for r in results:
            report_md += f"| **{r['patient_id']}** | {r['total_fields_evaluated']} | {r['matched_fields']} | **{r['accuracy_percent']}%** |\n"

        report_md += "\n---\n\n### Detailed Field-Level Breakdown\n"
        for r in results:
            report_md += f"\n#### Patient: {r['patient_id']}\n"
            report_md += "| Clinical Field | Ground Truth Form | Speech-Extracted Record | Concordance |\n"
            report_md += "|---|---|---|---|\n"
            for c in r["field_comparisons"]:
                status = "✅ MATCH" if c["match"] else "⚠️ DISCREPANCY"
                report_md += f"| {c['field']} | `{c['ground_truth']}` | `{c['extracted']}` | {status} |\n"

        with open("outputs/eval/evaluation_report.md", "w", encoding="utf-8") as f:
            f.write(report_md)

        return summary


if __name__ == "__main__":
    evaluator = PipelineEvaluator()
    summary = evaluator.evaluate_all()
    print(f"Overall Accuracy: {summary.get('overall_accuracy_percent')}%")
