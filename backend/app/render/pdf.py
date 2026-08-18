"""Print-ready PDF that mirrors the reference report layout."""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..config import APP_NAME
from . import style as S

PAGE = landscape(A4)
INK = colors.HexColor("#" + S.INK)
MUTED = colors.HexColor("#" + S.MUTED)
ACCENT = colors.HexColor("#" + S.ACCENT)
ACCENT_SOFT = colors.HexColor("#" + S.ACCENT_SOFT)
RULE = colors.HexColor("#" + S.RULE)
BAND = colors.HexColor("#" + S.BAND)
BASELINE_BG = colors.HexColor("#" + S.BASELINE_BG)
POSITIVE = colors.HexColor("#" + S.POSITIVE)
NEGATIVE = colors.HexColor("#" + S.NEGATIVE)

_FONT = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"


def _register_rupee_font() -> None:
    """Helvetica has no ₹ glyph; fall back to a system font that does."""
    global _FONT, _FONT_BOLD
    candidates = [
        (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf", "SegoeUI"),
        (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf", "ArialUni"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVu"),
    ]
    for regular, bold, name in candidates:
        if Path(regular).exists() and Path(bold).exists():
            try:
                pdfmetrics.registerFont(TTFont(name, regular))
                pdfmetrics.registerFont(TTFont(name + "-Bold", bold))
                _FONT, _FONT_BOLD = name, name + "-Bold"
                return
            except Exception:
                continue


_register_rupee_font()


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontName=_FONT_BOLD, fontSize=17,
                                textColor=INK, alignment=TA_LEFT, spaceAfter=2, leading=21),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"], fontName=_FONT, fontSize=8.5,
                                   textColor=MUTED, spaceAfter=10, leading=12),
        "section": ParagraphStyle("section", parent=base["Normal"], fontName=_FONT_BOLD, fontSize=10,
                                  textColor=colors.white, backColor=INK, borderPadding=(5, 5, 5, 5),
                                  spaceBefore=10, spaceAfter=6, leading=13),
        "day": ParagraphStyle("day", parent=base["Normal"], fontName=_FONT_BOLD, fontSize=9.5,
                              textColor=ACCENT, spaceBefore=8, spaceAfter=3),
        "note": ParagraphStyle("note", parent=base["Normal"], fontName=_FONT, fontSize=7.6,
                               textColor=MUTED, leading=10.5, spaceBefore=5, spaceAfter=5),
        "cell": ParagraphStyle("cell", parent=base["Normal"], fontName=_FONT, fontSize=7.6, leading=10),
        "cellb": ParagraphStyle("cellb", parent=base["Normal"], fontName=_FONT_BOLD, fontSize=7.6, leading=10),
    }


def _kpi_row(result: dict, st) -> Table:
    head = result["headline"]
    cards = [
        ("Revenue with AI", S.money(head["revenue_with_ai"])),
        ("Revenue without AI", S.money(head["revenue_without_ai"])),
        ("AI calling added", S.money(head["revenue_added"])),
        ("Relative uplift", S.pct(head["relative_uplift"])),
        ("Talk cost", S.money(head["talk_cost"])),
        ("ROI", S.multiple(head["roi"])),
    ]
    data = [
        [Paragraph(label.upper(), ParagraphStyle("k", fontName=_FONT, fontSize=6.6, textColor=MUTED))
         for label, _ in cards],
        [Paragraph(value, ParagraphStyle("v", fontName=_FONT_BOLD, fontSize=13, textColor=INK))
         for _, value in cards],
    ]
    table = Table(data, colWidths=[(PAGE[0] - 34 * mm) / len(cards)] * len(cards))
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BAND),
        ("BOX", (0, 0), (-1, -1), 0.5, RULE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.white),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def _group_table(rows: list[dict], st, width: float) -> Table:
    header = ["Group", "Registrants", "Showed", "Show-up %", "Show-up Δ", "Buyers", "Buyer %", "Buyer Δ"]
    data = [[Paragraph(h, st["cellb"]) for h in header]]
    styles = [
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT_SOFT),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, RULE),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]
    for index, item in enumerate(rows, start=1):
        is_total = item.get("key") == "total" or item.get("label") == "Total"
        is_baseline = item.get("key") == "baseline"
        cell_style = st["cellb"] if is_total else st["cell"]
        data.append([
            Paragraph(str(item["label"]), cell_style),
            Paragraph(f"{item['registrants']:,}", cell_style),
            Paragraph(f"{item['showed']:,}", cell_style),
            Paragraph(S.pct(item["show_rate"]), cell_style),
            Paragraph(_delta_markup(item["show_delta"]), cell_style),
            Paragraph(f"{item['buyers']:,}", cell_style),
            Paragraph(S.pct(item["buy_rate"], 2), cell_style),
            Paragraph(_delta_markup(item["buy_delta"]), cell_style),
        ])
        if is_total:
            styles.append(("BACKGROUND", (0, index), (-1, index), BAND))
        if is_baseline:
            styles.append(("BACKGROUND", (0, index), (-1, index), BASELINE_BG))
        styles.append(("LINEBELOW", (0, index), (-1, index), 0.25, RULE))

    col = width / 100
    table = Table(data, colWidths=[col * 30, col * 11, col * 9, col * 11, col * 11, col * 9, col * 10, col * 9])
    table.setStyle(TableStyle(styles))
    return table


