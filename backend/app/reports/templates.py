"""Report formats, one per client style.

A template is an ordered list of sections plus presentation settings. That is the
whole of "each client has their own report format" — no client gets bespoke
computation or bespoke rendering.

Built-in templates below are the starting point; `report_templates` rows in the
database override or extend them per client, so a format can be changed without
a deploy.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Brand:
    """Presentation only. Never affects a number."""
    accent: str = "5B3FE8"
    ink: str = "16141F"
    muted: str = "6B6683"
    rule: str = "E5E2F0"
    band: str = "F7F6FC"
    positive: str = "0E8F6A"
    negative: str = "CF2740"
    baseline: str = "FBEED2"
    logo_path: str | None = None
    footer: str | None = None


@dataclass
class SectionRef:
    """A section in a template, optionally reconfigured."""
    key: str
    title: str | None = None
    config: dict = field(default_factory=dict)


@dataclass
class Template:
    key: str
    label: str
    description: str
    sections: list[SectionRef]
    formats: list[str] = field(default_factory=lambda: ["xlsx", "pdf"])
    brand: Brand = field(default_factory=Brand)
    cover_title: str | None = None
    # Most formats open on a cover sheet. CoachEasily's workbook is two sheets
    # exactly, so it turns the cover off rather than gaining a third.
    cover: bool = True


# ------------------------------------------------------------------ #
# Built-in formats
# ------------------------------------------------------------------ #

BOOTCAMP = Template(
    key="bootcamp",
    label="Bootcamp — AI calling impact",
    description=(
        "The DVA layout. Five sections: headline, sign-up by bot, show-up uplift with a "
        "day-by-day breakdown, sales with the conservative valuation, and the named buyer list."
    ),
    cover_title="What AI calling added",
    sections=[
        SectionRef("headline", title="1. Overall"),
        SectionRef("call_funnel", title="1b. Funnel"),
        SectionRef("signup_by_bot", title="2. Sign-up",
                   config={"roles": ["signup", "day_of", "other"]}),
        SectionRef("showup_uplift", title="3. Show-up",
                   config={"roles": ["day_of", "signup"], "scope": "dialled"}),
        SectionRef("showup_by_day", title="3b. Show-up by day",
                   config={"roles": ["day_of", "signup"]}),
        SectionRef("rescue_campaign", title="3c. Rescue campaign"),
        SectionRef("per_campaign", title="3d. Per campaign",
                   config={"metric": "showed"}),
        SectionRef("sales_uplift", title="4. Sales"),
        SectionRef("money_received", title="4b. Money received"),
        SectionRef("cost", title="4c. Cost"),
        SectionRef("seat_value_roi", title="4d. Conservative ROI"),
        SectionRef("confidence", title="4e. How solid is it"),
        SectionRef("buyers", title="5. People (buyers)"),
        SectionRef("methodology", title="6. Method"),
    ],
    formats=["xlsx", "pdf"],
)

WEBINAR = Template(
    key="webinar",
    label="Standard — AI calling impact",
    description=(
        "The common format. Everything computable from the four standard inputs: "
        "registrations, AI calls, sales and Zoom attendance. Registration-scoped show-up "
        "and sales uplift, the step-by-step ROI derivation, a confidence band and a "
        "sensitivity check. This is the default for any client without a format of its own."
    ),
    cover_title="What AI calling added",
    sections=[
        SectionRef("headline", title="1. Overall"),
        SectionRef("call_funnel", title="1b. Funnel"),
        SectionRef("signup_by_bot", title="2. Sign-up"),
        SectionRef("showup_uplift", title="3. Show-up",
                   config={"roles": ["signup", "day_of"], "scope": "registrants"}),
        SectionRef("showup_by_day", title="3b. Show-up by day"),
        SectionRef("per_campaign", title="3c. Per campaign", config={"metric": "showed"}),
        SectionRef("sales_uplift", title="4. Sales & ROI"),
        SectionRef("money_received", title="4b. Money received"),
        SectionRef("cost", title="4c. Cost"),
        SectionRef("roi_derivation", title="4d. ROI derivation"),
        SectionRef("confidence", title="4e. How solid is it"),
        SectionRef("sensitivity", title="4f. Sensitivity"),
        SectionRef("buyers", title="5. People (buyers)"),
        SectionRef("methodology", title="6. Method"),
    ],
    formats=["xlsx", "pdf"],
)

# The full CBH format, including the sections that need a supplied lead list.
# They render as "unavailable, and why" until that list is uploaded.
LEAD_LIST = Template(
    key="lead_list",
    label="Lead list — called vs not called",
    description=(
        "The full CBH layout. Adds the four boxes and the lead-list registration uplift, "
        "which need the supplied lead list as a fifth input."
    ),
    cover_title="What AI calling added",
    sections=[
        SectionRef("headline", title="1. Leads"),
        SectionRef("call_funnel", title="1b. Funnel"),
        SectionRef("signup_uplift", title="2. Registrations"),
        SectionRef("signup_by_bot", title="2b. Sign-up by bot"),
        SectionRef("showup_uplift", title="3. Show-up",
                   config={"roles": ["signup", "day_of"], "scope": "registrants"}),
        SectionRef("showup_by_day", title="3b. Show-up by day"),
        SectionRef("per_campaign", title="3c. Per campaign", config={"metric": "showed"}),
        SectionRef("sales_uplift", title="4. Sales & ROI"),
        SectionRef("money_received", title="4b. Money received"),
        SectionRef("cost", title="4c. Cost"),
        SectionRef("roi_derivation", title="4d. ROI derivation"),
        SectionRef("confidence", title="4e. How solid is it"),
        SectionRef("sensitivity", title="4f. Sensitivity"),
        SectionRef("buyers", title="5. People (buyers)"),
        SectionRef("methodology", title="6. Method"),
    ],
    formats=["xlsx", "pdf"],
)

COACHEASILY_GENERAL = Template(
    key="coacheasily_general",
    label="CoachEasily General",
    description=(
        "The CoachEasily workbook: an Overview that shows how the AI-credited sales and the "
        "ROI are derived, and a per-programme report giving show-up and buyers by bot for the "
        "whole window and then for each call day. Two sheets, no cover."
    ),
    cover_title=None,
    cover=False,
    formats=["xlsx"],
    sections=[
        SectionRef("coacheasily_overview", title="Overview"),
        SectionRef("coacheasily_report", title="CBA X report"),
    ],
)

BUILT_IN: dict[str, Template] = {
    t.key: t for t in (BOOTCAMP, WEBINAR, LEAD_LIST, COACHEASILY_GENERAL)
}

DEFAULT_TEMPLATE_KEY = "webinar"   # the common format


def get_template(key: str | None) -> Template:
    return BUILT_IN.get(key or DEFAULT_TEMPLATE_KEY, BUILT_IN[DEFAULT_TEMPLATE_KEY])


def from_record(record) -> Template:
    """Build a Template from a `report_templates` row.

    The row stores the section list and brand as JSON, so a client's format can be
    edited in the UI without touching code.
    """
    base = get_template(record.base_key)
    spec = record.spec or {}
    sections = [
        SectionRef(key=s["key"], title=s.get("title"), config=s.get("config") or {})
        for s in spec.get("sections", [])
    ] or base.sections
    brand_spec = spec.get("brand") or {}
    brand = Brand(**{k: v for k, v in brand_spec.items() if k in Brand.__dataclass_fields__})
    return Template(
        key=record.key,
        label=record.name,
        description=record.description or base.description,
        sections=sections,
        formats=spec.get("formats") or base.formats,
        brand=brand,
        cover_title=spec.get("cover_title") or base.cover_title,
        cover=spec.get("cover", base.cover),
    )


def resolve_for_client(db, client_id: int, requested: str | None) -> Template:
    """Which format this report should use.

    Order of preference:
      1. a format key the caller asked for, belonging to this client
      2. a built-in key the caller asked for
      3. the client's own default format
      4. the built-in default

    A format defined for one client is never reachable from another — the lookup
    is always filtered by client_id.
    """
    from sqlalchemy import select

    from ..models import ReportFormat

    def own(key: str | None):
        if not key:
            return None
        return db.execute(
            select(ReportFormat).where(
                ReportFormat.client_id == client_id, ReportFormat.key == key
            )
        ).scalars().first()

    record = own(requested)
    if record:
        return from_record(record)
    if requested and requested in BUILT_IN:
        return BUILT_IN[requested]

    default = db.execute(
        select(ReportFormat).where(
            ReportFormat.client_id == client_id, ReportFormat.is_default.is_(True)
        )
    ).scalars().first()
    if default:
        return from_record(default)
    return BUILT_IN[DEFAULT_TEMPLATE_KEY]


def describe_all() -> list[dict]:
    return [
        {
            "key": t.key,
            "label": t.label,
            "description": t.description,
            "formats": t.formats,
            "sections": [{"key": s.key, "title": s.title} for s in t.sections],
        }
        for t in BUILT_IN.values()
    ]
