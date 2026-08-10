"""
Deterministic policy rule engine for ground-truth tier derivation.

Encodes coverage policies CP-101 (Oncology), CP-202 (Neurology), and
CP-303 (Orthopedics) as pure Python functions. Each function takes a
patient FHIR summary (produced by src.fhir_parser.extract_patient_summary)
and returns (expected_tier, expected_recommendation, rationale).

This runs in milliseconds and requires no LLM calls, providing a
reproducible ground-truth signal for the scaled benchmark.
"""
from typing import Dict, Tuple


# ---------------------------------------------------------------------------
# Policy constants (aligned with src/policies.py)
# ---------------------------------------------------------------------------

CP101_MALIGNANCY_CODES = {
    "254837009",  # Malignant neoplasm of breast
    "109838007",  # Overlapping malignant neoplasm of colon
    "126906006",  # Neoplasm of prostate
    "92691004",   # Carcinoma in situ of prostate
    "93761005",   # Primary malignant neoplasm of colon
    "363406005",  # Malignant neoplasm of colon
    "254632001",  # Small cell carcinoma of lung
    "254637007",  # Non-small cell lung cancer
    "424132000",
    "1080591000119105",
}

CP101_DIAGNOSTIC_PROCEDURE_CODES = {
    "71651007",   # Mammography
    "73761001",   # Colonoscopy
    "76164006",   # Biopsy of colon
    "312681000",  # Bone density scan
    "43075005",   # Partial resection of colon
}

# Oncology treatment RxNorm codes that count as "active regimen" evidence.
CP101_ONCOLOGY_REGIMEN_RXNORM = {
    "1732186",   # DOCEtaxel
    "1946519",   # Leuprolide Acetate
    "1803932",   # Leucovorin
    "1736776",   # Oxaliplatin
}

# Keywords used as a fallback in the medication display name.
CP101_ONCOLOGY_KEYWORDS = {
    "docetaxel", "leuprolide", "leucovorin", "oxaliplatin",
    "cisplatin", "carboplatin", "paclitaxel", "tamoxifen",
    "anastrozole", "letrozole", "fluorouracil", "capecitabine",
}


CP202_DIAGNOSIS_CODES = {
    "84757009",   # Epilepsy
    "128613002",  # Seizure disorder
    "230265002",  # Familial epilepsy
    "313307000",  # Focal epilepsy
}

CP202_FIRST_LINE_AED_KEYWORDS = {
    "carbamazepine", "tegretol",
    "levetiracetam", "keppra",
    "lamotrigine", "lamictal",
    "valproic", "depakene", "valproate",
    "phenytoin", "dilantin",
    "topiramate", "topamax",
}


CP303_DIAGNOSIS_CODES = {
    "239873007",  # Osteoarthritis of knee
    "239872002",  # Osteoarthritis of hip
    "396275006",  # Osteoarthritis
}

CP303_CONSERVATIVE_THERAPY_KEYWORDS = {
    "naproxen", "ibuprofen", "meloxicam", "diclofenac", "celecoxib",
    "nsaid", "physical therapy", "physiotherapy",
    "corticosteroid", "cortisone", "methylprednisolone", "triamcinolone",
}

# Comorbidities that trigger Moderate Risk on TKA (surgical clearance needed).
# Restricted to serious, ACTIVE cardiac conditions only. Historical MI or
# coronary atherosclerosis on the resolved list is not flagged, matching
# how a human auditor typically reads the record.
CP303_HIGH_RISK_COMORBIDITY_CODES = {
    "88805009",   # Chronic congestive heart failure (active)
}

# Comorbidities that trigger Moderate Risk on chemotherapy/oncology treatment.
# Restricted to ACTIVE cardiac diagnoses; historical cardiac arrest that has
# resolved is not treated as a contraindication for continuation of therapy.
CP101_CHEMO_COMORBIDITY_CODES = {
    "410429000",  # Cardiac arrest (active)
    "88805009",   # Chronic congestive heart failure (active)
}


# ---------------------------------------------------------------------------
# Helper predicates over the parsed patient summary
# ---------------------------------------------------------------------------

def _active_condition_codes(summary: dict) -> set:
    return {c["snomed_code"] for c in summary.get("active_conditions", [])}


def _all_condition_codes(summary: dict) -> set:
    active = {c["snomed_code"] for c in summary.get("active_conditions", [])}
    resolved = {c["snomed_code"] for c in summary.get("resolved_conditions", [])}
    return active | resolved


