"""Value normalization shared by ingestion and the metrics engine."""
from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta

_NON_DIGIT = re.compile(r"\D+")
_MULTISPACE = re.compile(r"\s+")
_EXCEL_EPOCH = datetime(1899, 12, 30)

DATE_FORMATS = (
    "%d %b %Y, %I:%M %p",
    "%d %B %Y, %I:%M %p",
    "%d %b %Y %I:%M %p",
    "%d %b %Y",
    "%d %B %Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %I:%M %p",
    "%d/%m/%Y %I:%M:%S %p",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d-%m-%Y %H:%M:%S",
    # Day-first shapes are listed above month-first ones so an ambiguous date
    # like 05/06/2026 keeps its existing reading. Zoom exports are month-first
    # with a 12-hour clock, and without these every Zoom attendance row failed
    # to parse and was dropped in silence.
    "%m/%d/%Y %I:%M:%S %p",
    "%m/%d/%Y %I:%M %p",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y",
    "%d.%m.%Y",
    "%I:%M %p",
)


def norm_phone(value) -> str | None:
    """Indian-first phone normalization: keep the last 10 digits."""
    if value is None:
        return None
    if isinstance(value, float):
        if math.isnan(value):
            return None
        value = f"{value:.0f}"
    digits = _NON_DIGIT.sub("", str(value))
    if not digits:
        return None
    digits = digits.lstrip("0")
    if len(digits) > 10:
        digits = digits[-10:]
    if len(digits) < 8:
        return None
    return digits


def norm_email(value) -> str | None:
    if not value:
        return None
    text = str(value).strip().lower()
    if "@" not in text or " " in text:
        return None
    return text


def norm_name(value) -> str | None:
    if not value:
        return None
    text = _MULTISPACE.sub(" ", str(value)).strip().lower()
    text = re.sub(r"[^a-z0-9 ]", "", text)
    return text or None


def to_float(value) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    if cleaned in ("", "-", "."):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def to_int(value) -> int | None:
    val = to_float(value)
    return int(val) if val is not None else None


def to_datetime(value, time_value=None) -> datetime | None:
    """Parse Excel serials, datetimes and the many string shapes in this data."""
    dt = _parse_single(value)
    if dt is None:
        return None
    if time_value is not None and dt.hour == 0 and dt.minute == 0:
        frac = _time_fraction(time_value)
        if frac is not None:
            dt = dt + timedelta(seconds=round(frac * 86400))
    return dt


def _time_fraction(value) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        val = float(value)
        if 0 <= val < 1:
            return val
        if val >= 1:  # seconds-in-session style values
            return None
    if isinstance(value, str):
        parsed = _parse_single(value)
        if parsed is not None:
            return (parsed.hour * 3600 + parsed.minute * 60 + parsed.second) / 86400
    return None


def _parse_single(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        serial = float(value)
        if 20000 < serial < 80000:  # plausible Excel date serial
            return _EXCEL_EPOCH + timedelta(days=serial)
        return None
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d{4,6}(\.\d+)?", text):
        serial = float(text)
        if 20000 < serial < 80000:
            return _EXCEL_EPOCH + timedelta(days=serial)
    text = text.replace(",,", ",")
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
            if fmt == "%I:%M %p":
                return None
            return parsed
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def to_date(value, time_value=None) -> date | None:
    dt = to_datetime(value, time_value)
    return dt.date() if dt else None


def clean_str(value, limit: int | None = None) -> str | None:
    if value is None:
        return None
    text = _MULTISPACE.sub(" ", str(value)).strip()
    if not text:
        return None
    return text[:limit] if limit else text


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")
