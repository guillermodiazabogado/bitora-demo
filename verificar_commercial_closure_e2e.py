from __future__ import annotations

import os
import tempfile
from pathlib import Path


tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
root = Path(tmp.name)
os.environ["QR_SQLITE_PATH"] = str(root / "commercial.sqlite3")
os.environ["BITORA_STORAGE_PATH"] = str(root / "storage")
os.environ["QR_REQUIRE_LOGIN"] = ""
os.environ["EMAIL_ENABLED"] = ""
os.environ["WHATSAPP_ENABLED"] = ""

import server  # noqa: E402


def expect(condition, message):
    if not condition:
        raise AssertionError(message)


server.init_db()
now = server.now_iso()

with server.connect() as db:
    org_id = int(db.execute(
        """
        INSERT INTO organizations (public_id, name, legal_name, trade_name, status, plan, created_at, updated_at)
        VALUES ('expo-patagonia-2027', 'EXPO PATAGONIA', 'EXPO PATAGONIA', 'EXPO PATAGONIA', 'active', 'standard', ?, ?)
        """,
        (now, now),
    ).lastrowid)
    event_id = int(db.execute(
        """
        INSERT INTO events (
            organization_id, name, venue, starts_at, ends_at, status, capacity,
            generar_certificados, controlar_asistencia, created_at
        ) VALUES (?, 'EXPO PATAGONIA 2027', 'Centro de Convenciones',
                  '2027-04-10T09:00:00+00:00', '2027-04-10T20:00:00+00:00',
                  'published', 500, 1, 1, ?)
        """,
        (org_id, now),
    ).lastrowid)
    server.ensure_default_types(db, event_id)
    space_id = int(db.execute(
        "INSERT INTO spaces (event_id, name, capacity, status, created_at) VALUES (?, 'Auditorio', 200, 'active', ?)",
        (event_id, now),
    ).lastrowid)

    speakers = ("Ana Sur", "Bruno Lago", "Carla Viento")
    for index in range(5):
        db.execute(
            """
            INSERT INTO activities (
                event_id, space_id, title, starts_at, ends_at, speaker, capacity,
                requiere_asistencia, porcentaje_minimo_asistencia, habilita_certificado,
                status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 80, 1, 80, 1, 'published', ?)
            """,
            (
                event_id,
                space_id,
                f"Charla {index + 1}",
                f"2027-04-10T{10 + index:02d}:00:00+00:00",
                f"2027-04-10T{10 + index:02d}:45:00+00:00",
                speakers[index % len(speakers)],
                now,
            ),
        )

    companies = [f"Empresa {index}" for index in range(1, 6)]
    registrations = []
    for index in range(20):
        payload = {
            "first_name": f"Participante {index + 1}",
            "last_name": "Demo",
            "email": f"participante{index + 1}@example.test",
            "company": companies[index % len(companies)],
            "type": "General" if index % 2 == 0 else "Invitado",
            "actor": "Admin",
            "source": "manual",
        }
        result = server.register_accreditation(db, event_id, payload)
        expect(result["ok"] and not result.get("existing"), "fallo al registrar participante ficticio")
        registrations.append(result)
    duplicate = server.register_accreditation(db, event_id, {
        "first_name": "Participante 1", "last_name": "Demo",
        "email": "participante1@example.test", "company": companies[0], "actor": "Admin",
    })
    expect(duplicate["ok"] and duplicate.get("existing"), "la deduplicacion de participante no funciono")
    expect(int(db.execute("SELECT COUNT(DISTINCT company) AS c FROM people WHERE company <> ''").fetchone()["c"]) == 5, "no persistieron las cinco empresas")

    first = registrations[0]
    activity_id = int(db.execute("SELECT id FROM activities WHERE event_id = ? ORDER BY id LIMIT 1", (event_id,)).fetchone()["id"])
    attendance = server.attendance_service().record_attendance(
        db,
        organization_id=org_id,
        event_id=event_id,
        participant_id=int(first["person_id"]),
        accreditation_id=int(first["id"]),
        activity_id=activity_id,
        attendance_type="ACTIVITY",
        status="PRESENT",
        source="MANUAL",
        actor="Admin",
        occurred_at=now,
        idempotency_key="expo-attendance-1",
    )
    expect(attendance["ok"], "no se registro la asistencia")

    close = server.event_lifecycle_service().close_event(
        db,
        event_id=event_id,
        actor="Admin",
        reason="Finalizacion de demostracion comercial",
        confirmation="FINALIZAR",
    )
    expect(close["ok"] and not close["idempotent"], "no se finalizo el evento")
    repeated_close = server.event_lifecycle_service().close_event(
        db, event_id=event_id, actor="Admin", reason="", confirmation="FINALIZAR"
    )
    expect(repeated_close["idempotent"], "el cierre repetido no fue idempotente")
    blocked = server.register_accreditation(db, event_id, {
        "first_name": "Tardia", "last_name": "Demo", "email": "tardia@example.test", "actor": "Admin",
    })
    expect(not blocked["ok"] and blocked.get("code") == "EVENT_CLOSED", "se permitio inscribir despues del cierre")

    certificate_type_id = int(db.execute(
        """
        INSERT INTO certificate_types (
            organization_id, event_id, code, name, kind, status, created_by, created_at, updated_at
        ) VALUES (?, ?, 'attendance-demo', 'Asistencia', 'ATTENDANCE', 'ACTIVE', 'Admin', ?, ?)
        """,
        (org_id, event_id, now, now),
    ).lastrowid)
    template_id = int(db.execute(
        """
        INSERT INTO certificate_templates (
            organization_id, event_id, certificate_type_id, name, status, created_by, created_at, updated_at
        ) VALUES (?, ?, ?, 'Plantilla EXPO', 'PUBLISHED', 'Admin', ?, ?)
        """,
        (org_id, event_id, certificate_type_id, now, now),
    ).lastrowid)
    version_id = int(db.execute(
        """
        INSERT INTO certificate_template_versions (
            template_id, organization_id, event_id, version_number, content_schema, content_hash,
            renderer_version, status, published_at, published_by, created_by, created_at
        ) VALUES (?, ?, ?, 1, '{}', 'demo-hash', 'bitora_certificate_renderer_v1',
                  'PUBLISHED', ?, 'Admin', 'Admin', ?)
        """,
        (template_id, org_id, event_id, now, now),
    ).lastrowid)
    issuance_id = int(db.execute(
        """
        INSERT INTO certificate_issuances (
            organization_id, event_id, participant_id, certificate_type_id, template_version_id,
            certificate_number, status, issued_at, issued_by, idempotency_key, request_hash,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 'EXPO-2027-0001', 'ISSUED', ?, 'Admin',
                  'expo-certificate-1', 'request-hash', ?, ?)
        """,
        (org_id, event_id, int(first["person_id"]), certificate_type_id, version_id, now, now, now),
    ).lastrowid)

    delivery = server.certificate_delivery_service().queue_email(
        db, organization_id=org_id, event_id=event_id, issuance_id=issuance_id, actor="Admin"
    )
    duplicate_delivery = server.certificate_delivery_service().queue_email(
        db, organization_id=org_id, event_id=event_id, issuance_id=issuance_id, actor="Admin"
    )
    resend = server.certificate_delivery_service().queue_email(
        db,
        organization_id=org_id,
        event_id=event_id,
        issuance_id=issuance_id,
        actor="Admin",
        resend_key="owner-approved-1",
    )
    expect(delivery["queue_id"] == duplicate_delivery["queue_id"] and duplicate_delivery["idempotent"], "la cola Gmail duplico el primer envio")
    expect(resend["queue_id"] != delivery["queue_id"], "el reenvio autorizado no quedo separado")
    history = server.certificate_delivery_service().history(
        db, organization_id=org_id, event_id=event_id, issuance_id=issuance_id
    )
    expect(len(history["items"]) == 2, "el historial de entrega no contiene envio y reenvio")
    db.commit()

with server.connect() as reopened:
    recovered = reopened.execute("SELECT status, closed_at, closed_by FROM events WHERE id = ?", (event_id,)).fetchone()
    expect(recovered and recovered["status"] == "closed" and recovered["closed_at"] and recovered["closed_by"] == "Admin", "el cierre no se recupero al reabrir la base")
    expect(int(reopened.execute("SELECT COUNT(*) AS c FROM accreditations WHERE event_id = ?", (event_id,)).fetchone()["c"]) == 20, "los participantes no se recuperaron")
    expect(int(reopened.execute("SELECT COUNT(*) AS c FROM activities WHERE event_id = ?", (event_id,)).fetchone()["c"]) == 5, "las charlas no se recuperaron")
    expect(int(reopened.execute("SELECT COUNT(*) AS c FROM communication_queue WHERE event_id = ? AND template_code = 'certificate_available'", (event_id,)).fetchone()["c"]) == 2, "la cola Gmail no persistio")

print("Commercial closure E2E (local, synthetic, no external delivery): OK")
