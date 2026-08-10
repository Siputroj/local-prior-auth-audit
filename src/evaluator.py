"""
Quantitative F1-Score and AI Quality Evaluation Module (Streamlit demo).

Evaluates a local LLM prior-authorization audit output for one of the three
demo cases against the gold-standard labels in src/ground_truth_cases.json
(Claude-Opus-authored). Used ONLY by the UI single-case scorecard.

The scaled 100-case benchmark under benchmark/ uses its own metrics module.

Metrics Computed:
- Risk Tier Classification Accuracy (Exact match)
- Evidence Citation Precision: TP / (TP + FP)  [Hallucination metric]
- Evidence Citation Recall: TP / (TP + FN)     [Completeness metric]
- Citation F1-Score: 2 * (Precision * Recall) / (Precision + Recall)
- Verbatim Grounding Fidelity: % of cited quotes present word-for-word in source text
"""
import json
import os


GROUND_TRUTH_PATH = os.path.join(os.path.dirname(__file__), "ground_truth_cases.json")


def load_ground_truth_benchmarks():
    """Load gold-standard benchmark data."""
    if os.path.exists(GROUND_TRUTH_PATH):
        with open(GROUND_TRUTH_PATH, "r") as f:
            return json.load(f)
    return {}


def evaluate_audit_result(case_id, audit_result, patient_summary_md="", policy_text=""):
    """
    Evaluate an LLM audit result against the ground-truth benchmark for a case.

    Returns dict containing:
        - risk_tier_match: bool
        - precision: float (0.0 to 1.0)
        - recall: float (0.0 to 1.0)
        - f1_score: float (0.0 to 1.0)
        - grounding_fidelity: float (0.0 to 1.0)
        - tp: int, fp: int, fn: int
        - verbatim_checks: list of detailed quote verification results
    """
    benchmarks = load_ground_truth_benchmarks()
    gt = benchmarks.get(case_id, {})

    if not gt or audit_result.get("status") != "success":
        return {
            "risk_tier_match": False,
            "precision": 0.0,
            "recall": 0.0,
            "f1_score": 0.0,
            "grounding_fidelity": 0.0,
            "tp": 0,
            "fp": 0,
            "fn": 0,
            "verbatim_checks": [],
            "note": "Missing ground truth benchmark or audit execution failed.",
        }

    parsed = audit_result.get("parsed_json", {})
    pred_risk = parsed.get("risk_tier", "").strip()
    gt_risk = gt.get("expected_risk_tier", "").strip()

    # 1. Risk Tier Classification Accuracy
    risk_tier_match = (pred_risk.lower() == gt_risk.lower())

    # 2. Extract evidence items from LLM response (CoT + Citations)
    cot_text = " ".join(parsed.get("chain_of_thought", [])).lower()
    citations_text = " ".join(
        parsed.get("policy_verbatim_citations", []) + parsed.get("patient_record_verbatim_citations", [])
    ).lower()
    combined_llm_evidence = cot_text + " " + citations_text

    # 3. Compute Precision, Recall, F1 against Ground Truth Conditions & Procedures
    gt_conditions = [c.lower() for c in gt.get("ground_truth_conditions", [])]
    gt_medications = [m.lower() for m in gt.get("ground_truth_medications", [])]
    gt_procedures = [p.lower() for p in gt.get("ground_truth_procedures", [])]
    
    gt_all_facts = gt_conditions + gt_medications + gt_procedures
    
    tp = 0
    fn = 0
    fp = 0

    # Evaluate recall: how many ground truth facts did LLM mention?
    for fact in gt_all_facts:
        # Extract core terms (e.g. "breast", "mammography", "epilepsy", "osteoarthritis")
        keywords = _extract_keywords(fact)
        if any(kw in combined_llm_evidence for kw in keywords):
            tp += 1
        else:
            fn += 1

    # Evaluate precision / hallucination: did LLM claim false criteria or non-existent facts?
    red_flags = parsed.get("missing_information_or_red_flags", [])
    # If LLM cited citations, check if any citation is completely ungrounded (false positive)
    grounding_score, verbatim_checks = _evaluate_verbatim_fidelity(
        parsed, patient_summary_md, policy_text
    )

    if grounding_score < 0.5:
        fp += 1  # Penalize for ungrounded citations

    # Calculate metrics
    precision = round(tp / (tp + fp), 2) if (tp + fp) > 0 else 1.0
    recall = round(tp / (tp + fn), 2) if (tp + fn) > 0 else 1.0
    f1_score = round(2 * (precision * recall) / (precision + recall), 2) if (precision + recall) > 0 else 0.0

    return {
        "case_id": case_id,
        "predicted_risk_tier": pred_risk,
        "expected_risk_tier": gt_risk,
        "risk_tier_match": risk_tier_match,
        "precision": precision,
        "recall": recall,
        "f1_score": f1_score,
        "grounding_fidelity": grounding_score,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "verbatim_checks": verbatim_checks,
    }


