# Presentation Guide: NLP Final Project

How to present this project for the highest marks: the storyline, what each slide must say, the live demo, related work, and answers to likely viva questions. The updated deck is `preasentation/Clinical_NLP_Final_Presentation.pptx`.

---

## 1. The storyline (memorise this)

> We turn Hindi doctor–patient conversations into a structured cancer-screening form. Speech is recognised and translated by Whisper. Our NLP layer finds clinical entities, decides whether each one was affirmed, denied or uncertain, and **projects every entity back to the original Hindi words**, which is the cross-lingual alignment the brief asked for. When we measured *where* the system fails, we found that **three quarters of the missing answers were lost in speech recognition and translation, before any NLP ran**. We also show that the obvious accuracy number is misleading: a system that always says "no" scores 96% on this data.

Every slide should support one part of that paragraph.

## 2. Slide plan (about 15 minutes + demo)

| # | Slide | Key message / numbers | Time |
|---|---|---|---|
| 1 | Title | Project, team, course | 0:20 |
| 2 | Problem | Hindi/code-mixed speech → structured form. Why it's hard: ASR noise, code-mixing, negation, questions vs answers | 1:00 |
| 3 | Brief and our approach | The brief: alignment-aware cross-lingual NER. Our answer: English NLP plus Hindi span projection | 0:45 |
| 4 | Related work | Whisper, NegEx/ConText, i2b2 2010 assertions, annotation projection, GLiNER, ACI-BENCH (see §4) | 1:00 |
| 5 | Architecture | Pipeline diagram with the **alignment** stage visible | 1:00 |
| 6 | Worked example | Uday: audio → transcript → entities → Hindi span → form field + evidence | 1:00 |
| 7 | NLP methods 1 | Dialogue Q/A segmentation; rule NER; 4-state assertion (ConText-style scope, question detection) | 1:00 |
| 8 | NLP methods 2: alignment | Timestamp anchoring + phonetic skeleton (कैंसर/कानसर/खंसर → one form) + hallucination filter | 1:00 |
| 9 | Evaluation design | 4-state metrics, coverage vs selective accuracy, why UNKNOWN ≠ ABSENT | 0:45 |
| 10 | Results | 39.3% exact, 39.3% coverage, 100% selective (22/22). **Trivial baseline 96.4%, 0% PRESENT recall** | 1:15 |
| 11 | Ablation | Question detection 16 → 0 errors; phonetic alignment 14.8% → 23.3% | 1:00 |
| 12 | Error propagation | 34 misses: 59% ASR, 15% translation, 26% NLP, 0% answer parsing | 1:15 |
| 13 | ASR quality | Hallucination: 71% of Uday's Hindi audio; English repetition loops. WER/CER once references are done | 0:45 |
| 14 | NER evaluation | P/R/F1 + inter-annotator κ (after TEAM_TASKS 1–2), rules vs GLiNER (after task 5) | 1:00 |
| 15 | Bug found and fixed | Family-history disagreement: question mentions counted as facts → fixed and regression-tested | 0:45 |
| 16 | Demo | Live dashboard (see §3) | 3:00 |
| 17 | Limitations and future work | See §5 | 0:45 |
| 18 | Conclusion | Three takeaways | 0:30 |

**Split the speaking:** each teammate presents the part they built. Examiners often ask "who did what".

## 3. Live demo script (3 minutes)

Before the talk: run `python3 src/serve.py`, open http://127.0.0.1:8080, and have the backup video ready.

1. **Case 005 (Uday)**, Form overview: "Here is the generated form. Every value links to the question and answer it came from." Scroll to **Extraction evidence**.
2. Point at **Family history: ABSENT, ⚠ review**: "The patient said 'No… it happened in a relative'. We flag contradictions instead of guessing."
3. **Transcripts** tab: "Hindi on the left, English on the right. Whisper heard 'Uday' as 'Odai'. ASR errors propagate."
4. **Medical entities** tab: the **Hindi span** column. "Each English entity is projected back to the Hindi words. Here 'pitaji' is aligned to 'father'." Then open **Case 002 (Praveen)** and show `cancer → खणसर`: "Noisy Hindi spelling, still matched by our phonetic normalisation."
5. **Evaluation** tab: "Coverage 39%, but when we answer, we are right."
6. Optional: open `annotate.html`: "This is the tool our annotators used to build the gold data."

## 4. Related work (slide 4, with references for the report)

