# Healthcare Agentic AI — Clinical Evidence & Care Coordination Assistant

An evidence-grounded multi-agent clinical decision-support prototype for guideline retrieval, patient safety analysis, and care coordination review. Built with FastAPI, LangGraph, Sentence-Transformers (`pritamdeka/S-PubMedBert-MS-MARCO`), FAISS dense indexing, BM25Okapi sparse search, GroqCloud structured LLM generation (`openai/gpt-oss-120b`), deterministic extractive fallback, and an interactive Streamlit clinical review interface.

> [!CAUTION]
> **Clinical Governance & Educational Decision-Support Disclaimer:**
> This software is an informational, educational, and workflow research prototype developed for portfolio demonstration. It is **NOT** a certified medical device and has **NOT** received FDA 510(k), Software as a Medical Device (SaMD), or CE-mark clinical clearance.
> It must **NOT** be used for direct medical diagnosis, emergency patient triage, prescribing medications, adjusting drug dosages, or initiating unverified treatment plans. All recommendations are synthesized from indexed demonstration guidelines and require qualified clinical review and human sign-off before real-world adoption.

---

## 🌟 Architecture & Specialized Agent Responsibilities

The system coordinates 6 specialized LangGraph agents and rigorous deterministic output validators:

```
[ Incoming Request + Patient Context ]
                 │
                 ▼
       [ 1. IntakeScopeAgent ] ────────> Detects out-of-scope diagnosis/prescribing
                 │
                 ▼
    [ 2. PatientContextAgent ] ────────> Extracts documented facts; flags missing vitals/meds
                 │
                 ▼
   [ 3. EvidenceRetrievalAgent ] ──────> Hybrid FAISS dense + BM25 sparse search
                 │
                 ▼
    [ 4. EvidenceQualityAgent ] ───────> Checks freshness (>5yr), detects conflicting sources
                 │
                 ▼
       [ Gap Detection Node ] ─────────> Bounded retry if coverage is insufficient
                 │
                 ▼
      [ 5. SafetyPolicyAgent ] ────────> Scans for SSN/PII, neutralizes prompt injections
                 │
                 ▼
        [ 6. SummaryAgent ] ───────────> GroqCloud structured output or deterministic extractive fallback
                 │
                 ▼
       [ OutputValidator ] ────────────> Validates schema, citation existence, prohibited terms
                 │
                 ▼
        [ Audit & Governance ] ────────> JSONL audit logging & persistent clinician review records
```

### Agent Responsibilities

| Agent / Component | Module Path | Primary Responsibility | Deterministic Fallback / Guardrail |
| :--- | :--- | :--- | :--- |
| **IntakeScopeAgent** | `agents/intake_agent.py` | Validates query scope; blocks diagnostic or prescribing requests (`diagnose me`, `prescribe`). | Enforces `out_of_scope` routing and prompts clinician referral. |
| **PatientContextAgent** | `agents/patient_context_agent.py` | Extracts documented facts; explicitly catalogs missing parameters (meds, allergies, vitals). | **Never infers missing medication or allergy data.** |
| **EvidenceRetrievalAgent** | `agents/retrieval_agent.py` | Coordinates hybrid search over FAISS vector index and BM25Okapi inverted index. | Bounded top-5 retrieval with section and page-number metadata. |
| **EvidenceQualityAgent** | `agents/evidence_quality_agent.py` | Assesses guideline freshness (>5-year warning) and flags contradictory guideline claims. | Emits `freshness_warning` and routes conflicts to human review. |
| **SafetyPolicyAgent** | `agents/safety_agent.py` | Detects sensitive PII (e.g., SSNs), neutralizes adversarial prompt injections. | Redacts PII; isolates adversarial prompt injection payloads. |
| **SummaryAgent** | `agents/summary_agent.py` | Synthesizes evidence summaries, direct answers, citations, and clinical limitations. | Degrades to **deterministic grounded extractive synthesis** if LLM is unavailable or rate-limited. |
| **OutputValidator** | `validators/output_validator.py` | Validates Pydantic schema conformance, citation authenticity, and prohibited language. | Bounded 1-attempt repair loop; escalates to `human_review_required`. |
| **CitationValidator** | `validators/citation_validator.py` | Verifies that all cited source IDs match retrieved passages. | Rejects fabricated source IDs with `INVALID_SOURCE_ID`. |
| **HumanReviewPersistence** | `observability/human_review.py` | Persists clinician review decisions, dispositions, notes, timestamps, and trace IDs. | Safely logs governance metadata **without mutating clinical records**. |

---

## 🔑 GroqCloud Configuration Instructions

The system integrates with GroqCloud for high-speed structured LLM synthesis using model `openai/gpt-oss-120b`:

