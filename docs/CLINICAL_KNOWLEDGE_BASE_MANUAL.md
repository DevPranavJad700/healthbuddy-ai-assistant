# HealthBuddy AI — Clinical Knowledge Base Manual & Clinical Guidelines Reference

> **Document Type:** Clinical Architecture & Medical Reference Manual  
> **Status:** Authoritative / Living Reference  
> **Target Audience:** Clinicians, Medical Informaticians, Software Engineers, AI Prompt Architects, Health System Integrators  
> **Version:** 2.4.0  

---

## Executive Clinical Summary

HealthBuddy AI integrates Retrieval-Augmented Generation (RAG) over a curated, peer-reviewed clinical knowledge corpus spanning over 30 core medical disciplines. Every piece of advice generated is grounded in authoritative clinical practice guidelines from accredited medical societies (AHA, ACC, ADA, KDIGO, GOLD, GINA, USPSTF, AAO, ASH, APA).

This manual documents the clinical evidence base, diagnostic criteria, emergency escalation protocols, and clinical governance principles underlying HealthBuddy AI.

---

## 1. Directory of Indexed Clinical Specializations

HealthBuddy AI's knowledge base covers 32 distinct medical domains, each structured with pathophysiology, evidence-based diagnostic criteria, guideline-directed medical therapy (GDMT), and red-flag emergency escalation rules:

| Domain | Primary Clinical Guidelines | Key Focus Areas & Pathologies |
| :--- | :--- | :--- |
| **Cardiovascular Health** | AHA / ACC / ESC | Essential hypertension, Heart failure (HFrEF/HFpEF), ACS / NSTEMI / STEMI, Atrial fibrillation, CHA2DS2-VASc |
| **Endocrinology & Metabolism** | ADA Standards of Care / ATA | Type 1 & 2 Diabetes, Diabetic Ketoacidosis (DKA), Hypothyroidism (Hashimoto's), Hyperthyroidism (Graves'), Adrenal insufficiency, PCOS |
| **Pulmonology & Respiratory** | GOLD 2024 / GINA 2023 | Asthma Action Plans, COPD staging (FEV1/FVC), Acute bronchitis, Pneumonia CURB-65, Pulmonary embolism |
| **Nephrology & Renal Medicine** | KDIGO 2021 / KDOQI / ASN | CKD Stages 1–5, Albuminuria (UACR), Diabetic nephropathy, Nephrolithiasis, Acute Kidney Injury (KDIGO criteria), Hyperkalemia |
| **Neurology & Headache Medicine** | ICHD-3 / AAN / AHA Stroke | Migraine with/without aura, Tension headache, Cluster headache, SNOOP4 red flags, Acute ischemic stroke (BE-FAST, tPA window), Concussion |
| **Gastroenterology & Hepatology** | ACG / AGA | GERD, Peptic ulcer disease (H. pylori eradication), Irritable Bowel Syndrome (Rome IV), Cirrhosis (MELD, Child-Pugh), Acute pancreatitis |
| **Hematology & Coagulation** | ASH / CHEST 2021 / WHO | Microcytic/Macrocytic/Normocytic anemia workup, Ferritin thresholds, DVT/PE Wells scores, DOAC vs Warfarin, Thrombocytopenia (ITP/TTP) |
| **Ophthalmology & Vision** | AAO Preferred Practice Patterns | Acute Angle-Closure Glaucoma, Retinal detachment, Diabetic retinopathy (NPDR/PDR), Age-related macular degeneration (AREDS2), Red eye differential |
| **Musculoskeletal & Orthopedics** | ACR / EULAR / AAOS | Osteoarthritis vs Rheumatoid arthritis, Acute low back pain, Sciatica, Cauda Equina red flags, PEACE & LOVE soft tissue injury protocol |
| **Geriatrics & Palliative Care** | AGS Beers Criteria 2023 | Sarcopenia, Osteoporosis (DEXA T-score), Fall risk assessment, Cognitive decline vs Dementia, Deprescribing anticholinergics |
| **Pediatric Medicine** | AAP / Bright Futures | Pediatric fever triage, Bronchiolitis, Croup (Westley score), Dehydration assessment (Gorelick score), Developmental milestones |
| **Allergy & Clinical Immunology** | WAO / AAAAI / ACAAI | Anaphylaxis diagnostic criteria, Intramuscular Epinephrine auto-injectors, Allergic rhinitis stepped therapy, Drug allergy delabeling |
| **Infectious Diseases & Sepsis** | IDSA / Surviving Sepsis Campaign | Sepsis-3 (qSOFA / SOFA), Upper respiratory viral differentiation, Cystitis vs Pyelonephritis, Adult immunization (CDC ACIP) |
| **Preventive Medicine & Oncology** | USPSTF 2023 / ACS | Colorectal, Breast, Cervical, Lung, Prostate cancer screenings, 10-year ASCVD risk stratification, Annual metabolic panel interpretation |
| **Mental Health & Psychiatry** | DSM-5-TR / APA / CANMAT | Major Depressive Disorder (PHQ-9), Generalized Anxiety Disorder (GAD-7), Panic disorder, Bipolar disorder screening, Crisis escalation |
| **Sleep Medicine** | AASM / ESRS | Obstructive sleep apnea (STOP-BANG score), Chronic insomnia disorder (CBT-I), Circadian rhythm sleep-wake disorders |
| **Dermatology** | AAD | ABCDE melanoma screening, Atopic dermatitis, Psoriasis, Acne vulgaris algorithmic management, Urticaria |
| **Women's Health & Obstetrics** | ACOG | Prenatal nutrition (folic acid), Gestational diabetes, Preeclampsia red flags, Menopause hormonal/non-hormonal management |

