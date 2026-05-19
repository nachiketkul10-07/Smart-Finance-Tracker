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
    Build and return a PDF summary report using reportlab.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                     Paragraph, Spacer, HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    output = io.BytesIO()
    doc    = SimpleDocTemplate(output, pagesize=A4,
                               rightMargin=2*cm, leftMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)

    styles  = getSampleStyleSheet()
    story   = []
    summary = get_summary(user_id, month or current_month())

    # ── Style helpers ─────────────────────────────────────────────────────────
    PURPLE = colors.HexColor("#6C5CE7")
    GREEN  = colors.HexColor("#00B894")
    RED    = colors.HexColor("#FF6B6B")
    DARK   = colors.HexColor("#2d2d44")

    title_style = ParagraphStyle("title", fontSize=22, textColor=PURPLE,
                                  alignment=TA_CENTER, spaceAfter=6, fontName="Helvetica-Bold")
    h2_style    = ParagraphStyle("h2", fontSize=14, textColor=DARK,
                                  spaceBefore=12, spaceAfter=4, fontName="Helvetica-Bold")
    normal_style = styles["Normal"]

    # ── Title ─────────────────────────────────────────────────────────────────
    story.append(Paragraph("💰 Smart Finance Tracker", title_style))
    story.append(Paragraph(f"Report for: {month or 'All Time'}  |  Generated: {date.today()}", normal_style))
    story.append(HRFlowable(width="100%", thickness=2, color=PURPLE, spaceAfter=12))

    # ── Summary table ─────────────────────────────────────────────────────────
    story.append(Paragraph("Financial Summary", h2_style))
    sum_data = [
        ["Metric", "Amount"],
        ["Total Income (All Time)",  fmt_currency(summary["total_income"],  currency_symbol)],
        ["Total Expense (All Time)", fmt_currency(summary["total_expense"], currency_symbol)],
        ["Net Savings (All Time)",   fmt_currency(summary["net_savings"],   currency_symbol)],
        [f"Income ({month or 'This Month'})",   fmt_currency(summary["month_income"],  currency_symbol)],
        [f"Expense ({month or 'This Month'})",  fmt_currency(summary["month_expense"], currency_symbol)],
        [f"Savings ({month or 'This Month'})",  fmt_currency(summary["month_savings"], currency_symbol)],
    ]
    tbl = Table(sum_data, colWidths=[10*cm, 7*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), PURPLE),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN",       (1, 0), (1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f8ff")]),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#ddd")),
        ("TOPPADDING",  (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.5*cm))

    # ── Recent transactions table ─────────────────────────────────────────────
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
                str(row.get("note", "") or "")[:30],
            ])
        txn_tbl = Table(txn_data, colWidths=[3*cm, 2.5*cm, 3.5*cm, 3.5*cm, 4.5*cm])
        txn_tbl.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0), DARK),
            ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
            ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5ff")]),
            ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#ddd")),
            ("TOPPADDING",  (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ]))
        story.append(txn_tbl)
    else:
        story.append(Paragraph("No transactions found.", normal_style))

    # ── Goals ─────────────────────────────────────────────────────────────────
    goals = get_goals(user_id)
    if goals:
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph("Savings Goals", h2_style))
        g_data = [["Goal", "Target", "Saved", "Progress %", "Deadline"]]
        for g in goals:
            pct = (g["saved_amount"] / g["target_amount"] * 100) if g["target_amount"] else 0
            g_data.append([
                g["name"],
                fmt_currency(g["target_amount"], currency_symbol),
                fmt_currency(g["saved_amount"],  currency_symbol),
                f"{pct:.1f}%",
                g.get("deadline", "—") or "—",
            ])
        g_tbl = Table(g_data, colWidths=[5*cm, 3.5*cm, 3.5*cm, 3*cm, 3*cm])
        g_tbl.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0), GREEN),
            ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
            ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0fff8")]),
            ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#ddd")),
            ("TOPPADDING",  (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ]))
        story.append(g_tbl)

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#ddd")))
    story.append(Paragraph("Smart Finance Tracker — Confidential Report", normal_style))

    doc.build(story)
    return output.getvalue()
