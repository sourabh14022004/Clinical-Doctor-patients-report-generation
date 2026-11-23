#!/usr/bin/env python3
"""Create local, blank human-annotation templates from existing NER transcripts.

Templates contain transcript text and therefore may contain personal/clinical data.
Keep them local, do not commit them, and use only with approval/consent.
"""
import argparse
import glob
import json
import os


def main():
    parser = argparse.ArgumentParser(description="Prepare independent NER gold annotation templates.")
    parser.add_argument("--ner-dir", default="outputs/ner")
    parser.add_argument("--output-dir", default="outputs/annotations")
    parser.add_argument("--force", action="store_true", help="Overwrite existing annotation templates")
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    paths = sorted(glob.glob(os.path.join(args.ner_dir, "*_ner.json")))
    created = skipped = 0
    for path in paths:
        with open(path, "r", encoding="utf-8") as handle:
            pred = json.load(handle)
        case_id = os.path.basename(path)[:-9]
        target = os.path.join(args.output_dir, f"{case_id}_gold.json")
        if os.path.exists(target) and not args.force:
            skipped += 1
            continue
        payload = {
            "schema_version": "1.0",
            "source_case_id": case_id,
            "annotation_status": "pending",
            "reviewer_1": "",
            "reviewer_2": "",
            "adjudication_complete": False,
            "transcript_text": str(pred.get("english_text", "")),
            "annotations": [],
            "annotation_instructions": {
                "span_offsets": "Use zero-based, end-exclusive character offsets into transcript_text.",
                "fields": ["start", "end", "text", "entity_type", "assertion"],
                "entity_type": "Use the project entity taxonomy listed in docs/M4_EVALUATION_PROTOCOL.md.",
                "assertion": "PRESENT, ABSENT, POSSIBLE, or UNKNOWN based on transcript context.",
                "independence": "Annotate from transcript/source material, not by copying predicted entities. Use two independent reviewers and adjudicate disagreements.",
                "completion": "Set annotation_status to complete only after review/adjudication."
            }
        }
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        created += 1
    print(f"Created {created} local annotation template(s); skipped existing: {skipped}.")
    print("WARNING: templates include transcript text and may contain sensitive data. Do not publish or commit them.")


if __name__ == "__main__":
    main()
