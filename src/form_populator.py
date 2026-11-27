#!/usr/bin/env python3
"""Clinical form population from English ASR transcript segments.

The module deliberately preserves missing/uncertain information. A missing answer is
UNKNOWN, not a clinical negative. Every populated field records the transcript answer
used to derive it so a reviewer can trace the generated form back to its source.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

ASSERTION_STATUSES = {"PRESENT", "ABSENT", "POSSIBLE", "UNKNOWN"}


class CancerScreeningFormPopulator:
    """Populate a screening form using question/answer alignment and conservative rules."""

    QUESTION_START = re.compile(
        r"^(?:what|how|where|when|who|why|which|are\s+you|do\s+you|did\s+you|"
        r"have\s+you|has\s+you|is\s+there|is\s+your|any\s+|tell\s+me|can\s+you|could\s+you|"
        r"would\s+you|will\s+you|please\s+tell|अपका|आपका|आपकी|क्या|कितनी|कितना|कहाँ|कौन)",
        re.IGNORECASE,
    )

    QUESTION_HINTS = (
        "your name", "what is your", "how old", "date of birth", "did you study",
        "where have you studied", "what do you do", "are you married", "address",
        "father", "husband", "monthly family income", "mobile number", "phone number",
        "government scheme", "insurance", "weight", "height", "diabetes", "tested for",
        "cancer in your family", "family history", "alcohol", "tobacco", "exercise",
        "fast food", "lost weight", "fever", "wound", "lump", "swelling", "pain",
        "bleeding", "opening your mouth", "white or red", "chewing", "swallowing",
    )

    def __init__(self, question_start_cues: bool = True):
        # False = detect questions by "?" only (ablation baseline).
        self.question_start_cues = question_start_cues

    def _is_question(self, text: str) -> bool:
        value = text.strip()
        if not value:
            return False
        if value.endswith("?"):
            return True
        return self.question_start_cues and bool(self.QUESTION_START.search(value))

    def extract_qa_turns(self, segments: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
        """Pair each question segment with following answer segments until next question.

        ASR output often omits question marks. Question-start cues are therefore used
        alongside punctuation. Inline "Question? Answer" segments are split as well.
        """
        units: List[str] = []
        for segment in segments:
            text = str(segment.get("text", "")).strip()
            if not text:
                continue
            # Split a single ASR segment containing both a question and its answer.
            match = re.match(r"^(.*?\?)\s*(.+)$", text)
            if match and self._is_question(match.group(1)):
                units.append(match.group(1).strip())
                if match.group(2).strip():
                    units.append(match.group(2).strip())
            else:
                units.append(text)

        turns: List[Tuple[str, str]] = []
        current_question: Optional[str] = None
        current_answers: List[str] = []

        def flush() -> None:
            nonlocal current_question, current_answers
            if current_question is not None:
                turns.append((current_question, " ".join(current_answers).strip()))
            current_question = None
            current_answers = []

        for text in units:
            if self._is_question(text):
                flush()
                current_question = text
            elif current_question is not None:
                current_answers.append(text)
        flush()
        return turns

    @staticmethod
    def _normalise_answer(answer: str) -> str:
        return re.sub(r"\s+", " ", str(answer or "")).strip().strip(" .,:;")

    def _answer_lookup(self, qa_turns: List[Tuple[str, str]], keywords: List[str]) -> Tuple[str, Optional[str]]:
        """Return the first matching non-empty answer and its question."""
        lowered_keywords = [k.lower() for k in keywords]
        for question, answer in qa_turns:
            q_lower = question.lower()
            if any(keyword in q_lower for keyword in lowered_keywords):
                cleaned = self._normalise_answer(answer)
                if cleaned:
                    return cleaned, question
        return "", None

    def _binary_assertion(self, answer: str) -> str:
        """Conservative four-state assertion classifier for short interview answers."""
        text = self._normalise_answer(answer).lower()
        if not text:
            return "UNKNOWN"

        possible_patterns = (
            r"\b(maybe|perhaps|possibly|might|may be|not sure|unsure|uncertain)\b",
            r"\b(शायद|हो सकता है|पता नहीं)\b",
        )
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in possible_patterns):
            return "POSSIBLE"

        negative_patterns = (
            r"^(?:no|nope|nah|never|none|nil|negative|i do not|i don't|i have not|i haven't)\b",
            r"\b(नहीं|ना|कभी नहीं)\b",
            r"\b(?:do not|does not|did not|denies|without|absent)\b",
            r"\bnot\s+(?:present|having|experienced|using|taking|consumed|diagnosed)\b",
        )
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in negative_patterns):
            return "ABSENT"

        affirmative_patterns = (
            r"^(?:yes|yeah|yep|yup|haan|han|correct|i do|i have|i am|occasionally|sometimes)\b",
            r"\b(हाँ|हां|जी हाँ)\b",
        )
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in affirmative_patterns):
            return "PRESENT"

        return "UNKNOWN"

    def _binary_field(self, answer: str, question: Optional[str]) -> Dict[str, Any]:
        assertion = self._binary_assertion(answer)
        reported: Optional[bool]
        if assertion == "PRESENT":
            reported = True
        elif assertion == "ABSENT":
            reported = False
        else:
            reported = None
        return {
            "reported": reported,
            "assertion": assertion,
            "evidence": answer or None,
            "source_question": question,
        }

    def populate_form(
        self,
        en_transcript_data: Dict[str, Any],
        hi_transcript_data: Optional[Dict[str, Any]] = None,
        ner_result: Optional[Dict[str, Any]] = None,
        patient_id: str = "",
    ) -> Dict[str, Any]:
        """Populate form fields; unanswered items remain null/UNKNOWN."""
        segments = en_transcript_data.get("transcription", [])
        qa_turns = self.extract_qa_turns(segments)
        evidence: Dict[str, Dict[str, Optional[str]]] = {}

        def lookup(field: str, keywords: List[str]) -> str:
            answer, question = self._answer_lookup(qa_turns, keywords)
            evidence[field] = {"question": question, "answer": answer or None}
            return answer

        # Demographics: no values are inferred from patient IDs, names or other unrelated fields.
        name = self._parse_name(lookup("demographics.name", ["your name", "name?"]))
        age = self._parse_age(lookup("demographics.age", ["how old", "your age"]))
        dob = self._parse_dob(lookup("demographics.dob", ["date of birth", "birth?"]))
        education = self._parse_education(lookup("demographics.education", ["studied", "study", "education"]))
        occupation = self._parse_occupation(lookup("demographics.occupation", ["what do you do", "occupation", "doing now"]))
        marital = self._parse_marital(lookup("demographics.marital_status", ["married"]))
        address = self._parse_address(lookup("demographics.address", ["address", "where do you live"]))
        mobile = self._parse_mobile(lookup("demographics.mobile", ["mobile", "phone"]))
        father_husband = self._parse_person_name(lookup("demographics.father_or_husband_name", ["father", "husband"]))
        income = self._parse_income(lookup("demographics.monthly_family_income", ["income"]))
        insurance_answer = lookup("demographics.health_insurance", ["ayushman", "insurance", "scheme"])
        insurance = self._parse_insurance(insurance_answer)
        sex = None  # Sex is not inferred from a name or patient identifier.

        # Anthropometrics are sourced only from the corresponding Q&A answers.
        weight = self._parse_weight(lookup("clinical_indicators.weight_kg", ["weight"]))
        height = self._parse_height(lookup("clinical_indicators.height", ["height"]))

        # History and screening responses
        pmh_answer = lookup("history.past_medical_history", ["diabetes", "bp", "sugar", "sick like", "chronic illness"])
        pmh = self._parse_pmh(pmh_answer)
        screened_answer = lookup("history.ever_screened_for_cancer", ["tested for any cancer", "screened", "breast oral"])
        screened = self._binary_field(screened_answer, evidence["history.ever_screened_for_cancer"]["question"])

        fam_answer = ""
        fam_question = None
        for index, (question, answer) in enumerate(qa_turns):
            q_lower = question.lower()
            if any(term in q_lower for term in (
                "cancer in your family", "family history", "family cancer",
                "anyone in your family", "cancer at home", "anyone get cancer",
                "did anyone get cancer",
            )):
                fam_answer, fam_question = self._normalise_answer(answer), question
                # A consecutive "For what?" turn is a follow-up to the family-history answer.
                if index + 1 < len(qa_turns) and "for what" in qa_turns[index + 1][0].lower():
                    follow_up = self._normalise_answer(qa_turns[index + 1][1])
                    if follow_up:
                        fam_answer = (fam_answer + " " + follow_up).strip()
                break
        evidence["history.family_history_of_cancer"] = {"question": fam_question, "answer": fam_answer or None}
        fam_cancer = self._parse_fam_cancer(fam_answer)

        prior_tobacco_alcohol_answer = lookup("history.consumed_tobacco_or_alcohol", ["alcohol or tobacco", "tobacco or alcohol"])
        prior_tobacco_alcohol = self._binary_field(
            prior_tobacco_alcohol_answer, evidence["history.consumed_tobacco_or_alcohol"]["question"]
        )

        tobacco_answer = lookup("risk_factors.current_tobacco_use", ["use tobacco", "currently use tobacco", "consume tobacco"])
        current_tobacco = self._binary_field(tobacco_answer, evidence["risk_factors.current_tobacco_use"]["question"])
        alcohol_answer = lookup("risk_factors.alcohol_consumption", ["drink alcohol", "alcohol consumption"])
        alcohol = self._parse_alcohol(alcohol_answer)
        diet_answer = lookup("risk_factors.dietary_habits", ["vegetarian", "dietary", "shakahari"])
        diet = self._parse_diet(diet_answer)
        fast_food_answer = lookup("risk_factors.fast_food_habit", ["fast food", "fried food"])
        fast_food = self._binary_field(fast_food_answer, evidence["risk_factors.fast_food_habit"]["question"])
        activity_answer = lookup("risk_factors.physical_activity_level", ["exercise", "physical activity", "daily"])
        physical_activity = self._parse_physical_activity(activity_answer)

        def symptom(field: str, keywords: List[str]) -> Dict[str, Any]:
            answer = lookup(field, keywords)
            return self._binary_field(answer, evidence[field]["question"])

        # The PMH question explicitly names diabetes / BP / sugar, which are the
        # chronic-illness examples represented by this screening field. Reuse that
        # answer with explicit provenance rather than leaving a duplicate field UNKNOWN.
        chronic_field = "general_cancer_symptoms.known_chronic_illness_dm_htn_tb"
        evidence[chronic_field] = {
            "question": evidence["history.past_medical_history"]["question"],
            "answer": pmh_answer or None,
        }

        general_symptoms = {
            "unexplained_weight_loss": symptom("general_cancer_symptoms.unexplained_weight_loss", ["lost weight", "weight loss", "lost a lot"]),
            "persistent_fever_or_fatigue": symptom("general_cancer_symptoms.persistent_fever_or_fatigue", ["fever", "fatigue", "long fever", "sick or tired", "sick or fatigued"]),
            "non_healing_ulcer_or_wound": symptom("general_cancer_symptoms.non_healing_ulcer_or_wound", ["wound", "ulcer", "not healed"]),
            "lump_or_swelling_anywhere": symptom("general_cancer_symptoms.lump_or_swelling_anywhere", ["lump", "swelling", "sore throat or swelling"]),
            "persistent_pain_without_known_cause": symptom("general_cancer_symptoms.persistent_pain_without_known_cause", ["pain"]),
            "bleeding_from_any_site": symptom("general_cancer_symptoms.bleeding_from_any_site", ["bleeding"]),
            "known_chronic_illness_dm_htn_tb": self._binary_field(
                pmh_answer, evidence["history.past_medical_history"]["question"]
            ),
        }
        oral_screening = {
            "difficulty_in_opening_mouth": symptom("oral_cancer_screening.difficulty_in_opening_mouth", ["opening your mouth", "opening mouth"]),
            "white_or_red_patch_in_mouth": symptom("oral_cancer_screening.white_or_red_patch_in_mouth", ["white or red", "patch in mouth", "white wound"]),
            "ulcer_in_mouth_lasting_gt_2_weeks": symptom("oral_cancer_screening.ulcer_in_mouth_lasting_gt_2_weeks", ["ulcer in mouth", "wound in your mouth", "lasting"]),
            "difficulty_in_chewing_or_swallowing": symptom("oral_cancer_screening.difficulty_in_chewing_or_swallowing", ["chewing", "swallowing"]),
        }

        return {
            "schema_version": "2.0",
            "institution": "Government Institute of Medical Science, Greater Noida",
            "form_title": "Cancer Health Check up",
            "patient_id": patient_id or None,
            "demographics": {
                "name": name, "age": age, "dob": dob, "sex": sex,
                "education": education, "occupation": occupation, "marital_status": marital,
                "address": address, "mobile": mobile,
                "father_or_husband_name": father_husband,
                "monthly_family_income": income, "health_insurance": insurance,
            },
            "clinical_indicators": {
                "weight_kg": weight,
                "height": height,
                "bmi": self._compute_bmi(weight, height) if weight is not None and height else None,
                "pulse": None, "rr": None, "bp": None,
            },
            "history": {
                "past_medical_history": pmh,
                "ever_screened_for_cancer": {
                    "screened": screened["reported"], "details": screened_answer or None,
                    "assertion": screened["assertion"], "evidence": screened["evidence"],
                    "source_question": screened["source_question"],
                },
                "family_history_of_cancer": fam_cancer,
                "consumed_tobacco_or_alcohol": {
                    "present": prior_tobacco_alcohol["reported"],
                    "assertion": prior_tobacco_alcohol["assertion"],
                    "evidence": prior_tobacco_alcohol["evidence"],
                    "source_question": prior_tobacco_alcohol["source_question"],
                },
            },
            "risk_factors": {
                "current_tobacco_use": {
                    "current_user": current_tobacco["reported"],
                    "assertion": current_tobacco["assertion"],
                    "smoked": None, "smokeless": None, "duration": None,
                    "evidence": current_tobacco["evidence"],
                    "source_question": current_tobacco["source_question"],
                },
                "alcohol_consumption": alcohol,
                "dietary_habits": diet,
                "fast_food_habit": fast_food,
                "physical_activity_level": physical_activity,
            },
            "general_cancer_symptoms": general_symptoms,
            "oral_cancer_screening": oral_screening,
            "extraction_evidence": evidence,
            "processing_notes": [
                "Unanswered fields are UNKNOWN/null and are not interpreted as negative.",
                "Sex, weight, height and other demographics are not inferred from patient identifiers.",
                "Generated output requires clinician review before any real-world use.",
            ],
        }

    def _parse_name(self, answer: str) -> Optional[str]:
        value = self._normalise_answer(answer)
        value = re.sub(r"^(?:my name is|name is|i am|it is)\s+", "", value, flags=re.IGNORECASE)
        return value or None

    def _parse_person_name(self, answer: str) -> Optional[str]:
        value = self._normalise_answer(answer)
        value = re.sub(r"^(?:mr\.?|mrs\.?|ms\.?|dr\.?|master)\s+", "", value, flags=re.IGNORECASE)
        return value or None

    def _parse_age(self, answer: str) -> Optional[int]:
        match = re.search(r"\b(\d{1,3})\b", answer)
        if not match:
            return None
        age = int(match.group(1))
        return age if 0 < age <= 120 else None

    def _parse_dob(self, answer: str) -> Optional[str]:
        value = self._normalise_answer(answer)
        return value or None

    def _parse_education(self, answer: str) -> Optional[str]:
        value = self._normalise_answer(answer)
        if not value:
            return None
        lower = value.lower()
        if "mbbs" in lower:
            return "MBBS"
        if "nursing" in lower or "b.sc" in lower or "bsc" in lower:
            return "BSc Nursing"
        if "msw" in lower:
            return "MSW"
        if "post grad" in lower or "postgraduation" in lower or "master" in lower:
            return "Post Graduation"
        if "graduat" in lower:
            return "Graduation"
        return value

    def _parse_occupation(self, answer: str) -> Optional[str]:
        value = self._normalise_answer(answer)
        if not value:
            return None
        lower = value.lower()
        if "pgjr" in lower or "junior resident" in lower:
            return "PGJR (Junior Resident)"
        if "nursing officer" in lower:
            return "Nursing Officer"
        if "msw" in lower or "social worker" in lower:
            return "Medical Social Worker"
        return value

    def _parse_marital(self, answer: str) -> Optional[str]:
        status = self._binary_assertion(answer)
        if status == "PRESENT":
            return "Married"
        if status == "ABSENT":
            return "Unmarried"
        value = self._normalise_answer(answer)
        if re.search(r"\b(married|unmarried|single)\b", value, re.IGNORECASE):
            return value
        return None

    def _parse_address(self, answer: str) -> Optional[str]:
        value = self._normalise_answer(answer)
        value = re.sub(r"^(?:i live in|my address is|address is)\s+", "", value, flags=re.IGNORECASE)
        return value or None

    def _parse_mobile(self, answer: str) -> Optional[str]:
        value = self._normalise_answer(answer)
        if not value:
            return None
        digits = re.sub(r"\D", "", value)
        # Do not turn a partial/garbled ASR sequence into a contact number.
        return digits if len(digits) == 10 else None

    def _parse_income(self, answer: str) -> Optional[str]:
        value = self._normalise_answer(answer)
        return value or None

    def _parse_insurance(self, answer: str) -> Optional[str]:
        status = self._binary_assertion(answer)
        if status == "PRESENT":
            return self._normalise_answer(answer)
        if status == "ABSENT":
            return "No"
        return self._normalise_answer(answer) or None

    def _parse_weight(self, answer: str) -> Optional[float]:
        match = re.search(r"\b(\d{1,3}(?:\.\d+)?)\s*(?:kg|kilos?)?\b", answer, re.IGNORECASE)
        if not match:
            return None
        value = float(match.group(1))
        return value if 1 <= value <= 400 else None

    def _parse_height(self, answer: str) -> Optional[str]:
        value = self._normalise_answer(answer)
        if not value:
            return None
        # Do not silently assign a unit to a bare number. BMI is computed only with units.
        return value

    def _compute_bmi(self, weight: float, height: Optional[str]) -> Optional[float]:
        if not height:
            return None
        cm_match = re.search(r"(\d{2,3}(?:\.\d+)?)\s*cm\b", height, re.IGNORECASE)
        feet_match = re.search(r"(\d)\s*(?:ft|')\s*(\d{1,2})?\s*(?:in|\")?", height, re.IGNORECASE)
        try:
            if cm_match:
                height_m = float(cm_match.group(1)) / 100
            elif feet_match:
                feet = float(feet_match.group(1))
                inches = float(feet_match.group(2) or 0)
                height_m = (feet * 12 + inches) * 0.0254
            else:
                return None
            if not 0.5 <= height_m <= 2.5:
                return None
            return round(weight / (height_m * height_m), 1)
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    def _parse_pmh(self, answer: str) -> Dict[str, Any]:
        status = self._binary_assertion(answer)
        details = None
        if status == "PRESENT":
            lower = answer.lower()
            if "bp" in lower or "hypertension" in lower:
                details = "Hypertension (BP)"
            elif "sugar" in lower or "diabetes" in lower:
                details = "Diabetes Mellitus"
            else:
                details = self._normalise_answer(answer)
        elif status == "ABSENT":
            details = "Explicitly denied"
        return {
            "present": True if status == "PRESENT" else False if status == "ABSENT" else None,
            "details": details,
            "assertion": status,
            "evidence": answer or None,
        }

    def _parse_fam_cancer(self, answer: str) -> Dict[str, Any]:
        status = self._binary_assertion(answer)
        value = answer.lower()
        mentions_relative = any(term in value for term in (
            "mother", "mummy", "mom", "father", "papa", "dad", "sister", "brother", "relative"
        ))
        # In response to a direct family-cancer question, a relative-only answer
        # (e.g. "mother") is a positive answer even when ASR omitted "yes".
        if status == "UNKNOWN" and mentions_relative:
            status = "PRESENT"
        # "No. It happened in a relative." both denies and reports a relative. Keep the
        # explicit denial (it answers the question asked) but flag it for clinician review.
        needs_review = status == "ABSENT" and mentions_relative
        review_note = (
            "Answer denies family history but also mentions a relative; confirm with patient."
            if needs_review else None
        )
        cancer_type = None
        relative = None
        if status == "PRESENT":
            if "breast" in value:
                cancer_type = "Breast cancer"
            elif "oral" in value or "mouth" in value:
                cancer_type = "Oral cancer"
            elif "cervical" in value:
                cancer_type = "Cervical cancer"
            if any(term in value for term in ("mother", "mummy", "mom")):
                relative = "Mother"
            elif any(term in value for term in ("father", "papa", "dad")):
                relative = "Father"
            elif "sister" in value:
                relative = "Sister"
            elif "brother" in value:
                relative = "Brother"
            else:
                relative = "Family member (unspecified)"
        return {
            "present": True if status == "PRESENT" else False if status == "ABSENT" else None,
            "cancer_type": cancer_type,
            "relative": relative,
            "assertion": status,
            "evidence": answer or None,
            "needs_review": needs_review,
            "review_note": review_note,
        }

    def _parse_alcohol(self, answer: str) -> Optional[str]:
        value = self._normalise_answer(answer)
        if not value:
            return None
        lower = value.lower()
        status = self._binary_assertion(value)
        if status == "ABSENT":
            return "Never"
        if "occasional" in lower or "sometimes" in lower:
            return "Occasional"
        if "daily" in lower or "regular" in lower:
            return "Regular"
        if status == "PRESENT":
            return value
        return value

    def _parse_diet(self, answer: str) -> Optional[str]:
        value = self._normalise_answer(answer)
        if not value:
            return None
        lower = value.lower()
        if "vegetarian" in lower or "shakahari" in lower:
            return "Predominantly Vegetarian"
        if "non-vegetarian" in lower or "non vegetarian" in lower or "mixed" in lower:
            return "Mixed / Non-vegetarian"
        return value

    def _parse_physical_activity(self, answer: str) -> Optional[str]:
        value = self._normalise_answer(answer)
        if not value:
            return None
        lower = value.lower()
        if "daily" in lower or "1 hour" in lower or "regular" in lower:
            return "Regular"
        if "occasional" in lower or "sometimes" in lower:
            return "Occasional"
        if "no exercise" in lower or "sedentary" in lower or self._binary_assertion(value) == "ABSENT":
            return "No/low activity reported"
        return value

    @staticmethod
    def _display(value: Any) -> str:
        return "Not reported" if value is None or value == "" else str(value)

    @staticmethod
    def _status_label(status: Optional[str]) -> str:
        return {
            "PRESENT": "YES (reported)",
            "ABSENT": "NO (explicitly denied)",
            "POSSIBLE": "POSSIBLE / UNCERTAIN",
            "UNKNOWN": "UNKNOWN (not answered / unclear)",
        }.get(status or "UNKNOWN", "UNKNOWN")

    def generate_markdown_report(self, form: Dict[str, Any]) -> str:
        demo = form["demographics"]
        clin = form["clinical_indicators"]
        hist = form["history"]
        risk = form["risk_factors"]
        gen = form["general_cancer_symptoms"]
        oral = form["oral_cancer_screening"]

        md = [
            f"# {form['institution']}",
            f"## {form['form_title']} Form Record",
            f"**Patient Identifier:** `{self._display(form.get('patient_id'))}`",
            "",
            "> Draft generated from speech transcripts. This is not a diagnosis and requires clinical review.",
            "",
            "### 1. Patient Demographic Profile",
            "| Field | Extracted information |",
            "|---|---|",
        ]
        demographic_labels = {
            "name": "Patient name", "age": "Age", "dob": "Date of birth", "sex": "Sex",
            "education": "Education", "occupation": "Occupation", "marital_status": "Marital status",
            "address": "Address", "mobile": "Mobile", "father_or_husband_name": "Father's / husband's name",
            "monthly_family_income": "Monthly family income", "health_insurance": "Health insurance",
        }
        for key, label in demographic_labels.items():
            md.append(f"| {label} | {self._display(demo.get(key))} |")

        md += [
            "", "### 2. Clinical and Anthropometric Indicators", "| Parameter | Value |", "|---|---|",
            f"| Weight | {self._display(clin.get('weight_kg'))} kg |",
            f"| Height | {self._display(clin.get('height'))} |",
            f"| BMI | {self._display(clin.get('bmi'))} |",
            f"| Pulse | {self._display(clin.get('pulse'))} |",
            f"| Respiratory rate | {self._display(clin.get('rr'))} |",
            f"| Blood pressure | {self._display(clin.get('bp'))} |",
            "", "### 3. Medical and Family History", "| Field | Status | Evidence |", "|---|---|---|",
        ]
        for key, label in [
            ("past_medical_history", "Past medical history"),
            ("ever_screened_for_cancer", "Ever screened for cancer"),
            ("family_history_of_cancer", "Family history of cancer"),
            ("consumed_tobacco_or_alcohol", "Prior tobacco or alcohol use"),
        ]:
            item = hist.get(key, {})
            evidence = item.get("evidence") or item.get("details")
            status = self._status_label(item.get("assertion"))
            if item.get("needs_review"):
                status += f" ⚠ REVIEW: {item.get('review_note')}"
            md.append(f"| {label} | {status} | {self._display(evidence)} |")

        md += ["", "### 4. Behavioral and Lifestyle Risk Factors", "| Field | Extracted information |", "|---|---|"]
        tobacco = risk.get("current_tobacco_use", {})
        md.append(f"| Current tobacco use | {self._status_label(tobacco.get('assertion'))} |")
        md.append(f"| Alcohol consumption | {self._display(risk.get('alcohol_consumption'))} |")
        md.append(f"| Dietary habits | {self._display(risk.get('dietary_habits'))} |")
        fast_food = risk.get("fast_food_habit", {})
        md.append(f"| Fast food / fried food | {self._status_label(fast_food.get('assertion'))} |")
        md.append(f"| Physical activity | {self._display(risk.get('physical_activity_level'))} |")

        md += ["", "### 5. General Cancer Warning Signs", "| Screening field | Status | Evidence |", "|---|---|---|"]
        general_labels = {
            "unexplained_weight_loss": "Unexplained weight loss",
            "persistent_fever_or_fatigue": "Persistent fever / fatigue",
            "non_healing_ulcer_or_wound": "Non-healing ulcer / wound",
            "lump_or_swelling_anywhere": "Lump / swelling",
            "persistent_pain_without_known_cause": "Persistent pain",
            "bleeding_from_any_site": "Bleeding from any site",
            "known_chronic_illness_dm_htn_tb": "Known chronic illness",
        }
        for key, label in general_labels.items():
            item = gen.get(key, {})
            md.append(f"| {label} | {self._status_label(item.get('assertion'))} | {self._display(item.get('evidence'))} |")

        md += ["", "### 6. Oral Cancer Screening", "| Screening field | Status | Evidence |", "|---|---|---|"]
        oral_labels = {
            "difficulty_in_opening_mouth": "Difficulty opening mouth",
            "white_or_red_patch_in_mouth": "White / red patch in mouth",
            "ulcer_in_mouth_lasting_gt_2_weeks": "Oral ulcer lasting more than two weeks",
            "difficulty_in_chewing_or_swallowing": "Difficulty chewing / swallowing",
        }
        for key, label in oral_labels.items():
            item = oral.get(key, {})
            md.append(f"| {label} | {self._status_label(item.get('assertion'))} | {self._display(item.get('evidence'))} |")

        md += ["", "### 7. Extraction Traceability", "Each populated field records the transcript question and answer used by the extractor. Unanswered fields remain UNKNOWN/null.", ""]
        for field, source in form.get("extraction_evidence", {}).items():
            md.append(f"- **{field}:** Q: {self._display(source.get('question'))}; A: {self._display(source.get('answer'))}")
        md += ["", "---", "*Generated by the Clinical Speech-to-Text & Information Extraction Pipeline. Human verification is required before clinical use.*"]
        return "\n".join(md) + "\n"


if __name__ == "__main__":
    print("Import CancerScreeningFormPopulator and call populate_form() with transcript JSON.")
