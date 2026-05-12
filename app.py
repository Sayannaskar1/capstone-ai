import streamlit as st
from pdf_processor import extract_text_from_pdf, extract_pages
from workflow import compliance_pipeline
from report_generator import generate_pdf_report

st.set_page_config(page_title="Compliance Checker", page_icon="📋",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
/* ── Metric cards ─────────────────────────────────────────────── */
.metric-card {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 20px 24px;
    text-align: center;
}
.metric-label {
    font-size: 10px;
    color: #94a3b8;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .08em;
    margin-bottom: 8px;
}
.metric-value { font-size: 30px; font-weight: 800; line-height: 1.1; color: #f1f5f9; }
.metric-sub   { font-size: 12px; color: #64748b; margin-top: 5px; }

/* ── Status pill ──────────────────────────────────────────────── */
.pill {
    display: inline-block;
    padding: 6px 18px;
    border-radius: 999px;
    font-size: 14px;
    font-weight: 800;
    letter-spacing: .05em;
}
.pill-green { background: #166534; color: #bbf7d0; border: 1px solid #15803d; }
.pill-amber { background: #78350f; color: #fde68a; border: 1px solid #92400e; }
.pill-red   { background: #7f1d1d; color: #fecaca; border: 1px solid #991b1b; }

/* ── Score bar ────────────────────────────────────────────────── */
.bar-wrap { background: #334155; border-radius: 999px; height: 8px; margin-top: 8px; }
.bar-fill  { height: 8px; border-radius: 999px; }
</style>
""", unsafe_allow_html=True)


# ── Rule presets ───────────────────────────────────────────────────────────────
RULE_PRESETS = {
    "Custom (enter your own)": "",

    "Privacy & Security Audit (4 Rules)": (
        "1. If text content contains PII/personal information (email, phone etc..)\n"
        "2. If text contains confidential information (for ex: sensitive company details or IP etc..)\n"
        "3. Encoding consistency UTF-8 across text (only language to be supported : EN)\n"
        "4. No Abusive languages in PDF or any unlawful content"
    ),

    "Standard Legal Contract Review": (
        "1. Document must contain a clearly defined Confidentiality or Non-Disclosure clause.\n"
        "2. The term 'Indemnity' or 'Indemnification' must be clearly defined with scope and limits.\n"
        "3. Applicable governing law and jurisdiction must be explicitly stated.\n"
        "4. Termination conditions and notice period must be specified.\n"
        "5. Dispute resolution mechanism (arbitration or litigation) must be stated."
    ),

    "SLA (Service Level Agreement) Review": (
        "1. Uptime or availability SLA percentage (e.g. 99.9%) must be explicitly defined.\n"
        "2. Incident response and resolution time targets must be specified.\n"
        "3. Penalty or credit clauses for SLA breach must be present.\n"
        "4. Measurement methodology and reporting frequency must be stated.\n"
        "5. Exclusions or force majeure conditions that exempt SLA obligations must be listed."
    ),

}

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    preset_choice = st.selectbox("Compliance Rule Set", list(RULE_PRESETS.keys()),
                                 help="Choose a preset or select Custom.")
    default_text = (
        "1. Document must contain a 'Confidentiality' clause.\n"
        "2. The term 'Indemnity' must be clearly defined.\n"
        "3. Applicable governing law must be stated."
        if preset_choice == "Custom (enter your own)"
        else RULE_PRESETS[preset_choice]
    )
    compliance_rules = st.text_area("Rules (editable)", value=default_text,
                                    height=260, help="Editable even with a preset selected.")
    st.divider()
    st.caption("**Model:** llama3 via Ollama  |  **Pipeline:** LangGraph + RAG")

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("# 📋 Compliance Checker")
st.caption("Upload a PDF, choose a rule set, get a clear compliance report.")
st.divider()

# ── Upload ─────────────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="collapsed")
if uploaded_file is None:
    st.info("👆 Upload a PDF document to get started.", icon="📄")
    st.stop()

st.success(f"**{uploaded_file.name}** uploaded.", icon="✅")
if not st.button("▶  Run Compliance Check", type="primary"):
    st.stop()

# ── Run pipeline ───────────────────────────────────────────────────────────────
with st.spinner("Analysing document…"):
    pdf_bytes  = uploaded_file.read()
    raw_text   = extract_text_from_pdf(pdf_bytes)
    pages_text = extract_pages(pdf_bytes)

    result = compliance_pipeline.invoke({
        "document_text":    raw_text,
        "compliance_rules": compliance_rules,
        "analysis_report":  "",
        "rule_results":     [],
        "final_score":      0.0,
        "overall_status":   "",
        "pages_text":       pages_text,
        "page_results":     [],
    })

rule_results   = result.get("rule_results", [])
final_score    = result.get("final_score", 0.0)
overall_status = result.get("overall_status", "NON-COMPLIANT")
n_total = len(rule_results)
n_c  = sum(1 for r in rule_results if r["status"] == "COMPLIANT")
n_p  = sum(1 for r in rule_results if r["status"] == "PARTIAL")
n_nc = sum(1 for r in rule_results if r["status"] == "NON-COMPLIANT")

# ── Overall verdict ────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Overall Verdict")
pill_class = {"COMPLIANT":"pill-green","PARTIAL":"pill-amber","NON-COMPLIANT":"pill-red"}.get(overall_status,"pill-red")
pill_icon  = {"COMPLIANT":"✔","PARTIAL":"~","NON-COMPLIANT":"✘"}.get(overall_status,"?")
bar_color  = {"COMPLIANT":"#22c55e","PARTIAL":"#f59e0b","NON-COMPLIANT":"#ef4444"}.get(overall_status,"#94a3b8")

c1,c2,c3,c4,c5 = st.columns([2,2,1,1,1])
with c1:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Status</div>'
                f'<span class="pill {pill_class}">{pill_icon}&nbsp; {overall_status}</span></div>',
                unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Compliance Score</div>'
                f'<div class="metric-value" style="color:{bar_color}">{final_score}'
                f'<span style="font-size:16px;color:#64748b">/100</span></div>'
                f'<div class="bar-wrap"><div class="bar-fill" style="width:{final_score}%;background:{bar_color}"></div></div>'
                f'</div>', unsafe_allow_html=True)
with c3:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Compliant</div>'
                f'<div class="metric-value" style="color:#4ade80">{n_c}</div>'
                f'<div class="metric-sub">of {n_total} rules</div></div>', unsafe_allow_html=True)
with c4:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Partial</div>'
                f'<div class="metric-value" style="color:#fbbf24">{n_p}</div>'
                f'<div class="metric-sub">of {n_total} rules</div></div>', unsafe_allow_html=True)
with c5:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Non-Compliant</div>'
                f'<div class="metric-value" style="color:#f87171">{n_nc}</div>'
                f'<div class="metric-sub">of {n_total} rules</div></div>', unsafe_allow_html=True)

# ── Rule-by-rule results ───────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Rule-by-Rule Results")
st.caption("Each rule evaluated against the full document. Page numbers show where evidence was found.")

STATUS_CFG = {
    "COMPLIANT":     ("✔", "#16a34a", "#dcfce755"),
    "PARTIAL":       ("~", "#d97706", "#fef9c355"),
    "NON-COMPLIANT": ("✘", "#dc2626", "#fee2e255"),
}

for idx, r in enumerate(rule_results, 1):
    status     = r.get("status", "NON-COMPLIANT")
    score      = r.get("compliance_score", 0)
    conf       = r.get("llm_confidence", 0)
    explanation= r.get("explanation", "")
    rule_text  = r.get("rule", "")
    pages      = r.get("evidence_pages", [])
    icon, color, bg = STATUS_CFG.get(status, ("?","#94a3b8","#f1f5f9"))

    page_badge = ""
    if pages:
        label = "Found on" if status == "COMPLIANT" else "Evidence on"
        page_badge = (f'&nbsp;&nbsp;<span style="font-size:11px;color:#3b82f6;font-weight:600;">'
                      f'📄 {label} pg {pages}</span>')

    st.markdown(
        f'<div style="border-left:5px solid {color};background:#ffffff;'
        f'border:1px solid #e2e8f0;border-radius:10px;padding:16px 20px;margin-bottom:12px;"'
        f'>'
        f'<div style="font-size:14px;font-weight:800;color:#0f172a;margin-bottom:6px;">'
        f'Rule {idx}&nbsp;&nbsp;<span style="color:{color};font-size:13px;">{icon} {status}</span>'
        f'<span style="font-size:11px;color:#475569;font-weight:500;margin-left:10px;">'
        f'Score: {int(score)}/100 &nbsp;·&nbsp; Confidence: {conf}%</span>{page_badge}</div>'
        f'<div style="font-size:12px;color:#475569;font-style:italic;margin-bottom:7px;line-height:1.5;">{rule_text}</div>'
        f'<div style="font-size:13px;color:#1e293b;line-height:1.6;font-weight:500;">{explanation}</div>'
        f'</div>', unsafe_allow_html=True)

# ── Downloads ──────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Download Report")
c_pdf, c_txt, _ = st.columns([1,1,3])

with c_pdf:
    try:
        pdf_out = generate_pdf_report(
            rule_results=rule_results, final_score=final_score,
            overall_status=overall_status, document_name=uploaded_file.name,
            page_results=[],
        )
        st.download_button("⬇  Download PDF Report", data=pdf_out,
                           file_name="compliance_report.pdf",
                           mime="application/pdf", use_container_width=True)
    except Exception as e:
        st.warning(f"PDF export error: {e}")

with c_txt:
    st.download_button("⬇  Download TXT Report", data=result["analysis_report"],
                       file_name="compliance_report.txt", mime="text/plain",
                       use_container_width=True)
