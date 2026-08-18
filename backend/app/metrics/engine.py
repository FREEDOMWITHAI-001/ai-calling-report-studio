"""The report engine.

Reproduces the calculation behind the reference CoachEasily reports:

  registrants (deduped people, team rows removed)
    -> connected / not-connected split from the bot call log (talk > 15s)
    -> show-up matched against the attendance list
    -> buyers matched against the sales list (one full sale per person)
    -> lead-age-banded weighted uplift  -> extra sales credited to AI
    -> revenue with / without AI, uplift, talk cost, ROI

Every threshold, pattern and rate lives in `params` (the methodology config) so
the numbers stay traceable and adjustable instead of hardcoded.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DEFAULT_METHODOLOGY
from ..models import AiCall, Attendance, Bot, Person, Registration, Sale, WebinarDaily
from .stats import relative_delta, safe_rate, two_proportion_z_test

GROUP_SIGNUP = "signup"
GROUP_DAYOF = "day_of"
GROUP_BOTH = "both"
GROUP_BASELINE = "baseline"
GROUP_CONNECTED = "connected"

BASELINE_LABELS = {
    "not_connected": "Not connected  (BASELINE)",
    "never_dialled": "Never dialled  (BASELINE)",
    "no_bot_reached": "No bot reached",
}


def _merge_params(params: dict | None) -> dict:
    merged = dict(DEFAULT_METHODOLOGY)
    merged.update(params or {})
    return merged


def _has_program(db: Session, model, client_id: int) -> bool:
    """Has this client actually tagged rows of this kind with a webinar?

    Scoping only switches on once the data can support it, so a client running
    one webinar — where nothing is tagged — keeps exactly the numbers it had.
    """
    return db.execute(
        select(model.id).where(model.client_id == client_id,
                               model.program.is_not(None)).limit(1)
    ).first() is not None


def _bot_maps(db: Session, client_id: int, params: dict):
    roles: dict[str, str] = {}
    languages: dict[str, str | None] = {}
    programs: dict[str, str | None] = {}
    for bot in db.execute(select(Bot).where(Bot.client_id == client_id)).scalars():
        roles[bot.name] = bot.role
        languages[bot.name] = bot.language
        programs[bot.name] = bot.program
    # Patterns win over whatever was stored at ingest time, so editing the
    # methodology re-classifies bots without re-uploading anything.
    for name in list(roles):
        lowered = name.lower()
        if any(p.lower() in lowered for p in params.get("signup_bot_patterns", [])):
            roles[name] = "signup"
        elif any(p.lower() in lowered for p in params.get("dayof_bot_patterns", [])):
            roles[name] = "day_of"
        for program, patterns in (params.get("program_bot_patterns") or {}).items():
            if any(str(pat).lower() in lowered for pat in patterns):
                programs[name] = program
                break
    return roles, languages, programs


def compute_report(
    db: Session,
    client_id: int,
    date_from: date,
    date_to: date,
    params: dict | None = None,
    language: str | None = None,
    program: str | None = None,
    bot_names: list[str] | None = None,
    product: str | None = None,
    title: str | None = None,
) -> dict:
    params = _merge_params(params)
    threshold = int(params.get("connect_threshold_s", 15))
    sale_value = float(params.get("sale_value", 6999))
    rate_per_min = float(params.get("cost_per_minute", 5.10))
    baseline_mode = params.get("baseline_mode", "not_connected")

    roles, bot_languages, bot_programs = _bot_maps(db, client_id, params)
    selected_bots = set(bot_names or [])
    lock_language = bool(language) and params.get("restrict_bots_to_language", True)

    def in_scope(bot_name: str | None) -> bool:
        """Which bots count towards 'connected' and towards the talk cost.

        An explicit bot selection replaces the signup/day-of filter, but only
        that filter: a chosen bot still has to belong to this report's language
        and programme. Letting a selection bypass those turned "show me these
        bots" into "charge every webinar for all of them", which is not what
        picking a bot from a list means.
        """
        if not bot_name:
            return False
        if selected_bots:
            if bot_name not in selected_bots:
                return False
        elif roles.get(bot_name, "other") not in ("signup", "day_of"):
            return False
        if lock_language:
            bot_language = bot_languages.get(bot_name)
            if bot_language and bot_language.lower() != language.lower():
                return False
        if program and any(bot_programs.values()):
            # Two webinars running side by side each have their own bots. Once
            # any bot is tagged, a report scoped to one programme counts only
            # that programme's bots, so its ROI is not charged the other's
            # talk time.
            bot_program = bot_programs.get(bot_name)
            if bot_program and bot_program.lower() != program.lower():
                return False
        return True

    def role_of(bot_name: str | None) -> str:
        return roles.get(bot_name or "", "other")

    # ------------------------------------------------------------------ #
    # 1. Registrants in the window, deduplicated to people
    # ------------------------------------------------------------------ #
    team_ids = {
        pid for (pid,) in db.execute(
            select(Person.id).where(Person.client_id == client_id, Person.is_team.is_(True))
        ).all()
    }

    reg_q = select(
        Registration.person_id,
        Registration.registration_date,
        Registration.name,
        Registration.phone_norm,
    ).where(
        Registration.client_id == client_id,
        Registration.registration_date >= date_from,
        Registration.registration_date <= date_to,
    )
    if language:
        reg_q = reg_q.where(Registration.language == language)
    if program:
        reg_q = reg_q.where(Registration.program == program)

    first_reg: dict[int, date] = {}
    reg_rows = 0
    team_reg_rows = 0
    for person_id, reg_date, _name, _phone in db.execute(reg_q).all():
        reg_rows += 1
        if person_id is None:
            continue
        if person_id in team_ids:
            team_reg_rows += 1
            continue
        current = first_reg.get(person_id)
        if current is None or reg_date < current:
            first_reg[person_id] = reg_date

    cohort = set(first_reg)
    registrants = len(cohort)

    # ------------------------------------------------------------------ #
    # 2. Calls in the window -> connection state per person
    # ------------------------------------------------------------------ #
    call_q = select(
        AiCall.person_id,
        AiCall.bot_name,
        AiCall.duration_s,
        AiCall.call_date,
        AiCall.status,
    ).where(
        AiCall.client_id == client_id,
        AiCall.call_date >= date_from,
        AiCall.call_date <= date_to,
    )

    connected_signup: set[int] = set()
    connected_dayof: set[int] = set()
    dialled: set[int] = set()
    calls_placed = calls_with_audio = calls_connected = 0
    talk_seconds = 0
    billed_minutes = 0
    cost_by_bot: dict[str, dict] = defaultdict(lambda: {"calls": 0, "billed_minutes": 0, "talk_seconds": 0})
    matched_calls = 0
    bots_seen: dict[str, int] = defaultdict(int)
    bot_days: dict[str, set] = defaultdict(set)

    for person_id, bot_name, duration, call_date, _status in db.execute(call_q).all():
        if person_id in team_ids:
            continue
        bots_seen[bot_name or "(unnamed)"] += 1
        if not in_scope(bot_name):
            continue
        duration = duration or 0
        calls_placed += 1
        if person_id in cohort:
            matched_calls += 1
            dialled.add(person_id)
        if duration > 0:
            calls_with_audio += 1
            talk_seconds += duration
            minutes = math.ceil(duration / 60) if params.get("billing_rounding") == "ceil_minute" else duration / 60
            billed_minutes += minutes
            bucket = cost_by_bot[bot_name]
            bucket["calls"] += 1
            bucket["billed_minutes"] += minutes
            bucket["talk_seconds"] += duration
            if call_date:
                bot_days[bot_name].add(call_date)
        if duration > threshold:
            calls_connected += 1
            if person_id in cohort:
                if role_of(bot_name) == "signup":
                    connected_signup.add(person_id)
                elif role_of(bot_name) == "day_of":
                    connected_dayof.add(person_id)
                else:
                    connected_signup.add(person_id)

    connected = connected_signup | connected_dayof
    both_bots = connected_signup & connected_dayof
    if baseline_mode == "never_dialled":
        baseline = cohort - dialled
    else:
        baseline = cohort - connected

    talk_cost = billed_minutes * rate_per_min
    for bot_name, bucket in cost_by_bot.items():
        bucket["cost"] = round(bucket["billed_minutes"] * rate_per_min, 2)
        bucket["role"] = role_of(bot_name)
        bucket["days_active"] = len(bot_days.get(bot_name, ()))

    # ------------------------------------------------------------------ #
    # 3. Show-up and buyers per person
    # ------------------------------------------------------------------ #
    # Show-up is a per-person match against the attendance data, the way the
    # reference reports do it. 'window' counts any attendance inside the report
    # window (people sometimes attend a later day than the one they signed up
    # for); 'same_day' ties attendance to the registration day.
    grace = int(params.get("attendance_match_days", 1))
    match_mode = params.get("attendance_match_mode", "window")
    att_q = select(Attendance.person_id, Attendance.attended_on).where(
        Attendance.client_id == client_id,
        Attendance.attended_on >= date_from,
        Attendance.attended_on <= date_to + timedelta(days=grace),
    )
    if language:
        att_q = att_q.where(Attendance.language == language)
    if program and _has_program(db, Attendance, client_id):
        att_q = att_q.where(Attendance.program == program)
    showed: set[int] = set()
    for person_id, attended_on in db.execute(att_q).all():
        if person_id not in cohort or attended_on is None:
            continue
        if match_mode == "same_day":
            reg_day = first_reg[person_id]
            if not (reg_day <= attended_on <= reg_day + timedelta(days=grace)):
                continue
        showed.add(person_id)

    sale_q = select(Sale.person_id, Sale.sale_date, Sale.amount).where(
        Sale.client_id == client_id,
        Sale.sale_date >= date_from,
        Sale.sale_date <= date_to,
    )
    if product:
        sale_q = sale_q.where(Sale.product == product)
    if program and _has_program(db, Sale, client_id):
        sale_q = sale_q.where(Sale.program == program)
    buyers: set[int] = set()
    sale_rows_in_window = 0
    sale_rows_outside_cohort = 0
    sale_rows_before_registration = 0
    for person_id, sale_date, amount in db.execute(sale_q).all():
        sale_rows_in_window += 1
        if person_id not in cohort:
            sale_rows_outside_cohort += 1
            continue
        if params.get("drop_sales_before_registration", True) and sale_date < first_reg[person_id]:
            sale_rows_before_registration += 1
            continue
        buyers.add(person_id)

    # ------------------------------------------------------------------ #
    # 4. Group table
    # ------------------------------------------------------------------ #
    def group_stats(members: set[int]) -> dict:
        n = len(members)
        showed_n = len(members & showed)
        buyers_n = len(members & buyers)
        return {
            "registrants": n,
            "showed": showed_n,
            "show_rate": safe_rate(showed_n, n),
            "buyers": buyers_n,
            "buy_rate": safe_rate(buyers_n, n),
        }

    baseline_stats = group_stats(baseline)
    groups = {
        "total": {**group_stats(cohort), "label": "Total"},
        GROUP_SIGNUP: {**group_stats(connected_signup), "label": "Signup bot (Instant Conf.)"},
        GROUP_DAYOF: {**group_stats(connected_dayof), "label": "Day-of bot (Session Today)"},
        GROUP_BOTH: {**group_stats(both_bots), "label": "Both bots"},
        GROUP_CONNECTED: {**group_stats(connected), "label": "Connected (either bot)"},
        GROUP_BASELINE: {**baseline_stats, "label": BASELINE_LABELS.get(baseline_mode, "Baseline")},
    }
    for key, stats in groups.items():
        if key in ("total", GROUP_BASELINE):
            stats["show_delta"] = None
            stats["buy_delta"] = None
        else:
            stats["show_delta"] = relative_delta(stats["show_rate"], baseline_stats["show_rate"])
            stats["buy_delta"] = relative_delta(stats["buy_rate"], baseline_stats["buy_rate"])

    # ------------------------------------------------------------------ #
    # 5. Uplift -> extra sales credited to AI
    # ------------------------------------------------------------------ #
    as_of = date_to
    band_edges = list(params.get("age_band_edges", [0, 3, 7, 10, 14]))
    bands = _build_bands(band_edges)
    band_rows = []
    weighted_extra = 0.0
    for low, high, label in bands:
        band_members = {
            pid for pid in cohort
            if low <= (as_of - first_reg[pid]).days <= (high if high is not None else 10**6)
        }
        conn_members = band_members & connected
        base_members = band_members & baseline
        conn_buy = safe_rate(len(conn_members & buyers), len(conn_members))
        base_buy = safe_rate(len(base_members & buyers), len(base_members))
        gap = conn_buy - base_buy
        extra = gap * len(conn_members)
        weighted_extra += extra
        band_rows.append({
            "band": label,
            "connected": len(conn_members),
            "connected_buyers": len(conn_members & buyers),
            "connected_buy_rate": conn_buy,
            "baseline": len(base_members),
            "baseline_buyers": len(base_members & buyers),
            "baseline_buy_rate": base_buy,
            "gap_points": gap,
            "extra_sales": extra,
        })

    conn_stats = group_stats(connected)
    simple_gap = conn_stats["buy_rate"] - baseline_stats["buy_rate"]
    simple_extra = simple_gap * len(connected)
    uplift_mode = params.get("uplift_mode", "weighted")
    extra_sales = weighted_extra if uplift_mode == "weighted" else simple_extra
    weighted_gap = safe_rate(weighted_extra, len(connected)) if connected else 0.0

    revenue_with = len(buyers) * sale_value
    revenue_added = extra_sales * sale_value
    revenue_without = revenue_with - revenue_added
    relative_uplift = safe_rate(revenue_added, revenue_without) if revenue_without else None
    roi = safe_rate(revenue_added, talk_cost) if talk_cost else None
    breakeven_sales = safe_rate(talk_cost, sale_value) if sale_value else None

    show_test = two_proportion_z_test(
        conn_stats["showed"], conn_stats["registrants"],
        baseline_stats["showed"], baseline_stats["registrants"],
    )
    buy_test = two_proportion_z_test(
        conn_stats["buyers"], conn_stats["registrants"],
        baseline_stats["buyers"], baseline_stats["registrants"],
    )

    # ------------------------------------------------------------------ #
    # 6. Per-day detail (by registration date)
    # ------------------------------------------------------------------ #
    by_day: dict[date, set[int]] = defaultdict(set)
    for pid, reg_day in first_reg.items():
        by_day[reg_day].add(pid)

    daily = []
    for day in sorted(by_day):
        members = by_day[day]
        day_baseline = members & baseline
        day_base_stats = group_stats(day_baseline)
        rows = []
        for key, label, subset in (
            ("total", "Total", members),
            (GROUP_SIGNUP, "Signup bot", members & connected_signup),
            (GROUP_DAYOF, "Day-of bot", members & connected_dayof),
            (GROUP_BOTH, "Both bots", members & both_bots),
            (GROUP_BASELINE, BASELINE_LABELS.get(baseline_mode, "Baseline").split("  ")[0], day_baseline),
        ):
            if key in (GROUP_DAYOF, GROUP_BOTH) and not subset:
                continue  # a bot that did not run that day is omitted, not zeroed
            stats = group_stats(subset)
            stats["label"] = label
            stats["key"] = key
            if key in ("total", GROUP_BASELINE):
                stats["show_delta"] = stats["buy_delta"] = None
            else:
                stats["show_delta"] = relative_delta(stats["show_rate"], day_base_stats["show_rate"])
                stats["buy_delta"] = relative_delta(stats["buy_rate"], day_base_stats["buy_rate"])
            rows.append(stats)
        daily.append({"date": day.isoformat(), "rows": rows})

    # ------------------------------------------------------------------ #
    # 7. Reconciliation against the platform's own numbers
    # ------------------------------------------------------------------ #
    platform = db.execute(
        select(WebinarDaily.leads, WebinarDaily.show_up).where(
            WebinarDaily.client_id == client_id,
            WebinarDaily.day >= date_from,
            WebinarDaily.day <= date_to,
        )
    ).all()
    platform_leads = sum(r[0] or 0 for r in platform)
    platform_show = sum(r[1] or 0 for r in platform)

    window_days = (date_to - date_from).days + 1
    label = title or "AI calling impact"

    return {
        "meta": {
            "title": label,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "window_days": window_days,
            "language": language,
            "program": program,
            "product": product,
            "bot_filter": sorted(selected_bots) or None,
            "baseline_mode": baseline_mode,
            "uplift_mode": uplift_mode,
            "params": params,
        },
        "headline": {
            "registrants": registrants,
            "connected_people": len(connected),
            "baseline_people": len(baseline),
            "showed": len(showed),
            "buyers": len(buyers),
            "revenue_with_ai": revenue_with,
            "revenue_without_ai": revenue_without,
            "revenue_added": revenue_added,
            "relative_uplift": relative_uplift,
            "extra_sales": extra_sales,
            "sale_value": sale_value,
            "talk_cost": talk_cost,
            "roi": roi,
            "breakeven_sales": breakeven_sales,
            "weighted_gap_points": weighted_gap,
            "simple_gap_points": simple_gap,
        },
        "groups": groups,
        "bands": band_rows,
        "daily": daily,
        "calls": {
            "calls_placed": calls_placed,
            "calls_with_audio": calls_with_audio,
            "calls_connected": calls_connected,
            "calls_never_connected": calls_placed - calls_with_audio,
            "talk_seconds": talk_seconds,
            "talk_minutes_exact": round(talk_seconds / 60, 1),
            "billed_minutes": billed_minutes,
            "cost_per_minute": rate_per_min,
            "talk_cost": talk_cost,
            "matched_calls": matched_calls,
            "match_rate": safe_rate(matched_calls, calls_placed),
            "by_bot": {k: v for k, v in sorted(cost_by_bot.items())},
            "bots_in_window": dict(sorted(bots_seen.items(), key=lambda kv: -kv[1])),
        },
        "audit": {
            "registration_rows": reg_rows,
            "team_registration_rows": team_reg_rows,
            "unique_registrants": registrants,
            "repeat_registration_rows": reg_rows - team_reg_rows - registrants,
            "sale_rows_in_window": sale_rows_in_window,
            "sale_rows_outside_cohort": sale_rows_outside_cohort,
            "sale_rows_before_registration": sale_rows_before_registration,
            "platform_leads": platform_leads or None,
            "platform_show_up": platform_show or None,
            "show_up_reconciliation": safe_rate(registrants, platform_leads) if platform_leads else None,
            "connected_threshold_s": threshold,
            "as_of": as_of.isoformat(),
        },
        "significance": {"show_up": show_test, "buying": buy_test},
    }


def _build_bands(edges: list[int]) -> list[tuple[int, int | None, str]]:
    bands: list[tuple[int, int | None, str]] = []
    ordered = sorted(set(int(e) for e in edges))
    for idx, low in enumerate(ordered):
        if idx + 1 < len(ordered):
            high = ordered[idx + 1] - 1
            bands.append((low, high, f"{low}-{high} days"))
        else:
            bands.append((low, None, f"{low}+ days"))
    return bands
