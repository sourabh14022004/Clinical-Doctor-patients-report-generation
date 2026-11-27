# ASR and translation quality

## 1. Whisper hallucination (no reference needed)

A hallucinated segment is a repetition loop (the same phrase over and over), a known Whisper failure on long or quiet audio.

| Case | Hindi segments | Hallucinated | Share of Hindi audio time | English segments in repetition loops |
|---|---:|---:|---:|---:|
| Kajal | 65 | 0 | 0.0% | 40/95 (42.1%) |
| Praveen | 56 | 0 | 0.0% | 28/74 (37.8%) |
| Priyanshi | 29 | 1 | 14.9% | 0/70 (0.0%) |
| Swarnima | 80 | 0 | 0.0% | 14/70 (20.0%) |
| Uday | 31 | 27 | 71.3% | 42/85 (49.4%) |

## 2. Against human reference transcripts

No reference transcripts yet. Add files to `outputs/asr_reference/` (see the docstring of this script).
