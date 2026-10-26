"""Versioned password hashing with compatibility for BITORA's legacy hashes.

New hashes carry their algorithm, work factor, and per-password salt.  Legacy
hashes were bare hexadecimal PBKDF2-SHA256 digests using a shared salt; they are
accepted only so callers can replace them after a successful login.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from cryptography.hazmat.primitives.kdf.argon2 import Argon2id


ALGORITHM = "argon2id"
PBKDF2_ALGORITHM = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 310_000
LEGACY_ITERATIONS = 120_000
LEGACY_SALT = b"qr-white-label-local"
SALT_BYTES = 16
ARGON2_ITERATIONS = 3
ARGON2_MEMORY_KIB = 65_536
ARGON2_LANES = 4
HASH_BYTES = 32


def hash_password(password: str) -> str:
    value = _password_bytes(password)
    salt = secrets.token_bytes(SALT_BYTES)
    digest = Argon2id(
        salt=salt,
        length=HASH_BYTES,
        iterations=ARGON2_ITERATIONS,
        lanes=ARGON2_LANES,
        memory_cost=ARGON2_MEMORY_KIB,
        ad=None,
        secret=None,
    ).derive(value)
    return f"{ALGORITHM}${ARGON2_ITERATIONS}${ARGON2_MEMORY_KIB}${ARGON2_LANES}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    value = _password_bytes(password)
    stored = str(stored_hash or "")
    if stored.startswith(f"{ALGORITHM}$"):
        try:
            _algorithm, iterations_text, memory_text, lanes_text, salt_hex, digest_hex = stored.split("$", 5)
            iterations = int(iterations_text)
            memory_cost = int(memory_text)
            lanes = int(lanes_text)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(digest_hex)
        except (TypeError, ValueError):
            return False
        if iterations < 1 or memory_cost < 8 or lanes < 1 or not salt or not expected:
            return False
        try:
            actual = Argon2id(salt=salt, length=len(expected), iterations=iterations, lanes=lanes, memory_cost=memory_cost, ad=None, secret=None).derive(value)
        except (TypeError, ValueError):
            return False
        return hmac.compare_digest(actual, expected)

    if stored.startswith(f"{PBKDF2_ALGORITHM}$"):
        try:
            _algorithm, rounds_text, salt_hex, digest_hex = stored.split("$", 3)
            rounds = int(rounds_text)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(digest_hex)
        except (TypeError, ValueError):
            return False
        if rounds < 1 or not salt or not expected:
            return False
        return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", value, salt, rounds), expected)

    # Compatibility path for the historical bare hexadecimal digest.
    try:
        expected = bytes.fromhex(stored)
    except ValueError:
        return False
    if len(expected) != hashlib.sha256().digest_size:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", value, LEGACY_SALT, LEGACY_ITERATIONS)
    return hmac.compare_digest(actual, expected)


def needs_rehash(stored_hash: str) -> bool:
    stored = str(stored_hash or "")
    if not stored.startswith(f"{ALGORITHM}$"):
        return True
    try:
        _algorithm, iterations_text, memory_text, lanes_text, salt_hex, digest_hex = stored.split("$", 5)
        iterations = int(iterations_text)
        memory_cost = int(memory_text)
        lanes = int(lanes_text)
        salt = bytes.fromhex(salt_hex)
        digest = bytes.fromhex(digest_hex)
    except (TypeError, ValueError):
        return True
    return (
        iterations < ARGON2_ITERATIONS
        or memory_cost < ARGON2_MEMORY_KIB
        or lanes < ARGON2_LANES
        or len(salt) < SALT_BYTES
        or len(digest) != HASH_BYTES
    )


def verify_and_upgrade(password: str, stored_hash: str) -> tuple[bool, str | None]:
    """Verify a password and return a replacement hash when it is obsolete."""
    if not verify_password(password, stored_hash):
        return False, None
    return True, hash_password(password) if needs_rehash(stored_hash) else None


def _password_bytes(password: str) -> bytes:
    if not isinstance(password, str):
        raise TypeError("password must be a string")
    return password.encode("utf-8")
