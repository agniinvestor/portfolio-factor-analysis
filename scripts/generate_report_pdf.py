#!/usr/bin/env python3
"""
Generate institutional-quality PDF from ABFRL Equity Research markdown report.
Uses ReportLab for precise layout control.
"""

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Colour palette (Tier-1 brokerage style) ────────────────────────────────
BRAND_DARK   = colors.HexColor("#0D2B4E")   # Navy — headers, rules
BRAND_GOLD   = colors.HexColor("#C8972A")   # Gold — accents, verdict strip
BRAND_LIGHT  = colors.HexColor("#EEF3F8")   # Light blue-grey — table bands
CALLOUT_BG   = colors.HexColor("#FFF8E6")   # Warm yellow — insight boxes
WARNING_BG   = colors.HexColor("#FFF0F0")   # Pink — warning boxes
MUTED_TEXT   = colors.HexColor("#555555")
TABLE_HEADER = colors.HexColor("#1A3A5C")

PAGE_W, PAGE_H = A4
MARGIN        = 18 * mm

# ── Style definitions ───────────────────────────────────────────────────────
base = getSampleStyleSheet()

def S(name, **kw):
    """Shorthand for ParagraphStyle."""
    return ParagraphStyle(name, **kw)

STYLES = {
    "report_header":  S("report_header",
        fontName="Helvetica-Bold", fontSize=7, textColor=colors.white,
        alignment=TA_CENTER, leading=10),
    "company_name":   S("company_name",
        fontName="Helvetica-Bold", fontSize=22, textColor=BRAND_DARK,
        alignment=TA_CENTER, leading=26, spaceAfter=2),
    "tagline":        S("tagline",
        fontName="Helvetica-Oblique", fontSize=10, textColor=MUTED_TEXT,
        alignment=TA_CENTER, leading=14, spaceAfter=6),
    "meta_text":      S("meta_text",
        fontName="Helvetica", fontSize=8, textColor=MUTED_TEXT,
        alignment=TA_CENTER, leading=11),
    "section":        S("section",
        fontName="Helvetica-Bold", fontSize=12, textColor=colors.white,
        leading=16, spaceBefore=10, spaceAfter=4),
    "subsection":     S("subsection",
        fontName="Helvetica-Bold", fontSize=10, textColor=BRAND_DARK,
        leading=14, spaceBefore=8, spaceAfter=3),
    "body":           S("body",
        fontName="Helvetica", fontSize=9, textColor=colors.black,
        leading=13, spaceAfter=4),
    "body_bold":      S("body_bold",
        fontName="Helvetica-Bold", fontSize=9, textColor=colors.black,
        leading=13, spaceAfter=4),
    "callout":        S("callout",
        fontName="Helvetica", fontSize=8.5, textColor=colors.HexColor("#3A2A00"),
        leading=12.5, leftIndent=6, rightIndent=6, spaceAfter=3),
    "callout_title":  S("callout_title",
        fontName="Helvetica-Bold", fontSize=9, textColor=colors.HexColor("#3A2A00"),
        leading=13, leftIndent=6, spaceAfter=2),
    "warning":        S("warning",
        fontName="Helvetica", fontSize=8.5, textColor=colors.HexColor("#5A0000"),
        leading=12.5, leftIndent=6, rightIndent=6, spaceAfter=3),
    "warning_title":  S("warning_title",
        fontName="Helvetica-Bold", fontSize=9, textColor=colors.HexColor("#5A0000"),
        leading=13, leftIndent=6, spaceAfter=2),
    "table_header":   S("table_header",
        fontName="Helvetica-Bold", fontSize=8, textColor=colors.white,
        alignment=TA_CENTER, leading=10),
    "table_cell":     S("table_cell",
        fontName="Helvetica", fontSize=8, textColor=colors.black,
        alignment=TA_LEFT, leading=10),
    "table_cell_c":   S("table_cell_c",
        fontName="Helvetica", fontSize=8, textColor=colors.black,
        alignment=TA_CENTER, leading=10),
    "table_cell_r":   S("table_cell_r",
        fontName="Helvetica", fontSize=8, textColor=colors.black,
        alignment=TA_RIGHT, leading=10),
    "table_cell_b":   S("table_cell_b",
        fontName="Helvetica-Bold", fontSize=8, textColor=colors.black,
        alignment=TA_LEFT, leading=10),
    "footer":         S("footer",
        fontName="Helvetica", fontSize=6.5, textColor=MUTED_TEXT,
        alignment=TA_CENTER, leading=9),
    "disclaimer":     S("disclaimer",
        fontName="Helvetica", fontSize=7.5, textColor=MUTED_TEXT,
        leading=11, spaceAfter=3),
    "bullet":         S("bullet",
        fontName="Helvetica", fontSize=9, textColor=colors.black,
        leading=13, leftIndent=12, spaceAfter=2, bulletIndent=4),
}

# ── Helper: coloured section header bar ────────────────────────────────────
def section_header(text, color=BRAND_DARK):
    p = Paragraph(f"<b>{text}</b>", STYLES["section"])
    t = Table([[p]], colWidths=[PAGE_W - 2 * MARGIN])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    return t

def subsection_header(text):
    return Paragraph(f"<b>{text}</b>", STYLES["subsection"])

def body(text):
    # Convert markdown bold to reportlab bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    return Paragraph(text, STYLES["body"])

def rule(color=BRAND_GOLD, thickness=1.5):
    return HRFlowable(width="100%", thickness=thickness,
                      color=color, spaceAfter=4, spaceBefore=4)

def spacer(h=4):
    return Spacer(1, h * mm)

def callout_box(title, lines, is_warning=False):
    """Render a tinted callout / warning box."""
    bg   = WARNING_BG if is_warning else CALLOUT_BG
    ts   = STYLES["warning_title"] if is_warning else STYLES["callout_title"]
    bs   = STYLES["warning"] if is_warning else STYLES["callout"]
    icon = "⚠  " if is_warning else "●  "
    elems = [Paragraph(f"{icon}{title}", ts)]
    for line in lines:
        line = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', line)
        line = re.sub(r'\*(.+?)\*', r'<i>\1</i>', line)
        elems.append(Paragraph(line, bs))
    inner = Table([[e] for e in elems],
                  colWidths=[PAGE_W - 2 * MARGIN - 16])
    inner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    border = Table([[inner]], colWidths=[PAGE_W - 2 * MARGIN])
    bcolor = colors.HexColor("#B05000") if is_warning else colors.HexColor("#B08000")
    border.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.5, bcolor),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return KeepTogether([border, spacer(3)])

def make_table(headers, rows, col_widths=None, stripe=True, highlight_col=None):
    """Build a styled data table."""
    avail = PAGE_W - 2 * MARGIN
    if col_widths is None:
        n = len(headers)
        col_widths = [avail / n] * n

    def fmt(cell, is_header=False):
        cell = str(cell) if cell is not None else ""
        cell = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', cell)
        cell = re.sub(r'\*(.+?)\*', r'<i>\1</i>', cell)
        if is_header:
            return Paragraph(cell, STYLES["table_header"])
        if cell.startswith("✅") or cell.startswith("⚠️") or cell.startswith("⚠"):
            return Paragraph(cell, STYLES["table_cell_c"])
        if cell.startswith("**"):
            return Paragraph(cell, STYLES["table_cell_b"])
        return Paragraph(cell, STYLES["table_cell"])

    data = [[fmt(h, True) for h in headers]]
    for row in rows:
        data.append([fmt(c) for c in row])

    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND",    (0, 0), (-1, 0),  TABLE_HEADER),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, BRAND_LIGHT] if stripe else [colors.white]),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]
    t.setStyle(TableStyle(style))
    return t

