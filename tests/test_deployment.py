import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

try:
    from src.serve import (
        LocalOnlyServer,
        alias_map,
        build_case_list,
        build_case_payload,
        discover_case_records,
        load_metrics,
        safe_case_id,
    )
except ImportError:
    from serve import (
        LocalOnlyServer,
        alias_map,
        build_case_list,
        build_case_payload,
        discover_case_records,
        load_metrics,
        safe_case_id,
    )


class DeploymentDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "outputs" / "forms").mkdir(parents=True)
        (self.root / "outputs" / "ner").mkdir(parents=True)
        (self.root / "outputs" / "transcripts").mkdir(parents=True)
        (self.root / "outputs" / "eval" / "m4").mkdir(parents=True)
        (self.root / "audio").mkdir()
        (self.root / "Docs").mkdir()
        form = {
            "patient_id": "Patient_Alpha",
            "demographics": {"name": "Alice Example", "age": 42, "sex": "Female", "mobile": "1234567890", "address": "Example Street"},
            "clinical_indicators": {"weight_kg": None},
            "general_cancer_symptoms": {"pain": {"assertion": "UNKNOWN", "evidence": None}},
            "extraction_evidence": {"pain": {"question": "Any pain?", "answer": None}},
        }
        (self.root / "outputs" / "forms" / "Patient_Alpha_form.json").write_text(json.dumps(form), encoding="utf-8")
        (self.root / "outputs" / "ner" / "Patient_Alpha_ner.json").write_text(json.dumps({"entities": [{"span": "pain"}], "relations": [], "ontology_grounded_count": 1}), encoding="utf-8")
        (self.root / "outputs" / "transcripts" / "Patient_Alpha_en.json").write_text(json.dumps({"transcription": [{"text": "Any pain?"}]}), encoding="utf-8")
        (self.root / "outputs" / "transcripts" / "Patient_Alpha_hi.json").write_text(json.dumps({"transcription": [{"text": "दर्द है?"}]}), encoding="utf-8")
        (self.root / "outputs" / "forms" / "Patient_Alpha_report.md").write_text("# Draft report\n", encoding="utf-8")
        metrics = {
            "field_evaluation": {
                "matched_case_count": 4,
                "assertion_metrics": {"n_scorable": 56, "correct": 22, "exact_accuracy": 22 / 56, "prediction_coverage": 22 / 56, "selective_accuracy": 1.0, "abstentions": 34, "gold_class_support": {"PRESENT": 2}, "per_class": {"PRESENT": {"support": 2}}},
            },
            "ner_evaluation": {"available": False, "reason": "Human annotations are pending."},
            "limitations": ["Small preliminary sample."],
        }
        (self.root / "outputs" / "eval" / "m4" / "m4_evaluation_summary.json").write_text(json.dumps(metrics), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_case_discovery_creates_pseudonymous_alias(self):
        records = discover_case_records(self.root)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["id"], "case-001")
        self.assertNotIn("Patient_Alpha", records[0]["id"])

    def test_alias_map_resolves_internal_case(self):
        self.assertEqual(alias_map(self.root), {"case-001": "Patient_Alpha"})

    def test_direct_demographic_identifiers_are_redacted(self):
        payload = build_case_payload(self.root, "case-001")
        self.assertEqual(payload["form"]["demographics"]["name"], "Redacted in prototype view")
        self.assertEqual(payload["form"]["demographics"]["mobile"], "Redacted in prototype view")
        self.assertEqual(payload["form"]["demographics"]["age"], 42)

    def test_form_source_file_is_not_mutated_by_redaction(self):
        build_case_payload(self.root, "case-001")
        original = json.loads((self.root / "outputs" / "forms" / "Patient_Alpha_form.json").read_text())
        self.assertEqual(original["demographics"]["name"], "Alice Example")

    def test_transcripts_and_evidence_are_exposed_for_local_review(self):
        payload = build_case_payload(self.root, "case-001")
        self.assertEqual(payload["transcripts"]["en"][0]["text"], "Any pain?")
        self.assertIn("extraction_evidence", payload["form"])

    def test_metrics_adapter_reads_m4_summary(self):
        metrics = load_metrics(self.root)
        self.assertTrue(metrics["available"])
        self.assertEqual(metrics["matched_case_count"], 4)
        self.assertEqual(metrics["correct_fields"], 22)
        self.assertFalse(metrics["ner_available"])

    def test_invalid_case_ids_are_rejected(self):
        self.assertTrue(safe_case_id("Patient_1"))
        self.assertFalse(safe_case_id("../secret"))
        self.assertFalse(safe_case_id("case/one"))
        self.assertFalse(safe_case_id(""))

    def test_case_list_does_not_expose_original_case_name(self):
        cases = build_case_list(self.root)
        self.assertEqual(cases[0]["label"], "Case 001")
        self.assertTrue(cases[0]["can_process"])

    def test_audio_only_cases_are_discovered_for_processing(self):
        (self.root / "audio" / "NewCase.mp3").write_bytes(b"fake-audio")
        records = discover_case_records(self.root)
        self.assertEqual([record["id"] for record in records], ["case-001", "case-002"])
        cases = build_case_list(self.root)
        audio_only = next(item for item in cases if item["label"] == "Case 001")
        self.assertTrue(audio_only["can_process"])
        self.assertFalse(audio_only["ready"])


class DeploymentApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import socket
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
            probe.listen(1)
            client = socket.create_connection(("127.0.0.1", port), timeout=0.5)
            client.close()
        except (PermissionError, OSError) as exc:
            raise unittest.SkipTest(f"Loopback socket connections not permitted in this environment: {exc}")
        finally:
            probe.close()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "web").mkdir(parents=True)
        (self.root / "web" / "index.html").write_text("<!doctype html><title>M5 smoke test</title>", encoding="utf-8")
        (self.root / "outputs" / "forms").mkdir(parents=True)
        (self.root / "outputs" / "transcripts").mkdir(parents=True)
        (self.root / "outputs" / "forms" / "CaseA_form.json").write_text(json.dumps({"demographics": {}, "clinical_indicators": {}}), encoding="utf-8")
        (self.root / "outputs" / "transcripts" / "CaseA_en.json").write_text(json.dumps({"transcription": []}), encoding="utf-8")
        self.server = LocalOnlyServer(("127.0.0.1", 0), self.root)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        if hasattr(self, "server"):
            self.server.shutdown()
            self.server.server_close()
        if hasattr(self, "thread"):
            self.thread.join(timeout=2)
        if hasattr(self, "temp"):
            self.temp.cleanup()

    def test_health_endpoint_responds(self):
        with urlopen(self.base + "/api/health") as response:
            payload = json.loads(response.read())
        self.assertEqual(payload["mode"], "local-only")

    def test_case_endpoint_uses_alias_id(self):
        with urlopen(self.base + "/api/cases") as response:
            payload = json.loads(response.read())
        self.assertEqual(payload["cases"][0]["id"], "case-001")

    def test_root_serves_dashboard_html(self):
        with urlopen(self.base + "/") as response:
            body = response.read().decode("utf-8")
        self.assertIn("M5 smoke test", body)

    def test_cross_origin_process_request_is_rejected(self):
        request = Request(
            self.base + "/api/cases/case-001/process",
            data=b"{}",
            headers={"Origin": "http://attacker.example"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code, 403)
        error.exception.close()

    def test_legacy_aggregate_data_json_is_not_served(self):
        (self.root / "web").mkdir(exist_ok=True)
        (self.root / "web" / "data.json").write_text('{"raw":"clinical data"}', encoding="utf-8")
        request = Request(self.base + "/data.json")
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code, 404)
        error.exception.close()

    def test_unknown_case_returns_404(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(self.base + "/api/cases/case-999")
        self.assertEqual(error.exception.code, 404)
        error.exception.close()


if __name__ == "__main__":
    unittest.main()
