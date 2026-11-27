#!/usr/bin/env python3
"""Hindi <-> English entity span alignment (cross-lingual entity projection).

The project brief (HindiNERWorkflow.docx) asks for alignment-aware cross-lingual
NER: run NER in English, but keep the link back to the original Hindi span.

Whisper is run twice on the same audio (Hindi transcription and English
translation), so the two transcripts are not sentence-aligned text, but both carry
audio timestamps. This module projects each English entity back to Hindi in two
steps:

1. Timestamp anchoring: the English segment that contains the entity is matched
   to Hindi segments whose audio time window overlaps it.
2. Lexical projection: inside those Hindi segments, Hindi / code-mixed
   equivalents of the English entity words are searched for. Hindi ASR output is
   noisy ("cancer" appears as कैंसर, कानसर, कंसर, खंसर, खणसर), so matching is done
   on a phonetic consonant skeleton with an approximate-match threshold.

Each entity receives a ``hindi_alignment`` record:

    method  = "lexical"   Hindi span found inside a time-overlapping segment
            = "segment"   time-overlapping Hindi segment found, no word-level match
            = "unaligned" no usable Hindi segment (missing or hallucinated)

Hindi segments that look like Whisper hallucination loops (the same phrase
repeated many times) are flagged and never used as alignment evidence.
"""
from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Sequence, Tuple

# English keyword -> Hindi / code-mixed surface forms (Devanagari).
# Includes English loanwords as Hindi speakers say them in clinics.
HINDI_LEXICON: Dict[str, List[str]] = {
    "cancer": ["कैंसर", "कानसर"],
    "breast": ["ब्रेस्ट", "स्तन"],
    "oral": ["ओरल", "औरल", "मुंह"],
    "cervical": ["सर्वाइकल"],
    "fever": ["बुखार"],
    "fatigue": ["थकान", "कमजोरी"],
    "tiredness": ["थकान", "कमजोरी"],
    "weight": ["वजन", "वेट"],
    "loss": ["कम"],
    "wound": ["घाव", "जख्म"],
    "ulcer": ["छाला", "अल्सर", "घाव"],
    "lump": ["गांठ"],
    "swelling": ["सूजन"],
    "pain": ["दर्द"],
    "bleeding": ["खून", "ब्लीडिंग"],
    "diabetes": ["डायबिटीज", "शुगर", "मधुमेह"],
    "sugar": ["शुगर", "डायबिटीज"],
    "hypertension": ["बीपी", "हाइपरटेंशन", "ब्लडप्रेशर"],
    "bp": ["बीपी", "ब्लडप्रेशर"],
    "tb": ["टीबी"],
    "tuberculosis": ["टीबी"],
    "mouth": ["मुंह", "मुख"],
    "opening": ["खोलने"],
    "chewing": ["चबाने"],
    "swallowing": ["निगलने"],
    "patch": ["पैच", "दाग"],
    "white": ["सफेद"],
    "red": ["लाल"],
    "tobacco": ["तंबाकू", "तमाकू"],
    "cigarette": ["सिगरेट"],
    "bidi": ["बीड़ी"],
    "gutkha": ["गुटखा"],
    "khaini": ["खैनी"],
    "alcohol": ["शराब", "अल्कोहल"],
    "mother": ["माँ", "मम्मी", "माता"],
    "mummy": ["मम्मी", "माँ"],
    "father": ["पिता", "पापा", "पिताजी"],
    "papa": ["पापा", "पिताजी"],
    "sister": ["बहन"],
    "brother": ["भाई"],
    "relative": ["रिश्तेदार"],
    "vegetarian": ["शाकाहारी"],
    "mixed": ["मिक्स"],
    "married": ["शादी"],
    "unmarried": ["शादी"],
    "insurance": ["बीमा", "इंश्योरेंस"],
    "ayushman": ["आयुष्मान"],
    "exercise": ["कसरत", "व्यायाम"],
    "nursing": ["नर्सिंग"],
    "officer": ["ऑफिसर"],
    "bareilly": ["बरेली"],
}

# Phonetic normalisation for noisy Devanagari ASR output.
_ASPIRATE_MAP = str.maketrans({
    "ख": "क", "घ": "ग", "छ": "च", "झ": "ज", "ठ": "ट", "ढ": "ड",
    "थ": "त", "ध": "द", "फ": "प", "भ": "ब", "ष": "स", "श": "स", "ण": "न",
})
_DROP_CHARS = re.compile(r"[़ँ-ःा-्॑-ॗॢॣ॰]")
_DEVANAGARI_WORD = re.compile(r"[ऀ-ॿ]+")