# ── Page template with header / footer ────────────────────────────────────
class ReportCanvas:
    """Mixin-style canvas callbacks for page header/footer."""
    def __init__(self, filename, **kw):
        self._filename = filename

    @staticmethod
    def on_page(canvas, doc):
        w, h = A4
        # Top strip
        canvas.saveState()
        canvas.setFillColor(BRAND_DARK)
        canvas.rect(0, h - 10 * mm, w, 10 * mm, fill=1, stroke=0)
        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(colors.white)
        canvas.drawString(MARGIN, h - 6 * mm,
                          "ADITYA BIRLA FASHION AND RETAIL LIMITED (NSE: ABFRL)")
        canvas.drawRightString(w - MARGIN, h - 6 * mm,
                               "EQUITY RESEARCH  ·  APRIL 2026")
        # Gold accent line
        canvas.setStrokeColor(BRAND_GOLD)
        canvas.setLineWidth(1.5)
        canvas.line(0, h - 10 * mm, w, h - 10 * mm)
        # Footer
        canvas.setFillColor(MUTED_TEXT)
        canvas.setFont("Helvetica", 6.5)
        canvas.drawCentredString(w / 2, 8 * mm,
            f"For informational use only  ·  Not a SEBI-registered research report  ·  Page {doc.page}")
        canvas.setStrokeColor(BRAND_GOLD)
        canvas.setLineWidth(0.8)
        canvas.line(MARGIN, 12 * mm, w - MARGIN, 12 * mm)
        canvas.restoreState()

