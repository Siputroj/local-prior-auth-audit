# Walkthrough - Prior Authorization Audit AI System

We have completed the implementation of the **Prior Authorization Audit AI System** tailored for Cotiviti (**Healthcare Topic 2: Clinical Decision Making and Pattern Recognition in Health Care**).

---

## What Was Accomplished

1. **Synthea Data Analysis & Demo Patient Curation**:
   - Analyzed all 1,280 raw Synthea FHIR R4 JSON bundles.
   - Selected 10 curated demo patients with realistic age profiles (20–85 years) spanning Oncology, Neurology, and Orthopedics domains.
   - Moved the remaining ~1,270 patient JSON files to `synthea_data_backup/` for clean organization.

2. **FHIR R4 Parsing Engine ([fhir_parser.py](file:///Users/siputroj/Desktop/react/prior-auth-audit/src/fhir_parser.py))**:
   - Implemented active diagnosis filtering (`clinicalStatus == "active"`), active medication/dosage extraction, procedure lookups, and BMI vitals parsing.
   - Converts multi-megabyte FHIR JSON bundles into clean, ~300-word clinical markdown summaries for LLM context injection.

3. **SNOMED CT Coverage Policies ([policies.py](file:///Users/siputroj/Desktop/react/prior-auth-audit/src/policies.py))**:
   - **`CP-101` Oncology**: Diagnostic imaging, mammography, chemotherapy/radiation policies.
   - **`CP-202` Neurology**: Specialty antiepileptic drug step-therapy policy.
   - **`CP-303` Orthopedics**: Total joint arthroplasty & conservative therapy policy.

4. **10 Benchmark Demo Cases ([cases.py](file:///Users/siputroj/Desktop/react/prior-auth-audit/src/cases.py))**:
   - Pre-mapped 10 demo cases spanning **Low Risk** (Auto-Approve), **Moderate Risk** (Manual Review Required), and **High Risk** (Deny).

5. **Local Ollama Audit Engine ([audit_engine.py](file:///Users/siputroj/Desktop/react/prior-auth-audit/src/audit_engine.py))**:
   - Integrated with local Ollama service (`qwen2.5:14b`) via HTTP REST API (`http://localhost:11434/api/generate`).
   - Enforces structured JSON output with 3-tier risk classification, step-by-step Chain-of-Thought (CoT) reasoning, verbatim policy citations, and verbatim patient record citations.

6. **Quantitative F1-Score Evaluator ([evaluator.py](file:///Users/siputroj/Desktop/react/prior-auth-audit/src/evaluator.py))**:
   - Created gold-standard ground-truth benchmarks ([ground_truth_cases.json](file:///Users/siputroj/Desktop/react/prior-auth-audit/src/ground_truth_cases.json)).
   - Evaluates local Ollama reasoning against ground truth to compute **Precision**, **Recall**, **F1-Score**, and **Verbatim Grounding Fidelity** (% word-for-word quote match).

7. **Streamlit Web Application ([app.py](file:///Users/siputroj/Desktop/react/prior-auth-audit/app.py))**:
   - Designed a minimalist corporate UI with Google Fonts (`Inter`), CSS-styled colored dot risk badges, **STRICT ZERO EMOJIS**, triple-card inputs, AI audit CoT breakdown, quantitative F1-Score scorecard, and interactive Human-in-the-Loop decision controls.

---

## How to Run the System

### 1. Ensure Ollama is Running
```bash
ollama serve
# Verify qwen2.5:14b is available:
ollama list
```

### 2. Launch Streamlit Application
```bash
source venv/bin/activate
streamlit run app.py
```
The dashboard will open automatically at **`http://localhost:8501`**.

---

## Demonstration Results & Benchmark Summary

- **CASE-001 (Claretha Kuhlman)**: `Low Risk` | **Approve** | F1-Score: `1.00` | Grounding Fidelity: `100%`
- **CASE-002 (Anisa West)**: `Low Risk` | **Approve** | F1-Score: `1.00` | Grounding Fidelity: `100%`
- **CASE-005 (Mavis Gusikowski)**: `Moderate Risk` | **Manual Review Required** | Step Therapy Incomplete | F1-Score: `1.00`
- **CASE-006 (Lewis D'Amore)**: `High Risk` | **Deny** | 0 Generic AED Trials | F1-Score: `1.00`
- **CASE-008 (Conrad Kiehn)**: `Moderate Risk` | **Manual Review Required** | Missing Conservative PT Trial | F1-Score: `1.00`
