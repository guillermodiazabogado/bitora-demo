from __future__ import annotations

import hashlib
import os
import tempfile
import threading
from pathlib import Path

tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
root = Path(tmp.name)
os.environ["QR_SQLITE_PATH"] = str(root / "v4_3_certificates.sqlite3")
os.environ["BITORA_ATTENDANCE_V4_ENABLED"] = "true"
os.environ["BITORA_ATTENDANCE_CLOSURE_ELIGIBILITY_V4_ENABLED"] = "true"
os.environ["BITORA_CERTIFICATES_V4_ENABLED"] = "true"
os.environ["BITORA_STORAGE_PATH"] = str(root / "storage")
os.environ["QR_REQUIRE_LOGIN"] = ""

import server  # noqa: E402


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def seed(db):
    now = server.now_iso()
    orgs = []
    events = []
    activities = {}
    people = {}
    accreditations = {}
    for org_name in ("Alfa V4.3", "Beta V4.3"):
        cur = db.execute(
            """
            INSERT INTO organizations (public_id, name, legal_name, trade_name, status, plan, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'active', 'standard', ?, ?)
            """,
            (org_name.lower().replace(" ", "_"), org_name, org_name, org_name, now, now),
        )
        orgs.append(int(cur.lastrowid))
    for org_index, org_id in enumerate(orgs):
        for event_index in range(2):
            cur = db.execute(
                "INSERT INTO events (organization_id, name, starts_at, ends_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (org_id, f"Evento Certificados {org_index}-{event_index}", "2026-10-01T09:00:00+00:00", "2026-10-01T18:00:00+00:00", now),
            )
            event_id = int(cur.lastrowid)
            events.append(event_id)
            space = db.execute("INSERT INTO spaces (event_id, name, capacity, status, created_at) VALUES (?, ?, 100, 'active', ?)", (event_id, f"Sala {event_id}", now))
            activities[event_id] = []
            for activity_index in range(2):
                activity = db.execute(
                    """
                    INSERT INTO activities (
                        event_id, space_id, title, starts_at, ends_at, capacity,
                        reservation_mode, requiere_asistencia, porcentaje_minimo_asistencia,
                        habilita_certificado, status, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, 100, 'optional', 1, 80, 1, 'published', ?)
                    """,
                    (event_id, int(space.lastrowid), f"Actividad {activity_index}", "2026-10-01T10:00:00+00:00", "2026-10-01T11:00:00+00:00", now),
                )
                activities[event_id].append(int(activity.lastrowid))
            people[event_id] = []
            accreditations[event_id] = []
            for person_index in range(3):
                person = db.execute(
                    """
                    INSERT INTO people (first_name, last_name, email, source, device_type, created_at)
                    VALUES (?, ?, ?, 'test', 'desktop', ?)
                    """,
                    (f"Persona{org_index}{event_index}{person_index}", "V43", f"v43-{org_index}-{event_index}-{person_index}@example.test", now),
                )
                person_id = int(person.lastrowid)
                people[event_id].append(person_id)
                acc = db.execute(
                    "INSERT INTO accreditations (event_id, person_id, token, type, status, created_at) VALUES (?, ?, ?, 'General', 'active', ?)",
                    (event_id, person_id, f"V43TOKEN{org_index}{event_index}{person_index}", now),
                )
                accreditations[event_id].append(int(acc.lastrowid))
    return {"orgs": orgs, "events": events, "activities": activities, "people": people, "accreditations": accreditations}


