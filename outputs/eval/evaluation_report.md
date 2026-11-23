# LEGACY Field-Agreement Report (Not Clinical Accuracy)
## Historical binary comparison against structured reference forms

> **Warning:** This legacy comparator does not correctly model PRESENT / ABSENT / POSSIBLE / UNKNOWN. Unknown values may be counted as negative in binary checks. Do not interpret or present this score as clinical accuracy, diagnostic performance or model quality.

**Legacy Field Agreement:** **47.2%**  
**Total Ground-Truth Fields Evaluated:** **72**  
**Total Accurately Populated Fields:** **34**

---

### Patient-Level Accuracy Summary
| Patient | Fields Evaluated | Correctly Matched | Accuracy (%) |
|---|---|---|---|
| **Praveen** | 18 | 8 | **44.4%** |
| **Priyanshi** | 18 | 15 | **83.3%** |
| **Swarnima** | 18 | 7 | **38.9%** |
| **Uday** | 18 | 4 | **22.2%** |

---

### Detailed Field-Level Breakdown

#### Patient: Praveen
| Clinical Field | Ground Truth Form | Speech-Extracted Record | Concordance |
|---|---|---|---|
| Age | `30` | `30` | ✅ MATCH |
| Sex | `Male` | `None` | ⚠️ DISCREPANCY |
| Marital Status | `Unmarried` | `Unmarried` | ✅ MATCH |
| Insurance | `No` | `No` | ✅ MATCH |
| Weight (kg) | `58.0` | `58.0` | ✅ MATCH |
| Family History of Cancer | `Yes (Mother - Breast Cancer)` | `YES` | ✅ MATCH |
| Current Tobacco Use | `NO` | `NO` | ⚠️ DISCREPANCY |
| General Symptom: Unexplained Weight Loss | `NO` | `NO` | ✅ MATCH |
| General Symptom: Persistent Fever / Fatigue | `NO` | `NO` | ✅ MATCH |
| General Symptom: Non-healing Ulcer / Wound | `NO` | `NO` | ⚠️ DISCREPANCY |
| General Symptom: Lump / Swelling in Body | `NO` | `NO` | ⚠️ DISCREPANCY |
| General Symptom: Persistent Pain | `NO` | `NO` | ⚠️ DISCREPANCY |
| General Symptom: Bleeding from Any Site | `NO` | `NO` | ⚠️ DISCREPANCY |
| General Symptom: Known Chronic Illness | `NO` | `NO` | ✅ MATCH |
| Oral: Difficulty Opening Mouth | `NO` | `NO` | ⚠️ DISCREPANCY |
| Oral: White / Red Patch | `NO` | `NO` | ⚠️ DISCREPANCY |
| Oral: Ulcer > 2 Weeks | `NO` | `NO` | ⚠️ DISCREPANCY |
| Oral: Chewing / Swallowing Difficulty | `NO` | `NO` | ⚠️ DISCREPANCY |

#### Patient: Priyanshi
| Clinical Field | Ground Truth Form | Speech-Extracted Record | Concordance |
|---|---|---|---|
| Age | `26` | `26` | ✅ MATCH |
| Sex | `Female` | `None` | ⚠️ DISCREPANCY |
| Marital Status | `Unmarried` | `Unmarried` | ✅ MATCH |
| Insurance | `No` | `No` | ✅ MATCH |
| Weight (kg) | `70.0` | `70.0` | ✅ MATCH |
| Family History of Cancer | `Yes (Breast Cancer)` | `YES` | ✅ MATCH |
| Current Tobacco Use | `NO` | `NO` | ⚠️ DISCREPANCY |
| General Symptom: Unexplained Weight Loss | `NO` | `NO` | ✅ MATCH |
| General Symptom: Persistent Fever / Fatigue | `NO` | `NO` | ✅ MATCH |
| General Symptom: Non-healing Ulcer / Wound | `NO` | `NO` | ✅ MATCH |
| General Symptom: Lump / Swelling in Body | `NO` | `NO` | ✅ MATCH |
| General Symptom: Persistent Pain | `NO` | `NO` | ✅ MATCH |
| General Symptom: Bleeding from Any Site | `NO` | `NO` | ✅ MATCH |
| General Symptom: Known Chronic Illness | `NO` | `NO` | ✅ MATCH |
| Oral: Difficulty Opening Mouth | `NO` | `NO` | ✅ MATCH |
| Oral: White / Red Patch | `NO` | `NO` | ✅ MATCH |
| Oral: Ulcer > 2 Weeks | `NO` | `NO` | ✅ MATCH |
| Oral: Chewing / Swallowing Difficulty | `NO` | `NO` | ⚠️ DISCREPANCY |

