"""Shared opaque credential construction and storage-safe digests."""

import hashlib
import secrets


def issue_opaque_credential() -> str:
    """Issue an unpredictable URL-safe credential suitable for a cookie."""
    return secrets.token_urlsafe(32)


def opaque_credential_digest(credential: str) -> str:
    """Return the stable SHA-256 digest used for credential lookup."""
    return hashlib.sha256(credential.encode()).hexdigest()
