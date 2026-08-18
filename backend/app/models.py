"""Normalized schema.

Every ingested file lands in a purpose-built table (registrations, ai_calls,
sales, attendance, webinar_daily) plus a generic key/value store for data types
that do not exist yet. People are resolved across all of them through the
`persons` table so a report can join registration -> calling -> attendance ->
sales for one human being.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .config import DB_SCHEMA
from .db import Base


def fk(target: str) -> str:
    """Schema-qualify a foreign key target when running on Postgres."""
    return f"{DB_SCHEMA}.{target}" if DB_SCHEMA else target


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# --------------------------------------------------------------------------- #
# Reference / dimension tables
# --------------------------------------------------------------------------- #
class Client(Base, TimestampMixin):
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    code: Mapped[str | None] = mapped_column(String(60))
    notes: Mapped[str | None] = mapped_column(Text)


class Event(Base, TimestampMixin):
    """A workshop / webinar occurrence (or a program-level bucket)."""

    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("client_id", "name", "event_date", name="uq_event"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey(fk("clients.id")), index=True)
    name: Mapped[str] = mapped_column(String(200))
    event_date: Mapped[date | None] = mapped_column(Date, index=True)
    language: Mapped[str | None] = mapped_column(String(40), index=True)
    program: Mapped[str | None] = mapped_column(String(80), index=True)

    client: Mapped[Client] = relationship()


class Bot(Base, TimestampMixin):
    __tablename__ = "bots"
    __table_args__ = (UniqueConstraint("client_id", "name", name="uq_bot"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey(fk("clients.id")), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    role: Mapped[str] = mapped_column(String(30), default="other")  # signup | day_of | other
    language: Mapped[str | None] = mapped_column(String(40))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Person(Base, TimestampMixin):
    """One human, resolved across every uploaded dataset."""

    __tablename__ = "persons"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey(fk("clients.id")), index=True)
    phone_norm: Mapped[str | None] = mapped_column(String(20), index=True)
    email_norm: Mapped[str | None] = mapped_column(String(200), index=True)
    name_norm: Mapped[str | None] = mapped_column(String(200), index=True)
    display_name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    is_team: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


# --------------------------------------------------------------------------- #
# Fact tables
# --------------------------------------------------------------------------- #
class Registration(Base, TimestampMixin):
    __tablename__ = "registrations"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey(fk("clients.id")), index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey(fk("events.id")), index=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey(fk("persons.id")), index=True)
    upload_id: Mapped[int | None] = mapped_column(ForeignKey(fk("raw_uploads.id")), index=True)

    name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    phone_norm: Mapped[str | None] = mapped_column(String(20), index=True)
    registered_at: Mapped[datetime | None] = mapped_column(DateTime)
    registration_date: Mapped[date | None] = mapped_column(Date, index=True)
    language: Mapped[str | None] = mapped_column(String(40), index=True)
    program: Mapped[str | None] = mapped_column(String(80), index=True)
    utm_source: Mapped[str | None] = mapped_column(String(120))
    utm_medium: Mapped[str | None] = mapped_column(String(200))
    utm_campaign: Mapped[str | None] = mapped_column(String(200))
    utm_content: Mapped[str | None] = mapped_column(String(300))
    utm_adname: Mapped[str | None] = mapped_column(String(300))
    salary_band: Mapped[str | None] = mapped_column(String(80))
    gender: Mapped[str | None] = mapped_column(String(30))
    row_hash: Mapped[str | None] = mapped_column(String(32), index=True)
    raw: Mapped[dict | None] = mapped_column(JSON)


class AiCall(Base, TimestampMixin):
    __tablename__ = "ai_calls"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey(fk("clients.id")), index=True)
    bot_id: Mapped[int | None] = mapped_column(ForeignKey(fk("bots.id")), index=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey(fk("persons.id")), index=True)
    upload_id: Mapped[int | None] = mapped_column(ForeignKey(fk("raw_uploads.id")), index=True)

    bot_name: Mapped[str | None] = mapped_column(String(200), index=True)
    contact_name: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    phone_norm: Mapped[str | None] = mapped_column(String(20), index=True)
    email: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str | None] = mapped_column(String(40), index=True)
    outcome: Mapped[str | None] = mapped_column(String(80))
    goal_outcome: Mapped[str | None] = mapped_column(String(120))
    interest_level: Mapped[str | None] = mapped_column(String(60))
    sentiment: Mapped[str | None] = mapped_column(String(60))
    lead_temperature: Mapped[str | None] = mapped_column(String(60))
    duration_s: Mapped[int] = mapped_column(Integer, default=0)
    turns: Mapped[int | None] = mapped_column(Integer)
    red_flags: Mapped[str | None] = mapped_column(String(60))
    summary: Mapped[str | None] = mapped_column(Text)
    transcript: Mapped[str | None] = mapped_column(Text)
    recording_url: Mapped[str | None] = mapped_column(Text)
    call_sid: Mapped[str | None] = mapped_column(String(80), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    source_created_at: Mapped[datetime | None] = mapped_column(DateTime)
    call_date: Mapped[date | None] = mapped_column(Date, index=True)
    row_hash: Mapped[str | None] = mapped_column(String(32), index=True)
    raw: Mapped[dict | None] = mapped_column(JSON)


class Sale(Base, TimestampMixin):
    __tablename__ = "sales"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey(fk("clients.id")), index=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey(fk("persons.id")), index=True)
    upload_id: Mapped[int | None] = mapped_column(ForeignKey(fk("raw_uploads.id")), index=True)

    name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    phone_norm: Mapped[str | None] = mapped_column(String(20), index=True)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime)
    sale_date: Mapped[date | None] = mapped_column(Date, index=True)
    product: Mapped[str | None] = mapped_column(String(120), index=True)   # e.g. "L1 English"
    payment_type: Mapped[str | None] = mapped_column(String(40))           # full | lock | balance
    payment_id: Mapped[str | None] = mapped_column(String(120))
    payment_status: Mapped[str | None] = mapped_column(String(60))
    language: Mapped[str | None] = mapped_column(String(40), index=True)
    row_hash: Mapped[str | None] = mapped_column(String(32), index=True)
    raw: Mapped[dict | None] = mapped_column(JSON)


class Attendance(Base, TimestampMixin):
    """Zoom / webinar attendance rows ("English Number Fetch")."""

    __tablename__ = "attendance"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey(fk("clients.id")), index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey(fk("events.id")), index=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey(fk("persons.id")), index=True)
    upload_id: Mapped[int | None] = mapped_column(ForeignKey(fk("raw_uploads.id")), index=True)

    name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    phone_norm: Mapped[str | None] = mapped_column(String(20), index=True)
    attended_on: Mapped[date | None] = mapped_column(Date, index=True)
    minutes_in_session: Mapped[float | None] = mapped_column(Float)
    language: Mapped[str | None] = mapped_column(String(40), index=True)
    row_hash: Mapped[str | None] = mapped_column(String(32), index=True)
    raw: Mapped[dict | None] = mapped_column(JSON)


class WebinarDaily(Base, TimestampMixin):
    """Platform's own daily counts, used only for reconciliation."""

    __tablename__ = "webinar_daily"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey(fk("clients.id")), index=True)
    upload_id: Mapped[int | None] = mapped_column(ForeignKey(fk("raw_uploads.id")), index=True)
    day: Mapped[date | None] = mapped_column(Date, index=True)
    language: Mapped[str | None] = mapped_column(String(40), index=True)
    leads: Mapped[int | None] = mapped_column(Integer)
    show_up: Mapped[int | None] = mapped_column(Integer)
    attendees_at_pitch: Mapped[int | None] = mapped_column(Integer)
    total_sale: Mapped[float | None] = mapped_column(Float)
    total_lock: Mapped[float | None] = mapped_column(Float)
    row_hash: Mapped[str | None] = mapped_column(String(32), index=True)
    raw: Mapped[dict | None] = mapped_column(JSON)


