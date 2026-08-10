"""
Demo Case Definitions for Prior Authorization Audit (Streamlit UI).

Ships THREE curated demo patients that appear in the dashboard - one per
coverage policy, spanning Low / Moderate / High risk tiers:

    CASE-DEMO-101 CP-101 Oncology       Low Risk       (Approve)
    CASE-DEMO-202 CP-202 Neurology      High Risk      (Deny)
    CASE-DEMO-303 CP-303 Orthopedics    Moderate Risk  (Manual Review Required)

The larger 100-case scaled F1 benchmark lives entirely under benchmark/
with its own patient corpus, so this module is only concerned with the
three showcase patients.
"""
import os


# Demo patient FHIR bundles live in src/synthea_data/ (ships with UI).
SYNTHEA_DATA_DIR = os.path.join(os.path.dirname(__file__), "synthea_data")


DEMO_CASES = [
    # -------------------------------------------------------------------------
    # CP-101 ONCOLOGY - Low Risk / Approve
    # -------------------------------------------------------------------------
    {
        "id": "CASE-DEMO-101",
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

    # -------------------------------------------------------------------------
    # CP-202 NEUROLOGY - High Risk / Deny
    # -------------------------------------------------------------------------
    {
        "id": "CASE-DEMO-202",
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

    # -------------------------------------------------------------------------
    # CP-303 ORTHOPEDICS - Moderate Risk / Manual Review
    # -------------------------------------------------------------------------
    {
        "id": "CASE-DEMO-303",
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
