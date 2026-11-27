import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

try:
    from src.alignment import HindiEnglishAligner, is_hallucinated, phonetic_skeleton
    from src.medical_ner import ClinicalNEREngine
except ImportError:
    from alignment import HindiEnglishAligner, is_hallucinated, phonetic_skeleton
    from medical_ner import ClinicalNEREngine


def seg(text, start, end):
    return {"text": text, "offsets": {"from": start, "to": end}}


class PhoneticNormalisationTests(unittest.TestCase):
    def test_asr_spelling_variants_of_cancer_match(self):
        aligner = HindiEnglishAligner()
        for variant in ("कैंसर", "कंसर", "खंसर", "कानसर", "खणसर"):
            with self.subTest(variant=variant):
                self.assertGreaterEqual(aligner.word_matches(variant, "cancer"), 0.8)

    def test_short_words_need_vowel_agreement(self):
        aligner = HindiEnglishAligner()
        self.assertEqual(phonetic_skeleton("पता"), phonetic_skeleton("पिता"))
        self.assertEqual(aligner.word_matches("पता", "father"), 0.0)  # "address", not "father"
        self.assertEqual(aligner.word_matches("पिता", "father"), 1.0)

    def test_unrelated_word_does_not_match(self):
        self.assertLess(HindiEnglishAligner().word_matches("शराब", "cancer"), 0.8)


class HallucinationTests(unittest.TestCase):
    def test_repetition_loop_is_flagged(self):
        self.assertTrue(is_hallucinated("अपकचे सार, अपकचे सार, अपकचे सार, अपकचे सार,"))
        self.assertTrue(is_hallucinated("पुषना चाूँँँँँँँँँँँँँँ"))

    def test_normal_sentence_is_not_flagged(self):
        self.assertFalse(is_hallucinated("आपकी फैमिली में किसी को कैंसर है? हाँ, मम्मी को ब्रेस्ट कैंसर था"))


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.engine = ClinicalNEREngine()

    def _project(self, en_segments, hi_segments):
        text = " ".join(s["text"].strip() for s in en_segments)
        entities = self.engine.detect_assertions(text, self.engine.detect_entities(text))
        summary = HindiEnglishAligner().align(entities, en_segments, hi_segments)
        return {e["span"].lower(): e["hindi_alignment"] for e in entities}, summary

    def test_multiword_entity_projects_to_hindi_span(self):
        en = [seg("Does anyone in your family have cancer?", 0, 3000), seg("Yes, mother had breast cancer.", 3000, 6000)]
        hi = [seg("आपकी फैमिली में किसी को कैंसर है?", 0, 3000), seg("हाँ, मम्मी को ब्रेस्ट कानसर था", 3000, 6000)]
        aligned, _ = self._project(en, hi)
        self.assertEqual(aligned["breast cancer"]["method"], "lexical")
        self.assertEqual(aligned["breast cancer"]["hindi_span"], "ब्रेस्ट कानसर")
        self.assertEqual(aligned["mother"]["hindi_span"], "मम्मी")

    def test_timestamps_choose_the_right_segment(self):
        # "cancer" appears in both Hindi segments; the English time window decides.
        en = [seg("Any cancer at home?", 0, 2000), seg("No.", 2000, 3000), seg("Was it breast cancer?", 9000, 11000)]
        hi = [seg("घर में किसी को कैंसर?", 0, 2000), seg("नहीं", 2000, 3000), seg("ब्रेस्ट कैंसर था?", 9000, 11000)]
        aligned, _ = self._project(en, hi)
        self.assertEqual(aligned["breast cancer"]["hi_time_ms"], [9000, 11000])

    def test_hallucinated_hindi_segment_is_not_used(self):
        en = [seg("Do you drink alcohol?", 0, 4000)]
        hi = [seg("अपकचे सार, अपकचे सार, अपकचे सार, अपकचे सार,", 0, 4000)]
        aligned, summary = self._project(en, hi)
        self.assertEqual(aligned["alcohol"]["method"], "unaligned")
        self.assertEqual(aligned["alcohol"]["reason"], "HINDI_SEGMENT_HALLUCINATED")
        self.assertEqual(summary["hallucinated_hindi_segments"], 1)

    def test_entity_without_lexicon_entry_falls_back_to_segment(self):
        en = [seg("How old are you? 32 years old.", 0, 3000)]
        hi = [seg("आपकी उम्र? बत्तीस साल", 0, 3000)]
        aligned, _ = self._project(en, hi)
        self.assertEqual(aligned["32 years old"]["method"], "segment")
        self.assertEqual(aligned["32 years old"]["reason"], "NO_LEXICON_ENTRY")


if __name__ == "__main__":
    unittest.main(verbosity=2)
