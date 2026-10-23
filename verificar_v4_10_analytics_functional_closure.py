import json
import os
import tempfile
from pathlib import Path

tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
root = Path(tmp.name)
os.environ["QR_SQLITE_PATH"] = str(root / "v4_10_analytics.sqlite3")
os.environ["BITORA_STORAGE_PATH"] = str(root / "storage")
os.environ["BITORA_ATTENDANCE_V4_ENABLED"] = "true"
os.environ["BITORA_ATTENDANCE_CLOSURE_ELIGIBILITY_V4_ENABLED"] = "true"
os.environ["BITORA_CERTIFICATES_V4_ENABLED"] = "true"
os.environ["BITORA_SURVEYS_V4_ENABLED"] = "true"
os.environ["BITORA_SPEAKERS_V4_ENABLED"] = "true"
os.environ["BITORA_ZONE_PERMISSIONS_V4_ENABLED"] = "true"
os.environ["BITORA_HISTORY_AUTOCOMPLETE_V4_ENABLED"] = "true"
os.environ["BITORA_OPERATIONS_CENTER_V4_ENABLED"] = "true"
os.environ["BITORA_COMMUNICATIONS_V4_ENABLED"] = "true"
os.environ["BITORA_COMMUNICATIONS_AUTOMATION_V4_ENABLED"] = "true"
os.environ["BITORA_ANALYTICS_V4_ENABLED"] = "true"
os.environ["BITORA_ANALYTICS_EXPORTS_V4_ENABLED"] = "true"
os.environ["BITORA_ANALYTICS_COMPARISON_V4_ENABLED"] = "true"
os.environ["BITORA_COMMUNICATIONS_LIVE_MODE_ENABLED"] = "false"
os.environ["QR_REQUIRE_LOGIN"] = ""

import server  # noqa: E402
from backend.services.analytics_closure import AnalyticsClosureError  # noqa: E402
from backend.services.backup import EventBackupService, EventRestoreService  # noqa: E402


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def insert_matching(db, table, values):
    columns = {row["name"]: row for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
    payload = {}
    now = server.now_iso()
    for name, meta in columns.items():
        if name == "id":
            continue
        if name in values:
            payload[name] = values[name]
        elif int(meta["notnull"] or 0) and meta["dflt_value"] is None:
            column_type = str(meta["type"] or "").upper()
            if name.endswith("_id"):
                payload[name] = values.get("event_id") or values.get("organization_id") or 1
            elif "INTEGER" in column_type:
                payload[name] = 0
            else:
                payload[name] = now if name.endswith("_at") else ""
    if not payload:
        return 0
    cols = list(payload)
    cur = db.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join(['?'] * len(cols))})", [payload[col] for col in cols])
    return int(cur.lastrowid or 0)


