from __future__ import annotations

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL, DB_SCHEMA

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    metadata = MetaData(schema=DB_SCHEMA)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added to tables that already exist. `create_all` creates missing
# tables but never alters existing ones, so each new column is listed here with
# the DDL to add it. Every statement is IF NOT EXISTS and safe to re-run.
_ADDED_COLUMNS: list[tuple[str, str, str]] = [
    ("report_runs", "template_key", "VARCHAR(60)"),
    ("report_runs", "template_label", "VARCHAR(160)"),
]


def _ensure_columns() -> None:
    prefix = f'"{DB_SCHEMA}".' if DB_SCHEMA else ""
    is_sqlite = DATABASE_URL.startswith("sqlite")
    with engine.begin() as conn:
        for table, column, ddl_type in _ADDED_COLUMNS:
            if is_sqlite:
                existing = {
                    row[1] for row in conn.execute(text(f'PRAGMA table_info("{table}")'))
                }
                if column in existing:
                    continue
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {column} {ddl_type}'))
            else:
                conn.execute(text(
                    f'ALTER TABLE {prefix}"{table}" '
                    f'ADD COLUMN IF NOT EXISTS {column} {ddl_type}'
                ))


def init_db() -> None:
    from . import models  # noqa: F401  (register mappers)

    if DB_SCHEMA:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{DB_SCHEMA}"'))
    Base.metadata.create_all(bind=engine)
    _ensure_columns()
