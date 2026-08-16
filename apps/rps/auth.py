"""Opaque guest credential primitives."""

import hashlib
import secrets


def issue_credential() -> str:
    return secrets.token_urlsafe(32)


def credential_digest(credential: str) -> str:
    return hashlib.sha256(credential.encode()).hexdigest()
