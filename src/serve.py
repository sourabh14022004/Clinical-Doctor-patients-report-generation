#!/usr/bin/env python3
"""Local-only web prototype for the clinical speech-to-structured-report project.

This server deliberately binds to loopback only. It is an academic demonstration,
not a production or clinical deployment. Patient data remain on the local machine.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
WEB_ROOT = ROOT / "web"
CASE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
ALLOWED_DOC_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


def load_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return {} if default is None else default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {} if default is None else default


def safe_case_id(case_id: str) -> bool:
    return bool(CASE_ID_RE.fullmatch(case_id or ""))


def discover_case_records(root: Path = ROOT) -> List[Dict[str, str]]:
    """Return internal case IDs with stable, pseudonymous display IDs."""
    forms_dir = root / "outputs" / "forms"
    transcript_dir = root / "outputs" / "transcripts"
    ner_dir = root / "outputs" / "ner"
    ids = set()
    if forms_dir.is_dir():
        ids.update(p.name[:-10] for p in forms_dir.glob("*_form.json") if p.is_file())
    if transcript_dir.is_dir():
        ids.update(p.name[:-8] for p in transcript_dir.glob("*_en.json") if p.is_file())
    if ner_dir.is_dir():
        ids.update(p.name[:-9] for p in ner_dir.glob("*_ner.json") if p.is_file())
    audio_dir = root / "audio"
    if audio_dir.is_dir():
        ids.update(p.stem for p in audio_dir.glob("*.mp3") if p.is_file())
    valid_ids = sorted(case_id for case_id in ids if safe_case_id(case_id))
    return [
        {"source_id": case_id, "id": f"case-{index:03d}", "label": f"Case {index:03d}"}
        for index, case_id in enumerate(valid_ids, start=1)
    ]


def alias_map(root: Path = ROOT) -> Dict[str, str]:
    return {item["id"]: item["source_id"] for item in discover_case_records(root)}


def _read_transcript(path: Path) -> List[Dict[str, Any]]:
    payload = load_json(path, {})
    segments = payload.get("transcription", []) if isinstance(payload, dict) else []
    return segments if isinstance(segments, list) else []


def _mask_demographics(form: Dict[str, Any]) -> Dict[str, Any]:
    """Copy a form and redact direct identifiers for display in the default UI."""
    safe_form = json.loads(json.dumps(form))
    demographics = safe_form.get("demographics")
    if isinstance(demographics, dict):
        for key in ("name", "dob", "address", "mobile", "father_or_husband_name"):
            if demographics.get(key):
                demographics[key] = "Redacted in prototype view"
    safe_form["patient_id"] = None
    return safe_form


def build_case_payload(root: Path, display_id: str, reveal_identifiers: bool = False) -> Optional[Dict[str, Any]]:
    cases = alias_map(root)
    source_id = cases.get(display_id)
    if not source_id:
        return None

    form = load_json(root / "outputs" / "forms" / f"{source_id}_form.json", {})
    ner = load_json(root / "outputs" / "ner" / f"{source_id}_ner.json", {})
    report_path = root / "outputs" / "forms" / f"{source_id}_report.md"
    try:
        report_md = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
    except (OSError, UnicodeError):
        report_md = ""

    doc_path = None
    for suffix in ALLOWED_DOC_SUFFIXES:
        candidate = root / "Docs" / f"{source_id}{suffix}"
        if candidate.is_file():
            doc_path = suffix
            break

    demographics = form.get("demographics", {}) if isinstance(form, dict) else {}
    audio_path = root / "audio" / f"{source_id}.mp3"
    response_form = form if reveal_identifiers else _mask_demographics(form)
    entities = ner.get("entities", []) if isinstance(ner, dict) else []
    relations = ner.get("relations", []) if isinstance(ner, dict) else []

    return {
        "id": display_id,
        "label": display_id.replace("-", " ").title(),
        "form": response_form,
        "transcripts": {
            "hi": _read_transcript(root / "outputs" / "transcripts" / f"{source_id}_hi.json"),
            "en": _read_transcript(root / "outputs" / "transcripts" / f"{source_id}_en.json"),
        },
        "ner": ner if isinstance(ner, dict) else {},
        "entities": entities if isinstance(entities, list) else [],
        "relations": relations if isinstance(relations, list) else [],
        "report_markdown": report_md,
        "audio_available": audio_path.is_file(),
        "document_available": doc_path is not None,
        "form_available": bool(form),
        "updated_at": datetime.fromtimestamp(
            (root / "outputs" / "forms" / f"{source_id}_form.json").stat().st_mtime,
            tz=timezone.utc,
        ).isoformat() if (root / "outputs" / "forms" / f"{source_id}_form.json").is_file() else None,
        "summary": {
            "entity_count": len(entities),
            "ontology_grounded_count": ner.get("ontology_grounded_count", 0) if isinstance(ner, dict) else 0,
            "relation_count": len(relations),
            "age": demographics.get("age") if isinstance(demographics, dict) else None,
            "sex": demographics.get("sex") if isinstance(demographics, dict) else None,
        },
    }


def build_case_list(root: Path = ROOT) -> List[Dict[str, Any]]:
    result = []
    for record in discover_case_records(root):
        source_id = record["source_id"]
        form_path = root / "outputs" / "forms" / f"{source_id}_form.json"
        form = load_json(form_path, {})
        ner = load_json(root / "outputs" / "ner" / f"{source_id}_ner.json", {})
        demo = form.get("demographics", {}) if isinstance(form, dict) else {}
        audio_available = (root / "audio" / f"{source_id}.mp3").is_file()
        transcripts_available = (root / "outputs" / "transcripts" / f"{source_id}_en.json").is_file()
        result.append({
            "id": record["id"],
            "label": record["label"],
            "age": demo.get("age") if isinstance(demo, dict) else None,
            "sex": demo.get("sex") if isinstance(demo, dict) else None,
            "entity_count": len(ner.get("entities", [])) if isinstance(ner, dict) else 0,
            "audio_available": audio_available,
            "ready": form_path.is_file(),
            "can_process": audio_available or transcripts_available,
        })
    return result


def build_health(root: Path = ROOT) -> Dict[str, Any]:
    whisper = shutil.which("whisper-cli")
    model_path = root / "models" / "ggml-small.bin"
    return {
        "status": "ok",
        "application": "Clinical Speech-to-Text and Structured Report Prototype",
        "version": "M5.1",
        "mode": "local-only",
        "case_count": len(discover_case_records(root)),
        "python_version": sys.version.split()[0],
        "whisper_cli_available": bool(whisper),
        "whisper_model_available": model_path.is_file(),
        "pipeline_source_available": (root / "src" / "pipeline.py").is_file(),
        "generated_forms_available": bool(list((root / "outputs" / "forms").glob("*_form.json"))) if (root / "outputs" / "forms").is_dir() else False,
    }


def load_metrics(root: Path = ROOT) -> Dict[str, Any]:
    path = root / "outputs" / "eval" / "m4" / "m4_evaluation_summary.json"
    summary = load_json(path, None)
    if not isinstance(summary, dict) or not summary:
        return {"available": False, "message": "Run the pipeline or python src/evaluate_m4.py to generate M4 metrics."}
    fields = summary.get("field_evaluation", {})
    assertions = fields.get("assertion_metrics", {})
    ner = summary.get("ner_evaluation", {})
    return {
        "available": True,
        "matched_case_count": fields.get("matched_case_count"),
        "scorable_fields": assertions.get("n_scorable"),
        "correct_fields": assertions.get("correct"),
        "exact_accuracy": assertions.get("exact_accuracy"),
        "prediction_coverage": assertions.get("prediction_coverage"),
        "selective_accuracy": assertions.get("selective_accuracy"),
        "abstentions": assertions.get("abstentions"),
        "gold_class_support": assertions.get("gold_class_support", {}),
        "per_class": assertions.get("per_class", {}),
        "ner_available": bool(ner.get("available")),
        "ner_reason": ner.get("reason"),
        "limitations": summary.get("limitations", []),
        "scope_warning": "Preliminary structured-field agreement only; not clinical validation or diagnostic accuracy.",
    }


class ClinicalRequestHandler(BaseHTTPRequestHandler):
    server_version = "ClinicalPrototype/5.1"

    @property
    def root(self) -> Path:
        return getattr(self.server, "project_root", ROOT)

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep logs concise and avoid request query strings that might contain data.
        print(f"[{self.log_date_time_string()}] {self.address_string()} {fmt % args}")

    def _json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _text(self, body: str, status: int = 200, content_type: str = "text/plain; charset=utf-8",
              filename: Optional[str] = None) -> None:
        raw = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(raw)

    def _file(self, path: Path, download_name: Optional[str] = None) -> None:
        try:
            resolved = path.resolve(strict=True)
            if not resolved.is_file():
                self._json({"error": "File not found"}, 404)
                return
        except OSError:
            self._json({"error": "File not found"}, 404)
            return
        content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        data = resolved.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if download_name:
            self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path == "/api/health":
            self._json(build_health(self.root))
            return
        if path == "/api/cases":
            self._json({"cases": build_case_list(self.root)})
            return
        if path == "/api/metrics":
            self._json(load_metrics(self.root))
            return
        if path.startswith("/api/jobs/"):
            job_id = path.rsplit("/", 1)[-1]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if not job:
                self._json({"error": "Job not found"}, 404)
            else:
                self._json(job)
            return
        if path.startswith("/api/cases/"):
            self._handle_case_get(path, parse_qs(parsed.query))
            return
        self._serve_static(path)

    def _handle_case_get(self, path: str, query: Dict[str, List[str]]) -> None:
        parts = [p for p in path.split("/") if p]
        if len(parts) < 3:
            self._json({"error": "Case route incomplete"}, 404)
            return
        display_id = parts[2]
        source_id = alias_map(self.root).get(display_id)
        if not source_id:
            self._json({"error": "Case not found"}, 404)
            return

        if len(parts) == 3:
            payload = build_case_payload(self.root, display_id, reveal_identifiers=False)
            self._json(payload if payload is not None else {"error": "Case not found"}, 200 if payload else 404)
            return
        resource = parts[3]
        if resource == "audio":
            audio_path = self.root / "audio" / f"{source_id}.mp3"
            self._file(audio_path)
            return
        if resource == "document":
            doc_path = None
            for suffix in ALLOWED_DOC_SUFFIXES:
                candidate = self.root / "Docs" / f"{source_id}{suffix}"
                if candidate.is_file():
                    doc_path = candidate
                    break
            if doc_path:
                self._file(doc_path)
            else:
                self._json({"error": "No linked document for this case"}, 404)
            return
        if resource == "export":
            form_path = self.root / "outputs" / "forms" / f"{source_id}_form.json"
            form = load_json(form_path, None)
            if not isinstance(form, dict) or not form:
                self._json({"error": "Generated form not found"}, 404)
                return
            export_format = (query.get("format") or ["json"])[0].lower()
            safe_stub = display_id.replace("-", "_")
            if export_format == "md":
                report_path = self.root / "outputs" / "forms" / f"{source_id}_report.md"
                if not report_path.is_file():
                    self._json({"error": "Markdown report not found"}, 404)
                    return
                self._file(report_path, f"{safe_stub}_clinical_report.md")
            elif export_format == "json":
                self._file(form_path, f"{safe_stub}_clinical_form.json")
            else:
                self._json({"error": "format must be json or md"}, 400)
            return
        self._json({"error": "Unknown case resource"}, 404)

    def _serve_static(self, path: str) -> None:
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        # The legacy static exporter may have created a raw data.json in web/.
        # Never expose that aggregate file through the static-file handler.
        if rel == "data.json" or rel.startswith("audio/"):
            self._json({"error": "Not found"}, 404)
            return
        # Only files under web/ can be served; reject traversal and hidden files.
        if ".." in Path(rel).parts or rel.startswith("."):
            self._json({"error": "Not found"}, 404)
            return
        web_root = self.root / "web"
        target = (web_root / rel).resolve()
        try:
            target.relative_to(web_root.resolve())
        except ValueError:
            self._json({"error": "Not found"}, 404)
            return
        if not target.is_file():
            self._json({"error": "Not found"}, 404)
            return
        self._file(target)

    def do_POST(self) -> None:  # noqa: N802
        # Browser requests must originate from this same local application.
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if origin and host:
            if urlparse(origin).netloc != host:
                self._json({"error": "Cross-origin requests are not allowed"}, 403)
                return
        parsed = urlparse(self.path)
        parts = [p for p in unquote(parsed.path).split("/") if p]
        if len(parts) != 4 or parts[:2] != ["api", "cases"] or parts[3] != "process":
            self._json({"error": "Unknown endpoint"}, 404)
            return
        display_id = parts[2]
        source_id = alias_map(self.root).get(display_id)
        if not source_id:
            self._json({"error": "Case not found"}, 404)
            return
        audio = self.root / "audio" / f"{source_id}.mp3"
        english = self.root / "outputs" / "transcripts" / f"{source_id}_en.json"
        if not audio.is_file() and not english.is_file():
            self._json({"error": "No source audio or English transcript is available for this case."}, 409)
            return

        job_id = uuid.uuid4().hex[:12]
        job = {
            "id": job_id,
            "case_id": display_id,
            "status": "queued",
            "message": "Pipeline queued",
            "started_at": None,
            "finished_at": None,
            "return_code": None,
            "log": "",
        }
        with JOBS_LOCK:
            JOBS[job_id] = job
        thread = threading.Thread(target=self._run_pipeline, args=(job_id, source_id), daemon=True)
        thread.start()
        self._json(job, 202)

    def _run_pipeline(self, job_id: str, source_id: str) -> None:
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "running"
            JOBS[job_id]["message"] = "Processing transcript, clinical entities and structured form"
            JOBS[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()
        try:
            completed = subprocess.run(
                [sys.executable, str(self.root / "src" / "pipeline.py"), source_id],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=3600,
                check=False,
            )
            output = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
            output = output[-16000:]
            with JOBS_LOCK:
                JOBS[job_id].update({
                    "status": "completed" if completed.returncode == 0 else "failed",
                    "message": "Pipeline completed" if completed.returncode == 0 else "Pipeline returned an error",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "return_code": completed.returncode,
                    "log": output,
                })
        except subprocess.TimeoutExpired as exc:
            with JOBS_LOCK:
                JOBS[job_id].update({
                    "status": "failed", "message": "Pipeline timed out after one hour",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "return_code": -1, "log": str(exc)[:4000],
                })
        except Exception as exc:  # pragma: no cover - defensive runtime path
            with JOBS_LOCK:
                JOBS[job_id].update({
                    "status": "failed", "message": "Pipeline could not be started",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "return_code": -1, "log": str(exc)[:4000],
                })


class LocalOnlyServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: Tuple[str, int], project_root: Path):
        self.project_root = project_root
        super().__init__(address, ClinicalRequestHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the clinical report-generation local web prototype.")
    parser.add_argument("--host", default="127.0.0.1", help="Loopback only (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        parser.error("For privacy, this prototype can bind only to localhost/loopback.")
    server = LocalOnlyServer((args.host, args.port), ROOT)
    print("Clinical documentation prototype is running.")
    print(f"Open: http://127.0.0.1:{args.port}")
    print("Safety: local-only prototype; do not expose it to a network or use for clinical decisions.")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping local prototype...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