# ── Build the PDF ──────────────────────────────────────────────────────────
def build():
    out_path = Path(__file__).parent.parent / "docs" / "ABFRL_Equity_Research_April2026.pdf"
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title="ABFRL Equity Research — April 2026",
        author="Portfolio Research Desk",
        subject="NSE: ABFRL — Buy on Dips, Target ₹95",
    )

    story = []
    avail = PAGE_W - 2 * MARGIN

    # ── COVER ──────────────────────────────────────────────────────────────
    story.append(spacer(4))
    # Brand strip
    cover_strip = Table(
        [[Paragraph("EQUITY RESEARCH  ·  NSE: ABFRL  ·  CONSUMER DISCRETIONARY",
                    STYLES["report_header"])]],
        colWidths=[avail],
    )
    cover_strip.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_DARK),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(cover_strip)

    # Gold rule
    story.append(HRFlowable(width="100%", thickness=3, color=BRAND_GOLD,
                             spaceBefore=0, spaceAfter=6))

    story.append(Paragraph("ADITYA BIRLA FASHION AND RETAIL LIMITED",
                            STYLES["company_name"]))
    story.append(Paragraph(
        "India's Post-Demerger Fashion Turnaround — "
        "Ethnic Jewel, Value Retail Drag, Distressed Entry Price",
        STYLES["tagline"]))

    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#CCCCCC"),
                             spaceBefore=2, spaceAfter=6))

    # Meta row
    meta = Table([[
        Paragraph("Exchange / Ticker<br/><b>NSE: ABFRL  ·  BSE: 535755</b>", STYLES["meta_text"]),
        Paragraph("Sector<br/><b>Consumer Discretionary / Fashion Retail</b>", STYLES["meta_text"]),
        Paragraph("Report Date<br/><b>April 12, 2026</b>", STYLES["meta_text"]),
        Paragraph("Data Through<br/><b>Q3 FY26 (Dec 2025)</b>", STYLES["meta_text"]),
    ]], colWidths=[avail / 4] * 4)
    meta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_LIGHT),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEAFTER",     (0, 0), (-2, -1), 0.5, colors.HexColor("#AAAAAA")),
    ]))
    story.append(meta)
    story.append(spacer(4))

    # ── PRICE SNAPSHOT ─────────────────────────────────────────────────────
    snap_title = Table(
        [[Paragraph(" PRICE SNAPSHOT  —  As of April 10, 2026 (NSE close via Google Finance)",
                    STYLES["report_header"])]],
        colWidths=[avail],
    )
    snap_title.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1A3A5C")),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(snap_title)

    snap = Table([[
        Paragraph("CMP<br/><b>₹60.33</b>",         STYLES["table_header"]),
        Paragraph("Prev. Close<br/><b>₹58.43</b>",  STYLES["table_header"]),
        Paragraph("52W High<br/><b>₹107.75</b>",    STYLES["table_header"]),
        Paragraph("52W Low<br/><b>₹53.51</b>",      STYLES["table_header"]),
        Paragraph("Market Cap<br/><b>~₹7,360 Cr</b>",STYLES["table_header"]),
        Paragraph("Shares Out.<br/><b>~122 Cr</b>", STYLES["table_header"]),
        Paragraph("P/B<br/><b>1.18x</b>",           STYLES["table_header"]),
    ]], colWidths=[avail / 7] * 7)
    snap.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#213E5E")),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEAFTER",     (0, 0), (-2, -1), 0.5, colors.HexColor("#3A5A7E")),
    ]))
    story.append(snap)
    story.append(Paragraph(
        "Prices reflect last NSE close. Source: Google Finance card (Dhan.co snippet), Apr 10 2026. "
        "Verify current price on NSE/BSE before trading.",
        ParagraphStyle("snap_note", fontName="Helvetica-Oblique", fontSize=7,
                       textColor=MUTED_TEXT, alignment=TA_CENTER, leading=10, spaceBefore=3)
    ))
    story.append(spacer(4))

    # ── INVESTMENT VERDICT BOX ─────────────────────────────────────────────
    verdict_inner = [
        [Paragraph("INVESTMENT VERDICT", ParagraphStyle(
            "vt", fontName="Helvetica-Bold", fontSize=11,
            textColor=colors.white, alignment=TA_CENTER))],
        [Table([[
            Paragraph("Rating<br/><b>BUY ON DIPS</b>",       STYLES["table_header"]),
            Paragraph("Target (18M Base)<br/><b>₹85–100</b>",STYLES["table_header"]),
            Paragraph("Bull Case<br/><b>₹120–130</b>",        STYLES["table_header"]),
            Paragraph("Bear Case<br/><b>₹40–50</b>",          STYLES["table_header"]),
            Paragraph("Accumulate Zone<br/><b>₹55–65</b>",    STYLES["table_header"]),
            Paragraph("Stop-Loss<br/><b>₹48</b>",             STYLES["table_header"]),
        ]], colWidths=[(avail - 12) / 6] * 6,
        style=TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#1A3A0A")),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LINEAFTER",     (0, 0), (-2, -1), 0.5, colors.HexColor("#3A6A1A")),
        ]))],
        [Paragraph(
            "Long-Term Contrarian Entry  ·  18–24 Month Horizon  ·  Position Size: 3–5% of equity portfolio",
            ParagraphStyle("vs", fontName="Helvetica-Oblique", fontSize=8.5,
                           textColor=colors.HexColor("#CCFFCC"), alignment=TA_CENTER))],
        [Paragraph(
            "Upside from CMP ₹60.33:  +41–66% (base)  ·  +99–115% (bull)  ·  Downside: -17 to -34% (bear)",
            ParagraphStyle("vup", fontName="Helvetica", fontSize=8,
                           textColor=colors.HexColor("#AAFFAA"), alignment=TA_CENTER))],
    ]
    verdict = Table(verdict_inner, colWidths=[avail])
    verdict.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#0D3A0D")),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("BOX",           (0, 0), (-1, -1), 2, BRAND_GOLD),
    ]))
    story.append(verdict)
    story.append(spacer(5))

    # ── SECTION 1: EXECUTIVE SUMMARY ───────────────────────────────────────
    story.append(section_header("1.  EXECUTIVE SUMMARY & KEY CATALYST"))
    story.append(spacer(2))

    story.append(body(
        "The most important thing to understand about ABFRL today is that "
        "<b>the company that existed two years ago no longer exists</b>. "
        "The demerger of Madura Fashion & Lifestyle (Louis Philippe, Van Heusen, Allen Solly, "
        "Peter England) into separately listed Aditya Birla Lifestyle Brands Limited (ABLBL), "
        "effective May 1, 2025, has created a fundamentally different investment proposition."
    ))
    story.append(body(
        "Post-demerger ABFRL is a bet on three converging stories: a struggling-but-transforming "
        "Pantaloons value-fashion chain, a fast-growing ethnic wear portfolio in a structurally "
        "expanding market, and a nascent D2C digital brand platform (TMRW) approaching profitability."
    ))

    story.append(subsection_header("Financial Transformation Is Real"))
    fin_rows = [
        ["₹4,239 Cr equity raise (Jan 2025)", "Debt halved: ₹9,451 Cr → ₹5,017 Cr (Mar 2024 → Mar 2025)  [Source: ICRA, Apr 2025]"],
        ["Operating Cash Flow FY25", "₹1,644 Cr — cash-generative despite reported losses"],
        ["Free Cash Flow FY25", "₹1,051 Cr — accelerating as interest costs decline"],
        ["Q3 FY26 Normalized PAT", "+₹115 Cr (reported -₹137 Cr includes ₹28.48 Cr one-off Labour Code provision)"],
        ["Ethnic Wear — Q3 FY26", "+20% YoY revenue; 22.7% EBITDA margin (+350 bps YoY); 8th consecutive growth quarter"],
        ["TMRW — Q3 FY26", "+29% YoY; ~900 bps EBITDA margin improvement  [Source: ABFRL Q3 FY26 Earnings Call, Feb 2026]"],
    ]
    story.append(make_table(
        ["Key Metric", "Detail"],
        fin_rows,
        col_widths=[avail * 0.35, avail * 0.65],
    ))
    story.append(spacer(3))

    story.append(body(
        "At ₹60.33 — trading at 1.18x book value and within 13% of its 52-week low — "
        "ABFRL represents one of the few large-cap Indian consumer names where valuation is "
        "clearly distressed relative to underlying asset quality. The AA credit rating "
        "(ICRA/CRISIL) underscores that the Aditya Birla Group backstop limits existential risk. "
        "This is a high-patience, high-conviction turnaround trade."
    ))

    story.append(callout_box(
        "Key Insight — The Invisible Inflection",
        [
            "ABFRL's normalized Q3 FY26 PAT of +₹115 Cr is absent from mainstream headlines "
            "because the reported loss is ₹137 Cr. Investors willing to look through one-time "
            "items and model the interest-cost trajectory are seeing an approaching earnings "
            "inflection the market has not yet priced.",
            "The triggering event: Q4 FY26 results (May 2026), which benefit from the deferred "
            "Pantaloons EOSS sale and the seasonally strongest quarter for ethnic wear.",
        ],
    ))

    # ── SECTION 2: MACRO ───────────────────────────────────────────────────
    story.append(section_header("2.  MACROECONOMIC PARADIGM: INDIA ORGANISED FASHION RETAIL"))
    story.append(spacer(2))
    story.append(body(
        "India's fashion and apparel market is estimated at ~₹8,00,000–8,40,000 Cr, "
        "with organised retail penetration still below 35% [Source: IBEF Textile & Apparel Report]. "
        "Organised fashion retail is growing at 12–15% CAGR; ethnic wear at 15–18% CAGR."
    ))
    macro_rows = [
        ["Income tax relief (Union Budget FY26)", "Expands discretionary spend for Pantaloons' middle-class customer base"],
        ["GST compliance enforcement",            "Disadvantages unorganised fashion competitors; supports organised market share gain"],
        ["PLI for textile sector",                "Supports supply-chain cost efficiency for ABFRL's apparel sourcing"],
        ["Digital public infrastructure (UPI/ONDC)", "Lowers TMRW's D2C customer acquisition cost"],
    ]
    story.append(make_table(
        ["Policy / Initiative", "Impact on ABFRL"],
        macro_rows,
        col_widths=[avail * 0.4, avail * 0.6],
    ))
    story.append(spacer(3))

    # ── SECTION 3: OPERATIONAL ARCHITECTURE ───────────────────────────────
    story.append(section_header("3.  OPERATIONAL ARCHITECTURE"))
    story.append(spacer(2))
    story.append(subsection_header("3.1  Pantaloons — Core Engine Under Transformation"))
    story.append(body(
        "India's leading multi-brand value fashion retailer with <b>412 stores</b> across "
        "~7.7 million sq ft as of Q3 FY26 [Source: ABFRL Q3 FY26 Results, Feb 2026]. "
        "Pantaloons posted -2% YoY revenue decline in Q3 FY26 — but management deliberately "
        "deferred the EOSS from December to January 2026 to capture better margins. "
        "Adjusted LTL: +3% underlying. Suraj Bahirwani appointed new CEO (April 2026) "
        "with mandate for format overhaul and Style Up sub-format expansion to 250 stores."
    ))
    story.append(callout_box(
        "Pantaloons Competitive Risk",
        [
            "Trent's Zudio format — scaled to 700+ stores with 14–15% EBITDA margins — "
            "is the most direct competitive threat. Reliance Retail's fashion formats add further pressure.",
            "Pantaloons' ability to sustain positive LTL sales is the #1 execution risk "
            "for the investment thesis. A sustained negative LTL invalidates the base case "
            "regardless of ethnic wear strength.",
        ],
        is_warning=True,
    ))

    story.append(subsection_header("3.2  Ethnic Wear — The Growth Engine"))
    story.append(body(
        "Portfolio: <b>Tasva</b> (premium Indian occasion wear), <b>Sabyasachi Mukherjee</b> "
        "partnership (luxury couture), <b>The Label</b> (accessible luxury), and designer-led brands. "
        "Delivered <b>eight consecutive quarters of growth</b>, reaching +20% YoY in Q3 FY26 "
        "with EBITDA margins of <b>22.7%</b> (+350 bps YoY). Designer-led brands grew 30%+. "
        "[Source: ABFRL Q3 FY26; Whalesbook, Feb 2026]"
    ))

    story.append(subsection_header("3.3  TMRW — The Digital-First Bet"))
    story.append(body(
        "Portfolio of digital-native D2C fashion brands targeting Gen Z and young millennials. "
        "Grew <b>29% YoY</b> in Q3 FY26 with EBITDA margins improving ~900 bps — from deeply "
        "loss-making toward near-breakeven. [Source: ABFRL Q3 FY26 Results, Feb 2026]"
    ))

    # ── SECTION 4: MOAT & TAM ──────────────────────────────────────────────
    story.append(section_header("4.  COMPETITIVE MOAT & TOTAL ADDRESSABLE MARKET"))
    story.append(spacer(2))
    story.append(body(
        "ABFRL's moat is a <b>brand portfolio and real-estate scale advantage</b> built over decades. "
        "The 412-store Pantaloons estate — anchored in premium mall locations — would cost "
        "₹10,000+ Cr to replicate at current real-estate costs. The Sabyasachi partnership "
        "(exclusivity, cultural capital, pricing power) cannot be replicated through capital alone. "
        "The ethnic portfolio's 3–4 distinct price tiers enable customer migration up the price "
        "ladder — creating a lifetime fashion journey within the ABFRL ecosystem."
    ))
    story.append(callout_box(
        "Brand Portfolio Barrier",
        ["ABFRL's multi-tier ethnic architecture provides cross-selling and price-ladder "
         "opportunities that single-brand competitors cannot replicate. A customer introduced "
         "through Pantaloons ethnic collection can migrate to Tasva and eventually to Sabyasachi "
         "— creating a lifetime fashion ecosystem proprietary to ABFRL."],
    ))

    story.append(subsection_header("Total Addressable Market"))
    tam_rows = [
        ["Total India Fashion & Apparel",  "~8,00,000",         "8–10%",  "IBEF"],
        ["Organised Fashion Retail",       "~2,50,000",         "12–15%", "IBEF / Apparel Resources"],
        ["Ethnic Wear (organised)",        "~90,000–1,00,000",  "15–18%", "Industry estimates"],
        ["Value Fashion (organised)",      "~50,000–60,000",    "15–20%", "Industry estimates"],
        ["D2C Fashion (India)",            "~20,000–25,000",    "30%+",   "DPIIT / Industry"],
    ]
    story.append(make_table(
        ["Market Segment", "Size (₹ Cr)", "CAGR", "Source"],
        tam_rows,
        col_widths=[avail * 0.40, avail * 0.22, avail * 0.12, avail * 0.26],
    ))
    story.append(body(
        "<b>ABFRL's Position (FY26E):</b> Revenue ~₹8,500 Cr = ~3.4% of organised fashion market. "
        "Ethnic revenue ~₹800–1,000 Cr = <1% of ethnic TAM — substantial runway."
    ))
    story.append(spacer(3))

    # ── SECTION 5: FINANCIALS ──────────────────────────────────────────────
    story.append(section_header("5.  FINANCIAL PERFORMANCE"))
    story.append(Paragraph(
        "All figures in ₹ Crore unless stated. Source: Screener.in (fetched April 10, 2026) "
        "and ABFRL BSE filings.",
        STYLES["disclaimer"],
    ))
    story.append(spacer(2))

    story.append(subsection_header("5.1  Annual Revenue & Profitability"))
    ann_rows = [
        ["Revenue",         "5,249", "8,136", "12,418", "6,441", "7,351",    "6,187"],
        ["Operating Profit","583",   "1,138", "1,557",  "408",   "699",      "~910 est."],
        ["OPM %",           "11%",   "14%",   "13%",    "6%",    "10%",      "~14.7%"],
        ["Net Profit",      "-736",  "-118",  "-59",    "-736",  "-456",     "~-185"],
        ["EPS (₹)",         "-7.93", "-1.16", "-0.38",  "-6.19", "-3.08",    "—"],
    ]
    story.append(make_table(
        ["Metric (₹ Cr)", "FY21", "FY22", "FY23*", "FY24", "FY25", "9M FY26"],
        ann_rows,
        col_widths=[avail*0.25, avail*0.10, avail*0.10, avail*0.11, avail*0.10, avail*0.10, avail*0.14],
    ))
    story.append(Paragraph(
        "*FY23 includes combined pre-demerger entity (Madura + ABFRL). "
        "Post-demerger run-rate: ₹7,000–8,500 Cr. [Source: Screener.in, Apr 2026]",
        STYLES["disclaimer"],
    ))
    story.append(spacer(2))
    story.append(body(
        "<b>Margin recovery in progress:</b> OPM 6% (FY24) → 10% (FY25) → ~14.7% (9M FY26) — "
        "+870 bps expansion driven by Pantaloons gross margin recovery, ethnic scale, "
        "and post-restructuring cost discipline."
    ))

    story.append(subsection_header("5.2  Quarterly Performance — FY26"))
    q_rows = [
        ["Q1 FY26 (Apr–Jun 25)",  "~1,813 est.", "~220 est.", "~12%",  "—"],
        ["Q2 FY26 (Jul–Sep 25)",  "~2,000 est.", "~300 est.", "~15%",  "—"],
        ["**Q3 FY26 (Oct–Dec 25)","**2,374",     "**370",     "**15.6%","**-137 (norm. +115)"],
        ["**9M FY26 Total",       "**6,187",     "**~910 est.","**~14.7%","—"],
    ]
    story.append(make_table(
        ["Quarter", "Revenue (₹ Cr)", "EBITDA (₹ Cr)", "EBITDA %", "Net Profit (₹ Cr)"],
        q_rows,
        col_widths=[avail*0.28, avail*0.18, avail*0.18, avail*0.14, avail*0.22],
    ))

    story.append(callout_box(
        "Q3 FY26 Reported Loss — Explained",
        [
            "The headline ₹137 Cr loss masks a normalized PAT of +₹115 Cr. Three items bridge the gap:",
            "1.  ₹28.48 Cr one-off Labour Code provisions",
            "2.  Residual interest costs on ₹5,665 Cr debt (declining 44% to ₹497 Cr FY26E per Trendlyne)",
            "3.  Ind AS 116 lease amortization on 7.7 mn sq ft retail estate",
            "On a cash basis, ABFRL is operationally profitable.",
        ],
        is_warning=False,
    ))

    story.append(subsection_header("5.3  Balance Sheet Architecture"))
    bs_rows = [
        ["Equity Capital",  "1,015",  "1,220",  "1,220"],
        ["Reserves",        "3,007",  "5,592",  "5,032"],
        ["**Total Equity",  "**4,022","**6,812","**6,252"],
        ["**Borrowings",    "**9,451","**5,017","**5,665"],
        ["Total Assets",    "21,790", "16,394", "17,641"],
    ]
    story.append(make_table(
        ["Item (₹ Cr)", "Mar 2024", "Mar 2025", "Sep 2025"],
        bs_rows,
        col_widths=[avail*0.40, avail*0.20, avail*0.20, avail*0.20],
    ))
    story.append(Paragraph("[Source: Screener.in, Apr 2026]", STYLES["disclaimer"]))
    story.append(body(
        "Borrowings halved from ₹9,451 Cr (Mar 2024) to ₹5,017 Cr (Mar 2025), "
        "funded by the ₹4,239.4 Cr equity raise (Jan 2025: ₹2,379 Cr preferential + ₹1,860 Cr QIP). "
        "[Source: ICRA rating rationale, April 2025]. Modest uptick to ₹5,665 Cr in Sep 2025 "
        "reflects seasonal working capital build."
    ))
    story.append(callout_box(
        "Balance Sheet Watch",
        [
            "Debt/EBITDA: ~8x on FY25 EBITDA, rapidly improving to ~4.4x on FY26E run-rate EBITDA "
            "of ~₹1,275 Cr. Still elevated but declining.",
            "Key risk: any additional equity raise will dilute existing shareholders. "
            "Monitor quarterly debt disclosures and equity-raise announcements.",
        ],
        is_warning=True,
    ))

    story.append(subsection_header("5.4  Cash Flow Analysis"))
    cf_rows = [
        ["Operating Cash Flow",   "1,067","1,395","1,341","**1,644"],
        ["Investing Cash Flow",   "-1,155","-2,108","-2,992","-1,665"],
        ["Free Cash Flow (est.)", "~300",  "~400",  "~600", "**1,051"],
    ]
    story.append(make_table(
        ["Cash Flows (₹ Cr)", "FY22", "FY23", "FY24", "FY25"],
        cf_rows,
        col_widths=[avail*0.42, avail*0.145, avail*0.145, avail*0.145, avail*0.145],
    ))
    story.append(Paragraph("[Source: Screener.in, Apr 2026]", STYLES["disclaimer"]))

    story.append(subsection_header("5.5  Capital Efficiency Ratios"))
    ratio_rows = [
        ["Debtor Days",   "22",   "35",   "73",   "**19",    "✅ Sharp improvement"],
        ["Inventory Days","320",  "277",  "532",  "**282",   "⚠  Still elevated vs 90–120 day benchmark"],
        ["ROCE %",        "9%",   "6%",   "-3%",  "-3%",     "→ Bottoming"],
        ["ROE %",         "-2%",  "-1%",  "-18%", "-11%",    "↑ Recovering"],
    ]
    story.append(make_table(
        ["Metric", "FY22", "FY23", "FY24", "FY25", "Trend"],
        ratio_rows,
        col_widths=[avail*0.22, avail*0.10, avail*0.10, avail*0.10, avail*0.10, avail*0.38],
    ))
    story.append(Paragraph("[Source: Screener.in, Apr 2026]", STYLES["disclaimer"]))
    story.append(spacer(3))

    # ── SECTION 5A: MANAGEMENT ─────────────────────────────────────────────
    story.append(section_header("5A.  MANAGEMENT QUALITY & CORPORATE GOVERNANCE"))
    story.append(spacer(2))
    story.append(body(
        "ABFRL is part of the <b>Aditya Birla Group</b> — one of India's largest conglomerates "
        "($65 Bn+ revenue), chaired by Kumar Mangalam Birla. Promoter entities: "
        "Birla Group Holdings (17.40%), IGH Holdings (11.18%), Grasim Industries (8.00%) — "
        "collectively 46.61% [Source: Trendlyne shareholding, Dec 2025]."
    ))

    gov_rows = [
        ["Auditor quality",           "Big 4 / S.R. Batliboi (EY affiliate)", "Annual report",       "✅"],
        ["Credit rating",             "ICRA AA/Stable; CRISIL AA/Positive",   "ICRA Apr 2025",       "✅"],
        ["Promoter pledging",         "7.18% locked (40.8 Mn shares)",        "Trendlyne Dec 2025",  "⚠"],
        ["Promoter holding trend",    "Declining: 55.45% → 46.61% (3 years)", "BSE shareholding",    "⚠"],
        ["SEBI enforcement actions",  "None identified",                       "SEBI/BSE search",     "✅"],
        ["Audit qualifications",      "Clean",                                 "Auditor's report",    "✅"],
    ]
    story.append(make_table(
        ["Parameter", "Status", "Evidence", "Rating"],
        gov_rows,
        col_widths=[avail*0.26, avail*0.38, avail*0.24, avail*0.12],
    ))
    story.append(body(
        "<b>Overall Governance Rating: Adequate</b> — Aditya Birla Group institutional standards. "
        "Declining promoter stake and 7.18% pledging are watch items, not red flags at current levels."
    ))

    story.append(callout_box(
        "Management Signal Tracker",
        [
            "Q4 FY25: EBITDA tripled to ₹295 Cr vs ₹35 Cr Q4 FY24 — delivered on guidance  [Source: Business Standard, May 2025]",
            "Q3 FY26: Interest expense guided to decline 44% to ₹497 Cr FY26E [Source: Trendlyne]; "
            "normalized PAT +₹115 Cr before Labour Code provision",
            "Ethnic: 8 consecutive growth quarters; 22.7% EBITDA margin positioning ethnic as long-term crown jewel",
            "Watch for: Q4 FY26 results confirming EOSS contribution and first reported PAT-positive quarter",
        ],
    ))

    # Shareholding pattern
    story.append(subsection_header("Shareholding Pattern"))
    sh_rows = [
        ["Promoters", "55.45%", "46.61%", "46.61%", "46.61%", "↓ Declining (stable last 3Q)"],
        ["FIIs",      "14.15%", "22.16%", "17.63%", "18.36%", "→ Broadly stable"],
        ["DIIs",      "17.00%", "14.70%", "12.08%", "**7.93%","↓↓ Rapid exit"],
        ["Mutual Funds","—",    "10.29%", "9.93%",  "**5.44%","↓↓ Exiting"],
        ["Public",    "12.91%", "17.39%", "26.89%", "26.79%", "↑↑ Rising"],
    ]
    story.append(make_table(
        ["Holder", "Dec 2023", "Mar 2025", "Jun 2025", "Dec 2025", "Trend"],
        sh_rows,
        col_widths=[avail*0.18, avail*0.12, avail*0.12, avail*0.12, avail*0.12, avail*0.34],
    ))
    story.append(Paragraph("[Source: Trendlyne shareholding; Screener.in, Dec 2025]", STYLES["disclaimer"]))
    story.append(spacer(3))

    # ── SECTION 5B: DuPont ─────────────────────────────────────────────────
    story.append(section_header("5B.  DuPONT ANALYSIS — ROE ATTRIBUTION"))
    story.append(spacer(2))
    dp_rows = [
        ["Net Profit Margin",    "-0.5%",  "-11.4%", "-6.2%",   "↑ Improving",   "Structural losses narrowing"],
        ["Asset Turnover (x)",   "0.57",   "0.30",   "0.45",    "↑ Recovering",  "Demerger distorted FY24; recovering"],
        ["Equity Multiplier (x)","5.8",    "5.4",    "**2.4",   "↓ Declining",   "Equity raise dramatically reduced leverage"],
        ["**ROE (%)",            "**-1.6%","**-18.3%","**-10.9%","**↑ Improving",""],
    ]
    story.append(make_table(
        ["Component", "FY23", "FY24", "FY25", "Trend", "Implication"],
        dp_rows,
        col_widths=[avail*0.25, avail*0.10, avail*0.10, avail*0.10, avail*0.17, avail*0.28],
    ))
    story.append(Paragraph("[Source: Screener.in; computed from annual financials]", STYLES["disclaimer"]))
    story.append(body(
        "The equity multiplier drop from 5.4x to 2.4x is the most significant structural change. "
        "When PAT turns positive, ROE expansion will be rapid given operating leverage in the model."
    ))
    story.append(spacer(3))

    # ── SECTION 5C: ROIC/WACC ─────────────────────────────────────────────
    story.append(section_header("5C.  ROIC vs WACC — VALUE CREATION ANALYSIS"))
    story.append(spacer(2))
    wacc_rows = [
        ["Risk-free rate (10Y G-Sec)",   "6.8%",   "RBI, approximate current yield"],
        ["Beta",                          "1.2",    "High-beta consumer discretionary; Trendlyne estimated"],
        ["Equity Risk Premium (India)",   "6.0%",   "Standard India ERP"],
        ["**Cost of Equity (Ke)",        "**14.0%","= 6.8% + (1.2 × 6.0%)"],
        ["Cost of Debt (post-tax)",       "6.5%",   "~9.0% pre-tax"],
        ["Capital structure (FY25)",      "53% / 47%","Equity / Debt; Screener.in"],
        ["**WACC",                        "**~10.5%",""],
    ]
    story.append(make_table(
        ["Component", "Value", "Note"],
        wacc_rows,
        col_widths=[avail*0.38, avail*0.15, avail*0.47],
    ))
    story.append(spacer(3))
    roic_rows = [
        ["NOPAT (₹ Cr)",       "~310",   "~-180",  "~-180"],
        ["Invested Capital (₹ Cr)","~21,000","~19,000","~13,000"],
        ["ROIC (%)",           "~1.5%",  "~-0.9%", "~-1.4%"],
        ["WACC (%)",           "~10.5%", "~10.5%", "~10.5%"],
        ["**Value Spread",     "**-9.0%","**-11.4%","**-11.9%"],
    ]
    story.append(make_table(
        ["Metric", "FY23", "FY24", "FY25"],
        roic_rows,
        col_widths=[avail*0.40, avail*0.20, avail*0.20, avail*0.20],
    ))
    story.append(Paragraph("[Computed from Screener.in balance sheet and P&L]", STYLES["disclaimer"]))
    story.append(callout_box(
        "Value Creation Verdict",
        [
            "ABFRL is destroying economic value (ROIC < WACC) — the fundamental driver of "
            "the discounted valuation. The inflection arrives when operating profit net of taxes "
            "exceeds the cost of debt.",
            "At current trajectory (EBITDA +20% YoY, debt declining), ROIC should approach "
            "WACC by FY28. The investment case is to enter before the market prices this "
            "inflection — which typically happens 12–18 months in advance.",
        ],
    ))

    # ── SECTION 5D: FORENSIC ──────────────────────────────────────────────
    story.append(section_header("5D.  FORENSIC ACCOUNTING CHECK"))
    story.append(spacer(2))
    forensic_rows = [
        ["OCF — absolute",         "₹1,341 Cr", "₹1,644 Cr", "✅ Positive, growing"],
        ["Debtor Days trend",      "73 days",   "19 days",   "✅ Major improvement"],
        ["Inventory Days",         "532 days",  "282 days",  "⚠  Still elevated"],
        ["Auditor change (3 yrs)", "No",         "No",        "✅"],
        ["Promoter pledging",      "—",         "7.18% locked","⚠  Watch"],
        ["Contingent liabilities", "Not material","Not material","✅"],
    ]
    story.append(make_table(
        ["Check", "FY24", "FY25", "Flag"],
        forensic_rows,
        col_widths=[avail*0.34, avail*0.18, avail*0.18, avail*0.30],
    ))
    story.append(body(
        "<b>Forensic Score: Clean (Minor Flags)</b> — No earnings quality concerns. "
        "OCF positive and growing despite PAT losses — the opposite of the typical forensic red flag pattern."
    ))
    story.append(spacer(3))

    # ── SECTION 6A: INSTITUTIONAL FLOWS ───────────────────────────────────
    story.append(section_header("6A.  INSTITUTIONAL FLOW TRACKER"))
    story.append(spacer(2))
    story.append(subsection_header("Bulk & Block Deal History — Last 9 Months"))
    block_rows = [
        ["Jun 4, 2025", "Flipkart Investments (Walmart) — Seller", "732", "₹79.50", "Block Sell", "Overhang cleared"],
    ]
    story.append(make_table(
        ["Date", "Buyer / Seller", "Qty (Lakh sh.)", "Price (₹)", "Type", "Signal"],
        block_rows,
        col_widths=[avail*0.13, avail*0.30, avail*0.12, avail*0.11, avail*0.12, avail*0.22],
    ))
    story.append(Paragraph("[Source: BusinessToday, Jun 4, 2025]", STYLES["disclaimer"]))
    story.append(body(
        "Flipkart sold its 6% stake at ₹79.50 (7% discount to prior close), causing a 9% "
        "single-day drop. <b>The positive read: this supply overhang above ₹80 is now fully cleared.</b>"
    ))

    story.append(subsection_header("Mutual Fund Holding Trend"))
    mf_rows = [
        ["Quant Small Cap Fund",       "Higher", "2.00%", "→ Stable / mild reduce"],
        ["Bandhan Large & Mid Cap",    "Higher", "1.65%", "↓ Reducing"],
        ["Nippon India Small Cap",     "Higher", "1.07%", "↓ Reducing"],
        ["SBI Life Insurance",         "—",      "1.16%", "→ Stable"],
    ]
    story.append(make_table(
        ["Fund", "Mar 2025", "Dec 2025", "Trend"],
        mf_rows,
        col_widths=[avail*0.38, avail*0.15, avail*0.15, avail*0.32],
    ))
    story.append(Paragraph("[Source: Trendlyne, Dec 2025]", STYLES["disclaimer"]))
    story.append(body(
        "<b>Flow Signal:</b> MF exits driven by redemption pressure and rotation to profitable "
        "growth stocks. Re-entry trigger: first quarter of reported positive PAT, likely Q1 or Q2 FY27."
    ))
    story.append(spacer(3))

    # ── SECTION 6B: RELATIVE STRENGTH ─────────────────────────────────────
    story.append(section_header("6B.  RELATIVE STRENGTH & ALPHA GENERATION"))
    story.append(spacer(2))
    rs_rows = [
        ["3 Months",  "~-15%",   "~-5%",  "~-10%"],
        ["6 Months",  "-27.48%", "~-5%",  "~-22%"],
        ["12 Months", "~-44% (peak ₹107.75)", "~+5%", "~-49%"],
    ]
    story.append(make_table(
        ["Period", "ABFRL Return", "Nifty 50 (approx)", "Alpha vs Nifty"],
        rs_rows,
        col_widths=[avail*0.18, avail*0.28, avail*0.24, avail*0.30],
    ))
    story.append(Paragraph("[Source: Trendlyne performance data, Apr 2026]", STYLES["disclaimer"]))
    story.append(spacer(3))

    # ── SECTION 7: VALUATION ───────────────────────────────────────────────
    story.append(section_header("7.  VALUATION"))
    story.append(Paragraph(
        "P/E not applicable (reported losses). Primary methods: EV/EBITDA, P/B, EV/Sales.",
        STYLES["disclaimer"]
    ))
    story.append(spacer(2))

    story.append(subsection_header("7.1  Peer Comparison"))
    peer_rows = [
        ["**ABFRL",         "**60.33",  "**~7,360",   "**~9x FY26E","**~15%", "**+8–10%","★ Turnaround"],
        ["Trent Ltd",       "~5,500",  "~1,75,000",  "~50x",      "14–15%", "22–25%", "Profitable; premium"],
        ["Shoppers Stop",   "~330",    "~3,500",     "~12–15x",   "6–8%",   "5–8%",   "Profitable; stable"],
        ["V-Mart Retail",   "~1,900",  "~3,600",     "~18–20x",   "8–10%",  "10–12%", "Profitable; growing"],
        ["Avenue Supermarts","~3,650", "~2,67,000",  "~55–60x",   "10–11%", "15–18%", "Profitable; grocery"],
    ]
    story.append(make_table(
        ["Company", "CMP (₹)", "Mkt Cap (₹ Cr)", "EV/EBITDA", "EBITDA Mgn", "Rev Growth", "Status"],
        peer_rows,
        col_widths=[avail*0.19, avail*0.10, avail*0.14, avail*0.12, avail*0.12, avail*0.12, avail*0.21],
    ))
    story.append(Paragraph("[Source: Trendlyne, Screener.in peers, Apr 2026 estimates]", STYLES["disclaimer"]))
    story.append(body(
        "ABFRL at ~9x FY26E EV/EBITDA is the cheapest fashion retailer in the peer set. "
        "<b>Analyst consensus: ₹76 target, 16 analysts, 75% Buy</b> [Source: Trendlyne, Apr 2026]. "
        "Recent: Motilal Oswal Neutral ₹75, Axis Direct Hold ₹75 (Feb 2026), Sharekhan Buy ₹95 (Jun 2025)."
    ))

    story.append(subsection_header("7.2  Valuation Models & Blended Target"))
    val_rows = [
        ["EV/EBITDA (Primary)",
         "FY27E EBITDA ₹1,500 Cr (16% margin on ~₹9,375 Cr revenue); Target 12x; "
         "Target EV ₹18,000 Cr less ₹4,200 Cr net debt → Mkt Cap ₹13,800 Cr",
         "₹113"],
        ["Price-to-Book",
         "FY27E BV/share ~₹50; Target P/B 1.5x (approaching profitability)",
         "₹75"],
        ["EV/Sales",
         "FY26E Revenue ₹8,500 Cr; Target 1.7x EV/Sales; less ₹4,600 Cr net debt",
         "₹81"],
    ]
    story.append(make_table(
        ["Method", "Assumptions", "Implied Target"],
        val_rows,
        col_widths=[avail*0.20, avail*0.63, avail*0.17],
    ))
    story.append(spacer(2))

    blend_rows = [
        ["EV/EBITDA", "50%", "₹113", "₹56.5"],
        ["P/B",       "30%", "₹75",  "₹22.5"],
        ["EV/Sales",  "20%", "₹81",  "₹16.2"],
        ["**Blended 18M Target", "**100%", "", "**₹95"],
    ]
    story.append(make_table(
        ["Method", "Weight", "Target (₹)", "Contribution"],
        blend_rows,
        col_widths=[avail*0.35, avail*0.15, avail*0.20, avail*0.30],
    ))
    story.append(spacer(2))
    story.append(callout_box(
        "Valuation Risk",
        [
            "At ₹95 target, the model assumes 16% EBITDA margins by FY27 and re-rating to 12x EV/EBITDA.",
            "If Pantaloons LTL turns negative: FY27 EBITDA ~₹1,200 Cr at 13% margins → at 10x, "
            "fair value collapses to ~₹65 (only 8% above CMP).",
            "Protection comes from P/B support at ~₹48–55 (book value floor).",
        ],
        is_warning=True,
    ))

    story.append(subsection_header("7.3  EV/EBITDA Sensitivity — FY27E"))
    sens_rows = [
        ["EBITDA ₹1,200 Cr", "₹62", "₹72", "₹88",  "₹106", "₹123"],
        ["EBITDA ₹1,500 Cr (Base)", "₹80", "₹93", "**₹113","₹132", "₹153"],
        ["EBITDA ₹1,800 Cr", "₹98", "₹114","**₹138","₹163", "₹188"],
    ]
    story.append(make_table(
        ["", "9x EV/EBITDA", "10x", "12x (Base)", "14x", "16x"],
        sens_rows,
        col_widths=[avail*0.30, avail*0.14, avail*0.14, avail*0.14, avail*0.14, avail*0.14],
    ))
    story.append(Paragraph(
        "Net debt assumed ₹4,200 Cr FY27E; 122 Cr shares. Bold = base case.",
        STYLES["disclaimer"],
    ))
    story.append(body(
        "<b>Risk / reward: +57% upside (base) vs -25% downside (bear) = 2.3x asymmetry.</b> "
        "At CMP ₹60.33, market prices ABFRL at ~7x FY27E EV/EBITDA — already discounting "
        "meaningful disappointment."
    ))
    story.append(spacer(3))

    # ── SECTION 9: SWOT ────────────────────────────────────────────────────
    story.append(section_header("9.  SWOT ANALYSIS"))
    story.append(spacer(2))
    strengths = [
        "ICRA/CRISIL AA — Aditya Birla Group backstop limits existential risk",
        "Ethnic wear: 8 consecutive growth quarters; 22.7% EBITDA margin",
        "₹4,239 Cr equity raise derisked balance sheet dramatically",
        "OCF ₹1,644 Cr FY25 — cash-generative despite P&L losses",
        "TMRW +29% growth, approaching breakeven",
        "Near 52W low — distressed entry valuation",
        "412-store estate: ~₹10,000+ Cr replacement cost moat",
    ]
    weaknesses = [
        "Persistent reported net losses (5+ years)",
        "Pantaloons in competitive battle vs Zudio / Reliance",
        "Promoter stake declining: 55% → 46%",
        "DII/MF rapid exit: 17% → 7.9% in 2 years",
        "Elevated inventory days (282) vs benchmark",
        "7.18% promoter shares pledged",
        "Ind AS 116 lease costs depress reported PAT",
    ]
    opportunities = [
        "Ethnic wear ₹1,00,000 Cr market at 15–18% CAGR; <1% penetrated",
        "PAT profitability expected FY27 — institutional re-entry trigger",
        "Style Up: 250-store rollout (low capex, asset-light)",
        "TMRW D2C: ₹25,000 Cr market largely unaddressed",
        "Budget FY26 middle-class tax relief → Pantaloons pool expands",
        "Flipkart ₹80 supply overhang fully cleared (Jun 2025)",
    ]
    threats = [
        "Zudio 700+ stores competing directly with Pantaloons",
        "Reliance Retail fashion formats scaling aggressively",
        "Consumer spending slowdown impacting discretionary",
        "Interest rate environment — debt servicing elevated",
        "Potential further equity dilution if debt targets missed",
        "Working capital normalization could pressure FCF",
    ]

    def bullet_list(items, style=STYLES["body"]):
        rows = []
        for item in items:
            item = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', item)
            rows.append([Paragraph(f"• {item}", style)])
        t = Table(rows, colWidths=[(avail / 2) - 4])
        t.setStyle(TableStyle([
            ("TOPPADDING",    (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING",   (0, 0), (-1, -1), 3),
        ]))
        return t

    sw_header = Table(
        [[Paragraph("<b>✅  STRENGTHS</b>", STYLES["table_header"]),
          Paragraph("<b>⚠  WEAKNESSES</b>", STYLES["table_header"])]],
        colWidths=[avail / 2, avail / 2],
    )
    sw_header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#1A5A1A")),
        ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#5A1A1A")),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    sw_body = Table(
        [[bullet_list(strengths), bullet_list(weaknesses)]],
        colWidths=[avail / 2, avail / 2],
    )
    sw_body.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [BRAND_LIGHT]),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEAFTER",     (0, 0), (-2, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))

    ot_header = Table(
        [[Paragraph("<b>🚀  OPPORTUNITIES</b>", STYLES["table_header"]),
          Paragraph("<b>⛔  THREATS</b>", STYLES["table_header"])]],
        colWidths=[avail / 2, avail / 2],
    )
    ot_header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#0D3A5A")),
        ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#5A3A0A")),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    ot_body = Table(
        [[bullet_list(opportunities), bullet_list(threats)]],
        colWidths=[avail / 2, avail / 2],
    )
    ot_body.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white]),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEAFTER",     (0, 0), (-2, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))

    story.extend([sw_header, sw_body, spacer(2), ot_header, ot_body, spacer(3)])

    # ── SECTION 10: TECHNICAL ─────────────────────────────────────────────
    story.append(section_header("10.  TECHNICAL ANALYSIS & PRICE ACTION"))
    story.append(spacer(2))
    story.append(body(
        "ABFRL's -44% drawdown from peak ₹107.75 (approx. May–Jun 2025) to ₹60.33 (Apr 10, 2026) "
        "was driven by: Flipkart 6% block sale at ₹79.50 (June 2025, -9% single-day drop), "
        "persistent reported losses, and DII institutional selling. "
        "Currently within 13% of 52-week low ₹53.51 — approaching capitulation."
    ))

    story.append(subsection_header("Moving Average Framework"))
    ma_rows = [
        ["200-DMA",             "~₹80–85 (est.)", "Structural downtrend — stock significantly below"],
        ["50-DMA",              "~₹65–70 (est.)", "Intermediate bearish — stock below"],
        ["20-DMA",              "~₹60–62 (est.)", "Short-term stabilization at/near"],
        ["Trendlyne Momentum",  "34.9 / 100",      "Technically Bearish"],
        ["6-Month Return",      "-27.48%",          "[Source: Trendlyne, Apr 2026]"],
    ]
    story.append(make_table(
        ["Indicator", "Estimated Level", "Signal"],
        ma_rows,
        col_widths=[avail*0.25, avail*0.23, avail*0.52],
    ))

    story.append(subsection_header("Support / Resistance Matrix"))
    sr_rows = [
        ["Resistance 3",   "~₹95–100", "Post-profitability re-rating zone — blended target"],
        ["Resistance 2",   "~₹80",     "Flipkart block deal price — strong supply zone"],
        ["Resistance 1",   "~₹68–70",  "50-DMA overhead resistance"],
        ["**Accumulate Zone","**₹55–65","**Near 52W low / Book Value support"],
        ["Support 1",       "~₹55",    "Recent consolidation base"],
        ["52W Low",         "₹53.51",  "Structural floor"],
        ["Bear Case Floor", "₹45–48",  "0.9x P/B (if losses deepen)"],
    ]
    story.append(make_table(
        ["Level", "Price (₹)", "Commentary"],
        sr_rows,
        col_widths=[avail*0.22, avail*0.18, avail*0.60],
    ))
    story.append(spacer(3))

    # ── SECTION 11: RISK MATRIX ────────────────────────────────────────────
    story.append(section_header("11.  RISK MATRIX — RANKED BY SEVERITY"))
    story.append(spacer(2))
    risk_rows = [
        ["1", "Pantaloons LTL turns negative",   "Competitive",   "CRITICAL",  "Zudio 700+ stores",                 "Quarterly LTL in results"],
        ["2", "Losses persist beyond FY27",       "Financial",     "HIGH",      "5+ years consecutive losses",       "Normalized PAT quarterly"],
        ["3", "Further promoter stake dilution",  "Governance",    "HIGH",      "Stake declined 55% → 46%",          "BSE shareholding quarterly"],
        ["4", "DII/MF continued exit",            "Institutional", "HIGH",      "17% → 7.9% in 2 years",            "Quarterly shareholding"],
        ["5", "Debt not declining as expected",   "Balance Sheet", "MEDIUM",    "Sep 2025 uptick to ₹5,665 Cr",     "Semi-annual borrowings"],
        ["6", "Reliance/Trent entering ethnic",   "Competitive",   "MEDIUM",    "Not yet; risk building",            "Ethnic LTL quarterly"],
        ["7", "Consumer spending slowdown",       "Macro",         "MEDIUM",    "Discretionary under pressure FY26", "Quarterly same-store sales"],
        ["8", "TMRW fails to scale",              "Execution",     "MEDIUM",    "Still unproven at scale",           "TMRW EBITDA quarterly"],
    ]
    story.append(make_table(
        ["#", "Risk", "Category", "Severity", "Evidence", "Monitor"],
        risk_rows,
        col_widths=[avail*0.04, avail*0.22, avail*0.12, avail*0.10, avail*0.27, avail*0.25],
    ))
    story.append(spacer(3))

    # ── SECTION 11A: EVENT CALENDAR ───────────────────────────────────────
    story.append(section_header("11A.  EVENT CALENDAR & CATALYST TRACKER"))
    story.append(spacer(2))
    ev_rows = [
        ["May 2026 ★",     "Q4 FY26 Results",                "Rev ~₹2,000 Cr; EOSS benefit",
         "Normalized PAT positive → institution re-entry", "PAT still negative → de-rating", "High"],
        ["Aug 2026",       "Q1 FY27 Results",                "First full demerger-comparable year",
         "Revenue +15%, near profitable",                   "Revenue <10%, losses persist",      "Medium"],
        ["Jun–Jul 2026",   "FY26 Annual Report",             "Debt trajectory disclosure",
         "Debt <₹5,000 Cr → FCF inflection",               "New equity raise → dilution",        "Medium"],
        ["FY26–27 ongoing","Style Up expansion — 250 stores","50+ new stores confirmed",
         "New format traction validates",                   "Slow rollout; margin pressure",      "Medium"],
        ["Q4 FY26",        "Ethnic peak season",             "25%+ growth, strongest quarter",
         "Confirms structural momentum",                    "Growth <15% = concern",              "High"],
    ]
    story.append(make_table(
        ["Est. Date", "Event", "Expected Outcome", "Bull Impact", "Bear Impact", "Prob."],
        ev_rows,
        col_widths=[avail*0.12, avail*0.18, avail*0.20, avail*0.19, avail*0.19, avail*0.08],
    ))
    story.append(body(
        "<b>★ Highest-Conviction Catalyst:</b> Q4 FY26 results (May 2026) — benefits from "
        "(a) deferred Pantaloons EOSS, (b) peak ethnic season (Gudi Padwa, summer weddings), "
        "(c) lowest interest expense quarter in cycle. Normalized PAT ₹150+ Cr will trigger "
        "institutional re-entry."
    ))
    story.append(spacer(3))

    # ── SECTION 12: INVESTMENT VERDICT ────────────────────────────────────
    story.append(PageBreak())
    story.append(section_header("12.  INVESTMENT VERDICT & ACTIONABLE RECOMMENDATIONS",
                                color=colors.HexColor("#0D3A0D")))
    story.append(spacer(2))

    story.append(subsection_header("For Existing Shareholders"))
    existing = [
        "<b>Hold through Q4 FY26 results</b> (May 2026) — strong seasonal tailwinds and deferred EOSS. Do not exit ahead of this potential catalyst.",
        "<b>Add at ₹55–58</b> if Q4 FY26 / Q1 FY27 confirm positive normalized PAT.",
        "<b>Stop-loss at ₹48:</b> If ABFRL breaks below ₹53.51 (52W low) on volume and sustains below ₹50, exit — signals Pantaloons LTL negative, profitability delayed beyond FY28.",
        "<b>Take 30% profits at ₹80</b> (Flipkart supply zone) on first recovery; let remaining position run to ₹95+.",
        "<b>#1 metric to watch:</b> Pantaloons LTL — sustained negative LTL invalidates thesis regardless of ethnic strength.",
    ]
    for item in existing:
        story.append(Paragraph(f"• {item}", STYLES["bullet"]))

    story.append(spacer(2))
    story.append(subsection_header("For New Investors"))
    new_inv = [
        "<b>Tranche strategy:</b> 50% at ₹55–60 (current zone); 30% at ₹48–52 (if 52W low breaks on market volatility); 20% at ₹63–68 after Q4 FY26 PAT confirmation.",
        "<b>Hard stop-loss: ₹45</b> — below this, P/B < 0.9x implies either book value eroding faster than modeled or distressed equity raise pending.",
        "<b>Minimum horizon: 18 months.</b> Do not invest capital needed sooner.",
        "<b>Position sizing: 3–5% of equity portfolio.</b> This is a recovery bet, not a core holding.",
    ]
    for item in new_inv:
        story.append(Paragraph(f"• {item}", STYLES["bullet"]))

    story.append(spacer(3))
    story.append(subsection_header("Investment Thesis Summary"))
    thesis_rows = [
        ["The Core Opportunity",
         "ABFRL at ₹60 is priced like a distressed asset but operates like a structurally sound, "
         "cash-generating fashion platform. P/B 1.18x provides a valuation floor. AA credit rating "
         "underscores the Aditya Birla Group backstop. OCF ₹1,644 Cr (FY25) proves cash generation."],
        ["The Growth Engine",
         "Ethnic wear — 20% growth, 22.7% EBITDA margins, 8 consecutive growth quarters — deserves "
         "a premium multiple. Currently undervalued, overshadowed by Pantaloons challenges. "
         "TMRW's 900 bps margin improvement and 29% growth shows an accelerating D2C platform."],
        ["Pantaloons Risk",
         "Zudio 700+ stores: genuine competitive threat, but Pantaloons' 412-store estate in "
         "premium malls took 15 years to build. New CEO (April 2026) + Style Up rollout = commitment "
         "to format reinvention. Adjusted LTL +3% in Q3 FY26 despite Zudio expansion."],
        ["Profitability Inflection",
         "Interest expense declining 44% to ₹497 Cr FY26E + EBITDA growing 20%+ YoY = mathematical "
         "path to reported PAT positive by Q1–Q2 FY27. Re-entry of domestic funds will drive "
         "re-rating from ~9x to ~12–14x EV/EBITDA."],
    ]
    story.append(make_table(
        ["Pillar", "Analysis"],
        thesis_rows,
        col_widths=[avail*0.22, avail*0.78],
    ))

    story.append(spacer(3))
    story.append(callout_box(
        "Practitioner's Edge",
        [
            "The key channel check is Pantaloons footfall in Q4 FY26 (Jan–Mar 2026). ABFRL "
            "deliberately deferred its EOSS from December to January — a margin management decision.",
            "Track mall management feedback on Pantaloons footfall vs Q4 FY25 — any outperformance "
            "year-on-year would be an early accumulation signal ahead of the May 2026 results "
            "announcement.",
        ],
    ))

    story.append(spacer(3))
    story.append(subsection_header("12.1  Scenario Analysis"))
    scenario_rows = [
        ["Bull Case",  "₹120–130", "25%",
         "Ethnic +25% through FY27; Pantaloons LTL +5%; TMRW breakeven; re-rate to 14x EV/EBITDA"],
        ["Base Case",  "₹85–100",  "50%",
         "Ethnic +18–20%; Pantaloons LTL +2–3%; losses end FY27; re-rate to 12x EV/EBITDA"],
        ["Bear Case",  "₹40–50",   "25%",
         "Pantaloons LTL negative; losses persist through FY27; P/B compresses to 0.9x"],
    ]
    scenario_tbl = make_table(
        ["Scenario", "Target (18M)", "Probability", "Key Assumptions"],
        scenario_rows,
        col_widths=[avail*0.14, avail*0.16, avail*0.14, avail*0.56],
    )
    story.append(scenario_tbl)
    story.append(spacer(5))

    # ── SECTION 13: DISCLAIMER ─────────────────────────────────────────────
    story.append(rule(color=BRAND_DARK))
    story.append(subsection_header("13.  DISCLAIMER & DISCLOSURE"))
    disclaimer_text = (
        "This report has been prepared for informational and educational purposes only, "
        "synthesising publicly available data from Screener.in (fetched April 10, 2026), "
        "BSE corporate filings, ABFRL Investor Relations, Trendlyne, Business Standard, "
        "BusinessToday, and other cited public market data sources. It does not constitute "
        "investment advice, a solicitation to buy or sell securities, or a SEBI-registered "
        "research report. Financial data is sourced from publicly available filings and may "
        "vary from independently audited statements. All financial projections, scenario analyses, "
        "and price targets are speculative estimates based on available data and reasonable "
        "assumptions — they are not guarantees of future performance. ABFRL carries significant "
        "operational and financial risks including persistent net losses, competitive pressures "
        "in value fashion, and ongoing debt servicing obligations. Investing in listed securities "
        "carries significant risk of loss of capital. Past performance is not indicative of future "
        "results. Readers are strongly advised to conduct their own independent due diligence and "
        "consult a SEBI-registered investment advisor before making any investment decisions."
    )
    story.append(Paragraph(disclaimer_text, STYLES["disclaimer"]))
    story.append(spacer(3))

    # ── DATA SOURCES ───────────────────────────────────────────────────────
    story.append(subsection_header("Data Sources"))
    src_rows = [
        ["Screener.in", "Annual P&L, balance sheet, cash flows, ratios, shareholding", "Apr 10, 2026"],
        ["Trendlyne",   "Analyst targets, momentum score, shareholding, analyst reports","Apr 10, 2026"],
        ["ABFRL Q3 FY26 Earnings (abfrl.com/investors)", "Q3 FY26 results, segment performance","Feb 2026"],
        ["Business Standard", "Q3 FY26, Q4 FY25 results, demerger news",       "Feb–May 2025"],
        ["BusinessToday",     "Flipkart block deal details",                    "Jun 2025"],
        ["ICRA",              "Credit rating AA/Stable rationale, equity raise impact","Apr 2025"],
        ["Google Finance (via search)", "CMP ₹60.33, 52W High ₹107.75, 52W Low ₹53.51","Apr 10, 2026"],
        ["Whalesbook / InvestyWise", "Q3 FY26 segment detail, ethnic +20%, TMRW +29%","Feb 2026"],
    ]
    story.append(make_table(
        ["Source", "Data Used", "Fetched"],
        src_rows,
        col_widths=[avail*0.30, avail*0.52, avail*0.18],
    ))

    story.append(spacer(3))
    story.append(Paragraph(
        "Report Date: April 12, 2026  ·  Primary Data Source: Screener.in (Apr 10, 2026)  ·  "
        "BSE Filings through Q3 FY26 (Dec 2025)  ·  © Portfolio Research Desk",
        STYLES["footer"],
    ))

    # ── BUILD ──────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=ReportCanvas.on_page, onLaterPages=ReportCanvas.on_page)
    print(f"PDF saved to: {out_path}")
    return str(out_path)


if __name__ == "__main__":
    build()
