#!/usr/bin/env python3
"""Compare NER systems: rule/lexicon (this project) vs learned baselines.

    python src/compare_ner_systems.py

Systems compared (each a directory of <case>_ner.json files):
  * Rule/lexicon (project)   outputs/ner
  * GLiNER zero-shot         outputs/baselines/gliner   (from baselines/gliner_baseline.py)

Two views are reported:
  1. Against completed human gold annotations (strict and lenient P/R/F1), when
     outputs/annotations/<case>_gold.json files are marked complete.
  2. Without gold: how much the systems agree with each other (overlap F1), and the
     entity counts per type. This is descriptive, not an accuracy measure.

Writes outputs/eval/ner_system_comparison.md
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

try:
    from src.evaluate_m4 import M4Evaluator
except ImportError:
    from evaluate_m4 import M4Evaluator

SYSTEMS = {
    "Rule/lexicon (project)": ROOT / "outputs" / "ner",
    "GLiNER zero-shot": ROOT / "outputs" / "baselines" / "gliner",
}
REPORT = ROOT / "outputs" / "eval" / "ner_system_comparison.md"


def pct(value: Optional[float]) -> str:
    return "N/A" if value is None else f"{value * 100:.1f}%"


def load_entities(directory: Path) -> Dict[str, List[dict]]:
    result = {}
    for path in sorted(glob.glob(str(directory / "*_ner.json"))):
        with open(path, encoding="utf-8") as handle:
            result[os.path.basename(path)[:-9]] = json.load(handle).get("entities", [])
    return result


def overlap_f1(a: List[dict], b: List[dict]) -> Optional[float]:
    used, matched = set(), 0
    for x in a:
        for i, y in enumerate(b):
            if i not in used and x["entity_type"] == y["entity_type"] and x["start"] < y["end"] and y["start"] < x["end"]:
                used.add(i)
                matched += 1
                break
    return (2 * matched / (len(a) + len(b))) if (a or b) else None


def main() -> None:
    available = {name: d for name, d in SYSTEMS.items() if glob.glob(str(d / "*_ner.json"))}
    lines = ["# NER system comparison", ""]
    missing = [name for name in SYSTEMS if name not in available]
    if missing:
        lines += [f"Not yet run: {', '.join(missing)}. See `baselines/gliner_baseline.py` (run on Kaggle/Colab).", ""]

    lines += ["## 1. Against human gold annotations", ""]
    gold_rows = []
    for name, directory in available.items():
        result = M4Evaluator(ner_dir=str(directory), annotations_dir=str(ROOT / "outputs" / "annotations")).evaluate_ner()
        if result.get("available"):
            s, l = result["entity_exact_span_type"], result["entity_lenient_overlap_type"]
            gold_rows.append(f"| {name} | {result['completed_annotation_cases']} | {pct(s['precision'])} | {pct(s['recall'])} | {pct(s['f1'])} | {pct(l['precision'])} | {pct(l['recall'])} | {pct(l['f1'])} |")
    if gold_rows:
        lines += ["| System | Gold cases | Strict P | Strict R | Strict F1 | Lenient P | Lenient R | Lenient F1 |", "|---|---:|---:|---:|---:|---:|---:|---:|"] + gold_rows
    else:
        lines.append("No completed gold annotations yet. Annotate with `web/annotate.html`, then run `python src/annotation_agreement.py` and adjudicate.")

    lines += ["", "## 2. Descriptive comparison (no gold needed)", ""]
    entities = {name: load_entities(d) for name, d in available.items()}
    types = Counter()
    per_system_types = {}
    for name, cases in entities.items():
        counts = Counter(e["entity_type"] for ents in cases.values() for e in ents)
        per_system_types[name] = counts
        types.update(counts)
    names = list(entities)
    lines += ["| Entity type | " + " | ".join(names) + " |", "|---|" + "---:|" * len(names)]
    for etype, _ in types.most_common():
        lines.append(f"| {etype} | " + " | ".join(str(per_system_types[n][etype]) for n in names) + " |")
    if len(names) >= 2:
        a, b = names[0], names[1]
        shared = sorted(set(entities[a]) & set(entities[b]))
        lines += ["", f"Overlap F1 between **{a}** and **{b}** (same type, overlapping span), per case:", ""]
        for case_id in shared:
            lines.append(f"- {case_id}: {pct(overlap_f1(entities[a][case_id], entities[b][case_id]))}")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
