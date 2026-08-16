"""Credential and opaque-session primitives using only the standard library."""

from dataclasses import dataclass
import hashlib
import hmac
import re
import secrets


HANDLE_PATTERN = re.compile(r"^[a-z0-9_]{3,20}$")
PASSWORD_MINIMUM = 8
PASSWORD_MAXIMUM = 128
SCRYPT_VERSION = 1
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


class ValidationError(ValueError):
    """A stable, user-correctable domain validation failure."""


@dataclass(frozen=True)
class PasswordHash:
    digest: bytes
    salt: bytes
    version: int = SCRYPT_VERSION
    n: int = SCRYPT_N
    r: int = SCRYPT_R
    p: int = SCRYPT_P


def normalize_handle(value: str) -> str:
    handle = value.strip().lower()
    if not HANDLE_PATTERN.fullmatch(handle):
        raise ValidationError("Handle must be 3–20 lowercase letters, numbers, or underscores.")
    return handle


def validate_password(value: str) -> str:
    if not PASSWORD_MINIMUM <= len(value) <= PASSWORD_MAXIMUM:
        raise ValidationError("Password must be 8–128 characters.")
    return value


def hash_password(password: str, *, salt: bytes | None = None) -> PasswordHash:
    validate_password(password)
    resolved_salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=resolved_salt,
        n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return PasswordHash(digest=digest, salt=resolved_salt)


def verify_password(password: str, credential: PasswordHash) -> bool:
    try:
        candidate = hashlib.scrypt(password.encode(), salt=credential.salt,
            n=credential.n, r=credential.r, p=credential.p)
    except (ValueError, TypeError):
        return False
    return credential.version == SCRYPT_VERSION and hmac.compare_digest(
        candidate, credential.digest)


def issue_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
