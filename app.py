import streamlit as st
import plotly.graph_objects as go
import json, hashlib, time
from datetime import datetime
from pdf_processor import extract_all
from workflow import compliance_pipeline
from report_generator import generate_pdf_report
from styles import CUSTOM_CSS
import storage

# ── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ComplianceAI · Enterprise Scanner",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ── Plotly theme helper ────────────────────────────────────────────────────────
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#94a3b8", size=12),
    margin=dict(t=30, b=30, l=30, r=30),
)

# ── Caching ────────────────────────────────────────────────────────────────────
@st.cache_resource
def _load_embedding_model():
    from rag_utils import get_embedding_model
    return get_embedding_model()

@st.cache_data(show_spinner=False)
def _extract_pdf(file_hash: str, pdf_bytes: bytes):
    return extract_all(pdf_bytes)

# ── Session State ──────────────────────────────────────────────────────────────
for key, default in [
    ("scan_results", None),
    ("doc_stats", None),
    ("uploaded_filename", None),
    ("scan_timestamp", None),
    ("editing_rule", None),
    ("show_rule_editor", False),
    ("show_history", False),
    ("history_view_id", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

if "rules" not in st.session_state:
    st.session_state.rules = [
        "If text content contains PII/personal information (email, phone etc..)",
        "If text contains confidential information (for ex: sensitive company details or IP etc..)",
        "Encoding consistency UTF-8 across text (only language to be supported : EN)",
        "No Abusive languages in PDF or any unlawful content",
    ]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SIDEBAR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with st.sidebar:
    # Brand
    st.markdown(
        '<div class="sb-brand">'
        '  <div class="sb-brand-icon">🛡️</div>'
        '  <div class="sb-brand-text">'
        '    <h3>ComplianceAI</h3>'
        '    <span>Document Scanner</span>'
        '  </div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Upload
    st.markdown('<div class="sb-section">📁 Document Upload</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="collapsed")

    # Rules — compact chip + edit button
    st.markdown('<div class="sb-section">📋 Compliance Rules</div>', unsafe_allow_html=True)
    rc = len(st.session_state.rules)
    st.markdown(
        f'<div class="sb-rule-chip">'
        f'  <div class="sb-rule-chip-left">'
        f'    <div class="sb-rule-chip-icon">📋</div>'
        f'    <div><div class="sb-rule-chip-text">{rc} Active Rule{"s" if rc != 1 else ""}</div>'
        f'    <div class="sb-rule-chip-sub">Click edit to manage</div></div>'
        f'  </div>'
        f'  <div class="sb-rule-count">{rc}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if st.button("✏️ Edit Rules", key="sb_edit_rules", use_container_width=True):
        st.session_state.show_rule_editor = not st.session_state.show_rule_editor
        st.rerun()

    # Preset loader
    preset = st.selectbox("Load Preset", ["—", "🔒 Privacy & Security", "⚖️ Legal Contracts", "📊 SLA Compliance"], label_visibility="collapsed")
    PRESETS = {
        "🔒 Privacy & Security": [
            "If text content contains PII/personal information (email, phone etc..)",
            "If text contains confidential information (sensitive company details or IP)",
            "Encoding consistency UTF-8 across text (only EN supported)",
            "No Abusive languages in PDF or any unlawful content",
        ],
        "⚖️ Legal Contracts": [
            "Document must contain a clearly defined Confidentiality or Non-Disclosure clause",
            "The term Indemnity or Indemnification must be clearly defined with scope and limits",
            "Applicable governing law and jurisdiction must be explicitly stated",
            "Termination conditions and notice period must be specified",
            "Dispute resolution mechanism (arbitration or litigation) must be stated",
        ],
        "📊 SLA Compliance": [
            "Uptime or availability SLA percentage (e.g. 99.9%) must be explicitly defined",
            "Incident response and resolution time targets must be specified",
            "Penalty or credit clauses for SLA breach must be present",
            "Measurement methodology and reporting frequency must be stated",
        ],
    }
    if preset != "—" and preset in PRESETS:
        st.session_state.rules = PRESETS[preset]
        st.rerun()

    # Run & History
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_run, col_hist = st.columns([3, 1])
    with col_run:
        run_scan = st.button("🚀 Run Scan", type="primary", use_container_width=True)
    with col_hist:
        if st.button("📂", help="View Scan History", use_container_width=True):
            st.session_state.show_history = not st.session_state.show_history
            st.session_state.show_rule_editor = False
            st.rerun()

    # System Info
    st.markdown('<div class="sb-section" style="margin-top:28px;">⚙️ System</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sb-info-card">'
        '  <div class="sb-info-row"><span class="sb-info-key"><span class="sb-dot sb-dot-green"></span>Status</span><span class="sb-info-val">Online</span></div>'
        '  <div class="sb-info-row"><span class="sb-info-key">Model</span><span class="sb-info-val">llama3 · 8B</span></div>'
        '  <div class="sb-info-row"><span class="sb-info-key">Pipeline</span><span class="sb-info-val">LangGraph</span></div>'
        '  <div class="sb-info-row"><span class="sb-info-key">RAG</span><span class="sb-info-val">FAISS + MiniLM</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BACKEND EXECUTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if run_scan:
    if not uploaded_file:
        st.sidebar.error("Please upload a PDF document first.")
    else:
        pdf_bytes = uploaded_file.read()
        doc_data = _extract_pdf(hashlib.md5(pdf_bytes).hexdigest(), pdf_bytes)

        st.session_state.doc_stats = {
            "page_count": doc_data["page_count"],
            "word_count": doc_data["word_count"],
        }
        st.session_state.uploaded_filename = uploaded_file.name
        st.session_state.scan_timestamp = datetime.now().strftime("%d %b %Y · %H:%M")

        compliance_rules = "\n".join(f"{i+1}. {r}" for i, r in enumerate(st.session_state.rules))
        import concurrent.futures, time

        pipeline_input = {
            "document_text": doc_data["full_text"],
            "compliance_rules": compliance_rules,
            "analysis_report": "",
            "rule_results": [],
            "final_score": 0.0,
            "overall_status": "",
            "pages_text": doc_data["pages"],
            "page_results": [],
        }

        status_box = st.empty()
        progress_box = st.empty()

        status_box.info("⏳ Running GenAI compliance pipeline…")

        try:
            elapsed = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(compliance_pipeline.invoke, pipeline_input)
                while not future.done():
                    time.sleep(0.3)
                    elapsed += 0.3
                    progress_box.caption(f"⏱ Elapsed: {elapsed:.0f}s — press **Stop** in header to cancel")
                result = future.result()

            progress_box.empty()
            status_box.success("✅ Scan complete")
            st.session_state.scan_results = result
            
            # Save to storage
            storage.save_scan(
                filename=st.session_state.uploaded_filename,
                scan_timestamp=st.session_state.scan_timestamp,
                page_count=st.session_state.doc_stats["page_count"],
                word_count=st.session_state.doc_stats["word_count"],
                final_score=result["final_score"],
                overall_status=result["overall_status"],
                rules_used=st.session_state.rules,
                rule_results=result["rule_results"],
                analysis_report=result["analysis_report"]
            )
        except Exception as e:
            progress_box.empty()
            status_box.error(f"⛔ Scan failed: {str(e)}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RULE EDITOR (standalone, toggled from sidebar)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if st.session_state.show_rule_editor:
    _rc = len(st.session_state.rules)

    # Close button row
    _, _close_col = st.columns([10, 1])
    with _close_col:
        if st.button("✕ Close", key="close_rule_editor"):
            st.session_state.show_rule_editor = False
            st.session_state.editing_rule = None
            st.rerun()

    st.markdown(
        f'<div class="rm-header">'
        f'  <div><div class="rm-title">Rule Configuration <span class="rm-title-badge">{_rc} rules</span></div>'
        f'  <div class="rm-subtitle">Add, edit, or remove compliance rules. Changes apply to the next scan.</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    _rules_to_delete = None
    for _i, _rule_text in enumerate(st.session_state.rules):
        if st.session_state.editing_rule == _i:
            _c1, _c2, _c3 = st.columns([8, 1, 1])
            with _c1:
                _new_val = st.text_input(f"e{_i}", value=_rule_text, label_visibility="collapsed", key=f"main_edit_{_i}")
            with _c2:
                if st.button("Save", key=f"main_save_{_i}", type="primary"):
                    st.session_state.rules[_i] = _new_val
                    st.session_state.editing_rule = None
                    st.rerun()
            with _c3:
                if st.button("Cancel", key=f"main_cancel_{_i}"):
                    st.session_state.editing_rule = None
                    st.rerun()
        else:
            _cr, _ce, _cd = st.columns([14, 1, 1])
            with _cr:
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:12px;padding:10px 14px;'
                    f'background:#1e293b;border:1px solid #334155;border-radius:10px;min-height:44px;">'
                    f'<span style="background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.2);'
                    f'color:#818cf8;font-weight:800;font-size:12px;width:28px;height:28px;border-radius:7px;'
                    f'display:flex;align-items:center;justify-content:center;flex-shrink:0;">{_i+1}</span>'
                    f'<span style="color:#f8fafc;font-size:13px;font-weight:500;line-height:1.4;">{_rule_text}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with _ce:
                if st.button("✏️", key=f"main_btn_edit_{_i}", help="Edit rule"):
                    st.session_state.editing_rule = _i
                    st.rerun()
            with _cd:
                if st.button("🗑", key=f"main_btn_del_{_i}", help="Delete rule"):
                    _rules_to_delete = _i

    if _rules_to_delete is not None:
        st.session_state.rules.pop(_rules_to_delete)
        st.rerun()

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    _cn, _ca = st.columns([12, 1])
    with _cn:
        _new_rule = st.text_input("add", placeholder="Type a new compliance rule…", label_visibility="collapsed", key="main_new_rule")
    with _ca:
        if st.button("＋", key="main_btn_add", type="primary", help="Add rule"):
            if _new_rule and _new_rule.strip():
                st.session_state.rules.append(_new_rule.strip())
                st.rerun()

    st.markdown("---")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN DASHBOARD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ---------- History View ----------
if st.session_state.show_history:
    st.markdown("<h2>📂 Scan History</h2><p style='color:#94a3b8; margin-bottom:24px;'>View past PDF compliance reports and results.</p>", unsafe_allow_html=True)
    scans = storage.get_all_scans()
    if not scans:
        st.info("No past scans found. Run a compliance scan to save history.")
    else:
        for s in scans:
            c1, c2, c3, c4 = st.columns([4, 2, 2, 2])
            with c1:
                st.markdown(f"**📄 {s['filename']}**<br><span style='color:#64748b; font-size:12px;'>{s['scan_timestamp']}</span>", unsafe_allow_html=True)
            with c2:
                color = "#10b981" if s['overall_status'] == "COMPLIANT" else "#f59e0b" if s['overall_status'] == "PARTIAL" else "#f43f5e"
                st.markdown(f"<strong style='color:{color}'>{s['overall_status']}</strong>", unsafe_allow_html=True)
            with c3:
                st.markdown(f"**Score:** {s['final_score']}/100")
            with c4:
                if st.button("View Report", key=f"hist_view_{s['id']}", type="secondary", use_container_width=True):
                    # Load from history into session state
                    st.session_state.scan_results = {
                        "final_score": s["final_score"],
                        "overall_status": s["overall_status"],
                        "rule_results": s["rule_results"],
                        "analysis_report": s["analysis_report"],
                    }
                    st.session_state.doc_stats = {
                        "page_count": s["page_count"],
                        "word_count": s["word_count"]
                    }
                    st.session_state.uploaded_filename = s["filename"]
                    st.session_state.scan_timestamp = s["scan_timestamp"]
                    st.session_state.show_history = False
                    st.rerun()
            st.markdown("---")
    st.stop()

# ---------- Empty State ----------
if st.session_state.scan_results is None:
    if not st.session_state.show_rule_editor:
        rc = len(st.session_state.rules)
        st.markdown('''
        <style>
        @keyframes float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-8px)} }
        @keyframes pulse-glow { 0%,100%{box-shadow:0 0 20px rgba(99,102,241,0.2)} 50%{box-shadow:0 0 40px rgba(99,102,241,0.4)} }
        @keyframes gradient-shift { 0%{background-position:0% 50%} 50%{background-position:100% 50%} 100%{background-position:0% 50%} }
        .hero-section { text-align:center; padding:48px 20px 32px; }
        .hero-icon { width:80px; height:80px; margin:0 auto 24px; background:linear-gradient(135deg,#4f46e5,#7c3aed,#6366f1); border-radius:22px; display:flex; align-items:center; justify-content:center; font-size:36px; animation:float 3s ease-in-out infinite, pulse-glow 3s ease-in-out infinite; }
        .hero-title { font-size:28px; font-weight:800; color:#f8fafc; letter-spacing:-0.03em; margin-bottom:8px; }
        .hero-gradient { background:linear-gradient(90deg,#818cf8,#a78bfa,#c084fc,#818cf8); background-size:200%; -webkit-background-clip:text; -webkit-text-fill-color:transparent; animation:gradient-shift 4s ease infinite; }
        .hero-sub { font-size:14px; color:#64748b; max-width:500px; margin:0 auto; line-height:1.6; }
        .steps-row { display:flex; justify-content:center; gap:40px; margin:36px 0 40px; }
        .step-item { display:flex; align-items:center; gap:10px; }
        .step-num { width:32px; height:32px; border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:16px; }
        .step-1 { background:linear-gradient(135deg,#3b82f6,#60a5fa); }
        .step-2 { background:linear-gradient(135deg,#f59e0b,#fbbf24); }
        .step-3 { background:linear-gradient(135deg,#10b981,#34d399); }
        .step-text { font-size:12px; font-weight:600; color:#94a3b8; }
        .step-line { width:40px; height:2px; background:linear-gradient(90deg,#334155,#475569); border-radius:2px; }
        .features-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:16px; max-width:900px; margin:0 auto 36px; }
        .feat-card { background:#1e293b; border:1px solid #334155; border-radius:14px; padding:24px 20px; text-align:center; transition:all 0.3s ease; cursor:default; position:relative; overflow:hidden; }
        .feat-card::before { content:''; position:absolute; top:0; left:0; right:0; height:3px; border-radius:14px 14px 0 0; }
        .feat-card:nth-child(1)::before { background:linear-gradient(90deg,#f43f5e,#fb7185); }
        .feat-card:nth-child(2)::before { background:linear-gradient(90deg,#6366f1,#818cf8); }
        .feat-card:nth-child(3)::before { background:linear-gradient(90deg,#10b981,#34d399); }
        .feat-card:hover { transform:translateY(-4px); border-color:#475569; box-shadow:0 8px 25px rgba(0,0,0,0.3); }
        .feat-icon { width:48px; height:48px; border-radius:12px; display:flex; align-items:center; justify-content:center; font-size:22px; margin:0 auto 14px; }
        .fi-1 { background:rgba(244,63,94,0.1); }
        .fi-2 { background:rgba(99,102,241,0.1); }
        .fi-3 { background:rgba(16,185,129,0.1); }
        .feat-title { font-size:14px; font-weight:700; color:#f8fafc; margin-bottom:6px; }
        .feat-desc { font-size:11px; color:#64748b; line-height:1.5; }
        .info-bar { display:flex; justify-content:center; gap:32px; padding:16px; background:#1e293b; border:1px solid #334155; border-radius:12px; max-width:600px; margin:0 auto; }
        .info-item { text-align:center; }
        .info-val { font-size:18px; font-weight:800; color:#818cf8; }
        .info-label { font-size:10px; color:#64748b; text-transform:uppercase; letter-spacing:0.06em; margin-top:2px; }
        </style>

        <div class="hero-section">
            <div class="hero-icon">🛡️</div>
            <div class="hero-title">AI-Powered <span class="hero-gradient">Compliance Scanner</span></div>
            <div class="hero-sub">Enterprise-grade document analysis powered by GenAI. Scan PDFs for PII, confidential data, encoding issues, and policy violations in seconds.</div>
        </div>

        <div class="steps-row">
            <div class="step-item"><div class="step-num step-1">📁</div><div class="step-text">Upload PDF</div></div>
            <div class="step-line"></div>
            <div class="step-item"><div class="step-num step-2">⚙️</div><div class="step-text">Configure Rules</div></div>
            <div class="step-line"></div>
            <div class="step-item"><div class="step-num step-3">🚀</div><div class="step-text">Run Scan</div></div>
        </div>

        <div class="features-grid">
            <div class="feat-card">
                <div class="feat-icon fi-1">🔍</div>
                <div class="feat-title">PII Detection</div>
                <div class="feat-desc">Automatically detect emails, phone numbers, and personal identifiers across all pages</div>
            </div>
            <div class="feat-card">
                <div class="feat-icon fi-2">📋</div>
                <div class="feat-title">Clause Verification</div>
                <div class="feat-desc">Verify presence of required legal clauses, NDA terms, and compliance statements</div>
            </div>
            <div class="feat-card">
                <div class="feat-icon fi-3">⚡</div>
                <div class="feat-title">Encoding Audit</div>
                <div class="feat-desc">Validate UTF-8 encoding consistency and detect foreign-language content violations</div>
            </div>
        </div>

        <div class="info-bar">
            <div class="info-item"><div class="info-val">''' + str(rc) + '''</div><div class="info-label">Active Rules</div></div>
            <div class="info-item"><div class="info-val">LLM</div><div class="info-label">Powered By</div></div>
            <div class="info-item"><div class="info-val">&lt;10s</div><div class="info-label">Scan Speed</div></div>
            <div class="info-item"><div class="info-val">PDF</div><div class="info-label">Export</div></div>
        </div>
        ''', unsafe_allow_html=True)
    st.stop()

# ---------- Results Extraction ----------
res = st.session_state.scan_results
stats = st.session_state.doc_stats
rr = res.get("rule_results", [])
fs = float(res.get("final_score", 0))
os_ = res.get("overall_status", "NON-COMPLIANT")

nt = len(rr)
nc = sum(1 for r in rr if r.get("status") == "COMPLIANT")
np_ = sum(1 for r in rr if r.get("status") == "PARTIAL")
nn = sum(1 for r in rr if r.get("status") == "NON-COMPLIANT")

scores = [float(r.get("compliance_score", 0)) for r in rr]
confs = [int(r.get("llm_confidence", 0)) for r in rr]

status_cls = "status-clean" if os_ == "COMPLIANT" else "status-warn" if os_ == "PARTIAL" else "status-flagged"
score_color = "#10b981" if os_ == "COMPLIANT" else "#f59e0b" if os_ == "PARTIAL" else "#f43f5e"

# ---------- Header ----------
st.markdown(
    f'<div class="dash-header">'
    f'  <div class="dash-header-left">'
    f'    <h1>📊 Compliance Report</h1>'
    f'    <p>Analysis of <b>{st.session_state.uploaded_filename}</b> · {st.session_state.scan_timestamp}</p>'
    f'  </div>'
    f'  <div class="status-badge {status_cls}">{os_} · {fs}/100</div>'
    f'</div>',
    unsafe_allow_html=True,
)

# ---------- Metric Cards ----------
st.markdown(
    f'''
    <div class="metric-grid">
        <div class="metric-card mc-blue">
            <div class="metric-icon mi-blue">📄</div>
            <div class="metric-label">Pages Scanned</div>
            <div class="metric-value">{stats["page_count"]}</div>
            <div class="metric-sub">{stats["word_count"]:,} words total</div>
        </div>
        <div class="metric-card mc-amber">
            <div class="metric-icon mi-amber">⚡</div>
            <div class="metric-label">Rules Evaluated</div>
            <div class="metric-value">{nt}</div>
            <div class="metric-sub">Batched LLM analysis</div>
        </div>
        <div class="metric-card mc-emerald">
            <div class="metric-icon mi-emerald">✅</div>
            <div class="metric-label">Rules Passed</div>
            <div class="metric-value">{nc}</div>
            <div class="metric-sub">{round(nc/max(nt,1)*100)}% pass rate</div>
        </div>
        <div class="metric-card mc-rose">
            <div class="metric-icon mi-rose">🚩</div>
            <div class="metric-label">Flagged Issues</div>
            <div class="metric-value">{nn + np_}</div>
            <div class="metric-sub">{nn} failed · {np_} partial</div>
        </div>
    </div>
    ''',
    unsafe_allow_html=True,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TABBED RESULTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
tab_dashboard, tab_findings, tab_rules, tab_export = st.tabs(["📈 Dashboard", "🔍 Detailed Findings", "⚙️ Rules", "📥 Export"])


# ─── TAB 1: DASHBOARD (CHARTS) ─────────────────────────────────────────────
with tab_dashboard:

    # Row 1: Gauge + Donut
    col_gauge, col_donut = st.columns(2)

    with col_gauge:
        st.markdown(
            '<div class="chart-card">'
            '  <div class="chart-card-title">Compliance Score Gauge</div>'
            '  <div class="chart-card-sub">Overall document compliance health</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=fs,
            number=dict(font=dict(color=score_color, size=48), suffix="/100"),
            delta=dict(reference=70, increasing_color="#10b981", decreasing_color="#f43f5e"),
            gauge=dict(
                axis=dict(range=[0, 100], tickfont=dict(color="#475569"), tickcolor="#334155"),
                bar=dict(color=score_color, thickness=0.25),
                bgcolor="#1e293b",
                borderwidth=0,
                steps=[
                    dict(range=[0, 40], color="rgba(244,63,94,0.08)"),
                    dict(range=[40, 70], color="rgba(245,158,11,0.08)"),
                    dict(range=[70, 100], color="rgba(16,185,129,0.08)"),
                ],
                threshold=dict(line=dict(color="#6366f1", width=3), thickness=0.8, value=fs),
            ),
        ))
        fig.update_layout(**PLOTLY_LAYOUT, height=320)
        st.plotly_chart(fig, use_container_width=True)

    with col_donut:
        st.markdown(
            '<div class="chart-card">'
            '  <div class="chart-card-title">Status Distribution</div>'
            '  <div class="chart-card-sub">Breakdown of rule evaluation results</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        fig = go.Figure(go.Pie(
            labels=["Compliant", "Partial", "Non-Compliant"],
            values=[nc, np_, nn],
            hole=0.65,
            marker=dict(colors=["#10b981", "#f59e0b", "#f43f5e"]),
            textfont=dict(size=13, color="white"),
            textinfo="label+percent",
            hoverinfo="label+value+percent",
        ))
        fig.update_layout(
            **PLOTLY_LAYOUT,
            height=320,
            showlegend=False,
            annotations=[dict(
                text=f"<b>{nc}/{nt}</b><br><span style='font-size:10px;color:#64748b'>Passed</span>",
                x=0.5, y=0.5, font=dict(size=24, color="#f8fafc"), showarrow=False,
            )],
        )
        st.plotly_chart(fig, use_container_width=True)

    # Row 2: Radar + Bar
    col_radar, col_bar = st.columns(2)

    with col_radar:
        st.markdown(
            '<div class="chart-card">'
            '  <div class="chart-card-title">Rule Coverage Radar</div>'
            '  <div class="chart-card-sub">Score distribution across all compliance rules</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        labels = [f"Rule {i+1}" for i in range(nt)]
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=scores + [scores[0]] if scores else [],
            theta=labels + [labels[0]] if labels else [],
            fill="toself",
            fillcolor="rgba(99,102,241,0.12)",
            line=dict(color="#818cf8", width=2),
            name="Score",
        ))
        fig.add_trace(go.Scatterpolar(
            r=confs + [confs[0]] if confs else [],
            theta=labels + [labels[0]] if labels else [],
            fill="toself",
            fillcolor="rgba(16,185,129,0.08)",
            line=dict(color="#34d399", width=1.5, dash="dot"),
            name="Confidence",
        ))
        fig.update_layout(
            **PLOTLY_LAYOUT,
            height=360,
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100], gridcolor="#334155", tickfont=dict(color="#475569")),
                angularaxis=dict(gridcolor="#334155", tickfont=dict(color="#94a3b8")),
                bgcolor="rgba(0,0,0,0)",
            ),
            legend=dict(orientation="h", y=-0.1, font=dict(color="#94a3b8", size=11)),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_bar:
        st.markdown(
            '<div class="chart-card">'
            '  <div class="chart-card-title">Rule-by-Rule Scores</div>'
            '  <div class="chart-card-sub">Individual compliance score with confidence markers</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        bar_labels = [f"Rule {i+1}" for i in range(nt)]
        bar_colors = [
            "#10b981" if r.get("status") == "COMPLIANT"
            else "#f59e0b" if r.get("status") == "PARTIAL"
            else "#f43f5e"
            for r in rr
        ]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=bar_labels, x=scores, orientation="h",
            name="Score",
            marker=dict(color=bar_colors, line=dict(width=0)),
            text=[f"{int(s)}" for s in scores],
            textposition="auto",
            textfont=dict(color="white", size=12, family="Inter"),
        ))
        fig.add_trace(go.Scatter(
            y=bar_labels, x=confs,
            mode="markers+text",
            name="Confidence",
            marker=dict(color="#6366f1", size=10, symbol="diamond"),
            text=[f"{c}%" for c in confs],
            textposition="middle right",
            textfont=dict(color="#818cf8", size=10),
        ))
        fig.update_layout(
            **PLOTLY_LAYOUT,
            height=max(300, nt * 65 + 60),
            xaxis=dict(range=[0, 115], gridcolor="rgba(51,65,85,0.5)", zeroline=False),
            yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)"),
            barmode="overlay",
            legend=dict(orientation="h", y=-0.15, font=dict(color="#94a3b8", size=11)),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Row 3: Risk Heatmap Bar
    st.markdown(
        '<div class="chart-card">'
        '  <div class="chart-card-title">Risk Severity Distribution</div>'
        '  <div class="chart-card-sub">Aggregated risk levels across all evaluated rules</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    def _risk(score, conf):
        if score < 40 or conf < 40: return "High"
        if score < 70 or conf < 65: return "Medium"
        return "Low"

    risk_labels = [_risk(s, c) for s, c in zip(scores, confs)]
    n_high = risk_labels.count("High")
    n_med = risk_labels.count("Medium")
    n_low = risk_labels.count("Low")

    fig = go.Figure()
    for name, val, color in [("High Risk", n_high, "#f43f5e"), ("Medium Risk", n_med, "#f59e0b"), ("Low Risk", n_low, "#10b981")]:
        fig.add_trace(go.Bar(
            x=[name], y=[val], name=name,
            marker=dict(color=color, line=dict(width=0)),
            text=[val], textposition="auto", textfont=dict(color="white", size=16, family="Inter"),
        ))
    fig.update_layout(
        **PLOTLY_LAYOUT,
        height=250,
        showlegend=False,
        xaxis=dict(gridcolor="rgba(0,0,0,0)"),
        yaxis=dict(gridcolor="rgba(51,65,85,0.3)"),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── TAB 2: DETAILED FINDINGS ──────────────────────────────────────────────
with tab_findings:
    for idx, r in enumerate(rr, 1):
        s = r.get("status", "NON-COMPLIANT")
        pill_cls = "pill-pass" if s == "COMPLIANT" else "pill-warn" if s == "PARTIAL" else "pill-fail"
        body_cls = "fb-pass" if s == "COMPLIANT" else "fb-warn" if s == "PARTIAL" else "fb-fail"
        icon = "✅" if s == "COMPLIANT" else "⚠️" if s == "PARTIAL" else "🚩"
        sc = float(r.get("compliance_score", 0))
        cf = int(r.get("llm_confidence", 0))
        with st.expander(f"{icon}  Rule {idx} — {s}", expanded=(s != "COMPLIANT")):
            meta_html = ""
            meta_html += f'<span>🎯 Score: {int(sc)}/100</span>'
            meta_html += f'<span>🔒 Confidence: {cf}%</span>'

            st.markdown(
                f'<div class="finding-box">'
                f'  <div class="finding-header">'
                f'    <div class="finding-rule">{r.get("rule", "")}</div>'
                f'    <div class="finding-pill {pill_cls}">{s}</div>'
                f'  </div>'
                f'  <div class="finding-body {body_cls}">'
                f'    <b>AI Analysis:</b> {r.get("explanation", "No details.")}'
                f'  </div>'
                f'  <div class="finding-meta">{meta_html}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )



# ─── TAB 3: RULES ──────────────────────────────────────────────────────────
with tab_rules:
    rc = len(st.session_state.rules)
    st.markdown(
        f'<div class="rm-header">'
        f'  <div><div class="rm-title">Rule Configuration <span class="rm-title-badge">{rc} rules</span></div>'
        f'  <div class="rm-subtitle">Add, edit, or remove compliance rules. Changes apply to the next scan.</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    rules_to_delete = None
    for i, rule_text in enumerate(st.session_state.rules):
        if st.session_state.editing_rule == i:
            col_input, col_save, col_cancel = st.columns([8, 1, 1])
            with col_input:
                new_val = st.text_input(f"e{i}", value=rule_text, label_visibility="collapsed", key=f"edit_input_{i}")
            with col_save:
                if st.button("Save", key=f"save_{i}", type="primary"):
                    st.session_state.rules[i] = new_val
                    st.session_state.editing_rule = None
                    st.rerun()
            with col_cancel:
                if st.button("Cancel", key=f"cancel_{i}"):
                    st.session_state.editing_rule = None
                    st.rerun()
        else:
            col_rule, col_edit, col_del = st.columns([14, 1, 1])
            with col_rule:
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:12px;padding:10px 14px;'
                    f'background:#1e293b;border:1px solid #334155;border-radius:10px;min-height:44px;">'
                    f'<span style="background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.2);'
                    f'color:#818cf8;font-weight:800;font-size:12px;width:28px;height:28px;border-radius:7px;'
                    f'display:flex;align-items:center;justify-content:center;flex-shrink:0;">{i+1}</span>'
                    f'<span style="color:#f8fafc;font-size:13px;font-weight:500;line-height:1.4;">{rule_text}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with col_edit:
                if st.button("✏️", key=f"btn_edit_{i}", help="Edit rule"):
                    st.session_state.editing_rule = i
                    st.rerun()
            with col_del:
                if st.button("🗑", key=f"btn_del_{i}", help="Delete rule"):
                    rules_to_delete = i

    if rules_to_delete is not None:
        st.session_state.rules.pop(rules_to_delete)
        st.rerun()

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    col_new, col_add = st.columns([12, 1])
    with col_new:
        new_rule = st.text_input("add", placeholder="Type a new compliance rule…", label_visibility="collapsed", key="new_rule_input")
    with col_add:
        if st.button("＋", key="btn_add_rule", type="primary", help="Add rule"):
            if new_rule and new_rule.strip():
                st.session_state.rules.append(new_rule.strip())
                st.rerun()


# ─── TAB 4: EXPORT ─────────────────────────────────────────────────────────
with tab_export:
    st.markdown(
        '<div class="export-panel">'
        '  <div class="export-title">📥 Download Official Compliance Report</div>'
        '  <div class="export-sub">Export the full audit trail with AI confidence scores, risk levels, and page-level evidence.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        try:
            pdf_out = generate_pdf_report(
                rule_results=rr,
                final_score=fs,
                overall_status=os_,
                document_name=st.session_state.uploaded_filename,
                page_results=[],
                doc_stats=stats,
            )
            st.download_button(
                "📄 PDF Report", data=pdf_out,
                file_name="compliance_audit.pdf", mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"PDF generation error: {e}")

    with c2:
        st.download_button(
            "📝 TXT Report",
            data=res.get("analysis_report", ""),
            file_name="compliance_audit.txt",
            mime="text/plain",
            use_container_width=True,
        )

    with c3:
        jd = json.dumps(
            {
                "document": st.session_state.uploaded_filename,
                "status": os_,
                "score": fs,
                "timestamp": st.session_state.scan_timestamp,
                "stats": stats,
                "rules": rr,
            },
            indent=2,
        )
        st.download_button(
            "🗂️ JSON Data",
            data=jd,
            file_name="compliance_audit.json",
            mime="application/json",
            use_container_width=True,
        )
