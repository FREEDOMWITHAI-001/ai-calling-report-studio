from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    dataset_type: str = "custom"
    sheet: str | None = None
    mapping: dict[str, str | None] = Field(default_factory=dict)
    # No client field: the target org is fixed on the upload row at upload time.
    language: str | None = None
    program: str | None = None
    product: str | None = None
    payment_type: str | None = None
    generic_dataset_name: str | None = None
    skip_duplicates: bool = True
    keep_raw: bool = True
    keep_transcripts: bool = True
    save_template_as: str | None = None


class UploadOut(BaseModel):
    id: int
    filename: str
    sheet_name: str | None = None
    dataset_type: str | None = None
    generic_dataset_name: str | None = None
    row_count: int = 0
    inserted_count: int = 0
    skipped_count: int = 0
    status: str
    error_detail: str | None = None
    uploaded_by: str | None = None
    uploaded_at: datetime | None = None
    finished_at: datetime | None = None
    size_bytes: int | None = None
    # Returned so re-opening an upload can restore the choices it was loaded
    # with. Without them a re-ingest silently drops the language and programme
    # the first run was given.
    mapping: dict | None = None
    options: dict | None = None

    class Config:
        from_attributes = True


class BotOut(BaseModel):
    id: int
    name: str
    role: str
    program: str | None = None
    language: str | None = None
    active: bool = True

    class Config:
        from_attributes = True


class BotUpdate(BaseModel):
    role: str | None = None
    # "" clears the programme; None leaves it alone.
    program: str | None = None
    active: bool | None = None
    language: str | None = None


class MethodologyIn(BaseModel):
    name: str
    params: dict[str, Any]
    description: str | None = None
    is_default: bool = False


class MethodologyOut(BaseModel):
    id: int
    name: str
    is_default: bool
    params: dict[str, Any]
    description: str | None = None

    class Config:
        from_attributes = True


class ReportRequest(BaseModel):
    title: str | None = None
    client_id: int | None = None
    # Which client format to render. Left unset, the client's own default
    # format is used. Set `use_template=False` to fall back to the original
    # webinar-uplift report instead.
    template: str | None = None
    use_template: bool = True
    date_from: date
    date_to: date
    formats: list[str] = Field(default_factory=lambda: ["xlsx", "pdf", "pptx"])
    language: str | None = None
    program: str | None = None
    product: str | None = None
    bot_names: list[str] | None = None
    methodology_id: int | None = None
    params_override: dict[str, Any] | None = None


class BatchReportRequest(BaseModel):
    ranges: list[ReportRequest]


class ReportOut(BaseModel):
    id: int
    title: str
    date_from: date
    date_to: date
    template_key: str | None = None
    template_label: str | None = None
    formats: list[str] | None = None
    status: str
    error_detail: str | None = None
    files: list[dict] | None = None
    generated_at: datetime | None = None
    finished_at: datetime | None = None
    filters: dict | None = None

    class Config:
        from_attributes = True
