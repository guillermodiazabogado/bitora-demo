from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

import server
from backend.database import DatabaseConfig


ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "output" / "live_integrations"


def live_enabled() -> bool:
    return os.environ.get("BITORA_LIVE_INTEGRATIONS", "").lower() in {"1", "true", "yes", "si"}


def classify(required_env: list[str]) -> tuple[str, list[str]]:
    missing = [key for key in required_env if not os.environ.get(key)]
    if missing:
        return "contract", missing
    return ("live" if live_enabled() else "sandbox", [])


def write_report(name: str, payload: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def synthetic_multitenant_db():
    os.environ.setdefault("BITORA_INTEGRATION_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    tmp = tempfile.TemporaryDirectory(prefix="bitora-live-integrations-", ignore_cleanup_errors=True)
    db_path = Path(tmp.name) / "bitora.sqlite3"
    original_config = server.DB_CONFIG
    original_path = server.DB_PATH
    server.DB_CONFIG = DatabaseConfig(engine="sqlite", sqlite_path=str(db_path), postgres_dsn="")
    server.DB_PATH = db_path
    server.init_db()
    db = server.connect()
    try:
        now = server.now_iso()
        org_a = server.bootstrap_default_organization(db)
        org_b = int(db.execute(
            """
            INSERT INTO organizations (public_id, name, legal_name, status, plan, safe_mode_email, safe_mode_whatsapp, force_email_recipient, force_whatsapp_recipient, created_at, updated_at)
            VALUES (?, 'Organizacion Beta', 'Organizacion Beta', 'active', 'standard', 1, 1, 'beta-safe@example.test', '5491100000000', ?, ?)
            """,
            (server.make_public_id("org"), now, now),
        ).lastrowid)
        admin = db.execute("SELECT * FROM users WHERE name = 'Admin'").fetchone()
        db.execute(
            "INSERT OR IGNORE INTO organization_users (organization_id, user_id, role, status, accepted_at, created_at, updated_at) VALUES (?, ?, 'organization_owner', 'active', ?, ?, ?)",
            (org_b, int(admin["id"]), now, now, now),
        )
        event_a = server.insert_event_from_config(db, {"name": "Evento Alfa", "organization_id": org_a}, "Admin")
        event_b = server.insert_event_from_config(db, {"name": "Evento Beta", "organization_id": org_b}, "Admin")
        encrypted = server.integration_secret_service().encrypt(json.dumps({"api_key": "secret-value", "token": "secret-token"}))
        integration_a = int(db.execute(
            """
            INSERT INTO organization_integrations (
                organization_id, provider, integration_type, name, mode, status,
                configuration_encrypted, metadata_json, created_by, updated_by, created_at, updated_at
            )
            VALUES (?, 'resend', 'email_provider', 'Email Alfa', 'client_owned', 'connected', ?, '{}', 'Admin', 'Admin', ?, ?)
            """,
            (org_a, encrypted, now, now),
        ).lastrowid)
        integration_b = int(db.execute(
            """
            INSERT INTO organization_integrations (
                organization_id, provider, integration_type, name, mode, status,
                configuration_encrypted, metadata_json, created_by, updated_by, created_at, updated_at
            )
            VALUES (?, 'meta', 'whatsapp_provider', 'WhatsApp Beta', 'client_owned', 'connected', ?, '{}', 'Admin', 'Admin', ?, ?)
            """,
            (org_b, encrypted, now, now),
        ).lastrowid)
        context = {
            "tmp": tmp,
            "db": db,
            "original_config": original_config,
            "original_path": original_path,
            "org_a": org_a,
            "org_b": org_b,
            "event_a": event_a,
            "event_b": event_b,
            "integration_a": integration_a,
            "integration_b": integration_b,
            "encrypted": encrypted,
        }
        return context
    except Exception:
        db.close()
        server.DB_CONFIG = original_config
        server.DB_PATH = original_path
        tmp.cleanup()
        raise


def close_context(context: dict[str, Any]) -> None:
    try:
        context["db"].close()
    finally:
        if "tmp" in context:
            context["tmp"].cleanup()
        server.DB_CONFIG = context.get("original_config", server.DB_CONFIG)
        server.DB_PATH = context.get("original_path", server.DB_PATH)


def contract_result(name: str, mode: str, missing: list[str], checks: dict[str, Any]) -> dict[str, Any]:
    status = "omitted" if mode != "live" and missing else "passed"
    return {
        "name": name,
        "mode": mode,
        "status": status,
        "missing_env": missing,
        "checks": checks,
    }