def phonetic_skeleton(word: str) -> str:
    """Reduce a Devanagari word to a consonant skeleton.

    Vowel signs, nukta, anusvara/chandrabindu and virama are dropped, and aspirated
    / sibilant / retroflex variants are merged, so कैंसर, कंसर and खंसर all reduce to
    "कसर" while कानसर and खणसर reduce to "कनसर".
    """
    return _DROP_CHARS.sub("", word).translate(_ASPIRATE_MAP)


_LIGHT_DROP = re.compile(r"[\u093C\u0901\u0902\u0903\u094D]")
_LONG_TO_SHORT = str.maketrans({"ी": "ि", "ू": "ु", "ै": "े", "ौ": "ो", "ई": "इ", "ऊ": "उ"})


def light_normalise(word: str) -> str:
    """Milder normalisation that keeps vowel signs (used for short words)."""
    return _LIGHT_DROP.sub("", word).translate(_ASPIRATE_MAP).translate(_LONG_TO_SHORT)


def is_hallucinated(text: str) -> bool:
    """Detect Whisper repetition loops such as "अपकचे सार, अपकचे सार, अपकचे सार"."""
    words = _DEVANAGARI_WORD.findall(text) or text.split()
    if re.search(r"(.)\1{9,}", text):  # a single character repeated 10+ times
        return True
    if len(words) < 6:
        return False
    bigrams = Counter(zip(words, words[1:]))
    most_common = bigrams.most_common(1)[0][1] if bigrams else 0
    return most_common >= 3 and len(set(words)) / len(words) < 0.4


def _joined_offsets(segments: Sequence[Dict[str, Any]]) -> Tuple[str, List[Tuple[int, int]]]:
    """Rebuild the space-joined text used by the NER engine with per-segment offsets."""
    pieces: List[str] = []
    offsets: List[Tuple[int, int]] = []
    cursor = 0
    for index, segment in enumerate(segments):
        if index:
            cursor += 1  # the joining space
        text = str(segment.get("text", "")).strip()
        offsets.append((cursor, cursor + len(text)))
        pieces.append(text)
        cursor += len(text)
    return " ".join(pieces), offsets


def _time_window(segment: Dict[str, Any]) -> Tuple[int, int]:
    offsets = segment.get("offsets") or {}
    return int(offsets.get("from", 0)), int(offsets.get("to", 0))