def _procedure_codes(summary: dict) -> set:
    return {p["snomed_code"] for p in summary.get("procedures", [])}


def _medication_texts(summary: dict) -> list:
    """Return lowercase display + rxnorm strings for both active and stopped meds."""
    meds = summary.get("medications_active", []) + summary.get("medications_stopped", [])
    return [
        (m.get("display", "").lower(), str(m.get("rxnorm_code", "")))
        for m in meds
    ]


def _matches_any_keyword(text: str, keywords: set) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def _bmi(summary: dict):
    """Return the most recent BMI value or None."""
    bmis = [o for o in summary.get("observations", []) if o.get("type") == "BMI"]
    if not bmis:
        return None
    latest = max(bmis, key=lambda x: x.get("date", ""))
    return latest.get("value")


# ---------------------------------------------------------------------------
# Rule engines
# ---------------------------------------------------------------------------

def _evaluate_cp101(summary: dict, claim: dict) -> Tuple[str, str, str]:
    """
    CP-101 Oncology rules:
    - Must have active malignant neoplasm (C1) -> otherwise High Risk / Deny
    - Must have diagnostic evidence OR active oncology regimen (C2) -> otherwise Moderate Risk
    - Must be 18+ (C3) -> otherwise High Risk / Deny
    - Serious cardiac comorbidity for chemo/radiation -> Moderate Risk
    - Otherwise Low Risk / Approve
    """
    reasons = []

    # C3 - age check (fail fast)
    age = summary.get("demographics", {}).get("age") or 0
    if age < 18:
        return "High Risk", "Deny", f"Patient age {age} < 18 fails CP-101-C3."

    # C1 - active malignancy
    active_codes = _active_condition_codes(summary)
    has_malignancy = bool(active_codes & CP101_MALIGNANCY_CODES)
    if not has_malignancy:
        return (
            "High Risk",
            "Deny",
            "No active malignant neoplasm on record fails CP-101-C1.",
        )
    reasons.append("Active malignancy present (C1 met).")

    # C2 - diagnostic evidence OR active oncology regimen
    proc_codes = _procedure_codes(summary)
    has_dx_procedure = bool(proc_codes & CP101_DIAGNOSTIC_PROCEDURE_CODES)

    active_meds = summary.get("medications_active", [])
    has_active_regimen = False
    for m in active_meds:
        rx = str(m.get("rxnorm_code", ""))
        display = m.get("display", "").lower()
        if rx in CP101_ONCOLOGY_REGIMEN_RXNORM or _matches_any_keyword(
            display, CP101_ONCOLOGY_KEYWORDS
        ):
            has_active_regimen = True
            break

    if not (has_dx_procedure or has_active_regimen):
        return (
            "Moderate Risk",
            "Manual Review Required",
            "Malignancy documented but no diagnostic imaging/biopsy AND no active "
            "oncology regimen (CP-101-C2 partial).",
        )
    reasons.append(
        "Diagnostic imaging present." if has_dx_procedure else "Active oncology regimen present."
    )

    # Chemo/radiation cardiac contraindication -> Moderate
    requested_proc = claim.get("procedure", "").lower()
    is_chemo_request = (
        "chemotherapy" in requested_proc
        or "radiation" in requested_proc
        or "docetaxel" in requested_proc
        or claim.get("snomed_code") in {"703423002", "1732186"}
    )
    if is_chemo_request:
        # Cardiac contraindication only matters at chemotherapy INITIATION.
        # If the patient is already on an active oncology regimen matching
        # the therapeutic class of the request, cardiac clearance was
        # completed at initiation and continuation does not require
        # re-review. Detect continuation-of-therapy via has_active_regimen.
        is_continuation = has_active_regimen
        if not is_continuation:
            cardiac_codes = _active_condition_codes(summary) & CP101_CHEMO_COMORBIDITY_CODES
            if cardiac_codes:
                return (
                    "Moderate Risk",
                    "Manual Review Required",
                    f"Chemotherapy initiation request with active cardiac condition "
                    f"(SNOMED: {sorted(cardiac_codes)}) requires cardiology clearance.",
                )

    return "Low Risk", "Approve", " ".join(reasons)


