#!/usr/bin/env python3
"""Inter-annotator agreement and adjudication for NER gold annotations.

Workflow
--------
1. ``python src/prepare_annotations.py``          -> blank ``<case>_gold.json`` templates
2. Two people annotate independently in ``web/annotate.html`` and save
   ``outputs/annotations/<case>_r1.json`` and ``<case>_r2.json``.
3. ``python src/annotation_agreement.py``         -> agreement report + merged files
   Agreed annotations are copied into ``<case>_gold.json``; disagreements are listed
   in that file for adjudication.
4. Load ``<case>_gold.json`` in ``web/annotate.html``, resolve every disagreement,
   download, and replace the file. When no disagreements remain the status becomes
   ``complete`` and ``python src/evaluate_m4.py`` reports NER precision/recall/F1.

Agreement measures
------------------
* Pairwise span F1 (strict = same span and type; lenient = overlapping span, same
  type). For span annotation Cohen's kappa is ill-defined because the number of
  "non-entity" units is unbounded, so pairwise F1 is the standard measure
  (Hripcsak & Rothschild, 2005).
* Cohen's kappa on entity type, over spans that both annotators marked.
* Cohen's kappa on assertion, over spans both annotators marked with the same type.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Tuple

Ann = Dict[str, Any]


def cohen_kappa(pairs: Sequence[Tuple[str, str]]) -> Optional[float]:
    """Cohen's kappa for two raters over the same items."""
    n = len(pairs)
    if not n:
        return None
    observed = sum(1 for a, b in pairs if a == b) / n
    count_a = Counter(a for a, _ in pairs)
    count_b = Counter(b for _, b in pairs)
    expected = sum(count_a[label] * count_b[label] for label in set(count_a) | set(count_b)) / (n * n)
    if expected == 1:
        return 1.0 if observed == 1 else 0.0
    return (observed - expected) / (1 - expected)


def _f1(matched: int, total_a: int, total_b: int) -> Optional[float]:
    return (2 * matched / (total_a + total_b)) if (total_a + total_b) else None


def _overlaps(a: Ann, b: Ann) -> bool:
    return a["start"] < b["end"] and b["start"] < a["end"]


def compare(anns_a: List[Ann], anns_b: List[Ann]) -> Dict[str, Any]:
    key = lambda a: (a["start"], a["end"], a["entity_type"])
    strict_a = {key(a): a for a in anns_a}
    strict_b = {key(b): b for b in anns_b}
    strict_match = len(set(strict_a) & set(strict_b))

    lenient_match = 0
    used = set()
    for a in anns_a:
        for i, b in enumerate(anns_b):
            if i not in used and a["entity_type"] == b["entity_type"] and _overlaps(a, b):
                used.add(i)
                lenient_match += 1
                break

    spans_a = {(a["start"], a["end"]): a for a in anns_a}
    spans_b = {(b["start"], b["end"]): b for b in anns_b}
    shared_spans = set(spans_a) & set(spans_b)
    type_pairs = [(spans_a[s]["entity_type"], spans_b[s]["entity_type"]) for s in shared_spans]
    assertion_pairs = [(strict_a[k]["assertion"], strict_b[k]["assertion"]) for k in set(strict_a) & set(strict_b)]

    return {
        "annotator_a_count": len(anns_a),
        "annotator_b_count": len(anns_b),
        "strict_matches": strict_match,
        "strict_f1": _f1(strict_match, len(anns_a), len(anns_b)),
        "lenient_matches": lenient_match,
        "lenient_f1": _f1(lenient_match, len(anns_a), len(anns_b)),
        "shared_spans": len(shared_spans),
        "entity_type_kappa": cohen_kappa(type_pairs),
        "assertion_pairs": len(assertion_pairs),
        "assertion_kappa": cohen_kappa(assertion_pairs),
        "assertion_raw_agreement": (sum(a == b for a, b in assertion_pairs) / len(assertion_pairs)) if assertion_pairs else None,
    }


def merge(doc_a: Dict[str, Any], doc_b: Dict[str, Any]) -> Dict[str, Any]:
    """Keep fully agreed annotations; list everything else for adjudication."""
    key = lambda a: (a["start"], a["end"], a["entity_type"], a["assertion"])
    by_a = {key(a): a for a in doc_a.get("annotations", [])}
    by_b = {key(b): b for b in doc_b.get("annotations", [])}
    agreed = [by_a[k] for k in sorted(set(by_a) & set(by_b))]
    only_a = [by_a[k] for k in sorted(set(by_a) - set(by_b))]
    only_b = [by_b[k] for k in sorted(set(by_b) - set(by_a))]

    disagreements = []
    remaining_b = list(only_b)
    for a in only_a:
        partner = next((b for b in remaining_b if _overlaps(a, b)), None)
        if partner is not None:
            remaining_b.remove(partner)
        disagreements.append({"annotator_a": a, "annotator_b": partner})
    disagreements += [{"annotator_a": None, "annotator_b": b} for b in remaining_b]

    merged = {k: v for k, v in doc_a.items() if k not in ("annotations", "annotator_id")}
    merged.update({
        "reviewer_1": doc_a.get("annotator_id", "A"),
        "reviewer_2": doc_b.get("annotator_id", "B"),
        "annotations": agreed,
        "disagreements": disagreements,
        "annotation_status": "complete" if not disagreements else "needs_adjudication",
        "adjudication_complete": not disagreements,
    })
    return merged