# --------------------------------------------------------------------------- #
# Generic store for data types that do not have a first-class table yet
# --------------------------------------------------------------------------- #
class GenericDataset(Base, TimestampMixin):
    __tablename__ = "generic_datasets"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey(fk("clients.id")), index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    columns: Mapped[list | None] = mapped_column(JSON)
    row_count: Mapped[int] = mapped_column(Integer, default=0)


class GenericRecord(Base):
    __tablename__ = "generic_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey(fk("generic_datasets.id")), index=True)
    upload_id: Mapped[int | None] = mapped_column(ForeignKey(fk("raw_uploads.id")), index=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey(fk("persons.id")), index=True)
    row_date: Mapped[date | None] = mapped_column(Date, index=True)
    row_hash: Mapped[str | None] = mapped_column(String(32), index=True)
    data: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# --------------------------------------------------------------------------- #
# Operational tables
# --------------------------------------------------------------------------- #
class FileBlob(Base):
    """Durable bytes for an uploaded or generated file.

    The filesystem is a cache, not the record. On a serverless host every
    request may land on a fresh instance with an empty disk, so anything that
    must outlive a single request is kept here and materialized back to a local
    path on demand (see `app.storage`).
    """

    __tablename__ = "file_blobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(400))
    content_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RawUpload(Base):
    __tablename__ = "raw_uploads"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(400))
    stored_path: Mapped[str] = mapped_column(Text)
    blob_key: Mapped[str | None] = mapped_column(String(64), index=True)
    content_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    sheet_name: Mapped[str | None] = mapped_column(String(200))
    dataset_type: Mapped[str | None] = mapped_column(String(60), index=True)
    generic_dataset_name: Mapped[str | None] = mapped_column(String(120))
    client_id: Mapped[int | None] = mapped_column(ForeignKey(fk("clients.id")), index=True)
    mapping: Mapped[dict | None] = mapped_column(JSON)
    options: Mapped[dict | None] = mapped_column(JSON)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    inserted_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    error_detail: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[str | None] = mapped_column(String(120), default="local")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class MappingTemplate(Base, TimestampMixin):
    """Remembers 'these headers mean this' so repeat uploads are one click."""

    __tablename__ = "mapping_templates"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    dataset_type: Mapped[str] = mapped_column(String(60), index=True)
    signature: Mapped[str] = mapped_column(String(64), index=True)
    mapping: Mapped[dict] = mapped_column(JSON)
    use_count: Mapped[int] = mapped_column(Integer, default=0)


