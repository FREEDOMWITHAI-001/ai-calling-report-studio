"""The shared cohort — everything the section library computes from.

Built once per report from the four inputs the client supplies:

    1. registrations   2. ai_calls   3. sales   4. attendance (Zoom)

Two definitions matter and are deliberately kept apart, because the client
workbooks report them separately and conflating them overstates reach:

    connected  the call was answered at all            (duration > 0)
    reached    answered AND talked past the threshold  (duration > reach_threshold_s)

People-level and call-level counts are also kept apart. "3,653 people called"
and "20,502 calls placed" describe the same activity and must never be read
across each other.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DEFAULT_METHODOLOGY
from ..models import AiCall, Attendance, Bot, Person, Registration, Sale
from .stats import safe_rate


def merge_params(params: dict | None) -> dict:
    merged = dict(DEFAULT_METHODOLOGY)
    merged.update(params or {})
    return merged


@dataclass
class BotStat:
    name: str
    role: str = "other"
    language: str | None = None
    attempts: int = 0                       # dials, not people
    answered: int = 0                       # dials that connected
    reached_calls: int = 0                  # dials that passed the reach threshold
    talk_seconds: int = 0
    billed_minutes: int = 0
    days_active: set = field(default_factory=set)
    people_dialled: set = field(default_factory=set)
    people_connected: set = field(default_factory=set)
    people_reached: set = field(default_factory=set)

    def cost(self, rate_per_min: float) -> float:
        return round(self.billed_minutes * rate_per_min, 2)


@dataclass
class GroupStat:
    """One row of any called-vs-not-called / reached-vs-not-reached table."""
    label: str
    people: int = 0
    registered: int = 0
    showed: int = 0
    buyers: int = 0
    revenue: float = 0.0

    @property
    def reg_rate(self) -> float | None:
        return safe_rate(self.registered, self.people)

    @property
    def show_rate(self) -> float | None:
        return safe_rate(self.showed, self.people)

    @property
    def buy_rate(self) -> float | None:
        return safe_rate(self.buyers, self.people)


class Cohort:
    """Everything one report window knows about one client."""

    def __init__(self, db: Session, client_id: int, date_from: date, date_to: date,
                 params: dict | None = None, language: str | None = None,
                 program: str | None = None):
        self.db = db
        self.client_id = client_id
        self.date_from = date_from
        self.date_to = date_to
        self.language = language
        self.program = program
        self.params = merge_params(params)

        self.connect_threshold_s = int(self.params.get("connect_threshold_s", 15))
        # "reached" defaults to the same bar the old engine called "connected",
        # so existing numbers keep their meaning while the new split is added.
        self.reach_threshold_s = int(self.params.get("reach_threshold_s",
                                                     self.connect_threshold_s))
        self.rate_per_min = float(self.params.get("cost_per_minute", 5.10))
        self.sale_value = float(self.params.get("sale_value", 6999))

        self._load_people()
        self._load_bots()
        self._load_registrations()
        self._load_calls()
        self._load_attendance()
        self._load_sales()

    # ------------------------------------------------------------------ #
    # loading
    # ------------------------------------------------------------------ #
    def _load_people(self) -> None:
        self.team_ids = {
            pid for (pid,) in self.db.execute(
                select(Person.id).where(Person.client_id == self.client_id,
                                        Person.is_team.is_(True))
            ).all()
        }

    def _load_bots(self) -> None:
        self.bot_roles: dict[str, str] = {}
        self.bot_languages: dict[str, str | None] = {}
        for bot in self.db.execute(
            select(Bot).where(Bot.client_id == self.client_id)
        ).scalars():
            self.bot_roles[bot.name] = bot.role
            self.bot_languages[bot.name] = bot.language

        # Patterns win over whatever was stored at ingest time, so editing the
        # methodology re-classifies bots without re-uploading anything.
        for name in list(self.bot_roles):
            lowered = name.lower()
            if any(p.lower() in lowered for p in self.params.get("signup_bot_patterns", [])):
                self.bot_roles[name] = "signup"
            elif any(p.lower() in lowered for p in self.params.get("dayof_bot_patterns", [])):
                self.bot_roles[name] = "day_of"

    def role_of(self, bot_name: str | None) -> str:
        return self.bot_roles.get(bot_name or "", "other")

    def _load_registrations(self) -> None:
        query = select(Registration.person_id, Registration.registration_date).where(
            Registration.client_id == self.client_id,
            Registration.registration_date >= self.date_from,
            Registration.registration_date <= self.date_to,
        )
        if self.language:
            query = query.where(Registration.language == self.language)
        if self.program:
            query = query.where(Registration.program == self.program)

        self.first_reg: dict[int, date] = {}
        self.registration_rows = 0
        self.team_registration_rows = 0
        for person_id, reg_date in self.db.execute(query).all():
            self.registration_rows += 1
            if person_id is None:
                continue
            if person_id in self.team_ids:
                self.team_registration_rows += 1
                continue
            current = self.first_reg.get(person_id)
            if current is None or (reg_date and reg_date < current):
                self.first_reg[person_id] = reg_date
        self.registrants: set[int] = set(self.first_reg)

    def _load_calls(self) -> None:
        rows = self.db.execute(
            select(AiCall.person_id, AiCall.bot_name, AiCall.duration_s, AiCall.call_date).where(
                AiCall.client_id == self.client_id,
                AiCall.call_date >= self.date_from,
                AiCall.call_date <= self.date_to,
            )
        ).all()

        self.calls_placed = 0
        self.calls_connected = 0
        self.calls_reached = 0
        self.talk_seconds = 0
        self.billed_minutes = 0
        self.matched_calls = 0

        self.dialled: set[int] = set()
        self.connected: set[int] = set()
        self.reached: set[int] = set()
        self.bots: dict[str, BotStat] = {}
        self._call_durations: list[tuple[int | None, int]] = []
        self._reached_cache: dict[int, set[int]] = {}

        for person_id, bot_name, duration, call_date in rows:
            duration = int(duration or 0)
            self._call_durations.append((person_id, duration))
            name = bot_name or "(unnamed bot)"
            stat = self.bots.get(name)
            if stat is None:
                stat = self.bots[name] = BotStat(
                    name=name,
                    role=self.role_of(bot_name),
                    language=self.bot_languages.get(name),
                )

            self.calls_placed += 1
            stat.attempts += 1
            if call_date:
                stat.days_active.add(call_date)

            # Billing is per started minute, matching the client invoices.
            billed = -(-duration // 60) if duration else 0
            self.talk_seconds += duration
            self.billed_minutes += billed
            stat.talk_seconds += duration
            stat.billed_minutes += billed

            if duration > 0:
                self.calls_connected += 1
                stat.answered += 1
            if duration > self.reach_threshold_s:
                self.calls_reached += 1
                stat.reached_calls += 1

            if person_id is None:
                continue
            self.matched_calls += 1
            if person_id in self.team_ids:
                continue

            self.dialled.add(person_id)
            stat.people_dialled.add(person_id)
            if duration > 0:
                self.connected.add(person_id)
                stat.people_connected.add(person_id)
            if duration > self.reach_threshold_s:
                self.reached.add(person_id)
                stat.people_reached.add(person_id)

        self.talk_cost = round(self.billed_minutes * self.rate_per_min, 2)

    def _load_attendance(self) -> None:
        rows = self.db.execute(
            select(Attendance.person_id, Attendance.attended_on, Attendance.minutes_in_session).where(
                Attendance.client_id == self.client_id,
                Attendance.attended_on >= self.date_from,
                Attendance.attended_on <= self.date_to,
            )
        ).all()

        self.attended: set[int] = set()
        self.attended_by_day: dict[date, set[int]] = defaultdict(set)
        self.minutes_by_person: dict[int, float] = defaultdict(float)
        for person_id, day, minutes in rows:
            if person_id is None or person_id in self.team_ids:
                continue
            self.attended.add(person_id)
            if day:
                self.attended_by_day[day].add(person_id)
            if minutes:
                self.minutes_by_person[person_id] += float(minutes)

    def _load_sales(self) -> None:
        rows = self.db.execute(
            select(Sale.person_id, Sale.amount, Sale.sale_date, Sale.product,
                   Sale.payment_type).where(
                Sale.client_id == self.client_id,
                Sale.sale_date >= self.date_from,
                Sale.sale_date <= self.date_to,
            )
        ).all()
        self._sale_detail = rows

        self.buyers: set[int] = set()
        self.revenue_by_person: dict[int, float] = defaultdict(float)
        self.sale_rows = 0
        for person_id, amount, _day, _product, _ptype in rows:
            self.sale_rows += 1
            if person_id is None or person_id in self.team_ids:
                continue
            self.buyers.add(person_id)
            self.revenue_by_person[person_id] += float(amount or 0)

        self.revenue_total = round(sum(self.revenue_by_person.values()), 2)
        # Buyers who never appear in the registration list for this window.
        self.buyers_without_registration = self.buyers - self.registrants

        # Cash actually received, split the way the client workbooks split it.
        # ROI is priced on cash-per-sale rather than a headline programme price,
        # because deposits and instalments mean the two are rarely the same.
        self.orders_by_type: dict[str, dict] = {}
        for _pid, amount, _day, _product, payment_type in self._sale_detail:
            key = (payment_type or "unspecified").lower()
            bucket = self.orders_by_type.setdefault(key, {"orders": 0, "amount": 0.0})
            bucket["orders"] += 1
            bucket["amount"] += float(amount or 0)
        for bucket in self.orders_by_type.values():
            bucket["amount"] = round(bucket["amount"], 2)

    @property
    def cash_per_sale(self) -> float | None:
        """Total cash received divided by unique buyers."""
        return (self.revenue_total / len(self.buyers)) if self.buyers else None

    # ------------------------------------------------------------------ #
    # slicing
    # ------------------------------------------------------------------ #
    def people_for_roles(self, roles: tuple[str, ...], level: str = "reached") -> set[int]:
        """People touched by bots of the given roles, at the given contact level."""
        out: set[int] = set()
        for stat in self.bots.values():
            if stat.role not in roles:
                continue
            if level == "dialled":
                out |= stat.people_dialled
            elif level == "connected":
                out |= stat.people_connected
            else:
                out |= stat.people_reached
        return out

    def stat_for(self, label: str, people: set[int]) -> GroupStat:
        """Turn any set of people into a comparable row."""
        return GroupStat(
            label=label,
            people=len(people),
            registered=len(people & self.registrants),
            showed=len(people & self.attended),
            buyers=len(people & self.buyers),
            revenue=round(sum(self.revenue_by_person.get(p, 0.0) for p in people), 2),
        )

    def reached_at(self, threshold_s: int) -> set[int]:
        """People reached at an arbitrary threshold — used by the sensitivity check.

        Re-reads the call rows, because 'reached' at 30s is not derivable from
        the sets built at 15s.
        """
        cached = self._reached_cache.get(threshold_s)
        if cached is not None:
            return cached
        out: set[int] = set()
        for person_id, duration in self._call_durations:
            if person_id is not None and duration > threshold_s:
                out.add(person_id)
        out -= self.team_ids
        self._reached_cache[threshold_s] = out
        return out

    def billed_for_roles(self, roles: tuple[str, ...] | None = None) -> tuple[int, float]:
        """Billed minutes and cost for the bots that count against this report.

        `cost_bot_scope` decides whether a report is charged for every bot that
        ran in the window or only the ones it is measuring. Charging a webinar
        report for an unrelated re-engagement campaign makes the ROI meaningless,
        so the default is to bill only the bots in scope.
        """
        if roles is None:
            scope = self.params.get("cost_bot_scope", "signup_and_dayof")
            if scope == "all_bots":
                return self.billed_minutes, self.talk_cost
            roles = ("signup", "day_of")
        minutes = sum(b.billed_minutes for b in self.bots.values() if b.role in roles)
        return minutes, round(minutes * self.rate_per_min, 2)

    def bots_by_role(self, roles: tuple[str, ...]) -> list[BotStat]:
        return sorted(
            (b for b in self.bots.values() if b.role in roles),
            key=lambda b: -b.attempts,
        )

    @property
    def window_days(self) -> int:
        return (self.date_to - self.date_from).days + 1

    @property
    def event_days(self) -> list[date]:
        return sorted(self.attended_by_day)