def _pct(value: Optional[float]) -> str:
    return "N/A" if value is None else f"{value * 100:.1f}%"


def _num(value: Optional[float]) -> str:
    return "N/A" if value is None else f"{value:.3f}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute inter-annotator agreement and prepare adjudication files.")
    parser.add_argument("--dir", default="outputs/annotations")
    parser.add_argument("--a", default="r1", help="Suffix of annotator A files (default r1)")
    parser.add_argument("--b", default="r2", help="Suffix of annotator B files (default r2)")
    parser.add_argument("--report", default="outputs/eval/annotation_agreement.md")
    parser.add_argument("--no-merge", action="store_true", help="Only report agreement; do not write <case>_gold.json")
    args = parser.parse_args()

    results = {}
    for path_a in sorted(glob.glob(os.path.join(args.dir, f"*_{args.a}.json"))):
        case_id = os.path.basename(path_a)[: -len(f"_{args.a}.json")]
        path_b = os.path.join(args.dir, f"{case_id}_{args.b}.json")
        if not os.path.exists(path_b):
            print(f"[!] {case_id}: missing {os.path.basename(path_b)}; skipped")
            continue
        with open(path_a, encoding="utf-8") as fa, open(path_b, encoding="utf-8") as fb:
            doc_a, doc_b = json.load(fa), json.load(fb)
        if doc_a.get("transcript_text") != doc_b.get("transcript_text"):
            print(f"[!] {case_id}: annotators used different transcript text; skipped")
            continue
        results[case_id] = compare(doc_a.get("annotations", []), doc_b.get("annotations", []))
        if not args.no_merge:
            gold_path = os.path.join(args.dir, f"{case_id}_gold.json")
            existing = {}
            if os.path.exists(gold_path):
                with open(gold_path, encoding="utf-8") as handle:
                    existing = json.load(handle)
            if existing.get("annotation_status") == "complete":
                print(f"[=] {case_id}: gold already adjudicated; not overwritten")
            else:
                merged = merge(doc_a, doc_b)
                with open(gold_path, "w", encoding="utf-8") as handle:
                    json.dump(merged, handle, ensure_ascii=False, indent=2)
                print(f"[✓] {case_id}: {len(merged['annotations'])} agreed, {len(merged['disagreements'])} to adjudicate -> {gold_path}")

    if not results:
        print("No annotator pairs found. Expected files like outputs/annotations/<case>_r1.json and <case>_r2.json.")
        return

    pooled_a = sum(r["annotator_a_count"] for r in results.values())
    pooled_b = sum(r["annotator_b_count"] for r in results.values())
    pooled = {
        "strict_f1": _f1(sum(r["strict_matches"] for r in results.values()), pooled_a, pooled_b),
        "lenient_f1": _f1(sum(r["lenient_matches"] for r in results.values()), pooled_a, pooled_b),
    }
    lines = ["# Inter-annotator agreement", "",
             "Pairwise F1 treats one annotator as reference (it is symmetric). Kappa values: <0.40 poor, 0.40-0.60 moderate, 0.60-0.80 substantial, >0.80 near-perfect (Landis & Koch, 1977).", "",
             "| Case | A | B | Strict F1 | Lenient F1 | Type kappa | Assertion kappa |", "|---|---:|---:|---:|---:|---:|---:|"]
    for case_id, r in results.items():
        lines.append(f"| {case_id} | {r['annotator_a_count']} | {r['annotator_b_count']} | {_pct(r['strict_f1'])} | {_pct(r['lenient_f1'])} | {_num(r['entity_type_kappa'])} | {_num(r['assertion_kappa'])} |")
    lines.append(f"| **Pooled** | {pooled_a} | {pooled_b} | **{_pct(pooled['strict_f1'])}** | **{_pct(pooled['lenient_f1'])}** | | |")
    os.makedirs(os.path.dirname(args.report), exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    with open(os.path.splitext(args.report)[0] + ".json", "w", encoding="utf-8") as handle:
        json.dump({"cases": results, "pooled": pooled}, handle, indent=2)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
