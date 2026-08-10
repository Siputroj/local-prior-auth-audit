"""
Benchmark package: scaled F1 evaluation of the local LLM Prior Auth auditor.

Cleanly separated from the `src/` package used by the Streamlit demo. The
demo ships with 3 curated patients (one per policy, one per risk tier);
this benchmark ships with 100 curated cases drawn from 97 Synthea
patients living in `benchmark/synthea_data/`.

Modules:
    benchmark.config         Paths to cases_100.json, synthea_data/, results/
    benchmark.policy_rules   Deterministic rule engine that generated the
                             expected_risk_tier labels in cases_100.json.
                             Kept for auditability; not called at run time.
    benchmark.metrics        Multi-class macro-F1, per-tier P/R/F1, confusion
                             matrix, grounding fidelity, latency percentiles.
    benchmark.run_scaled     CLI entrypoint - runs the LLM against every case
                             and writes benchmark_results.csv + summary.

Data:
    benchmark/cases_100.json     Frozen 100-case fixture (33/33/34 split)
    benchmark/synthea_data/      97 FHIR bundles referenced by the fixture
    benchmark/results/           Runtime CSV/JSON/TXT outputs (gitignored)

Usage:
    python -m benchmark.run_scaled                    # full run
    python -m benchmark.run_scaled --limit 10         # smoke test
    python -m benchmark.run_scaled --resume           # continue after crash
"""
