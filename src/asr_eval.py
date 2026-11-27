#!/usr/bin/env python3
"""Speech-recognition and translation quality for the Whisper outputs.

    python src/asr_eval.py

1. Without any reference (always available)
   * Hindi hallucination rate: share of Hindi ASR segments / audio time that are
     Whisper repetition loops (see alignment.is_hallucinated).
2. With a human reference for the first part of a recording
   * Hindi transcription: WER and CER (word / character error rate, Levenshtein).
   * English translation: chrF (character n-gram F-score, Popovic 2015), the
     standard metric for translation into or out of morphologically rich languages.

Reference files (plain UTF-8 text), written by a person listening to the audio:

    outputs/asr_reference/<case>_hi.txt   Hindi as actually spoken (Devanagari)
    outputs/asr_reference/<case>_en.txt   faithful English translation (optional)

The first line may be ``# end_ms: 120000`` to say how much audio the reference
covers (here the first two minutes); the hypothesis is cut at the same point.
Two minutes per recording is enough for a meaningful estimate.

Writes outputs/eval/asr/asr_report.md and asr_summary.json.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

try:
    from src.alignment import is_hallucinated
except ImportError:
    from alignment import is_hallucinated

TRANSCRIPTS = ROOT / "outputs" / "transcripts"
REFERENCES = ROOT / "outputs" / "asr_reference"
OUT_DIR = ROOT / "outputs" / "eval" / "asr"

_PUNCT = re.compile(r"[।॥.,!?;:\"'()\[\]{}\-–—…।]")


def normalise(text: str) -> str:
    """Lower-case, drop punctuation (incl. Devanagari danda) and nukta, squash spaces."""
    text = _PUNCT.sub(" ", text.lower()).replace("़", "")
    return re.sub(r"\s+", " ", text).strip()


def edit_distance(ref: Sequence[str], hyp: Sequence[str]) -> Tuple[int, int, int, int]:
    """Levenshtein alignment. Returns (distance, substitutions, deletions, insertions)."""
    rows, cols = len(ref) + 1, len(hyp) + 1
    dist = [[(0, 0, 0, 0)] * cols for _ in range(rows)]
    for i in range(1, rows):
        dist[i][0] = (i, 0, i, 0)
    for j in range(1, cols):
        dist[0][j] = (j, 0, 0, j)
    for i in range(1, rows):
        for j in range(1, cols):
            if ref[i - 1] == hyp[j - 1]:
                dist[i][j] = dist[i - 1][j - 1]
                continue
            sub, dele, ins = dist[i - 1][j - 1], dist[i - 1][j], dist[i][j - 1]
            best = min(sub, dele, ins, key=lambda t: t[0])
            if best is sub:
                dist[i][j] = (sub[0] + 1, sub[1] + 1, sub[2], sub[3])
            elif best is dele:
                dist[i][j] = (dele[0] + 1, dele[1], dele[2] + 1, dele[3])
            else:
                dist[i][j] = (ins[0] + 1, ins[1], ins[2], ins[3] + 1)
    return dist[-1][-1]


def error_rate(reference: str, hypothesis: str, unit: str = "word") -> Dict[str, Any]:
    ref, hyp = normalise(reference), normalise(hypothesis)
    ref_units = ref.split() if unit == "word" else list(ref.replace(" ", ""))
    hyp_units = hyp.split() if unit == "word" else list(hyp.replace(" ", ""))
    d, s, de, ins = edit_distance(ref_units, hyp_units)
    n = len(ref_units)
    return {"rate": d / n if n else None, "substitutions": s, "deletions": de, "insertions": ins,
            "reference_length": n, "hypothesis_length": len(hyp_units)}


def chrf(reference: str, hypothesis: str, max_n: int = 6, beta: float = 2.0) -> Optional[float]:
    """chrF score in [0, 1] (spaces removed, character n-grams 1..6, recall-weighted)."""
    ref, hyp = normalise(reference).replace(" ", ""), normalise(hypothesis).replace(" ", "")
    precisions, recalls = [], []
    for n in range(1, max_n + 1):
        ref_ngrams = Counter(ref[i:i + n] for i in range(len(ref) - n + 1))
        hyp_ngrams = Counter(hyp[i:i + n] for i in range(len(hyp) - n + 1))
        if not ref_ngrams or not hyp_ngrams:
            continue
        overlap = sum((ref_ngrams & hyp_ngrams).values())
        precisions.append(overlap / sum(hyp_ngrams.values()))
        recalls.append(overlap / sum(ref_ngrams.values()))
    if not precisions:
        return None
    p, r = sum(precisions) / len(precisions), sum(recalls) / len(recalls)
    return 0.0 if p + r == 0 else (1 + beta ** 2) * p * r / (beta ** 2 * p + r)


def load_segments(case_id: str, lang: str) -> List[Dict[str, Any]]:
    path = TRANSCRIPTS / f"{case_id}_{lang}.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8", errors="replace") as handle:
        return json.load(handle).get("transcription", [])


def read_reference(path: Path) -> Tuple[str, Optional[int]]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\s*#\s*end_ms\s*:\s*(\d+)\s*\n", text)
    if match:
        return text[match.end():], int(match.group(1))
    return text, None


def hypothesis_text(segments: List[Dict[str, Any]], end_ms: Optional[int]) -> str:
    kept = [s for s in segments if end_ms is None or int((s.get("offsets") or {}).get("from", 0)) < end_ms]
    return " ".join(str(s.get("text", "")).strip() for s in kept)


def hallucination_stats(segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    flagged = [s for s in segments if is_hallucinated(str(s.get("text", "")))]
    duration = lambda segs: sum(max(0, int(s["offsets"]["to"]) - int(s["offsets"]["from"])) for s in segs if s.get("offsets"))
    total_ms = duration(segments)
    return {"segments": len(segments), "hallucinated_segments": len(flagged),
            "hallucinated_audio_share": (duration(flagged) / total_ms) if total_ms else None}


def repeated_segment_loops(segments: List[Dict[str, Any]], min_run: int = 3) -> Dict[str, Any]:
    """Count segments inside runs of >= min_run near-identical consecutive segments.

    Catches loops spread across many short segments (common in the English output),
    which the within-segment check cannot see.
    """
    texts = [normalise(str(s.get("text", ""))) for s in segments]
    in_loop = [False] * len(texts)
    i = 0
    while i < len(texts):
        j = i
        # A loop unit can be one segment ("no") or a question+answer pair.
        for width in (1, 2):
            k = i
            while k + 2 * width <= len(texts) and texts[k:k + width] == texts[k + width:k + 2 * width] and any(texts[k:k + width]):
                k += width
            if (k - i) // width + 1 >= min_run:
                for idx in range(i, k + width):
                    in_loop[idx] = True
                j = max(j, k + width - 1)
        i = max(i + 1, j + 1) if j > i else i + 1
    return {"segments": len(texts), "segments_in_loops": sum(in_loop),
            "loop_share": (sum(in_loop) / len(texts)) if texts else None}


def pct(value: Optional[float]) -> str:
    return "N/A" if value is None else f"{value * 100:.1f}%"


def main() -> None:
    cases = sorted(p.name[:-8] for p in TRANSCRIPTS.glob("*_hi.json"))
    summary: Dict[str, Any] = {}
    lines = ["# ASR and translation quality", "",
             "## 1. Whisper hallucination (no reference needed)", "",
             "A hallucinated segment is a repetition loop (the same phrase over and over), a known Whisper failure on long or quiet audio.", "",
             "| Case | Hindi segments | Hallucinated | Share of Hindi audio time | English segments in repetition loops |", "|---|---:|---:|---:|---:|"]
    for case_id in cases:
        stats = hallucination_stats(load_segments(case_id, "hi"))
        summary.setdefault(case_id, {})["hindi_hallucination"] = stats
        loops = repeated_segment_loops(load_segments(case_id, "en"))
        summary[case_id]["english_repetition_loops"] = loops
        lines.append(f"| {case_id} | {stats['segments']} | {stats['hallucinated_segments']} | {pct(stats['hallucinated_audio_share'])} | {loops['segments_in_loops']}/{loops['segments']} ({pct(loops['loop_share'])}) |")

    lines += ["", "## 2. Against human reference transcripts", ""]
    rows = []
    totals = {"word_errors": 0, "words": 0, "char_errors": 0, "chars": 0}
    for case_id in cases:
        hi_ref = REFERENCES / f"{case_id}_hi.txt"
        en_ref = REFERENCES / f"{case_id}_en.txt"
        if not hi_ref.exists() and not en_ref.exists():
            continue
        entry = summary.setdefault(case_id, {})
        wer = cer = score = None
        covered = None
        if hi_ref.exists():
            reference, end_ms = read_reference(hi_ref)
            hypothesis = hypothesis_text(load_segments(case_id, "hi"), end_ms)
            wer, cer = error_rate(reference, hypothesis, "word"), error_rate(reference, hypothesis, "char")
            entry.update({"hindi_wer": wer, "hindi_cer": cer, "reference_end_ms": end_ms})
            covered = end_ms
            totals["word_errors"] += wer["substitutions"] + wer["deletions"] + wer["insertions"]
            totals["words"] += wer["reference_length"]
            totals["char_errors"] += cer["substitutions"] + cer["deletions"] + cer["insertions"]
            totals["chars"] += cer["reference_length"]
        if en_ref.exists():
            reference, end_ms = read_reference(en_ref)
            score = chrf(reference, hypothesis_text(load_segments(case_id, "en"), end_ms))
            entry["english_chrf"] = score
            covered = covered or end_ms
        rows.append(f"| {case_id} | {'whole file' if covered is None else f'first {covered / 1000:.0f} s'} | "
                    f"{pct(wer['rate']) if wer else 'N/A'} | {pct(cer['rate']) if cer else 'N/A'} | "
                    f"{'N/A' if score is None else f'{score * 100:.1f}'} |")
    if rows:
        lines += ["| Case | Audio covered | Hindi WER | Hindi CER | English chrF (0-100) |", "|---|---|---:|---:|---:|"] + rows
        if totals["words"]:
            lines += ["", f"Pooled Hindi WER: **{pct(totals['word_errors'] / totals['words'])}**, pooled CER: **{pct(totals['char_errors'] / totals['chars'])}**.",
                      "", "CER is usually far lower than WER for Hindi ASR: many 'wrong' words are spelling variants (कैंसर vs कानसर) that a phonetic matcher can still use."]
    else:
        lines.append(f"No reference transcripts yet. Add files to `{REFERENCES.relative_to(ROOT)}/` (see the docstring of this script).")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "asr_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with open(OUT_DIR / "asr_summary.json", "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
