"""
Internal Benchmark Script: Average F1-Score across all demo cases.

Runs the local AI audit for every case in src/cases.DEMO_CASES, evaluates
each result against ground truth, and prints per-case F1 plus the overall
average F1 you should paste into the app.
"""
import sys
import time

from src.audit_engine import run_audit
from src.cases import DEMO_CASES
from src.evaluator import evaluate_audit_result
from src.fhir_parser import (
    extract_patient_summary,
    format_clinical_summary_markdown,
    load_fhir_bundle,
)
from src.policies import get_policy
from src.cases import get_patient_filepath


def main():
    print("=" * 72)
    print("PRIOR AUTHORIZATION AUDIT AI - INTERNAL F1 BENCHMARK")
    print("=" * 72)

    f1_scores = []
    tier_matches = 0
    total_latency = 0.0

    for case in DEMO_CASES:
        case_id = case["id"]
        print(f"\n> Running {case_id} ({case['patient_name']} / {case['policy_id']}) ...", flush=True)

        fpath = get_patient_filepath(case)
        bundle = load_fhir_bundle(fpath)
        summary = extract_patient_summary(bundle)
        summary_md = format_clinical_summary_markdown(summary)
        policy = get_policy(case["policy_id"])
        policy_text = policy["policy_text"]

        t0 = time.time()
        audit_res = run_audit(case)
        elapsed = time.time() - t0
        total_latency += elapsed

        if audit_res["status"] != "success":
            print(f"  ERROR: {audit_res.get('error_message')}")
            f1_scores.append(0.0)
            continue

        eval_res = evaluate_audit_result(case_id, audit_res, summary_md, policy_text)
        f1 = eval_res.get("f1_score", 0.0)
        tier_ok = eval_res.get("risk_tier_match", False)
        f1_scores.append(f1)
        tier_matches += 1 if tier_ok else 0

        print(
            f"  predicted_tier={eval_res.get('predicted_risk_tier')} | "
            f"expected_tier={eval_res.get('expected_risk_tier')} | "
            f"tier_match={tier_ok} | "
            f"P={eval_res.get('precision')} R={eval_res.get('recall')} F1={f1} | "
            f"latency={elapsed:.1f}s"
        )

    if not f1_scores:
        print("\nNo results.")
        sys.exit(1)

    avg_f1 = sum(f1_scores) / len(f1_scores)
    tier_acc = tier_matches / len(DEMO_CASES)

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print(f"Cases evaluated       : {len(DEMO_CASES)}")
    print(f"Risk-tier accuracy    : {tier_matches}/{len(DEMO_CASES)}  ({tier_acc*100:.1f}%)")
    print(f"Total inference time  : {total_latency:.1f}s")
    print(f"Average F1-Score      : {avg_f1:.4f}")
    print("=" * 72)
    print(f"\nPASTE-READY VALUE: {avg_f1:.2f}")


if __name__ == "__main__":
    main()
