"""Shared visual language for every output format."""
from __future__ import annotations

INK = "0F172A"        # near-black headline
MUTED = "64748B"      # secondary text
ACCENT = "1D4ED8"     # brand blue
ACCENT_SOFT = "DBEAFE"
POSITIVE = "047857"
NEGATIVE = "B91C1C"
RULE = "E2E8F0"
BAND = "F8FAFC"
BASELINE_BG = "FEF3C7"

CURRENCY = "₹"


def money(value: float | None, decimals: int = 0) -> str:
    if value is None:
        return "—"
    return f"{CURRENCY}{value:,.{decimals}f}"


def pct(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.{decimals}f}%"


def delta(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "—"
    return f"{'+' if value >= 0 else ''}{value * 100:.{decimals}f}%"


def multiple(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}×"


def number(value: float | None, decimals: int = 0) -> str:
    if value is None:
        return "—"
    return f"{value:,.{decimals}f}"


def p_value(value: float | None) -> str:
    if value is None:
        return "—"
    if value < 0.0001:
        return "p = 0.0000"
    return f"p = {value:.4f}"


def subtitle_line(result: dict) -> str:
    meta = result["meta"]
    audit = result["audit"]
    params = meta["params"]
    parts = [
        f"{_pretty(meta['date_from'])} – {_pretty(meta['date_to'])}",
    ]
    if meta.get("language"):
        parts.append(f"{meta['language']} workshop")
    parts.append(f"base = {result['headline']['registrants']:,} registrants")
    parts.append(f"connected = bot talk > {params.get('connect_threshold_s', 15)}s")
    parts.append("baseline = not connected" if meta["baseline_mode"] == "not_connected"
                 else f"baseline = {meta['baseline_mode'].replace('_', ' ')}")
    if audit.get("team_registration_rows"):
        parts.append("team numbers deleted")
    return " · ".join(parts)


def _pretty(iso: str) -> str:
    from datetime import date

    d = date.fromisoformat(iso)
    return d.strftime("%d %b %Y").lstrip("0")


def pretty_date(iso: str) -> str:
    return _pretty(iso)


def method_note(result: dict) -> str:
    head = result["headline"]
    meta = result["meta"]
    params = meta["params"]
    baseline_word = "not-connected" if meta["baseline_mode"] != "never_dialled" else "never-dialled"
    mode = "weighted, like-for-like" if meta["uplift_mode"] == "weighted" else "unweighted"
    return (
        f"Method: 'with AI' = all {head['buyers']:,} buyers among the window's registrants × "
        f"{money(head['sale_value'])}. 'without AI' = that minus the extra AI created "
        f"(connected leads {head['connected_people']:,} × the "
        f"{head['weighted_gap_points'] * 100:+.2f} pt buy-lift = {head['extra_sales']:.1f} sales, {mode}). "
        f"ROI = AI added ÷ bot talk-cost ({money(head['talk_cost'])}). "
        f"Base = {head['registrants']:,} registrants; connected = a bot conversation longer than "
        f"{params.get('connect_threshold_s', 15)}s; baseline = the {head['baseline_people']:,} "
        f"registrants the bots never held a conversation with ({baseline_word}). "
        f"Full detail, per-bot and per-day, on the detail tab."
    )


def narrative(result: dict) -> str:
    head = result["headline"]
    groups = result["groups"]
    sig = result["significance"]
    conn = groups["connected"]
    base = groups["baseline"]
    lift = None
    if base["buy_rate"]:
        lift = (conn["buy_rate"] - base["buy_rate"]) / base["buy_rate"]
    both = groups["both"]
    text = (
        f"Connected leads buy at {pct(conn['buy_rate'], 2)} vs {pct(base['buy_rate'], 2)} for leads the bots "
        f"never got talking — a {delta(lift, 0)} relative lift ({p_value(sig['buying']['p_value'])}), and they "
        f"show up {pct(conn['show_rate'])} vs {pct(base['show_rate'])} ({p_value(sig['show_up']['p_value'])}). "
        f"Being reached by BOTH bots is the strongest position of all ({pct(both['buy_rate'], 2)} buy rate) — "
        f"the two calls compound. Bot rows are INCLUSIVE and overlap (a lead reached by BOTH also appears in "
        f"Signup and in Day-of), so they do not add up to the total. Buyers and buy-rates come straight from "
        f"the sales data. '—' in a Δ column means that group had zero, i.e. no signal, not '100% worse'."
    )
    if head.get("breakeven_sales") is not None:
        text += (
            f" Break-even is {head['breakeven_sales']:.1f} sales and the AI is credited with "
            f"{head['extra_sales']:.1f}."
        )
    return text