def _overlap(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


class HindiEnglishAligner:
    """Project English entity spans onto Hindi transcript spans."""

    def __init__(self, lexicon: Optional[Dict[str, List[str]]] = None,
                 match_threshold: float = 0.8, time_tolerance_ms: int = 1000,
                 phonetic: bool = True):
        self.lexicon = lexicon or HINDI_LEXICON
        self.phonetic = phonetic  # False = exact string match only (ablation baseline)
        self.match_threshold = match_threshold
        self.time_tolerance_ms = time_tolerance_ms
        self._skeletons = {
            key: [(phonetic_skeleton(form), light_normalise(form)) for form in forms]
            for key, forms in self.lexicon.items()
        }

    def word_matches(self, hindi_word: str, english_key: str) -> float:
        """Similarity between a Hindi token and the lexicon forms of an English key."""
        if not self.phonetic:
            return 1.0 if hindi_word in self.lexicon.get(english_key, []) else 0.0
        skeleton = phonetic_skeleton(hindi_word)
        if len(skeleton) < 2:
            return 0.0
        light = light_normalise(hindi_word)
        best = 0.0
        for form, form_light in self._skeletons.get(english_key, []):
            if not form:
                continue
            if min(len(skeleton), len(form)) < 3:
                # Short words collapse to ambiguous skeletons (पता / पिता -> "पत"),
                # so they must also agree once vowel signs are kept.
                if skeleton == form and light == form_light:
                    return 1.0
                continue
            if skeleton == form:
                return 1.0
            best = max(best, SequenceMatcher(None, skeleton, form).ratio())
        return best

    def _candidate_segments(self, window: Tuple[int, int], hi_segments: Sequence[Dict[str, Any]]) -> List[int]:
        start, end = window
        padded = (start - self.time_tolerance_ms, end + self.time_tolerance_ms)
        scored = []
        for index, segment in enumerate(hi_segments):
            overlap = _overlap(padded, _time_window(segment))
            if overlap > 0:
                scored.append((overlap, index))
        return [index for _, index in sorted(scored, reverse=True)]

    def align_entity(self, entity: Dict[str, Any], en_segments: Sequence[Dict[str, Any]],
                     en_offsets: Sequence[Tuple[int, int]], hi_segments: Sequence[Dict[str, Any]],
                     hi_offsets: Sequence[Tuple[int, int]], hallucinated: Sequence[bool]) -> Dict[str, Any]:
        start = int(entity.get("start", 0))
        en_index = next((i for i, (s, e) in enumerate(en_offsets) if s <= start < e), None)
        if en_index is None:
            return {"method": "unaligned", "reason": "ENGLISH_SEGMENT_NOT_FOUND"}

        window = _time_window(en_segments[en_index])
        record: Dict[str, Any] = {"en_time_ms": list(window)}
        candidates = self._candidate_segments(window, hi_segments)
        if not candidates:
            record.update({"method": "unaligned", "reason": "NO_TIME_OVERLAPPING_HINDI_SEGMENT"})
            return record
        usable = [i for i in candidates if not hallucinated[i]]
        if not usable:
            record.update({"method": "unaligned", "reason": "HINDI_SEGMENT_HALLUCINATED",
                           "hindi_segment": str(hi_segments[candidates[0]].get("text", "")).strip()})
            return record

        keys = [w for w in re.findall(r"[a-z]+", str(entity.get("span", "")).lower()) if w in self.lexicon]
        best: Optional[Tuple[float, int, int, int]] = None  # (score, segment, start, end)
        for seg_index in usable:
            seg_text = str(hi_segments[seg_index].get("text", "")).strip()
            by_key: Dict[str, List[Tuple[float, int, int]]] = {}
            for key in dict.fromkeys(keys):
                for token in _DEVANAGARI_WORD.finditer(seg_text):
                    score = self.word_matches(token.group(0), key)
                    if score >= self.match_threshold:
                        by_key.setdefault(key, []).append((score, token.start(), token.end()))
            if not by_key:
                continue
            # Multi-word entity ("breast cancer" -> "ब्रेस्ट कानसर"): anchor on each
            # match and take the nearest match of every other word; keep the tightest
            # window. Words more than 15 characters apart are not merged.
            candidates_spans = []
            for anchor in (m for group in by_key.values() for m in group):
                parts = [anchor]
                for other in by_key.values():
                    if anchor in other:
                        continue
                    nearest = min(other, key=lambda m: abs(m[1] - anchor[1]))
                    if abs(nearest[1] - anchor[1]) <= 15:
                        parts.append(nearest)
                span_start = min(p[1] for p in parts)
                span_end = max(p[2] for p in parts)
                # Score: mean similarity x share of entity words covered.
                score = (sum(p[0] for p in parts) / len(parts)) * (len(parts) / len(set(keys)))
                candidates_spans.append((score, -(span_end - span_start), span_start, span_end))
            score, _, span_start, span_end = max(candidates_spans)
            if best is None or score > best[0]:
                best = (score, seg_index, span_start, span_end)

        seg_index = best[1] if best else usable[0]
        segment = hi_segments[seg_index]
        seg_text = str(segment.get("text", "")).strip()
        record.update({
            "hindi_segment": seg_text,
            "hi_time_ms": list(_time_window(segment)),
        })
        if best:
            base = hi_offsets[seg_index][0]
            record.update({
                "method": "lexical",
                "hindi_span": seg_text[best[2]:best[3]],
                "hindi_start": base + best[2],
                "hindi_end": base + best[3],
                "confidence": round(best[0], 2),
            })
        else:
            record.update({
                "method": "segment",
                "reason": "NO_LEXICON_ENTRY" if not keys else "NO_WORD_LEVEL_MATCH",
            })
        return record

    def align(self, entities: List[Dict[str, Any]], en_segments: Sequence[Dict[str, Any]],
              hi_segments: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        """Attach ``hindi_alignment`` to every entity and return summary statistics."""
        _, en_offsets = _joined_offsets(en_segments)
        _, hi_offsets = _joined_offsets(hi_segments)
        hallucinated = [is_hallucinated(str(s.get("text", ""))) for s in hi_segments]
        counts: Counter = Counter()
        for entity in entities:
            if not hi_segments:
                entity["hindi_alignment"] = {"method": "unaligned", "reason": "NO_HINDI_TRANSCRIPT"}
            else:
                entity["hindi_alignment"] = self.align_entity(
                    entity, en_segments, en_offsets, hi_segments, hi_offsets, hallucinated)
            counts[entity["hindi_alignment"]["method"]] += 1
        total = len(entities)
        return {
            "entities": total,
            "lexical": counts["lexical"],
            "segment": counts["segment"],
            "unaligned": counts["unaligned"],
            "lexical_rate": round(counts["lexical"] / total, 3) if total else None,
            "hindi_segments": len(hi_segments),
            "hallucinated_hindi_segments": sum(hallucinated),
        }
