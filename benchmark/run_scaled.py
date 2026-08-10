"""
Scaled F1 benchmark runner.

Reads the frozen 100-case fixture (benchmark/cases_100.json) whose patient
FHIR bundles live in benchmark/synthea_data/. For each case, this script:
    1. Loads the patient bundle and formats the clinical summary
    2. Calls the local Ollama LLM audit
    3. Parses predicted risk tier, JSON validity, verbatim citations
    4. Computes grounding fidelity against source text
    5. Compares against the deterministic rule-based ground truth
    6. Writes per-case CSV rows and an aggregate summary (JSON + TXT)

Resumable: with --resume, previously-completed case IDs are skipped based
on the existing benchmark_results.csv.

Usage:
    python -m benchmark.run_scaled                    # full 100-case run
    python -m benchmark.run_scaled --limit 10         # smoke test
    python -m benchmark.run_scaled --resume           # continue after crash
"""
import argparse
import csv
import json
import os
import sys
import time
from typing import Dict, List

# Allow running as a script (python benchmark/run_scaled.py) too.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

from benchmark.config import CASES_JSON_PATH, PATIENT_DIR, RESULTS_DIR
from benchmark.metrics import format_summary_text, summarize
from src.audit_engine import (
    DEFAULT_MODEL,
    OLLAMA_API_URL,
    SYSTEM_PROMPT,
    _clean_and_parse_json,
    build_audit_prompt,
    warm_up_model,
)
from src.evaluator import _sub_quote_match
from src.fhir_parser import (
    extract_patient_summary,
    format_clinical_summary_markdown,
    load_fhir_bundle,
)
from src.policies import get_policy_text


RESULTS_CSV_NAME = "benchmark_results.csv"
SUMMARY_JSON_NAME = "benchmark_summary.json"
SUMMARY_TXT_NAME = "benchmark_summary.txt"

CSV_COLUMNS = [
    "case_id",
    "policy_id",
    "patient_file",
    "patient_name",
    "expected_tier",
    "predicted_tier",
    "tier_match",
    "json_valid",
    "grounding_fidelity",
    "n_policy_quotes",
    "n_patient_quotes",
    "latency_seconds",
    "rule_rationale",
    "error",
]


def load_cases() -> List[dict]:
    with open(CASES_JSON_PATH, "r") as f:
        return json.load(f)


def _run_single_audit(case: dict, model: str, timeout: int) -> Dict:
    """Run one LLM audit, resolving the patient file from benchmark/synthea_data/."""
    fpath = os.path.join(PATIENT_DIR, case["patient_file"])
    if not os.path.exists(fpath):
        return {"status": "error", "error_message": f"missing: {fpath}", "latency_seconds": 0}

    bundle = load_fhir_bundle(fpath)
    summary = extract_patient_summary(bundle)
    patient_summary_md = format_clinical_summary_markdown(summary)

    policy_text = get_policy_text(case["policy_id"])
    if not policy_text:
        return {
            "status": "error",
            "error_message": f"policy not found: {case['policy_id']}",
            "latency_seconds": 0,
        }

    prompt = build_audit_prompt(case, patient_summary_md, policy_text)

    payload = {
        "model": model,
        "system": SYSTEM_PROMPT,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "keep_alive": "30m",
        "options": {"temperature": 0.1, "top_p": 0.9, "num_predict": 450, "num_ctx": 4096},
    }

    t0 = time.time()
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=timeout)
        latency = round(time.time() - t0, 2)
        if response.status_code != 200:
            return {
                "status": "error",
                "error_message": f"HTTP {response.status_code}: {response.text[:200]}",
                "latency_seconds": latency,
            }
        raw = response.json().get("response", "")
        return {
            "status": "success",
            "parsed_json": _clean_and_parse_json(raw),
            "latency_seconds": latency,
            "patient_summary_md": patient_summary_md,
            "policy_text": policy_text,
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e)[:200],
            "latency_seconds": round(time.time() - t0, 2),
        }


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


def _grounding_fidelity(parsed: dict, patient_md: str, policy_text: str) -> float:
    policy_quotes = parsed.get("policy_verbatim_citations", []) or []
    patient_quotes = parsed.get("patient_record_verbatim_citations", []) or []
    checks = []
    for q in policy_quotes:
        s_q = _to_str(q)
        if s_q:
            checks.append(_sub_quote_match(s_q, policy_text))
    for q in patient_quotes:
        s_q = _to_str(q)
        if s_q:
            checks.append(_sub_quote_match(s_q, patient_md))
    if not checks:
        return 1.0
    return round(sum(1 for x in checks if x) / len(checks), 4)


