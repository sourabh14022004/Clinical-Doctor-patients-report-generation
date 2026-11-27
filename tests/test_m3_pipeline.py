import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

try:
    from src.form_populator import CancerScreeningFormPopulator
    from src.medical_ner import ClinicalNEREngine
except ImportError:
    from form_populator import CancerScreeningFormPopulator
    from medical_ner import ClinicalNEREngine


class FormPopulatorTests(unittest.TestCase):
    def setUp(self):
        self.populator = CancerScreeningFormPopulator()

    def test_question_answer_alignment_without_question_mark(self):
        segments = [
            {"text": "What is your name?"},
            {"text": "Alex Morgan."},
            {"text": "How old are you"},
            {"text": "31."},
        ]
        self.assertEqual(
            self.populator.extract_qa_turns(segments),
            [("What is your name?", "Alex Morgan."), ("How old are you", "31.")],
        )

    def test_four_state_assertion_classifier(self):
        cases = {
            "Yes, I do": "PRESENT",
            "No, never": "ABSENT",
            "Maybe, I am not sure": "POSSIBLE",
            "": "UNKNOWN",
            "not mentioned": "UNKNOWN",
            "not reported": "UNKNOWN",
            "not present": "ABSENT",
            "I think it might be": "POSSIBLE",
        }
        for answer, expected in cases.items():
            with self.subTest(answer=answer):
                self.assertEqual(self.populator._binary_assertion(answer), expected)

    def test_missing_values_are_not_fabricated_from_patient_id(self):
        form = self.populator.populate_form({"transcription": []}, patient_id="synthetic_case_123")
        self.assertIsNone(form["demographics"]["name"])
        self.assertIsNone(form["demographics"]["sex"])
        self.assertIsNone(form["demographics"]["marital_status"])
        self.assertIsNone(form["clinical_indicators"]["weight_kg"])
        self.assertIsNone(form["clinical_indicators"]["height"])
        self.assertIsNone(form["clinical_indicators"]["bmi"])
        self.assertIsNone(form["clinical_indicators"]["pulse"])
        self.assertEqual(
            form["general_cancer_symptoms"]["persistent_pain_without_known_cause"]["assertion"],
            "UNKNOWN",
        )

    def test_explicit_negative_is_not_unknown(self):
        transcript = {
            "transcription": [
                {"text": "Have you ever been sick like diabetes or BP?"},
                {"text": "No."},
            ]
        }
        form = self.populator.populate_form(transcript)
        self.assertFalse(form["history"]["past_medical_history"]["present"])
        self.assertEqual(form["history"]["past_medical_history"]["assertion"], "ABSENT")

    def test_unanswered_screening_item_remains_unknown(self):
        transcript = {"transcription": [{"text": "What is your name?"}, {"text": "Alex Morgan."}]}
        form = self.populator.populate_form(transcript)
        item = form["general_cancer_symptoms"]["bleeding_from_any_site"]
        self.assertIsNone(item["reported"])
        self.assertEqual(item["assertion"], "UNKNOWN")
        self.assertIn("general_cancer_symptoms.bleeding_from_any_site", form["extraction_evidence"])

    def test_bare_height_does_not_trigger_unverified_bmi(self):
        transcript = {
            "transcription": [
                {"text": "What is your weight?"}, {"text": "60 kg."},
                {"text": "What is your height?"}, {"text": "168."},
            ]
        }
        form = self.populator.populate_form(transcript)
        self.assertEqual(form["clinical_indicators"]["weight_kg"], 60.0)
        self.assertEqual(form["clinical_indicators"]["height"], "168")
        self.assertIsNone(form["clinical_indicators"]["bmi"])

    def test_family_history_relative_only_answer_is_positive_in_context(self):
        transcript = {
            "transcription": [
                {"text": "Has anyone in your family had cancer?"},
                {"text": "Mother."},
            ]
        }
        form = self.populator.populate_form(transcript)
        history = form["history"]["family_history_of_cancer"]
        self.assertTrue(history["present"])
        self.assertEqual(history["assertion"], "PRESENT")
        self.assertEqual(history["relative"], "Mother")


