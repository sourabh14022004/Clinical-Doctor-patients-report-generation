import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

try:
    from src.annotation_agreement import cohen_kappa, compare, merge
    from src.evaluate_m4 import M4Evaluator
except ImportError:
    from annotation_agreement import cohen_kappa, compare, merge
    from evaluate_m4 import M4Evaluator

TEXT = "Do you have fever? No. Any lump? Yes, a lump in the breast."


def ann(text, entity_type, assertion, occurrence=0):
    start = -1
    for _ in range(occurrence + 1):
        start = TEXT.index(text, start + 1)
    return {"start": start, "end": start + len(text), "text": text, "entity_type": entity_type, "assertion": assertion}


class KappaTests(unittest.TestCase):
    def test_perfect_agreement_is_one(self):
        self.assertAlmostEqual(cohen_kappa([("A", "A"), ("B", "B"), ("A", "A")]), 1.0)

    def test_textbook_value(self):
        # 20 items: both yes 7, both no 9, A yes/B no 2, A no/B yes 2 -> kappa = 0.596
        pairs = [("y", "y")] * 7 + [("n", "n")] * 9 + [("y", "n")] * 2 + [("n", "y")] * 2
        self.assertAlmostEqual(cohen_kappa(pairs), 0.5960, places=3)

    def test_empty_is_none(self):
        self.assertIsNone(cohen_kappa([]))


class AgreementTests(unittest.TestCase):
    def setUp(self):
        self.a = [ann("fever", "SIGN_SYMPTOM", "UNKNOWN"), ann("lump", "SIGN_SYMPTOM", "UNKNOWN"),
                  ann("lump", "SIGN_SYMPTOM", "PRESENT", 1)]
        self.b = [ann("fever", "SIGN_SYMPTOM", "UNKNOWN"), ann("lump", "SIGN_SYMPTOM", "UNKNOWN"),
                  ann("lump in the breast", "SIGN_SYMPTOM", "PRESENT")]

    def test_strict_and_lenient_f1(self):
        result = compare(self.a, self.b)
        self.assertEqual(result["strict_matches"], 2)
        self.assertAlmostEqual(result["strict_f1"], 2 / 3)
        self.assertEqual(result["lenient_matches"], 3)  # "lump" overlaps "lump in the breast"
        self.assertAlmostEqual(result["lenient_f1"], 1.0)

    def test_merge_keeps_agreement_and_lists_disagreements(self):
        merged = merge({"transcript_text": TEXT, "annotations": self.a, "annotator_id": "r1"},
                       {"transcript_text": TEXT, "annotations": self.b, "annotator_id": "r2"})
        self.assertEqual(len(merged["annotations"]), 2)
        self.assertEqual(len(merged["disagreements"]), 1)  # overlapping pair grouped together
        self.assertEqual(merged["annotation_status"], "needs_adjudication")


class NerEvaluationTests(unittest.TestCase):
    def test_strict_lenient_and_per_type_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            ner_dir, ann_dir = os.path.join(tmp, "ner"), os.path.join(tmp, "ann")
            os.makedirs(ner_dir)
            os.makedirs(ann_dir)
            gold = [ann("fever", "SIGN_SYMPTOM", "UNKNOWN"), ann("lump in the breast", "SIGN_SYMPTOM", "PRESENT")]
            pred = [ann("fever", "SIGN_SYMPTOM", "UNKNOWN"), ann("lump", "SIGN_SYMPTOM", "PRESENT", 1),
                    ann("breast", "CANCER_TYPE", "PRESENT")]
            with open(os.path.join(ner_dir, "c1_ner.json"), "w") as f:
                json.dump({"entities": pred}, f)
            with open(os.path.join(ann_dir, "c1_gold.json"), "w") as f:
                json.dump({"annotation_status": "complete", "transcript_text": TEXT, "annotations": gold}, f)
            evaluator = M4Evaluator(ner_dir=ner_dir, annotations_dir=ann_dir)
            result = evaluator.evaluate_ner()
        self.assertTrue(result["available"])
        strict = result["entity_exact_span_type"]
        self.assertEqual((strict["true_positive"], strict["false_positive"], strict["false_negative"]), (1, 2, 1))
        lenient = result["entity_lenient_overlap_type"]
        self.assertEqual(lenient["true_positive"], 2)
        self.assertAlmostEqual(lenient["recall"], 1.0)
        self.assertIn("CANCER_TYPE", result["per_entity_type_strict"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
