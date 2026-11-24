import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

try:
    from src.evaluate_m4 import M4Evaluator, classification_metrics, normalize_assertion
except ImportError:
    from evaluate_m4 import M4Evaluator, classification_metrics, normalize_assertion


class NormalizeAssertionTests(unittest.TestCase):
    def test_explicit_yes_and_no(self):
        self.assertEqual(normalize_assertion("Yes"), "PRESENT")
        self.assertEqual(normalize_assertion("No"), "ABSENT")

    def test_uncertain_is_possible(self):
        self.assertEqual(normalize_assertion("Maybe"), "POSSIBLE")
        self.assertEqual(normalize_assertion("possibly present"), "POSSIBLE")

    def test_missing_is_unknown(self):
        self.assertEqual(normalize_assertion(None), "UNKNOWN")
        self.assertEqual(normalize_assertion("not reported"), "UNKNOWN")

    def test_negative_precedes_generic_positive_word(self):
        self.assertEqual(normalize_assertion("No history of cancer"), "ABSENT")

    def test_free_text_family_history_is_present(self):
        self.assertEqual(normalize_assertion("Mother had cancer", parser="family_history"), "PRESENT")


class ClassificationMetricTests(unittest.TestCase):
    def test_unknown_gold_is_excluded(self):
        result = classification_metrics([("ABSENT", "ABSENT"), ("UNKNOWN", "PRESENT")])
        self.assertEqual(result["n_scorable"], 1)
        self.assertEqual(result["excluded_unknown_gold"], 1)
        self.assertEqual(result["exact_accuracy"], 1.0)

    def test_unknown_prediction_is_abstention_not_negative(self):
        result = classification_metrics([("ABSENT", "UNKNOWN")])
        self.assertEqual(result["exact_accuracy"], 0.0)
        self.assertEqual(result["prediction_coverage"], 0.0)
        self.assertEqual(result["abstentions"], 1)
        self.assertEqual(result["confusion_matrix"]["ABSENT"]["UNKNOWN"], 1)

    def test_present_sensitivity_unavailable_without_positive_gold(self):
        result = classification_metrics([("ABSENT", "ABSENT"), ("ABSENT", "UNKNOWN")])
        self.assertFalse(result["present_sensitivity_available"])
        self.assertIsNone(result["present_sensitivity"])

    def test_correct_four_state_prediction(self):
        pairs = [("PRESENT", "PRESENT"), ("ABSENT", "ABSENT"),
                 ("POSSIBLE", "POSSIBLE"), ("UNKNOWN", "UNKNOWN")]
        result = classification_metrics(pairs)
        self.assertEqual(result["n_scorable"], 3)
        self.assertEqual(result["exact_accuracy"], 1.0)
        self.assertEqual(result["prediction_coverage"], 1.0)


class NerAnnotationTests(unittest.TestCase):
    def test_completed_human_annotation_is_scored_by_exact_span_and_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            ner_dir = os.path.join(tmp, "ner")
            annotations_dir = os.path.join(tmp, "annotations")
            os.makedirs(ner_dir)
            os.makedirs(annotations_dir)
            transcript = "Patient denies fever today."
            prediction = {
                "english_text": transcript,
                "entities": [{
                    "start": 15, "end": 20, "span": "fever",
                    "entity_type": "SIGN_SYMPTOM", "assertion": "ABSENT"
                }]
            }
            gold = {
                "schema_version": "1.0",
                "source_case_id": "case_a",
                "annotation_status": "complete",
                "transcript_text": transcript,
                "annotations": [{
                    "start": 15, "end": 20, "text": "fever",
                    "entity_type": "SIGN_SYMPTOM", "assertion": "ABSENT"
                }]
            }
            with open(os.path.join(ner_dir, "case_a_ner.json"), "w", encoding="utf-8") as f:
                json.dump(prediction, f)
            with open(os.path.join(annotations_dir, "case_a_gold.json"), "w", encoding="utf-8") as f:
                json.dump(gold, f)
            evaluator = M4Evaluator(
                ground_truth_dir=os.path.join(tmp, "gt"),
                forms_dir=os.path.join(tmp, "forms"),
                ner_dir=ner_dir,
                annotations_dir=annotations_dir,
                output_dir=os.path.join(tmp, "eval"),
            )
            result = evaluator.evaluate_ner()
            self.assertTrue(result["available"])
            self.assertEqual(result["entity_exact_span_type"]["f1"], 1.0)
            self.assertEqual(
                result["assertion_on_exact_entity_matches"]["exact_accuracy"], 1.0
            )


if __name__ == "__main__":
    unittest.main()
