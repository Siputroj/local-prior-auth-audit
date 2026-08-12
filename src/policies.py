"""
Synthetic Coverage Policies for Prior Authorization Audit.

Three SNOMED CT-aligned coverage policies used to evaluate
prior authorization claims against patient medical records.
"""


POLICIES = {
    "CP-101": {
        "id": "CP-101",
        "title": "Oncology Diagnostic and Treatment Procedure Policy",
        "domain": "Oncology",
        "effective_date": "2022-01-01",
        "version": "1.0",
        "description": (
            "This policy governs prior authorization requirements for oncology-related "
            "diagnostic procedures, surgical interventions, and chemotherapy/radiation "
            "treatment regimens. All requests must demonstrate confirmed malignancy and "
            "clinical necessity supported by pathology and imaging findings."
        ),
        "covered_procedures": [
            "Mammography (procedure) (SNOMED: 71651007)",
            "Colonoscopy (SNOMED: 73761001)",
            "Biopsy of colon (SNOMED: 76164006)",
            "Partial resection of colon (SNOMED: 43075005)",
            "Combined chemotherapy and radiation therapy (SNOMED: 703423002)",
            "Bone density scan (procedure) (SNOMED: 312681000)",
            "1 ML DOCEtaxel 20 MG/ML Injection (RxNorm: 1732186)",
            "0.25 ML Leuprolide Acetate 30 MG/ML Prefilled Syringe (RxNorm: 1946519)",
            "Leucovorin 100 MG Injection (RxNorm: 1803932)",
            "10 ML oxaliplatin 5 MG/ML Injection (RxNorm: 1736776)",
        ],
        "mandatory_criteria": [
            {
                "id": "CP-101-C1",
                "description": "Patient must have a confirmed malignant neoplasm diagnosis with an active clinical status.",
                "required_snomed_codes": ["254837009", "109838007", "126906006", "92691004", "93761005", "363406005"],
                "required_snomed_labels": [
                    "Malignant neoplasm of breast (SNOMED: 254837009)",
                    "Overlapping malignant neoplasm of colon (SNOMED: 109838007)",
                    "Neoplasm of prostate (SNOMED: 126906006)",
                    "Carcinoma in situ of prostate (SNOMED: 92691004)",
                ],
            },
            {
                "id": "CP-101-C2",
                "description": "Patient must have documented diagnostic imaging or biopsy confirming the malignancy on record.",
                "required_procedures": ["71651007", "73761001", "76164006", "312681000"],
                "required_procedure_labels": [
                    "Mammography (SNOMED: 71651007)",
                    "Colonoscopy (SNOMED: 73761001)",
                    "Biopsy of colon (SNOMED: 76164006)",
                    "Bone density scan (SNOMED: 312681000)",
                ],
            },
            {
                "id": "CP-101-C3",
                "description": "Patient must be 18 years or older.",
                "min_age": 18,
            },
        ],
        "policy_text": (
            "COVERAGE POLICY CP-101: ONCOLOGY DIAGNOSTIC AND TREATMENT PROCEDURES\n\n"
            "Section 1 - Eligibility Requirements:\n"
            "Prior authorization is required for all oncology diagnostic procedures, surgical "
            "interventions, and chemotherapy/radiation treatment regimens.\n\n"
            "Section 2 - Mandatory Clinical Criteria:\n"
            "2.1 The patient MUST have a confirmed active malignant neoplasm diagnosis documented "
            "in their medical record. Acceptable diagnoses include (non-exhaustive): Malignant "
            "neoplasm of breast (SNOMED: 254837009), Overlapping malignant neoplasm of colon "
            "(SNOMED: 109838007), Neoplasm of prostate (SNOMED: 126906006), or Carcinoma in situ "
            "of prostate (SNOMED: 92691004). Any confirmed active malignant neoplasm satisfies "
            "this criterion.\n\n"
            "2.2 The patient MUST have documented pathologic or radiologic evidence supporting the "
            "malignancy. Examples of acceptable evidence include, but are NOT limited to: "
            "Mammography (SNOMED: 71651007), Colonoscopy (SNOMED: 73761001), Biopsy of colon "
            "(SNOMED: 76164006), or Bone density scan (SNOMED: 312681000). Any diagnostic imaging, "
            "biopsy, pathologic report, or surgical resection relevant to the malignancy's organ "
            "system satisfies this criterion. In addition, an ACTIVE oncology treatment regimen "
            "already documented in the patient record (e.g., active chemotherapy, hormone therapy, "
            "or radiation with a matching diagnosis) is itself sufficient proof of a prior "
            "confirmed workup and SATISFIES 2.2 for continuation-of-therapy requests.\n\n"
            "2.3 The patient MUST be at least 18 years of age (age 18 or older; there is no upper "
            "age limit) at the time of the request.\n\n"
            "Section 3 - Decision Tiers & Criteria:\n"
            "3.1 LOW RISK (Approve): Confirmed active malignant neoplasm diagnosis AND documented "
            "diagnostic evidence or active oncology regimen AND age >= 18.\n"
            "3.2 MODERATE RISK (Manual Review Required): Malignancy documented but missing diagnostic "
            "or active regimen evidence; OR chemotherapy/radiation initiation request in a patient with "
            "active severe cardiac comorbidity (e.g. active cardiac arrest, chronic heart failure) "
            "requiring cardiology clearance.\n"
            "3.3 HIGH RISK (Deny): Patient has NO active malignant neoplasm diagnosis, OR age < 18."
        ),
    },

    "CP-202": {
        "id": "CP-202",
        "title": "Neurology Specialty Medication Step Therapy Policy",
        "domain": "Neurology",
        "effective_date": "2022-01-01",
        "version": "1.0",
        "description": (
            "This policy governs prior authorization for brand-name and specialty "
            "antiepileptic drugs (AEDs). Step therapy requires documented trial and failure "
            "of at least two first-line generic AEDs before specialty medications are approved."
        ),
        "step_therapy_first_line_drugs": [
            "Carbamazepine (Tegretol)",
            "Levetiracetam (Keppra)",
            "Lamotrigine (Lamictal)",
            "Valproic Acid (Depakene)",
            "Phenytoin (Dilantin)",
            "Topiramate (Topamax)",
        ],
        "mandatory_criteria": [
            {
                "id": "CP-202-C1",
                "description": "Patient must have an active epilepsy or seizure disorder diagnosis.",
                "required_snomed_codes": ["84757009", "128613002", "230265002"],
                "required_snomed_labels": [
                    "Epilepsy (SNOMED: 84757009)",
                    "Seizure disorder (SNOMED: 128613002)",
                    "Familial epilepsy (SNOMED: 230265002)",
                ],
            },
            {
                "id": "CP-202-C2",
                "description": (
                    "Patient must have documented trial of at least 2 first-line generic "
                    "antiepileptic drugs (AEDs) for a minimum of 90 days each. First-line AEDs "
                    "include: Carbamazepine, Levetiracetam, Lamotrigine, Valproic Acid, "
                    "Phenytoin, or Topiramate."
                ),
                "min_drug_trials": 2,
                "min_trial_duration_days": 90,
            },
            {
                "id": "CP-202-C3",
                "description": "Patient must have documented treatment failure or intolerance to the first-line AEDs.",
            },
        ],
        "policy_text": (
            "COVERAGE POLICY CP-202: NEUROLOGY SPECIALTY MEDICATION STEP THERAPY\n\n"
            "Section 1 - Eligibility Requirements:\n"
            "Prior authorization is required for all brand-name and specialty antiepileptic "
            "drugs (AEDs). Step therapy must be completed before specialty AEDs are approved.\n\n"
            "Section 2 - Mandatory Clinical Criteria:\n"
            "2.1 The patient MUST have an active epilepsy or seizure disorder diagnosis documented "
            "in their medical record. Acceptable diagnoses include: Epilepsy (SNOMED: 84757009), "
            "Seizure disorder (SNOMED: 128613002), or Familial epilepsy (SNOMED: 230265002).\n\n"
            "2.2 The patient MUST have documented trial of at least 2 first-line generic "
            "antiepileptic drugs (AEDs) for a minimum of 90 days each for full Low Risk approval. "
            "First-line AEDs include: Carbamazepine (Tegretol), Levetiracetam (Keppra), "
            "Lamotrigine (Lamictal), Valproic Acid (Depakene), Phenytoin (Dilantin), or Topiramate (Topamax).\n\n"
            "2.3 The patient MUST have documented treatment failure or intolerance to the "
            "first-line AEDs before specialty medications will be considered.\n\n"
            "Section 3 - Decision Tiers & Criteria:\n"
            "3.1 LOW RISK (Approve): Patient has active epilepsy diagnosis AND at least 2 first-line generic AED trials documented.\n"
            "3.2 MODERATE RISK (Manual Review Required): Patient has active epilepsy diagnosis AND documented trial of EXACTLY 1 first-line generic AED (or incomplete trial duration documentation).\n"
            "3.3 HIGH RISK (Deny): Patient has NO active epilepsy diagnosis, OR has 0 first-line generic AED trials documented."
        ),
    },

    "CP-303": {
        "id": "CP-303",
        "title": "Orthopedic Surgery and Joint Replacement Policy",
        "domain": "Orthopedics",
        "effective_date": "2022-01-01",
        "version": "1.0",
        "description": (
            "This policy governs prior authorization for elective total joint replacements."
        ),
        "covered_procedures": [
            "Total knee replacement (procedure) (SNOMED: 609588000)",
            "Total hip replacement (procedure) (SNOMED: 52734007)",
        ],
        "mandatory_criteria": [
            {
                "id": "CP-303-C1",
                "description": "Patient must have a confirmed active osteoarthritis diagnosis of the affected joint.",
                "required_snomed_codes": ["239873007", "239872002", "396275006"],
                "required_snomed_labels": [
                    "Osteoarthritis of knee (SNOMED: 239873007)",
                    "Osteoarthritis of hip (SNOMED: 239872002)",
                    "Osteoarthritis (SNOMED: 396275006)",
                ],
            },
            {
                "id": "CP-303-C2",
                "description": (
                    "Patient must have documented trial of conservative therapy for a minimum "
                    "of 6 weeks. Conservative therapy includes: physical therapy, NSAIDs "
                    "(e.g. Naproxen, Ibuprofen), or corticosteroid injections."
                ),
                "conservative_therapy_keywords": [
                    "physical therapy", "physiotherapy",
                    "Naproxen", "Ibuprofen", "NSAID",
                    "corticosteroid injection", "cortisone",
                ],
                "min_therapy_duration_weeks": 6,
            },
            {
                "id": "CP-303-C3",
                "description": "Patient BMI must be below 40 for elective joint replacement surgery.",
                "max_bmi": 40,
            },
        ],
        "policy_text": (
            "COVERAGE POLICY CP-303: ORTHOPEDIC SURGERY AND JOINT REPLACEMENT\n\n"
            "Section 1 - Eligibility Requirements:\n"
            "Prior authorization is required for all elective total knee arthroplasty (TKA), "
            "total hip arthroplasty (THA), and other major joint replacement procedures.\n\n"
            "Section 2 - Mandatory Clinical Criteria:\n"
            "2.1 The patient MUST have a confirmed active osteoarthritis diagnosis of the "
            "affected joint. Acceptable diagnoses include: Osteoarthritis of knee "
            "(SNOMED: 239873007), Osteoarthritis of hip (SNOMED: 239872002), or Osteoarthritis "
            "(SNOMED: 396275006).\n\n"
            "2.2 The patient MUST have documented trial of conservative therapy for a minimum "
            "of 6 weeks prior to the surgery request. Conservative therapy includes: physical "
            "therapy, NSAIDs (e.g. Naproxen sodium 220 MG Oral Tablet, Ibuprofen 200 MG Oral "
            "Tablet), or corticosteroid injections.\n\n"
            "2.3 The patient's BMI MUST be below 40 for elective joint replacement surgery. "
            "Patients with BMI >= 40 must complete a supervised weight management program first.\n\n"
            "Section 3 - Decision Tiers & Criteria:\n"
            "3.1 LOW RISK (Approve): Active osteoarthritis diagnosis AND conservative therapy documented AND BMI < 40.\n"
            "3.2 MODERATE RISK (Manual Review Required): Osteoarthritis documented but no conservative therapy trial found; OR active severe cardiac comorbidity (e.g. chronic heart failure) requiring surgical clearance.\n"
            "3.3 HIGH RISK (Deny): Patient has NO active osteoarthritis diagnosis, OR patient BMI is >= 40 without weight management program."
        ),
    },
}


def get_policy(policy_id):
    """Get a coverage policy by its ID."""
    return POLICIES.get(policy_id)


def get_policy_text(policy_id):
    """Get the full text of a coverage policy for LLM context."""
    policy = get_policy(policy_id)
    if policy:
        return policy["policy_text"]
    return None


def get_all_policies():
    """Get all coverage policies."""
    return POLICIES


def list_policy_ids():
    """List all available policy IDs."""
    return list(POLICIES.keys())