def _load_completed_ids(csv_path: str) -> set:
    if not os.path.exists(csv_path):
        return set()
    completed = set()
    with open(csv_path, "r", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("case_id") and not row.get("error"):
                completed.add(row["case_id"])
    return completed


def _row_from_result(case: dict, audit: dict) -> dict:
    expected = case["expected_risk_tier"]
    row = {
        "case_id": case["id"],
        "policy_id": case["policy_id"],
        "patient_file": case["patient_file"],
        "patient_name": case["patient_name"],
        "expected_tier": expected,
        "predicted_tier": "",
        "tier_match": False,
        "json_valid": False,
        "grounding_fidelity": "",
        "n_policy_quotes": 0,
        "n_patient_quotes": 0,
        "latency_seconds": audit.get("latency_seconds", 0),
        "rule_rationale": case.get("rule_rationale", ""),
        "error": "",
    }
    if audit.get("status") != "success":
        row["error"] = audit.get("error_message", "")
        return row

    parsed = audit.get("parsed_json") or {}
    predicted = str(parsed.get("risk_tier", "")).strip()
    row["predicted_tier"] = predicted
    row["json_valid"] = predicted in {"Low Risk", "Moderate Risk", "High Risk"}
    row["tier_match"] = predicted == expected
    row["n_policy_quotes"] = len(parsed.get("policy_verbatim_citations", []) or [])
    row["n_patient_quotes"] = len(parsed.get("patient_record_verbatim_citations", []) or [])
    row["grounding_fidelity"] = _grounding_fidelity(
        parsed, audit.get("patient_summary_md", ""), audit.get("policy_text", "")
    )
    return row


def _rows_for_summary(csv_path: str) -> List[dict]:
    rows = []
    with open(csv_path, "r", newline="") as f:
        for r in csv.DictReader(f):
            gf = r.get("grounding_fidelity", "")
            rows.append(
                {
                    "expected_tier": r["expected_tier"],
                    "predicted_tier": r["predicted_tier"] or None,
                    "json_valid": r["json_valid"] == "True",
                    "latency_seconds": float(r["latency_seconds"] or 0.0),
                    "grounding_fidelity": float(gf) if gf else None,
                }
            )
    return rows


def main():
    parser = argparse.ArgumentParser(description="Scaled F1 benchmark runner.")
    parser.add_argument("--limit", type=int, default=100, help="Number of cases to run.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model.")
    parser.add_argument("--timeout", type=int, default=600, help="Per-request timeout seconds.")
    parser.add_argument("--output", default=RESULTS_DIR, help="Output directory.")
    parser.add_argument("--resume", action="store_true", help="Skip case IDs already in CSV.")
    parser.add_argument("--no-warmup", action="store_true", help="Skip model warm-up.")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    csv_path = os.path.join(args.output, RESULTS_CSV_NAME)
    summary_json_path = os.path.join(args.output, SUMMARY_JSON_NAME)
    summary_txt_path = os.path.join(args.output, SUMMARY_TXT_NAME)

    cases = load_cases()[: args.limit]
    print(f"Model      : {args.model}")
    print(f"Cases      : {len(cases)} (from {CASES_JSON_PATH})")
    print(f"Patient dir: {PATIENT_DIR}")
    print(f"Output dir : {args.output}")

    completed = _load_completed_ids(csv_path) if args.resume else set()
    if completed:
        print(f"Resume: {len(completed)} cases already completed - skipping.")

    write_header = not os.path.exists(csv_path) or (not args.resume)
    mode = "a" if (args.resume and os.path.exists(csv_path)) else "w"
    csv_file = open(csv_path, mode, newline="")
    writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
    if write_header:
        writer.writeheader()
        csv_file.flush()

    if not args.no_warmup:
        print("\nWarming up model...")
        wu = warm_up_model(model=args.model)
        print(f"  warm-up: {wu.get('status')} in {wu.get('latency_seconds', 0)}s")

    print(f"\nRunning {len([c for c in cases if c['id'] not in completed])} cases...\n")
    for idx, case in enumerate(cases, 1):
        if case["id"] in completed:
            continue
        print(
            f"[{idx}/{len(cases)}] {case['id']} {case['policy_id']} "
            f"expected={case['expected_risk_tier']:14s} ...",
            end="",
            flush=True,
        )
        audit = _run_single_audit(case, model=args.model, timeout=args.timeout)
        row = _row_from_result(case, audit)
        writer.writerow(row)
        csv_file.flush()
        mark = "OK " if row["tier_match"] else "MISS"
        print(
            f" pred={row['predicted_tier'] or 'ERR':14s} [{mark}] "
            f"gf={row['grounding_fidelity']} lat={row['latency_seconds']}s"
            + (f"  err={row['error'][:60]}" if row["error"] else "")
        )

    csv_file.close()

    print("\nAggregating metrics...")
    summary = summarize(_rows_for_summary(csv_path))
    with open(summary_json_path, "w") as f:
        json.dump(summary, f, indent=2)
    text = format_summary_text(summary)
    with open(summary_txt_path, "w") as f:
        f.write(text + "\n")

    print("\n" + text)
    print(f"\nCSV     : {csv_path}")
    print(f"Summary : {summary_txt_path}")
    print(f"JSON    : {summary_json_path}")


if __name__ == "__main__":
    main()
