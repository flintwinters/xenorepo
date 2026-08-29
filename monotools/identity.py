"""Define canonical identity schemas for independent monoapp databases.

Applications selectively install account, identifier, credential, session, and
realtime tables while these operations preserve shared identity invariants.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import hmac
import secrets
from typing import Iterable
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, MetaData, String, Table, or_, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from monotools.auth import issue_opaque_credential, opaque_credential_digest


class MonotoolsBase(DeclarativeBase):
    """One registry for concrete, selectively installed Monotools tables."""


class Account(MonotoolsBase):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class AccountHandle(MonotoolsBase):
    __tablename__ = "account_handles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    canonical_handle: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class AccountName(MonotoolsBase):
    __tablename__ = "account_names"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(255), index=True)
    first_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class AccountEmail(MonotoolsBase):
    __tablename__ = "account_emails"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    normalized_address: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class PasswordCredential(MonotoolsBase):
    __tablename__ = "password_credentials"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    digest: Mapped[bytes] = mapped_column(LargeBinary)
    salt: Mapped[bytes] = mapped_column(LargeBinary)
    work_n: Mapped[int] = mapped_column(Integer)
    work_r: Mapped[int] = mapped_column(Integer)
    work_p: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class AuthenticationSession(MonotoolsBase):
    __tablename__ = "authentication_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    credential_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    client_host: Mapped[str | None] = mapped_column(String(255))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    origin: Mapped[str | None] = mapped_column(String(500))


class RealtimeConnection(MonotoolsBase):
    __tablename__ = "realtime_connections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), index=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    client_host: Mapped[str | None] = mapped_column(String(255))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    origin: Mapped[str | None] = mapped_column(String(500))


@dataclass(frozen=True)
class SchemaGroup:
    """A named maximal table set with explicit group dependencies."""

    name: str
    models: tuple[type[MonotoolsBase], ...]
    dependencies: frozenset[str] = frozenset()

    @property
    def tables(self) -> tuple[Table, ...]:
        return tuple(model.__table__ for model in self.models)


SCHEMA_GROUPS = {
    group.name: group for group in (
        SchemaGroup("identity", (Account,)),
        SchemaGroup("identity-handles", (AccountHandle,), frozenset({"identity"})),
        SchemaGroup("identity-names", (AccountName,), frozenset({"identity"})),
        SchemaGroup("identity-emails", (AccountEmail,), frozenset({"identity"})),
        SchemaGroup("identity-passwords", (PasswordCredential,), frozenset({"identity"})),
        SchemaGroup("identity-sessions", (AuthenticationSession,), frozenset({"identity"})),
        SchemaGroup("realtime-records", (RealtimeConnection,), frozenset({"identity"})),
    )
}


@dataclass(frozen=True)
class DatabaseSchema:
    """Validated platform capabilities plus explicitly app-owned tables."""

    groups: frozenset[str]
    domain_tables: tuple[Table, ...] = ()

    def __init__(self, groups: Iterable[str], domain_tables: Iterable[Table] = ()) -> None:
        selected = frozenset(groups)
        unknown = selected - SCHEMA_GROUPS.keys()
        if unknown:
            raise ValueError(f"unknown database schema group(s): {', '.join(sorted(unknown))}")
        missing = {dependency for name in selected
            for dependency in SCHEMA_GROUPS[name].dependencies if dependency not in selected}
        if missing:
            raise ValueError(f"database schema is missing dependencies: {', '.join(sorted(missing))}")
        object.__setattr__(self, "groups", selected)
        object.__setattr__(self, "domain_tables", tuple(domain_tables))

    @property
    def metadata(self) -> MetaData:
        return MonotoolsBase.metadata

    @property
    def tables(self) -> tuple[Table, ...]:
        platform = tuple(table for name, group in SCHEMA_GROUPS.items()
            if name in self.groups for table in group.tables)
        return tuple(dict.fromkeys((*platform, *self.domain_tables)))


@dataclass(frozen=True)
class PasswordHash:
    digest: bytes
    salt: bytes
    version: int = 1
    work_n: int = 2**14
    work_r: int = 8
    work_p: int = 1


def hash_password(password: str, *, salt: bytes | None = None,
    work_n: int = 2**14, work_r: int = 8, work_p: int = 1) -> PasswordHash:
    """Create the canonical versioned scrypt verifier; never retain plaintext."""
    if not password:
        raise ValueError("password must not be empty")
    resolved_salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=resolved_salt,
        n=work_n, r=work_r, p=work_p)
    return PasswordHash(digest, resolved_salt, 1, work_n, work_r, work_p)


def verify_password(password: str, credential: PasswordCredential | PasswordHash) -> bool:
    """Compare a password with a supported credential without leaking timing."""
    if credential.version != 1:
        return False
    candidate = hashlib.scrypt(password.encode(), salt=credential.salt,
        n=credential.work_n, r=credential.work_r, p=credential.work_p)
    return hmac.compare_digest(candidate, credential.digest)


def create_account(session: Session, at: datetime, *, account_id: str | None = None) -> Account:
    account = Account(id=account_id or str(uuid4()), created_at=at, updated_at=at,
        last_seen_at=None, disabled_at=None)
    session.add(account)
    return account


def add_handle(session: Session, account_id: str, canonical_handle: str,
    at: datetime) -> AccountHandle:
    return _add_identifier(session, AccountHandle, account_id, at,
        canonical_handle=canonical_handle, created_at=at)


def add_name(session: Session, account_id: str, display_name: str,
    at: datetime) -> AccountName:
    return _add_identifier(session, AccountName, account_id, at,
        display_name=display_name, first_used_at=at, last_used_at=at)


def add_email(session: Session, account_id: str, normalized_address: str,
    at: datetime) -> AccountEmail:
    return _add_identifier(session, AccountEmail, account_id, at,
        normalized_address=normalized_address, created_at=at, verified_at=None)


def _add_identifier(session: Session, model: type[MonotoolsBase], account_id: str,
    at: datetime, **values: object):
    session.execute(model.__table__.update().where(
        model.__table__.c.account_id == account_id,
        model.__table__.c.retired_at.is_(None)).values(retired_at=at))
    record = model(id=str(uuid4()), account_id=account_id, retired_at=None, **values)
    session.add(record)
    return record


def set_password(session: Session, account_id: str, password: str,
    at: datetime) -> PasswordCredential:
    secured = hash_password(password)
    session.execute(PasswordCredential.__table__.update().where(
        PasswordCredential.account_id == account_id,
        PasswordCredential.retired_at.is_(None)).values(retired_at=at))
    credential = PasswordCredential(id=str(uuid4()), account_id=account_id,
        version=secured.version, digest=secured.digest, salt=secured.salt,
        work_n=secured.work_n, work_r=secured.work_r, work_p=secured.work_p,
        created_at=at, retired_at=None)
    session.add(credential)
    return credential


def issue_session(session: Session, account_id: str, at: datetime,
    *, lifetime: timedelta | None, provenance: dict[str, str | None] | None = None,
    session_id: str | None = None) -> tuple[AuthenticationSession, str]:
    raw = issue_opaque_credential()
    record = AuthenticationSession(id=session_id or str(uuid4()), account_id=account_id,
        credential_digest=opaque_credential_digest(raw), issued_at=at,
        expires_at=at + lifetime if lifetime is not None else None, last_seen_at=None,
        revoked_at=None, **(provenance or {}))
    session.add(record)
    return record, raw


def resolve_session(session: Session, raw_credential: str, at: datetime,
    *, touch: bool = True) -> AuthenticationSession | None:
    record = session.scalar(select(AuthenticationSession).where(
        AuthenticationSession.credential_digest == opaque_credential_digest(raw_credential),
        AuthenticationSession.revoked_at.is_(None),
        or_(AuthenticationSession.expires_at.is_(None), AuthenticationSession.expires_at > at)))
    if record is None:
        return None
    if touch:
        record.last_seen_at = at
    return record


def revoke_session(session: Session, raw_credential: str, at: datetime) -> bool:
    record = session.scalar(select(AuthenticationSession).where(
        AuthenticationSession.credential_digest == opaque_credential_digest(raw_credential)))
    if record is None or record.revoked_at is not None:
        return False
    record.revoked_at = at
    return True
