#!/usr/bin/env python3
"""Export local pipeline artifacts for the browser dashboard.

The generated web/data.json may contain sensitive clinical information. Keep it local
and do not commit it to a public repository.
"""

import glob
import json
import os
from pathlib import Path


def _load_json(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return json.load(handle)


def export_dashboard_data():
    os.makedirs("web", exist_ok=True)

    # Discover cases from generated forms rather than maintaining a patient-name list.
    form_paths = sorted(glob.glob("outputs/forms/*_form.json"))
    case_ids = [Path(path).name[:-len("_form.json")] for path in form_paths]
    if not case_ids:
        transcript_paths = sorted(glob.glob("outputs/transcripts/*_en.json"))
        case_ids = [Path(path).name[:-len("_en.json")] for path in transcript_paths]

    data = {
        "patients": {},
        "evaluation_summary": _load_json("outputs/eval/evaluation_summary.json"),
    }

    for case_id in case_ids:
        audio_path = f"audio/{case_id}.mp3"
        image_candidates = [f"Docs/{case_id}.jpeg", f"Docs/{case_id}.jpg", f"Docs/{case_id}.png"]
        doc_image = next((path for path in image_candidates if os.path.exists(path)), None)
        patient_data = {
            "id": case_id,
            "audio_file": audio_path if os.path.exists(audio_path) else None,
            "doc_image": doc_image,
            "transcripts": {
                "en": _load_json(f"outputs/transcripts/{case_id}_en.json").get("transcription", []),
                "hi": _load_json(f"outputs/transcripts/{case_id}_hi.json").get("transcription", []),
            },
            "ner": _load_json(f"outputs/ner/{case_id}_ner.json"),
            "form": _load_json(f"outputs/forms/{case_id}_form.json"),
            "report_md": "",
        }
        report_path = f"outputs/forms/{case_id}_report.md"
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8", errors="replace") as handle:
                patient_data["report_md"] = handle.read()
        data["patients"][case_id] = patient_data

    output_path = "web/data.json"
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)

    print(f"Exported {len(case_ids)} case(s) to {output_path}.")
    print("Reminder: web/data.json may contain patient information; do not publish or commit it.")


if __name__ == "__main__":
    export_dashboard_data()
