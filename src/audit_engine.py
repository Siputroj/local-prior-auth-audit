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


SYSTEM_PROMPT = """You are an expert AI Prior Authorization Medical Auditor for an insurance company (Cotiviti).
Your task is to evaluate a Prior Authorization Claim Request against the patient's FHIR medical record and the health plan's Coverage Policy.

CRITICAL INSTRUCTIONS:
1. CLINICAL AUDIT STANDARDS:
   - Base your evaluation on the patient's medical record, coverage policy criteria, and sound clinical knowledge.
   - Accurately assess whether patient diagnoses, procedure histories, drug trials, and clinical indicators meet the coverage policy requirements.

2. Classify the claim into exactly one of three Risk Tiers:
   - "Low Risk": Meets all core policy clinical criteria explicitly documented in the record (Recommendation: "Approve").
   - "Moderate Risk": Partial criteria met (e.g. exactly 1 valid first-line AED trial for CP-202), incomplete documentation, or explicit policy requirement for clinician review (Recommendation: "Manual Review Required").
   - "High Risk": Total failure of mandatory clinical guidelines (e.g. zero valid AED trials for CP-202, missing core diagnosis, or BMI >= 40 for CP-303) (Recommendation: "Deny").

3. CLINICAL REASONING GUIDELINES:
   (a) CP-101 (ONCOLOGY):
       - C1: Confirmed active malignant neoplasm diagnosis (breast, prostate, colon, lung, etc.) -> SATISFIED if present.
       - C2: Documented diagnostic procedure (mammography, colonoscopy, biopsy, bone scan, etc.) OR active oncology medication regimen (Docetaxel, Leuprolide, Oxaliplatin, Leucovorin, etc.) -> SATISFIED if present.
       - C3: Patient MUST be 18 years of age or older. Note: Any age of 18 or greater (e.g. 25, 45, 65, 70, 85, 90, 105 years old) is >= 18 and SATISFIES criterion C3. An age of 105 is greater than 18 and SATISFIES C3.
       - IF C1, C2, and C3 are met AND no active cardiac comorbidity (SNOMED: 410429000 Cardiac arrest, 88805009 Heart failure) is present on chemotherapy initiation, classify as "Low Risk" (Approve).
       - EXCEPTION: If the request is for chemotherapy/radiation initiation AND the patient has an active cardiac condition (SNOMED: 410429000 Cardiac arrest, 88805009 Heart failure), classify as "Moderate Risk" (Manual Review Required) per Section 3.2.
   (b) CP-202 (NEUROLOGY STEP THERAPY):
       - C1: Active epilepsy or seizure disorder diagnosis.
       - C2: First-line generic AEDs are ONLY: Carbamazepine (Tegretol), Levetiracetam (Keppra), Lamotrigine (Lamictal), Valproic Acid (Depakene), Phenytoin (Dilantin), Topiramate (Topamax). Active OR stopped records count as valid trials.
         * Count = 0 valid AEDs (e.g. only non-AEDs like Donepezil, Memantine, Simvastatin) -> "High Risk" (Deny).
         * Count = 1 valid AED (e.g. Carbamazepine/Tegretol) -> "Moderate Risk" (Manual Review Required).
         * Count >= 2 valid AEDs -> "Low Risk" (Approve).
   (c) CP-303 (ORTHOPEDICS):
       - C1: Active osteoarthritis diagnosis (knee, hip, general).
       - C2: Conservative therapy trial (NSAIDs e.g. Ibuprofen, Naproxen, physical therapy, immobilization, corticosteroid injection). Active OR stopped records count.
       - C3: BMI < 40.
       - IF C1, C2, and C3 (BMI < 40) are met, you MUST classify as "Low Risk" (Approve).

4. OUTPUT SCHEMA INSTRUCTIONS:
   - Output ONLY valid JSON matching the exact schema below.
   - You MUST include "risk_tier" and "recommendation" as the VERY FIRST keys in your output JSON object!
   - Keep "chain_of_thought" as a simple flat list of strings.

REQUIRED JSON OUTPUT FORMAT:
{
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
}
"""


def build_audit_prompt(case, patient_summary_md, policy_text):
    """Build the complete audit prompt for the LLM."""
    claim = case["claim"]

    user_prompt = f"""{SYSTEM_PROMPT}

=== PRIOR AUTHORIZATION CLAIM REQUEST ===
- Claim ID: {case['id']}
- Patient Name: {case['patient_name']}
- Requested Procedure / Item: {claim['procedure']} (SNOMED / RxNorm: {claim['snomed_code']})
- Reason for Request: {claim['reason']}
- Requesting Provider: {claim['requesting_provider']}
- Applicable Coverage Policy ID: {case['policy_id']}

=== COVERAGE POLICY ({case['policy_id']}) ===
{policy_text}

=== PATIENT MEDICAL RECORD (FHIR SUMMARY) ===
{patient_summary_md}

=== AUDIT TASK ===
Evaluate the above claim against the Coverage Policy and Patient Record.
Follow the system instructions to produce a step-by-step Chain-of-Thought audit in strict JSON format:
"""
    return user_prompt


def run_audit(case, model=DEFAULT_MODEL, timeout_seconds=600):
    """
    Execute a local Ollama AI audit for a given prior auth case.

    Returns dict containing:
        - raw_response: text output from LLM
        - parsed_json: structured JSON response
        - latency_seconds: inference execution time
        - status: "success" or "error"
        - error_message: string if error occurred
    """
    # 1. Load patient FHIR data
    fpath = get_patient_filepath(case)
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

    # 3. Build prompt
    prompt = build_audit_prompt(case, patient_summary_md, policy_text)

    # 4. Call Ollama REST API
    payload = {
        "model": model,
        "system": SYSTEM_PROMPT,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "keep_alive": "30m",
        "options": {
            "temperature": 0.1,  # Low temperature for deterministic, factual audit
            "top_p": 0.9,
            "num_predict": 2048,
            "num_ctx": 4096,
        },
    }

    start_time = time.time()
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=timeout_seconds)
        latency = round(time.time() - start_time, 2)

        if response.status_code != 200:
            return {
                "status": "error",
                "error_message": f"Ollama HTTP error {response.status_code}: {response.text}",
                "latency_seconds": latency,
            }

        response_data = response.json()
        raw_text = response_data.get("response", "")

        # 5. Parse JSON output
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