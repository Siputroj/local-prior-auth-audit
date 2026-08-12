"""
AI Prior Authorization Audit Engine.

Integrates with local Ollama service (default: qwen2.5:7b) via HTTP REST API.
Formulates structured prompts combining Coverage Policy, Patient FHIR Record,
and Claim Request. Enforces strict JSON output with Chain-of-Thought reasoning
and verbatim evidence citations.
"""
import json
import os
import re
import time
import requests
from src.policies import get_policy_text
from src.fhir_parser import load_fhir_bundle, extract_patient_summary, format_clinical_summary_markdown
from src.cases import get_patient_filepath


def _load_env():
    """Load key-value pairs from root .env file into os.environ if not already set."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip())


_load_env()

OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")


EXTRACTION_SYSTEM_PROMPT = """You are a clinical fact extraction assistant.
Your task is to parse a Patient Medical Record (FHIR Summary) and extract key clinical details required for prior authorization auditing.
Extract and output ONLY a valid JSON object matching the exact schema below. Do not include any explanation.

REQUIRED JSON OUTPUT FORMAT:
{
  "demographics": {
    "age": 0,
    "gender": "male | female"
  },
  "active_conditions": [
    "Condition name (SNOMED: code)"
  ],
  "active_medications": [
    "Medication name (RxNorm: code)"
  ],
  "stopped_or_historical_medications": [
    "Medication name (RxNorm: code)"
  ],
  "procedures": [
    "Procedure name (SNOMED: code) [date: YYYY-MM-DD]"
  ],
  "observations": [
    "Observation type (e.g. BMI): value [date: YYYY-MM-DD]"
  ]
}
"""

def get_decomposed_system_prompt(policy_id):
    from src.policies import get_policy
    policy = get_policy(policy_id)
    guidelines = policy.get("guidelines", "") if policy else ""

    return f"""You are an expert AI Prior Authorization Medical Auditor for an insurance company (Cotiviti).
Your task is to evaluate a Prior Authorization Claim Request against the patient's Extracted Clinical Facts and the health plan's Coverage Policy.

CRITICAL INSTRUCTIONS:
1. CLINICAL AUDIT STANDARDS:
   - Base your evaluation on the patient's medical record, coverage policy criteria, and sound clinical knowledge.
   - Accurately assess whether patient diagnoses, procedure histories, drug trials, and clinical indicators meet the coverage policy requirements.

2. Classify the claim into exactly one of three Risk Tiers:
   - "Low Risk": Meets all core policy clinical criteria explicitly documented in the record (Recommendation: "Approve").
   - "Moderate Risk": Partial criteria met (e.g. exactly 1 valid first-line AED trial for CP-202), incomplete documentation, or explicit policy requirement for clinician review (Recommendation: "Manual Review Required").
   - "High Risk": Total failure of mandatory clinical guidelines (e.g. zero valid AED trials for CP-202, missing core diagnosis, or BMI >= 40 for CP-303) (Recommendation: "Deny").

3. CLINICAL REASONING GUIDELINES FOR {policy_id}:
{guidelines}

4. OUTPUT SCHEMA INSTRUCTIONS:
   - Output ONLY valid JSON matching the exact schema below.
   - You MUST include "risk_tier" and "recommendation" as the VERY FIRST keys in your output JSON object!
   - Keep "chain_of_thought" as a simple flat list of strings.

REQUIRED JSON OUTPUT FORMAT:
{{
  "risk_tier": "Low Risk | Moderate Risk | High Risk",
  "recommendation": "Approve | Manual Review Required | Deny",
  "confidence_score": 95,
  "chain_of_thought": [
    "Step 1 - Diagnosis Verification: [Detailed finding sentence]",
    "Step 2 - Diagnostic Procedure History: [Detailed finding sentence]",
    "Step 3 - Medication & Step Therapy: [Detailed finding sentence]",
    "Step 4 - Contraindications & Red Flags: [Detailed finding sentence]"
  ],
  "policy_verbatim_citations": [
    "Exact verbatim quote from policy..."
  ],
  "patient_record_verbatim_citations": [
    "Exact verbatim quote from patient record..."
  ]
}}
"""

# Dynamic few-shot examples block for reference
FEW_SHOT_EXAMPLE = """
=== FEW-SHOT AUDIT EXAMPLE ===

