import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

try:
    from src.asr_eval import chrf, error_rate, hypothesis_text, normalise, repeated_segment_loops
except ImportError:
    from asr_eval import chrf, error_rate, hypothesis_text, normalise, repeated_segment_loops


class ErrorRateTests(unittest.TestCase):
    def test_identical_text_is_zero(self):
        self.assertEqual(error_rate("मुझे बुखार है", "मुझे बुखार है")["rate"], 0.0)

    def test_substitution_deletion_insertion_counts(self):
        # ref: a b c d ; hyp: a x c d e -> 1 substitution, 1 insertion -> WER 2/4
        result = error_rate("a b c d", "a x c d e")
        self.assertEqual((result["substitutions"], result["deletions"], result["insertions"]), (1, 0, 1))
        self.assertAlmostEqual(result["rate"], 0.5)

    def test_punctuation_and_danda_ignored(self):
        self.assertEqual(normalise("हाँ। नहीं, ठीक?"), "हाँ नहीं ठीक")
        self.assertEqual(error_rate("हाँ। ठीक है", "हाँ ठीक है")["rate"], 0.0)

    def test_cer_lower_than_wer_for_spelling_variant(self):
        wer = error_rate("मुझे कैंसर था", "मुझे कानसर था", "word")["rate"]
        cer = error_rate("मुझे कैंसर था", "मुझे कानसर था", "char")["rate"]
        self.assertLess(cer, wer)


class ChrfTests(unittest.TestCase):
    def test_bounds(self):
        self.assertAlmostEqual(chrf("the patient has fever", "the patient has fever"), 1.0)
        self.assertLess(chrf("the patient has fever", "completely unrelated words"), 0.3)


class HypothesisWindowTests(unittest.TestCase):
    def test_cut_at_reference_end(self):
        segments = [{"text": "one", "offsets": {"from": 0, "to": 1000}},
                    {"text": "two", "offsets": {"from": 1000, "to": 2000}},
                    {"text": "three", "offsets": {"from": 5000, "to": 6000}}]
        self.assertEqual(hypothesis_text(segments, 2000), "one two")
        self.assertEqual(hypothesis_text(segments, None), "one two three")


class LoopTests(unittest.TestCase):
    def test_question_answer_loop_detected(self):
        texts = ["What is your name?", "Ravi."] + ["Do you get diabetes?", "No."] * 4 + ["Thank you."]
        result = repeated_segment_loops([{"text": t} for t in texts])
        self.assertEqual(result["segments_in_loops"], 8)

    def test_normal_dialogue_has_no_loop(self):
        texts = ["Do you smoke?", "No.", "Do you drink?", "No.", "Any pain?", "No."]
        self.assertEqual(repeated_segment_loops([{"text": t} for t in texts])["segments_in_loops"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