---

## 2. Emergency Escalation Protocols (SNOOP4, qSOFA, BE-FAST, Red Flags)

HealthBuddy AI enforces an automated emergency safety tier. When high-acuity trigger keywords or clinical profiles are detected, the system immediately prioritizes life-saving triage instructions and directs the patient to call local emergency services (911/112/999/108) or seek immediate emergency department care.

### A. Neurologic Emergencies
- **BE-FAST Stroke Protocol**:
  - **B**alance: Sudden loss of balance or coordination.
  - **E**yes: Sudden blurred, double, or lost vision in one or both eyes.
  - **F**ace: Unilateral facial droop, uneven smile.
  - **A**rms: Unilateral arm or leg weakness or drifting.
  - **S**peech: Slurred speech, inability to repeat simple phrases, word-finding difficulty.
  - **T**ime: Call emergency services immediately. Note exact time last known normal (critical for 4.5-hour IV thrombolysis and 24-hour endovascular thrombectomy windows).
- **SNOOP4 Headache Red Flags**:
  - **S**ystemic symptoms (fever, weight loss, night sweats) or secondary risk factors (HIV, active cancer).
  - **N**eurologic signs or symptoms (confusion, altered sensorium, focal motor weakness).
  - **O**nset: Sudden "thunderclap" headache reaching maximum intensity within 60 seconds (suggestive of Subarachnoid Hemorrhage).
  - **O**lder age: New or worsening headache onset after age 50 (Giant Cell / Temporal Arteritis).
  - **P**rogression / Positional / Papilledema: Headache worsening with posture, coughing, or Valsalva maneuver.

### B. Cardiovascular Emergencies
- **Acute Coronary Syndrome (ACS)**:
  - Crushing substernal chest pressure, tightness, or pain radiating to left shoulder, arm, neck, or jaw.
  - Accompanied by diaphoresis, shortness of breath, nausea, or lightheadedness.
  - Atypical presentations in women, elderly, and diabetics: Unexplained dyspnea, nausea, fatigue, or epigastric discomfort without overt chest pain.
- **Acute Decompensated Heart Failure**:
  - Paroxysmal nocturnal dyspnea, orthopnea requiring multiple pillows, sudden weight gain (> 3 lbs in 24 hours), bilateral pitting pretibial edema.

### C. Respiratory & Anaphylactic Emergencies
- **Anaphylaxis Two-System Rule**:
  - Acute onset of skin/mucosal symptoms (generalized hives, pruritus, swollen lips/tongue/uvula) PLUS at least one of:
    1. Respiratory compromise (stridor, wheezing, dyspnea, hypoxemia).
    2. Hemodynamic compromise (systolic BP < 90 mmHg, collapse, syncope).
  - Action: Immediate Intramuscular (IM) Epinephrine 0.3 mg (adult) into the anterolateral mid-thigh. Never delay epinephrine for antihistamines.
- **Severe Respiratory Distress**:
  - Inability to speak in full sentences, cyanosis (blue lips/fingernails), accessory muscle use, silent chest in severe asthma attack.

