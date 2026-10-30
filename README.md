# Healthcare Agentic AI — Clinical Evidence and Care Coordination Assistant

An end-to-end evidence-grounded agentic assistant for clinical guideline retrieval, patient safety analysis, and care coordination review. Built with FastAPI, LangGraph, Sentence-Transformers (`pritamdeka/S-PubMedBert-MS-MARCO`), FAISS dense indexing, BM25Okapi sparse search, and a Streamlit clinical review interface.

> [!CAUTION]
> **Clinical Governance & Educational Boundary:**
> This system is an informational, educational, and workflow research prototype. It is **NOT** a certified medical device and must **NOT** be used for direct medical diagnosis, patient triage, prescribing medications, or unverified treatment decisions. All responses are derived strictly from indexed demonstration sources and require qualified clinical review before real-world adoption.

---

## 🌟 Key Features & Architecture

1. **Robust Ingestion Pipeline (`retrieval/hybrid.py`)**:
   - Ingests WHO Patient Safety Action Plan, Five Moments for Medication Safety, Medication Without Harm Policy Brief, and OCR-extracted Fact Sheets.
   - Cleans OCR noise, Unicode ligatures (`ﬂ` -> `fl`, `ﬁ` -> `fi`), timestamp artifacts, and URL headers.
   - Preserves granular page-level and section-level provenance metadata across all chunks.

2. **Calibrated Hybrid Retrieval Engine (`retrieval/hybrid.py`)**:
   - Dense semantic vector search via `faiss-cpu` and PubMedBERT embeddings (`pritamdeka/S-PubMedBert-MS-MARCO`).
   - Sparse keyword search via `BM25Okapi`.
   - Tuned hybrid weighting (Default: 35% Sparse, 65% Dense) solving challenging queries like R008 without degradation.
   - Atomic cache writing (`.tmp` -> replace), SHA-256 manifest signature verification, and automated cache rebuilds.

3. **Agentic Orchestration Graph (`orchestration/graph.py` & `agents/nodes.py`)**:
   - **Intake & Scope Guardrails**: Prohibits diagnostic and prescribing queries (`diagnose me`, `prescribe`), immediately routing out-of-scope requests to human clinical escalation.
   - **Context Analysis**: Flags missing vital clinical parameters (medications, allergies, vital signs, symptom duration).
   - **Hybrid Retrieval**: Extracts top-ranked guideline passages with provenance.
   - **Evidence Quality & Gap Detection**: Inspects coverage and executes a bounded single retry if relevance falls below safety thresholds.
   - **Safety Policy Routing**: Evaluates escalation triggers and enforces `human_review_required` when appropriate.
   - **Grounded Answer Synthesis**: Produces Direct Answers, Key Findings, and verbatim evidence citations.
   - **Deterministic Output Validation**: Audits that all cited source IDs exist in retrieved evidence and required schemas are complete.

4. **REST API & Observability (`api/main.py` & `observability/audit.py`)**:
   - `/health`: System status, clinical prototype mode, and index statistics.
   - `/sources`: Versioned registry of indexed healthcare documents.
   - `/retrieval/search`: Diagnostic endpoint for direct sparse-dense hybrid queries.
   - `/cases/review`: Full multi-node agent workflow execution.
   - `/evaluation/latest`: Retrieval evaluation benchmark results.
   - De-identified JSONL audit trail written to `audit.jsonl`.

5. **Interactive Streamlit Review Interface (`app/streamlit_app.py`)**:
   - Case Review & Q&A with synthetic clinical case presets.
   - Interactive Document Source registry browser.
   - Real-time Hybrid Retrieval Diagnostic search tool with score breakdowns.
   - Automated Evaluation Benchmark viewer displaying recall and reciprocal rank tables.

---

## 📊 Benchmark Evaluation Results

Evaluated across the complete 12 clinical / safety queries in `evaluation/dataset.json` at top-$k=5$:

| Metric | Baseline (Pre-Implementation) | Current Validated System | Delta / Improvement |
| :--- | :--- | :--- | :--- |
| **Total Benchmark Queries** | 12 | 12 | — |
| **Mean Recall@5** | 0.8750 | **0.9583** | **+0.0833 (+9.5%)** |
| **Mean Precision@5** | 0.1833 | **0.2000** | **+0.0167 (+9.1%)** |
| **Mean Reciprocal Rank (MRR)** | 0.7500 | **0.8333** | **+0.0833 (+11.1%)** |
| **Failed Queries (Recall = 0.0)** | 1 (`R008`) | **0 (`[]`)** | **100% Resolved** |

- **R008** (*"What system and organizational factors can contribute to patient harm?"*): Improved from Rank 6 (out of top 5) to Rank 2 (Recall = 1.0, Reciprocal Rank = 0.5).
- **R011** (*"How can patient and family engagement contribute to safer healthcare?"*): Successfully retrieves primary guideline `who_global_patient_safety_001` at Rank 1 (Recall = 0.5, Reciprocal Rank = 1.0).

---

## 🛠️ Installation & Environment Setup

### Prerequisites
- Python 3.11 or 3.12 (Tested on Python 3.12.10 Windows / Linux)
- Git

### 1. Clone & Set Up Virtual Environment

**Windows PowerShell:**
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**macOS / Linux:**
```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```

---

## 🚀 Running the Application

### Option A: Run Backend API (FastAPI)
```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```
- Interactive Swagger API docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

### Option B: Run Clinical Reviewer UI (Streamlit)
In a separate terminal window:
```powershell
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py
```
Access the web application at `http://localhost:8501`.

### Option C: CLI Retrieval & Rebuild
- **Search CLI**:
  ```powershell
  .\.venv\Scripts\python.exe -m retrieval.hybrid --query "What are the five moments for medication safety?" --top-k 5
  ```
- **Force Index Rebuild**:
  ```powershell
  .\.venv\Scripts\python.exe -m retrieval.hybrid --rebuild
  ```

---

## 🧪 Testing & Evaluation

### Run Test Suite (33 Tests Passed)
```powershell
.\.venv\Scripts\python.exe -m pytest -v
```
The test suite covers:
- Ingestion, text cleaning, ligature normalization, and chunking (`tests/test_ingestion.py`)
- FAISS vector persistence and cache reload (`tests/test_persistence.py`)
- Hybrid search ranking, edge cases, and weight validation (`tests/test_retrieval.py`)
- LangGraph agent workflow, gap detection, and safety policies (`tests/test_workflow.py`)
- FastAPI endpoints, validation, and error handling (`tests/test_api.py`)
- Evaluation metrics calculation (`tests/test_evaluation.py`)

### Run Benchmark Evaluation
```powershell
.\.venv\Scripts\python.exe -m evaluation.run_evaluation
```
Outputs full JSON metrics report to `evaluation/latest_report.json`.

---

## 🔒 Security & Safe Medical AI Design

1. **De-identified Data Only**: Tested exclusively with synthetic cases (`data/synthetic/`).
2. **Audit Logging**: Structured events in `audit.jsonl` omit raw patient identifying text by default.
3. **Strict Citation Validation**: Every assertion in the generated draft is mapped to a valid `source_id` present in retrieved passages.
4. **Input Sanitization**: Search queries and API requests enforce Pydantic boundaries preventing path traversal or injection.
5. **Bounded Graph Transitions**: Maximum recursion limits and single-pass retries prevent infinite loops.
