"""
FHIR R4 Bundle Parser for Synthea Patient Records.

Extracts structured clinical profiles from raw FHIR JSON bundles:
- Patient demographics (name, age, gender)
- Active conditions with SNOMED CT codes
- Medication history with RxNorm codes and dosages
- Procedure history with SNOMED CT codes
- Key observations (BMI, vitals)
"""
import json
import os
from datetime import datetime, date


# Reference date for Synthea Coherent dataset (Nov 7, 2022)
REFERENCE_DATE = date(2022, 11, 7)


def load_fhir_bundle(filepath):
    """Load a FHIR R4 Bundle JSON file and return the parsed dict."""
    with open(filepath, "r") as f:
        return json.load(f)


def extract_patient_summary(bundle):
    """
    Extract a structured clinical summary from a FHIR R4 Bundle.

    Returns a dict with:
        - demographics: name, birth_date, age, gender
        - active_conditions: list of active diagnoses with SNOMED codes
        - resolved_conditions: list of resolved diagnoses
        - medications: list of medication requests (active and stopped)
        - procedures: list of performed procedures with SNOMED codes
        - observations: key vitals (BMI, blood pressure)
    """
    demographics = {}
    active_conditions = []
    resolved_conditions = []
    medications_active = []
    medications_stopped = []
    procedures = []
    observations = []

    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        resource_type = resource.get("resourceType")

        if resource_type == "Patient":
            demographics = _extract_demographics(resource)

        elif resource_type == "Condition":
            condition = _extract_condition(resource)
            if condition:
                if condition["clinical_status"] == "active":
                    active_conditions.append(condition)
                else:
                    resolved_conditions.append(condition)

        elif resource_type == "MedicationRequest":
            med = _extract_medication(resource)
            if med:
                if med["status"] == "active":
                    medications_active.append(med)
                else:
                    medications_stopped.append(med)

        elif resource_type == "Procedure":
            proc = _extract_procedure(resource)
            if proc:
                procedures.append(proc)

        elif resource_type == "Observation":
            obs = _extract_observation(resource)
            if obs:
                observations.append(obs)

    # Sort procedures by date (most recent first)
    procedures.sort(key=lambda x: x.get("date", ""), reverse=True)

    # Deduplicate stopped medications (keep most recent)
    medications_stopped = _deduplicate_medications(medications_stopped)

    return {
        "demographics": demographics,
        "active_conditions": active_conditions,
        "resolved_conditions": resolved_conditions,
        "medications_active": medications_active,
        "medications_stopped": medications_stopped,
        "procedures": procedures,
        "observations": observations,
    }


def _extract_demographics(patient_resource):
    """Extract patient demographics from a FHIR Patient resource."""
    names = patient_resource.get("name", [{}])[0]
    given = " ".join(names.get("given", []))
    family = names.get("family", "")
    birth_date_str = patient_resource.get("birthDate", "")

    age = None
    if birth_date_str:
        try:
            birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
            age = (REFERENCE_DATE - birth_date).days // 365
        except ValueError:
            pass

    return {
        "name": f"{given} {family}".strip(),
        "birth_date": birth_date_str,
        "age": age,
        "gender": patient_resource.get("gender", "unknown"),
    }


def _extract_condition(condition_resource):
    """Extract a condition from a FHIR Condition resource."""
    clinical_status = (
        condition_resource.get("clinicalStatus", {})
        .get("coding", [{}])[0]
        .get("code", "unknown")
    )

    code_obj = condition_resource.get("code", {})
    coding = code_obj.get("coding", [{}])[0]
    display = code_obj.get("text") or coding.get("display", "Unknown")
    snomed_code = coding.get("code", "N/A")
    system = coding.get("system", "")

    onset = condition_resource.get("onsetDateTime", "")
    # Trim to date only
    if onset and "T" in onset:
        onset = onset.split("T")[0]

    if display == "Unknown" or display == "N/A":
        return None

    return {
        "display": display,
        "snomed_code": snomed_code,
        "system": system,
        "clinical_status": clinical_status,
        "onset_date": onset,
    }


def _extract_medication(med_resource):
    """Extract medication info from a FHIR MedicationRequest resource."""
    status = med_resource.get("status", "unknown")
    med_concept = med_resource.get("medicationCodeableConcept", {})
    coding = med_concept.get("coding", [{}])[0]
    display = med_concept.get("text") or coding.get("display", "N/A")
    rxnorm_code = coding.get("code", "N/A")

    authored_on = med_resource.get("authoredOn", "")
    if authored_on and "T" in authored_on:
        authored_on = authored_on.split("T")[0]

    # Extract dosage instructions if available
    dosage_text = ""
    dosage_instructions = med_resource.get("dosageInstruction", [])
    if dosage_instructions:
        first_dosage = dosage_instructions[0]
        timing = first_dosage.get("timing", {}).get("repeat", {})
        dose_qty = first_dosage.get("doseAndRate", [{}])[0].get("doseQuantity", {})
        if dose_qty:
            dosage_text = f"{dose_qty.get('value', '')} {dose_qty.get('unit', '')}".strip()

    if display == "N/A":
        return None

    return {
        "display": display,
        "rxnorm_code": rxnorm_code,
        "status": status,
        "authored_on": authored_on,
        "dosage": dosage_text,
    }


