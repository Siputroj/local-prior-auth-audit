"""
Benchmark configuration.

The scaled F1 benchmark is fully self-contained: the 100 curated cases
live in benchmark/cases_100.json and their patient FHIR files live in
benchmark/synthea_data/. Nothing here needs to point at an external
corpus anymore.
"""
import os


BENCHMARK_DIR = os.path.dirname(os.path.abspath(__file__))

# Frozen 100-case fixture (id -> case object).
CASES_JSON_PATH = os.path.join(BENCHMARK_DIR, "cases_100.json")

# 97 patient FHIR bundles referenced by the 100 cases (some patients are
# shared across policies).
PATIENT_DIR = os.path.join(BENCHMARK_DIR, "synthea_data")

# Output directory for CSV / summary artifacts.
RESULTS_DIR = os.path.join(BENCHMARK_DIR, "results")
