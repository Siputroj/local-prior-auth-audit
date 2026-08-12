"""
Demo Case Definitions for Prior Authorization Audit (Streamlit UI).

Ships THREE curated demo patients that appear in the dashboard,
ordered to showcase all three risk tiers:

    CASE-DEMO-001 CP-101 Oncology       Low Risk       (Approve)
    CASE-DEMO-002 CP-202 Neurology      Moderate Risk  (Manual Review Required)
    CASE-DEMO-003 CP-202 Neurology      High Risk      (Deny)

The larger 100-case scaled F1 benchmark lives entirely under benchmark/
with its own patient corpus, so this module is only concerned with the
three showcase patients.
"""
import os


# Demo patient FHIR bundles live in src/synthea_data/ (ships with UI).
SYNTHEA_DATA_DIR = os.path.join(os.path.dirname(__file__), "synthea_data")


DEMO_CASES = [
    # -------------------------------------------------------------------------
    # CASE 1: CP-101 ONCOLOGY - Low Risk / Approve
    # -------------------------------------------------------------------------
    {
        "id": "CASE-DEMO-001",
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
    # CASE 2: CP-202 NEUROLOGY - Moderate Risk / Manual Review
    # Patient has exactly 1 valid first-line AED (Carbamazepine/Tegretol).
    # Per CP-202 Section 3.3: "Authorization SHALL require MANUAL REVIEW if
    # the patient has trialed only 1 first-line AED."
    # -------------------------------------------------------------------------
    {
        "id": "CASE-DEMO-002",
        "patient_file": "Mavis612_Gusikowski974_503d6f48-db61-baca-882b-5d2767482889.json",
        "patient_name": "Mavis Gusikowski",
        "policy_id": "CP-202",
        "claim": {
            "procedure": "Specialty AED: Lacosamide (Vimpat) 100 MG Oral Tablet",
            "snomed_code": "230265002",
            "reason": "Request for specialty antiepileptic drug for continued seizure activity",
            "requesting_provider": "Dr. Robert Kim, MD - Neurology",
        },
        "expected_risk_tier": "Moderate Risk",
        "expected_recommendation": "Manual Review Required",
        "rationale": (
            "Patient has active Epilepsy (SNOMED: 84757009) and Seizure disorder "
            "(SNOMED: 128613002), satisfying CP-202 criterion 2.1. Patient has exactly "
            "1 valid first-line generic AED on record: Carbamazepine/Tegretol (RxNorm: 308971). "
            "Per CP-202 Section 3.3, only 1 first-line AED trial documented when 2 are required "
            "triggers mandatory Manual Review."
        ),
    },

    # -------------------------------------------------------------------------
    # CASE 3: CP-202 NEUROLOGY - High Risk / Deny
    # Patient has 0 valid first-line AEDs. All medications are non-AED
    # (Donepezil, Memantine, Simvastatin). Step therapy completely unmet.
    # Per CP-202 Section 3.4: "Claims without any prior generic AED trial
    # history present a HIGH RISK of policy non-compliance."
    # -------------------------------------------------------------------------
    {
        "id": "CASE-DEMO-003",
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
            "Step therapy requirement completely unmet per CP-202 Section 3.4."
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


def get_patient_filepath(case, patient_dir=None):
    """Get the full file path for a case's patient FHIR file."""
    directory = patient_dir if patient_dir is not None else SYNTHEA_DATA_DIR
    return os.path.join(directory, case["patient_file"])


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
