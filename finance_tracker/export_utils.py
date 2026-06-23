"""
export_utils.py
---------------
Provides Excel (.xlsx) and PDF (.pdf) export functionality.
Uses openpyxl/xlsxwriter for Excel and reportlab for PDF.
Returns raw bytes that Streamlit can offer as download.
"""

import io
import pandas as pd
from datetime import date
from analytics import get_df, get_summary
from database import get_goals, get_budgets
from utils import fmt_currency, current_month


# ══════════════════════════════════════════════════════════════════════════════
# EXCEL EXPORT
# ══════════════════════════════════════════════════════════════════════════════

def export_excel(user_id: int, month: str = None, currency_symbol: str = "₹") -> bytes:
    """
    Build and return an Excel workbook with:
      - Transactions sheet
      - Summary sheet
      - Goals sheet
    """
    output  = io.BytesIO()
    filters = {"month": month} if month else {}
    df      = get_df(user_id, filters)

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        wb  = writer.book

        # ── Formats ──────────────────────────────────────────────────────────
        hdr_fmt = wb.add_format({
            "bold": True, "bg_color": "#6C5CE7", "font_color": "#FFFFFF",
            "border": 1, "align": "center", "valign": "vcenter",
        })
        money_fmt = wb.add_format({"num_format": f'#,##0.00', "border": 1})
        date_fmt  = wb.add_format({"num_format": "DD-MMM-YYYY", "border": 1})
        cell_fmt  = wb.add_format({"border": 1})
        inc_fmt   = wb.add_format({"font_color": "#00B894", "border": 1, "bold": True})
        exp_fmt   = wb.add_format({"font_color": "#FF6B6B", "border": 1, "bold": True})

        # ── Transactions Sheet ────────────────────────────────────────────────
        if not df.empty:
            export_df = df[["trans_date", "type", "category", "amount",
                             "payment_mode", "note"]].copy()
            export_df["trans_date"] = export_df["trans_date"].dt.strftime("%Y-%m-%d")
            export_df.columns = ["Date", "Type", "Category", "Amount (₹)", "Payment Mode", "Note"]
        else:
            export_df = pd.DataFrame(columns=["Date", "Type", "Category",
                                               "Amount (₹)", "Payment Mode", "Note"])

        export_df.to_excel(writer, sheet_name="Transactions", index=False, startrow=1)
        ws = writer.sheets["Transactions"]
        ws.set_row(0, 20)
        ws.write(0, 0, f"Finance Transactions  |  Exported: {date.today()}", hdr_fmt)
        ws.merge_range(0, 0, 0, 5, f"Finance Transactions  |  Exported: {date.today()}", hdr_fmt)

        for col_num, col_name in enumerate(export_df.columns):
            ws.write(1, col_num, col_name, hdr_fmt)
        ws.set_column("A:A", 14)
        ws.set_column("B:B", 10)
        ws.set_column("C:C", 16)
        ws.set_column("D:D", 14)
        ws.set_column("E:E", 14)
        ws.set_column("F:F", 30)

        for row_num, row in enumerate(export_df.itertuples(index=False), start=2):
            fmt = inc_fmt if row.Type == "income" else exp_fmt if row.Type == "expense" else cell_fmt
            ws.write(row_num, 0, row.Date, cell_fmt)
            ws.write(row_num, 1, row.Type.capitalize(), fmt)
            ws.write(row_num, 2, row.Category, cell_fmt)
            ws.write(row_num, 3, row[3], money_fmt)
            ws.write(row_num, 4, row[4], cell_fmt)
            ws.write(row_num, 5, str(row.Note or ""), cell_fmt)

        # ── Summary Sheet ─────────────────────────────────────────────────────
        summary = get_summary(user_id, month or current_month())
        ws2 = wb.add_worksheet("Summary")
        ws2.set_column("A:A", 28)
        ws2.set_column("B:B", 20)
        title_fmt = wb.add_format({"bold": True, "font_size": 14,
                                    "bg_color": "#2d2d44", "font_color": "#FFFFFF"})
        lbl_fmt   = wb.add_format({"bold": True, "bg_color": "#f5f5f5"})
        val_fmt   = wb.add_format({"num_format": "#,##0.00"})

        ws2.merge_range(0, 0, 0, 1, "Financial Summary", title_fmt)
        rows_data = [
            ("Total Income (All Time)",   summary["total_income"]),
            ("Total Expense (All Time)",  summary["total_expense"]),
            ("Net Savings (All Time)",    summary["net_savings"]),
            ("", ""),
            (f"Income ({month or 'This Month'})",   summary["month_income"]),
            (f"Expense ({month or 'This Month'})",  summary["month_expense"]),
            (f"Savings ({month or 'This Month'})",  summary["month_savings"]),
        ]
        for i, (label, value) in enumerate(rows_data, start=1):
            ws2.write(i, 0, label, lbl_fmt)
            if isinstance(value, (int, float)):
                ws2.write(i, 1, value, val_fmt)

        # ── Goals Sheet ───────────────────────────────────────────────────────
        goals = get_goals(user_id)
        ws3 = wb.add_worksheet("Goals")
        ws3.set_column("A:A", 24)
        ws3.set_column("B:F", 16)
        g_headers = ["Goal", "Target (₹)", "Saved (₹)", "Remaining (₹)", "Progress %", "Deadline"]
        for ci, h in enumerate(g_headers):
            ws3.write(0, ci, h, hdr_fmt)
        for ri, g in enumerate(goals, start=1):
            rem  = g["target_amount"] - g["saved_amount"]
            pct  = (g["saved_amount"] / g["target_amount"] * 100) if g["target_amount"] else 0
            ws3.write(ri, 0, g["name"], cell_fmt)
            ws3.write(ri, 1, g["target_amount"], money_fmt)
            ws3.write(ri, 2, g["saved_amount"], money_fmt)
            ws3.write(ri, 3, rem, money_fmt)
            ws3.write(ri, 4, round(pct, 1), cell_fmt)
            ws3.write(ri, 5, g.get("deadline", ""), cell_fmt)

    return output.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# PDF EXPORT
