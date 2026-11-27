#!/usr/bin/env python3
"""Error-propagation analysis: at which pipeline stage was each answer lost?

    python src/error_analysis.py

For every scored form field the system left UNKNOWN although the reference has an
answer (an "abstention"), the field's topic is searched for in

  * the Hindi ASR transcript (phonetic matching, see alignment.py), and
  * the English Whisper translation,

and the form's own extraction evidence is checked. Each abstention is assigned to
the first stage that lost it:

  A. Lost in ASR (both transcripts): topic absent from Hindi and English text.
     Often a hallucinated / looping Hindi transcript.
  B. Lost in translation: topic present in Hindi but absent from English, typically
     because the English output is a repetition loop over that stretch of audio.
  C. Missed by question matching: topic present in English, but no question was
     matched for the field (paraphrase not covered by the keyword list).
  D. Answer not classified: a question was matched but its answer gave no clear
     yes / no / maybe.

Writes outputs/eval/error_analysis/error_analysis.md and .json.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

try:
    from src.alignment import HindiEnglishAligner, is_hallucinated
    from src.evaluate_m4 import ASSERTION_FIELDS, get_prediction, normalize_assertion
except ImportError:
    from alignment import HindiEnglishAligner, is_hallucinated
    from evaluate_m4 import ASSERTION_FIELDS, get_prediction, normalize_assertion

TRANSCRIPTS = ROOT / "outputs" / "transcripts"
FORMS = ROOT / "outputs" / "forms"
GROUND_TRUTH = ROOT / "outputs" / "ground_truth"
OUT_DIR = ROOT / "outputs" / "eval" / "error_analysis"

# Topic words per scored field: English (substring match) and Hindi (phonetic match).
TOPICS: Dict[str, Dict[str, List[str]]] = {
    "family_history_of_cancer": {"en": ["family", "at home", "anyone"], "hi": ["फैमिली", "परिवार", "घर"]},
    "consumed_tobacco_or_alcohol": {"en": ["tobacco", "alcohol"], "hi": ["तंबाकू", "शराब", "अल्कोहल"]},
    "current_tobacco_use": {"en": ["tobacco", "cigarette", "bidi", "gutkha"], "hi": ["तंबाकू", "बीड़ी", "सिगरेट", "गुटखा"]},
    "unexplained_weight_loss": {"en": ["weight"], "hi": ["वजन"]},
    "persistent_fever_or_fatigue": {"en": ["fever", "fatigue", "tired"], "hi": ["बुखार", "थकान", "कमजोरी"]},
    "non_healing_ulcer_or_wound": {"en": ["wound", "ulcer", "heal"], "hi": ["घाव", "छाला", "जख्म"]},
    "lump_or_swelling_anywhere": {"en": ["lump", "swelling"], "hi": ["गांठ", "सूजन"]},
    "persistent_pain_without_known_cause": {"en": ["pain", "ache"], "hi": ["दर्द"]},
    "bleeding_from_any_site": {"en": ["bleed", "blood"], "hi": ["खून", "ब्लीडिंग"]},
    "known_chronic_illness_dm_htn_tb": {"en": ["diabetes", "bp", "sugar", "illness"], "hi": ["बीमारी", "डायबिटीज", "बीपी", "शुगर"]},
    "difficulty_in_opening_mouth": {"en": ["opening", "open your mouth"], "hi": ["खोलने"]},
    "white_or_red_patch_in_mouth": {"en": ["patch", "white", "red"], "hi": ["सफेद", "लाल", "पैच"]},
    "ulcer_in_mouth_lasting_gt_2_weeks": {"en": ["mouth ulcer", "ulcer in", "wound in your mouth", "2 weeks", "two weeks"], "hi": ["छाला", "हफ्ते"]},
    "difficulty_in_chewing_or_swallowing": {"en": ["chew", "swallow"], "hi": ["चबाने", "निगलने"]},
}

STAGES = {
    "A": "Lost in ASR (absent from Hindi and English)",
    "B": "Lost in translation (in Hindi, not in English)",
    "C": "Missed by question matching (in English, no question matched)",
    "D": "Answer not classified (question matched, answer unclear)",
}


def read(path: Path) -> Dict[str, Any]:
    with open(path, encoding="utf-8", errors="replace") as handle:
        return json.load(handle)


def segments(case_id: str, lang: str) -> List[Dict[str, Any]]:
    path = TRANSCRIPTS / f"{case_id}_{lang}.json"
    return read(path).get("transcription", []) if path.exists() else []


def main() -> None:
    aligner = HindiEnglishAligner(lexicon={field: t["hi"] for field, t in TOPICS.items()})
    rows: List[Dict[str, Any]] = []
    case_ids = sorted(p.stem for p in GROUND_TRUTH.glob("*.json") if (FORMS / f"{p.stem}_form.json").exists())
    for case_id in case_ids:
        gold_doc, form = read(GROUND_TRUTH / f"{case_id}.json"), read(FORMS / f"{case_id}_form.json")
        en_text = " ".join(s.get("text", "") for s in segments(case_id, "en")).lower()
        hi_segments = [s for s in segments(case_id, "hi") if not is_hallucinated(str(s.get("text", "")))]
        hi_tokens = [t for s in hi_segments for t in re.findall(r"[ऀ-ॿ]+", str(s.get("text", "")))]
        for spec in ASSERTION_FIELDS:
            gold = normalize_assertion(gold_doc.get(spec.gold_key), parser=spec.parser)
            predicted = get_prediction(form, spec)
            if gold == "UNKNOWN" or predicted != "UNKNOWN":
                continue
            topic = TOPICS[spec.field]
            in_en = any(word in en_text for word in topic["en"])
            in_hi = any(aligner.word_matches(token, spec.field) >= aligner.match_threshold for token in hi_tokens)
            evidence = form.get("extraction_evidence", {}).get(f"{spec.section}.{spec.field}", {})
            if evidence.get("question"):
                stage = "D"
            elif in_en:
                stage = "C"
            elif in_hi:
                stage = "B"
            else:
                stage = "A"
            rows.append({"case": case_id, "field": spec.label, "gold": gold, "stage": stage,
                         "topic_in_hindi": in_hi, "topic_in_english": in_en})

    counts = Counter(r["stage"] for r in rows)
    by_case = defaultdict(Counter)
    for r in rows:
        by_case[r["case"]][r["stage"]] += 1
    total = len(rows)
    lines = [
        "# Error-propagation analysis", "",
        f"Scope: the {total} scored form fields that the system left UNKNOWN although the reference record has an answer. "
        "Each is attributed to the first pipeline stage that lost it. Reproduce with `python src/error_analysis.py`.", "",
        "| Stage where the answer was lost | Fields | Share |", "|---|---:|---:|",
    ]
    for key, label in STAGES.items():
        lines.append(f"| {key}. {label} | {counts[key]} | {counts[key] / total * 100:.1f}% |" if total else f"| {key}. {label} | 0 | - |")
    lines += ["", "## Per case", "", "| Case | " + " | ".join(STAGES) + " | Total |", "|---|" + "---:|" * (len(STAGES) + 1)]
    for case_id, c in sorted(by_case.items()):
        lines.append(f"| {case_id} | " + " | ".join(str(c[k]) for k in STAGES) + f" | {sum(c.values())} |")
    lines += ["", "## Field detail", "", "| Case | Field | Reference | Topic in Hindi | Topic in English | Stage |", "|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['case']} | {r['field']} | {r['gold']} | {'yes' if r['topic_in_hindi'] else 'no'} | {'yes' if r['topic_in_english'] else 'no'} | {r['stage']} |")
    lines += ["", "Topic detection uses keyword lists (English) and phonetic matching (Hindi); it indicates where information disappeared, not a precise measurement. Hallucinated Hindi segments are excluded."]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "error_analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with open(OUT_DIR / "error_analysis.json", "w", encoding="utf-8") as handle:
        json.dump({"stages": STAGES, "counts": dict(counts), "rows": rows}, handle, ensure_ascii=False, indent=2)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
