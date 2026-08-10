"""
Metrics for the scaled benchmark.

Computes:
    - Multi-class macro-F1 over risk tiers (Low / Moderate / High)
    - Per-tier precision / recall / F1
    - Overall tier accuracy
    - Confusion matrix (expected vs predicted)
    - Grounding fidelity aggregate (from src.evaluator._sub_quote_match)
    - JSON validity rate
    - Latency percentiles (p50, p95)

No sklearn dependency - metrics are computed from scratch to keep the
project dependency footprint tight.
"""
from statistics import median
from typing import Dict, List

TIERS = ["Low Risk", "Moderate Risk", "High Risk"]


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_v) - 1)
    if f == c:
        return sorted_v[f]
    return sorted_v[f] + (sorted_v[c] - sorted_v[f]) * (k - f)


def _tier_prf(y_true: List[str], y_pred: List[str], tier: str) -> Dict[str, float]:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == tier and p == tier)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t != tier and p == tier)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == tier and p != tier)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "support": tp + fn,
    }


def _confusion_matrix(y_true: List[str], y_pred: List[str]) -> Dict[str, Dict[str, int]]:
    cm = {t: {p: 0 for p in TIERS + ["Invalid"]} for t in TIERS}
    for t, p in zip(y_true, y_pred):
        if t not in cm:
            continue
        col = p if p in TIERS else "Invalid"
        cm[t][col] += 1
    return cm


def summarize(rows: List[dict]) -> Dict:
    """
    rows: each row must contain
        expected_tier, predicted_tier (or None if invalid),
        json_valid (bool), latency_seconds (float),
        grounding_fidelity (float in [0,1] or None)
    """
    y_true, y_pred = [], []
    latencies, gfs = [], []
    json_valid_count = 0

    for r in rows:
        y_true.append(r["expected_tier"])
        y_pred.append(r.get("predicted_tier") or "Invalid")
        if r.get("json_valid"):
            json_valid_count += 1
        latencies.append(float(r.get("latency_seconds") or 0.0))
        gf = r.get("grounding_fidelity")
        if gf is not None:
            gfs.append(float(gf))

    per_tier = {t: _tier_prf(y_true, y_pred, t) for t in TIERS}
    macro_f1 = round(sum(per_tier[t]["f1"] for t in TIERS) / len(TIERS), 4)

    tier_matches = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    accuracy = round(tier_matches / len(rows), 4) if rows else 0.0

    return {
        "n_cases": len(rows),
        "json_validity_rate": round(json_valid_count / len(rows), 4) if rows else 0.0,
        "tier_accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_tier": per_tier,
        "confusion_matrix": _confusion_matrix(y_true, y_pred),
        "grounding_fidelity_mean": round(sum(gfs) / len(gfs), 4) if gfs else None,
        "latency": {
            "p50": round(median(latencies), 2) if latencies else 0.0,
            "p95": round(_percentile(latencies, 0.95), 2),
            "mean": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
            "total_seconds": round(sum(latencies), 2),
        },
    }


def format_summary_text(summary: Dict) -> str:
    """Return a paste-ready plain-text summary block."""
    lines = []
    lines.append("=" * 72)
    lines.append(f"SCALED F1 BENCHMARK - {summary['n_cases']} CASES")
    lines.append("=" * 72)
    lines.append(f"JSON validity rate      : {summary['json_validity_rate'] * 100:.1f}%")
    lines.append(f"Tier accuracy           : {summary['tier_accuracy'] * 100:.1f}%")
    lines.append(f"Macro-F1 (3 tiers)      : {summary['macro_f1']:.4f}")
    if summary.get("grounding_fidelity_mean") is not None:
        lines.append(
            f"Grounding fidelity mean : {summary['grounding_fidelity_mean'] * 100:.1f}%"
        )
    lat = summary["latency"]
    lines.append(
        f"Latency (s)             : p50={lat['p50']}  p95={lat['p95']}  "
        f"mean={lat['mean']}  total={lat['total_seconds']}"
    )
    lines.append("")
    lines.append("Per-tier metrics:")
    for tier in TIERS:
        m = summary["per_tier"][tier]
        lines.append(
            f"  {tier:14s}  P={m['precision']:.3f}  R={m['recall']:.3f}  "
            f"F1={m['f1']:.3f}  support={m['support']}"
        )
    lines.append("")
    lines.append("Confusion matrix (rows=expected, cols=predicted):")
    cm = summary["confusion_matrix"]
    header = "                 " + "  ".join(f"{t[:8]:>8}" for t in TIERS + ["Invalid"])
    lines.append(header)
    for t in TIERS:
        row_vals = "  ".join(f"{cm[t][p]:>8d}" for p in TIERS + ["Invalid"])
        lines.append(f"  {t:14s}  {row_vals}")
    lines.append("=" * 72)
    return "\n".join(lines)