def prepare_closure(db, data, event_id, org_id, prefix):
    attendance = server.attendance_service()
    activity_1, activity_2 = data["activities"][event_id]
    p1, p2, _p3 = data["people"][event_id]
    a1, a2, _a3 = data["accreditations"][event_id]
    attendance.record_attendance(db, organization_id=org_id, event_id=event_id, participant_id=p1, accreditation_id=a1, activity_id=activity_1, attendance_type="ACTIVITY", status="PRESENT", source="MANUAL", actor="Admin", occurred_at="2026-10-01T10:05:00+00:00", idempotency_key=f"{prefix}-att-1")
    attendance.record_attendance(db, organization_id=org_id, event_id=event_id, participant_id=p2, accreditation_id=a2, activity_id=activity_1, attendance_type="ACTIVITY", status="PRESENT", source="MANUAL", actor="Admin", occurred_at="2026-10-01T10:05:00+00:00", idempotency_key=f"{prefix}-att-2")
    attendance.record_attendance(db, organization_id=org_id, event_id=event_id, participant_id=p2, accreditation_id=a2, activity_id=activity_2, attendance_type="ACTIVITY", status="PRESENT", source="MANUAL", actor="Admin", occurred_at="2026-10-01T11:05:00+00:00", idempotency_key=f"{prefix}-att-3")
    rule_set = attendance.create_rule_set(db, organization_id=org_id, event_id=event_id, actor="Admin", name=f"Regla {prefix}", scope_type="EVENT")
    version = attendance.create_rule_set_version(
        db,
        organization_id=org_id,
        event_id=event_id,
        rule_set_id=rule_set["item"]["id"],
        actor="Admin",
        configuration={
            "minimum_attendance_percentage": "50",
            "mandatory_activity_ids": [activity_1],
            "require_all_mandatory_activities": True,
            "allow_manual_override": True,
        },
    )
    attendance.publish_rule_set_version(db, organization_id=org_id, event_id=event_id, rule_set_id=rule_set["item"]["id"], version_id=version["item"]["id"], actor="Admin", idempotency_key=f"{prefix}-publish")
    closure = attendance.close_attendance(db, organization_id=org_id, event_id=event_id, actor="Admin", rule_set_version_id=version["item"]["id"], scope_type="EVENT", cutoff_at="2026-10-01T23:59:00+00:00", idempotency_key=f"{prefix}-close")
    decisions = attendance.participant_eligibility(db, organization_id=org_id, event_id=event_id, participant_id=p1)["items"]
    decision_p1 = decisions[0]
    decision_p3 = attendance.override_eligibility(db, organization_id=org_id, event_id=event_id, participant_id=data["people"][event_id][2], actor="Admin", manual_result="MANUALLY_APPROVED", reason="Aprobacion manual controlada", closure_id=closure["item"]["id"], idempotency_key=f"{prefix}-override")["item"]
    return {"closure": closure["item"], "eligible_decision": decision_p1, "manual_decision": decision_p3}