def _delta_markup(value: float | None) -> str:
    if value is None:
        return "—"
    color = "#" + (S.POSITIVE if value >= 0 else S.NEGATIVE)
    return f'<font color="{color}">{S.delta(value)}</font>'


def build_pdf(result: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    st = _styles()
    head = result["headline"]
    meta = result["meta"]
    width = PAGE[0] - 34 * mm

    doc = SimpleDocTemplate(
        str(path), pagesize=PAGE,
        leftMargin=17 * mm, rightMargin=17 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
        # The client this report is for, not whichever client the app was first
        # written for. A DVA report used to be authored "CoachEasily".
        title=meta.get("title") or "AI calling report",
        author=meta.get("client") or APP_NAME,
    )
    story = [
        Paragraph(
            f"{(meta.get('client') or 'AI CALLING').upper()} — WHAT AI CALLING ADDED"
            f"&nbsp;&nbsp;({meta['title']})", st["title"]),
        Paragraph(S.subtitle_line(result), st["subtitle"]),
        _kpi_row(result, st),
        Spacer(1, 8),
        Paragraph("REVENUE WITH AI CALLING vs WITHOUT", st["section"]),
    ]

    revenue_header = ["Program", "Revenue without AI", "Revenue with AI", "AI added", "Relative uplift", "ROI"]
    revenue_rows = [[Paragraph(h, st["cellb"]) for h in revenue_header]]
    for label, bold in ((meta["title"], False), ("Total", True)):
        cell_style = st["cellb"] if bold else st["cell"]
        revenue_rows.append([
            Paragraph(label, cell_style),
            Paragraph(S.money(head["revenue_without_ai"]), cell_style),
            Paragraph(S.money(head["revenue_with_ai"]), cell_style),
            Paragraph(S.money(head["revenue_added"]), cell_style),
            Paragraph(S.pct(head["relative_uplift"]), cell_style),
            Paragraph(f'<font color="#{S.ACCENT}">{S.multiple(head["roi"])}</font>', st["cellb"]),
        ])
    revenue_table = Table(revenue_rows, colWidths=[width * 0.3] + [width * 0.14] * 5)
    revenue_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT_SOFT),
        ("BACKGROUND", (0, 2), (-1, 2), BAND),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [revenue_table, Paragraph(S.method_note(result), st["note"])]

    story += [
        Paragraph("SHOW-UP &amp; BUYERS — by bot reached (whole window · Δ = vs baseline)", st["section"]),
        _group_table([
            {**result["groups"]["total"], "key": "total"},
            {**result["groups"]["signup"], "key": "signup"},
            {**result["groups"]["day_of"], "key": "day_of"},
            {**result["groups"]["both"], "key": "both"},
            {**result["groups"]["baseline"], "key": "baseline"},
        ], st, width),
        Paragraph(S.narrative(result), st["note"]),
    ]

    if result["bands"]:
        band_header = ["Lead age band", "Connected", "Connected buy %", "Baseline", "Baseline buy %", "Extra sales"]
        band_rows = [[Paragraph(h, st["cellb"]) for h in band_header]]
        for band in result["bands"]:
            band_rows.append([
                Paragraph(band["band"], st["cell"]),
                Paragraph(f"{band['connected']:,}", st["cell"]),
                Paragraph(S.pct(band["connected_buy_rate"], 2), st["cell"]),
                Paragraph(f"{band['baseline']:,}", st["cell"]),
                Paragraph(S.pct(band["baseline_buy_rate"], 2), st["cell"]),
                Paragraph(f"{band['extra_sales']:.1f}", st["cellb"]),
            ])
        band_table = Table(band_rows, colWidths=[width * 0.22] + [width * 0.156] * 5)
        band_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT_SOFT),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ]))
        story += [
            Paragraph("EXTRA SALES — WEIGHTED BY LEAD AGE (like-for-like)", st["section"]),
            band_table,
        ]

    story.append(PageBreak())
    story.append(Paragraph("PER-CALL-DAY DETAIL  (each webinar day · Δ = vs that day's baseline)", st["section"]))
    for day in result["daily"]:
        story.append(KeepTogether([
            Paragraph(S.pretty_date(day["date"]), st["day"]),
            _group_table(day["rows"], st, width),
        ]))

    story.append(PageBreak())
    story.append(Paragraph("METHOD, SOURCES &amp; DATA AUDIT", st["section"]))
    for label, text in _audit_entries(result):
        story.append(Paragraph(f'<b>{label}</b> — {text}', st["note"]))

    doc.build(story)
    return path


