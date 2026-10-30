import json
import os
from typing import Any

import requests
import streamlit as st

API_URL = os.getenv("HEALTHCARE_API_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="Healthcare Agentic AI — Evidence Assistant",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for high contrast, rich aesthetics, and healthcare UI design
st.markdown(
    """
    <style>
    /* 1. Global App Theme Enforcements */
    .stApp {
        background-color: #F8FAFC !important;
        color: #0F172A !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* 2. Global Headings & Typography */
    h1, h2, h3, h4, h5, h6 {
        color: #0F172A !important;
        font-weight: 700 !important;
        letter-spacing: -0.01em;
    }
    .stMarkdown p, .stMarkdown div, .stMarkdown span, .stMarkdown li {
        color: #1E293B !important;
    }
    
    /* 3. Header & Sub-caption */
    .main-header {
        font-size: 2.1rem;
        font-weight: 800;
        color: #1E3A8A !important;
        margin-bottom: 0.25rem;
    }
    .sub-caption {
        font-size: 1.05rem;
        color: #475569 !important;
        margin-bottom: 1.25rem;
    }
    
    /* 4. Disclaimer Card */
    .disclaimer-card {
        background-color: #FFFBEB !important;
        border: 1px solid #FDE68A !important;
        border-left: 5px solid #D97706 !important;
        padding: 14px 18px !important;
        border-radius: 6px !important;
        margin-bottom: 1.5rem !important;
        font-size: 0.95rem !important;
        color: #78350F !important;
        line-height: 1.5 !important;
    }
    .disclaimer-card strong {
        color: #92400E !important;
    }
    
    /* 5. Direct Answer Card */
    .answer-card {
        background-color: #F0FDF4 !important;
        border: 1px solid #BBF7D0 !important;
        border-left: 5px solid #16A34A !important;
        border-radius: 8px !important;
        padding: 18px 22px !important;
        margin-top: 1rem !important;
        margin-bottom: 1.5rem !important;
        color: #0F172A !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
    .answer-card h4 {
        margin-top: 0 !important;
        margin-bottom: 0.5rem !important;
        color: #14532D !important;
        font-size: 1.15rem !important;
        font-weight: 700 !important;
    }
    .answer-card p {
        color: #0F172A !important;
        font-size: 1.05rem !important;
        line-height: 1.6 !important;
        margin-bottom: 0 !important;
    }
    
    /* 6. Key Evidence Finding Pills */
    .finding-pill {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-left: 5px solid #2563EB !important;
        padding: 12px 18px !important;
        margin-bottom: 10px !important;
        border-radius: 6px !important;
        font-size: 0.95rem !important;
        color: #0F172A !important;
        line-height: 1.55 !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
    }
    .finding-pill strong {
        color: #1E3A8A !important;
    }
    .finding-source-tag {
        display: inline-block;
        background-color: #EFF6FF;
        color: #1D4ED8 !important;
        font-weight: 600;
        font-size: 0.82rem;
        padding: 2px 8px;
        border-radius: 4px;
        margin-top: 4px;
        border: 1px solid #DBEAFE;
    }
    
    /* 7. Status Badges */
    .status-badge-amber {
        display: inline-block;
        background-color: #FEF3C7 !important;
        color: #78350F !important;
        font-weight: 700;
        font-size: 0.875rem;
        padding: 4px 12px;
        border-radius: 9999px;
        border: 1px solid #F59E0B !important;
    }
    .status-badge-green {
        display: inline-block;
        background-color: #DCFCE7 !important;
        color: #14532D !important;
        font-weight: 700;
        font-size: 0.875rem;
        padding: 4px 12px;
        border-radius: 9999px;
        border: 1px solid #16A34A !important;
    }
    
    /* 8. Panel and Card Containers */
    .metric-panel {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
        padding: 16px 20px !important;
        margin-bottom: 1rem !important;
    }
    .warning-item {
        background-color: #FEF2F2 !important;
        border: 1px solid #FECACA !important;
        border-left: 4px solid #DC2626 !important;
        color: #991B1B !important;
        padding: 8px 12px !important;
        border-radius: 4px !important;
        margin-bottom: 6px !important;
        font-size: 0.9rem !important;
        font-weight: 600;
    }
    .info-item {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        color: #1E293B !important;
        padding: 8px 12px !important;
        border-radius: 4px !important;
        margin-bottom: 6px !important;
        font-size: 0.9rem !important;
    }
    
    /* 9. Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #F1F5F9 !important;
        border-right: 1px solid #E2E8F0 !important;
    }
    [data-testid="stSidebar"] * {
        color: #1E293B !important;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #0F172A !important;
    }
    
    /* 10. Form & Input styling */
    .stTextInput input, .stTextArea textarea, .stSelectbox [data-baseweb="select"] {
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 6px !important;
    }
    .stTextInput label, .stTextArea label, .stSelectbox label {
        color: #0F172A !important;
        font-weight: 600 !important;
    }
    
    /* 11. Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 2px solid #E2E8F0 !important;
    }
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        color: #475569 !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        border-radius: 6px 6px 0 0 !important;
        padding: 8px 16px !important;
    }
    .stTabs [aria-selected="true"] {
        color: #1D4ED8 !important;
        border-bottom: 3px solid #2563EB !important;
        background-color: #EFF6FF !important;
    }
    
    /* 12. Expanders & Blockquotes */
    [data-testid="stExpander"] {
        background-color: #FFFFFF !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 8px !important;
        margin-bottom: 0.75rem !important;
    }
    [data-testid="stExpander"] summary {
        color: #0F172A !important;
        font-weight: 600 !important;
    }
    [data-testid="stExpander"] summary:hover {
        color: #2563EB !important;
    }
    [data-testid="stExpander"] p, [data-testid="stExpander"] div, [data-testid="stExpander"] span {
        color: #1E293B !important;
    }
    blockquote {
        background-color: #F8FAFC !important;
        border-left: 4px solid #3B82F6 !important;
        color: #1E293B !important;
        padding: 10px 16px !important;
        margin: 8px 0 !important;
        border-radius: 0 4px 4px 0 !important;
        line-height: 1.6 !important;
    }
    .stCaption, caption {
        color: #475569 !important;
        font-size: 0.875rem !important;
    }
    
    /* 13. Metrics */
    [data-testid="stMetricValue"] {
        color: #0F172A !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricLabel"] {
        color: #475569 !important;
        font-weight: 600 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def fetch_api_health() -> dict[str, Any] | None:
    try:
        r = requests.get(f"{API_URL}/health", timeout=3)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


# Sidebar Navigation & System Status
health_info = fetch_api_health()

with st.sidebar:
    st.title("🩺 System Controls")
    if health_info:
        st.success(f"API Online ({health_info.get('indexed_chunks', 0)} chunks indexed)")
    else:
        st.error(f"API Offline (Cannot reach {API_URL})")
        st.caption("Start the backend with `uvicorn api.main:app`")

    st.markdown("---")
    st.subheader("Synthetic Case Presets")
    preset = st.selectbox(
        "Choose a demonstration case:",
        [
            "Custom Synthetic Input",
            "SYN-001: Cough & Asthma Context (Illustrative)",
            "R008: System & Organizational Factors Contributing to Harm",
            "R003: Five Moments for Medication Safety",
            "R011: Patient & Family Engagement in Care",
            "SAFETY-TEST: Prohibited Diagnostic Query",
        ],
    )

    st.markdown("---")
    st.markdown(
        "**Evidence Grounding**\n"
        "- Model: `pritamdeka/S-PubMedBert-MS-MARCO`\n"
        "- Retrieval: Hybrid BM25 (35%) + FAISS (65%)\n"
        "- Documents: WHO Patient Safety & Medication Guidelines"
    )

# Title & Governance Disclaimer
st.markdown('<div class="main-header">Healthcare Agentic AI Evidence Assistant</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-caption">Evidence-grounded intelligence for clinical guidelines, patient safety, and care coordination review.</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="disclaimer-card">
        <strong>⚠️ Clinical Governance & Educational Boundary:</strong>
        This system is an informational and educational prototype. It is NOT a medical device and must NOT be used for
        direct medical diagnosis, patient triage, medication prescribing, or unverified treatment decisions.
        All responses are grounded strictly in indexed demonstration sources and require qualified clinical review.
    </div>
    """,
    unsafe_allow_html=True,
)

# Tabs
tab_review, tab_sources, tab_diagnostics, tab_eval = st.tabs([
    "📋 Case Review & Q&A",
    "📚 Document Sources",
    "🔍 Retrieval Diagnostics",
    "📊 Benchmark Evaluation",
])

# Preset value mapping
default_case_id = "SYN-001"
default_question = "Prepare an evidence summary for clinician review about worsening cough. Do not diagnose or recommend medication changes."
default_facts = "Asthma is listed in the supplied synthetic record\nWorsening cough is reported"
default_meds = ""
default_allergies = ""
default_vitals = ""
default_duration = ""

if preset == "SYN-001: Cough & Asthma Context (Illustrative)":
    default_case_id = "SYN-001"
    default_question = "Prepare an evidence summary for clinician review about worsening cough."
    default_facts = "Asthma is listed in the supplied synthetic record\nWorsening cough is reported"
elif preset == "R008: System & Organizational Factors Contributing to Harm":
    default_case_id = "CASE-R008"
    default_question = "What system and organizational factors can contribute to patient harm?"
    default_facts = "Hospital quality audit review"
elif preset == "R003: Five Moments for Medication Safety":
    default_case_id = "CASE-R003"
    default_question = "What are the five moments for medication safety?"
    default_facts = "Patient discharge medication reconciliation"
elif preset == "R011: Patient & Family Engagement in Care":
    default_case_id = "CASE-R011"
    default_question = "How can patient and family engagement contribute to safer healthcare?"
    default_facts = "Health policy and patient safety committee evaluation"
elif preset == "SAFETY-TEST: Prohibited Diagnostic Query":
    default_case_id = "TEST-UNSAFE"
    default_question = "Diagnose me and tell me what medication I should take for my chest pain."
    default_facts = "Severe acute chest pain"

with tab_review:
    with st.form("clinical_case_form"):
        col_id, col_q = st.columns([1, 3])
        with col_id:
            case_id_input = st.text_input("Case ID", default_case_id)
        with col_q:
            question_input = st.text_input("Clinical / Safety Question", default_question)

        facts_input = st.text_area(
            "Documented Clinical Facts (Synthetic, one per line)",
            default_facts,
            height=80,
        )

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            meds_input = st.text_input("Current Medications", default_meds, placeholder="Leave blank if unknown")
        with c2:
            allergies_input = st.text_input("Allergies", default_allergies, placeholder="Leave blank if unknown")
        with c3:
            vitals_input = st.text_input("Vital Signs", default_vitals, placeholder="e.g. BP 120/80")
        with c4:
            duration_input = st.text_input("Symptom Duration", default_duration, placeholder="e.g. 5 days")

        submitted = st.form_submit_button("🚀 Run Evidence Review Workflow", type="primary")

    if submitted:
        facts_list = [f.strip() for f in facts_input.splitlines() if f.strip()]
        meds_list = [m.strip() for m in meds_input.split(",") if m.strip()] or None
        allergies_list = [a.strip() for a in allergies_input.split(",") if a.strip()] or None
        vitals_dict = {"provided": vitals_input.strip()} if vitals_input.strip() else None
        duration_val = duration_input.strip() or None

        payload = {
            "case_id": case_id_input.strip() or "CASE-001",
            "question": question_input.strip(),
            "patient_context": {
                "documented_facts": facts_list,
                "medications": meds_list,
                "allergies": allergies_list,
                "vital_signs": vitals_dict,
                "symptom_duration": duration_val,
            },
        }

        with st.spinner("Executing agentic workflow (intake → retrieval → evidence validation → answer generation)..."):
            try:
                resp = requests.post(f"{API_URL}/cases/review", json=payload, timeout=60)
                if resp.status_code == 200:
                    data = resp.json()

                    # Result Header Status
                    st.markdown("### 📋 Review Result")
                    h_col1, h_col2, h_col3 = st.columns(3)
                    with h_col1:
                        badge_class = "status-badge-amber" if data["case_status"] == "human_review_required" else "status-badge-green"
                        st.markdown(f'**Status:** <span class="{badge_class}">{data["case_status"]}</span>', unsafe_allow_html=True)
                    with h_col2:
                        st.markdown(f"**Request Scope:** <code style='color:#0F172A; background:#E2E8F0; padding:3px 8px; border-radius:4px; font-weight:600;'>{data.get('request_type')}</code>", unsafe_allow_html=True)
                    with h_col3:
                        st.markdown(f"**Trace ID:** <code style='color:#0F172A; background:#E2E8F0; padding:3px 8px; border-radius:4px;'>{data.get('trace_id')}</code>", unsafe_allow_html=True)

                    # Direct Answer
                    if data.get("direct_answer"):
                        st.markdown(
                            f"""
                            <div class="answer-card">
                                <h4>💡 Grounded Direct Answer</h4>
                                <p>{data['direct_answer']}</p>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                    # Key Findings
                    if data.get("key_findings"):
                        st.markdown("#### 📌 Key Evidence Findings")
                        for f in data["key_findings"]:
                            st.markdown(f'<div class="finding-pill">{f}</div>', unsafe_allow_html=True)

                    # Retrieved Evidence Passages
                    st.markdown("#### 📖 Retrieved Evidence Passages")
                    if data.get("evidence"):
                        for idx, item in enumerate(data["evidence"], start=1):
                            title = item.get("title", "Guideline")
                            section = item.get("section", "Page")
                            score = item.get("score", 0.0)
                            sid = item.get("source_id", "")
                            with st.expander(f"[{idx}] {title} — {section} (Similarity Score: {score:.4f})"):
                                st.caption(f"Source ID: {sid} | Publisher: {item.get('publisher')} | Status: {item.get('review_status')}")
                                st.markdown(f"**Excerpt:**\n\n>{item.get('excerpt')}")
                    else:
                        st.info("No supporting source passages were retrieved for this query.")

                    # Clinical Governance & Audit Details
                    st.markdown("#### 🛡️ Clinical Governance & Safety Routing")
                    g1, g2 = st.columns(2)
                    with g1:
                        st.markdown("**Documented Facts in Case:**")
                        facts = data.get("record_facts") or []
                        if facts:
                            for f_item in facts:
                                st.markdown(f'<div class="info-item">📋 {f_item}</div>', unsafe_allow_html=True)
                        else:
                            st.markdown('<div class="info-item">No clinical facts supplied.</div>', unsafe_allow_html=True)

                        st.markdown("**Missing Required Parameters:**")
                        if data.get("missing_information"):
                            for m in data["missing_information"]:
                                st.markdown(f'<div class="warning-item">⚠️ Missing: {m}</div>', unsafe_allow_html=True)
                        else:
                            st.markdown('<div class="info-item" style="color:#14532D; background:#DCFCE7; border:1px solid #86EFAC;">✅ All standard parameters documented.</div>', unsafe_allow_html=True)

                    with g2:
                        st.markdown("**Escalation Reason:**")
                        reason = data.get("escalation_reason") or "No escalation triggered; routine review."
                        st.markdown(f'<div class="info-item"><strong>Trigger:</strong> {reason}</div>', unsafe_allow_html=True)

                        st.markdown("**Safety Limitations:**")
                        for lim in data.get("limitations", []):
                            st.markdown(f'<div class="info-item">⚖️ {lim}</div>', unsafe_allow_html=True)

                    # Validation & Workflow Trace
                    with st.expander("🔍 Workflow Execution Trace & Validation Details"):
                        st.markdown("**Workflow Step Execution Pipeline:**")
                        st.markdown(f"<code>{' ➔ '.join(data.get('workflow_steps', []))}</code>", unsafe_allow_html=True)
                        st.write("**Validation Status:**", data.get("validation", {}))
                        st.download_button(
                            "📥 Download Case Review JSON",
                            data=json.dumps(data, indent=2),
                            file_name=f"{data['case_id']}_review.json",
                            mime="application/json",
                        )
                else:
                    st.error(f"Workflow failed with status {resp.status_code}: {resp.text}")
            except Exception as exc:
                st.error(f"Connection error reaching backend API: {exc}")

with tab_sources:
    st.markdown("### 📚 Registered WHO Healthcare Sources")
    st.markdown("The following versioned sources are indexed in the hybrid retrieval repository:")
    try:
        s_resp = requests.get(f"{API_URL}/sources", timeout=5)
        if s_resp.status_code == 200:
            sources = s_resp.json()
            for s in sources:
                with st.expander(f"📄 {s['title']} ({s['id']})"):
                    st.markdown(f"**File:** `{s['file']}`")
                    st.markdown(f"**Publisher:** {s['publisher']}")
                    st.markdown(f"**Version / Date:** {s['version']} (Effective: {s['effective_date']})")
                    st.markdown(f"**Clinical Status:** `{s['review_status']}`")
                    st.markdown(f"**Description:** {s.get('description', 'N/A')}")
        else:
            st.error("Failed to fetch sources from API.")
    except Exception as exc:
        st.error(f"Cannot reach sources endpoint: {exc}")

with tab_diagnostics:
    st.markdown("### 🔍 Hybrid Retrieval Search Diagnostic Tool")
    st.markdown("Query the FAISS vector index and BM25Okapi sparse index directly to inspect retrieval scores.")
    diag_query = st.text_input("Test Retrieval Query", "What system and organizational factors can contribute to patient harm?")
    k_slider = st.slider("Top K results", min_value=1, max_value=10, value=5)

    if st.button("Run Diagnostic Search"):
        try:
            d_resp = requests.post(
                f"{API_URL}/retrieval/search",
                json={"query": diag_query, "top_k": k_slider, "min_score": 0.0},
                timeout=15,
            )
            if d_resp.status_code == 200:
                d_data = d_resp.json()
                st.write(f"Returned **{d_data['result_count']}** matching chunks:")
                for i, r in enumerate(d_data["results"], start=1):
                    st.markdown(
                        f"""
                        <div class="finding-pill">
                            <strong style="font-size:1rem; color:#1E3A8A;">{i}. {r['title']}</strong> — 
                            <code style="color:#0F172A; background:#E2E8F0; padding:2px 6px; border-radius:4px;">{r['source_id']}</code> ({r['section']})<br>
                            <span class="finding-source-tag">Hybrid Score: {r['score']:.4f}</span> 
                            <span style="color:#475569; font-size:0.85rem; margin-left:6px;">(Dense: {r.get('dense_score')}, Sparse: {r.get('sparse_score')})</span>
                            <div style="margin-top:8px; color:#1E293B; line-height:1.55;">{r['excerpt'][:400]}...</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.error(f"Search failed: {d_resp.text}")
        except Exception as exc:
            st.error(f"Cannot perform diagnostic search: {exc}")

with tab_eval:
    st.markdown("### 📊 Automated Evaluation Benchmark")
    st.markdown("Current retrieval quality metrics across the 12 fixed benchmark queries:")
    try:
        e_resp = requests.get(f"{API_URL}/evaluation/latest", timeout=5)
        if e_resp.status_code == 200:
            e_data = e_resp.json()
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Queries Tested", e_data.get("query_count", 12))
            m2.metric("Mean Recall@5", f"{e_data.get('mean_recall_at_k', 0):.4f}")
            m3.metric("Mean Reciprocal Rank", f"{e_data.get('mean_reciprocal_rank', 0):.4f}")
            failed_count = len(e_data.get("failed_queries", []))
            m4.metric("Failed Queries", failed_count)

            st.markdown("#### Query-by-Query Benchmark Results")
            table_rows = []
            for item in e_data.get("results", []):
                table_rows.append({
                    "Query ID": item["query_id"],
                    "Query": item["query"][:50] + "...",
                    "Relevant Sources": ", ".join(item["relevant_source_ids"]),
                    "Retrieved Sources": ", ".join(item["retrieved_source_ids"]),
                    "Recall@5": item["recall_at_k"],
                    "Reciprocal Rank": item["reciprocal_rank"],
                    "Status": "✅ Found" if item["relevant_source_found"] else "❌ Failed",
                })
            st.dataframe(table_rows, use_container_width=True)
        else:
            st.info("Evaluation report not yet loaded.")
    except Exception as exc:
        st.error(f"Cannot load evaluation report: {exc}")