### D. Sepsis Screening (qSOFA)
- Any 2 of the following 3 criteria in the setting of suspected infection indicate high risk of in-hospital mortality and urgent ICU escalation:
  1. Respiratory rate >= 22 breaths per minute.
  2. Altered mentation (Glasgow Coma Scale < 15).
  3. Systolic blood pressure <= 100 mmHg.

### E. Spinal Cord Compression (Cauda Equina Syndrome)
- Severe low back pain with:
  - Bilateral lower extremity motor weakness or numbness.
  - "Saddle anesthesia" (loss of sensation in the perineal, buttock, and groin regions).
  - Acute urinary retention, overflow incontinence, or fecal incontinence.
  - Mandates emergent MRI within 6 hours and decompressive laminectomy.

---

## 3. Evidence-Based Chronic Disease Management

### Type 2 Diabetes Mellitus
- **Glycemic Targets**:
  - Non-pregnant adults: HbA1c < 7.0% (53 mmol/mol).
  - Stringent target (< 6.5%): Young patients, short disease duration, no significant CVD, low hypoglycemia risk.
  - Relaxed target (< 8.0%): Elderly, history of severe hypoglycemia, limited life expectancy, extensive vascular comorbidities.
- **Fasting & Postprandial Blood Glucose Targets**:
  - Fasting / Preprandial: 80–130 mg/dL (4.4–7.2 mmol/L).
  - 2-Hour Postprandial: < 180 mg/dL (< 10.0 mmol/L).
- **Cardiorenal Protection**:
  - SGLT2 inhibitors (Empagliflozin, Dapagliflozin) or GLP-1 receptor agonists (Semaglutide, Dulaglutide) with proven ASCVD and CKD benefit should be initiated independent of baseline HbA1c in patients with established ASCVD, heart failure, or CKD.

### Hypertension (AHA/ACC 2017 Categories)
- **Normal**: SBP < 120 and DBP < 80 mmHg.
- **Elevated**: SBP 120–129 and DBP < 80 mmHg.
- **Stage 1 Hypertension**: SBP 130–139 or DBP 80–89 mmHg.
- **Stage 2 Hypertension**: SBP >= 140 or DBP >= 90 mmHg.
- **Hypertensive Crisis**: SBP > 180 and/or DBP > 120 mmHg. (Assess for acute end-organ damage: encephalopathy, pulmonary edema, acute MI, stroke, aortic dissection).
- **Target Blood Pressure**: < 130/80 mmHg for all adult patients with confirmed hypertension.

---

## 4. Medication Safety & Drug Interaction Rules

HealthBuddy AI's clinical engine incorporates safety guardrails for common high-risk pharmacotherapies:

1. **Levothyroxine (Synthroid) Administration**:
   - Must be taken in the morning on an empty stomach with a full glass of water, 30 to 60 minutes before breakfast or coffee.
   - Calcium carbonate, iron supplements, antacids, and PPIs bind levothyroxine in the gut; separate by at least 4 hours.
2. **Anticoagulants & Antiplatelets (DOACs / Warfarin / Aspirin)**:
   - High caution with concurrent NSAID use (Ibuprofen, Naproxen), which multiplies upper gastrointestinal bleeding risk by 4-fold.
   - Acetaminophen (Paracetamol) is the preferred mild analgesic for patients on anticoagulants.
3. **Statins (HMG-CoA Reductase Inhibitors)**:
   - Grapefruit juice inhibits CYP3A4, increasing serum concentrations of Simvastatin and Atorvastatin (elevating rhabdomyolysis risk).
   - Rosuvastatin and Pravastatin are not metabolized via CYP3A4 and are safer alternatives for patients consuming citrus juices.
4. **ACE Inhibitors & Potassium Spreading**:
   - Monitor for dry persistent cough (bradykinin accumulation, occurring in 10-15% of patients; switch to ARB).
   - Avoid salt substitutes containing potassium chloride due to synergistic hyperkalemia risk.

---

## 5. Clinical Governance & Content Verification

- **Review Cycle**: All clinical documents are scheduled for semiannual re-validation or immediate updating upon release of major society guidelines (e.g., ADA January updates, GOLD November updates).
- **Citation Integrity**: Every clinical recommendation generated by HealthBuddy AI includes direct citations to indexed document source chunks with semantic similarity and reranker confidence scores.
- **Hallucination Prevention**: Strict temperature parameters (T = 0.2) and prompt guardrails prevent speculative medical advice. When symptoms or questions fall outside the indexed evidence corpus, HealthBuddy explicitly advises consultation with a licensed healthcare provider.