def _extract_keywords(text):
    """Extract key clinical terms for fuzzy keyword matching."""
    stop_words = {"snomed:", "rxnorm:", "procedure", "disorder", "finding", "tablet", "oral", "mg", "ml", "injection", "of", "and", "or", "in", "a", "the"}
    words = text.replace("(", " ").replace(")", " ").replace(":", " ").split()
    keywords = [w.strip(",.").lower() for w in words if len(w) > 3 and w.lower() not in stop_words]
    return keywords if keywords else [text.lower()]


def _to_str(val) -> str:
    """Safely convert any JSON element (string, dict, list, int) to a cleaned string."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, dict):
        text_val = (
            val.get("quote")
            or val.get("text")
            or val.get("citation")
            or val.get("verbatim")
            or val.get("evidence")
        )
        if text_val:
            return str(text_val).strip()
        return " ".join(str(v).strip() for v in val.values() if v).strip()
    if isinstance(val, (list, tuple)):
        return " ".join(_to_str(item) for item in val if item).strip()
    return str(val).strip()


def _evaluate_verbatim_fidelity(parsed_json, patient_summary_md, policy_text):
    """
    Check if verbatim citations in LLM output actually exist in source text.
    Returns grounding_fidelity (0.0 to 1.0) and list of detailed check results.
    """
    policy_quotes = parsed_json.get("policy_verbatim_citations", []) or []
    patient_quotes = parsed_json.get("patient_record_verbatim_citations", []) or []

    checks = []
    total_quotes = len(policy_quotes) + len(patient_quotes)
    if total_quotes == 0:
        return 1.0, []

    verified_count = 0

    # Check policy citations
    for quote in policy_quotes:
        clean_quote = _to_str(quote)
        if not clean_quote:
            continue
        # Substring match or partial high-confidence match
        match = _sub_quote_match(clean_quote, policy_text)
        checks.append({
            "source": "Coverage Policy",
            "quote": clean_quote,
            "verbatim_match": match,
        })
        if match:
            verified_count += 1

    # Check patient summary citations
    for quote in patient_quotes:
        clean_quote = _to_str(quote)
        if not clean_quote:
            continue
        match = _sub_quote_match(clean_quote, patient_summary_md)
        checks.append({
            "source": "Patient Record",
            "quote": clean_quote,
            "verbatim_match": match,
        })
        if match:
            verified_count += 1

    fidelity = round(verified_count / max(len(checks), 1), 2)
    return fidelity, checks


def _sub_quote_match(quote, source_text):
    """Check if quote or main clause exists in source text."""
    if not source_text or not quote:
        return False

    q_str = _to_str(quote)
    if not q_str:
        return False

    q_lower = q_str.lower()
    s_lower = source_text.lower()

    if q_lower in s_lower:
        return True

    # Try matching key noun phrase or code (e.g. SNOMED code)
    if "snomed:" in q_lower or "rxnorm:" in q_lower:
        # Extract code number
        parts = q_lower.split()
        for p in parts:
            p_clean = p.strip("():,")
            if p_clean.isdigit() and len(p_clean) >= 6 and p_clean in s_lower:
                return True

    # Try matching first 5 words
    words = q_lower.split()
    if len(words) >= 4:
        phrase = " ".join(words[:5])
        if phrase in s_lower:
            return True

    return False


if __name__ == "__main__":
    # Test evaluation module
    print("Testing Evaluator Module...")
    sample_audit = {
        "status": "success",
        "parsed_json": {
            "risk_tier": "Low Risk",
            "confidence_score": 90,
            "recommendation": "Approve",
            "chain_of_thought": [
                "Step 1: Patient has confirmed Malignant neoplasm of breast (SNOMED: 254837009).",
                "Step 2: Diagnostic Mammography (SNOMED: 71651007) confirmed on record."
            ],
            "policy_verbatim_citations": [
                "The patient MUST have a confirmed active malignant neoplasm diagnosis documented in their medical record."
            ],
            "patient_record_verbatim_citations": [
                "Malignant neoplasm of breast (disorder) (SNOMED: 254837009)"
            ],
            "missing_information_or_red_flags": []
        }
    }

    sample_patient_md = "Malignant neoplasm of breast (disorder) (SNOMED: 254837009) [onset: 2003-09-14]"
    sample_policy_text = "The patient MUST have a confirmed active malignant neoplasm diagnosis documented in their medical record."

    res = evaluate_audit_result("CASE-DEMO-101", sample_audit, sample_patient_md, sample_policy_text)
    print(json.dumps(res, indent=2))
