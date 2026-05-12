"""
report_generator.py
Generates a polished, downloadable PDF compliance report using ReportLab.
Enhanced with risk badges, visual score bars, richer formatting, and document stats.
"""

import io
from datetime import datetime
from typing import List, Dict, Any, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak
)


# ── Colour palette ─────────────────────────────────────────────────────────────
C_COMPLIANT      = colors.HexColor("#15803d")   # green-700
C_PARTIAL        = colors.HexColor("#b45309")   # amber-700
C_NON_COMPLIANT  = colors.HexColor("#b91c1c")   # red-700
C_HEADER_BG      = colors.HexColor("#0f172a")   # slate-900
C_HEADER_ACCENT  = colors.HexColor("#3b82f6")   # blue-500
C_ROW_ALT        = colors.HexColor("#f8fafc")   # slate-50
C_BORDER         = colors.HexColor("#e2e8f0")   # slate-200
C_TEXT           = colors.HexColor("#1e293b")   # slate-900
C_MUTED          = colors.HexColor("#64748b")   # slate-500
C_RISK_HIGH      = colors.HexColor("#dc2626")   # red-600
C_RISK_MED       = colors.HexColor("#d97706")   # amber-600
C_RISK_LOW       = colors.HexColor("#16a34a")   # green-600
C_BG_RISK_HIGH   = colors.HexColor("#fef2f2")
C_BG_RISK_MED    = colors.HexColor("#fffbeb")
C_BG_RISK_LOW    = colors.HexColor("#f0fdf4")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _status_color(status: str) -> colors.Color:
    return {"COMPLIANT": C_COMPLIANT, "PARTIAL": C_PARTIAL,
            "NON-COMPLIANT": C_NON_COMPLIANT}.get(status, C_MUTED)


def _status_label(status: str) -> str:
    return {"COMPLIANT": "✔  COMPLIANT", "PARTIAL": "~  PARTIAL",
            "NON-COMPLIANT": "✘  NON-COMPLIANT"}.get(status, status)


def _risk_level(score: float, confidence: int) -> str:
    if score < 40 or confidence < 40:
        return "HIGH"
    if score < 70 or confidence < 65:
        return "MEDIUM"
    return "LOW"


def _risk_color(risk: str) -> colors.Color:
    return {"HIGH": C_RISK_HIGH, "MEDIUM": C_RISK_MED, "LOW": C_RISK_LOW}.get(risk, C_MUTED)


def _risk_bg(risk: str) -> colors.Color:
    return {"HIGH": C_BG_RISK_HIGH, "MEDIUM": C_BG_RISK_MED,
            "LOW": C_BG_RISK_LOW}.get(risk, colors.white)


def _score_bar(score: float, width: int = 25) -> str:
    """Unicode block-based visual score bar."""
    filled = round((score / 100) * width)
    return "█" * filled + "░" * (width - filled)


def _make_style(name: str, parent_style, **kwargs) -> ParagraphStyle:
    return ParagraphStyle(name, parent=parent_style, **kwargs)


# ── Main entry point ───────────────────────────────────────────────────────────