def _evaluate_cp202(summary: dict, claim: dict) -> Tuple[str, str, str]:
    """
    CP-202 Neurology rules:
    - Must have epilepsy / seizure disorder (C1) -> High Risk if missing
    - Must have >=2 first-line AED trials (C2) -> High Risk if 0, Moderate if 1
    - Otherwise Low Risk
    """
    active_codes = _active_condition_codes(summary)
    has_diagnosis = bool(active_codes & CP202_DIAGNOSIS_CODES)
    if not has_diagnosis:
        return (
            "High Risk",
            "Deny",
            "No active epilepsy or seizure disorder diagnosis (CP-202-C1).",
        )

    # Count first-line AED trials across active + stopped medications
    aed_names_seen = set()
    for display, _rx in _medication_texts(summary):
        for kw in CP202_FIRST_LINE_AED_KEYWORDS:
            if kw in display:
                aed_names_seen.add(kw)
                break

    n_aed_trials = len(aed_names_seen)

    if n_aed_trials == 0:
        return (
            "High Risk",
            "Deny",
            "Zero first-line AED trials on record (CP-202-C2 fully unmet).",
        )
    if n_aed_trials == 1:
        return (
            "Moderate Risk",
            "Manual Review Required",
            f"Only 1 first-line AED trial documented ({sorted(aed_names_seen)}); "
            f"CP-202-C2 requires >=2.",
        )

    return (
        "Low Risk",
        "Approve",
        f"Epilepsy documented and {n_aed_trials} first-line AED trials on record.",
    )


def _evaluate_cp303(summary: dict, claim: dict) -> Tuple[str, str, str]:
    """
    CP-303 Orthopedics rules:
    - Must have osteoarthritis diagnosis (C1) -> High Risk if missing
    - Must have conservative therapy evidence (C2) -> Moderate Risk if missing
    - BMI must be < 40 (C3) -> High Risk if >= 40
    - Serious cardiac comorbidity -> Moderate Risk (surgical clearance)
    - Otherwise Low Risk
    """
    active_codes = _active_condition_codes(summary)
    has_diagnosis = bool(active_codes & CP303_DIAGNOSIS_CODES)
    if not has_diagnosis:
        return (
            "High Risk",
            "Deny",
            "No active osteoarthritis diagnosis on record (CP-303-C1).",
        )

    # BMI check
    bmi_value = _bmi(summary)
    if bmi_value is not None and bmi_value >= 40:
        return (
            "High Risk",
            "Deny",
            f"BMI {bmi_value} >= 40 without weight management program (CP-303-C3).",
        )

    # Conservative therapy check
    has_conservative = False
    for display, _rx in _medication_texts(summary):
        if _matches_any_keyword(display, CP303_CONSERVATIVE_THERAPY_KEYWORDS):
            has_conservative = True
            break
    if not has_conservative:
        # Check procedures for physical therapy
        for p in summary.get("procedures", []):
            if _matches_any_keyword(
                p.get("display", ""), CP303_CONSERVATIVE_THERAPY_KEYWORDS
            ):
                has_conservative = True
                break

    if not has_conservative:
        return (
            "Moderate Risk",
            "Manual Review Required",
            "Osteoarthritis documented but no conservative therapy trial found (CP-303-C2).",
        )

    # Cardiac comorbidity -> surgical clearance
    cardiac = _active_condition_codes(summary) & CP303_HIGH_RISK_COMORBIDITY_CODES
    if cardiac:
        return (
            "Moderate Risk",
            "Manual Review Required",
            f"Osteoarthritis + conservative therapy met, but cardiac comorbidity "
            f"(SNOMED: {sorted(cardiac)}) requires surgical clearance.",
        )

    return (
        "Low Risk",
        "Approve",
        "Osteoarthritis, conservative therapy, and BMI criteria all met.",
    )


# ---------------------------------------------------------------------------
# Public dispatcher
# ---------------------------------------------------------------------------

POLICY_EVALUATORS = {
    "CP-101": _evaluate_cp101,
    "CP-202": _evaluate_cp202,
    "CP-303": _evaluate_cp303,
}


def evaluate_case(policy_id: str, patient_summary: dict, claim: dict) -> Dict[str, str]:
    """
    Compute the deterministic expected outcome for a case.

    Returns dict with:
        - expected_risk_tier: "Low Risk" | "Moderate Risk" | "High Risk"
        - expected_recommendation: "Approve" | "Manual Review Required" | "Deny"
        - rationale: short human-readable justification
    """
    evaluator = POLICY_EVALUATORS.get(policy_id)
    if not evaluator:
        raise ValueError(f"Unknown policy: {policy_id}")

    tier, rec, rationale = evaluator(patient_summary, claim)
    return {
        "expected_risk_tier": tier,
        "expected_recommendation": rec,
        "rationale": rationale,
    }