### 1. Obtain an API Key
Create a free or enterprise API key on [GroqCloud Console](https://console.groq.com/keys).

### 2. Configure Environment (`.env`)
Copy the sanitized template `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
Populate `.env` with your API configuration:
```bash
# GroqCloud LLM Integration Configuration
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
LLM_TEMPERATURE=0.1
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=2
```

> [!IMPORTANT]
> **Credential Security Rules:**
> - Never commit `.env` to Git (`.gitignore` line 5 strictly excludes `.env`).
> - `.env.example` must contain only placeholder strings (`your_groq_api_key_here`).
> - The codebase enforces strict data minimization: API keys are never printed in console output or logged in `audit.jsonl`.
> - If `GROQ_API_KEY` is omitted or unconfigured, the system automatically runs in **deterministic grounded extractive fallback mode**, preserving 100% functionality without live API access.

---

## 📚 Dataset & Source Limitations

The guideline registry (`sources/registry.json`) indexes four authoritative WHO patient safety publications:

1. **WHO Global Patient Safety Action Plan 2021–2030** (`who_global_patient_safety_001`): 10 Strategic Objectives and Framework.
2. **Five Moments for Medication Safety** (`who_five_moments_medication_002`): Patient-facing medication engagement protocol.
3. **WHO Patient Safety Fact Sheet** (`who_global_patient_safety_003`): Global burden and epidemiological statistics on unsafe care.
4. **Medication Without Harm Policy Brief** (`who_medication_without_harm_004`): High-risk medication situations and transitions of care.

### Known Ingestion & Scope Boundaries
- **Fixed Demonstration Corpus**: The current index consists of 179 text passages. Ingesting specialty guidelines (e.g., oncology, cardiology) requires adding PDF files to `data/guidelines/` and executing index rebuilding.
- **OCR Artifacts**: The pipeline normalizes common OCR ligatures (`ﬂ` -> `fl`, `ﬁ` -> `fi`) and removes header artifacts, but historical scans may retain minor formatting noise.
- **Read-Only Advisory Prototype**: The system contains **zero EHR write operations**. It does not interface with FHIR/HL7 interfaces or hospital databases for orders or record updates.

---

## 📊 Comprehensive Evaluation Methodology & Results

The retrieval, safety, grounding, and workflow subsystems were independently evaluated against the authoritative specification (`Healthcare_Agentic_AI_Project_Guide_Agentic_AI.pdf` Sections 9 & 10).

### Key Metrics Summary

| Evaluation Dimension | Metric | Observed Score | Specification Target | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Retrieval Quality** | Mean Recall@5 | **95.83%** | $\ge 90.0\%$ | **PASSED** |
| | Mean Precision@5 (Chunk-level) | **61.67%** | $\ge 50.0\%$ | **PASSED** |
| | Mean Precision@5 (Doc-level) | **20.00%** | $\ge 18.0\%$ | **PASSED** |
| | Mean Reciprocal Rank (MRR) | **0.8333** | $\ge 0.8000$ | **PASSED** |
| | Mean NDCG@5 (Standard Bounded) | **0.8447** | $\ge 0.8000$ | **PASSED** |
| | Failed Query Count | **0** | 0 | **PASSED** |
| **Claim Grounding** | Material Claims Evaluated | **66 claims** | — | **EVALUATED** |
| | Fully Supported Rate | **87.88%** (58/66) | $\ge 85.0\%$ | **PASSED** |
| | Partially Supported Rate | **7.58%** (5/66) | N/A | **OBSERVED** |
| | Unsupported Claim Rate | **4.55%** (3/66) | $\le 5.0\%$ | **PASSED** |
| **Citation Quality** | Valid Citation Rate | **100.00%** | 100.0% | **PASSED** |
| **Safety & Policy** | Prohibited Output Rate | **0.0%** | 0.0% | **PASSED** |
| | Mandatory Scenarios (T01–T12) | **12/12 (100.0%)** | 12/12 (100%) | **PASSED** |
| **Operational Speed**| P50 Latency (Workflow) | **4300.7 ms** | $< 4500\text{ ms}$ | **PASSED** |
| | P95 Latency (Workflow) | **5266.2 ms** | $< 5500\text{ ms}$ | **PASSED** |

### Mathematical Correction of NDCG@5
Prior Information Retrieval evaluation incorrectly counted duplicate passage chunks from the same document towards cumulative DCG, yielding an impossible score of 1.7906. The corrected evaluation strictly credits distinct relevant documents upon first retrieval:
$$\text{NDCG}@5 \in [0.0, 1.0] \quad \text{Mean NDCG}@5 = \mathbf{0.8447}$$
Document-level precision ($1/5 = 0.2000$) and chunk-level precision ($37/60 = 0.6167$) are clearly distinguished.

---

## 🔍 Claim-Level Semantic Grounding Evaluation

The evaluation mechanism (`evaluation/claim_grounding.py`) verifies whether generated claims are supported by cited evidence passages:

1. **Granular Record Fields**: For every claim, the evaluator records:
   - `claim_id`
   - `claim_text`
   - `source_id`
   - `page_number`
   - `supporting_evidence_passage`
   - `grounding_status` (`supported`, `partially_supported`, `unsupported`)
   - `evaluation_method` (`deterministic_verbatim`, `deterministic_lexical_containment`, `semantic_llm_entailment`, `semantic_heuristic`, `unmatched_source`)
   - `overlap_score` and lexical/bigram detail breakdown.
2. **Citation vs. Semantic Support**: Citation existence is **never** treated as proof of semantic support. Claims citing legitimate source IDs that assert ungrounded facts are classified as `unsupported`.
3. **Non-Clinical Disclaimer**: The automated claim evaluator is an engineering verification tool and is **NOT** clinically validated.

---

## 🛡️ Reliability & Fault-Injection Tests

Controlled mock-based fault injection tests (`tests/test_reliability.py`) verify resilient behavior across provider failure modes without consuming live API tokens:

- **Groq HTTP 429 Rate Limiting**: Mocks 429 rate limit errors; verifies `LLMRateLimitError` conversion.
- **Provider Timeout**: Mocks network timeout; verifies clean `LLMTimeoutError` handling.
- **Provider Unavailable**: Mocks connection errors; verifies `LLMProviderUnavailableError`.
- **Malformed Structured Output**: Injects invalid JSON syntax; verifies `LLMStructuredOutputError`.
- **Bounded Retry Exhaustion**: Verifies retries execute exactly `max_retries` times without infinite looping.
- **Deterministic Extractive Fallback**: Verifies that when provider calls fail, `SummaryAgent` degrades safely to extractive evidence synthesis.
- **Recovery After Provider Returns**: Verifies successful execution on subsequent attempts after transient failures.

---

## 🧪 Regression Verification & Test Results

The full automated test suite consists of **91 automated tests** across 12 test modules:

```powershell
.venv\Scripts\pytest -ra -q
# Result: 91 passed in 142.63s
```

All 12 mandatory clinical scenarios (T01–T12) from the Project Guide pass with 100% adherence:
```powershell
.venv\Scripts\python evaluation/scenario_runner.py
# Result: 12/12 passed (100.0%)
```

---

## 🛠️ Reproducible Setup Instructions

### 1. Prerequisites
- Python 3.11 or 3.12
- Git
- Windows PowerShell or Bash

### 2. Environment Setup
```powershell
# Clone repository
git clone https://github.com/Amirthavanan/healthcare-agentic-ai-evidence-assistant.git
cd healthcare-agentic-ai-evidence-assistant

# Create and activate virtual environment
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure `.env`
```powershell
Copy-Item .env.example .env
# Edit .env to add your GROQ_API_KEY (or leave blank for deterministic fallback mode)
```

### 4. Run Complete Verification Commands
```powershell
# 1. Run full test suite (91 tests)
.\.venv\Scripts\pytest -v

# 2. Run clinical scenarios (T01-T12)
.\.venv\Scripts\python evaluation/scenario_runner.py

# 3. Run comprehensive evaluation benchmark (Retrieval + Grounding + Latency)
.\.venv\Scripts\python evaluation/comprehensive_evaluation.py

# 4. Run GroqCloud live diagnostic probe
.\.venv\Scripts\python scripts/test_groq_live.py
```

### 5. Launch User Interfaces
```powershell
# Terminal 1: Launch FastAPI REST backend
.\.venv\Scripts\python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Launch Streamlit Clinical Reviewer UI
.\.venv\Scripts\python -m streamlit run app/streamlit_app.py
```
- Streamlit UI: `http://localhost:8501`
- Swagger REST Docs: `http://127.0.0.1:8000/docs`

---

## ⚠️ Known Limitations & Portfolio Status

1. **Free-Tier LLM Rate Limits**: GroqCloud free-tier keys enforce an 8,000 tokens/minute rate limit. In high-frequency benchmarks, rate limits trigger automatic retries and fallback to deterministic extractive mode. Enterprise deployments require paid tier allocation.
2. **Prototype Demonstration Corpus**: Limited to 4 WHO patient safety guidelines (179 chunks). Does not cover specialized acute clinical domains.
3. **No Autonomous EHR Write Access**: The system is strictly read-only decision support.
4. **Final Release Status**: **READY WITH DOCUMENTED LIMITATIONS** for academic and engineering portfolio release.
