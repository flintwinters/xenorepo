"""Durable workspace facts for the localhost terminal desktop."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
import hashlib
import hmac
import secrets
from uuid import UUID, uuid4

from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKey, Integer, LargeBinary,
    String, inspect, select)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from monotools.appkit import SystemClock
from monotools.database import create_session_factory as _create_session_factory


MAX_TRANSCRIPT_BYTES = 1_000_000
PASSWORD_HASH_VERSION = 1
PASSWORD_SCRYPT_N = 2**14
PASSWORD_SCRYPT_R = 8
PASSWORD_SCRYPT_P = 1
SETTINGS_ID = 1


class Base(DeclarativeBase):
    pass


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ServerSettings(Base):
    """The single durable server identity and access-control configuration."""

    __tablename__ = "server_settings"
    __table_args__ = (CheckConstraint("id = 1", name="single_server_settings"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canonical_workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), unique=True)
    password_digest: Mapped[bytes | None] = mapped_column(LargeBinary)
    password_salt: Mapped[bytes | None] = mapped_column(LargeBinary)
    password_hash_version: Mapped[int] = mapped_column(Integer)
    access_session_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


@dataclass(frozen=True)
class PasswordVerifier:
    digest: bytes
    salt: bytes
    version: int = PASSWORD_HASH_VERSION


def _hash_password(password: str, salt: bytes | None = None) -> PasswordVerifier:
    resolved_salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=resolved_salt,
        n=PASSWORD_SCRYPT_N, r=PASSWORD_SCRYPT_R, p=PASSWORD_SCRYPT_P)
    return PasswordVerifier(digest, resolved_salt)


def _password_matches(password: str | None, settings: ServerSettings) -> bool:
    if not password or settings.password_digest is None or settings.password_salt is None:
        return False
    if settings.password_hash_version != PASSWORD_HASH_VERSION:
        return False
    candidate = _hash_password(password, settings.password_salt)
    return hmac.compare_digest(candidate.digest, settings.password_digest)


class WorkspaceShortcut(Base):
    """A user-owned keyboard binding for one desktop action."""

    __tablename__ = "workspace_shortcuts"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    action: Mapped[str] = mapped_column(String(40), primary_key=True)
    key: Mapped[str] = mapped_column(String(40))
    control: Mapped[bool] = mapped_column(Boolean)
    alt: Mapped[bool] = mapped_column(Boolean)
    shift: Mapped[bool] = mapped_column(Boolean)
    meta: Mapped[bool] = mapped_column(Boolean)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TerminalWindow(Base):
    __tablename__ = "terminal_windows"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    title: Mapped[str] = mapped_column(String(80))
    x: Mapped[int] = mapped_column(Integer)
    y: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    z: Mapped[int] = mapped_column(Integer)
    minimized: Mapped[bool] = mapped_column(Boolean)
    maximized: Mapped[bool] = mapped_column(Boolean)
    active_tab_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Retained only so existing SQLite databases can be migrated without losing history.
    transcript: Mapped[bytes] = mapped_column(LargeBinary, default=b"")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TerminalTab(Base):
    """A durable shell session which may move between window containers."""

    __tablename__ = "terminal_tabs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    window_id: Mapped[str] = mapped_column(ForeignKey("terminal_windows.id", ondelete="CASCADE"),
        index=True)
    title: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(Integer)
    transcript: Mapped[bytes] = mapped_column(LargeBinary, default=b"")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    """Create the standalone domain factory used by Worminal tests."""
    return _create_session_factory(database_url, Base.metadata, _migrate_legacy_schema)


def _migrate_legacy_schema(engine: Engine) -> None:
    """Quarantine the experimental pre-workspace schema before creating this model."""
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("terminal_windows")}
    if "workspace_id" in columns:
        with engine.begin() as connection:
            if "active_tab_id" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE terminal_windows ADD COLUMN active_tab_id VARCHAR(36)")
            connection.exec_driver_sql("""
                INSERT INTO terminal_tabs
                    (id, window_id, title, position, transcript, created_at, updated_at)
                SELECT id, id, title, 0, transcript, created_at, updated_at
                FROM terminal_windows
                WHERE NOT EXISTS (
                    SELECT 1 FROM terminal_tabs WHERE terminal_tabs.window_id = terminal_windows.id
                )
            """)
            connection.exec_driver_sql("""
                UPDATE terminal_windows
                SET active_tab_id = id
                WHERE active_tab_id IS NULL
                  AND EXISTS (SELECT 1 FROM terminal_tabs WHERE window_id = terminal_windows.id)
            """)
        return
    with engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE terminal_windows RENAME TO terminal_windows_legacy")
    Base.metadata.create_all(engine)


def _window_state(window: TerminalWindow) -> dict[str, object]:
    return {
        "id": window.id, "title": window.title, "x": window.x, "y": window.y,
        "width": window.width, "height": window.height, "z": window.z,
        "minimized": window.minimized, "maximized": window.maximized,
        "active_tab_id": window.active_tab_id,
    }


def _tab_state(tab: TerminalTab) -> dict[str, object]:
    return {"id": tab.id, "title": tab.title, "position": tab.position}


DEFAULT_SHORTCUTS = [{"action": "new-shell", "key": "Meta", "control": False,
    "alt": False, "shift": False, "meta": False}]


def _shortcut_state(shortcut: WorkspaceShortcut) -> dict[str, object]:
    return {"action": shortcut.action, "key": shortcut.key, "control": shortcut.control,
        "alt": shortcut.alt, "shift": shortcut.shift, "meta": shortcut.meta}


class WorkspaceRepository:
    """Own workspace identity, window geometry, and bounded terminal history."""

    def __init__(self, sessions: sessionmaker[Session],
        clock: Callable[[], datetime] | None = None) -> None:
        self.sessions = sessions
        self.clock = clock or SystemClock().now

    def create_workspace(self) -> str:
        identifier, timestamp = str(uuid4()), self.clock()
        with self.sessions.begin() as session:
            session.add(Workspace(id=identifier, created_at=timestamp, updated_at=timestamp))
        return identifier

    def initialize(self, initial_access_password: str | None = None) -> str:
        """Create the server singleton once, optionally seeding its first password."""
        with self.sessions.begin() as session:
            settings = session.get(ServerSettings, SETTINGS_ID)
            if settings is not None:
                if settings.password_digest is None and initial_access_password:
                    verifier = _hash_password(initial_access_password)
                    settings.password_digest = verifier.digest
                    settings.password_salt = verifier.salt
                    settings.password_hash_version = verifier.version
                    settings.access_session_version = secrets.token_hex(32)
                    settings.updated_at = self.clock()
                return settings.canonical_workspace_id
            workspace = session.scalar(
                select(Workspace).order_by(Workspace.updated_at.desc()).limit(1))
            timestamp = self.clock()
            if workspace is None:
                workspace = Workspace(id=str(uuid4()), created_at=timestamp, updated_at=timestamp)
                session.add(workspace)
                session.flush()
            verifier = (_hash_password(initial_access_password)
                if initial_access_password else None)
            session.add(ServerSettings(id=SETTINGS_ID,
                canonical_workspace_id=workspace.id,
                password_digest=verifier.digest if verifier else None,
                password_salt=verifier.salt if verifier else None,
                password_hash_version=PASSWORD_HASH_VERSION,
                access_session_version=secrets.token_hex(32),
                created_at=timestamp, updated_at=timestamp))
            return workspace.id

    def shared_workspace(self) -> str:
        """Return the canonical desktop selected when server settings were created."""
        return self.initialize()

    def access_session_version(self) -> str | None:
        """Return the active session generation only when remote access is configured."""
        self.initialize()
        with self.sessions() as session:
            settings = session.get(ServerSettings, SETTINGS_ID)
            return (settings.access_session_version
                if settings.password_digest is not None else None)

    def verify_access_password(self, password: str | None) -> bool:
        self.initialize()
        with self.sessions() as session:
            return _password_matches(password, session.get(ServerSettings, SETTINGS_ID))

    def change_access_password(self, current_password: str, new_password: str) -> bool:
        """Replace the verifier and invalidate every previously issued access cookie."""
        if not new_password:
            raise ValueError("New password is required.")
        self.initialize()
        with self.sessions.begin() as session:
            settings = session.get(ServerSettings, SETTINGS_ID)
            if not _password_matches(current_password, settings):
                return False
            verifier = _hash_password(new_password)
            settings.password_digest = verifier.digest
            settings.password_salt = verifier.salt
            settings.password_hash_version = verifier.version
            settings.access_session_version = secrets.token_hex(32)
            settings.updated_at = self.clock()
            return True

    def workspace_exists(self, workspace_id: str | None) -> bool:
        return bool(workspace_id) and self._valid_identifier(workspace_id) and self._workspace(workspace_id)

    def windows(self, workspace_id: str) -> list[dict[str, object]]:
        with self.sessions() as session:
            windows = list(session.scalars(select(TerminalWindow)
                .where(TerminalWindow.workspace_id == workspace_id)
                .order_by(TerminalWindow.z, TerminalWindow.created_at)))
            tabs = list(session.scalars(select(TerminalTab)
                .join(TerminalWindow, TerminalWindow.id == TerminalTab.window_id)
                .where(TerminalWindow.workspace_id == workspace_id)
                .order_by(TerminalTab.position, TerminalTab.created_at)))
            by_window: dict[str, list[dict[str, object]]] = {}
            for tab in tabs:
                by_window.setdefault(tab.window_id, []).append(_tab_state(tab))
            return [{**_window_state(window), "tabs": by_window.get(window.id, [])}
                for window in windows]

    def shortcuts(self, workspace_id: str) -> list[dict[str, object]]:
        with self.sessions() as session:
            stored = list(session.scalars(select(WorkspaceShortcut)
                .where(WorkspaceShortcut.workspace_id == workspace_id)
                .order_by(WorkspaceShortcut.action)))
            return [_shortcut_state(shortcut) for shortcut in stored] or DEFAULT_SHORTCUTS.copy()

    def replace_windows(self, workspace_id: str, windows: Iterable[dict[str, object]]) -> None:
        declared = list(windows)
        self._validate_windows(declared)
        timestamp = self.clock()
        with self.sessions.begin() as session:
            workspace = self._require_workspace(session, workspace_id)
            identifiers = {str(item["id"]) for item in declared}
            for window in session.scalars(select(TerminalWindow)
                .where(TerminalWindow.workspace_id == workspace_id)):
                if window.id not in identifiers:
                    session.delete(window)
            self._upsert_windows(session, workspace_id, declared, timestamp)
            workspace.updated_at = timestamp

    def update_windows(self, workspace_id: str, windows: Iterable[dict[str, object]]) -> None:
        """Upsert client-known windows without deleting concurrent additions."""
        declared = list(windows)
        self._validate_windows(declared)
        timestamp = self.clock()
        with self.sessions.begin() as session:
            workspace = self._require_workspace(session, workspace_id)
            self._upsert_windows(session, workspace_id, declared, timestamp)
            workspace.updated_at = timestamp

    @staticmethod
    def _validate_windows(declared: list[dict[str, object]]) -> None:
        if not WorkspaceRepository._identifiers_unique(declared):
            raise ValueError("Window IDs must be unique.")
        tabs = [tab for item in declared for tab in item["tabs"]]
        if not WorkspaceRepository._identifiers_unique(tabs):
            raise ValueError("Tab IDs must be unique.")
        for item in declared:
            if not WorkspaceRepository._active_tab_is_declared(item):
                raise ValueError("Each window must have an active tab.")

    @staticmethod
    def _identifiers_unique(items: Iterable[dict[str, object]]) -> bool:
        identifiers = [str(item["id"]) for item in items]
        return len(identifiers) == len(set(identifiers))

    @staticmethod
    def _active_tab_is_declared(window: dict[str, object]) -> bool:
        tabs = window["tabs"]
        return bool(tabs) and window["active_tab_id"] in {tab["id"] for tab in tabs}

    @staticmethod
    def _require_workspace(session: Session, workspace_id: str) -> Workspace:
        workspace = session.get(Workspace, workspace_id)
        if workspace is None:
            raise ValueError("Workspace is not available.")
        return workspace

    @staticmethod
    def _upsert_windows(session: Session, workspace_id: str,
        declared: list[dict[str, object]], timestamp: datetime) -> None:
        identifiers = [str(item["id"]) for item in declared]
        existing = WorkspaceRepository._existing_windows(session, workspace_id, identifiers)
        for item in declared:
            WorkspaceRepository._upsert_window(
                session, workspace_id, item, existing, timestamp)
        session.flush()
        tabs = WorkspaceRepository._declared_tabs(declared)
        tab_ids = [str(tab["id"]) for tab in tabs]
        existing_tabs = WorkspaceRepository._existing_tabs(session, tab_ids)
        for values in tabs:
            WorkspaceRepository._upsert_tab(session, values, existing_tabs, timestamp)

    @staticmethod
    def _existing_windows(session: Session, workspace_id: str,
        identifiers: list[str]) -> dict[str, TerminalWindow]:
        if not identifiers:
            return {}
        windows = session.scalars(select(TerminalWindow).where(
            TerminalWindow.workspace_id == workspace_id,
            TerminalWindow.id.in_(identifiers)))
        return {window.id: window for window in windows}

    @staticmethod
    def _declared_tabs(declared: list[dict[str, object]]) -> list[dict[str, object]]:
        return [{**tab, "window_id": str(item["id"])}
            for item in declared for tab in item["tabs"]]

    @staticmethod
    def _existing_tabs(session: Session,
        identifiers: list[str]) -> dict[str, TerminalTab]:
        if not identifiers:
            return {}
        tabs = session.scalars(select(TerminalTab).where(TerminalTab.id.in_(identifiers)))
        return {tab.id: tab for tab in tabs}

    @staticmethod
    def _upsert_window(session: Session, workspace_id: str, values: dict[str, object],
        existing: dict[str, TerminalWindow], timestamp: datetime) -> None:
        identifier = str(values["id"])
        payload = {key: value for key, value in values.items() if key not in {"id", "tabs"}}
        window = existing.get(identifier)
        if window is None:
            session.add(TerminalWindow(id=identifier, workspace_id=workspace_id,
                transcript=b"", created_at=timestamp, updated_at=timestamp, **payload))
            return
        WorkspaceRepository._update_model(window, payload, timestamp)

    @staticmethod
    def _upsert_tab(session: Session, values: dict[str, object],
        existing: dict[str, TerminalTab], timestamp: datetime) -> None:
        identifier = str(values["id"])
        payload = {key: value for key, value in values.items() if key != "id"}
        tab = existing.get(identifier)
        if tab is None:
            session.add(TerminalTab(id=identifier, transcript=b"",
                created_at=timestamp, updated_at=timestamp, **payload))
            return
        WorkspaceRepository._update_model(tab, payload, timestamp)

    @staticmethod
    def _update_model(model: TerminalWindow | TerminalTab, values: dict[str, object],
        timestamp: datetime) -> None:
        for key, value in values.items():
            setattr(model, key, value)
        model.updated_at = timestamp

    def replace_shortcuts(self, workspace_id: str, shortcuts: Iterable[dict[str, object]]) -> None:
        declared = list(shortcuts)
        actions = [str(item["action"]) for item in declared]
        if actions != ["new-shell"]:
            raise ValueError("Exactly one new-shell shortcut is required.")
        timestamp = self.clock()
        with self.sessions.begin() as session:
            workspace = session.get(Workspace, workspace_id)
            if workspace is None:
                raise ValueError("Workspace is not available.")
            shortcut = session.get(WorkspaceShortcut, (workspace_id, "new-shell"))
            if shortcut is None:
                shortcut = WorkspaceShortcut(workspace_id=workspace_id, updated_at=timestamp,
                    **declared[0])
                session.add(shortcut)
            else:
                for key, value in declared[0].items():
                    setattr(shortcut, key, value)
                shortcut.updated_at = timestamp
            workspace.updated_at = timestamp

    def delete_window(self, workspace_id: str, window_id: str) -> list[str] | None:
        with self.sessions.begin() as session:
            window = session.get(TerminalWindow, window_id)
            if window is None or window.workspace_id != workspace_id:
                return None
            tab_ids = list(session.scalars(select(TerminalTab.id)
                .where(TerminalTab.window_id == window_id)))
            session.delete(window)
            session.get(Workspace, workspace_id).updated_at = self.clock()
            return tab_ids

    def delete_tab(self, workspace_id: str, tab_id: str) -> bool:
        with self.sessions.begin() as session:
            tab = session.get(TerminalTab, tab_id)
            window = session.get(TerminalWindow, tab.window_id) if tab else None
            if window is None or window.workspace_id != workspace_id:
                return False
            session.delete(tab)
            session.get(Workspace, workspace_id).updated_at = self.clock()
            return True

    def transcript(self, workspace_id: str, tab_id: str) -> bytes | None:
        with self.sessions() as session:
            tab = session.get(TerminalTab, tab_id)
            window = session.get(TerminalWindow, tab.window_id) if tab else None
            return None if window is None or window.workspace_id != workspace_id else tab.transcript

    def append_output(self, workspace_id: str, tab_id: str, output: bytes) -> bool:
        if not output:
            return True
        with self.sessions.begin() as session:
            tab = session.get(TerminalTab, tab_id)
            window = session.get(TerminalWindow, tab.window_id) if tab else None
            if window is None or window.workspace_id != workspace_id:
                return False
            tab.transcript = (tab.transcript + output)[-MAX_TRANSCRIPT_BYTES:]
            tab.updated_at = self.clock()
            session.get(Workspace, workspace_id).updated_at = tab.updated_at
            return True

    def _workspace(self, workspace_id: str) -> bool:
        with self.sessions() as session:
            return session.get(Workspace, workspace_id) is not None

    @staticmethod
    def _valid_identifier(value: str) -> bool:
        try:
            UUID(value)
        except ValueError:
            return False
        return True
