"""The section library.

Every section in the DVA and CBH workbooks is one entry here. A section declares
what data it needs; if the client has not supplied that data the section reports
itself unavailable with a reason rather than rendering zeros as if they were
findings.

Adding a client format means listing section keys in a template — not writing
new computation or new renderer code.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..metrics.cohort import Cohort
from ..metrics.stats import (
    proportion_diff_ci,
    relative_delta,
    safe_rate,
    two_proportion_z_test,
)
from .blocks import Block, Col, Item, Section, Stage, funnel, kpi, matrix, table, text

# What a section can require. "leads" is the supplied lead list, which is not one
# of the four inputs — sections needing it degrade instead of failing.
REQUIRES = ("registrations", "ai_calls", "sales", "attendance", "leads", "sale_grading")

_REGISTRY: dict[str, "SectionDef"] = {}


@dataclass
class SectionDef:
    key: str
    title: str
    requires: tuple[str, ...]
    build: Callable[[Cohort, dict], list[Block]]
    description: str = ""


def section(key: str, title: str, requires: tuple[str, ...], description: str = ""):
    def wrap(fn):
        _REGISTRY[key] = SectionDef(key=key, title=title, requires=requires,
                                    build=fn, description=description)
        return fn
    return wrap


def registry() -> dict[str, SectionDef]:
    return dict(_REGISTRY)


def availability(cohort: Cohort) -> dict[str, str | None]:
    """None means available; a string explains what is missing."""
    return {
        "registrations": None if cohort.registrants else "no registrations in this window",
        "ai_calls": None if cohort.calls_placed else "no AI calls in this window",
        "sales": None if cohort.sale_rows else "no sales in this window",
        "attendance": None if cohort.attended else "no attendance (Zoom) data in this window",
        "leads": "no supplied lead list has been uploaded for this client",
        "sale_grading": "no transcript grading has been recorded for these sales",
    }


def build_section(key: str, cohort: Cohort, config: dict | None = None) -> Section:
    definition = _REGISTRY.get(key)
    if definition is None:
        return Section(key=key, title=key, available=False,
                       unavailable_reason=f"unknown section '{key}'")

    have = availability(cohort)
    missing = [have[r] for r in definition.requires if have.get(r)]
    config = config or {}
    title = config.get("title") or definition.title
    if missing:
        return Section(key=key, title=title, available=False,
                       unavailable_reason="; ".join(missing))
    return Section(key=key, title=title, blocks=definition.build(cohort, config))


# ------------------------------------------------------------------ #
# helpers
# ------------------------------------------------------------------ #

def _uplift_rows(treated, control, label_treated: str, label_control: str,
                 metric: str) -> tuple[list[dict], dict]:
    """Two comparable rows plus the delta/lift/p-value row underneath them.

    `metric` picks which numerator to test: registered, showed or buyers. Both
    the percentage-point difference and the relative lift are reported, because
    the client workbooks always show both and they answer different questions.
    """
    num_t = getattr(treated, metric)
    num_c = getattr(control, metric)
    rate_t = safe_rate(num_t, treated.people)
    rate_c = safe_rate(num_c, control.people)
    test = two_proportion_z_test(num_t, treated.people, num_c, control.people)

    rows = [
        {"group": label_treated, "people": treated.people, "count": num_t, "rate": rate_t},
        {"group": label_control, "people": control.people, "count": num_c, "rate": rate_c},
    ]
    summary = {
        "delta_pp": (rate_t - rate_c) if (rate_t is not None and rate_c is not None) else None,
        "relative": relative_delta(rate_t, rate_c),
        "p_value": test.get("p_value") if test else None,
        "significant": bool(test and test.get("significant")),
        # The headline number: how many extra events the calls produced.
        "extra": ((rate_t - rate_c) * treated.people
                  if (rate_t is not None and rate_c is not None) else None),
    }
    return rows, summary


UPLIFT_COLS = [
    Col("group", "Group"),
    Col("people", "People", fmt="int", align="right"),
    Col("count", "Count", fmt="int", align="right"),
    Col("rate", "Rate", fmt="pct", align="right"),
]


def _uplift_block(title: str, subtitle: str, rows: list[dict], summary: dict,
                  count_label: str, extra_label: str) -> Block:
    cols = list(UPLIFT_COLS)
    cols[2] = Col("count", count_label, fmt="int", align="right")
    body = list(rows)
    body.append({
        "group": "Difference",
        "people": None,
        "count": None,
        "rate": summary["delta_pp"],
        "_fmt_rate": "pp",
    })
    body.append({
        "group": "Relative lift",
        "people": None,
        "count": None,
        "rate": summary["relative"],
        "_fmt_rate": "delta",
    })
    body.append({
        "group": extra_label,
        "people": None,
        "count": summary["extra"],
        "rate": None,
        "_fmt_count": "number",
    })
    notes = []
    if summary["p_value"] is not None:
        verdict = "significant" if summary["significant"] else "inconclusive"
        notes.append(f"Two-proportion z-test vs the baseline: p = {summary['p_value']:.4f} ({verdict}).")
    notes.append("Observational comparison — the treated group is self-selected, "
                 "so this measures association, not a randomised effect.")
    return table(title, cols, body, subtitle=subtitle, notes=notes,
                 emphasis={"Difference": "total", "Relative lift": "total", extra_label: "verdict",
                           rows[1]["group"]: "baseline"})


# ------------------------------------------------------------------ #
# 1 · Overall
# ------------------------------------------------------------------ #

@section("headline", "Headline", ("ai_calls",),
         "Top-line numbers: calls, contact levels, attendance and sales.")
def _headline(c: Cohort, cfg: dict) -> list[Block]:
    reached_stat = c.stat_for("Reached", c.reached)
    not_reached = c.stat_for("Not reached", c.dialled - c.reached)
    _, summary = _uplift_rows(reached_stat, not_reached, "Reached", "Not reached", "showed")

    items = [
        Item("AI calls placed", c.calls_placed, fmt="int"),
        Item("…connected (answered)", c.calls_connected, fmt="int",
             note=f"{safe_rate(c.calls_connected, c.calls_placed):.1%}" if c.calls_placed else None),
        Item(f"…reached (answered & >{c.reach_threshold_s}s)", c.calls_reached, fmt="int",
             note=f"{safe_rate(c.calls_reached, c.calls_placed):.1%}" if c.calls_placed else None),
        Item("Unique people dialled", len(c.dialled), fmt="int"),
        Item("Registrants in window", len(c.registrants), fmt="int"),
        Item("Attendees (any day)", len(c.attended), fmt="int"),
        Item("Buyers", len(c.buyers), fmt="int"),
        Item("Revenue recorded", c.revenue_total, fmt="money"),
    ]
    billed, cost = c.billed_for_roles()
    items.append(Item("AI calling cost", cost, fmt="money",
                      note=f"{billed:,} billed minutes @ {c.rate_per_min:.2f}/min, bots in scope"))
    if summary["relative"] is not None:
        items.append(Item("Show-up lift, reached vs not reached", summary["relative"],
                          fmt="delta", tone="pos" if summary["relative"] > 0 else "warn"))
    if summary["extra"] is not None:
        items.append(Item("Extra show-ups the calls created", summary["extra"], fmt="number",
                          tone="accent"))
    return [kpi("Headline", items, subtitle=cfg.get("subtitle"))]


@section("call_funnel", "Call funnel", ("ai_calls",),
         "Dials and people, kept as two separate ladders.")
def _call_funnel(c: Cohort, cfg: dict) -> list[Block]:
    calls = funnel(
        "Calls — one row per dial",
        [
            Stage("Total calls placed", c.calls_placed, rate=1.0 if c.calls_placed else None),
            Stage("Connected (answered)", c.calls_connected,
                  rate=safe_rate(c.calls_connected, c.calls_placed)),
            Stage("Not connected", c.calls_placed - c.calls_connected,
                  rate=safe_rate(c.calls_placed - c.calls_connected, c.calls_placed), dim=True),
            Stage(f"Reached (>{c.reach_threshold_s}s)", c.calls_reached,
                  rate=safe_rate(c.calls_reached, c.calls_placed)),
        ],
        subtitle="Attempts, not people.",
    )
    people = funnel(
        "People — unique, one row per person",
        [
            Stage("Dialled", len(c.dialled), rate=1.0 if c.dialled else None),
            Stage("Connected (answered at least once)", len(c.connected),
                  rate=safe_rate(len(c.connected), len(c.dialled))),
            Stage("Never connected", len(c.dialled - c.connected),
                  rate=safe_rate(len(c.dialled - c.connected), len(c.dialled)), dim=True),
            Stage(f"Reached (answered & >{c.reach_threshold_s}s)", len(c.reached),
                  rate=safe_rate(len(c.reached), len(c.dialled))),
            Stage("Not reached", len(c.dialled - c.reached),
                  rate=safe_rate(len(c.dialled - c.reached), len(c.dialled)), dim=True),
        ],
        subtitle="Deduplicated to people.",
        notes=["People and dials must not be read across each other — "
               "one person can account for many attempts."],
    )
    return [people, calls]


# ------------------------------------------------------------------ #
# 2 · Sign-up
# ------------------------------------------------------------------ #

@section("signup_uplift", "Sign-up uplift", ("registrations", "ai_calls", "leads"),
         "Registration rate, called vs not called on the supplied lead list.")
def _signup_uplift(c: Cohort, cfg: dict) -> list[Block]:  # pragma: no cover - needs leads
    return []


@section("signup_by_bot", "Sign-up by bot", ("registrations", "ai_calls"),
         "Which bot reached which people, and how many of them registered.")
def _signup_by_bot(c: Cohort, cfg: dict) -> list[Block]:
    roles = tuple(cfg.get("roles") or ("signup", "day_of", "other"))
    cols = [
        Col("bot", "Bot"),
        Col("role", "Role"),
        Col("dialled", "People dialled", fmt="int", align="right"),
        Col("connected", "People connected", fmt="int", align="right"),
        Col("reached", "People reached", fmt="int", align="right"),
        Col("attempts", "Dial attempts", fmt="int", align="right"),
        Col("answered", "Attempts answered", fmt="int", align="right"),
        Col("registered", "…who registered", fmt="int", align="right"),
        Col("reg_rate", "Reg. rate of reached", fmt="pct", align="right"),
        Col("cost", "Talk cost", fmt="money", align="right"),
    ]
    rows = []
    for stat in c.bots_by_role(roles):
        registered = len(stat.people_reached & c.registrants)
        rows.append({
            "bot": stat.name,
            "role": stat.role,
            "dialled": len(stat.people_dialled),
            "connected": len(stat.people_connected),
            "reached": len(stat.people_reached),
            "attempts": stat.attempts,
            "answered": stat.answered,
            "registered": registered,
            "reg_rate": safe_rate(registered, len(stat.people_reached)),
            "cost": stat.cost(c.rate_per_min),
        })
    rows.append({
        "bot": "All bots", "role": "", "dialled": len(c.dialled),
        "connected": len(c.connected), "reached": len(c.reached),
        "attempts": c.calls_placed, "answered": c.calls_connected,
        "registered": len(c.reached & c.registrants),
        "reg_rate": safe_rate(len(c.reached & c.registrants), len(c.reached)),
        "cost": c.talk_cost,
    })
    return [table("Bot-wise call data", cols, rows,
                  notes=["Bot rows overlap: a person reached by two bots appears under each, "
                         "so the columns do not sum to the 'All bots' row."],
                  emphasis={"All bots": "total"})]


# ------------------------------------------------------------------ #
# 3 · Show-up
# ------------------------------------------------------------------ #

@section("showup_uplift", "Show-up uplift", ("registrations", "ai_calls", "attendance"),
         "Attendance among people the day-of calls reached vs did not reach.")
def _showup_uplift(c: Cohort, cfg: dict) -> list[Block]:
    roles = tuple(cfg.get("roles") or ("signup", "day_of"))
    reached = c.people_for_roles(roles, "reached")
    dialled = c.people_for_roles(roles, "dialled")
    scope = cfg.get("scope", "dialled")

    if scope == "registrants":
        universe = c.registrants
        treated = reached & universe
        control = (universe - reached)
        label_t, label_c = "Reached", "Not reached (baseline)"
        subtitle = "Measured inside the registered pool only."
    else:
        treated = reached
        control = dialled - reached
        label_t, label_c = "Reached", "Not reached (baseline)"
        subtitle = "Everyone the bots dialled, split by whether a real conversation happened."

    rows, summary = _uplift_rows(
        c.stat_for(label_t, treated), c.stat_for(label_c, control),
        label_t, label_c, "showed",
    )
    return [_uplift_block("Show-up — reached vs not reached", subtitle, rows, summary,
                          "Showed up", "Extra show-ups created")]


@section("showup_by_day", "Show-up by day", ("ai_calls", "attendance"),
         "Per-event-day attendance for people reached that day vs everyone else.")
def _showup_by_day(c: Cohort, cfg: dict) -> list[Block]:
    roles = tuple(cfg.get("roles") or ("day_of", "signup"))
    reached = c.people_for_roles(roles, "reached")
    dialled = c.people_for_roles(roles, "dialled")
    control_pool = dialled - reached

    cols = [
        Col("day", "Day"),
        Col("reached", "Reached", fmt="int", align="right"),
        Col("attended", "Attended that day", fmt="int", align="right"),
        Col("rate", "Rate", fmt="pct", align="right"),
        Col("control_rate", "Control rate", fmt="pct", align="right"),
        Col("lift", "Relative lift", fmt="delta", align="right"),
        Col("p_value", "p", fmt="p", align="right"),
    ]
    rows = []
    weighted_num = 0.0
    weighted_den = 0
    for index, day in enumerate(c.event_days, start=1):
        present = c.attended_by_day[day]
        t_n, t_d = len(reached & present), len(reached)
        c_n, c_d = len(control_pool & present), len(control_pool)
        rate = safe_rate(t_n, t_d)
        control_rate = safe_rate(c_n, c_d)
        test = two_proportion_z_test(t_n, t_d, c_n, c_d)
        lift = relative_delta(rate, control_rate)
        if lift is not None and t_d:
            weighted_num += lift * t_d
            weighted_den += t_d
        rows.append({
            "day": f"Day {index} ({day:%d %b})",
            "reached": t_d,
            "attended": t_n,
            "rate": rate,
            "control_rate": control_rate,
            "lift": lift,
            "p_value": test.get("p_value") if test else None,
        })
    if weighted_den:
        rows.append({
            "day": "Weighted average lift", "reached": weighted_den, "attended": None,
            "rate": None, "control_rate": None,
            "lift": weighted_num / weighted_den, "p_value": None,
        })
    return [table("Show-up lift by day", cols, rows,
                  subtitle="Each day compares people a bot reached against people it dialled but never reached.",
                  emphasis={"Weighted average lift": "total"})]


# ------------------------------------------------------------------ #
# 4 · Sales & ROI
# ------------------------------------------------------------------ #

@section("sales_uplift", "Sales uplift", ("registrations", "sales", "ai_calls"),
         "Buy rate among reached vs not-reached registrants.")
def _sales_uplift(c: Cohort, cfg: dict) -> list[Block]:
    universe = c.registrants
    treated = c.reached & universe
    control = universe - c.reached
    rows, summary = _uplift_rows(
        c.stat_for("Reached", treated), c.stat_for("Not reached (baseline)", control),
        "Reached", "Not reached (baseline)", "buyers",
    )
    blocks = [_uplift_block("Sales — reached vs not reached", "Everyone here registered in the window.",
                            rows, summary, "Bought", "Extra sales created")]

    reconciliation = [
        {"group": "Buyers who registered and were reached", "count": len(treated & c.buyers)},
        {"group": "Buyers who registered, not reached", "count": len(control & c.buyers)},
        {"group": "Buyers with no registration in this window", "count": len(c.buyers_without_registration)},
        {"group": "All unique buyers", "count": len(c.buyers)},
    ]
    blocks.append(table("Buyer reconciliation",
                        [Col("group", "Source"), Col("count", "Buyers", fmt="int", align="right")],
                        reconciliation, emphasis={"All unique buyers": "total"},
                        notes=["Every buyer appears exactly once across the first three rows."]))
    return blocks


@section("cost", "AI calling cost", ("ai_calls",),
         "Billed minutes, cost, and cost per extra outcome.")
def _cost(c: Cohort, cfg: dict) -> list[Block]:
    roles = tuple(cfg.get("roles") or ("signup", "day_of"))
    reached = c.people_for_roles(roles, "reached")
    dialled = c.people_for_roles(roles, "dialled")
    _, summary = _uplift_rows(
        c.stat_for("Reached", reached), c.stat_for("Not reached", dialled - reached),
        "Reached", "Not reached", "showed",
    )
    extra = summary["extra"]
    billed, cost = c.billed_for_roles(roles if cfg.get("roles") else None)
    items = [
        Item("Billed minutes (bots in scope)", billed, fmt="int", note="60-second increments"),
        Item("Rate per minute", c.rate_per_min, fmt="money"),
        Item("AI calling cost", cost, fmt="money", tone="accent"),
    ]
    if billed != c.billed_minutes:
        items.append(Item("All bots, for reference", c.talk_cost, fmt="money",
                          note=f"{c.billed_minutes:,} minutes across every bot in the window"))
    if extra and extra > 0:
        items.append(Item("Extra attendances created", extra, fmt="number"))
        items.append(Item("Cost per extra attendance", cost / extra, fmt="money", tone="pos"))
    return [kpi("AI calling cost", items,
                notes=["Only the bots this report measures are billed to it — "
                       "an unrelated campaign running in the same window is excluded. "
                       "Change with the `cost_bot_scope` methodology setting."])]


@section("direct_roi", "Direct ROI", ("registrations", "sales", "ai_calls"),
         "Extra sales × sale value, against the talk cost.")
def _direct_roi(c: Cohort, cfg: dict) -> list[Block]:
    universe = c.registrants
    treated = c.reached & universe
    control = universe - c.reached
    _, summary = _uplift_rows(
        c.stat_for("Reached", treated), c.stat_for("Not reached", control),
        "Reached", "Not reached", "buyers",
    )
    extra_sales = summary["extra"] or 0.0
    sale_value = float(cfg.get("sale_value") or c.sale_value)
    revenue_added = extra_sales * sale_value
    _, cost = c.billed_for_roles()
    roi = safe_rate(revenue_added, cost) if cost else None

    return [kpi("Direct ROI", [
        Item("Extra sales attributed", extra_sales, fmt="number"),
        Item("Sale value", sale_value, fmt="money"),
        Item("Revenue added", revenue_added, fmt="money"),
        Item("AI calling cost", cost, fmt="money"),
        Item("Return", roi, fmt="multiple", tone="pos" if (roi or 0) >= 1 else "warn"),
        Item("Break-even sales", safe_rate(cost, sale_value), fmt="number"),
    ], subtitle="The straight calculation: extra sales priced at the programme value.")]


@section("seat_value_roi", "Conservative ROI", ("registrations", "sales", "attendance", "ai_calls"),
         "Prices the extra attendance, then discounts it to the buy rate of people AI never reached.")
def _seat_value_roi(c: Cohort, cfg: dict) -> list[Block]:
    roles = tuple(cfg.get("roles") or ("signup", "day_of"))
    reached = c.people_for_roles(roles, "reached")
    dialled = c.people_for_roles(roles, "dialled")
    _, showup = _uplift_rows(
        c.stat_for("Reached", reached), c.stat_for("Not reached", dialled - reached),
        "Reached", "Not reached", "showed",
    )
    extra_attendees = showup["extra"] or 0.0

    attendees = c.attended
    seat_value = safe_rate(c.revenue_total, len(attendees)) if attendees else None

    # The conservative rate: how often someone buys when AI never reached them.
    untouched = attendees - reached
    conservative_rate = safe_rate(len(untouched & c.buyers), len(untouched)) if untouched else None

    extra_sales = (extra_attendees * conservative_rate) if conservative_rate else None
    sale_value = float(cfg.get("sale_value") or c.sale_value)
    claimed = (extra_sales * sale_value) if extra_sales else None
    _, cost = c.billed_for_roles()
    roi = safe_rate(claimed, cost) if (claimed and cost) else None

    items = [
        Item("Revenue recorded", c.revenue_total, fmt="money"),
        Item("Unique attendees", len(attendees), fmt="int"),
        Item("Value of one seat in the room", seat_value, fmt="money"),
        Item("Extra attendees the calls created", extra_attendees, fmt="number"),
        Item("Buy rate among attendees AI never reached", conservative_rate, fmt="pct",
             note="the conservative basis"),
        Item("Extra sales at that rate", extra_sales, fmt="number"),
        Item("Value claimed", claimed, fmt="money", tone="accent"),
        Item("AI calling cost", cost, fmt="money"),
        Item("Return on the conservative estimate", roi, fmt="multiple",
             tone="pos" if (roi or 0) >= 1 else "warn"),
    ]
    return [kpi("Conservative valuation", items,
                subtitle="Deliberately understates: extra attendance is priced at the buy rate of "
                         "people the AI never reached, not at the rate of people it did."),
            text("This is the number to quote externally. It does not claim a sale the "
                 "transcripts cannot support — it claims the extra attendance, valued at the "
                 "most pessimistic conversion rate in the dataset.")]


@section("sales_attribution", "Sales attribution", ("sales", "sale_grading"),
         "Per-sale grading read from the call transcripts.")
def _sales_attribution(c: Cohort, cfg: dict) -> list[Block]:  # pragma: no cover - needs grading
    return []


@section("money_received", "Money received", ("sales",),
         "Orders and cash by payment type, and the cash actually received per buyer.")
def _money_received(c: Cohort, cfg: dict) -> list[Block]:
    cols = [Col("type", "Payment type"),
            Col("orders", "Orders", fmt="int", align="right"),
            Col("amount", "Cash received", fmt="money", align="right")]
    rows = [{"type": k.replace("_", " ").title(), "orders": v["orders"], "amount": v["amount"]}
            for k, v in sorted(c.orders_by_type.items())]
    rows.append({"type": "Total cash received", "orders": c.sale_rows, "amount": c.revenue_total})
    blocks = [table("Cash received", cols, rows, emphasis={"Total cash received": "total"})]

    blocks.append(kpi("Cash per sale", [
        Item("Unique buyers", len(c.buyers), fmt="int"),
        Item("Total cash received", c.revenue_total, fmt="money"),
        Item("Cash per sale", c.cash_per_sale, fmt="money", tone="accent",
             note="what a buyer is actually worth in this window"),
    ], subtitle="Deposits and instalments mean the headline programme price and the cash "
                "received are rarely the same. ROI is priced on this figure."))
    return blocks


@section("per_campaign", "Per campaign", ("ai_calls", "registrations"),
         "Extra outcomes attributable to each bot, weighted sum vs direct unique.")
def _per_campaign(c: Cohort, cfg: dict) -> list[Block]:
    metric = cfg.get("metric", "showed")
    roles = tuple(cfg.get("roles") or ("signup", "day_of"))
    universe = c.people_for_roles(roles, "dialled")
    baseline_pool = universe - c.people_for_roles(roles, "reached")
    base_stat = c.stat_for("baseline", baseline_pool)
    base_rate = getattr(base_stat, {"showed": "show_rate", "buyers": "buy_rate",
                                    "registered": "reg_rate"}[metric])

    label = {"showed": "show-ups", "buyers": "sales", "registered": "registrations"}[metric]
    cols = [Col("campaign", "Campaign"),
            Col("people", "People reached", fmt="int", align="right"),
            Col("rate", "Rate", fmt="pct", align="right"),
            Col("extra", f"Extra {label}", fmt="number", align="right")]

    rows = []
    weighted_people = 0
    weighted_extra = 0.0
    for stat in c.bots_by_role(roles):
        people = stat.people_reached
        if not people:
            continue
        s = c.stat_for(stat.name, people)
        rate = getattr(s, {"showed": "show_rate", "buyers": "buy_rate",
                           "registered": "reg_rate"}[metric])
        extra = (rate - base_rate) * len(people)
        weighted_people += len(people)
        weighted_extra += extra
        rows.append({"campaign": stat.name, "people": len(people), "rate": rate, "extra": extra})

    rows.append({"campaign": "Weighted sum (multi-touch people counted repeatedly)",
                 "people": weighted_people, "rate": None, "extra": weighted_extra})

    unique = c.people_for_roles(roles, "reached")
    u = c.stat_for("all", unique)
    u_rate = getattr(u, {"showed": "show_rate", "buyers": "buy_rate",
                         "registered": "reg_rate"}[metric])
    rows.append({"campaign": "Direct unique — all reached (quote this)",
                 "people": len(unique), "rate": u_rate,
                 "extra": (u_rate - base_rate) * len(unique)})

    return [table(f"Per campaign — extra {label}", cols, rows,
                  subtitle="Each bot measured against the same baseline: people dialled but never reached.",
                  emphasis={"Weighted sum (multi-touch people counted repeatedly)": "total",
                            "Direct unique — all reached (quote this)": "verdict"},
                  notes=["The weighted sum counts a person once per bot that reached them, so it "
                         "overstates the total. Quote the direct-unique row."])]


@section("roi_derivation", "ROI derivation", ("registrations", "sales", "ai_calls"),
         "The ROI shown as numbered steps, each with the arithmetic behind it.")
def _roi_derivation(c: Cohort, cfg: dict) -> list[Block]:
    universe = c.registrants
    treated = c.reached & universe
    control = universe - c.reached
    t, ctrl = c.stat_for("reached", treated), c.stat_for("not reached", control)
    rate_t, rate_c = t.buy_rate, ctrl.buy_rate
    uplift = (rate_t or 0) - (rate_c or 0)
    extra_sales = uplift * t.people
    per_sale = c.cash_per_sale or c.sale_value
    extra_revenue = extra_sales * per_sale
    _, cost = c.billed_for_roles()
    roi = safe_rate(extra_revenue, cost) if cost else None

    cols = [Col("step", "Step"), Col("value", "Value", fmt="number", align="right"),
            Col("derivation", "Derivation")]
    rows = [
        {"step": "1. Buy rate, reached registrants", "value": rate_t,
         "derivation": f"{t.buyers} of {t.people:,}", "_fmt_value": "pct"},
        {"step": "2. Buy rate, not reached", "value": rate_c,
         "derivation": f"{ctrl.buyers} of {ctrl.people:,}", "_fmt_value": "pct"},
        {"step": "3. Uplift", "value": uplift, "derivation": "step 1 − step 2", "_fmt_value": "pp"},
        {"step": "4. Extra sales", "value": extra_sales,
         "derivation": f"{t.people:,} reached × step 3"},
        {"step": "5. Cash per sale", "value": per_sale,
         "derivation": f"{c.revenue_total:,.0f} ÷ {len(c.buyers)} buyers", "_fmt_value": "money"},
        {"step": "6. Extra revenue", "value": extra_revenue,
         "derivation": "step 4 × step 5", "_fmt_value": "money"},
        {"step": "7. AI calling cost", "value": cost,
         "derivation": f"billed minutes × {c.rate_per_min:.2f}/min", "_fmt_value": "money"},
        {"step": "8. ROI", "value": roi, "derivation": "step 6 ÷ step 7", "_fmt_value": "multiple"},
    ]
    return [table("ROI, step by step", cols, rows,
                  emphasis={"8. ROI": "verdict"},
                  notes=[f"The per-minute rate ({c.rate_per_min:.2f}) is a methodology setting, "
                         "not an invoice. Change it under Methodology and every step follows."])]


@section("confidence", "How solid is it?", ("registrations", "sales", "ai_calls"),
         "95% interval on the extra sales and the ROI, plus the break-even point.")
def _confidence(c: Cohort, cfg: dict) -> list[Block]:
    universe = c.registrants
    treated = c.reached & universe
    control = universe - c.reached
    t, ctrl = c.stat_for("reached", treated), c.stat_for("not reached", control)
    band = proportion_diff_ci(t.buyers, t.people, ctrl.buyers, ctrl.people)
    per_sale = c.cash_per_sale or c.sale_value
    _, cost = c.billed_for_roles()

    def to_roi(diff):
        if diff is None or not cost:
            return None
        return (diff * t.people * per_sale) / cost

    cols = [Col("bound", ""), Col("extra_sales", "Extra sales", fmt="number", align="right"),
            Col("roi", "ROI", fmt="multiple", align="right")]
    rows = [
        {"bound": "95% interval — low", "extra_sales": (band["low"] or 0) * t.people if band["low"] is not None else None,
         "roi": to_roi(band["low"])},
        {"bound": "Point estimate", "extra_sales": (band["point"] or 0) * t.people if band["point"] is not None else None,
         "roi": to_roi(band["point"])},
        {"bound": "95% interval — high", "extra_sales": (band["high"] or 0) * t.people if band["high"] is not None else None,
         "roi": to_roi(band["high"])},
        {"bound": "Break-even — extra sales needed to cover cost",
         "extra_sales": safe_rate(cost, per_sale) if per_sale else None, "roi": 1.0},
    ]
    notes = []
    if band["crosses_zero"]:
        notes.append("The interval crosses zero: on this sample the uplift is not "
                     "statistically distinguishable from no effect. Report it as inconclusive.")
    else:
        notes.append("The interval stays on one side of zero, so the direction of the effect "
                     "is supported by this sample.")
    return [table("How solid is it?", cols, rows,
                  emphasis={"Point estimate": "verdict"}, notes=notes)]


@section("sensitivity", "Sensitivity", ("registrations", "sales", "ai_calls"),
         "Does the result survive a different definition of 'reached'?")
def _sensitivity(c: Cohort, cfg: dict) -> list[Block]:
    thresholds = cfg.get("thresholds") or [10, 15, 30, 60]
    universe = c.registrants
    per_sale = c.cash_per_sale or c.sale_value
    _, cost = c.billed_for_roles()

    # Recompute the reached set at each threshold straight from the bot stats.
    cols = [Col("definition", "Definition of reached"),
            Col("people", "People", fmt="int", align="right"),
            Col("buy_rate", "Buy %", fmt="pct", align="right"),
            Col("extra", "Extra sales", fmt="number", align="right"),
            Col("roi", "ROI", fmt="multiple", align="right"),
            Col("p_value", "p", fmt="p", align="right")]
    rows = []
    for threshold in sorted(set(thresholds)):
        reached = c.reached_at(threshold)
        treated = reached & universe
        control = universe - reached
        t, ctrl = c.stat_for("t", treated), c.stat_for("c", control)
        uplift = (t.buy_rate or 0) - (ctrl.buy_rate or 0)
        extra = uplift * t.people
        test = two_proportion_z_test(t.buyers, t.people, ctrl.buyers, ctrl.people)
        rows.append({
            "definition": f"Answered and > {threshold}s"
                          + ("  (used above)" if threshold == c.reach_threshold_s else ""),
            "people": t.people,
            "buy_rate": t.buy_rate,
            "extra": extra,
            "roi": safe_rate(extra * per_sale, cost) if cost else None,
            "p_value": test.get("p_value") if test else None,
        })
    return [table("Sensitivity to the 'reached' threshold", cols, rows,
                  subtitle="If the finding only holds at one arbitrary cut-off, it is not a finding.",
                  notes=["A result that holds across thresholds is robust; one that flips is not."])]


@section("rescue_campaign", "Rescue campaign", ("ai_calls", "attendance"),
         "For no-shows called after a missed day: did they come back?")
def _rescue(c: Cohort, cfg: dict) -> list[Block]:
    days = c.event_days
    if len(days) < 2:
        return [text("A rescue campaign needs at least two event days to measure a return.")]

    roles = tuple(cfg.get("roles") or ("day_of",))
    first_day, later_days = days[0], days[1:]
    attended_first = c.attended_by_day[first_day]
    returned = set().union(*(c.attended_by_day[d] for d in later_days))

    # People dialled after day 1 who had not attended day 1.
    called = c.people_for_roles(roles, "dialled") - attended_first
    reached = c.people_for_roles(roles, "reached") & called
    not_reached = called - reached

    cols = [Col("group", "Group"), Col("people", "People", fmt="int", align="right"),
            Col("returned", "Returned later", fmt="int", align="right"),
            Col("rate", "Return %", fmt="pct", align="right")]
    r_rate = safe_rate(len(reached & returned), len(reached))
    n_rate = safe_rate(len(not_reached & returned), len(not_reached))
    rows = [
        {"group": "Reached", "people": len(reached),
         "returned": len(reached & returned), "rate": r_rate},
        {"group": "Not reached (baseline)", "people": len(not_reached),
         "returned": len(not_reached & returned), "rate": n_rate},
        {"group": "Relative lift", "people": None, "returned": None,
         "rate": relative_delta(r_rate, n_rate), "_fmt_rate": "delta"},
        {"group": "Extra returners recovered", "people": None,
         "returned": (r_rate - n_rate) * len(reached), "rate": None,
         "_fmt_returned": "number"},
    ]
    test = two_proportion_z_test(len(reached & returned), len(reached),
                                 len(not_reached & returned), len(not_reached))
    notes = [f"Measured on return, not first attendance — everyone here missed {first_day:%d %b}."]
    if test and test.get("p_value") is not None:
        notes.append(f"p = {test['p_value']:.4f}")
    return [table("Return after a missed day", cols, rows,
                  emphasis={"Relative lift": "total", "Extra returners recovered": "verdict",
                            "Not reached (baseline)": "baseline"},
                  notes=notes)]


@section("buyers", "People (buyers)", ("sales",),
         "Every buyer named, with the AI contact they actually had.")
def _buyers(c: Cohort, cfg: dict) -> list[Block]:
    from sqlalchemy import select as _select
    from ..models import Person as _Person

    ids = sorted(c.buyers)
    if not ids:
        return [text("No buyers in this window.")]

    people = {
        p.id: p for p in c.db.execute(
            _select(_Person).where(_Person.id.in_(ids))
        ).scalars()
    }
    cols = [
        Col("name", "Name"),
        Col("phone", "Phone"),
        Col("contact", "AI contact"),
        Col("registered", "Registered"),
        Col("attended", "Attended"),
        Col("revenue", "Revenue", fmt="money", align="right"),
    ]
    rows = []
    for pid in ids:
        person = people.get(pid)
        if pid in c.reached:
            contact = f"reached (>{c.reach_threshold_s}s)"
        elif pid in c.connected:
            contact = "connected, brief"
        elif pid in c.dialled:
            contact = "dialled, never answered"
        else:
            contact = "never dialled"
        rows.append({
            "name": (person.display_name if person else None) or f"person {pid}",
            "phone": (person.phone if person else None) or "—",
            "contact": contact,
            "registered": "Yes" if pid in c.registrants else "No",
            "attended": "Yes" if pid in c.attended else "No",
            "revenue": c.revenue_by_person.get(pid, 0.0),
        })
    rows.sort(key=lambda r: (r["contact"], r["name"]))
    return [table(f"The {len(ids)} buyers — AI contact", cols, rows,
                  notes=["Contact level is derived from the call log. It says a conversation "
                         "happened, not that the conversation caused the sale — that judgement "
                         "needs the transcripts."])]


# ------------------------------------------------------------------ #
# 5 · Method
# ------------------------------------------------------------------ #

@section("methodology", "Method & audit", (),
         "Definitions, thresholds and row-level reconciliation.")
def _methodology(c: Cohort, cfg: dict) -> list[Block]:
    definitions = [
        {"term": "Connected", "meaning": "The call was answered — any talk time above zero."},
        {"term": "Reached", "meaning": f"Answered and talked for more than {c.reach_threshold_s}s. "
                                       "This is the bar for 'a real conversation happened'."},
        {"term": "Baseline", "meaning": "People the bots dialled but never reached. They opted in "
                                        "the same way; the only difference is whether a conversation landed."},
        {"term": "Extra outcomes", "meaning": "Rate difference in percentage points × the size of the "
                                              "treated group."},
        {"term": "Billed minutes", "meaning": "Talk time rounded up to whole minutes, per call."},
    ]
    audit = [
        {"item": "Registration rows read", "value": c.registration_rows},
        {"item": "…team/test rows removed", "value": c.team_registration_rows},
        {"item": "…unique registrants", "value": len(c.registrants)},
        {"item": "Calls read", "value": c.calls_placed},
        {"item": "…matched to a person", "value": c.matched_calls},
        {"item": "Sale rows read", "value": c.sale_rows},
        {"item": "…buyers with no registration", "value": len(c.buyers_without_registration)},
        {"item": "Attendance — unique attendees", "value": len(c.attended)},
        {"item": "Event days seen", "value": len(c.event_days)},
        {"item": "Connect threshold (s)", "value": c.connect_threshold_s},
        {"item": "Reach threshold (s)", "value": c.reach_threshold_s},
        {"item": "Cost per minute", "value": c.rate_per_min},
    ]
    return [
        table("Definitions", [Col("term", "Term"), Col("meaning", "Meaning")], definitions),
        table("Data audit", [Col("item", "Item"), Col("value", "Value", fmt="number", align="right")], audit),
        text("Every comparison here is observational. People who answered a call differ from people "
             "who did not in ways this data cannot see, so treat the uplift as association, not "
             "proof of cause."),
    ]
