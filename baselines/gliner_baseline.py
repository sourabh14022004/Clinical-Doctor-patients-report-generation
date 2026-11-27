#!/usr/bin/env python3
"""Neural NER baseline: zero-shot GLiNER on the same English transcripts.

Purpose
-------
The project's NER is rule/lexicon based. This script produces a *learned-model*
baseline so the two can be compared on the same text and the same human gold
annotations. GLiNER (Zaratiana et al., NAACL 2024) is a zero-shot span-extraction
model: entity types are given as natural-language labels, so no training data is
needed, which suits a five-recording dataset.

It needs PyTorch, so it is meant to run on Kaggle / Colab (or any machine with
internet access to PyPI and Hugging Face):

    pip install gliner
    python baselines/gliner_baseline.py --ner-dir outputs/ner --out-dir outputs/baselines/gliner

Input:  outputs/ner/<case>_ner.json  (only the "english_text" field is used, so the
        character offsets match the human gold annotations exactly)
Output: outputs/baselines/gliner/<case>_ner.json in the same format as the rule system

Then, on the project machine:

    python src/compare_ner_systems.py

Privacy: transcripts can contain personal data. Upload them only to a *private*
Kaggle dataset / notebook, and delete them afterwards.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re

# Natural-language label (what GLiNER sees) -> project entity type.
LABELS = {
    "symptom or sign": "SIGN_SYMPTOM",
    "disease or diagnosis": "DIAGNOSIS",
    "type of cancer": "CANCER_TYPE",
    "oral or mouth sign": "ORAL_SIGN",
    "tobacco product or tobacco use": "RISK_FACTOR_TOBACCO",
    "alcohol use": "RISK_FACTOR_ALCOHOL",
    "family member or relative": "FAMILY_MEMBER",
    "age": "AGE",
    "date of birth": "DOB",
    "education level": "EDUCATION",
    "occupation": "OCCUPATION",
    "marital status": "MARITAL_STATUS",
    "place or address": "ADDRESS",
    "phone number": "CONTACT_PHONE",
    "income": "FAMILY_INCOME",
    "health insurance scheme": "HEALTH_INSURANCE",
    "body weight": "WEIGHT",
    "height": "HEIGHT",
    "diet": "DIETARY_HABIT",
    "physical activity": "PHYSICAL_ACTIVITY",
    "time duration": "DURATION",
    "person name": "PATIENT_NAME",
}


def sentence_chunks(text: str, max_chars: int = 600):
    """Yield (offset, chunk) pieces that respect sentence boundaries."""
    start = 0
    for match in re.finditer(r"[^.?!]+[.?!]*\s*", text):
        if match.end() - start > max_chars and match.start() > start:
            yield start, text[start:match.start()]
            start = match.start()
    if start < len(text):
        yield start, text[start:]


def main() -> None:
    parser = argparse.ArgumentParser(description="Zero-shot GLiNER NER baseline")
    parser.add_argument("--ner-dir", default="outputs/ner")
    parser.add_argument("--out-dir", default="outputs/baselines/gliner")
    parser.add_argument("--model", default="urchade/gliner_medium-v2.1")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    from gliner import GLiNER  # imported here so --help works without the package

    model = GLiNER.from_pretrained(args.model)
    labels = list(LABELS)
    os.makedirs(args.out_dir, exist_ok=True)
    for path in sorted(glob.glob(os.path.join(args.ner_dir, "*_ner.json"))):
        case_id = os.path.basename(path)[:-9]
        with open(path, encoding="utf-8") as handle:
            text = json.load(handle).get("english_text", "")
        entities = []
        for offset, chunk in sentence_chunks(text):
            for ent in model.predict_entities(chunk, labels, threshold=args.threshold):
                start, end = offset + ent["start"], offset + ent["end"]
                entities.append({
                    "span": text[start:end], "start": start, "end": end,
                    "entity_type": LABELS[ent["label"]], "score": round(float(ent["score"]), 3),
                    "assertion": "UNKNOWN",  # GLiNER does not do assertion detection
                })
        with open(os.path.join(args.out_dir, f"{case_id}_ner.json"), "w", encoding="utf-8") as handle:
            json.dump({"system": f"GLiNER zero-shot ({args.model}, threshold {args.threshold})",
                       "english_text": text, "entities": entities}, handle, ensure_ascii=False, indent=2)
        print(f"{case_id}: {len(entities)} entities")


if __name__ == "__main__":
    main()