#### Patient: Swarnima
| Clinical Field | Ground Truth Form | Speech-Extracted Record | Concordance |
|---|---|---|---|
| Age | `30` | `30` | ✅ MATCH |
| Sex | `Female` | `None` | ⚠️ DISCREPANCY |
| Marital Status | `Married` | `Married` | ✅ MATCH |
| Insurance | `No` | `No` | ✅ MATCH |
| Weight (kg) | `64.0` | `64.0` | ✅ MATCH |
| Family History of Cancer | `No` | `NO` | ✅ MATCH |
| Current Tobacco Use | `NO` | `NO` | ⚠️ DISCREPANCY |
| General Symptom: Unexplained Weight Loss | `NO` | `NO` | ✅ MATCH |
| General Symptom: Persistent Fever / Fatigue | `NO` | `NO` | ✅ MATCH |
| General Symptom: Non-healing Ulcer / Wound | `NO` | `NO` | ⚠️ DISCREPANCY |
| General Symptom: Lump / Swelling in Body | `NO` | `NO` | ⚠️ DISCREPANCY |
| General Symptom: Persistent Pain | `NO` | `NO` | ⚠️ DISCREPANCY |
| General Symptom: Bleeding from Any Site | `NO` | `NO` | ⚠️ DISCREPANCY |
| General Symptom: Known Chronic Illness | `NO` | `NO` | ⚠️ DISCREPANCY |
| Oral: Difficulty Opening Mouth | `NO` | `NO` | ⚠️ DISCREPANCY |
| Oral: White / Red Patch | `NO` | `NO` | ⚠️ DISCREPANCY |
| Oral: Ulcer > 2 Weeks | `NO` | `NO` | ⚠️ DISCREPANCY |
| Oral: Chewing / Swallowing Difficulty | `NO` | `NO` | ⚠️ DISCREPANCY |

#### Patient: Uday
| Clinical Field | Ground Truth Form | Speech-Extracted Record | Concordance |
|---|---|---|---|
| Age | `32` | `32` | ✅ MATCH |
| Sex | `Male` | `None` | ⚠️ DISCREPANCY |
| Marital Status | `Married` | `Married` | ✅ MATCH |
| Insurance | `No` | `None` | ⚠️ DISCREPANCY |
| Weight (kg) | `78.0` | `None` | ⚠️ DISCREPANCY |
| Family History of Cancer | `No (Relative reported at end)` | `NO` | ✅ MATCH |
| Current Tobacco Use | `NO` | `NO` | ⚠️ DISCREPANCY |
| General Symptom: Unexplained Weight Loss | `NO` | `NO` | ⚠️ DISCREPANCY |
| General Symptom: Persistent Fever / Fatigue | `NO` | `NO` | ⚠️ DISCREPANCY |
| General Symptom: Non-healing Ulcer / Wound | `NO` | `NO` | ⚠️ DISCREPANCY |
| General Symptom: Lump / Swelling in Body | `NO` | `NO` | ⚠️ DISCREPANCY |
| General Symptom: Persistent Pain | `NO` | `NO` | ⚠️ DISCREPANCY |
| General Symptom: Bleeding from Any Site | `NO` | `NO` | ⚠️ DISCREPANCY |
| General Symptom: Known Chronic Illness | `NO` | `NO` | ✅ MATCH |
| Oral: Difficulty Opening Mouth | `NO` | `NO` | ⚠️ DISCREPANCY |
| Oral: White / Red Patch | `NO` | `NO` | ⚠️ DISCREPANCY |
| Oral: Ulcer > 2 Weeks | `NO` | `NO` | ⚠️ DISCREPANCY |
| Oral: Chewing / Swallowing Difficulty | `NO` | `NO` | ⚠️ DISCREPANCY |
