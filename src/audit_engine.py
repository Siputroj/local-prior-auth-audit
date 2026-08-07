"""
AI Prior Authorization Audit Engine.

Integrates with local Ollama service (qwen2.5:14b) via HTTP REST API.
Formulates structured prompts combining Coverage Policy, Patient FHIR Record,
and Claim Request. Enforces strict JSON output with Chain-of-Thought reasoning
and verbatim evidence citations.
"""
import json
import os
import time
import requests
from src.policies import get_policy_text
from src.fhir_parser import load_fhir_bundle, extract_patient_summary, format_clinical_summary_markdown
from src.cases import get_patient_filepath


OLLAMA_API_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen2.5:7b"


SYSTEM_PROMPT = """You are an expert AI Prior Authorization Medical Auditor for an insurance company (Cotiviti).
Your task is to evaluate a Prior Authorization Claim Request against the patient's FHIR medical record and the health plan's Coverage Policy.

CRITICAL INSTRUCTIONS:
1. You MUST operate as an explainable AI designed for Human-in-the-Loop review.
2. Evaluate all mandatory policy criteria step-by-step using Chain-of-Thought (CoT) reasoning.
3. Classify the claim into exactly one of three Risk Tiers:
   - "Low Risk": Meets 100% of policy clinical criteria with verified medical necessity (Recommendation: "Approve").
   - "Moderate Risk": Missing documentation, step-therapy ambiguity, or partial criteria match requiring clinician review (Recommendation: "Manual Review Required").
   - "High Risk": Fails mandatory clinical guidelines, missing core diagnosis, or contraindications present (Recommendation: "Deny").

4. CLINICAL REASONING HEURISTICS (apply carefully before deciding the tier):
   (a) POLICY EXAMPLE LISTS ARE NON-EXHAUSTIVE. When a policy criterion lists specific
       procedures, diagnoses, or drugs as "acceptable" or "including" items, treat them as
       ILLUSTRATIVE EXAMPLES unless the policy uses restrictive language such as "only",
       "exclusively", or "must be one of the following". If the policy says "include" or
       "such as", any clinically equivalent evidence for the same organ system or therapeutic
       class also satisfies the criterion.
   (b) CONTINUATION-OF-THERAPY EVIDENCE. If the patient is ALREADY on an active oncology,
       neurologic, or chronic-disease treatment regimen matching the requested item's
       therapeutic class AND the required diagnosis is documented as active, treat this as
       strong prima facie evidence that a prior clinical workup occurred. Do NOT deny or
       flag as Moderate solely because the specific diagnostic procedure listed as an
       "example" in the policy is absent, when the active regimen is a match.
   (c) ORGAN-SYSTEM RELEVANCE. A diagnostic procedure only supports the diagnosis if it is
       relevant to the same organ system. Do NOT credit unrelated procedures (e.g., a
       Colonoscopy does NOT support a Prostate cancer diagnosis). Rely on active regimen
       evidence (heuristic b) instead when no organ-relevant procedure is on file.
   (d) STEP THERAPY IS STRICT. Where policies list first-line drugs by class (e.g., first-line
       AEDs), only medications in that named class count. Unrelated drugs (statins, dementia
       medications, NSAIDs for non-orthopedic use) do NOT count toward step therapy.
   (e) CONTRAINDICATIONS TRIGGER MODERATE, NOT HIGH. A confirmed diagnosis with a serious
       comorbidity that raises procedural risk (e.g., cardiac history for chemotherapy or
       elective surgery) should be classified Moderate Risk / Manual Review, not High Risk.

5. Provide EXHAUSTIVE VERBATIM CITATIONS:
   - "policy_verbatim_citations": Quote EVERY policy section or criterion evaluated in your Chain-of-Thought word-for-word.
   - "patient_record_verbatim_citations": YOU MUST INCLUDE A VERBATIM ENTRY FOR EVERY SINGLE PIECE OF EVIDENCE REFERENCED IN YOUR CHAIN-OF-THOUGHT. Specifically, quote every relevant diagnosis (with SNOMED code), EVERY evaluated procedure (with SNOMED code and date), and medication evaluated in your audit. Do NOT omit procedures or dates mentioned in your reasoning.
6. COMPLETE ALL REASONING STEPS: Every step in "chain_of_thought" MUST contain a complete clinical evaluation statement and a finding sentence. NEVER end on a header title without a detailed conclusion.
7. Output ONLY valid JSON matching the specified format. Do not include markdown preamble or extra conversational text outside the JSON.

REQUIRED JSON OUTPUT FORMAT:
{
  "risk_tier": "Low Risk | Moderate Risk | High Risk",
  "confidence_score": 90,
  "recommendation": "Approve | Manual Review Required | Deny",
  "chain_of_thought": [
    "Step 1 - Diagnosis Verification: [Detailed clinical evaluation finding...]",
    "Step 2 - Diagnostic Procedure History: [Detailed clinical evaluation finding...]",
    "Step 3 - Medication & Step Therapy: [Detailed clinical evaluation finding...]",
    "Step 4 - Contraindications & Red Flags: [Detailed clinical evaluation finding or explicitly state no red flags found]"
  ],
  "policy_verbatim_citations": [
    "Exact sentence quoted from coverage policy..."
  ],
  "patient_record_verbatim_citations": [
    "Exact diagnosis quoted from patient summary...",
    "Exact procedure line quoted from patient summary (including SNOMED code and date)...",
    "Exact medication line quoted from patient summary..."
  ],
  "missing_information_or_red_flags": [
    "Description of missing documentation or clinical red flag..."
  ]
}
"""


def build_audit_prompt(case, patient_summary_md, policy_text):
    """Build the complete audit prompt for the LLM."""
    claim = case["claim"]

    user_prompt = f"""=== PRIOR AUTHORIZATION CLAIM REQUEST ===
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
Follow the system instructions to produce a step-by-step Chain-of-Thought audit in strict JSON format.
REMINDER: Every single diagnosis, procedure (e.g. Mammography, Colonoscopy), medication, or clinical date evaluated in your Chain-of-Thought MUST be explicitly included in your "patient_record_verbatim_citations" array. Do NOT leave out any procedure or record detail that you used to form your audit decision!
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


def _clean_and_parse_json(text):
    """Extract and parse JSON from LLM response text, handling markdown blocks."""
    clean_text = text.strip()

    # Remove markdown code fences if present
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    elif clean_text.startswith("```"):
        clean_text = clean_text[3:]

    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]

    clean_text = clean_text.strip()

    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        # Fallback: try finding first '{' and last '}'
        start_idx = clean_text.find("{")
        end_idx = clean_text.rfind("}")
        if start_idx != -1 and end_idx != -1:
            try:
                return json.loads(clean_text[start_idx : end_idx + 1])
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
    # Test audit engine on Case 1
    from src.cases import DEMO_CASES
    print("Testing Audit Engine on CASE-001...")
    result = run_audit(DEMO_CASES[0])
    print(f"Status: {result['status']}")
    print(f"Latency: {result.get('latency_seconds')}s")
    if result["status"] == "success":
        print(json.dumps(result["parsed_json"], indent=2))
    else:
        print(f"Error: {result.get('error_message')}")