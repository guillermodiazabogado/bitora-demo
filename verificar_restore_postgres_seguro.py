from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "scripts" / "restore_postgres.ps1"


def policy(database_url: str, prefix: str, confirmation: str, *, production: bool = False) -> bool:
    if production or not prefix or len(prefix) < 8:
        return False
    try:
        parsed = urlsplit(database_url)
    except ValueError:
        return False
    if parsed.scheme.lower() not in {"postgres", "postgresql"} or not parsed.netloc:
        return False
    database = unquote(parsed.path.removeprefix("/"))
    if not database or "/" in database or not re.fullmatch(r"[A-Za-z0-9_]+", database):
        return False
    if not database.startswith(prefix):
        return False
    if re.search(r"(^|[\W_])(prod|production)([\W_]|$)", database_url.lower()):
        return False
    return confirmation == f"RESTORE {database}"


def check_script_contract() -> None:
    text = SCRIPT.read_text(encoding="utf-8-sig")
    required = (
        "[string]$ChecksumPath",
        "[string]$AllowedDatabasePrefix",
        "[string]$ConfirmDestination",
        "Get-FileHash -Algorithm SHA256",
        "$databaseName.StartsWith($AllowedDatabasePrefix",
        '$expectedConfirmation = "RESTORE $databaseName"',
        "Checksum SHA-256 del dump no coincide",
        "Restore bloqueado en production",
    )
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise AssertionError(f"faltan controles en PowerShell: {missing}")
    if "[switch]$Yes" in text:
        raise AssertionError("la confirmacion booleana insegura aun esta presente")
    restore_pos = text.find("pg_restore ")
    for marker in ("Get-FileHash -Algorithm SHA256", "$expectedConfirmation", "$databaseName.StartsWith"):
        if text.find(marker) < 0 or text.find(marker) > restore_pos:
            raise AssertionError(f"control posterior a pg_restore: {marker}")


def check_policy_cases() -> None:
    safe = "postgresql://operator@example.internal:5432/bitora_restore_20261027"
    assert policy(safe, "bitora_restore_", "RESTORE bitora_restore_20261027")
    rejected = (
        ("postgresql://operator@example.internal:5432/bitora", "bitora_restore_", "RESTORE bitora"),
        ("postgresql://operator@production.internal:5432/bitora_restore_1", "bitora_restore_", "RESTORE bitora_restore_1"),
        ("postgresql://operator@example.internal:5432/bitora_restore_prod", "bitora_restore_", "RESTORE bitora_restore_prod"),
        ("postgresql://operator@example.internal:5432/bitora_restore_1/extra", "bitora_restore_", "RESTORE bitora_restore_1/extra"),
        ("sqlite:///bitora_restore_1", "bitora_restore_", "RESTORE bitora_restore_1"),
        (safe, "bitora_restore_", "YES"),
        (safe, "short", "RESTORE bitora_restore_20261027"),
    )
    for database_url, prefix, confirmation in rejected:
        assert not policy(database_url, prefix, confirmation), database_url
    assert not policy(safe, "bitora_restore_", "RESTORE bitora_restore_20261027", production=True)


if __name__ == "__main__":
    check_script_contract()
    check_policy_cases()
    print("OK - restore PostgreSQL exige checksum, aislamiento y confirmacion tipada")
