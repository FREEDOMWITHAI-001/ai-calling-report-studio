"""Client (organisation) scoping.

Every route that touches client data goes through `require_client`. The rule is
deliberately strict:

* `client_id` is **required** — there is no "default client" and no fallback to
  the first row, because a fallback is how one org ends up looking at another
  org's numbers.
* A row fetched by its own id is only returned if it belongs to that client, so
  guessing `/api/reports/3` cannot leak another org's report.
* Nothing here ever creates a client. Clients are seeded deliberately
  (`scripts/seed_clients.py`), never conjured from a typo in a form field.

When login lands, `require_client` is the single place that also has to check the
signed-in user is a member of the requested org.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .db import get_db
from .models import Client


def require_client(
    client_id: int = Query(..., description="Organisation the request is scoped to"),
    db: Session = Depends(get_db),
) -> Client:
    """Resolve `?client_id=` to a real client, or refuse the request."""
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(404, f"No client with id {client_id}")
    return client


def resolve_client(db: Session, client_id: int | None) -> Client:
    """Body-supplied client id (POST payloads). Same rules, no query parameter."""
    if not client_id:
        raise HTTPException(422, "client_id is required — pick a client first")
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(404, f"No client with id {client_id}")
    return client


def owned(record, client_id: int, what: str = "Record"):
    """Return `record` only if it belongs to `client_id`.

    A row owned by another org is reported as missing rather than forbidden, so
    the response cannot be used to probe what other orgs have.
    """
    if record is None or getattr(record, "client_id", None) != client_id:
        raise HTTPException(404, f"{what} not found")
    return record