def generate_pdf_report(
    rule_results: List[Dict[str, Any]],
    final_score: float,
    overall_status: str,
    document_name: str = "Uploaded Document",
    page_results: Optional[List[Dict[str, Any]]] = None,
    doc_stats: Optional[Dict[str, Any]] = None,
) -> bytes:
    """
    Build a polished PDF compliance report in memory and return raw bytes.

    Args:
        rule_results:    Per-rule result dicts from workflow.
        final_score:     Aggregated compliance score (0-100).
        overall_status:  COMPLIANT / PARTIAL / NON-COMPLIANT.
        document_name:   Original file name shown in the header.
        page_results:    Optional per-page findings (unused, kept for compat).
        doc_stats:       Optional dict with page_count, word_count keys.

    Returns:
        PDF bytes ready for st.download_button.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=2.0 * cm, bottomMargin=2.0 * cm,
    )

    base = getSampleStyleSheet()
    W = A4[0] - 3.6 * cm  # usable width

    # ── Styles ─────────────────────────────────────────────────────────────────
    s_title = _make_style("RT", base["Title"], fontSize=22, leading=28,
                          textColor=colors.white, spaceAfter=2, alignment=TA_LEFT)
    s_sub   = _make_style("RS", base["Normal"], fontSize=8.5, textColor=colors.HexColor("#94a3b8"),
                          spaceAfter=0)
    s_h2    = _make_style("H2", base["Heading2"], fontSize=11, textColor=C_HEADER_ACCENT,
                          spaceBefore=18, spaceAfter=6)
    s_body  = _make_style("Bo", base["Normal"], fontSize=9, leading=14, textColor=C_TEXT)
    s_expl  = _make_style("Ex", base["Normal"], fontSize=8.5, leading=13,
                          textColor=C_TEXT, leftIndent=4)
    s_foot  = _make_style("Fo", base["Normal"], fontSize=7, textColor=C_MUTED,
                          alignment=TA_CENTER)
    s_mono  = _make_style("Mo", base["Code"], fontSize=7.5, leading=11,
                          textColor=colors.HexColor("#94a3b8"))
    s_white = _make_style("Wh", base["Normal"], fontSize=9, textColor=colors.white,
                          leading=13)
    s_white_sm = _make_style("WS", base["Normal"], fontSize=8, textColor=colors.white,
                             leading=11)

    story = []
    generated_at = datetime.now().strftime("%d %B %Y  ·  %H:%M")

    # ── ❶ Cover / header block ─────────────────────────────────────────────────
    header_data = [[
        Paragraph("Compliance Analysis Report", s_title),
        Paragraph(f"Generated: {generated_at}", s_sub),
    ]]
    header_table = Table(header_data, colWidths=[W * 0.65, W * 0.35])
    header_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_HEADER_BG),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (1, 0), (1, 0), "RIGHT"),
    ]))
    story.append(header_table)

    # Document info bar
    doc_info_parts = [f"<b>Document:</b> {document_name}"]
    if doc_stats:
        doc_info_parts += [
            f"Pages: {doc_stats.get('page_count', '—')}",
            f"Words: {doc_stats.get('word_count', '—'):,}",
        ]
    info_bar_data = [[Paragraph("   ".join(doc_info_parts), s_white_sm)]]
    info_bar = Table(info_bar_data, colWidths=[W])
    info_bar.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_HEADER_ACCENT),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
    ]))
    story.append(info_bar)
    story.append(Spacer(1, 14))

    # ── ❷ Overall verdict card ─────────────────────────────────────────────────
    status_col = _status_color(overall_status)
    n_c  = sum(1 for r in rule_results if r["status"] == "COMPLIANT")
    n_p  = sum(1 for r in rule_results if r["status"] == "PARTIAL")
    n_nc = sum(1 for r in rule_results if r["status"] == "NON-COMPLIANT")
    total = len(rule_results) or 1

    verdict_data = [
        [
            Paragraph("<b>OVERALL STATUS</b>", _make_style("vh1", base["Normal"], fontSize=7.5,
                      textColor=C_MUTED, alignment=TA_CENTER)),
            Paragraph("<b>COMPLIANCE SCORE</b>", _make_style("vh2", base["Normal"], fontSize=7.5,
                      textColor=C_MUTED, alignment=TA_CENTER)),
            Paragraph("<b>COMPLIANT</b>", _make_style("vh3", base["Normal"], fontSize=7.5,
                      textColor=C_MUTED, alignment=TA_CENTER)),
            Paragraph("<b>PARTIAL</b>", _make_style("vh4", base["Normal"], fontSize=7.5,
                      textColor=C_MUTED, alignment=TA_CENTER)),
            Paragraph("<b>NON-COMPLIANT</b>", _make_style("vh5", base["Normal"], fontSize=7.5,
                      textColor=C_MUTED, alignment=TA_CENTER)),
        ],
        [
            Paragraph(
                f"<b>{_status_label(overall_status)}</b>",
                _make_style("vs1", base["Normal"], fontSize=12, textColor=status_col,
                            leading=16, alignment=TA_CENTER),
            ),
            Paragraph(
                f"<b>{final_score}/100</b><br/>"
                f"<font size='6.5' color='#94a3b8'>{_score_bar(final_score)}</font>",
                _make_style("vs2", base["Normal"], fontSize=12, textColor=status_col,
                            leading=16, alignment=TA_CENTER),
            ),
            Paragraph(
                f"<b><font color='#15803d'>{n_c}</font></b>"
                f"<br/><font size='7' color='#64748b'>{round(n_c/total*100)}%</font>",
                _make_style("vs3", base["Normal"], fontSize=13, leading=17, alignment=TA_CENTER),
            ),
            Paragraph(
                f"<b><font color='#b45309'>{n_p}</font></b>"
                f"<br/><font size='7' color='#64748b'>{round(n_p/total*100)}%</font>",
                _make_style("vs4", base["Normal"], fontSize=13, leading=17, alignment=TA_CENTER),
            ),
            Paragraph(
                f"<b><font color='#b91c1c'>{n_nc}</font></b>"
                f"<br/><font size='7' color='#64748b'>{round(n_nc/total*100)}%</font>",
                _make_style("vs5", base["Normal"], fontSize=13, leading=17, alignment=TA_CENTER),
            ),
        ],
    ]
    verdict_table = Table(verdict_data, colWidths=[W * 0.22, W * 0.26, W * 0.17, W * 0.17, W * 0.18])
    verdict_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), C_ROW_ALT),
        ("BACKGROUND",    (0, 1), (-1, 1), colors.white),
        ("BOX",           (0, 0), (-1, -1), 1.5, C_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, C_BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(verdict_table)
    story.append(Spacer(1, 16))

    # ── ❸ Rules summary table ──────────────────────────────────────────────────
    story.append(Paragraph("Rule-by-Rule Analysis", s_h2))
    story.append(HRFlowable(width=W, thickness=1, color=C_BORDER, spaceAfter=8))

    rule_header_row = [
        Paragraph("<b>#</b>", _make_style("rh0", base["Normal"], fontSize=8, textColor=colors.white, alignment=TA_CENTER)),
        Paragraph("<b>Rule</b>", _make_style("rh1", base["Normal"], fontSize=8, textColor=colors.white)),
        Paragraph("<b>Status</b>", _make_style("rh2", base["Normal"], fontSize=8, textColor=colors.white, alignment=TA_CENTER)),
        Paragraph("<b>Score</b>", _make_style("rh3", base["Normal"], fontSize=8, textColor=colors.white, alignment=TA_CENTER)),
        Paragraph("<b>Risk</b>", _make_style("rh4", base["Normal"], fontSize=8, textColor=colors.white, alignment=TA_CENTER)),
        Paragraph("<b>Findings</b>", _make_style("rh5", base["Normal"], fontSize=8, textColor=colors.white)),
    ]
    rule_rows = [rule_header_row]

    rule_style_cmds = [
        ("BACKGROUND",    (0, 0), (-1, 0), C_HEADER_BG),
        ("BOX",           (0, 0), (-1, -1), 0.75, C_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.4, C_BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]

    for idx, r in enumerate(rule_results, 1):
        status  = r.get("status", "NON-COMPLIANT")
        score   = float(r.get("compliance_score", 0))
        conf    = int(r.get("llm_confidence", 0))
        expl    = r.get("explanation", "—")
        rule_t  = r.get("rule", "")
        risk    = _risk_level(score, conf)
        rc      = _risk_color(risk)
        sc      = _status_color(status)

        row = [
            Paragraph(str(idx), _make_style(f"ri{idx}", base["Normal"], fontSize=8,
                      alignment=TA_CENTER, textColor=C_MUTED)),
            Paragraph(rule_t, s_expl),
            Paragraph(
                f"<b>{_status_label(status)}</b>",
                _make_style(f"rs{idx}", base["Normal"], fontSize=7.5, textColor=sc,
                            leading=11, alignment=TA_CENTER),
            ),
            Paragraph(
                f"<b>{int(score)}</b>/100<br/>"
                f"<font size='6.5' color='#94a3b8'>conf {conf}%</font>",
                _make_style(f"rsc{idx}", base["Normal"], fontSize=8, leading=12, alignment=TA_CENTER),
            ),
            Paragraph(
                f"<b>{risk}</b>",
                _make_style(f"rrk{idx}", base["Normal"], fontSize=7.5, textColor=rc,
                            leading=11, alignment=TA_CENTER),
            ),
            Paragraph(expl, s_expl),
        ]
        rule_rows.append(row)
        if idx % 2 == 0:
            rule_style_cmds.append(("BACKGROUND", (0, idx), (-1, idx), C_ROW_ALT))

    col_w = [W * f for f in (0.04, 0.22, 0.14, 0.10, 0.08, 0.42)]
    rule_table = Table(rule_rows, colWidths=col_w, repeatRows=1)
    rule_table.setStyle(TableStyle(rule_style_cmds))
    story.append(rule_table)
    story.append(Spacer(1, 20))

    # ── ❹ Risk Distribution Summary ───────────────────────────────────────────
    risks = [_risk_level(float(r.get("compliance_score", 0)), int(r.get("llm_confidence", 0)))
             for r in rule_results]
    n_high = risks.count("HIGH")
    n_med  = risks.count("MEDIUM")
    n_low  = risks.count("LOW")

    story.append(Paragraph("Risk Distribution", s_h2))
    risk_data = [
        [Paragraph("<b>Risk Level</b>", _make_style("rdh0", base["Normal"], fontSize=8, textColor=colors.white)),
         Paragraph("<b>Rules</b>", _make_style("rdh1", base["Normal"], fontSize=8, textColor=colors.white, alignment=TA_CENTER)),
         Paragraph("<b>Share</b>", _make_style("rdh2", base["Normal"], fontSize=8, textColor=colors.white, alignment=TA_CENTER))],
        [Paragraph("<b>🔴 HIGH RISK</b>", _make_style("rdr0", base["Normal"], fontSize=8.5, textColor=C_RISK_HIGH)),
         Paragraph(str(n_high), _make_style("rdn0", base["Normal"], fontSize=10, alignment=TA_CENTER)),
         Paragraph(f"{round(n_high/total*100)}%", _make_style("rdp0", base["Normal"], fontSize=8.5, alignment=TA_CENTER))],
        [Paragraph("<b>🟡 MEDIUM RISK</b>", _make_style("rdr1", base["Normal"], fontSize=8.5, textColor=C_RISK_MED)),
         Paragraph(str(n_med), _make_style("rdn1", base["Normal"], fontSize=10, alignment=TA_CENTER)),
         Paragraph(f"{round(n_med/total*100)}%", _make_style("rdp1", base["Normal"], fontSize=8.5, alignment=TA_CENTER))],
        [Paragraph("<b>🟢 LOW RISK</b>", _make_style("rdr2", base["Normal"], fontSize=8.5, textColor=C_RISK_LOW)),
         Paragraph(str(n_low), _make_style("rdn2", base["Normal"], fontSize=10, alignment=TA_CENTER)),
         Paragraph(f"{round(n_low/total*100)}%", _make_style("rdp2", base["Normal"], fontSize=8.5, alignment=TA_CENTER))],
    ]
    risk_table = Table(risk_data, colWidths=[W * 0.55, W * 0.22, W * 0.23])
    risk_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), C_HEADER_BG),
        ("BACKGROUND",    (0, 1), (-1, 1), C_BG_RISK_HIGH),
        ("BACKGROUND",    (0, 2), (-1, 2), C_BG_RISK_MED),
        ("BACKGROUND",    (0, 3), (-1, 3), C_BG_RISK_LOW),
        ("BOX",           (0, 0), (-1, -1), 0.75, C_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.4, C_BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(risk_table)

    # ── ❺ Footer ───────────────────────────────────────────────────────────────
    story.append(Spacer(1, 24))
    story.append(HRFlowable(width=W, thickness=0.5, color=C_BORDER, spaceAfter=6))
    story.append(Paragraph(
        "Generated by AI-Accelerated Compliance Pipeline &nbsp;|&nbsp; "
        "LangGraph + RAG + LLM &nbsp;|&nbsp; "
        "This report is for informational purposes only.",
        s_foot,
    ))

    doc.build(story)
    return buffer.getvalue()
