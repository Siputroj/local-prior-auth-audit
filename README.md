# Local Prior Authorization Audit AI (`local-prior-auth-audit`)

An explainable, privacy-preserving local AI system built for **Cotiviti Healthcare Topic 2: Clinical Decision Making and Pattern Recognition in Health Care**.

---

## Overview

This application automates and audits **Prior Authorization (PA) claims** against health plan coverage policies using a locally deployed Large Language Model (LLM).

### Workflow & Core Capabilities
1. **FHIR R4 Parsing**: Extracts patient medical history (diagnoses, SNOMED codes, medications, procedures, vitals) from Synthea FHIR bundles.
2. **Policy Matching**: Evaluates requests against structured coverage policies:
   - **CP-101**: Oncology (Chemotherapy / Diagnostic Imaging)
   - **CP-202**: Neurology (Antiepileptic Step Therapy)
   - **CP-303**: Orthopedics (Joint Replacement & Conservative Therapy)
3. **Local LLM Audit Engine**: Formulates structured prompts for a local **Ollama (`qwen2.5:7b`)** model to generate:
   - **3-Tier Risk Classification**: `Low Risk` (Approve), `Moderate Risk` (Manual Review), `High Risk` (Deny)
   - **Step-by-Step Chain-of-Thought (CoT)** clinical reasoning
   - **Verbatim Evidence Citations** from policy and medical records for full grounding and explainability
   - **Red Flag & Contraindication Detection** (e.g. cardiac clearance requirements)
4. **Human-in-the-Loop (HITL) Dashboard**: Streamlit interface allowing medical auditors to review recommendations, inspect CoT reasoning, check verbatim citations, and issue final sign-offs.

---

## Deliverables Included

- **`app.py` & `src/`**: Streamlit interactive demo dashboard.
- **`benchmark/`**: Scaled 100-case evaluation harness measuring macro-F1, grounding fidelity, and latency.
- **`paper_submission.docx`**: 2-page research report (+ bibliography) on *The Strategic Imperative of Local AI Deployment in Healthcare Operations*.

---

## Prerequisites

- **OS**: macOS or Linux
- **Python**: 3.10+
- **RAM**: 16 GB+ recommended (Apple Silicon M-series or GPU machine recommended for optimal inference speed)
- **Ollama**: Local LLM engine

---

## Step-by-Step Setup Guide

### 1. Install & Configure Ollama

1. Download and install Ollama from [ollama.com](https://ollama.com).
2. Start the local Ollama service:
   ```bash
   ollama serve
   ```
3. In a separate terminal window, pull the required model (`qwen2.5:7b`):
   ```bash
   ollama pull qwen2.5:7b
   ```
4. Verify Ollama is running by accessing `http://localhost:11434` or testing via CLI:
   ```bash
   ollama run qwen2.5:7b "Hello"
   ```

---

### 2. Set Up Python Virtual Environment

```bash
# Clone or navigate into the repository
cd local-prior-auth-audit

# Create python virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS / Linux:
source venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
```

---

## Running the Application

### Option A: Streamlit Interactive Web App (Demo Cases)

Launch the interactive dashboard to evaluate prior authorization claims in real-time with local CoT reasoning:

```bash
streamlit run app.py
```

Once running, open `http://localhost:8501` in your browser.

**Included Demo Cases**:
| Case ID | Policy | Patient | Expected Classification |
| :--- | :--- | :--- | :--- |
| `CASE-DEMO-101` | CP-101 Oncology | Claretha Kuhlman | **Low Risk** (Approve) |
| `CASE-DEMO-202` | CP-202 Neurology | Lewis D'Amore | **High Risk** (Deny) |
| `CASE-DEMO-303` | CP-303 Orthopedics | Lorita Kautzer | **Moderate Risk** (Manual Review) |

**Demo Case Explanations:**
- **CASE-DEMO-101 (Low Risk)**: This case is classified as **Low Risk** because the patient has a confirmed, active diagnosis of Malignant neoplasm of breast (SNOMED: 254837009) and a documented history of mammography procedures, fully satisfying the mandatory clinical criteria of CP-101 without any contraindications.
- **CASE-DEMO-202 (High Risk)**: This case is classified as **High Risk** because although the patient has an active seizure disorder diagnosis, they have exactly 0 valid first-line generic AEDs (antiepileptic drugs) in their medication history. This is a complete failure of the CP-202 step-therapy requirement, triggering an automatic denial recommendation.
- **CASE-DEMO-303 (Moderate Risk)**: This case is classified as **Moderate Risk** because while the patient meets the criteria for total knee replacement (Osteoarthritis of knee), they also have a history of Congestive heart failure (SNOMED: 88805009). This presents a significant surgical risk and requires explicit cardiology clearance, mandating a human-in-the-loop manual review.

---

### Option B: Scaled Benchmark (100 Cases)

Evaluate macro-F1, per-tier precision/recall, and latency across 100 Synthea FHIR patient cases:

```bash
# Smoke test (2 cases)
python -m benchmark.run_scaled --limit 2

# Full benchmark run (100 cases)
python -m benchmark.run_scaled

# Resume interrupted run
python -m benchmark.run_scaled --resume
```

Benchmark output files will land in `benchmark/results/`:
- `benchmark_results.csv`: Row-by-row audit logs.
- `benchmark_summary.json`: Macro-F1, confusion matrix, precision/recall, and latency metrics.

---

## Project Structure

```
local-prior-auth-audit/
├── app.py                     # Streamlit web dashboard entrypoint
├── requirements.txt           # Dependency requirements (streamlit, requests, python-docx)
├── paper_submission.docx      # Submitted research report on Local AI Deployment
├── generate_paper.py          # Script used to generate the DOCX research paper
├── src/                       # Application core package
│   ├── audit_engine.py        # Ollama API client, system prompt, CoT & JSON parser
│   ├── cases.py               # Demo case loader
│   ├── evaluator.py           # Single-case audit evaluator & metric builder
│   ├── fhir_parser.py         # Synthea FHIR R4 parser & markdown formatter
│   ├── ground_truth_cases.json# Gold-standard case labels
│   ├── policies.py            # Clinical coverage policies (CP-101, CP-202, CP-303)
│   └── synthea_data/          # Demo FHIR bundles
└── benchmark/                 # Scaled benchmark evaluation harness
    ├── cases_100.json         # 100-case evaluation dataset
    ├── config.py              # Path configurations
    ├── metrics.py             # Macro-F1 & precision/recall metric computer
    ├── policy_rules.py        # Deterministic reference rules
    ├── run_scaled.py          # CLI runner for 100-case evaluation
    ├── synthea_data/          # FHIR patient bundles for benchmark
    └── results/               # Generated benchmark outputs (gitignored)
```