=== PRIOR AUTHORIZATION CLAIM REQUEST ===
- Claim ID: CASE-EXAMPLE-01
- Patient Name: John Doe
- Requested Procedure / Item: Specialty AED: Lacosamide (Vimpat) 100 MG Oral Tablet (RxNorm: 230265002)
- Reason for Request: Request for specialty antiepileptic drug for continued seizure activity
- Requesting Provider: Dr. Robert Kim, MD - Neurology
- Applicable Coverage Policy ID: CP-202

=== COVERAGE POLICY (CP-202) ===
Section 2 - Mandatory Clinical Criteria:
2.1 The patient MUST have an active epilepsy or seizure disorder diagnosis documented in their medical record. Acceptable diagnoses include: Epilepsy (SNOMED: 84757009), Seizure disorder (SNOMED: 128613002).
2.2 The patient MUST have documented trial of at least 2 first-line generic antiepileptic drugs (AEDs). First-line AEDs include: Carbamazepine (Tegretol), Levetiracetam (Keppra).
Section 3 - Decision Tiers & Criteria:
3.1 LOW RISK (Approve): Patient has active epilepsy diagnosis AND at least 2 first-line generic AED trials documented.
3.2 MODERATE RISK (Manual Review Required): Patient has active epilepsy diagnosis AND documented trial of EXACTLY 1 first-line generic AED (or incomplete trial duration documentation).
3.3 HIGH RISK (Deny): Patient has NO active epilepsy diagnosis, OR has 0 first-line generic AED trials documented.

=== EXTRACTED CLINICAL FACTS ===
{
  "demographics": {
    "age": 45,
    "gender": "male"
  },
  "active_conditions": [
    "Seizure disorder (SNOMED: 128613002)"
  ],
  "active_medications": [
    "Levetiracetam (Keppra) (RxNorm: 1043400)"
  ],
  "stopped_or_historical_medications": [
    "Carbamazepine (Tegretol) (RxNorm: 308971)"
  ],
  "procedures": [],
  "observations": [
    "BMI: 28"
  ]
}

=== EXPECTED JSON OUTPUT ===
{
  "risk_tier": "Low Risk",
  "recommendation": "Approve",
  "confidence_score": 95,
  "chain_of_thought": [
    "Step 1 - Diagnosis Verification: Patient has documented active Seizure disorder (SNOMED: 128613002), satisfying CP-202-2.1.",
    "Step 2 - Diagnostic Procedure History: No diagnostic procedures required for CP-202.",
    "Step 3 - Medication & Step Therapy: Patient has active Levetiracetam (Keppra) and historical Carbamazepine (Tegretol) trials on record. This represents 2 first-line generic AED trials, satisfying the CP-202-2.2 step-therapy requirement.",
    "Step 4 - Contraindications & Red Flags: No cardiac comorbidities or contraindications present."
  ],
  "policy_verbatim_citations": [
    "2.1 The patient MUST have an active epilepsy or seizure disorder diagnosis documented",
    "2.2 The patient MUST have documented trial of at least 2 first-line generic antiepileptic drugs (AEDs)."
  ],
  "patient_record_verbatim_citations": [
    "Seizure disorder (SNOMED: 128613002)",
    "Levetiracetam (Keppra)",
    "Carbamazepine (Tegretol)"
  ]
}
"""


def build_audit_prompt(case, extracted_facts_json, policy_text):
    """Build the complete audit prompt for the LLM using extracted facts."""
    claim = case["claim"]
    sys_prompt = get_decomposed_system_prompt(case["policy_id"])

    user_prompt = f"""{sys_prompt}

=== PRIOR AUTHORIZATION CLAIM REQUEST ===
- Claim ID: {case['id']}
- Patient Name: {case['patient_name']}
- Requested Procedure / Item: {claim['procedure']} (SNOMED / RxNorm: {claim['snomed_code']})
- Reason for Request: {claim['reason']}
- Requesting Provider: {claim['requesting_provider']}
- Applicable Coverage Policy ID: {case['policy_id']}

=== COVERAGE POLICY ({case['policy_id']}) ===
{policy_text}

=== EXTRACTED CLINICAL FACTS (JSON) ===
{extracted_facts_json}

