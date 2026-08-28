"""Curated domain, API, persistence, and document contracts for WIRE/98."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from pathlib import Path
from threading import Event, get_ident
import unittest

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from apps.microblog.backend.auth import issue_token, token_digest
from apps.microblog.backend.database import (
    Account,
    AuthenticationSession,
    DomainError,
    LikeEvent,
    MicroblogRepository,
    PasswordCredential,
    Post,
    create_session_factory,
    now,
)
from monotools.auth import opaque_credential_digest


class MicroblogTests(unittest.TestCase):
    database = Path("apps/microblog/data/test-microblog.db")

    def setUp(self) -> None:
        self.database.unlink(missing_ok=True)
        self.sessions = create_session_factory(f"sqlite:///{self.database}")
        self.repository = MicroblogRepository(self.sessions)

    def tearDown(self) -> None:
        self.sessions.kw["bind"].dispose()
        self.database.unlink(missing_ok=True)

    def register(self, handle: str = "ada_l", password: str = "analytical1") -> Account:
        return self.repository.register(handle, password)

    def test_session_adapter_preserves_opaque_credentials_and_provenance(self) -> None:
        self.assertRegex(issue_token(), r"^[A-Za-z0-9_-]{43}$")
        self.assertEqual(token_digest("opaque-test"),
            opaque_credential_digest("opaque-test"))
        provenance = {"client_host": "127.0.0.1", "user_agent": "tests",
            "origin": "http://microblog.test"}
        expected_lengths = {"client_host": 255, "user_agent": 500, "origin": 500}
        self.assertEqual({name: AuthenticationSession.__table__.c[name].type.length
            for name in expected_lengths}, expected_lengths)
        session = AuthenticationSession(**provenance)
        self.assertEqual({name: getattr(session, name) for name in provenance}, provenance)

    def test_accounts_are_normalized_unique_and_credentials_verify(self) -> None:
        account = self.register("  ada_l  ")
        self.assertEqual(account.handle, "ada_l")
        self.assertEqual(self.repository.verify_login("ADA_L", "analytical1").id, account.id)
        self.assertIsNone(self.repository.verify_login("ada_l", "incorrect1"))
        with self.assertRaisesRegex(DomainError, "already registered"):
            self.register("ADA_L")
        with self.sessions() as session:
            credential = session.get(PasswordCredential, account.id)
            self.assertNotEqual(credential.digest, b"analytical1")
            self.assertEqual(credential.version, 1)
            self.assertGreater(credential.work_n, 1)

    def test_handle_password_and_post_validation_are_stable(self) -> None:
        with self.assertRaisesRegex(ValueError, "3–20"):
            self.register("No")
        with self.assertRaisesRegex(ValueError, "8–128"):
            self.register("valid_name", "short")
        account = self.register()
        for body in ("", "x" * 281):
            with self.subTest(length=len(body)), self.assertRaisesRegex(DomainError, "1–280"):
                self.repository.add_post(account.id, body)

    def test_sessions_expire_and_revoke_without_storing_raw_tokens(self) -> None:
        account, token = self.register(), "opaque-secret-token"
        authentication = self.repository.create_session(account.id, token,
            {"client_host": "127.0.0.1", "user_agent": "tests", "origin": None})
        self.assertEqual(self.repository.account_for_token(token).id, account.id)
        self.assertIsNone(self.repository.account_for_token(token,
            authentication.expires_at + timedelta(microseconds=1)))
        with self.sessions() as session:
            stored = session.get(AuthenticationSession, authentication.id)
            self.assertEqual(stored.token_digest, token_digest(token))
            self.assertNotIn(token, stored.token_digest)
        self.repository.revoke_session(token)
        self.assertIsNone(self.repository.account_for_token(token))

    def test_posts_are_newest_first_paginated_and_persist_after_restart(self) -> None:
        account = self.register()
        first = self.repository.add_post(account.id, "First")
        second = self.repository.add_post(account.id, "Second")
        self.assertEqual([post["id"] for post in self.repository.posts()],
            [second["id"], first["id"]])
        self.assertEqual(self.repository.posts(before=second["id"], limit=1)[0]["body"], "First")
        restarted_sessions = create_session_factory(f"sqlite:///{self.database}")
        try:
            restarted = MicroblogRepository(restarted_sessions)
            self.assertEqual([post["body"] for post in restarted.posts()], ["Second", "First"])
        finally:
            restarted_sessions.kw["bind"].dispose()

    def test_like_transitions_are_idempotent_and_derived_across_accounts(self) -> None:
        ada, grace = self.register(), self.register("grace_h", "compiler1")
        post_id = int(self.repository.add_post(ada.id, "Signals welcome")["id"])
        first = self.repository.set_like(ada.id, post_id, True)
        repeated = self.repository.set_like(ada.id, post_id, True)
        self.assertEqual((first["like_count"], repeated["like_count"]), (1, 1))
        self.repository.set_like(grace.id, post_id, True)
        self.assertEqual(self.repository.posts(ada.id)[0]["like_count"], 2)
        unliked = self.repository.set_like(ada.id, post_id, False)
        repeated_unlike = self.repository.set_like(ada.id, post_id, False)
        self.assertEqual((unliked["like_count"], unliked["liked_by_me"]), (1, False))
        self.assertEqual(repeated_unlike["like_count"], 1)
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(LikeEvent)), 3)
        with self.assertRaisesRegex(DomainError, "not found"):
            self.repository.set_like(ada.id, 999, True)

    def test_relational_constraints_and_normalized_entity_counts(self) -> None:
        account = self.register()
        self.repository.add_post(account.id, "A durable fact")
        with self.assertRaises(IntegrityError), self.sessions.begin() as session:
            session.add(Post(author_id="missing-account", body="invalid", created_at=now()))
        with self.sessions() as session:
            counts = {model.__tablename__: session.scalar(select(func.count()).select_from(model))
                for model in (Account, PasswordCredential, AuthenticationSession, Post, LikeEvent)}
        self.assertEqual(counts, {"accounts": 1, "password_credentials": 1,
            "authentication_sessions": 0, "posts": 1, "like_events": 0})

    def test_api_authentication_origin_errors_and_cookie_contract(self) -> None:
        from starlette.requests import Request

        from apps.microblog.backend.server import COOKIE, Credentials, PostInput, create_app

        application = create_app(f"sqlite:///{self.database}")
        endpoints = {route.path + ":" + next(iter(route.methods or ())): route.endpoint
            for route in application.routes if hasattr(route, "endpoint")}

        def request(headers: dict[str, str] | None = None) -> Request:
            encoded = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
            return Request({"type": "http", "scheme": "http", "path": "/",
                "headers": encoded, "client": ("127.0.0.1", 1), "server": ("testserver", 80)})

        with self.assertRaisesRegex(DomainError, "Authentication required") as unauthorized:
            endpoints["/api/posts:POST"](PostInput(body="No identity"), request())
        self.assertEqual(unauthorized.exception.kind, "authentication")
        with self.assertRaisesRegex(DomainError, "origin is not allowed") as rejected:
            endpoints["/api/accounts:POST"](Credentials(handle="api_user",
                password="securepass"), request({"Origin": "https://foreign.example"}))
        self.assertEqual(rejected.exception.kind, "forbidden")
        created = endpoints["/api/accounts:POST"](
            Credentials(handle="api_user", password="securepass"), request())
        self.assertEqual(created.status_code, 201)
        cookie = created.headers["set-cookie"]
        self.assertIn(f"{COOKIE}=", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=lax", cookie)
        session_cookie = cookie.split(";", 1)[0]
        authenticated_request = request({"Cookie": session_cookie})
        published = endpoints["/api/posts:POST"](PostInput(body="From the API"), authenticated_request)
        liked = endpoints["/api/posts/{post_id}/like:PUT"](published["id"], authenticated_request)
        self.assertEqual(liked["like_count"], 1)
        logged_out = endpoints["/api/session:DELETE"](authenticated_request)
        self.assertFalse(json.loads(logged_out.body)["authenticated"])

    def test_live_feed_announces_each_confirmed_change(self) -> None:
        from apps.microblog.backend.server import ChangeFeed

        changes = ChangeFeed(keepalive_seconds=0)
        revision = changes.publish()
        events = changes.events()
        event = next(events)
        self.assertEqual(revision, 1)
        self.assertEqual(event, "id: 1\nevent: feed\ndata: 1\n\n")
        with ThreadPoolExecutor(max_workers=1) as workers:
            keepalive = workers.submit(next, events).result(timeout=1)
        self.assertEqual(keepalive, ": keepalive\n\n")
        events.close()

    def test_live_feed_delivers_across_threads_without_holding_its_condition(self) -> None:
        from apps.microblog.backend.server import ChangeFeed

        changes = ChangeFeed(keepalive_seconds=1)
        events = changes.events()
        waiting = Event()

        def wait_for_change() -> tuple[int, str]:
            waiting.set()
            return get_ident(), next(events)

        def publish_change() -> tuple[int, int]:
            return get_ident(), changes.publish()

        def condition_can_be_acquired() -> bool:
            acquired = changes.condition.acquire(timeout=0.1)
            if acquired:
                changes.condition.release()
            return acquired

        with ThreadPoolExecutor(max_workers=2) as workers:
            delivery = workers.submit(wait_for_change)
            self.assertTrue(waiting.wait(timeout=1))
            published = workers.submit(publish_change)
            publisher_thread, revision = published.result(timeout=1)
            delivery_thread, event = delivery.result(timeout=1)
            self.assertNotEqual(delivery_thread, publisher_thread)
            self.assertEqual(revision, 1)
            self.assertEqual(event, "id: 1\nevent: feed\ndata: 1\n\n")

            # A suspended generator must not retain the thread-owned condition lock.
            self.assertTrue(workers.submit(condition_can_be_acquired).result(timeout=1))
        events.close()

    def test_frontend_has_operational_responsive_and_accessible_contracts(self) -> None:
        frontend = Path("apps/microblog/frontend")
        document = "\n".join(path.read_text(encoding="utf-8")
            for path in sorted(frontend.glob("*.js")))
        for marker in ('aria-live="polite"', 'aria-labelledby="feed-title"',
            ":focus-visible", "@media (max-width: 620px)", "EventSource", "REFRESH",
            "maxlength=\"280\"", 'id="authMessage" role="alert"',
            "REGISTER THIS HANDLE", 'minlength="8"', '!event.shiftKey',
            '$("postForm").requestSubmit()'):
            with self.subTest(marker=marker):
                self.assertIn(marker, document)
        self.assertNotIn("https://", document)
        self.assertNotIn("http://", document)


if __name__ == "__main__":
    unittest.main()
