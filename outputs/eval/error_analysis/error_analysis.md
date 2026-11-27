# Error-propagation analysis

Scope: the 34 scored form fields that the system left UNKNOWN although the reference record has an answer. Each is attributed to the first pipeline stage that lost it. Reproduce with `python src/error_analysis.py`.

| Stage where the answer was lost | Fields | Share |
|---|---:|---:|
| A. Lost in ASR (absent from Hindi and English) | 20 | 58.8% |
| B. Lost in translation (in Hindi, not in English) | 5 | 14.7% |
| C. Missed by question matching (in English, no question matched) | 9 | 26.5% |
| D. Answer not classified (question matched, answer unclear) | 0 | 0.0% |

## Per case

| Case | A | B | C | D | Total |
|---|---:|---:|---:|---:|---:|
| Praveen | 5 | 2 | 3 | 0 | 10 |
| Priyanshi | 0 | 1 | 1 | 0 | 2 |
| Swarnima | 5 | 1 | 4 | 0 | 10 |
| Uday | 10 | 1 | 1 | 0 | 12 |

## Field detail

| Case | Field | Reference | Topic in Hindi | Topic in English | Stage |
|---|---|---|---|---|---|
| Praveen | Past tobacco or alcohol use | ABSENT | yes | yes | C |
| Praveen | Current tobacco use | ABSENT | no | yes | C |
| Praveen | Non-healing ulcer or wound | ABSENT | no | no | A |
| Praveen | Lump or swelling | ABSENT | yes | no | B |
| Praveen | Persistent pain | ABSENT | yes | no | B |
| Praveen | Bleeding from any site | ABSENT | no | no | A |
| Praveen | Difficulty opening mouth | ABSENT | no | no | A |
| Praveen | White or red oral patch | ABSENT | yes | yes | C |
| Praveen | Oral ulcer over two weeks | ABSENT | no | no | A |
| Praveen | Difficulty chewing or swallowing | ABSENT | no | no | A |
| Priyanshi | Current tobacco use | ABSENT | yes | yes | C |
| Priyanshi | Difficulty chewing or swallowing | ABSENT | yes | no | B |
| Swarnima | Current tobacco use | ABSENT | no | yes | C |
| Swarnima | Non-healing ulcer or wound | ABSENT | no | yes | C |
| Swarnima | Lump or swelling | ABSENT | no | no | A |
| Swarnima | Persistent pain | ABSENT | yes | no | B |
| Swarnima | Bleeding from any site | ABSENT | no | no | A |
| Swarnima | Known chronic illness | ABSENT | yes | yes | C |
| Swarnima | Difficulty opening mouth | ABSENT | no | no | A |
| Swarnima | White or red oral patch | ABSENT | no | yes | C |
| Swarnima | Oral ulcer over two weeks | ABSENT | no | no | A |
| Swarnima | Difficulty chewing or swallowing | ABSENT | no | no | A |
| Uday | Past tobacco or alcohol use | ABSENT | no | yes | C |
| Uday | Current tobacco use | ABSENT | no | no | A |
| Uday | Unexplained weight loss | ABSENT | yes | no | B |
| Uday | Persistent fever or fatigue | ABSENT | no | no | A |
| Uday | Non-healing ulcer or wound | ABSENT | no | no | A |
| Uday | Lump or swelling | ABSENT | no | no | A |
| Uday | Persistent pain | ABSENT | no | no | A |
| Uday | Bleeding from any site | ABSENT | no | no | A |
| Uday | Difficulty opening mouth | ABSENT | no | no | A |
| Uday | White or red oral patch | ABSENT | no | no | A |
| Uday | Oral ulcer over two weeks | ABSENT | no | no | A |
| Uday | Difficulty chewing or swallowing | ABSENT | no | no | A |

Topic detection uses keyword lists (English) and phonetic matching (Hindi); it indicates where information disappeared, not a precise measurement. Hallucinated Hindi segments are excluded.
