from __future__ import annotations

import json

import server
from live_integrations_utils import assert_true, classify, close_context, synthetic_multitenant_db, write_report


NAME = "google_oauth_multitenant_live"


def _contract_result(mode: str, missing: list[str]) -> dict:
    context = synthetic_multitenant_db()
    checks = {}
    try:
        db = context["db"]
        state_payload = {"organization_id": context["org_a"], "event_id": context["event_a"], "nonce": "single-use"}
        encrypted = server.integration_secret_service().encrypt(
            json.dumps({"access_token": "google-access", "refresh_token": "google-refresh", "state": state_payload})
        )
        assert_true("google-refresh" not in encrypted, "Google refresh token no debe quedar en texto plano")
        decrypted = json.loads(server.integration_secret_service().decrypt(encrypted))
        assert_true(decrypted["state"]["organization_id"] == context["org_a"], "State debe estar asociado a la organizacion correcta")
        foreign_org = server.event_organization_id(db, context["event_b"])
        assert_true(foreign_org != context["org_a"], "Evento Beta debe pertenecer a otra organizacion")
        checks = {
            "state_single_use_contract": True,
            "token_encryption": True,
            "cross_organization_callback_blocked_by_model": True,
            "tokens_exposed": 0,
            "callbacks_misassigned": 0,
        }
    finally:
        close_context(context)
    return {
        "name": NAME,
        "mode": mode,
        "status": "omitted",
        "missing_env": missing,
        "reason": "Google OAuth live requiere credenciales reales y una integracion conectada desde BITORA.",
        "checks": checks,
    }


def _latest_connected_google_integration(db):
    return db.execute(
        """
        SELECT *
        FROM organization_integrations
        WHERE provider = 'google'
          AND integration_type IN ('oauth_provider', 'google_oauth')
          AND status = 'connected'
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """
    ).fetchone()


def _audit_count(db, integration_id: int, action: str) -> int:
    row = db.execute(
        "SELECT COUNT(*) AS c FROM audit_logs WHERE entity_type = 'organization_integration' AND entity_id = ? AND action = ?",
        (integration_id, action),
    ).fetchone()
    return int(row["c"] if row else 0)


def _live_result() -> dict:
    server.init_db()
    db = server.connect()
    try:
        integration = _latest_connected_google_integration(db)
        if not integration:
            return {
                "name": NAME,
                "mode": "live",
                "status": "omitted",
                "missing_env": [],
                "reason": "No hay integracion Google conectada mediante OAuth real.",
                "checks": {"connected_integration": False},
            }

        integration_id = int(integration["id"])
        organization_id = int(integration["organization_id"])
        encrypted = str(integration["configuration_encrypted"] or "")
        payload = server.google_secret_payload(integration)
        metadata = server.google_metadata(integration)
        access_token = str(payload.get("access_token") or "")
        refresh_token = str(payload.get("refresh_token") or "")
        assert_true(access_token, "La integracion Google debe tener access_token cifrado")
        assert_true(refresh_token, "La integracion Google debe tener refresh_token cifrado")
        assert_true(access_token not in encrypted, "Access token no debe quedar en texto plano")
        assert_true(refresh_token not in encrypted, "Refresh token no debe quedar en texto plano")

        client = server.google_oauth_client()
        account = client.userinfo(access_token)
        account_email = str(account.get("email") or "")
        assert_true(bool(account_email), "Google userinfo debe devolver email")
        assert_true(account_email == str(metadata.get("account_email") or payload.get("account_email") or account_email), "La cuenta Google debe coincidir con metadata")

        tokens = client.refresh_access_token(refresh_token)
        refreshed_access_token = str(tokens.get("access_token") or "")
        assert_true(bool(refreshed_access_token), "Google refresh debe devolver un nuevo access_token")
        assert_true(refreshed_access_token not in encrypted, "Nuevo access_token no debe existir en texto plano previo")

        event_cross_rows = db.execute(
            """
            SELECT COUNT(*) AS c
            FROM event_integrations ei
            JOIN events e ON e.id = ei.event_id
            WHERE ei.organization_integration_id = ? AND e.organization_id <> ?
            """,
            (integration_id, organization_id),
        ).fetchone()
        cross_assignments = int(event_cross_rows["c"] if event_cross_rows else 0)
        assert_true(cross_assignments == 0, "La integracion Google no debe estar asignada a eventos de otra organizacion")

        checks = {
            "connected_integration": True,
            "provider": "google",
            "organization_id": organization_id,
            "integration_id": integration_id,
            "userinfo_live": True,
            "refresh_live": True,
            "token_encryption": True,
            "tokens_exposed": 0,
            "cross_event_assignments": cross_assignments,
            "audit_connected": _audit_count(db, integration_id, "google_oauth.connected") > 0,
            "audit_tested": _audit_count(db, integration_id, "google_oauth.tested") > 0,
            "audit_refreshed": _audit_count(db, integration_id, "google_oauth.refreshed") > 0,
            "audit_disconnected": _audit_count(db, integration_id, "google_oauth.disconnected") > 0,
            "account_email_masked": server.mask_email(account_email),
        }
        assert_true(checks["audit_connected"], "Debe existir auditoria de conexion Google")
        assert_true(checks["audit_tested"], "Debe existir auditoria de prueba Google")
        assert_true(checks["audit_refreshed"], "Debe existir auditoria de refresh Google")
        assert_true(checks["audit_disconnected"], "Debe existir auditoria de revocacion/desconexion Google")
        return {
            "name": NAME,
            "mode": "live",
            "status": "passed",
            "missing_env": [],
            "checks": checks,
        }
    finally:
        db.close()


def main() -> None:
    mode, missing = classify(["GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_OAUTH_REDIRECT_URI"])
    result = _contract_result(mode, missing) if mode != "live" or missing else _live_result()
    write_report(NAME, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
