# Ablation study

Each row switches one component off (or replaces the system with a trivial baseline) and is scored with the same M4 evaluator on the same matched cases. Reproduce with `python src/ablation.py`.

## 1. Form filling (14 assertion fields x matched cases)

| Configuration | Description | Exact agreement | Coverage | Selective accuracy | PRESENT recall | ABSENT recall |
|---|---|---:|---:|---:|---:|---:|
| Trivial baseline: always ABSENT | No NLP. Predicts 'no' for every field. | 96.4% | 100.0% | 96.4% | 0.0% | 100.0% |
| Trivial baseline: always UNKNOWN | No NLP. Abstains on every field. | 0.0% | 0.0% | N/A | 0.0% | 0.0% |
| Full system | All components on. | 39.3% | 39.3% | 100.0% | 100.0% | 37.0% |
| - question-start cues | Questions detected by '?' only; ASR often drops '?'. | 39.3% | 39.3% | 100.0% | 100.0% | 37.0% |
| + pre-M3 default (UNKNOWN -> ABSENT) | Unanswered fields silently become 'no' (old behaviour). | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

**How to read this.** The reference set has 56 scorable fields and almost all of them are ABSENT. A system that answers 'no' to everything therefore scores very high exact agreement while having **0% PRESENT recall**: it would miss every patient who actually has a symptom or family history. The pre-M3 default (turn every UNKNOWN into ABSENT) reaches 100.0% for the same reason: it guesses 'no' wherever the system found no answer, and on this data the guess happens to be right. **This does not show that guessing is better; it shows that this reference set cannot distinguish careful extraction from guessing.** That is why the project reports coverage, selective accuracy and PRESENT recall separately, and why positive and uncertain cases are needed before any accuracy claim.

Question-start cues had **no measurable effect** on these transcripts (39.3% vs 39.3%): Whisper kept the '?' on these recordings. The cues remain as a safeguard for ASR output without punctuation, which the unit tests cover.

## 2. Assertion detection: question mentions

Clinical entity mentions labelled PRESENT although the clause ends with '?' (i.e. the clinician asked about it; it is not a patient finding).

| Configuration | Clinical entities | PRESENT inside a question (errors) |
|---|---:|---:|
| Full system | 113 | 0 |
| - clause-level question detection | 113 | 16 |

## 3. Hindi <-> English alignment

Share of English entities projected to a specific Hindi word span (not just a time-aligned segment).

| Configuration | All entities aligned to a Hindi span | Clinical entities aligned |
|---|---:|---:|
| Phonetic skeleton matching (full) | 41/176 (23.3%) | 32/113 (28.3%) |
| Exact string matching only | 26/176 (14.8%) | 22/113 (19.5%) |

Hindi ASR spells the same word many ways (कैंसर / कानसर / कंसर / खंसर / खणसर); exact matching misses most of them.
