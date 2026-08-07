# Prior Authorization Audit AI

A local, explainable AI proof-of-concept for **Cotiviti Healthcare Topic 2: Clinical Decision Making and Pattern Recognition in Health Care**.

## What This Application Does

This system audits **Prior Authorization (PA) claims** against payer coverage policies using a locally-hosted LLM. For a given claim, it:

1. Parses a **Synthea FHIR R4** patient bundle to extract active diagnoses, medications, procedures, and vitals.
2. Retrieves the applicable **SNOMED CT-aligned coverage policy** (Oncology `CP-101`, Neurology `CP-202`, Orthopedics `CP-303`).
3. Sends the structured clinical summary + policy criteria to a local **Ollama `qwen2.5:14b`** model.
4. Returns a structured JSON verdict containing:
   - 3-tier risk classification (Low / Moderate / High)
   - Recommendation (Approve / Manual Review / Deny)
   - Step-by-step **Chain-of-Thought** clinical reasoning
   - **Verbatim citations** from both policy and patient record (grounding)
   - Missing information / clinical red flags
5. Presents a **Human-in-the-Loop (HITL)** reviewer panel for final auditor sign-off.

Everything runs locally — no PHI leaves the machine.

## Prerequisites

- macOS / Linux with Python 3.10+
- [Ollama](https://ollama.com) installed
- `qwen2.5:14b` model pulled (~9 GB), running on Apple Silicon with ≥16 GB RAM recommended

## How to Run

### 1. Start Ollama and pull the model
```bash
ollama serve
ollama pull qwen2.5:14b
```

### 2. Install Python dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Launch the Streamlit app
```bash
streamlit run app.py
```
Open `http://localhost:8501`, pick a case in the sidebar, click **Run Local AI Audit**.

### 4. (Optional) Run the F1 benchmark
```bash
python benchmark_f1.py
```

## Project Structure

- [app.py](file:///Users/siputroj/Desktop/react/prior-auth-audit/app.py) — Streamlit UI
- [src/audit_engine.py](file:///Users/siputroj/Desktop/react/prior-auth-audit/src/audit_engine.py) — Ollama prompt + JSON parsing
- [src/fhir_parser.py](file:///Users/siputroj/Desktop/react/prior-auth-audit/src/fhir_parser.py) — FHIR R4 bundle extraction
- [src/policies.py](file:///Users/siputroj/Desktop/react/prior-auth-audit/src/policies.py) — Coverage policy definitions
- [src/cases.py](file:///Users/siputroj/Desktop/react/prior-auth-audit/src/cases.py) — 10 curated demo cases
- [src/evaluator.py](file:///Users/siputroj/Desktop/react/prior-auth-audit/src/evaluator.py) — Precision / Recall / F1 vs. ground truth
- [synthea_data/](file:///Users/siputroj/Desktop/react/prior-auth-audit/synthea_data) — Synthetic FHIR patient bundles
