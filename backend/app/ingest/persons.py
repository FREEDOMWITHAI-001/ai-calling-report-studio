"""Cross-dataset person resolution.

The reference reports match people by phone OR email OR name, and count someone
who registered twice under two numbers only once. This resolver does the same,
holding an in-memory index for the duration of one ingestion or report run.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Person
from ..util.normalize import norm_email, norm_name, norm_phone


class PersonResolver:
    def __init__(self, db: Session, client_id: int, team_email_domains=None,
                 team_name_patterns=None, team_phones=None):
        self.db = db
        self.client_id = client_id
        self.team_email_domains = [d.lower() for d in (team_email_domains or [])]
        self.team_name_patterns = [p.lower() for p in (team_name_patterns or [])]
        self.team_phones = {norm_phone(p) for p in (team_phones or []) if norm_phone(p)}
        self._by_phone: dict[str, Person] = {}
        self._by_email: dict[str, Person] = {}
        self._by_name: dict[str, Person] = {}
        self._pending: list[Person] = []
        self._load()

    def _load(self) -> None:
        rows = self.db.execute(
            select(Person).where(Person.client_id == self.client_id)
        ).scalars().all()
        for person in rows:
            self._index(person)

    def _index(self, person: Person) -> None:
        if person.phone_norm:
            self._by_phone.setdefault(person.phone_norm, person)
        if person.email_norm:
            self._by_email.setdefault(person.email_norm, person)
        if person.name_norm:
            self._by_name.setdefault(person.name_norm, person)

    def is_team(self, name, email, phone) -> bool:
        email_n = norm_email(email)
        if email_n:
            domain = email_n.split("@")[-1]
            if domain in self.team_email_domains:
                return True
        name_n = (str(name).lower() if name else "")
        for pattern in self.team_name_patterns:
            if pattern and pattern in name_n:
                return True
        phone_n = norm_phone(phone)
        return bool(phone_n and phone_n in self.team_phones)

    def resolve(self, name=None, email=None, phone=None, create: bool = True) -> Person | None:
        """Find (or create) the person these identifiers point at.

        Phone wins over email, email over name — the same precedence the reports
        use. Whichever identifiers were missing on the stored person get filled
        in, so later files can match on any of them.
        """
        phone_n = norm_phone(phone)
        email_n = norm_email(email)
        name_n = norm_name(name)
        if not (phone_n or email_n or name_n):
            return None

        person = None
        if phone_n:
            person = self._by_phone.get(phone_n)
        if person is None and email_n:
            person = self._by_email.get(email_n)
        if person is None and name_n and not phone_n:
            # Name is the last resort, and only when the row carries no usable
            # phone number to contradict it. Attendance exports are the real
            # case: they often show "Not Found" for the number and a platform
            # alias for the email, leaving the name as the only handle. Rows
            # that *do* have a phone are never merged on name alone — that
            # would fuse two different people who share a common name.
            person = self._by_name.get(name_n)

        if person is None:
            if not create:
                return None
            person = Person(
                client_id=self.client_id,
                phone_norm=phone_n,
                email_norm=email_n,
                name_norm=name_n,
                display_name=str(name).strip() if name else None,
                email=str(email).strip() if email else None,
                phone=str(phone).strip() if phone else None,
                is_team=self.is_team(name, email, phone),
            )
            self.db.add(person)
            self._pending.append(person)
            self._index(person)
            return person

        changed = False
        if phone_n and not person.phone_norm:
            person.phone_norm, person.phone, changed = phone_n, str(phone).strip(), True
            self._by_phone.setdefault(phone_n, person)
        if email_n and not person.email_norm:
            person.email_norm, person.email, changed = email_n, str(email).strip(), True
            self._by_email.setdefault(email_n, person)
        if name_n and not person.name_norm:
            person.name_norm, changed = name_n, True
            person.display_name = person.display_name or (str(name).strip() if name else None)
            self._by_name.setdefault(name_n, person)
        if not person.is_team and self.is_team(name, email, phone):
            person.is_team, changed = True, True
        if changed:
            self.db.add(person)
        return person

    def flush(self) -> None:
        """Assign primary keys to newly created people."""
        if self._pending:
            self.db.flush()
            self._pending.clear()
