# --- NEW CODE START ---
"""
report_generator.py
Generates a polished, downloadable PDF compliance report using ReportLab.
"""

import io
from datetime import datetime
from typing import List, Dict, Any

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)


# ── Colour palette ─────────────────────────────────────────────────────────────
C_COMPLIANT     = colors.HexColor("#1a7f4b")   # dark green
C_PARTIAL       = colors.HexColor("#b45309")   # amber
C_NON_COMPLIANT = colors.HexColor("#b91c1c")   # red
C_HEADER_BG     = colors.HexColor("#1e3a5f")   # navy
C_ROW_ALT       = colors.HexColor("#f0f4f8")   # very light blue-grey
C_BORDER        = colors.HexColor("#cbd5e1")   # slate-200
C_TEXT          = colors.HexColor("#1e293b")   # slate-900
C_MUTED         = colors.HexColor("#64748b")   # slate-500


def _status_color(status: str) -> colors.Color:
    return {
        "COMPLIANT":     C_COMPLIANT,
        "PARTIAL":       C_PARTIAL,
        "NON-COMPLIANT": C_NON_COMPLIANT,
    }.get(status, C_MUTED)


def _status_label(status: str) -> str:
    return {
        "COMPLIANT":     "✔  COMPLIANT",
        "PARTIAL":       "~  PARTIAL",
        "NON-COMPLIANT": "✘  NON-COMPLIANT",
    }.get(status, status)


