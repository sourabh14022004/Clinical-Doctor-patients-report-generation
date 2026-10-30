#!/usr/bin/env python3
"""
Exports all pipeline data, transcripts, NER entities, populated forms,
and evaluation metrics into web/data.json for the interactive dashboard.
"""

import os
import json
import glob

def export_dashboard_data():
    os.makedirs("web", exist_ok=True)
    
    patients = ["Praveen", "Priyanshi", "Swarnima", "Uday", "Kajal"]
    
    data = {
        "patients": {},
        "evaluation_summary": {}
    }
    
    # Load evaluation summary
    if os.path.exists("outputs/eval/evaluation_summary.json"):
        with open("outputs/eval/evaluation_summary.json", "r", encoding="utf-8") as f:
            data["evaluation_summary"] = json.load(f)
            
    for p in patients:
        p_data = {
            "id": p,
            "audio_file": f"audio/{p}.mp3",
            "doc_image": f"Docs/{p}.jpeg" if os.path.exists(f"Docs/{p}.jpeg") else "Docs/ManojKumar.jpeg",
            "transcripts": {
                "en": [],
                "hi": []
            },
            "ner": {},
            "form": {},
            "report_md": ""
        }
        
        # English transcript
        en_path = f"outputs/transcripts/{p}_en.json"
        if os.path.exists(en_path):
            with open(en_path, "r", encoding="utf-8", errors="replace") as f:
                d = json.load(f)
                p_data["transcripts"]["en"] = d.get("transcription", [])
                
        # Hindi transcript
        hi_path = f"outputs/transcripts/{p}_hi.json"
        if os.path.exists(hi_path):
            with open(hi_path, "r", encoding="utf-8", errors="replace") as f:
                d = json.load(f)
                p_data["transcripts"]["hi"] = d.get("transcription", [])
                
        # NER
        ner_path = f"outputs/ner/{p}_ner.json"
        if os.path.exists(ner_path):
            with open(ner_path, "r", encoding="utf-8") as f:
                p_data["ner"] = json.load(f)
                
        # Form
        form_path = f"outputs/forms/{p}_form.json"
        if os.path.exists(form_path):
            with open(form_path, "r", encoding="utf-8") as f:
                p_data["form"] = json.load(f)
                
        # Markdown report
        rep_path = f"outputs/forms/{p}_report.md"
        if os.path.exists(rep_path):
            with open(rep_path, "r", encoding="utf-8") as f:
                p_data["report_md"] = f.read()
                
        data["patients"][p] = p_data
        
    with open("web/data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        
    print(f"Exported data for {len(patients)} patients to web/data.json")

if __name__ == "__main__":
    export_dashboard_data()