| Area | Work | How we relate |
|---|---|---|
| Speech recognition | Radford et al., *Robust Speech Recognition via Large-Scale Weak Supervision* (Whisper), ICML 2023 | Our ASR + translation front end |
| ASR hallucination | Koenecke et al., *Careless Whisper: Speech-to-Text Hallucination Harms*, ACM FAccT 2024 | We measured the same failure (71% of one recording) and filter it |
| Negation / assertion | Chapman et al., *NegEx*, J. Biomed. Inform. 2001; Harkema et al., *ConText*, J. Biomed. Inform. 2009 | Our clause-scoped assertion rules are ConText-style |
| Assertion classes | Uzuner et al., *2010 i2b2/VA challenge on concepts, assertions, and relations*, JAMIA 2011 | Source of the present / absent / possible distinction |
| Clinical concept mapping | Aronson, *MetaMap*, AMIA 2001; Savova et al., *cTAKES*, JAMIA 2010; Bodenreider, *UMLS*, NAR 2004 | Our SNOMED-CT/UMLS lookup is a small local version |
| Cross-lingual NER | Yarowsky et al., *Inducing multilingual text analysis tools via robust projection*, HLT 2001; Mayhew et al., *Cheap Translation for Cross-Lingual NER*, EMNLP 2017 | Annotation projection: the idea behind our alignment |
| Zero-shot NER | Zaratiana et al., *GLiNER*, NAACL 2024 | Our neural baseline |
| Indian-language models | Khanuja et al., *MuRIL*, 2021 | Future work: native Hindi NER |
| Conversation → clinical note | Yim et al., *ACI-BENCH*, Scientific Data 2023 | The same task family (ambient clinical documentation) |
| Agreement / metrics | Hripcsak & Rothschild, JAMIA 2005 (agreement F-measure); Landis & Koch 1977 (kappa); Popović, *chrF*, WMT 2015 | Our evaluation methods |

## 5. Limitations and future work (say these yourselves)

1. **Tiny, imbalanced data:** 4 matched cases, 54 of 56 references are "no", so no positive-symptom recall can be estimated. *Fix:* more recordings, including positive cases.
2. **Upstream errors dominate:** 74% of misses come from ASR and translation. *Fix:* a better Hindi ASR (e.g. a larger Whisper, or an Indic ASR model), hallucination-aware decoding (VAD, chunking), and a separate MT system instead of Whisper's translate mode.
3. **Rule-based NER:** high precision, limited recall. *Fix:* fine-tune MuRIL/IndicBERT, or use GLiNER, once there is gold data.
4. **Alignment is partial:** about 28% of clinical entities reach word level. *Fix:* a larger lexicon, or neural word alignment (e.g. SimAlign/awesome-align) on a proper MT output.
5. **No speaker diarization:** doctor vs patient is inferred from question marks.

## 6. Likely viva questions and answers

**Q: Why rules instead of a neural model?**
A: Five recordings is far too little to train or fine-tune. Rules are transparent, and every prediction can be traced, which matters clinically. We quantified the cost (coverage 39%) and compared against a zero-shot neural model, GLiNER.

**Q: Your accuracy is 39%. Isn't that bad?**
A: 39% is coverage. When the system answers, it is 22 out of 22 correct. The error analysis shows the misses come mostly from speech recognition and translation, not from the NLP. We also show why accuracy alone misleads here: "always no" gets 96%.

**Q: Then why not just default to "no"? It scores higher.**
A: Because it has 0% recall on positive cases. It would tell a patient with a lump that they have no lump. On this data the guess happens to be right because almost every reference answer is "no". The data can't distinguish careful extraction from guessing, which is exactly why we report coverage and recall separately.

**Q: How does your alignment work, and why not just translate?**
A: Translating loses the link to the source words, which the brief warns against. We have both a Hindi transcript and an English translation from the same audio, with timestamps. We match segments by time, then match words using a Hindi lexicon with phonetic normalisation, because ASR spells "cancer" five different ways. Phonetic matching aligns 23.3% of entities, against 14.8% with exact matching.

**Q: What is UNKNOWN, and why not just ABSENT?**
A: UNKNOWN means "not established": not asked, or not understood. ABSENT means the patient denied it. Merging them invents negative findings, which is unsafe.

**Q: How do you know your gold annotations are reliable?**
A: Two annotators labelled independently, we measured agreement (pairwise F1 and Cohen's κ), and disagreements were adjudicated. *(Quote your numbers.)*

**Q: Did you tune on the test set?**
A: The early keyword fixes were made by looking at these same recordings, so the 33.9% → 39.3% improvement is not a held-out result. We state that. With 5 recordings there is no separate test split; more data is the first item of future work.

**Q: What would you do with one more month?**
A: Collect more recordings with positive cases, try a stronger Hindi ASR, then fine-tune a multilingual NER model on the gold annotations we now have tooling for.

## 7. Delivery tips

- Open with the example, not the architecture: "A patient says *'Nahi… ek rishtedaar ko hua tha'*. What should the form say?"
- Show numbers *with* their denominators (22/22, not "100%").
- Point out your own limitations first. Examiners reward this.
- Finish on time. Leave the last minute for "three takeaways".