def generate_pdf_report(
    rule_results: List[Dict[str, Any]],
    final_score: float,
    overall_status: str,
    document_name: str = "Uploaded Document",
    page_results: List[Dict[str, Any]] = None,   # --- NEW CODE: page-wise findings ---
) -> bytes:
    """
    Build a PDF compliance report in memory and return raw bytes.

    Args:
        rule_results:    List of per-rule result dicts from workflow.
        final_score:     Aggregated compliance score (0-100).
        overall_status:  COMPLIANT / PARTIAL / NON-COMPLIANT.
        document_name:   Original file name to display in header.
        page_results:    Optional list of per-page findings dicts.

    Returns:
        PDF file contents as bytes (ready for st.download_button).
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    W = A4[0] - 4 * cm   # usable page width

    # ── Custom styles ──────────────────────────────────────────────────────────
    style_title = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=20,
        leading=26,
        textColor=C_HEADER_BG,
        spaceAfter=4,
        alignment=TA_LEFT,
    )
    style_subtitle = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=9,
        textColor=C_MUTED,
        spaceAfter=12,
    )
    style_section = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontSize=11,
        textColor=C_HEADER_BG,
        spaceBefore=16,
        spaceAfter=6,
        borderPad=0,
    )
    style_body = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9,
        leading=14,
        textColor=C_TEXT,
    )
    style_explanation = ParagraphStyle(
        "Explanation",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=13,
        textColor=C_TEXT,
        leftIndent=4,
    )
    style_footer = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=7.5,
        textColor=C_MUTED,
        alignment=TA_CENTER,
    )

    story = []

    # ── Header block ───────────────────────────────────────────────────────────
    story.append(Paragraph("Compliance Analysis Report", style_title))
    generated_at = datetime.now().strftime("%d %B %Y, %H:%M")
    story.append(Paragraph(
        f"Document: <b>{document_name}</b> &nbsp;&nbsp;|&nbsp;&nbsp; Generated: {generated_at}",
        style_subtitle,
    ))
    story.append(HRFlowable(width=W, thickness=2, color=C_HEADER_BG, spaceAfter=14))

    # ── Overall verdict card ───────────────────────────────────────────────────
    status_col = _status_color(overall_status)
    score_bar_filled = int((final_score / 100) * 30)   # out of 30 chars
    score_bar = "█" * score_bar_filled + "░" * (30 - score_bar_filled)

    verdict_data = [
        [
            Paragraph("<b>Overall Status</b>", ParagraphStyle("vh", fontSize=9, textColor=C_MUTED)),
            Paragraph("<b>Compliance Score</b>", ParagraphStyle("vh", fontSize=9, textColor=C_MUTED)),
            Paragraph("<b>Rules Evaluated</b>", ParagraphStyle("vh", fontSize=9, textColor=C_MUTED)),
        ],
        [
            Paragraph(
                f"<b>{_status_label(overall_status)}</b>",
                ParagraphStyle("vs", fontSize=14, textColor=status_col, leading=18),
            ),
            Paragraph(
                f"<b>{final_score}/100</b><br/>"
                f"<font size='7' color='#94a3b8'>{score_bar}</font>",
                ParagraphStyle("vsc", fontSize=14, textColor=status_col, leading=18),
            ),
            Paragraph(
                f"<b>{len(rule_results)}</b>",
                ParagraphStyle("vrc", fontSize=14, textColor=C_HEADER_BG, leading=18),
            ),
        ],
    ]
    verdict_table = Table(verdict_data, colWidths=[W / 3] * 3)
    verdict_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_ROW_ALT),
        ("BACKGROUND", (0, 1), (-1, 1), colors.white),
        ("BOX",        (0, 0), (-1, -1), 1, C_BORDER),
        ("INNERGRID",  (0, 0), (-1, -1), 0.5, C_BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(verdict_table)
    story.append(Spacer(1, 14))

    # ── Summary counts ─────────────────────────────────────────────────────────
    n_c  = sum(1 for r in rule_results if r["status"] == "COMPLIANT")
    n_p  = sum(1 for r in rule_results if r["status"] == "PARTIAL")
    n_nc = sum(1 for r in rule_results if r["status"] == "NON-COMPLIANT")

    summary_data = [
        ["", "Count", "Share"],
        ["Compliant",     str(n_c),  f"{round(n_c  / len(rule_results) * 100)}%"],
        ["Partial",       str(n_p),  f"{round(n_p  / len(rule_results) * 100)}%"],
        ["Non-Compliant", str(n_nc), f"{round(n_nc / len(rule_results) * 100)}%"],
    ]
    label_colors = [C_COMPLIANT, C_PARTIAL, C_NON_COMPLIANT]

    story.append(Paragraph("Summary", style_section))
    sum_table = Table(summary_data, colWidths=[W * 0.55, W * 0.2, W * 0.25])
    sum_style = [
        ("BACKGROUND",  (0, 0), (-1, 0), C_HEADER_BG),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 8.5),
        ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 1), (-1, -1), 8.5),
        ("BOX",         (0, 0), (-1, -1), 0.75, C_BORDER),
        ("INNERGRID",   (0, 0), (-1, -1), 0.5, C_BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",       (1, 0), (-1, -1), "CENTER"),
    ]
    for row_i, col in enumerate(label_colors, start=1):
        sum_style += [
            ("TEXTCOLOR", (0, row_i), (0, row_i), col),
            ("FONTNAME",  (0, row_i), (0, row_i), "Helvetica-Bold"),
            ("BACKGROUND", (0, row_i), (-1, row_i),
             C_ROW_ALT if row_i % 2 == 0 else colors.white),
        ]
    sum_table.setStyle(TableStyle(sum_style))
    story.append(sum_table)
    story.append(Spacer(1, 14))

    # ── Rule-wise detail table ─────────────────────────────────────────────────
    story.append(Paragraph("Rule-by-Rule Analysis", style_section))

    rule_header = ["#", "Rule", "Status", "Score", "Findings"]
    rule_rows = [rule_header]

    for idx, r in enumerate(rule_results, 1):
        status  = r.get("status", "NON-COMPLIANT")
        score   = r.get("compliance_score", 0)
        conf    = r.get("llm_confidence", 0)
        explanation = r.get("explanation", "—")

        rule_rows.append([
            Paragraph(str(idx), ParagraphStyle("rc", fontSize=8.5, alignment=TA_CENTER, textColor=C_MUTED)),
            Paragraph(r.get("rule", ""), style_explanation),
            Paragraph(
                f"<b>{_status_label(status)}</b>",
                ParagraphStyle("sc", fontSize=8, textColor=_status_color(status), leading=12),
            ),
            Paragraph(
                f"<b>{int(score)}</b>/100<br/>"
                f"<font size='7' color='#94a3b8'>conf: {conf}%</font>",
                ParagraphStyle("scc", fontSize=8.5, alignment=TA_CENTER, leading=13),
            ),
            Paragraph(explanation, style_explanation),
        ])

    col_widths = [W * 0.04, W * 0.26, W * 0.17, W * 0.10, W * 0.43]
    rule_table = Table(rule_rows, colWidths=col_widths, repeatRows=1)
    rule_style = [
        # Header row
        ("BACKGROUND",  (0, 0), (-1, 0), C_HEADER_BG),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 8.5),
        ("ALIGN",       (0, 0), (-1, 0), "CENTER"),
        # Data rows
        ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 1), (-1, -1), 8.5),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("BOX",         (0, 0), (-1, -1), 0.75, C_BORDER),
        ("INNERGRID",   (0, 0), (-1, -1), 0.5, C_BORDER),
    ]
    # Alternating row shading
    for row_i in range(1, len(rule_rows)):
        if row_i % 2 == 0:
            rule_style.append(("BACKGROUND", (0, row_i), (-1, row_i), C_ROW_ALT))
    rule_table.setStyle(TableStyle(rule_style))
    story.append(rule_table)

    # ── Footer ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width=W, thickness=0.5, color=C_BORDER, spaceAfter=6))
    story.append(Paragraph(
        "Generated by AI-Accelerated Compliance Pipeline &nbsp;|&nbsp; "
        "This report is for informational purposes only.",
        style_footer,
    ))

    doc.build(story)
    return buffer.getvalue()
# --- NEW CODE END ---