def _extract_procedure(proc_resource):
    """Extract procedure info from a FHIR Procedure resource."""
    code_obj = proc_resource.get("code", {})
    coding = code_obj.get("coding", [{}])[0]
    display = code_obj.get("text") or coding.get("display", "Unknown")
    snomed_code = coding.get("code", "N/A")

    performed = proc_resource.get("performedPeriod", {}).get(
        "start", proc_resource.get("performedDateTime", "")
    )
    if performed and "T" in performed:
        performed = performed.split("T")[0]

    if display == "Unknown":
        return None

    return {
        "display": display,
        "snomed_code": snomed_code,
        "date": performed,
    }


def _extract_observation(obs_resource):
    """Extract key observations (BMI, blood pressure) from FHIR Observation resource."""
    code_obj = obs_resource.get("code", {})
    coding = code_obj.get("coding", [{}])[0]
    display = coding.get("display", "")
    loinc_code = coding.get("code", "")

    # Only extract BMI and Blood Pressure
    relevant_codes = {
        "39156-5": "BMI",
        "55284-4": "Blood Pressure",
        "8302-2": "Body Height",
        "29463-7": "Body Weight",
    }

    if loinc_code not in relevant_codes:
        return None

    value = None
    unit = ""
    value_qty = obs_resource.get("valueQuantity", {})
    if value_qty:
        value = value_qty.get("value")
        unit = value_qty.get("unit", "")

    # For blood pressure, extract components
    components = []
    for comp in obs_resource.get("component", []):
        comp_coding = comp.get("code", {}).get("coding", [{}])[0]
        comp_value = comp.get("valueQuantity", {})
        components.append({
            "display": comp_coding.get("display", ""),
            "value": comp_value.get("value"),
            "unit": comp_value.get("unit", ""),
        })

    effective = obs_resource.get("effectiveDateTime", "")
    if effective and "T" in effective:
        effective = effective.split("T")[0]

    return {
        "type": relevant_codes.get(loinc_code, display),
        "display": display,
        "value": value,
        "unit": unit,
        "components": components,
        "date": effective,
    }


def _deduplicate_medications(medications):
    """Deduplicate stopped medications, keeping the most recent entry per drug name."""
    seen = {}
    for med in medications:
        key = med["display"]
        if key not in seen or med["authored_on"] > seen[key]["authored_on"]:
            seen[key] = med
    return list(seen.values())


def format_clinical_summary_markdown(summary):
    """
    Format a patient clinical summary as a structured Markdown string
    suitable for LLM context injection.
    """
    d = summary["demographics"]
    lines = []
    lines.append(f"## Patient Clinical Summary")
    lines.append(f"- Name: {d['name']}")
    lines.append(f"- Age: {d['age']} years old")
    lines.append(f"- Gender: {d['gender']}")
    lines.append(f"- Date of Birth: {d['birth_date']}")

    # Active Conditions
    lines.append(f"\n### Active Conditions ({len(summary['active_conditions'])})")
    for c in summary["active_conditions"]:
        lines.append(f"- {c['display']} (SNOMED: {c['snomed_code']}) [onset: {c['onset_date']}]")

    # Active Medications
    lines.append(f"\n### Active Medications ({len(summary['medications_active'])})")
    if summary["medications_active"]:
        for m in summary["medications_active"]:
            dosage_str = f" | Dosage: {m['dosage']}" if m["dosage"] else ""
            lines.append(f"- {m['display']} (RxNorm: {m['rxnorm_code']}){dosage_str}")
    else:
        lines.append("- No active medications on record.")

    # Stopped Medications (recent, for step-therapy history)
    stopped = summary["medications_stopped"][:10]
    if stopped:
        lines.append(f"\n### Recent Medication History ({len(stopped)} most recent)")
        for m in stopped:
            lines.append(f"- [STOPPED] {m['display']} (RxNorm: {m['rxnorm_code']}) [last prescribed: {m['authored_on']}]")

    # Procedures
    recent_procs = summary["procedures"][:15]
    lines.append(f"\n### Procedure History ({len(recent_procs)} most recent)")
    for p in recent_procs:
        lines.append(f"- {p['display']} (SNOMED: {p['snomed_code']}) [date: {p['date']}]")

    # Key Observations (most recent BMI)
    bmi_obs = [o for o in summary["observations"] if o["type"] == "BMI"]
    if bmi_obs:
        latest_bmi = max(bmi_obs, key=lambda x: x.get("date", ""))
        lines.append(f"\n### Key Vitals")
        lines.append(f"- BMI: {latest_bmi['value']} {latest_bmi['unit']} [date: {latest_bmi['date']}]")

    return "\n".join(lines)


def get_patient_files(data_dir):
    """List all FHIR JSON files in the given directory."""
    import glob
    return sorted(glob.glob(os.path.join(data_dir, "*.json")))


if __name__ == "__main__":
    # Quick test: parse the first patient in synthea_data/
    import sys
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "synthea_data")
    files = get_patient_files(data_dir)
    if files:
        bundle = load_fhir_bundle(files[0])
        summary = extract_patient_summary(bundle)
        md = format_clinical_summary_markdown(summary)
        print(md)
        print(f"\n--- Token estimate: ~{len(md.split())} words ---")
    else:
        print("No FHIR files found.")