class ClinicalAssertionTests(unittest.TestCase):
    def setUp(self):
        self.engine = ClinicalNEREngine()

    def test_negation_does_not_leak_across_sentence_boundary(self):
        text = "No fever. The patient reports pain."
        entities = self.engine.detect_entities(text)
        results = self.engine.detect_assertions(text, entities)
        by_span = {item["span"].lower(): item["assertion"] for item in results}
        self.assertEqual(by_span["fever"], "ABSENT")
        self.assertEqual(by_span["pain"], "PRESENT")

    def test_contrastive_conjunction_resets_negation_scope(self):
        text = "No fever, but the patient reports pain."
        entities = self.engine.detect_entities(text)
        results = self.engine.detect_assertions(text, entities)
        by_span = {item["span"].lower(): item["assertion"] for item in results}
        self.assertEqual(by_span["fever"], "ABSENT")
        self.assertEqual(by_span["pain"], "PRESENT")

    def test_entity_mentioned_in_question_is_unknown(self):
        text = "Do you have fever?"
        entities = self.engine.detect_entities(text)
        results = self.engine.detect_assertions(text, entities)
        fever = next(item for item in results if item["span"].lower() == "fever")
        self.assertEqual(fever["assertion"], "UNKNOWN")
        self.assertEqual(fever["assertion_reason"], "MENTION_IN_QUESTION")

    def test_question_without_you_is_unknown(self):
        text = "Did anyone get cancer at home? No. What type of cancer?"
        entities = self.engine.detect_entities(text)
        results = self.engine.detect_assertions(text, entities)
        cancers = [item for item in results if item["entity_type"] == "CANCER_TYPE"]
        self.assertTrue(cancers)
        for item in cancers:
            self.assertEqual(item["assertion"], "UNKNOWN")
            self.assertEqual(item["assertion_reason"], "MENTION_IN_QUESTION")

    def test_family_relation_ignores_question_relatives_and_dedupes(self):
        text = ("What is your father's name? Ram. Did anyone get cancer at home? "
                "It happened in a relative. Did anyone get cancer at home? It happened in a relative.")
        result_entities = self.engine.detect_assertions(text, self.engine.detect_entities(text))
        relations = [r for r in self.engine.extract_relations(result_entities)
                     if r["relation_type"] == "FamilyHistory_Of"]
        self.assertEqual(len(relations), 1)
        self.assertEqual(relations[0]["tail"]["span"].lower(), "relative")

    def test_family_history_conflicting_answer_is_reconciled_and_flagged(self):
        populator = CancerScreeningFormPopulator()
        transcript = {"transcription": [
            {"text": "Did anyone get cancer at home?"},
            {"text": "No. It happened in a relative."},
        ]}
        form = populator.populate_form(transcript)
        family = form["history"]["family_history_of_cancer"]
        self.assertEqual(family["assertion"], "ABSENT")
        self.assertTrue(family["needs_review"])

        ner = {"relations": [{"relation_type": "FamilyHistory_Of", "assertion": "PRESENT",
                              "head": {"span": "cancer"}, "tail": {"span": "relative"}}]}
        self.engine.reconcile_family_history(ner, form)
        relation = ner["relations"][0]
        self.assertEqual(relation["assertion"], family["assertion"])
        self.assertTrue(relation["conflict"])
        self.assertEqual(relation["nlp_assertion"], "PRESENT")

    def test_uncertainty_cue_is_possible(self):
        text = "Possible fever was reported."
        entities = self.engine.detect_entities(text)
        results = self.engine.detect_assertions(text, entities)
        fever = next(item for item in results if item["span"].lower() == "fever")
        self.assertEqual(fever["assertion"], "POSSIBLE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
