# Complete Technical Interview Study Guide & Architecture Review
## Local Prior Authorization Audit AI (`local-prior-auth-audit`)

**Candidate / Author**: Jason Siputro  
**Topic**: Clinical Decision Making and Pattern Recognition in Health Care (Cotiviti Topic 2)  
**Core Technologies**: Python 3.10+, Streamlit, Ollama (`qwen2.5:7b`), HL7 FHIR R4, SNOMED CT, RxNorm, Synthea Synthetic Records.

---

## Table of Contents
1. [Executive Summary & The "Elevator Pitch"](#1-executive-summary--the-elevator-pitch)
2. [High-Level Systems Design & Architecture](#2-high-level-systems-design--architecture)
3. [AI & Engineering Design Patterns Used](#3-ai--engineering-design-patterns-used)
4. [Comprehensive File-by-File Breakdown](#4-comprehensive-file-by-file-breakdown)
5. [Clinical Coverage Policies & Clinical Logic](#5-clinical-coverage-policies--clinical-logic)
6. [Benchmarking, Metrics & Evaluation Deep Dive](#6-benchmarking-metrics--evaluation-deep-dive)
7. [Anticipated Interview Questions & Strong Technical Answers](#7-anticipated-interview-questions--strong-technical-answers)

---

## 1. Executive Summary & The "Elevator Pitch"

### What is this project?
An explainable, privacy-preserving, local AI prior authorization (PA) auditing system. It automatically evaluates healthcare claims against structured health plan coverage policies and patient electronic medical records (EMRs) in HL7 FHIR R4 format, using an on-premises/local Large Language Model (`qwen2.5:7b` served via Ollama).

### What core problems does it solve?
1. **Privacy & HIPAA Compliance**: Commercial cloud LLM APIs (OpenAI, Anthropic) pose significant compliance and data-governance concerns when sending Protected Health Information (PHI). By running fully local with Ollama, zero patient data ever leaves the secure perimeter.
2. **Hallucination & Black-Box Decisions**: Medical decisions cannot rely on black-box outputs. The system enforces structured JSON outputs, 4-tier Chain-of-Thought (CoT) clinical reasoning, and verbatim evidence citations anchored in both the policy document and the patient's FHIR record.
3. **Clinical Safety via Human-in-the-Loop (HITL)**: Rather than fully autonomous adjudication, the system acts as an expert copilot. It classifies claims into a 3-tier risk matrix (**Low Risk** / Approve, **Moderate Risk** / Manual Review Required, **High Risk** / Deny) and provides an interactive auditor dashboard for human review and sign-off.
4. **Rigorous Empirical Evaluation**: Includes both single-case gold-standard verification and a scaled 100-case benchmark evaluating multi-class Macro-F1, grounding fidelity, JSON validity, and latency percentiles.

---

## 2. High-Level Systems Design & Architecture

```
                                +---------------------------+
                                |  Synthea FHIR R4 Bundles  |
                                |      (Patient JSON)       |
                                +-------------+-------------+
                                              |
                                              v
                                +---------------------------+
                                |      src/fhir_parser.py   |
                                |  - SNOMED Diagnoses       |
                                |  - RxNorm Medications     |
                                |  - Procedures & BMI       |
                                +-------------+-------------+
                                              |
                                              v
+-----------------------+       +---------------------------+       +--------------------------+
| Prior Auth Claim JSON | ----> |    src/audit_engine.py    | <---- |    src/policies.py       |
| (Procedure, Provider) |       |  (Prompt Builder & Model) |       | (CP-101, CP-202, CP-303) |
+-----------------------+       +-------------+-------------+       +--------------------------+
                                              |
                                              | HTTP REST (127.0.0.1:11434)
                                              v
                                +---------------------------+
                                |  Local Ollama Engine      |
                                |  Model: qwen2.5:7b        |
                                |  Format: strict JSON      |
                                +-------------+-------------+
                                              |
                                              v
                                +---------------------------+
                                |  JSON Normalizer & Guard  |
                                |  - Safe extraction        |
                                |  - Tier normalization     |
                                +-------------+-------------+
                                              |
                       +----------------------+----------------------+
                       |                                             |
                       v                                             v
        +-----------------------------+               +-----------------------------+
        |         app.py              |               |     benchmark/run_scaled.py |
        |  Streamlit HITL Dashboard   |               |  100-Case Scaled F1 Engine  |
        |  - Input Cards (Claim/FHIR) |               |  - Macro-F1 & Per-tier PRF  |
        |  - Risk Tier & Latency      |               |  - Confusion Matrix         |
        |  - 4-Step CoT Reasoner      |               |  - Grounding Fidelity Mean  |
        |  - Verbatim Citations       |               |  - Latency p50/p95          |
        |  - Auditor Action & Notes   |               +-----------------------------+
        +-----------------------------+
```

### Data Pipeline Flow:
1. **Input Ingestion**: FHIR R4 JSON bundle for the patient is read from disk.
2. **Deterministic Context Distillation**: `fhir_parser.py` parses raw FHIR resources (`Patient`, `Condition`, `MedicationRequest`, `Procedure`, `Observation`), filters out active vs. resolved states, deduplicates medications, and formats a token-efficient clinical Markdown summary (~300–500 tokens from a raw 100k+ token bundle).
3. **Structured Prompt Synthesis**: `audit_engine.py` constructs a system prompt with specialized policy clinical guidelines and a user prompt containing the claim, the policy text, and the parsed clinical summary.
4. **Local LLM Inference**: Sends payload to Ollama (`http://localhost:11434/api/generate`) with `format: "json"`, `temperature: 0.1`, `top_p: 0.9`, and `keep_alive: "30m"`.
5. **Defensive Parsing & Fallbacks**: The response is parsed with regex and `json.loads`. If JSON decoding fails or alternative key formats are generated, `_clean_and_parse_json` and `_normalize_parsed_json` safely normalize the output into standard fields.
6. **HITL Adjudication / Automated Benchmarking**: The output populates the Streamlit reviewer dashboard or feeds the 100-case evaluation harness.

---

## 3. AI & Engineering Design Patterns Used

### 1. Privacy-Preserving On-Premises Inference Pattern
- **Why**: Zero PHI egress. Composes standard REST payloads to a local Ollama daemon.
- **Optimization**: Uses `keep_alive: "30m"` and a dedicated warm-up call (`warm_up_model()`) to ensure model weights remain resident in GPU/VRAM or RAM, eliminating cold-start latencies of 15–30s on first request.

### 2. Clinical Context Distillation (Deterministic Pre-RAG / Token Minimizer)
- Rather than feeding the entire multi-megabyte FHIR bundle or using probabilistic vector search (which can drop subtle temporal medication lines), the system uses a **deterministic Python parser** to distill the bundle into clinical sections:
  - Active diagnoses with SNOMED CT codes and onset dates.
  - Active medications vs. stopped medications (critical for step therapy trials).
  - Recent procedures with SNOMED codes.
  - Vitals / Observations (BMI, Blood Pressure).
- This guarantees **100% recall of structured medical facts** within the LLM context window without chunking loss.

### 3. Chain-of-Thought (CoT) Clinical Decomposition
- Prompting instructs the LLM to output a 4-step sequence in `chain_of_thought`:
  - `Step 1`: Diagnosis Verification (confirmed active diagnosis & SNOMED check).
  - `Step 2`: Diagnostic Procedure History (pathology, imaging, surgery).
  - `Step 3`: Medication & Step Therapy (trial count, durations, generic vs. specialty).
  - `Step 4`: Contraindications & Red Flags (e.g., cardiac risk on chemo initiation, BMI >= 40).
- Forces the LLM to generate reasoned intermediate tokens before settling on the risk tier classification, significantly reducing hallucinations.

### 4. Citation-Anchored Generation & Verbatim Grounding
- The LLM is required to output two citation arrays:
  - `policy_verbatim_citations`: Exact substrings from the coverage policy.
  - `patient_record_verbatim_citations`: Exact substrings from the patient FHIR summary.
- The system verifies these quotes using an automated substring and n-gram search (`_sub_quote_match` in `benchmark/evaluator.py`), producing an objective **Grounding Fidelity** score (0.0 to 1.0).

### 5. Defensive Structured Output & Normalization Layer
- Small local models (7B) occasionally wrap JSON in markdown blocks (` ```json ... ``` `), use synonymous keys (`reasoning` vs. `chain_of_thought`), or output nested structures.
- The parser implements a 3-tier safety net:
  1. Regex block extraction.
  2. Direct `json.loads`.
  3. First/last brace boundary slicer.
  4. Synonym key normalization (`_normalize_parsed_json`).
  5. Fallback object that gracefully defaults to "Moderate Risk" (Manual Review) if complete failure occurs, ensuring clinical safety.

### 6. Human-in-the-Loop (HITL) Triaging
- The AI never executes the final approval or denial in a clinical silo.
- Low Risk claims can be fast-tracked; Moderate and High Risk claims require human auditor action.
- Streamlit provides an interactive Reviewer Panel supporting `Approve`, `Deny`, and `Request More Info` with audit log timestamps and notes.

---

## 4. Comprehensive File-by-File Breakdown

### Root Directory
| File | Role & Functionality |
| :--- | :--- |
| `app.py` | **Streamlit HITL Auditor Dashboard**. Implements clean corporate styling (zero emojis, Inter typography). Displays 3 input cards (Claim, Patient History, Policy), triggers local Ollama audit, renders CoT expander, verbatim citation boxes, self-reported confidence gauge, and the HITL Reviewer action panel. |
| `requirements.txt` | Minimalist dependencies: `streamlit==1.45.1`, `requests>=2.31.0`. Keeps deployment lightweight and dependency conflict-free. |
| `README.md` | Complete setup guide, prerequisites, Ollama instructions, policy summaries, and demo case specifications. |
| `.env` / `.env.example` | Environment configurations: `OLLAMA_MODEL=qwen2.5:7b`, `OLLAMA_API_URL=http://localhost:11434/api/generate`. |

---

### `src/` Directory (Core Application Logic)

#### 1. `src/fhir_parser.py`
- **Purpose**: Ingestion and distillation of HL7 FHIR R4 JSON bundles generated by Synthea.
- **Key Functions**:
  - `load_fhir_bundle(filepath)`: Loads raw JSON.
  - `extract_patient_summary(bundle)`: Iterates over bundle resources. Maps `Patient` to demographics (calculating age relative to reference date `2022-11-07`); maps `Condition` to active vs. resolved; maps `MedicationRequest` to active vs. stopped (deduplicating multiple prescription fills); extracts `Procedure` and key `Observation` (LOINC 39156-5 for BMI).
  - `format_clinical_summary_markdown(summary)`: Formats the extracted dictionary into an LLM-ready markdown document with SNOMED and RxNorm identifiers.

#### 2. `src/policies.py`
- **Purpose**: Repository of structured, SNOMED-aligned clinical coverage policies.
- **Policies Included**:
  - **CP-101 (Oncology)**: Diagnostic and treatment procedures (mammography, colonoscopy, chemo).
  - **CP-202 (Neurology)**: Step therapy for specialty AEDs (requires documented failure of 2 first-line generic AEDs).
  - **CP-303 (Orthopedics)**: Elective total joint replacements (osteoarthritis diagnosis, conservative therapy >= 6 weeks, BMI < 40).
- **Key Functions**: `get_policy()`, `get_policy_text()`, `list_policy_ids()`.

#### 3. `src/cases.py`
- **Purpose**: Curated showcase demo cases used in the Streamlit UI.
- **Cases**:
  - `CASE-DEMO-001` (CP-101, Claretha Kuhlman): Active breast cancer + annual mammography history -> **Low Risk** (Approve).
  - `CASE-DEMO-002` (CP-202, Mavis Gusikowski): Active epilepsy + only 1 AED (Carbamazepine) -> **Moderate Risk** (Manual Review).
  - `CASE-DEMO-003` (CP-202, Lewis D'Amore): Active epilepsy + 0 AEDs (only dementia/cholesterol meds) -> **High Risk** (Deny).

#### 4. `src/audit_engine.py`
- **Purpose**: The orchestration layer communicating with Ollama.
- **Key Functions**:
  - `build_audit_prompt(case, patient_summary_md, policy_text)`: Assembles clinical prompts.
  - `get_system_prompt(policy_id)`: Injects policy-specific reasoning guidelines.
  - `run_audit(case, model, timeout_seconds, patient_dir)`: Sends POST request to Ollama, parses JSON, records latency, handles connection errors.
  - `warm_up_model(model)`: Sends a 1-token dummy prompt to preload weights into RAM/VRAM.
  - `_clean_and_parse_json(text)` & `_normalize_parsed_json(data)`: Robust JSON cleaning and key normalization.

---

### `benchmark/` Directory (Scaled 100-Case Evaluation)

#### 1. `benchmark/config.py`
- Centralized paths for benchmark fixtures: `CASES_JSON_PATH` (`ground_truth.json`), `PATIENT_DIR` (`benchmark/synthea_data`), and `RESULTS_DIR`.

#### 2. `benchmark/metrics.py`
- Zero-dependency statistical calculation engine (no heavy `scikit-learn` dependency).
- Computes: Multi-class Macro-F1 across the 3 risk tiers, per-tier Precision/Recall/F1, Confusion Matrix, Overall Accuracy, Mean Grounding Fidelity, and Latency percentiles (`p50`, `p95`, `mean`).

#### 3. `benchmark/evaluator.py`
- Automated quote verification and grounding evaluation engine.
- Key Functions:
  - `_sub_quote_match(quote, source_text)`: Substring and n-gram verification engine that tests whether a model's cited quote actually exists in the source text.
  - `evaluate_audit_result()`: Computes tier matching, citation precision, recall, and grounding fidelity against ground-truth benchmarks.

#### 4. `benchmark/run_scaled.py`
- Resumable automated test harness.
- Runs 100 Synthea cases through `audit_engine.py`.
- Computes grounding fidelity and correctness against deterministic ground truth.
- Generates `benchmark_results.csv`, `benchmark_summary.json`, and `benchmark_summary.txt`.
- Features: `--resume` (continues if interrupted) and `--limit N` (for quick smoke tests).

#### 4. `benchmark/results/`
- Actual benchmark outputs:
  - `benchmark_results.csv`: Per-case breakdown of expected vs. predicted tiers, citations, latency, and match status.
  - `benchmark_summary.txt`: Executive summary of evaluation metrics.

---

## 5. Clinical Coverage Policies & Clinical Logic

### CP-101: Oncology Diagnostic & Treatment
- **Mandatory Criteria**:
  - `C1`: Confirmed active malignant neoplasm (SNOMED codes e.g. 254837009 Breast, 109838007 Colon, 126906006 Prostate).
  - `C2`: Documented diagnostic procedure (mammography, colonoscopy, biopsy, bone scan) OR active oncology medication regimen (continuation of therapy).
  - `C3`: Age >= 18.
- **Risk Tiers**:
  - `Low Risk`: C1, C2, C3 met, no active cardiac comorbidity.
  - `Moderate Risk`: Malignancy present but missing diagnostic proof; OR chemotherapy initiation in patient with active severe cardiac disease (cardiac arrest / heart failure) requiring cardiology clearance.
  - `High Risk`: No active malignancy OR age < 18.

### CP-202: Neurology AED Step Therapy
- **Mandatory Criteria**:
  - `C1`: Active epilepsy or seizure disorder diagnosis (SNOMED 84757009, 128613002).
  - `C2`: Documented trial of at least two first-line generic AEDs (Carbamazepine, Levetiracetam, Lamotrigine, Valproic Acid, Phenytoin, Topiramate).
- **Risk Tiers**:
  - `Low Risk`: Active diagnosis AND >= 2 generic AED trials documented.
  - `Moderate Risk`: Active diagnosis AND exactly 1 generic AED trial documented.
  - `High Risk`: No active diagnosis OR 0 generic AED trials documented (e.g. patient only on Alzheimer's or statin drugs).

### CP-303: Orthopedic Joint Replacement
- **Mandatory Criteria**:
  - `C1`: Confirmed active osteoarthritis diagnosis of affected joint (knee/hip).
  - `C2`: Documented conservative therapy for >= 6 weeks (physical therapy, NSAIDs like Naproxen/Ibuprofen, cortisone injection).
  - `C3`: Patient BMI < 40.
- **Risk Tiers**:
  - `Low Risk`: C1, C2, and C3 (BMI < 40) met.
  - `Moderate Risk`: Osteoarthritis documented but no conservative therapy trial; OR active severe cardiac comorbidity requiring clearance.
  - `High Risk`: No osteoarthritis diagnosis OR patient BMI >= 40.

---

## 6. Benchmarking, Metrics & Evaluation Deep Dive

### Real Scaled Benchmark Results (100 Cases on `qwen2.5:7b`)
From `benchmark/results/benchmark_summary.txt`:
```
JSON validity rate      : 100.0%
Tier accuracy           : 41.0%
Macro-F1 (3 tiers)      : 0.3780
Grounding fidelity mean : 64.5%
Latency (s)             : p50=51.48s | p95=66.44s | mean=53.93s | total=5392s

Per-tier metrics:
  Low Risk        P=0.800  R=0.235  F1=0.364  (support=51)
  Moderate Risk   P=0.417  R=0.217  F1=0.286  (support=23)
  High Risk       P=0.329  R=0.923  F1=0.485  (support=26)

Confusion matrix (rows=expected, cols=predicted):
                 Low Risk  Moderate  High Risk  Invalid
  Low Risk             12         5         34        0
  Moderate Risk         3         5         15        0
  High Risk             0         2         24        0
```

### Critical Interview Talking Points on Benchmark Performance:
1. **Safety-First / Conservative Bias**:
   - Notice the High Risk recall is **92.3%** (24 out of 26 true High Risk cases were correctly flagged).
   - In healthcare audit systems, **a false approval (approving an ineligible claim) is vastly more hazardous than a false denial/manual review**. The local 7B model displays a strong conservative bias, shifting borderline or complex cases to High Risk / Deny.
2. **100% JSON Structural Integrity**:
   - Zero crashes, zero unparseable outputs across 100 cases, proving the robustness of the prompt constraints and `_clean_and_parse_json` defensive normalization.
3. **64.5% Verbatim Grounding Fidelity**:
   - Nearly two-thirds of all extracted quotes matched the exact clinical source text word-for-word, demonstrating effective hallucination suppression.
4. **Why HITL is Essential**:
   - These raw metrics highlight exactly why autonomous AI is not suitable for healthcare adjudication: a 41% accuracy model would be dangerous if fully automated, but as an **auditor copilot** that extracts evidence, highlights citations, and routes cases to human reviewers, it dramatically accelerates audit throughput while keeping humans in the loop.

---

## 7. Anticipated Interview Questions & Strong Technical Answers

### Q1: "Why did you choose a local LLM over commercial cloud APIs like GPT-4 or Claude?"
> **Strong Answer**:
> *"In healthcare, patient data security and HIPAA compliance are paramount. Using public cloud APIs introduces PHI egress risks, vendor data handling agreements (BAAs), and recurring token costs. By deploying `qwen2.5:7b` locally through Ollama, the entire pipeline runs strictly air-gapped on-premises. Zero patient data leaves the infrastructure, and operational cost scales with local hardware rather than API usage."*

### Q2: "Why didn't you use a Vector DB / RAG system for the patient records?"
> **Strong Answer**:
> *"Vector retrieval with semantic chunking is great for unstructured knowledge bases, but clinical medical records have strict temporal and deterministic dependencies. For instance, in CP-202 step therapy, we need to know if a patient trialed exactly two generic AEDs vs. zero, and whether they were discontinued. Vector embeddings can miss negative assertions or lose small medication line items. Instead, I built a deterministic FHIR R4 parser that extracts 100% of the structured clinical profile (active vs. stopped medications, SNOMED diagnoses, procedures, and vitals) into a clean, token-efficient summary of around 300 to 500 tokens. This completely fits within the model's 4k context window with zero retrieval loss."*

### Q3: "How do you mitigate hallucinations in medical decision making?"
> **Strong Answer**:
> *"We tackle hallucinations at three layers:
> 1. **Prompt Engineering & CoT**: We force the model into a 4-step Chain-of-Thought decomposition (Diagnosis -> Procedures -> Medications -> Contraindications), forcing it to evaluate evidence before reaching a tier.
> 2. **Verbatim Grounding Requirement**: The model must provide verbatim quote citations from both the coverage policy and the patient record.
> 3. **Automated Verbatim Verification**: In `benchmark/evaluator.py`, we implement a quote matching algorithm (`_sub_quote_match`) that checks whether cited quotes actually exist in the source document. We score this as Grounding Fidelity, which averaged 64.5% across 100 test cases."*

### Q4: "What does your benchmark tell us about the limitations of smaller local models (7B)?"
> **Strong Answer**:
> *"Running a 100-case scaled benchmark revealed that `qwen2.5:7b` has 100% JSON compliance and high recall for High Risk (92.3%), but exhibits an over-conservative bias, often classifying Low Risk cases as High Risk when it fails to synthesize multi-criteria rules. This confirms two things: first, 7B models require few-shot prompting or fine-tuning (LoRA) for clinical nuance; and second, autonomous AI decision-making is premature—the system must operate as a Human-in-the-Loop decision support tool where humans make the final determination."*

### Q5: "How does the Human-in-the-Loop (HITL) workflow operate in practice?"
> **Strong Answer**:
> *"The Streamlit application provides a three-card view comparing the Claim, Patient FHIR Summary, and Policy Criteria side-by-side. When the audit runs, the auditor doesn't just see 'Approve' or 'Deny'—they see the AI's step-by-step clinical rationale, self-reported confidence, and highlighted verbatim citations. The auditor can verify the facts in seconds and record a binding decision (Approve, Deny, Request More Info) with auditable clinical notes and timestamps."*

### Q6: "How did you optimize inference latency?"
> **Strong Answer**:
> *"Local inference can suffer from cold-start penalties where loading weights from disk into memory takes 15 to 30 seconds on the first call. I implemented a model warm-up routine (`warm_up_model()`) that fires a lightweight 1-token prompt on application startup with Ollama's `keep_alive: '30m'`. This keeps model weights resident in RAM/VRAM across user sessions, ensuring consistent inference times."*
