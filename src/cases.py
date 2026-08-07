"""
Demo Case Definitions for Prior Authorization Audit.

Maps 10 curated Synthea patients to coverage policies and claim requests,
with expected risk tier outcomes for benchmarking.
"""
import os


# Base directory for Synthea data
SYNTHEA_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "synthea_data")


DEMO_CASES = [
    # =========================================================================
    # CP-101 ONCOLOGY (4 cases)
    # =========================================================================
    {
        "id": "CASE-001",
        "patient_file": "Claretha922_Kuhlman484_351adae3-d3a7-32ea-c345-568f944a77e7.json",
        "patient_name": "Claretha Kuhlman",
        "policy_id": "CP-101",
        "claim": {
            "procedure": "Mammography (procedure)",
            "snomed_code": "71651007",
            "reason": "Annual diagnostic mammography for ongoing breast neoplasm surveillance",
            "requesting_provider": "Dr. Sarah Mitchell, MD - Oncology",
        },
        "expected_risk_tier": "Low Risk",
        "expected_recommendation": "Approve",
        "rationale": (
            "Patient has confirmed active Malignant neoplasm of breast (SNOMED: 254837009) "
            "with extensive mammography history on record. Age 70, meets all CP-101 criteria."
        ),
    },
    {
        "id": "CASE-002",
        "patient_file": "Anisa442_West559_36772777-d04d-c2ef-6044-8b48e1738806.json",
        "patient_name": "Anisa West",
        "policy_id": "CP-101",
        "claim": {
            "procedure": "Combined chemotherapy and radiation therapy (procedure)",
            "snomed_code": "703423002",
            "reason": "Continuation of chemotherapy regimen for overlapping malignant neoplasm of colon",
            "requesting_provider": "Dr. James Chen, MD - Medical Oncology",
        },
        "expected_risk_tier": "Low Risk",
        "expected_recommendation": "Approve",
        "rationale": (
            "Patient has active Overlapping malignant neoplasm of colon (SNOMED: 109838007) "
            "with documented colonoscopy, biopsy, polypectomy, partial colon resection, and "
            "ongoing chemotherapy (Leucovorin + Oxaliplatin). Meets all CP-101 criteria."
        ),
    },
    {
        "id": "CASE-003",
        "patient_file": "Joshua658_Powlowski563_a4fd8715-f5c8-11ab-751f-d0428db09c6b.json",
        "patient_name": "Joshua Powlowski",
        "policy_id": "CP-101",
        "claim": {
            "procedure": "1 ML DOCEtaxel 20 MG/ML Injection",
            "snomed_code": "1732186",
            "reason": "Continuation of DOCEtaxel chemotherapy for prostate carcinoma",
            "requesting_provider": "Dr. Michael Torres, MD - Urologic Oncology",
        },
        "expected_risk_tier": "Low Risk",
        "expected_recommendation": "Approve",
        "rationale": (
            "Patient has active Neoplasm of prostate (SNOMED: 126906006) and Carcinoma in situ "
            "of prostate (SNOMED: 92691004). Currently on active DOCEtaxel + Leuprolide regimen. "
            "Meets all CP-101 criteria."
        ),
    },
    {
        "id": "CASE-004",
        "patient_file": "Zachary28_Funk324_f5ff9933-8a9c-dd0f-e0ae-65f34989dc62.json",
        "patient_name": "Zachary Funk",
        "policy_id": "CP-101",
        "claim": {
            "procedure": "Combined chemotherapy and radiation therapy (procedure)",
            "snomed_code": "703423002",
            "reason": "Request for chemotherapy initiation for breast neoplasm",
            "requesting_provider": "Dr. Emily Park, MD - Oncology",
        },
        "expected_risk_tier": "Moderate Risk",
        "expected_recommendation": "Manual Review Required",
        "rationale": (
            "Patient has active Malignant neoplasm of breast (SNOMED: 254837009) and prior "
            "mammography on record, meeting diagnosis and imaging criteria. However, patient "
            "also has Cardiac Arrest history (SNOMED: 410429000) which may present "
            "contraindication risks for chemotherapy. Requires manual clinical review."
        ),
    },

    # =========================================================================
    # CP-202 NEUROLOGY (3 cases)
    # =========================================================================
    {
        "id": "CASE-005",
        "patient_file": "Mavis612_Gusikowski974_503d6f48-db61-baca-882b-5d2767482889.json",
        "patient_name": "Mavis Gusikowski",
        "policy_id": "CP-202",
        "claim": {
            "procedure": "Specialty AED: Lacosamide (Vimpat) 100 MG Oral Tablet",
            "snomed_code": "230265002",
            "reason": "Request for specialty antiepileptic drug due to continued seizure activity",
            "requesting_provider": "Dr. Robert Kim, MD - Neurology",
        },
        "expected_risk_tier": "Moderate Risk",
        "expected_recommendation": "Manual Review Required",
        "rationale": (
            "Patient has active Epilepsy (SNOMED: 84757009) and Seizure disorder (SNOMED: 128613002). "
            "Currently on Carbamazepine (Tegretol) which is 1 first-line AED, but policy CP-202 "
            "requires trial of at least 2 first-line generic AEDs. Step therapy incomplete."
        ),
    },
    {
        "id": "CASE-006",
        "patient_file": "Lewis216_D'Amore443_911e6aeb-5844-9daf-7fd7-6aa2c137b22f.json",
        "patient_name": "Lewis D'Amore",
        "policy_id": "CP-202",
        "claim": {
            "procedure": "Specialty AED: Brivaracetam (Briviact) 50 MG Oral Tablet",
            "snomed_code": "230265002",
            "reason": "Request for specialty antiepileptic drug for refractory epilepsy management",
            "requesting_provider": "Dr. Lisa Nakamura, MD - Neurology",
        },
        "expected_risk_tier": "High Risk",
        "expected_recommendation": "Deny",
        "rationale": (
            "Patient has active Epilepsy (SNOMED: 84757009) and Seizure disorder (SNOMED: 128613002), "
            "meeting the diagnosis requirement. However, current active medications are Donepezil/"
            "Memantine (for dementia) and Simvastatin -- NONE of which are first-line AEDs. "
            "No evidence of any prior generic AED trial in the medication history. "
            "Step therapy requirement completely unmet per CP-202 Section 2.2."
        ),
    },
    {
        "id": "CASE-007",
        "patient_file": "Gabriela205_Arag\u00f3n562_483b8dd4-c6e0-32b3-b91c-d6bfd3375ae7.json",
        "patient_name": "Gabriela Aragon",
        "policy_id": "CP-202",
        "claim": {
            "procedure": "Specialty AED: Perampanel (Fycompa) 2 MG Oral Tablet",
            "snomed_code": "128613002",
            "reason": "Request for specialty antiepileptic drug for seizure disorder management",
            "requesting_provider": "Dr. Carlos Rivera, MD - Neurology",
        },
        "expected_risk_tier": "High Risk",
        "expected_recommendation": "Deny",
        "rationale": (
            "Patient has active Seizure disorder (SNOMED: 128613002) but NOT Epilepsy (84757009) "
            "specifically. Active medications include Naproxen and Simvastatin -- NONE are "
            "antiepileptic drugs. No evidence of any prior first-line AED trial in the "
            "medication history. Step therapy requirement completely unmet per CP-202."
        ),
    },

    # =========================================================================
    # CP-303 ORTHOPEDICS (3 cases)
    # =========================================================================
    {
        "id": "CASE-008",
        "patient_file": "Conrad619_Kiehn525_4d5b258e-e71a-1352-2b8c-a9efead91fb0.json",
        "patient_name": "Conrad Kiehn",
        "policy_id": "CP-303",
        "claim": {
            "procedure": "Total knee replacement (procedure)",
            "snomed_code": "609588000",
            "reason": "Elective total knee arthroplasty for severe osteoarthritis of knee",
            "requesting_provider": "Dr. William Hayes, MD - Orthopedic Surgery",
        },
        "expected_risk_tier": "Moderate Risk",
        "expected_recommendation": "Manual Review Required",
        "rationale": (
            "Patient has active Osteoarthritis of knee (SNOMED: 239873007), meeting the "
            "diagnosis requirement. However, the medical record must be reviewed for documented "
            "conservative therapy trial (physical therapy, NSAIDs) of at least 6 weeks. "
            "Patient has obesity (BMI 30+) but policy requires BMI < 40, which needs "
            "verification from vitals."
        ),
    },
    {
        "id": "CASE-009",
        "patient_file": "Norma469_Lynch190_4fef9f33-4d12-e8c3-4928-f10d24f9c2f2.json",
        "patient_name": "Norma Lynch",
        "policy_id": "CP-303",
        "claim": {
            "procedure": "Total knee replacement (procedure)",
            "snomed_code": "609588000",
            "reason": "Elective total knee arthroplasty for osteoarthritis with chronic pain",
            "requesting_provider": "Dr. Patricia Coleman, MD - Orthopedic Surgery",
        },
        "expected_risk_tier": "Low Risk",
        "expected_recommendation": "Approve",
        "rationale": (
            "Patient has active Osteoarthritis of knee (SNOMED: 239873007) with documented "
            "Chronic pain (SNOMED: 82423001). Active medications include Naproxen sodium "
            "(an NSAID) and Simvastatin, showing evidence of conservative NSAID therapy. "
            "Coronary Heart Disease is noted but not a contraindication for TKA."
        ),
    },
    {
        "id": "CASE-010",
        "patient_file": "Lorita217_Kautzer186_66b65dab-7533-5a06-e6f8-7b83fbf5610c.json",
        "patient_name": "Lorita Kautzer",
        "policy_id": "CP-303",
        "claim": {
            "procedure": "Total knee replacement (procedure)",
            "snomed_code": "609588000",
            "reason": "Elective total knee arthroplasty for osteoarthritis management",
            "requesting_provider": "Dr. Andrew Walsh, MD - Orthopedic Surgery",
        },
        "expected_risk_tier": "Moderate Risk",
        "expected_recommendation": "Manual Review Required",
        "rationale": (
            "Patient has active Osteoarthritis of knee (SNOMED: 239873007), meeting the "
            "diagnosis requirement. However, patient also has Chronic congestive heart failure "
            "(SNOMED: 88805009) which presents significant surgical risk. Active cardiac "
            "medications (Furosemide, Carvedilol) indicate ongoing heart failure management. "
            "Requires cardiology clearance and surgical risk assessment."
        ),
    },
]


def get_demo_case(case_id):
    """Get a demo case by its ID."""
    for case in DEMO_CASES:
        if case["id"] == case_id:
            return case
    return None


def get_all_demo_cases():
    """Get all demo cases."""
    return DEMO_CASES


def get_patient_filepath(case):
    """Get the full file path for a case's patient FHIR file."""
    return os.path.join(SYNTHEA_DATA_DIR, case["patient_file"])


def list_case_ids():
    """List all case IDs with summary."""
    return [
        {
            "id": c["id"],
            "patient": c["patient_name"],
            "policy": c["policy_id"],
            "expected": c["expected_risk_tier"],
        }
        for c in DEMO_CASES
    ]