class MethodologyConfig(Base, TimestampMixin):
    __tablename__ = "methodology_configs"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    params: Mapped[dict] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(Text)


class ReportFormat(Base, TimestampMixin):
    """A client's own report format.

    `base_key` names the built-in layout it starts from; `spec` overrides the
    section list, brand and output formats. One format per client is the
    default, and that is what a report uses when none is chosen explicitly —
    which is what "each client has their own format" means in practice.
    """

    __tablename__ = "report_formats"
    __table_args__ = (UniqueConstraint("client_id", "key", name="uq_report_format"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey(fk("clients.id")), index=True)
    key: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(160))
    base_key: Mapped[str] = mapped_column(String(60), default="bootcamp")
    description: Mapped[str | None] = mapped_column(Text)
    spec: Mapped[dict | None] = mapped_column(JSON)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class ReportRun(Base):
    __tablename__ = "report_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(240))
    client_id: Mapped[int | None] = mapped_column(ForeignKey(fk("clients.id")), index=True)
    methodology_id: Mapped[int | None] = mapped_column(ForeignKey(fk("methodology_configs.id")))
    # Which format produced this run. A first-class column rather than a key
    # buried in `filters`, so history can be read and filtered by format.
    template_key: Mapped[str | None] = mapped_column(String(60), index=True)
    template_label: Mapped[str | None] = mapped_column(String(160))
    date_from: Mapped[date] = mapped_column(Date, index=True)
    date_to: Mapped[date] = mapped_column(Date, index=True)
    filters: Mapped[dict | None] = mapped_column(JSON)
    formats: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    error_detail: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[dict | None] = mapped_column(JSON)
    files: Mapped[list | None] = mapped_column(JSON)
    generated_by: Mapped[str | None] = mapped_column(String(120), default="local")
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


Index("ix_calls_bot_date", AiCall.bot_name, AiCall.call_date)
Index("ix_reg_client_date", Registration.client_id, Registration.registration_date)
