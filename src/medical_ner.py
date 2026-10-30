#!/usr/bin/env python3
"""
Medical NER, Assertion Detection, Relation Extraction, and Ontology Grounding Module
Implements the clinical information extraction workflow described in:
- HindiNERWorkflow.docx (Hindi/Code-mixed Clinical Speech to English Medical NER)
- IEhealthcare4RUAS-17thApr2025.pptx (Oracle AI / IIIT-Delhi Clinical NLP Architecture)
"""

import re
import os
import json
from typing import Dict, List, Any, Optional

# Medical Ontology Mapping Dictionary (SNOMED-CT / UMLS)
ONTOLOGY_MAPPINGS = {
    # Symptoms & Conditions
    "high fever": {"concept_id": "386661006", "ontology": "SNOMED-CT", "preferred_term": "Pyrexia", "cui": "C0015967"},
    "fever": {"concept_id": "386661006", "ontology": "SNOMED-CT", "preferred_term": "Fever", "cui": "C0015967"},
    "fatigue": {"concept_id": "84229001", "ontology": "SNOMED-CT", "preferred_term": "Fatigue", "cui": "C0015672"},
    "weight loss": {"concept_id": "89362005", "ontology": "SNOMED-CT", "preferred_term": "Unintentional weight loss", "cui": "C0043096"},
    "wound": {"concept_id": "13930003", "ontology": "SNOMED-CT", "preferred_term": "Wound", "cui": "C0043187"},
    "non-healing ulcer": {"concept_id": "56208002", "ontology": "SNOMED-CT", "preferred_term": "Ulcer", "cui": "C0041582"},
    "ulcer": {"concept_id": "56208002", "ontology": "SNOMED-CT", "preferred_term": "Ulcer", "cui": "C0041582"},
    "lump": {"concept_id": "300844002", "ontology": "SNOMED-CT", "preferred_term": "Mass of body structure", "cui": "C0577559"},
    "swelling": {"concept_id": "65124004", "ontology": "SNOMED-CT", "preferred_term": "Swelling", "cui": "C0038999"},
    "persistent pain": {"concept_id": "22253000", "ontology": "SNOMED-CT", "preferred_term": "Pain", "cui": "C0030193"},
    "pain": {"concept_id": "22253000", "ontology": "SNOMED-CT", "preferred_term": "Pain", "cui": "C0030193"},
    "bleeding": {"concept_id": "131148009", "ontology": "SNOMED-CT", "preferred_term": "Bleeding", "cui": "C0019080"},
    
    # Oral Cancer Signs
    "mouth opening difficulty": {"concept_id": "46241004", "ontology": "SNOMED-CT", "preferred_term": "Trismus", "cui": "C0041105"},
    "trismus": {"concept_id": "46241004", "ontology": "SNOMED-CT", "preferred_term": "Trismus", "cui": "C0041105"},
    "white patch": {"concept_id": "24540003", "ontology": "SNOMED-CT", "preferred_term": "Leukoplakia of oral mucosa", "cui": "C0023531"},
    "red patch": {"concept_id": "25458004", "ontology": "SNOMED-CT", "preferred_term": "Erythroplakia of oral mucosa", "cui": "C0014781"},
    "oral ulcer": {"concept_id": "26284000", "ontology": "SNOMED-CT", "preferred_term": "Recurrent aphthous stomatitis / Oral ulcer", "cui": "C0149745"},
    "chewing difficulty": {"concept_id": "399122002", "ontology": "SNOMED-CT", "preferred_term": "Difficulty chewing", "cui": "C0241443"},
    "swallowing difficulty": {"concept_id": "40739000", "ontology": "SNOMED-CT", "preferred_term": "Dysphagia", "cui": "C0011168"},
    "dysphagia": {"concept_id": "40739000", "ontology": "SNOMED-CT", "preferred_term": "Dysphagia", "cui": "C0011168"},

    # Cancer and Systemic Diseases
    "cancer": {"concept_id": "363346000", "ontology": "SNOMED-CT", "preferred_term": "Malignant neoplastic disease", "cui": "C0006826"},
    "breast cancer": {"concept_id": "254837009", "ontology": "SNOMED-CT", "preferred_term": "Malignant neoplasm of breast", "cui": "C0006142"},
    "oral cancer": {"concept_id": "363406005", "ontology": "SNOMED-CT", "preferred_term": "Malignant neoplasm of oral cavity", "cui": "C0027651"},
    "cervical cancer": {"concept_id": "363354003", "ontology": "SNOMED-CT", "preferred_term": "Malignant neoplasm of cervix uteri", "cui": "C0007847"},
    "diabetes": {"concept_id": "73211009", "ontology": "SNOMED-CT", "preferred_term": "Diabetes mellitus", "cui": "C0011849"},
    "hypertension": {"concept_id": "38341003", "ontology": "SNOMED-CT", "preferred_term": "Hypertensive disorder", "cui": "C0020538"},
    "high bp": {"concept_id": "38341003", "ontology": "SNOMED-CT", "preferred_term": "Hypertension", "cui": "C0020538"},
    "tuberculosis": {"concept_id": "56717001", "ontology": "SNOMED-CT", "preferred_term": "Tuberculosis", "cui": "C0041296"},

    # Risk Factors
    "tobacco": {"concept_id": "7200002", "ontology": "SNOMED-CT", "preferred_term": "Tobacco smoking behavior", "cui": "C0040329"},
    "cigarette": {"concept_id": "65568007", "ontology": "SNOMED-CT", "preferred_term": "Cigarette smoker", "cui": "C0008688"},
    "bidi": {"concept_id": "897148007", "ontology": "SNOMED-CT", "preferred_term": "Bidi smoker", "cui": "C5441993"},
    "gutkha": {"concept_id": "228509002", "ontology": "SNOMED-CT", "preferred_term": "Chewing tobacco user", "cui": "C0008034"},
    "khaini": {"concept_id": "228509002", "ontology": "SNOMED-CT", "preferred_term": "Chewing tobacco user", "cui": "C0008034"},
    "alcohol": {"concept_id": "160573003", "ontology": "SNOMED-CT", "preferred_term": "Alcohol intake", "cui": "C0001948"},
    
    # Anatomy
    "breast": {"concept_id": "76752008", "ontology": "SNOMED-CT", "preferred_term": "Breast structure", "cui": "C0006141"},
    "mouth": {"concept_id": "123851003", "ontology": "SNOMED-CT", "preferred_term": "Mouth structure", "cui": "C0226896"},
    "oral cavity": {"concept_id": "123851003", "ontology": "SNOMED-CT", "preferred_term": "Mouth structure", "cui": "C0226896"},
    "cervix": {"concept_id": "71252005", "ontology": "SNOMED-CT", "preferred_term": "Cervix uteri structure", "cui": "C0007873"},
    "body": {"concept_id": "38266002", "ontology": "SNOMED-CT", "preferred_term": "Entire body structure", "cui": "C1268086"}
}