def _audit_entries(result: dict) -> list[tuple[str, str]]:
    head = result["headline"]
    meta = result["meta"]
    audit = result["audit"]
    calls = result["calls"]
    sig = result["significance"]
    entries = [
        ("Window", f"{S.pretty_date(meta['date_from'])} – {S.pretty_date(meta['date_to'])} "
                   f"({meta['window_days']} days) by registration date."),
        ("Registrants", f"{audit['registration_rows']:,} rows → {audit['team_registration_rows']:,} team/test and "
                        f"{audit['repeat_registration_rows']:,} repeat rows removed → "
                        f"{audit['unique_registrants']:,} unique people (matched by phone OR email OR name)."),
        ("Connected", f"Talk longer than {audit['connected_threshold_s']}s. {calls['calls_placed']:,} calls placed, "
                      f"{calls['calls_connected']:,} connected, reaching {head['connected_people']:,} distinct "
                      f"registrants; {calls['calls_never_connected']:,} never connected."),
        ("Buyers", f"{audit['sale_rows_in_window']:,} sale rows in window; "
                   f"{audit['sale_rows_outside_cohort']:,} outside the cohort and "
                   f"{audit['sale_rows_before_registration']:,} pre-registration rows dropped. Every counted person "
                   f"is one full sale of {S.money(head['sale_value'])}."),
        ("Cost", f"{calls['calls_with_audio']:,} calls with talk time · {calls['talk_minutes_exact']:,} real minutes "
                 f"→ {calls['billed_minutes']:,} billed minutes (rounded up per call) × "
                 f"{S.money(calls['cost_per_minute'], 2)} = {S.money(calls['talk_cost'])}."),
        ("Extra sales", f"Lead-age-banded weighted gap of {head['weighted_gap_points'] * 100:.2f} points "
                        f"(unweighted {head['simple_gap_points'] * 100:.2f}) → {head['extra_sales']:.1f} sales × "
                        f"{S.money(head['sale_value'])} = {S.money(head['revenue_added'])} ÷ "
                        f"{S.money(head['talk_cost'])} = {S.multiple(head['roi'])}."),
        ("Significance", f"Show-up {S.p_value(sig['show_up']['p_value'])} · Buying "
                         f"{S.p_value(sig['buying']['p_value'])} (two-proportion z-test vs baseline)."),
        ("The big caveat", "Observational, not an experiment: nobody was randomly left uncalled, so connected people "
                           "are self-selected. Lead-age normalisation removes the one measurable bias; a hold-out "
                           "test would settle the rest."),
    ]
    return entries