def main():
    server.init_db()
    service = server.certificate_service()
    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        data = seed(db)
        db.execute("COMMIT")

    org_id = data["orgs"][0]
    event_id = data["events"][0]
    batch_event_id = data["events"][1]
    other_org_id = data["orgs"][1]
    other_event_id = data["events"][2]
    eligible_participant = data["people"][event_id][0]
    not_eligible_participant = data["people"][event_id][1]
    manual_participant = data["people"][event_id][2]

    with server.connect() as db:
        assert_true(server.certificates_v4_enabled(db, event_id), "feature flag V4.3 no habilitado")
        assert_true(server.certificates_v4_dependencies_enabled(db, event_id), "dependencias V4.1/V4.2 no habilitadas")

    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        closure_data = prepare_closure(db, data, event_id, org_id, "v43-main")
        batch_closure_data = prepare_closure(db, data, batch_event_id, org_id, "v43-batch")
        cert_type = service.create_certificate_type(db, organization_id=org_id, event_id=event_id, actor="Admin", code="ATTENDANCE", name="Certificado de asistencia", kind="ATTENDANCE")["item"]
        template = service.create_template(db, organization_id=org_id, event_id=event_id, actor="Admin", certificate_type_id=cert_type["id"], name="Plantilla asistencia")["item"]
        version = service.create_template_version(
            db,
            organization_id=org_id,
            template_id=template["id"],
            actor="Admin",
            content_schema={
                "title": "Certificado de {{certificate_type}}",
                "subtitle": "{{organization_name}}",
                "body": "Se certifica que {{participant_name}} participo en {{event_name}}.",
                "footer": "Validar con codigo {{verification_code}}",
                "location": "Buenos Aires",
                "signatures": ["Direccion academica"],
            },
        )["item"]
        published = service.publish_template_version(db, organization_id=org_id, template_id=template["id"], version_id=version["id"], actor="Admin", idempotency_key="v43-template-publish")["item"]
        assert_true(published["status"] == "PUBLISHED", "plantilla no publicada")
        original_hash = published["content_hash"]
        preview = service.preview_template_version(db, organization_id=org_id, template_id=template["id"], version_id=version["id"])
        assert_true(preview["item"]["content_hash"] == original_hash, "preview no usa version publicada")
        try:
            service.create_template_version(db, organization_id=org_id, template_id=template["id"], actor="Admin", content_schema={"body": "<script>alert(1)</script>"})
            raise AssertionError("plantilla maliciosa aceptada")
        except server.CertificateDomainError as exc:
            assert_true(exc.code == "CERTIFICATE_TEMPLATE_INVALID", "error de sanitizacion incorrecto")
        issued = service.issue_certificate(db, organization_id=org_id, event_id=event_id, actor="Admin", participant_id=eligible_participant, certificate_type_id=cert_type["id"], template_version_id=version["id"], eligibility_decision_id=closure_data["eligible_decision"]["id"], idempotency_key="v43-issue-eligible")
        issuance = issued["item"]
        assert_true(issuance["status"] == "ISSUED", "certificado no emitido")
        assert_true(issuance["document"]["sha256_hash"], "hash de documento ausente")
        assert_true(issuance["attendance_closure_id"] == closure_data["closure"]["id"], "emision no referencia cierre")
        assert_true(issuance["evaluation_id"], "emision no referencia evaluacion")
        assert_true(issuance["eligibility_decision_id"] == closure_data["eligible_decision"]["id"], "emision no referencia decision")
        item, content = service.document_bytes(db, organization_id=org_id, event_id=event_id, issuance_id=issuance["id"])
        assert_true(content.startswith(b"%PDF"), "documento no es PDF")
        assert_true(hashlib.sha256(content).hexdigest() == item["document"]["sha256_hash"], "hash PDF inconsistente")
        verify = service.verify_public(db, token=issued["verification_token"])
        assert_true(verify["valid"], "verificacion publica no valida certificado emitido")
        assert_true("@" not in verify["participant"], "verificacion expone email")
        replay = service.issue_certificate(db, organization_id=org_id, event_id=event_id, actor="Admin", participant_id=eligible_participant, certificate_type_id=cert_type["id"], template_version_id=version["id"], eligibility_decision_id=closure_data["eligible_decision"]["id"], idempotency_key="v43-issue-eligible")
        assert_true(replay["idempotent"], "emision repetida no fue idempotente")
        try:
            service.issue_certificate(db, organization_id=org_id, event_id=event_id, actor="Admin", participant_id=not_eligible_participant, certificate_type_id=cert_type["id"], template_version_id=version["id"], eligibility_decision_id=closure_data["eligible_decision"]["id"], idempotency_key="v43-issue-wrong-decision")
            raise AssertionError("decision de otro participante aceptada")
        except server.CertificateDomainError as exc:
            assert_true(exc.code == "CERTIFICATE_ELIGIBILITY_REQUIRED", "decision cruzada no fue rechazada")
        manual_issue = service.issue_certificate(db, organization_id=org_id, event_id=event_id, actor="Admin", participant_id=manual_participant, certificate_type_id=cert_type["id"], template_version_id=version["id"], eligibility_decision_id=closure_data["manual_decision"]["id"], idempotency_key="v43-issue-manual")
        assert_true(manual_issue["item"]["status"] == "ISSUED", "override aprobado no fue respetado")
        revoked = service.revoke_certificate(db, organization_id=org_id, event_id=event_id, issuance_id=issuance["id"], actor="Admin", reason="Prueba de revocacion")
        assert_true(revoked["item"]["status"] == "REVOKED", "revocacion no actualizo estado")
        assert_true(not service.verify_public(db, token=issued["verification_token"])["valid"], "certificado revocado sigue valido")
        reissued = service.reissue_certificate(db, organization_id=org_id, event_id=event_id, issuance_id=issuance["id"], actor="Admin", reason="Correccion de documento", idempotency_key="v43-reissue-001")
        assert_true(reissued["item"]["status"] == "ISSUED", "reemision no emitio nuevo certificado")
        assert_true(reissued["item"]["id"] != issuance["id"], "reemision sobrescribio certificado")
        assert_true(reissued["item"]["certificate_number"] != issuance["certificate_number"], "numero reutilizado en reemision")
        try:
            service.issue_certificate(db, organization_id=other_org_id, event_id=event_id, actor="Admin", participant_id=eligible_participant, certificate_type_id=cert_type["id"], template_version_id=version["id"], eligibility_decision_id=closure_data["eligible_decision"]["id"], idempotency_key="v43-cross-org")
            raise AssertionError("emision cross-org aceptada")
        except server.CertificateDomainError as exc:
            assert_true(exc.code in {"CERTIFICATE_TYPE_NOT_FOUND", "CERTIFICATE_SCOPE_MISMATCH"}, "error cross-org incorrecto")
        try:
            service.issue_certificate(db, organization_id=org_id, event_id=other_event_id, actor="Admin", participant_id=eligible_participant, certificate_type_id=cert_type["id"], template_version_id=version["id"], eligibility_decision_id=closure_data["eligible_decision"]["id"], idempotency_key="v43-cross-event")
            raise AssertionError("emision cross-event aceptada")
        except server.CertificateDomainError as exc:
            assert_true(exc.code == "CERTIFICATE_SCOPE_MISMATCH", "error cross-event incorrecto")
        batch_type = service.create_certificate_type(db, organization_id=org_id, event_id=batch_event_id, actor="Admin", code="BATCH_ATT", name="Certificado batch", kind="ATTENDANCE")["item"]
        batch_template = service.create_template(db, organization_id=org_id, event_id=batch_event_id, actor="Admin", certificate_type_id=batch_type["id"], name="Plantilla batch")["item"]
        batch_version = service.create_template_version(db, organization_id=org_id, template_id=batch_template["id"], actor="Admin", content_schema={"title": "Batch {{certificate_number}}", "body": "{{participant_name}} - {{event_name}}", "footer": "BITORA"})["item"]
        service.publish_template_version(db, organization_id=org_id, template_id=batch_template["id"], version_id=batch_version["id"], actor="Admin", idempotency_key="v43-batch-template-publish")
        batch = service.create_batch(db, organization_id=org_id, event_id=batch_event_id, actor="Admin", certificate_type_id=batch_type["id"], template_version_id=batch_version["id"], idempotency_key="v43-batch-001")
        assert_true(batch["item"]["success_count"] >= 2, "batch no emitio elegibles")
        payload = server.EventBackupService(server.BACKUP_DIR, server.connect, server.DB_LOCK, server.APP_VERSION, server.STORAGE)._event_payload(event_id, "test")
        for table in ("certificate_types", "certificate_templates", "certificate_template_versions", "certificate_issuances", "certificate_documents", "certificate_verification_tokens", "certificate_revocations", "certificate_reissuances"):
            assert_true(table in payload["tables"], f"backup no incluye {table}")
        audit_count = db.execute("SELECT COUNT(*) AS c FROM audit_logs WHERE event_id = ? AND action LIKE 'certificates.%'", (event_id,)).fetchone()["c"]
        assert_true(int(audit_count) >= 6, "auditoria de certificados insuficiente")
        numbers = db.execute("SELECT event_id, certificate_number, COUNT(*) AS c FROM certificate_issuances WHERE organization_id = ? GROUP BY event_id, certificate_number HAVING COUNT(*) > 1", (org_id,)).fetchall()
        assert_true(not numbers, "numeracion duplicada")
        db.execute("COMMIT")

    bundle = server.event_backup_service().create_event_bundle(event_id, "test")
    raw = bundle.read_bytes()
    restored = server.event_restore_service().restore_bytes(raw, mode="new_event", actor="test", new_event_name="Evento V4.3 restaurado")
    assert_true(restored["ok"], "restore de evento con certificados fallo")
    restored_event_id = int(restored["event_id"])
    with server.connect() as db:
        restored_doc = db.execute("SELECT * FROM certificate_documents WHERE event_id = ? LIMIT 1", (restored_event_id,)).fetchone()
        assert_true(restored_doc and str(restored_doc["storage_key"]).startswith(f"events/{restored_event_id}/certificates/"), "storage de certificado no fue remapeado")

    def concurrent_issue(results):
        with server.DB_LOCK, server.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute("SELECT * FROM certificate_issuances WHERE event_id = ? AND status = 'ISSUED' ORDER BY id DESC LIMIT 1", (event_id,)).fetchone()
                service.revoke_certificate(db, organization_id=org_id, event_id=event_id, issuance_id=int(row["id"]), actor="Admin", reason="Revocacion concurrente")
                db.execute("COMMIT")
                results.append("ok")
            except Exception as exc:
                db.execute("ROLLBACK")
                results.append(exc)

    results = []
    threads = [threading.Thread(target=concurrent_issue, args=(results,)) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    with server.connect() as db:
        duplicate_revocations = db.execute("SELECT issuance_id, COUNT(*) AS c FROM certificate_revocations GROUP BY issuance_id HAVING COUNT(*) > 1").fetchall()
        assert_true(not duplicate_revocations, "revocaciones duplicadas")
        assert_true(server.attendance_closure_v4_enabled(db, event_id), "regresion V4.2 flag")
        assert_true(server.certificates_v4_enabled(db, event_id), "regresion V4.3 flag")

    print("V4.3 certificates foundation: OK")


if __name__ == "__main__":
    try:
        main()
    finally:
        tmp.cleanup()
