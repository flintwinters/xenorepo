"""Opaque guest credential primitives."""

from monotools.auth import issue_opaque_credential, opaque_credential_digest


def issue_credential() -> str:
    """Issue an RPS-compatible opaque guest credential."""
    return issue_opaque_credential()


def credential_digest(credential: str) -> str:
    """Return the storage-safe digest for an RPS guest credential."""
    return opaque_credential_digest(credential)
