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

### 3. Configure Local Environment (`.env`)

You can easily configure which Ollama model and endpoint the system uses without changing any code. Create or edit the `.env` file in the root directory:

```bash
# Copy example configuration file
cp .env.example .env
```

Inside `.env`, adjust the variables as needed:
```env
# Specify your local Ollama model (e.g. qwen2.5:7b, qwen2.5:14b, llama3:8b)
OLLAMA_MODEL=qwen2.5:7b

# Specify your local Ollama REST API endpoint
OLLAMA_API_URL=http://localhost:11434/api/generate
```

The Streamlit UI dashboard, benchmark harness, and audit engine automatically load your selected model from `.env` and display the active model label dynamically across the application interface.

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
| `CASE-DEMO-001` | CP-101 Oncology | Claretha Kuhlman | **Low Risk** (Approve) |
| `CASE-DEMO-002` | CP-202 Neurology | Mavis Gusikowski | **Moderate Risk** (Manual Review) |
| `CASE-DEMO-003` | CP-202 Neurology | Lewis D'Amore | **High Risk** (Deny) |

**Demo Case Explanations:**
- **CASE-DEMO-001 (Low Risk)**: Patient has a confirmed active Malignant neoplasm of breast (SNOMED: 254837009) with extensive mammography history. All CP-101 criteria are fully met.
- **CASE-DEMO-002 (Moderate Risk)**: Patient has active Epilepsy and Seizure disorder, but only 1 valid first-line AED (Carbamazepine/Tegretol) on record. Per CP-202 Section 3.3, having only 1 AED trial when 2 are required triggers mandatory Manual Review.
- **CASE-DEMO-003 (High Risk)**: Patient has active Epilepsy and Seizure disorder, but has exactly 0 valid first-line AEDs in their medication history (all meds are non-AED: Donepezil, Memantine, Simvastatin). Per CP-202 Section 3.4, zero prior AED trials is a HIGH RISK of policy non-compliance → Deny.

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
    ├── ground_truth.json      # 100-case expert ground-truth dataset
    ├── config.py              # Path configurations
    ├── metrics.py             # Macro-F1 & precision/recall metric computer
    ├── run_scaled.py          # CLI runner for 100-case evaluation
    ├── synthea_data/          # FHIR patient bundles for benchmark
    └── results/               # Generated benchmark outputs (gitignored)
```
