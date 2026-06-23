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
    Build and return a premium, professional PDF financial report using reportlab.
    Includes branded header, KPI cards, category breakdown with progress bars,
    budget utilization, savings goals with status, transactions, and page numbers.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                     Paragraph, Spacer, HRFlowable,
                                     PageBreak, KeepTogether)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.graphics.shapes import Drawing, Rect, String, Line
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.pdfgen import canvas as pdfcanvas

    output = io.BytesIO()
    page_w, page_h = A4

    # ── Color Palette ─────────────────────────────────────────────────────────
    PURPLE       = colors.HexColor("#6C5CE7")
    PURPLE_LIGHT = colors.HexColor("#A29BFE")
    GREEN        = colors.HexColor("#00B894")
    GREEN_LIGHT  = colors.HexColor("#55EFC4")
    RED          = colors.HexColor("#FF6B6B")
    RED_LIGHT    = colors.HexColor("#FFA8A8")
    BLUE         = colors.HexColor("#0984E3")
    BLUE_LIGHT   = colors.HexColor("#74B9FF")
    ORANGE       = colors.HexColor("#E17055")
    DARK         = colors.HexColor("#2D2D44")
    DARK_ALT     = colors.HexColor("#1E1E30")
    LIGHT_GRAY   = colors.HexColor("#F8F9FA")
    MID_GRAY     = colors.HexColor("#E9ECEF")
    TEXT_DARK    = colors.HexColor("#212529")
    TEXT_MED     = colors.HexColor("#495057")
    TEXT_LIGHT   = colors.HexColor("#868E96")
    WHITE        = colors.white
    CARD_BG      = colors.HexColor("#F1F3F5")

    # ── Paragraph Styles ──────────────────────────────────────────────────────
    title_style = ParagraphStyle(
        "pdf_title", fontSize=26, textColor=WHITE, alignment=TA_CENTER,
        spaceAfter=2, fontName="Helvetica-Bold", leading=30)
    subtitle_style = ParagraphStyle(
        "pdf_subtitle", fontSize=10, textColor=colors.HexColor("#D0D0E8"),
        alignment=TA_CENTER, spaceAfter=6, fontName="Helvetica")
    h2_style = ParagraphStyle(
        "pdf_h2", fontSize=14, textColor=DARK, spaceBefore=16,
        spaceAfter=8, fontName="Helvetica-Bold", leading=18)
    h3_style = ParagraphStyle(
        "pdf_h3", fontSize=11, textColor=PURPLE, spaceBefore=10,
        spaceAfter=5, fontName="Helvetica-Bold")
    label_style = ParagraphStyle(
        "pdf_label", fontSize=8.5, fontName="Helvetica",
        textColor=TEXT_LIGHT, leading=11)
    value_lg_style = ParagraphStyle(
        "pdf_value_lg", fontSize=16, fontName="Helvetica-Bold",
        textColor=TEXT_DARK, leading=20)
    value_style = ParagraphStyle(
        "pdf_value", fontSize=9, fontName="Helvetica", textColor=TEXT_DARK)
    value_bold_style = ParagraphStyle(
        "pdf_value_bold", fontSize=9, fontName="Helvetica-Bold", textColor=TEXT_DARK)
    small_style = ParagraphStyle(
        "pdf_small", fontSize=7.5, fontName="Helvetica", textColor=TEXT_LIGHT)
    footer_style = ParagraphStyle(
        "pdf_footer", fontSize=8, textColor=TEXT_LIGHT, alignment=TA_CENTER)
    center_style = ParagraphStyle(
        "pdf_center", fontSize=9, fontName="Helvetica",
        textColor=TEXT_MED, alignment=TA_CENTER)

    # ── Page Number Callback ──────────────────────────────────────────────────
    def _add_page_extras(canvas_obj, doc_obj):
        """Draw page number at bottom-right and a thin top accent line."""
        canvas_obj.saveState()
        # Top accent gradient bar (thin 3pt stripe)
        canvas_obj.setFillColor(PURPLE)
        canvas_obj.rect(0, page_h - 4, page_w, 4, fill=True, stroke=0)
        # Page number
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.setFillColor(colors.HexColor("#868E96"))
        page_num = canvas_obj.getPageNumber()
        canvas_obj.drawRightString(
            page_w - 1.5*cm, 1*cm,
            f"Page {page_num}")
        # Footer line
        canvas_obj.setStrokeColor(MID_GRAY)
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(1.5*cm, 1.3*cm, page_w - 1.5*cm, 1.3*cm)
        # Footer text
        canvas_obj.drawCentredString(
            page_w / 2, 0.8*cm,
            "Smart Finance Tracker v2.0 • Generated Securely & Locally")
        canvas_obj.restoreState()

    doc = SimpleDocTemplate(
        output, pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=2*cm)

    story = []
    summary = get_summary(user_id, month or current_month())

    # ── Helper: Progress Bar Drawing ──────────────────────────────────────────
    def make_bar(pct, bar_color, width=130, height=10):
        pct = max(0.0, min(100.0, float(pct)))
        d = Drawing(width, height)
        # Background track
        d.add(Rect(0, 1, width, height - 2,
                   fillColor=colors.HexColor("#E9ECEF"),
                   strokeColor=None, rx=3, ry=3))
        # Fill
        fill_w = (pct / 100.0) * width
        if fill_w > 0:
            d.add(Rect(0, 1, fill_w, height - 2,
                       fillColor=bar_color,
                       strokeColor=None, rx=3, ry=3))
        return d

    # ── Helper: Section Divider ───────────────────────────────────────────────
    def section_divider():
        story.append(Spacer(1, 0.3*cm))
        story.append(HRFlowable(
            width="100%", thickness=0.8, color=MID_GRAY,
            spaceBefore=2, spaceAfter=6))

    # ══════════════════════════════════════════════════════════════════════════
    # BRANDED HEADER BLOCK
    # ══════════════════════════════════════════════════════════════════════════
    header_data = [[
        Paragraph("Smart Finance Tracker", title_style),
    ], [
        Paragraph(
            f"Financial Report  •  {month or 'All Time'}  •  {date.today().strftime('%d %B %Y')}",
            subtitle_style),
    ]]
    header_tbl = Table(header_data, colWidths=[page_w - 3*cm])
    header_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, 0), 22),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 18),
        ("LEFTPADDING",   (0, 0), (-1, -1), 20),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 20),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 0.5*cm))

    # ══════════════════════════════════════════════════════════════════════════
    # KPI SUMMARY CARDS (3 colored cards side-by-side)
    # ══════════════════════════════════════════════════════════════════════════
    savings_rate = (
        (summary["month_savings"] / summary["month_income"] * 100)
        if summary["month_income"] > 0 else 0.0
    )
    # Determine card colors based on health
    sav_color = GREEN if summary["month_savings"] >= 0 else RED

    def _kpi_card(title, month_val, all_time_val, accent):
        """Build a mini-table that looks like a KPI card."""
        card_data = [
            [Paragraph(f"<b>{title}</b>", ParagraphStyle(
                "kpi_title", fontSize=8, fontName="Helvetica-Bold",
                textColor=WHITE))],
            [Paragraph(fmt_currency(month_val, currency_symbol), ParagraphStyle(
                "kpi_big", fontSize=18, fontName="Helvetica-Bold",
                textColor=WHITE, leading=22))],
            [Paragraph(f"All-Time: {fmt_currency(all_time_val, currency_symbol)}",
                       ParagraphStyle("kpi_sub", fontSize=7.5,
                                      fontName="Helvetica", textColor=colors.HexColor("#D0D0D0")))],
        ]
        tbl = Table(card_data, colWidths=[5.5*cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), accent),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ]))
        return tbl

    kpi_row = Table(
        [[
            _kpi_card("INCOME", summary["month_income"], summary["total_income"], GREEN),
            _kpi_card("EXPENSES", summary["month_expense"], summary["total_expense"], RED),
            _kpi_card("NET SAVINGS", summary["month_savings"], summary["net_savings"], PURPLE),
        ]],
        colWidths=[6*cm, 6*cm, 6*cm],
        hAlign="CENTER"
    )
    kpi_row.setStyle(TableStyle([
        ("ALIGN",   (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",  (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(kpi_row)
    story.append(Spacer(1, 0.2*cm))

    # Savings rate sub-bar
    rate_label = f"Monthly Savings Rate: {savings_rate:.1f}%"
    rate_data = [[
        Paragraph(f"<b>{rate_label}</b>", ParagraphStyle(
            "rate_lbl", fontSize=9, fontName="Helvetica-Bold", textColor=TEXT_MED)),
        make_bar(savings_rate, GREEN if savings_rate >= 20 else ORANGE if savings_rate >= 0 else RED, width=200, height=12),
    ]]
    rate_tbl = Table(rate_data, colWidths=[8*cm, 10*cm])
    rate_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
        ("ALIGN",      (0, 0), (0, 0), "LEFT"),
        ("ALIGN",      (1, 0), (1, 0), "LEFT"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
    ]))
    story.append(rate_tbl)

    section_divider()

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORY-WISE EXPENSE BREAKDOWN
    # ══════════════════════════════════════════════════════════════════════════
    filters = {"month": month} if month else {}
    df = get_df(user_id, filters)

    if not df.empty:
        exp_df = df[df["type"] == "expense"]
        if not exp_df.empty:
            story.append(Paragraph("Expense Breakdown by Category", h2_style))
            cat_totals = exp_df.groupby("category")["amount"].sum().sort_values(ascending=False)
            total_exp = cat_totals.sum()

            cat_header = [
                Paragraph("<b>Category</b>", value_bold_style),
                Paragraph("<b>Amount</b>", value_bold_style),
                Paragraph("<b>Share</b>", value_bold_style),
                Paragraph("<b>Distribution</b>", value_bold_style),
            ]
            cat_rows = [cat_header]

            # Assign rotating colors for category bars
            cat_colors = [PURPLE, BLUE, GREEN, ORANGE, RED, PURPLE_LIGHT, BLUE_LIGHT]
            for idx, (cat, amt) in enumerate(cat_totals.items()):
                pct = (amt / total_exp * 100) if total_exp > 0 else 0
                bar_c = cat_colors[idx % len(cat_colors)]
                cat_rows.append([
                    Paragraph(str(cat), value_style),
                    Paragraph(fmt_currency(amt, currency_symbol), value_style),
                    Paragraph(f"{pct:.1f}%", value_style),
                    make_bar(pct, bar_c, width=110, height=9),
                ])

            # Totals row
            cat_rows.append([
                Paragraph("<b>TOTAL</b>", value_bold_style),
                Paragraph(f"<b>{fmt_currency(total_exp, currency_symbol)}</b>", value_bold_style),
                Paragraph("<b>100%</b>", value_bold_style),
                Paragraph("", value_style),
            ])

            cat_tbl = Table(cat_rows, colWidths=[5*cm, 4*cm, 2.5*cm, 6.5*cm])
            cat_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, 0), DARK),
                ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
                ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
                ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
                ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -2), [WHITE, LIGHT_GRAY]),
                ("BACKGROUND",    (0, -1), (-1, -1), colors.HexColor("#E8E8ED")),
                ("GRID",          (0, 0), (-1, -1), 0.4, MID_GRAY),
                ("TOPPADDING",    (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ]))
            story.append(cat_tbl)
            section_divider()

    # ══════════════════════════════════════════════════════════════════════════
    # BUDGET vs ACTUAL (if budgets exist)
    # ══════════════════════════════════════════════════════════════════════════
    budgets = get_budgets(user_id, month or current_month())
    if budgets:
        story.append(Paragraph("Budget vs Actual Spending", h2_style))

        # Get actual spending per category for the month
        act_by_cat = {}
        if not df.empty:
            exp_month = df[df["type"] == "expense"]
            if not exp_month.empty:
                act_by_cat = exp_month.groupby("category")["amount"].sum().to_dict()

        b_header = [
            Paragraph("<b>Category</b>", value_bold_style),
            Paragraph("<b>Budget</b>", value_bold_style),
            Paragraph("<b>Spent</b>", value_bold_style),
            Paragraph("<b>Remaining</b>", value_bold_style),
            Paragraph("<b>Usage</b>", value_bold_style),
            Paragraph("<b>Status</b>", value_bold_style),
        ]
        b_rows = [b_header]

        for b in budgets:
            bcat = b["category"]
            blimit = b["amount"]
            spent = act_by_cat.get(bcat, 0)
            remaining = blimit - spent
            usage_pct = (spent / blimit * 100) if blimit > 0 else 0

            if usage_pct > 100:
                status_txt = "OVER"
                status_color = RED
                bar_c = RED
            elif usage_pct >= 80:
                status_txt = "WARNING"
                status_color = ORANGE
                bar_c = ORANGE
            else:
                status_txt = "OK"
                status_color = GREEN
                bar_c = GREEN

            b_rows.append([
                Paragraph(str(bcat), value_style),
                Paragraph(fmt_currency(blimit, currency_symbol), value_style),
                Paragraph(fmt_currency(spent, currency_symbol), value_style),
                Paragraph(fmt_currency(max(remaining, 0), currency_symbol), value_style),
                make_bar(min(usage_pct, 100), bar_c, width=80, height=8),
                Paragraph(f"<b>{status_txt}</b>", ParagraphStyle(
                    "b_status", fontSize=8, fontName="Helvetica-Bold",
                    textColor=status_color)),
            ])

        b_tbl = Table(b_rows, colWidths=[3.5*cm, 2.8*cm, 2.8*cm, 2.8*cm, 3.3*cm, 2.8*cm])
        b_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), PURPLE),
            ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
            ("GRID",          (0, 0), (-1, -1), 0.4, MID_GRAY),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ]))
        story.append(b_tbl)
        section_divider()

    # ══════════════════════════════════════════════════════════════════════════
    # SAVINGS GOALS with Status Indicators
    # ══════════════════════════════════════════════════════════════════════════
    goals = get_goals(user_id)
    if goals:
        story.append(Paragraph("Savings Goals Progress", h2_style))

        g_header = [
            Paragraph("<b>Goal</b>", value_bold_style),
            Paragraph("<b>Target</b>", value_bold_style),
            Paragraph("<b>Saved</b>", value_bold_style),
            Paragraph("<b>Remaining</b>", value_bold_style),
            Paragraph("<b>Progress</b>", value_bold_style),
            Paragraph("<b>Deadline</b>", value_bold_style),
        ]
        g_rows = [g_header]

        for g in goals:
            target = g["target_amount"]
            saved  = g["saved_amount"]
            rem    = max(target - saved, 0)
            pct    = (saved / target * 100) if target > 0 else 0
            dl     = g.get("deadline", "") or ""

            # Color the bar based on progress
            if pct >= 100:
                bar_c = GREEN
            elif pct >= 60:
                bar_c = BLUE
            elif pct >= 30:
                bar_c = ORANGE
            else:
                bar_c = RED

            g_rows.append([
                Paragraph(str(g["name"]), value_style),
                Paragraph(fmt_currency(target, currency_symbol), value_style),
                Paragraph(fmt_currency(saved, currency_symbol), value_style),
                Paragraph(fmt_currency(rem, currency_symbol), value_style),
                make_bar(pct, bar_c, width=90, height=9),
                Paragraph(f"<font size='7.5'>{dl or '—'}</font>",
                          ParagraphStyle("g_dl", fontSize=7.5,
                                         fontName="Helvetica", textColor=TEXT_MED)),
            ])

        g_tbl = Table(g_rows, colWidths=[4*cm, 3*cm, 3*cm, 3*cm, 3*cm, 2*cm])
        g_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), GREEN),
            ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
            ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
            ("GRID",          (0, 0), (-1, -1), 0.4, MID_GRAY),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ]))
        story.append(g_tbl)
        section_divider()

    # ══════════════════════════════════════════════════════════════════════════
    # TRANSACTIONS TABLE (Enhanced with colored type tags)
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("Transaction Details", h2_style))
    max_rows = 50  # Show up to 50 transactions instead of 20

    if not df.empty:
        recent = df.head(max_rows)

        # Income style (green bold) vs expense style (red bold)
        inc_type_style = ParagraphStyle(
            "inc_type", fontSize=8, fontName="Helvetica-Bold", textColor=GREEN)
        exp_type_style = ParagraphStyle(
            "exp_type", fontSize=8, fontName="Helvetica-Bold", textColor=RED)

        txn_header = [
            Paragraph("<b>#</b>", value_bold_style),
            Paragraph("<b>Date</b>", value_bold_style),
            Paragraph("<b>Type</b>", value_bold_style),
            Paragraph("<b>Category</b>", value_bold_style),
            Paragraph("<b>Amount</b>", value_bold_style),
            Paragraph("<b>Payment</b>", value_bold_style),
            Paragraph("<b>Note</b>", value_bold_style),
        ]
        txn_rows = [txn_header]

        for idx, (_, row) in enumerate(recent.iterrows(), 1):
            t = row["type"]
            type_st = inc_type_style if t == "income" else exp_type_style
            txn_rows.append([
                Paragraph(str(idx), small_style),
                Paragraph(str(row["trans_date"].date()), value_style),
                Paragraph(t.upper(), type_st),
                Paragraph(str(row["category"]), value_style),
                Paragraph(fmt_currency(row["amount"], currency_symbol), value_style),
                Paragraph(str(row.get("payment_mode", "") or "—"), small_style),
                Paragraph(str(row.get("note", "") or "")[:35], small_style),
            ])

        txn_tbl = Table(
            txn_rows,
            colWidths=[1*cm, 2.5*cm, 2*cm, 3*cm, 3*cm, 2.5*cm, 4*cm])
        txn_tbl.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0), DARK),
            ("TEXTCOLOR",      (0, 0), (-1, 0), WHITE),
            ("FONTNAME",       (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1, -1), 8),
            ("ALIGN",          (0, 0), (0, -1), "CENTER"),  # # column centered
            ("ALIGN",          (1, 0), (-1, -1), "LEFT"),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
            ("GRID",           (0, 0), (-1, -1), 0.3, MID_GRAY),
            ("TOPPADDING",     (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
            ("LEFTPADDING",    (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 4),
        ]))
        story.append(txn_tbl)

        # Transaction count note
        total_txns = len(df)
        if total_txns > max_rows:
            story.append(Spacer(1, 0.2*cm))
            story.append(Paragraph(
                f"Showing {max_rows} of {total_txns} transactions. "
                f"Download the Excel report for the complete dataset.",
                ParagraphStyle("txn_note", fontSize=7.5, fontName="Helvetica-Oblique",
                               textColor=TEXT_LIGHT, alignment=TA_CENTER)))
    else:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph(
            "No transactions recorded for this period.",
            center_style))

    # ══════════════════════════════════════════════════════════════════════════
    # SUMMARY FOOTER BLOCK
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 0.8*cm))

    # Final summary mini-table
    total_txns = len(df) if not df.empty else 0
    total_goals = len(goals) if goals else 0
    total_budgets = len(budgets) if budgets else 0

    foot_data = [[
        Paragraph(f"<b>{total_txns}</b> Transactions", center_style),
        Paragraph(f"<b>{total_goals}</b> Goals", center_style),
        Paragraph(f"<b>{total_budgets}</b> Budgets", center_style),
        Paragraph(f"<b>{savings_rate:.0f}%</b> Savings Rate", center_style),
    ]]
    foot_tbl = Table(foot_data, colWidths=[4.5*cm, 4.5*cm, 4.5*cm, 4.5*cm])
    foot_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), CARD_BG),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("GRID",          (0, 0), (-1, -1), 0.5, MID_GRAY),
    ]))
    story.append(foot_tbl)

    # Build with page number callbacks
    doc.build(story,
              onFirstPage=_add_page_extras,
              onLaterPages=_add_page_extras)
    return output.getvalue()
