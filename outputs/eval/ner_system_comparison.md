# NER system comparison

Not yet run: GLiNER zero-shot. See `baselines/gliner_baseline.py` (run on Kaggle/Colab).

## 1. Against human gold annotations

No completed gold annotations yet. Annotate with `web/annotate.html`, then run `python src/annotation_agreement.py` and adjudicate.

## 2. Descriptive comparison (no gold needed)

| Entity type | Rule/lexicon (project) |
|---|---:|
| SIGN_SYMPTOM | 40 |
| DIAGNOSIS | 33 |
| DURATION | 23 |
| CANCER_TYPE | 21 |
| DIETARY_HABIT | 7 |
| FAMILY_MEMBER | 7 |
| MARITAL_STATUS | 6 |
| HEALTH_INSURANCE | 6 |
| RISK_FACTOR_ALCOHOL | 6 |
| RISK_FACTOR_TOBACCO | 6 |
| PATIENT_NAME | 5 |
| AGE | 3 |
| EDUCATION | 3 |
| OCCUPATION | 3 |
| FAMILY_INCOME | 3 |
| WEIGHT | 1 |
| DOB | 1 |
| HEIGHT | 1 |
| ADDRESS | 1 |