=== AUDIT TASK ===
Evaluate the above claim against the Coverage Policy and the Extracted Clinical Facts.
Follow the system instructions to produce a step-by-step Chain-of-Thought audit in strict JSON format:
"""
    return user_prompt


def run_audit(case, model=DEFAULT_MODEL, timeout_seconds=600, patient_dir=None):
    """
    Execute a decomposed multi-step local Ollama AI audit:
      1. Extract relevant clinical facts from patient record.
      2. Audits policy compliance against the extracted facts and policy.
    """
    # 1. Load patient FHIR data
    fpath = get_patient_filepath(case, patient_dir=patient_dir)
    if not os.path.exists(fpath):
        return {
            "status": "error",
            "error_message": f"Patient file not found: {fpath}",
            "latency_seconds": 0,
        }

    bundle = load_fhir_bundle(fpath)
    summary = extract_patient_summary(bundle)
    patient_summary_md = format_clinical_summary_markdown(summary)

    # 2. Get coverage policy text
    policy_text = get_policy_text(case["policy_id"])
    if not policy_text:
        return {
            "status": "error",
            "error_message": f"Policy not found: {case['policy_id']}",
            "latency_seconds": 0,
        }

    start_time = time.time()

    # Step 1: Clinical Fact Extraction
    extract_payload = {
        "model": model,
        "system": EXTRACTION_SYSTEM_PROMPT,
        "prompt": f"Please parse this patient FHIR summary and extract clinical details:\n\n{patient_summary_md}",
        "stream": False,
        "format": "json",
        "keep_alive": "30m",
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "num_predict": 1024,
            "num_ctx": 4096,
        },
    }

    try:
        extract_response = requests.post(OLLAMA_API_URL, json=extract_payload, timeout=timeout_seconds)
        if extract_response.status_code != 200:
            return {
                "status": "error",
                "error_message": f"Extraction HTTP error {extract_response.status_code}: {extract_response.text}",
                "latency_seconds": round(time.time() - start_time, 2),
            }
        extracted_facts_json = extract_response.json().get("response", "{}")
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Fact extraction failed: {str(e)}",
            "latency_seconds": round(time.time() - start_time, 2),
        }

    # Step 2: Policy Compliance Evaluation
    prompt = build_audit_prompt(case, extracted_facts_json, policy_text)
    sys_prompt = get_decomposed_system_prompt(case["policy_id"])

    audit_payload = {
        "model": model,
        "system": sys_prompt,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "keep_alive": "30m",
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "num_predict": 2048,
            "num_ctx": 4096,
        },
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=audit_payload, timeout=timeout_seconds)
        latency = round(time.time() - start_time, 2)

        if response.status_code != 200:
            return {
                "status": "error",
                "error_message": f"Audit HTTP error {response.status_code}: {response.text}",
                "latency_seconds": latency,
            }

        response_data = response.json()
        raw_text = response_data.get("response", "")

        # Parse JSON output
        parsed_json = _clean_and_parse_json(raw_text)

        return {
            "status": "success",
            "raw_response": raw_text,
            "parsed_json": parsed_json,
            "latency_seconds": latency,
            "patient_summary_md": patient_summary_md,
            "policy_text": policy_text,
        }

    except requests.exceptions.ConnectionError:
        return {
            "status": "error",
            "error_message": "Could not connect to local Ollama service. Ensure Ollama is running (`ollama serve`).",
            "latency_seconds": round(time.time() - start_time, 2),
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "latency_seconds": round(time.time() - start_time, 2),
        }


def warm_up_model(model=DEFAULT_MODEL, timeout_seconds=300):
    """
    Pre-load the Ollama model into memory to eliminate cold-start latency on
    the first real audit call. Sends a minimal prompt and instructs Ollama to
    keep the model resident in RAM for 30 minutes via keep_alive.

    Returns dict with:
        - status: "success" or "error"
        - latency_seconds: warm-up time
        - error_message: string if error occurred
    """
    payload = {
        "model": model,
        "prompt": "ok",
        "stream": False,
        "keep_alive": "30m",
        "options": {"num_predict": 1},
    }

    start_time = time.time()
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=timeout_seconds)
        latency = round(time.time() - start_time, 2)
        if response.status_code != 200:
            return {
                "status": "error",
                "error_message": f"Ollama warm-up HTTP error {response.status_code}: {response.text}",
                "latency_seconds": latency,
            }
        return {"status": "success", "latency_seconds": latency}
    except requests.exceptions.ConnectionError:
        return {
            "status": "error",
            "error_message": "Could not connect to local Ollama service. Ensure Ollama is running (`ollama serve`).",
            "latency_seconds": round(time.time() - start_time, 2),
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "latency_seconds": round(time.time() - start_time, 2),
        }


def _normalize_parsed_json(data):
    """Ensure standard keys exist and chain_of_thought is a flat list of strings."""
    # Check all possible tier/result keys generated by local LLMs
    tier_raw = str(
        data.get("risk_tier")
        or data.get("audit_result")
        or data.get("recommendation")
        or data.get("tier")
        or ""
    ).strip().lower()

    if not tier_raw and isinstance(data.get("risk_assessment"), list) and len(data["risk_assessment"]) > 0:
        first_item = data["risk_assessment"][0]
        if isinstance(first_item, dict):
            tier_raw = str(first_item.get("tier") or first_item.get("risk_tier") or first_item.get("recommendation") or "").strip().lower()

    if "high" in tier_raw or "deny" in tier_raw:
        data["risk_tier"] = "High Risk"
    elif "low" in tier_raw or "approve" in tier_raw:
        data["risk_tier"] = "Low Risk"
    elif "moderate" in tier_raw or "manual" in tier_raw or "review" in tier_raw:
        data["risk_tier"] = "Moderate Risk"
    else:
        data["risk_tier"] = "Moderate Risk"

    rec_map = {
        "Low Risk": "Approve",
        "Moderate Risk": "Manual Review Required",
        "High Risk": "Deny",
    }
    if data.get("risk_tier") in rec_map:
        data["recommendation"] = rec_map[data["risk_tier"]]

    # Handle alternate CoT key names (e.g. audit_reasoning)
    if "chain_of_thought" not in data:
        for alt_key in ["audit_reasoning", "reasoning", "cot_reasoning", "audit_steps"]:
            if alt_key in data:
                val = data.pop(alt_key)
                if isinstance(val, list):
                    flattened = []
                    for item in val:
                        if isinstance(item, dict):
                            step_desc = item.get("description") or item.get("finding") or item.get("conclusion") or str(item)
                            flattened.append(str(step_desc))
                        else:
                            flattened.append(str(item))
                    data["chain_of_thought"] = flattened
                elif isinstance(val, str):
                    data["chain_of_thought"] = [val]

    cot = data.get("chain_of_thought", [])
    if isinstance(cot, list):
        data["chain_of_thought"] = [str(x) for x in cot]
    elif isinstance(cot, str):
        data["chain_of_thought"] = [cot]

    for list_key in ["policy_verbatim_citations", "patient_record_verbatim_citations"]:
        if list_key not in data or not isinstance(data[list_key], list):
            data[list_key] = []

    return data


def _clean_and_parse_json(text):
    """Extract and parse JSON from LLM response text, handling markdown blocks."""
    import re
    
    # Try to find JSON block using regex if wrapped in markdown
    json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
    if json_match:
        clean_text = json_match.group(1).strip()
    else:
        clean_text = text.strip()

    try:
        data = json.loads(clean_text)
        return _normalize_parsed_json(data)
    except json.JSONDecodeError:
        pass

    # Fallback: try finding first '{' and last '}'
    start_idx = clean_text.find("{")
    end_idx = clean_text.rfind("}")
    if start_idx != -1 and end_idx != -1:
        try:
            data = json.loads(clean_text[start_idx : end_idx + 1])
            return _normalize_parsed_json(data)
        except json.JSONDecodeError:
            pass

    # Return fallback error object
    return {
        "risk_tier": "Moderate Risk",
        "confidence_score": 50,
        "recommendation": "Manual Review Required",
        "chain_of_thought": ["Raw response could not be fully parsed as structured JSON.", text[:500]],
        "policy_verbatim_citations": [],
        "patient_record_verbatim_citations": [],
        "missing_information_or_red_flags": ["LLM response parsing format warning."],
    }


if __name__ == "__main__":
    # Test audit engine on the first demo case
    from src.cases import DEMO_CASES
    print(f"Testing Audit Engine on {DEMO_CASES[0]['id']}...")
    result = run_audit(DEMO_CASES[0])
    print(f"Status: {result['status']}")
    print(f"Latency: {result.get('latency_seconds')}s")
    if result["status"] == "success":
        print(json.dumps(result["parsed_json"], indent=2))
    else:
        print(f"Error: {result.get('error_message')}")