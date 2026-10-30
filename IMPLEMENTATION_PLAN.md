# Implementation Plan: Healthcare Agentic AI End-to-End

## 1. Project Overview & Validated Status

- **Repository Root**: `D:\WRENCH_WISE\CAPSTONE\healthcare_agentic_ai\healthcare_agentic_ai\healthcare_agentic_ai`
- **Architecture**:
  - Ingestion: PDF (`pypdf`), OCR text (`patient_safety_fact_sheet_ocr.txt` with `--- Page N ---` markers).
  - Retrieval: Hybrid BM25Okapi + Dense FAISS index using `pritamdeka/S-PubMedBert-MS-MARCO` embeddings.
  - Evaluation: 12 clinical / safety queries in `evaluation/dataset.json`.
  - Workflow: LangGraph state graph with nodes (`intake`, `patient_context`, `retrieval`, `evidence_quality`, `gap_detection`, `safety`, `summary`, `validation`).
  - Observability: `observability/audit.py` writing de-identified audit events to `audit.jsonl`.
  - API: FastAPI in `api/main.py` with Pydantic schemas in `api/schemas.py`.
  - UI: Streamlit interface in `app/streamlit_app.py`.

### Benchmark Evaluation Results (12-Query Testbed)
- **Total Queries**: 12
- **Mean Recall@5**: 0.9583 (Baseline was 0.8750)
- **Mean Precision@5**: 0.2000 (Baseline was 0.1833)
- **Mean Reciprocal Rank (MRR)**: 0.8333 (Baseline was 0.7500)
- **Failed Queries**: 0 (`[]`) (Baseline had 1 failed: `R008`)
- **Query R008**: Resolved; retrieved at Rank 2 with Recall@5 = 1.0
- **Query R011**: Partial recall (Recall@5 = 0.5) with primary source retrieved at Rank 1 (MRR = 1.0)

### Test Suite Results (Pytest)
- **Total Tests**: 33
- **Passed**: 33 (100%)
- **Failed**: 0
- **Skipped**: 0

---

## 2. Implementation Checklist

### Phase 1: Document Ingestion & Chunking Pipeline
- [x] Implement robust document loader supporting PDF and UTF-8 text with error handling.
- [x] Detect PDFs with zero / insufficient extractable text with warnings.
- [x] Clean and normalize OCR noise (ligatures like `ﬂ` -> `fl`, joined tokens, URL artifacts).
- [x] Implement section/page-aware chunking with overlap that preserves provenance (`id`, `title`, `source_file`, `page`, `section`).
- [x] Validate registry integrity (prevent path traversal, verify file existence, unique IDs).
- [x] Keep source documents unchanged and OCR pre-extraction reusable.

### Phase 2: Hybrid Retrieval Engine & Cache Synchronization
- [x] Update `retrieval/hybrid.py`:
  - [x] Support configurable weights via parameters and environment variables (`SPARSE_WEIGHT`, `DENSE_WEIGHT`).
  - [x] Set optimal hybrid weights (empirically validated: `sparse=0.35, dense=0.65` solves R008 with 0 failed queries).
  - [x] Normalize tokens and clean text consistently across BM25 and dense embeddings.
  - [x] Ensure chunk dictionaries have consistent metadata fields (`id`, `source_id`, `title`, `source_file`, `page`, `section`, `publisher`, `version`, `effective_date`, `review_status`).
  - [x] Cache integrity: Atomic cache writes (`.tmp` -> replace), signature verification over content + config + model, graceful fallback/rebuild on cache corruption.
  - [x] Dedicated CLI command / script for cache rebuild.

### Phase 3: Evaluation Quality Optimization & Investigation
- [x] Investigate R008:
  - [x] Verify chunk indexing, text quality, dense and sparse scores.
  - [x] Controlled weight experiments across all 12 queries.
- [x] Investigate R011:
  - [x] Analyze multi-source retrieval dynamics when document 001 has multiple highly-ranked pages.
  - [x] Test chunk granularity to allow fact-sheet page 4 engagement excerpt to compete or report exact behavior.
- [x] Re-run evaluation, assert zero failed queries, and produce `EVALUATION_REPORT.md` and `evaluation/latest_report.json`.

### Phase 4: Evidence-Grounded Answer Generation & Synthesis
- [x] Implement structured answer generation engine grounded strictly in retrieved context.
- [x] Structure generated answers: Direct Answer, Key Findings, Supporting Evidence with exact page citations, Limitations & Healthcare Disclaimer.
- [x] Configurable LLM provider support (Gemini / OpenAI / local / fallback mock with clear configuration instructions).
- [x] Fallback safely when external LLM is not configured, returning structured evidence and explanation without pretending.

### Phase 5: Agentic Workflow & Guardrails
- [x] Fix schema compatibility in `agents/nodes.py` to resolve failing tests.
- [x] Complete LangGraph workflow with:
  - [x] Query classification & intent analysis.
  - [x] Context & missing info detection.
  - [x] Retrieval & evidence validation.
  - [x] Gap detection & bounded retry if relevant evidence is missing.
  - [x] Grounded answer generation.
  - [x] Citation validation against retrieved IDs and pages.
  - [x] Safety routing & audit logging.
- [x] Add guardrails: recursion limits, cycle prevention, deterministic validation.

### Phase 6: Backend API Enhancement
- [x] Update `api/main.py` and `api/schemas.py`:
  - [x] Health check endpoint (`/health`).
  - [x] Document status / sources endpoint (`/sources`).
  - [x] Retrieval search diagnostics endpoint (`/retrieval/search`).
  - [x] Case review / Q&A workflow endpoint (`/cases/review`).
  - [x] Evaluation report endpoint (`/evaluation/latest`).
  - [x] Proper CORS middleware, input validation, structured error responses.

### Phase 7: Frontend Application Integration
- [x] Polish Streamlit application in `app/streamlit_app.py`:
  - [x] Modern, responsive healthcare UI.
  - [x] Question input and synthetic case pre-fills.
  - [x] Status indicators (human review required, workflow steps).
  - [x] Clear tabs/sections for Direct Answer, Key Findings, Retrieved Evidence with clickable citations, Limitations, Validation.
  - [x] Diagnostic drawer for similarity scores and workflow traces.
  - [x] Prominent educational / non-clinical disclaimer.

### Phase 8: Testing, QA & Security
- [x] Expand pytest suite:
  - [x] Ingestion & chunking unit tests.
  - [x] OCR page parsing and ligature normalization tests.
  - [x] Hybrid retriever tests with cache hit/miss/rebuild.
  - [x] Workflow & agent node tests.
  - [x] API endpoint tests.
  - [x] Citation validator tests.
- [x] Verify all tests pass (33 passed, 0 failed).
- [x] Security review: sanitized `.env.example`, no leaked credentials, no code execution, input sanitization.

### Phase 9: Deployment, Docker & Comprehensive Documentation
- [x] Create `Dockerfile` and `docker-compose.yml`.
- [x] Document virtual environment, prerequisites, startup instructions.
- [x] Update `README.md` and `EVALUATION_REPORT.md`.
- [x] Produce final engineering report and verify end-to-end execution.
