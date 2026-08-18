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
    ("raw_uploads", "blob_key", "VARCHAR(64)"),
    ("bots", "program", "VARCHAR(120)"),
    ("attendance", "program", "VARCHAR(80)"),
    ("sales", "program", "VARCHAR(80)"),
]


# Any constant will do; it only has to be the same in every instance so they
# queue behind each other rather than migrating at the same moment.
_MIGRATION_LOCK_KEY = 8_274_531


def _ensure_columns() -> None:
    """Add the columns listed above, and take no lock when there is nothing to do.

    `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` is a no-op logically but still
    takes an AccessExclusiveLock while Postgres evaluates it. Every cold start
    runs this, and a serverless host cold-starts constantly, so instances were
    deadlocking against each other's readers:

        Process A waits for AccessShareLock on attendance
        Process B waits for AccessExclusiveLock, blocked by A

    So the catalog is consulted first and the ALTER only runs when the column is
    genuinely missing — which is once, ever. The advisory lock then keeps two
    instances that both find work from doing it simultaneously.
    """
    prefix = f'"{DB_SCHEMA}".' if DB_SCHEMA else ""
    is_sqlite = DATABASE_URL.startswith("sqlite")

    with engine.begin() as conn:
        if is_sqlite:
            for table, column, ddl_type in _ADDED_COLUMNS:
                existing = {
                    row[1] for row in conn.execute(text(f'PRAGMA table_info("{table}")'))
                }
                if column not in existing:
                    conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {column} {ddl_type}'))
            return

        present = {
            (row[0], row[1])
            for row in conn.execute(
                text(
                    "SELECT table_name, column_name FROM information_schema.columns "
                    "WHERE table_schema = :schema"
                ),
                {"schema": DB_SCHEMA or "public"},
            )
        }
        missing = [c for c in _ADDED_COLUMNS if (c[0], c[1]) not in present]
        if not missing:
            return

        conn.execute(text("SELECT pg_advisory_xact_lock(:key)"),
                     {"key": _MIGRATION_LOCK_KEY})
        for table, column, ddl_type in missing:
            conn.execute(text(
                f'ALTER TABLE {prefix}"{table}" '
                f'ADD COLUMN IF NOT EXISTS {column} {ddl_type}'
            ))


def init_db() -> None:
    """Bring the database up to date. Safe to call from every instance at once.

    Each step checks before it writes, because this runs on every cold start and
    DDL that looks like a no-op still takes locks that readers then deadlock on.
    """
    from . import models  # noqa: F401  (register mappers)

    if DB_SCHEMA:
        with engine.begin() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :s"),
                {"s": DB_SCHEMA},
            ).first()
            if not exists:
                conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{DB_SCHEMA}"'))
    # checkfirst=True: inspects the catalog and emits CREATE only for tables
    # that are actually absent.
    Base.metadata.create_all(bind=engine, checkfirst=True)
    _ensure_columns()
