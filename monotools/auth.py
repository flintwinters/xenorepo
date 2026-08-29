"""Construct opaque credentials and storage-safe digests.

The helpers centralize unpredictable credential issuance and one-way hashing
so applications can persist authenticators without storing bearer secrets.
"""

import hashlib
import secrets


def issue_opaque_credential() -> str:
    """Issue an unpredictable URL-safe credential suitable for a cookie."""
    return secrets.token_urlsafe(32)


def opaque_credential_digest(credential: str) -> str:
    """Return the stable SHA-256 digest used for credential lookup."""
    return hashlib.sha256(credential.encode()).hexdigest()