def seed_event(db, org_id, public_id, name, participants=8):
    now = server.now_iso()
    event_id = insert_matching(
        db,
        "events",
        {
            "organization_id": org_id,
            "public_id": public_id,
            "name": name,
            "starts_at": "2027-03-01T09:00:00+00:00",
            "ends_at": "2027-03-01T18:00:00+00:00",
            "status": "draft",
            "capacity": 200,
            "created_at": now,
        },
    )
    for flag in [
        "attendance_v4_enabled",
        "attendance_closure_eligibility_v4_enabled",
        "certificates_v4_enabled",
        "surveys_v4_enabled",
        "speakers_v4_enabled",
        "zone_permissions_v4_enabled",
        "history_autocomplete_v4_enabled",
        "operations_center_v4_enabled",
        "communications_v4_enabled",
        "communications_automation_v4_enabled",
        "analytics_v4_enabled",
    ]:
        db.execute(
            "INSERT OR REPLACE INTO feature_flags (flag_key,scope_type,scope_id,enabled,updated_by,updated_at) VALUES (?,?,?,?,?,?)",
            (flag, "event", event_id, 1, "verificador", now),
        )
    activity_ids = []
    for index in range(2):
        space_id = insert_matching(db, "spaces", {"event_id": event_id, "name": f"Sala {index + 1}", "capacity": 80, "status": "active", "created_at": now})
        activity_id = insert_matching(db, "activities", {"event_id": event_id, "space_id": space_id, "title": f"Actividad {index + 1}", "capacity": 60, "status": "active", "starts_at": "2027-03-01T10:00:00+00:00", "ends_at": "2027-03-01T11:00:00+00:00", "created_at": now})
        activity_ids.append(activity_id)
    acc_ids = []
    for index in range(participants):
        person_id = insert_matching(db, "people", {"first_name": f"Persona{index}", "last_name": "Analytics", "email": f"v410-{public_id}-{index}@example.test", "phone": f"5491100001{index:03d}", "created_at": now})
        acc_id = insert_matching(db, "accreditations", {"event_id": event_id, "person_id": person_id, "type": "General", "token": f"V410-{public_id}-{index}", "status": "active", "source": "web", "checked_in_at": now if index < participants // 2 else None, "checked_in_by": "qa" if index < participants // 2 else "", "created_at": now})
        acc_ids.append(acc_id)
        if index < 5:
            insert_matching(db, "reservations", {"event_id": event_id, "activity_id": activity_ids[index % 2], "accreditation_id": acc_id, "status": "confirmed", "created_at": now})
            insert_matching(db, "activity_attendance", {"event_id": event_id, "activity_id": activity_ids[index % 2], "accreditation_id": acc_id, "status": "Presente", "recorded_at": now, "recorded_by": "qa"})
            insert_matching(db, "access_logs", {"event_id": event_id, "activity_id": activity_ids[index % 2], "accreditation_id": acc_id, "token": f"V410-{public_id}-{index}", "result": "granted", "checkpoint": "Ingreso", "access_point": "Puerta A", "created_at": now})
    zone_id = insert_matching(db, "event_zones", {"organization_id": org_id, "event_id": event_id, "name": "Backstage", "code": f"Z-{public_id}", "status": "ACTIVE", "created_at": now, "updated_at": now})
    insert_matching(db, "zone_access_validations", {"organization_id": org_id, "event_id": event_id, "zone_id": zone_id, "accreditation_id": acc_ids[0], "decision": "allowed", "reason": "", "idempotency_key": f"zone-{public_id}", "created_at": now})
    speaker_id = insert_matching(db, "speaker_profiles", {"organization_id": org_id, "public_id": f"sp-{public_id}", "display_name": "Speaker Demo", "status": "published", "created_at": now, "updated_at": now})
    insert_matching(db, "speaker_event_assignments", {"organization_id": org_id, "event_id": event_id, "speaker_profile_id": speaker_id, "status": "CONFIRMED", "role": "speaker", "created_at": now, "updated_at": now})
    insert_matching(db, "speaker_activity_assignments", {"organization_id": org_id, "event_id": event_id, "speaker_profile_id": speaker_id, "activity_id": activity_ids[0], "role": "speaker", "created_at": now})
    for acc_id in acc_ids[:4]:
        insert_matching(db, "certificate_eligibility", {"event_id": event_id, "activity_id": activity_ids[0], "accreditation_id": acc_id, "porcentaje": 100, "elegible": 1, "estado": "Elegible", "fecha_calculo": now})
    template = insert_matching(db, "communication_v4_templates", {"organization_id": org_id, "event_id": event_id, "channel": "email", "name": "Aviso", "status": "APPROVED", "created_by": "qa", "created_at": now, "updated_at": now})
    template_version = insert_matching(db, "communication_v4_template_versions", {"organization_id": org_id, "event_id": event_id, "template_id": template, "version_number": 1, "subject": "QA", "content": "BITORA STAGING", "variables_json": "[]", "status": "APPROVED", "content_hash": f"hash-{public_id}", "created_by": "qa", "created_at": now})
    segment = insert_matching(db, "communication_v4_segments", {"organization_id": org_id, "event_id": event_id, "name": "Todos QA", "rules_json": "{}", "status": "ACTIVE", "created_by": "qa", "created_at": now, "updated_at": now})
    db.execute("UPDATE communication_v4_templates SET current_version_id = ? WHERE id = ?", (template_version, template))
    campaign = insert_matching(db, "communication_v4_campaigns", {"organization_id": org_id, "event_id": event_id, "name": "Campana QA", "channel": "email", "template_id": template, "template_version_id": template_version, "segment_id": segment, "status": "COMPLETED", "safe_mode": 1, "live_mode": 0, "recipient_count": 2, "sent_count": 2, "created_by": "qa", "created_at": now, "updated_at": now})
    msg = insert_matching(db, "communication_v4_messages", {"organization_id": org_id, "event_id": event_id, "campaign_id": campaign, "channel": "email", "recipient": "qa@example.test", "status": "sent", "provider": "sink", "provider_message_id": f"sink-{public_id}-1", "idempotency_key": f"msg-{public_id}-1", "created_by": "qa", "created_at": now, "updated_at": now})
    insert_matching(db, "communication_v4_deliveries", {"organization_id": org_id, "event_id": event_id, "message_id": msg, "channel": "email", "provider": "sink", "provider_message_id": f"sink-{public_id}-1", "status": "delivered", "created_at": now, "updated_at": now})
    insert_matching(db, "operations_center_incidents", {"organization_id": org_id, "event_id": event_id, "title": "Incidente cerrado", "category": "GENERAL", "severity": "LOW", "status": "CLOSED", "reporter": "qa", "created_at": now, "updated_at": now})
    insert_matching(db, "operations_center_tasks", {"organization_id": org_id, "event_id": event_id, "title": "Tarea QA", "status": "OPEN", "created_by": "qa", "created_at": now, "updated_at": now})
    return event_id


def main():
    server.init_db()
    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        now = server.now_iso()
        org_a = insert_matching(db, "organizations", {"public_id": "analytics-a", "name": "Analytics Alfa", "legal_name": "Analytics Alfa", "trade_name": "Analytics Alfa", "status": "active", "plan": "standard", "created_at": now, "updated_at": now})
        org_b = insert_matching(db, "organizations", {"public_id": "analytics-b", "name": "Analytics Beta", "legal_name": "Analytics Beta", "trade_name": "Analytics Beta", "status": "active", "plan": "standard", "created_at": now, "updated_at": now})
        event_a = seed_event(db, org_a, "alfa", "Evento Analytics Alfa")
        event_a2 = seed_event(db, org_a, "alfa2", "Evento Analytics Alfa 2", participants=5)
        event_b = seed_event(db, org_b, "beta", "Evento Analytics Beta", participants=4)
        db.execute("COMMIT")

    service = server.analytics_closure_service()
    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        definitions = service.metric_definitions()
        check(len(definitions["items"]) >= 10, "catalogo de metricas incompleto")
        overview = service.overview(db, organization_id=org_a, event_id=event_a, actor="tester")
        check(overview["sections"]["registrations"]["total"] == 8, "total de inscripciones incorrecto")
        check(overview["sections"]["attendance"]["attendees"] >= 4, "asistencia no calculada")
        check(overview["sections"]["communications"]["live_mode_campaigns"] == 0, "Live Mode mezclado en analytics")
        snapshot = service.create_snapshot(db, organization_id=org_a, event_id=event_a, actor="tester")
        report = service.create_report(db, organization_id=org_a, event_id=event_a, actor="tester", data={"snapshot_id": snapshot["snapshot_id"], "title": "Reporte =seguro"})
        exported = service.export_report(db, organization_id=org_a, event_id=event_a, report_id=report["report"]["id"], actor="tester", export_format="csv")
        check(exported["checksum"] and "access_token" not in exported["content"], "exportacion insegura")
        check("'=seguro" in exported["file_name"] or exported["file_name"].endswith(".csv"), "nombre de archivo invalido")
        closure = service.create_closure_review(db, organization_id=org_a, event_id=event_a, actor="tester", data={"run_id": "V4-CLOSURE-VERIFIER"})
        check(closure["review"]["status"] in {"READY_FOR_APPROVAL", "APPROVED"}, "cierre funcional con bloqueos inesperados")
        approved = service.approve_closure_review(db, organization_id=org_a, event_id=event_a, review_id=closure["review"]["id"], actor="approver")
        check(approved["review"]["status"] == "APPROVED", "cierre funcional no aprobado")
        comparison = service.compare_events(db, organization_id=org_a, event_ids=[event_a, event_a2], actor="tester")
        check(len(comparison["items"]) == 2, "comparacion intra-organizacion fallo")
        try:
            service.compare_events(db, organization_id=org_a, event_ids=[event_a, event_b], actor="tester")
            raise AssertionError("comparacion cross-tenant permitida")
        except AnalyticsClosureError:
            pass
        try:
            service.overview(db, organization_id=org_b, event_id=event_a, actor="tester")
            raise AssertionError("overview cross-tenant permitido")
        except AnalyticsClosureError:
            pass
        db.execute("COMMIT")

    backup_dir = root / "backups"
    backup = EventBackupService(backup_dir, server.connect, server.DB_LOCK, app_version=server.APP_VERSION, storage=server.STORAGE).create_event_bundle(event_a, actor="tester")
    restore = EventRestoreService(server.connect, server.DB_LOCK, server.make_token, server.now_iso, app_version=server.APP_VERSION, backup_service=None, storage=server.STORAGE)
    restored = restore.restore_bytes(backup.read_bytes(), actor="tester", mode="new_event", new_event_name="Evento Analytics Restaurado")
    check(restored["ok"], "restore V4.10 fallo")
    with server.connect() as db:
        new_event_id = int(restored["event_id"])
        restored_snapshot = db.execute("SELECT status FROM analytics_v4_snapshots WHERE event_id = ? LIMIT 1", (new_event_id,)).fetchone()
        restored_report = db.execute("SELECT status FROM analytics_v4_reports WHERE event_id = ? LIMIT 1", (new_event_id,)).fetchone()
        restored_closure = db.execute("SELECT status, approved_by FROM functional_closure_reviews WHERE event_id = ? LIMIT 1", (new_event_id,)).fetchone()
        check(restored_snapshot and restored_snapshot["status"] == "STALE", "snapshot restaurado no quedo reconstruible")
        check(restored_report and restored_report["status"] == "RESTORED_REVIEW", "reporte restaurado inseguro")
        check(restored_closure and restored_closure["status"] == "RESTORED_REVIEW" and not restored_closure["approved_by"], "cierre restaurado aprobado silenciosamente")
        restored_overview = service.overview(db, organization_id=org_a, event_id=new_event_id, actor="tester")
        check(restored_overview["sections"]["registrations"]["total"] == 8, "metricas post-restore incorrectas")
    print("V4.10 analytics functional closure: OK")


if __name__ == "__main__":
    try:
        main()
    finally:
        tmp.cleanup()
