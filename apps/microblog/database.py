"""Normalized SQLAlchemy persistence and domain operations for WIRE/98."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, aliased, mapped_column, sessionmaker

from apps.microblog.auth import PasswordHash, hash_password, normalize_handle, token_digest, verify_password
from monotools.database import ClientProvenanceMixin
from monotools.database import create_session_factory as shared_session_factory
from monotools.database import sqlite_url


SESSION_LIFETIME = timedelta(days=30)


def now() -> datetime:
    return datetime.now(timezone.utc)


def utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class DomainError(ValueError):
    def __init__(self, message: str, kind: str = "validation") -> None:
        super().__init__(message)
        self.kind = kind


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    handle: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PasswordCredential(Base):
    __tablename__ = "password_credentials"
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
    digest: Mapped[bytes] = mapped_column(LargeBinary)
    salt: Mapped[bytes] = mapped_column(LargeBinary)
    work_n: Mapped[int] = mapped_column(Integer)
    work_r: Mapped[int] = mapped_column(Integer)
    work_p: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuthenticationSession(ClientProvenanceMixin, Base):
    __tablename__ = "authentication_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (CheckConstraint("length(body) BETWEEN 1 AND 280", name="post_body_length"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class LikeEvent(Base):
    __tablename__ = "like_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    liked: Mapped[bool] = mapped_column(Boolean)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    return shared_session_factory(database_url, Base.metadata)


class MicroblogRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def register(self, handle: str, password: str) -> Account:
        normalized, secured, timestamp = normalize_handle(handle), hash_password(password), now()
        account = Account(id=str(uuid4()), handle=normalized, created_at=timestamp)
        try:
            with self.sessions.begin() as session:
                session.add(account)
                session.flush()
                session.add(PasswordCredential(account_id=account.id, version=secured.version,
                    digest=secured.digest, salt=secured.salt, work_n=secured.n,
                    work_r=secured.r, work_p=secured.p, created_at=timestamp))
        except IntegrityError as error:
            raise DomainError("Handle is already registered.", "conflict") from error
        return account

    def verify_login(self, handle: str, password: str) -> Account | None:
        try:
            normalized = normalize_handle(handle)
        except ValueError:
            return None
        with self.sessions() as session:
            row = session.execute(select(Account, PasswordCredential).join(PasswordCredential)
                .where(Account.handle == normalized)).one_or_none()
            if row is None:
                return None
            account, stored = row
            credential = PasswordHash(stored.digest, stored.salt, stored.version,
                stored.work_n, stored.work_r, stored.work_p)
            return account if verify_password(password, credential) else None

    def create_session(self, account_id: str, raw_token: str,
        provenance: dict[str, str | None]) -> AuthenticationSession:
        timestamp = now()
        authentication = AuthenticationSession(id=str(uuid4()), account_id=account_id,
            token_digest=token_digest(raw_token), issued_at=timestamp,
            expires_at=timestamp + SESSION_LIFETIME, revoked_at=None, **provenance)
        with self.sessions.begin() as session:
            session.add(authentication)
        return authentication

    def account_for_token(self, raw_token: str | None, at: datetime | None = None) -> Account | None:
        if not raw_token:
            return None
        timestamp = at or now()
        with self.sessions() as session:
            row = session.execute(select(Account).join(AuthenticationSession)
                .where(AuthenticationSession.token_digest == token_digest(raw_token),
                    AuthenticationSession.revoked_at.is_(None),
                    AuthenticationSession.expires_at > timestamp)).scalar_one_or_none()
            return row

    def revoke_session(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        with self.sessions.begin() as session:
            authentication = session.scalar(select(AuthenticationSession)
                .where(AuthenticationSession.token_digest == token_digest(raw_token)))
            if authentication and authentication.revoked_at is None:
                authentication.revoked_at = now()

    def add_post(self, account_id: str, body: str) -> dict[str, object]:
        cleaned = body.strip()
        if not 1 <= len(cleaned) <= 280:
            raise DomainError("Post must contain 1–280 characters.")
        with self.sessions.begin() as session:
            post = Post(author_id=account_id, body=cleaned, created_at=now())
            session.add(post)
            session.flush()
            handle = session.get(Account, account_id).handle
            return self._serialize(post, handle, 0, False)

    def posts(self, viewer_id: str | None = None, before: int | None = None,
        limit: int = 50) -> list[dict[str, object]]:
        if not 1 <= limit <= 100:
            raise DomainError("Limit must be between 1 and 100.")
        with self.sessions() as session:
            query = select(Post, Account.handle).join(Account).order_by(Post.id.desc()).limit(limit)
            if before is not None:
                query = query.where(Post.id < before)
            rows = session.execute(query).all()
            return [self._post_state(session, post, handle, viewer_id) for post, handle in rows]

    def set_like(self, account_id: str, post_id: int, liked: bool) -> dict[str, object]:
        with self.sessions.begin() as session:
            post = session.get(Post, post_id)
            if post is None:
                raise DomainError("Post not found.", "missing")
            latest = session.scalar(select(LikeEvent).where(LikeEvent.post_id == post_id,
                LikeEvent.account_id == account_id).order_by(LikeEvent.id.desc()).limit(1))
            if latest is None or latest.liked != liked:
                session.add(LikeEvent(post_id=post_id, account_id=account_id,
                    liked=liked, occurred_at=now()))
                session.flush()
            handle = session.get(Account, post.author_id).handle
            return self._post_state(session, post, handle, account_id)

    @staticmethod
    def _post_state(session: Session, post: Post, handle: str,
        viewer_id: str | None) -> dict[str, object]:
        latest_ids = select(func.max(LikeEvent.id).label("id")).where(
            LikeEvent.post_id == post.id).group_by(LikeEvent.account_id).subquery()
        current = aliased(LikeEvent)
        likes = session.scalar(select(func.count()).select_from(current).join(
            latest_ids, current.id == latest_ids.c.id).where(current.liked.is_(True))) or 0
        liked_by_me = False
        if viewer_id:
            liked_by_me = bool(session.scalar(select(LikeEvent.liked).where(
                LikeEvent.post_id == post.id, LikeEvent.account_id == viewer_id)
                .order_by(LikeEvent.id.desc()).limit(1)))
        return MicroblogRepository._serialize(post, handle, likes, liked_by_me)

    @staticmethod
    def _serialize(post: Post, handle: str, likes: int,
        liked_by_me: bool) -> dict[str, object]:
        return {"id": post.id, "author": handle, "body": post.body,
            "created_at": utc(post.created_at).isoformat().replace("+00:00", "Z"),
            "like_count": likes, "liked_by_me": liked_by_me}