class ClinicalNEREngine:
    """
    Extracts Named Entities, Assertion Status, Relations, and SNOMED Concept Mappings
    from bilingual consultation transcripts.
    """

    def __init__(self):
        self.ontology = ONTOLOGY_MAPPINGS

    def parse_turns(self, transcript_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Groups transcript segments into question-answer turns between Doctor and Patient.
        """
        turns = []
        current_q = None
        current_a = []

        for seg in transcript_segments:
            text = seg.get("text", "").strip()
            if not text:
                continue

            # Question indicators
            is_question = (
                text.endswith("?") or 
                any(k in text.lower() for k in [
                    "your name", "how old", "what is your", "where have you", 
                    "are you married", "address", "father's name", "husband's name",
                    "monthly income", "health insurance", "weight", "height",
                    "have you ever", "do you drink", "do you exercise", "diet",
                    "नाप", "उम्र", "पिता", "पता", "वजन", "बीमारी", "कैंसर", "तंबाकू", "शराब"
                ])
            )

            if is_question and current_q:
                # Save previous turn
                turns.append({
                    "question": current_q,
                    "answer": " ".join([s.get("text", "").strip() for s in current_a]),
                    "segments": [current_q] + current_a
                })
                current_q = seg
                current_a = []
            elif is_question and not current_q:
                current_q = seg
            else:
                if current_q:
                    current_a.append(seg)
                else:
                    # Statement before first question
                    turns.append({
                        "question": seg,
                        "answer": "",
                        "segments": [seg]
                    })

        if current_q:
            turns.append({
                "question": current_q,
                "answer": " ".join([s.get("text", "").strip() for s in current_a]),
                "segments": [current_q] + current_a
            })

        return turns

    def detect_entities(self, text: str, lang: str = "en") -> List[Dict[str, Any]]:
        """
        Detects medical named entities with offsets, canonical term, entity type, and ontology mapping.
        """
        entities = []
        lower_text = text.lower()

        patterns = [
            # Demographics
            (r"(?:name is|dr\.|mr\.|mrs\.|ms\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", "PATIENT_NAME"),
            (r"\b(\d{1,2})\s*(?:years old|years|y/o|साल)\b", "AGE"),
            (r"\b(\d{1,2}[\s\/\.\-]+\d{1,2}[\s\/\.\-]+(?:\d{4}|\d{2}))\b", "DOB"),
            (r"\b(mbbs|b\.?sc nursing|graduation|post graduation|msw|matric|intermediate|10th|12th)\b", "EDUCATION"),
            (r"\b(pgjr|junior resident|nursing officer|doctor|medical social worker|job|service|student)\b", "OCCUPATION"),
            (r"\b(unmarried|married|single|विवाहित|अविवाहित)\b", "MARITAL_STATUS"),
            (r"\b(bareilly|noida|greater noida|aligarh|delhi|up|बरेली|नोएडा)\b", "ADDRESS"),
            (r"\b(\d{10}|\d{4}[\s\-]\d{4}[\s\-]\d{2})\b", "CONTACT_PHONE"),
            (r"\b(\d{1,3}(?:,\d{3})*|\d+)\s*(?:thousand|lakh|lakhs|k|रू|हजार|लाख)\b", "FAMILY_INCOME"),
            (r"\b(ayushman|esic|insurance|आयुष्मान)\b", "HEALTH_INSURANCE"),

            # Vitals
            (r"\b(\d{2,3})\s*(?:kg|kilos|किलो)\b", "WEIGHT"),
            (r"\b(\d{1,3}\s*(?:cm|cms|feet|inch|\'|\"))\b", "HEIGHT"),

            # Conditions & Symptoms
            (r"\b(high fever|fever|बुखार)\b", "SIGN_SYMPTOM"),
            (r"\b(fatigue|tiredness|थकान)\b", "SIGN_SYMPTOM"),
            (r"\b(weight loss|वजन कम)\b", "SIGN_SYMPTOM"),
            (r"\b(non-healing ulcer|ulcer|wound|छाला|घाव)\b", "SIGN_SYMPTOM"),
            (r"\b(lump|swelling|गांठ|सूजन)\b", "SIGN_SYMPTOM"),
            (r"\b(pain|body ache|दर्द)\b", "SIGN_SYMPTOM"),
            (r"\b(bleeding|खून बहना)\b", "SIGN_SYMPTOM"),
            (r"\b(diabetes|sugar|मधुमेह)\b", "DIAGNOSIS"),
            (r"\b(hypertension|high bp|bp|रक्तचाप)\b", "DIAGNOSIS"),
            (r"\b(tuberculosis|tb|टीबी)\b", "DIAGNOSIS"),

            # Cancer Types
            (r"\b(breast cancer|ब्रेस्ट कैंसर|स्तन कैंसर)\b", "CANCER_TYPE"),
            (r"\b(oral cancer|मुंह का कैंसर)\b", "CANCER_TYPE"),
            (r"\b(cervical cancer|गर्भाशय ग्रीवा कैंसर)\b", "CANCER_TYPE"),
            (r"\b(cancer|कैंसर)\b", "CANCER_TYPE"),

            # Oral signs
            (r"\b(difficulty in opening mouth|mouth opening|मुंह खोलने में दिक्कत)\b", "ORAL_SIGN"),
            (r"\b(white patch|red patch|patch|सफेद दाग|लाल चकत्ते)\b", "ORAL_SIGN"),
            (r"\b(difficulty in chewing|difficulty in swallowing|चबाने में दिक्कत|निगलने में परेशानी)\b", "ORAL_SIGN"),

            # Risk Factors
            (r"\b(cigarette|bidi|gutkha|khaini|pan|tobacco|तंबाकू|बीड़ी|सिगरेट|गुटखा)\b", "RISK_FACTOR_TOBACCO"),
            (r"\b(alcohol|liquor|wine|beer|शराब|मदिरा)\b", "RISK_FACTOR_ALCOHOL"),
            (r"\b(vegetarian|mixed|non-vegetarian|शाकाहारी|मांसाहारी)\b", "DIETARY_HABIT"),
            (r"\b(fast food|fried food|junk food)\b", "DIETARY_HABIT"),
            (r"\b(regular exercise|occasional exercise|sedentary|daily \d+ hour|कसरत|व्यायाम)\b", "PHYSICAL_ACTIVITY"),

            # Family Members
            (r"\b(mother|mummy|father|papa|brother|sister|relative|माता|पिता|भाई|बहन)\b", "FAMILY_MEMBER"),

            # Durations
            (r"\b(last 6 months|last 2 weeks|>2 weeks|<5 years|5-10 years|>10 years|पिछले 6 महीने)\b", "DURATION")
        ]

        seen_spans = set()
        for pattern, entity_type in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                span_text = match.group(0).strip()
                start, end = match.span()
                key = (start, end)
                if key in seen_spans:
                    continue
                seen_spans.add(key)

                # Canonical and ontology lookup
                lookup_key = span_text.lower()
                ontology_info = None
                for term, info in self.ontology.items():
                    if term in lookup_key:
                        ontology_info = info
                        break

                entities.append({
                    "span": span_text,
                    "start": start,
                    "end": end,
                    "entity_type": entity_type,
                    "ontology_grounding": ontology_info
                })

        return entities

    def detect_assertions(self, text: str, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detects assertion status for each entity:
        - PRESENT (Affirmed)
        - ABSENT (Negated)
        - POSSIBLE (Suspected/Uncertain)
        """
        negation_terms = [
            r"\bno\b", r"\bnot\b", r"\bdenies\b", r"\bnever\b", r"\bwithout\b",
            r"\bनहीं\b", r"\bना\b", r"\bकभी नहीं\b"
        ]
        possible_terms = [
            r"\bpossible\b", r"\bsuspected\b", r"\bmaybe\b", r"\brule out\b",
            r"\bशायद\b", r"\bहो सकता है\b"
        ]

        enriched = []
        for ent in entities:
            # Look at a surrounding window of 60 characters before and after the entity
            window_start = max(0, ent["start"] - 60)
            window_end = min(len(text), ent["end"] + 60)
            context = text[window_start:window_end].lower()

            assertion = "PRESENT"
            for n_term in negation_terms:
                if re.search(n_term, context, re.IGNORECASE):
                    assertion = "ABSENT"
                    break
            
            if assertion == "PRESENT":
                for p_term in possible_terms:
                    if re.search(p_term, context, re.IGNORECASE):
                        assertion = "POSSIBLE"
                        break

            item = dict(ent)
            item["assertion"] = assertion
            enriched.append(item)

        return enriched

    def extract_relations(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extracts clinical relations between entities:
        - FamilyHistory_Of(CANCER_TYPE, FAMILY_MEMBER)
        - Site_Of(SIGN_SYMPTOM, ANATOMICAL_SITE)
        - Duration_Of(HABIT / SYMPTOM, DURATION)
        - Status_Of(RISK_FACTOR, ASSERTION)
        """
        relations = []

        # Find Cancer -> Family Member relations
        cancers = [e for e in entities if e["entity_type"] == "CANCER_TYPE"]
        relatives = [e for e in entities if e["entity_type"] == "FAMILY_MEMBER"]
        for c in cancers:
            for r in relatives:
                # If they are close in text (< 120 chars)
                if abs(c["start"] - r["start"]) < 120:
                    relations.append({
                        "relation_type": "FamilyHistory_Of",
                        "head": {"span": c["span"], "type": c["entity_type"]},
                        "tail": {"span": r["span"], "type": r["entity_type"]},
                        "assertion": c.get("assertion", "PRESENT")
                    })

        # Find Risk Factor -> Assertion / Duration relations
        risk_factors = [e for e in entities if "RISK_FACTOR" in e["entity_type"]]
        durations = [e for e in entities if e["entity_type"] == "DURATION"]
        for rf in risk_factors:
            relations.append({
                "relation_type": "Status_Of",
                "head": {"span": rf["span"], "type": rf["entity_type"]},
                "tail": {"assertion": rf.get("assertion", "ABSENT")},
            })
            for d in durations:
                if abs(rf["start"] - d["start"]) < 80:
                    relations.append({
                        "relation_type": "Duration_Of",
                        "head": {"span": rf["span"], "type": rf["entity_type"]},
                        "tail": {"span": d["span"], "type": d["entity_type"]},
                    })

        return relations

    def process_consultation(
        self,
        hindi_transcript_path: str,
        english_transcript_path: str
    ) -> Dict[str, Any]:
        """
        Executes the full pipeline on bilingual transcripts:
        ASR Segmentation -> Entity Detection -> Assertion Detection -> Relation Extraction -> Grounding.
        """
        with open(english_transcript_path, "r", encoding="utf-8", errors="replace") as f:
            en_data = json.load(f)

        hi_data = {}
        if hindi_transcript_path and os.path.exists(hindi_transcript_path):
            with open(hindi_transcript_path, "r", encoding="utf-8", errors="replace") as f:
                hi_data = json.load(f)

        en_segments = en_data.get("transcription", [])
        hi_segments = hi_data.get("transcription", [])

        # Full joined text
        en_full_text = " ".join([s.get("text", "").strip() for s in en_segments])
        hi_full_text = " ".join([s.get("text", "").strip() for s in hi_segments])

        # Group turns
        turns = self.parse_turns(en_segments)

        # Entity recognition & assertion detection
        entities = self.detect_entities(en_full_text, lang="en")
        entities_with_assertion = self.detect_assertions(en_full_text, entities)

        # Relation extraction
        relations = self.extract_relations(entities_with_assertion)

        return {
            "english_text": en_full_text,
            "hindi_text": hi_full_text,
            "turns_count": len(turns),
            "turns": turns,
            "entities": entities_with_assertion,
            "relations": relations,
            "ontology_grounded_count": sum(1 for e in entities_with_assertion if e.get("ontology_grounding") is not None)
        }


if __name__ == "__main__":
    import sys
    engine = ClinicalNEREngine()
    en_file = sys.argv[1] if len(sys.argv) > 1 else "outputs/transcripts/Praveen_en.json"
    hi_file = sys.argv[2] if len(sys.argv) > 2 else "outputs/transcripts/Praveen_hi.json"
    result = engine.process_consultation(hi_file, en_file)
    print(f"Entities found: {len(result['entities'])}")
    print(f"Relations found: {len(result['relations'])}")
    print(json.dumps(result["entities"][:5], indent=2))