# ══════════════════════════════════════════════════════════════════════════════

def export_pdf(user_id: int, month: str = None, currency_symbol: str = "₹") -> bytes:
    """
    Build and return a professional PDF summary report using reportlab,
    including summary statistics, progress bars, and clean layouts.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                     Paragraph, Spacer, HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.graphics.shapes import Drawing, Rect

    output = io.BytesIO()
    doc    = SimpleDocTemplate(output, pagesize=A4,
                               rightMargin=1.5*cm, leftMargin=1.5*cm,
                               topMargin=1.5*cm, bottomMargin=1.5*cm)

    styles  = getSampleStyleSheet()
    story   = []
    summary = get_summary(user_id, month or current_month())

    # ── Colors & Styles ───────────────────────────────────────────────────────
    PURPLE = colors.HexColor("#6C5CE7")
    GREEN  = colors.HexColor("#00B894")
    RED    = colors.HexColor("#FF6B6B")
    DARK   = colors.HexColor("#2D2D44")
    LIGHT_GRAY = colors.HexColor("#F8F9FA")
    BORDER_COLOR = colors.HexColor("#E9ECEF")

    title_style = ParagraphStyle("title", fontSize=24, textColor=PURPLE,
                                  alignment=TA_CENTER, spaceAfter=4, fontName="Helvetica-Bold")
    subtitle_style = ParagraphStyle("subtitle", fontSize=10, textColor=colors.HexColor("#6C757D"),
                                     alignment=TA_CENTER, spaceAfter=15, fontName="Helvetica")
    h2_style    = ParagraphStyle("h2", fontSize=13, textColor=DARK,
                                  spaceBefore=14, spaceAfter=6, fontName="Helvetica-Bold")
    label_style = ParagraphStyle("label", fontSize=9, fontName="Helvetica-Bold", textColor=colors.HexColor("#495057"))
    value_style = ParagraphStyle("value", fontSize=9, fontName="Helvetica", textColor=colors.HexColor("#212529"))

    # ── Progress Bar Drawing Helper ───────────────────────────────────────────
    def make_pdf_progress_bar(pct, color):
        pct = max(0.0, min(100.0, float(pct)))
        d = Drawing(120, 8)
        # Background
        d.add(Rect(0, 0, 120, 8, fillColor=colors.HexColor("#E9ECEF"), strokeColor=None))
        # Fill
        fill_w = (pct / 100.0) * 120
        if fill_w > 0:
            d.add(Rect(0, 0, fill_w, 8, fillColor=color, strokeColor=None))
        return d

    # ── Title Block ───────────────────────────────────────────────────────────
    story.append(Paragraph("💰 Smart Finance Tracker Report", title_style))
    story.append(Paragraph(f"Period: {month or 'All Time'}  |  Generated: {date.today().strftime('%d %b %Y')}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=PURPLE, spaceAfter=15))

    # ── Summary Statistics Grid ───────────────────────────────────────────────
    story.append(Paragraph("Financial Summary", h2_style))
    
    savings_rate = (summary["month_savings"] / summary["month_income"] * 100) if summary["month_income"] > 0 else 0.0
    
    stat_data = [
        [
            Paragraph("<b>Total Income (All Time)</b>", label_style),
            Paragraph(fmt_currency(summary["total_income"], currency_symbol), value_style),
            Paragraph(f"<b>Income ({month or 'This Month'})</b>", label_style),
            Paragraph(fmt_currency(summary["month_income"], currency_symbol), value_style),
        ],
        [
            Paragraph("<b>Total Expenses (All Time)</b>", label_style),
            Paragraph(fmt_currency(summary["total_expense"], currency_symbol), value_style),
            Paragraph(f"<b>Expenses ({month or 'This Month'})</b>", label_style),
            Paragraph(fmt_currency(summary["month_expense"], currency_symbol), value_style),
        ],
        [
            Paragraph("<b>Net Savings (All Time)</b>", label_style),
            Paragraph(fmt_currency(summary["net_savings"], currency_symbol), value_style),
            Paragraph(f"<b>Savings ({month or 'This Month'})</b>", label_style),
            Paragraph(fmt_currency(summary["month_savings"], currency_symbol), value_style),
        ],
        [
            Paragraph("", label_style), Paragraph("", value_style),
            Paragraph("<b>Savings Rate</b>", label_style),
            Paragraph(f"{savings_rate:.1f}%", value_style),
        ]
    ]
    
    stat_table = Table(stat_data, colWidths=[5*cm, 4*cm, 5*cm, 4*cm])
    stat_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(stat_table)
    story.append(Spacer(1, 0.4*cm))

    # ── Savings Goals Table ───────────────────────────────────────────────────
    goals = get_goals(user_id)
    if goals:
        story.append(Paragraph("Savings Goals Progress", h2_style))
        g_data = [["Goal Name", "Target", "Saved", "Progress %", "Visual Bar", "Deadline"]]
        
        for g in goals:
            pct = (g["saved_amount"] / g["target_amount"] * 100) if g["target_amount"] else 0.0
            g_data.append([
                g["name"],
                fmt_currency(g["target_amount"], currency_symbol),
                fmt_currency(g["saved_amount"], currency_symbol),
                f"{pct:.1f}%",
                make_pdf_progress_bar(pct, GREEN if pct >= 80 else PURPLE),
                g.get("deadline", "—") or "—"
            ])
            
        g_table = Table(g_data, colWidths=[4.5*cm, 3*cm, 3*cm, 2.2*cm, 3.2*cm, 2.1*cm])
        g_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), GREEN),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(g_table)
        story.append(Spacer(1, 0.4*cm))

    # ── Recent Transactions Table ─────────────────────────────────────────────
    story.append(Paragraph("Recent Transactions (Last 20)", h2_style))
    filters = {"month": month} if month else {}
    df = get_df(user_id, filters)

    if not df.empty:
        recent = df.head(20)
        txn_data = [["Date", "Type", "Category", "Amount", "Note"]]
        for _, row in recent.iterrows():
            txn_data.append([
                str(row["trans_date"].date()),
                row["type"].capitalize(),
                row["category"],
                fmt_currency(row["amount"], currency_symbol),
                str(row.get("note", "") or "")[:28],
            ])
        txn_tbl = Table(txn_data, colWidths=[3.2*cm, 2.3*cm, 3.5*cm, 3.5*cm, 5.5*cm])
        txn_tbl.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0), DARK),
            ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
            ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 8),
            ("ALIGN",       (0, 0), (-1, -1), "LEFT"),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ("GRID",        (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ("TOPPADDING",  (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ]))
        story.append(txn_tbl)
    else:
        story.append(Paragraph("No transactions recorded for this period.", value_style))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.8*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceAfter=8))
    footer_style = ParagraphStyle("footer", fontSize=8, textColor=colors.HexColor("#868E96"), alignment=TA_CENTER)
    story.append(Paragraph("Smart Finance Tracker © v2.0 • Generated Securely and Locally", footer_style))

    doc.build(story)
    return output.getvalue()
