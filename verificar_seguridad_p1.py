from __future__ import annotations

import hashlib
import sqlite3

from backend.security.passwords import LEGACY_ITERATIONS, LEGACY_SALT, hash_password, needs_rehash, verify_and_upgrade, verify_password
from backend.services.edge_sync import DeviceEdgeSyncService


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify_password_hashing() -> None:
    password = "Correcta-Enterprise-2026!"
    first = hash_password(password)
    second = hash_password(password)
    check(first != second, "cada hash debe usar un salt individual")
    check(verify_password(password, first), "el hash nuevo debe verificar")
    check(not verify_password("incorrecta", first), "una clave incorrecta no debe verificar")
    check(not needs_rehash(first), "el hash actual no debe requerir migracion")
    check(not verify_password(password, "pbkdf2_sha256$broken"), "un hash malformado debe fallar cerrado")

    legacy = hashlib.pbkdf2_hmac("sha256", password.encode(), LEGACY_SALT, LEGACY_ITERATIONS).hex()
    ok, replacement = verify_and_upgrade(password, legacy)
    check(ok and replacement is not None, "un hash legacy valido debe proponer migracion")
    check(verify_password(password, replacement or ""), "el reemplazo debe verificar")
    failed, replacement = verify_and_upgrade("incorrecta", legacy)
    check(not failed and replacement is None, "nunca debe migrarse tras credenciales invalidas")


def verify_device_activation_gate() -> None:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute(
        """CREATE TABLE enterprise_devices (
            id INTEGER PRIMARY KEY, organization_id INTEGER, event_id INTEGER,
            status TEXT, credential_hash TEXT, capabilities_json TEXT
        )"""
    )
    service = DeviceEdgeSyncService(access_engine=object())
    secret = "dev-test-secret"
    digest = service._hash(secret)
    db.execute("INSERT INTO enterprise_devices VALUES (1, 10, 20, 'PROVISIONED', ?, '[\"SYNC_DATASET\"]')", (digest,))
    check(not service.authenticate_device(db, organization_id=10, event_id=20, device_id=1, secret=secret, capability="SYNC_DATASET").ok, "PROVISIONED no debe operar")
    db.execute("UPDATE enterprise_devices SET status = 'ACTIVE' WHERE id = 1")
    check(service.authenticate_device(db, organization_id=10, event_id=20, device_id=1, secret=secret, capability="SYNC_DATASET").ok, "ACTIVE debe autenticar")
    check(not service.authenticate_device(db, organization_id=10, event_id=20, device_id=1, secret="wrong", capability="SYNC_DATASET").ok, "un secreto invalido debe rechazarse")
    check(not service.authenticate_device(db, organization_id=10, event_id=20, device_id=1, secret=secret, capability="VALIDATE_ACCESS").ok, "una capacidad ausente debe rechazarse")


if __name__ == "__main__":
    verify_password_hashing()
    verify_device_activation_gate()
    print("OK - seguridad P1")
