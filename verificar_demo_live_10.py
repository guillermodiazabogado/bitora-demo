from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("QR_REQUIRE_LOGIN", "0")
os.environ.setdefault("EMAIL_ENABLED", "false")
os.environ.setdefault("WHATSAPP_ENABLED", "false")
os.environ["QR_DB_ENGINE"] = "sqlite"
os.environ["DATABASE_ENGINE"] = "sqlite"

import server


def insert_participant(db, event_id: int, index: int, kind: str, acc_type: str):
    person_id = int(
        db.execute(
            """
            INSERT INTO people (first_name, last_name, email, phone, dni, company, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"Demo{index:02d}",
                "Live",
                f"demo.live.{index:02d}@bitora.test",
                f"54929945221{index:02d}",
                f"300000{index:02d}",
                "BITORA QA",
                server.now_iso(),
            ),
        ).lastrowid
    )
    accreditation_id = int(
        db.execute(
            """
            INSERT INTO accreditations (event_id, person_id, type, token, status, checked_in_at, checked_in_by, access_count, created_at)
            VALUES (?, ?, ?, ?, 'active', NULL, '', 0, ?)
            """,
            (event_id, person_id, acc_type, f"EVT-LIVE10{index:02d}", server.now_iso()),
        ).lastrowid
    )
    server.upsert_communication_preference(
        db,
        person_id,
        {
            "email": f"demo.live.{index:02d}@bitora.test",
            "phone": f"54929945221{index:02d}",
            "acepta_email": 1,
            "acepta_whatsapp": 1,
            "canal_preferido": "whatsapp" if index % 2 else "email",
        },
    )
    db.execute(
        "INSERT INTO audit_logs (event_id, actor, action, entity_type, entity_id, payload, created_at) VALUES (?, ?, 'demo_live_10.participant_created', 'accreditation', ?, ?, ?)",
        (event_id, kind, accreditation_id, json.dumps({"source": kind}, ensure_ascii=False), server.now_iso()),
    )
    return accreditation_id


def count(db, sql: str, params: tuple = ()) -> int:
    return int(db.execute(sql, params).fetchone()["c"] or 0)


def main() -> None:
    fd, db_file = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    original_path = server.DB_PATH
    server.DB_PATH = server.Path(db_file)
    output_dir = Path("output") / "demo_live_10"
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        server.init_db()
        with server.connect() as db:
            event_id = int(
                db.execute(
                    """
                    INSERT INTO events (
                        name, description, venue, starts_at, ends_at, status, project_type,
                        capacity, activities_enabled, capacity_control_enabled, waitlist_enabled,
                        generar_certificados, controlar_asistencia, attendance_mode, created_at
                    )
                    VALUES (
                        'BITORA Demo Live 10',
                        'Evento controlado para validar circuito operativo completo',
                        'Sala Demo BITORA',
                        '2026-07-20T09:00:00',
                        '2026-07-20T13:00:00',
                        'published',
                        'conference',
                        10,
                        1,
                        1,
                        1,
                        1,
                        1,
                        'entry_only',
                        ?
                    )
                    """,
                    (server.now_iso(),),
                ).lastrowid
            )
            server.ensure_default_types(db, event_id)
            server.ensure_super_admin_event_access(db, event_id)
            users = {row["name"]: row for row in db.execute("SELECT * FROM users").fetchall()}
            for user_name, role in [
                ("Productor", "Productor"),
                ("Recepcion", "Operador de recepcion"),
                ("Acceso", "Operador de acceso"),
                ("Comunicaciones", "Comunicaciones"),
            ]:
                if user_name in users:
                    server.assign_user_to_event(db, int(users[user_name]["id"]), event_id, role)

            db.execute("DELETE FROM accreditation_types WHERE event_id = ?", (event_id,))
            db.execute("INSERT INTO accreditation_types (event_id, name, capacity, access_enabled, created_at) VALUES (?, 'Participante General', 8, 1, ?)", (event_id, server.now_iso()))
            db.execute("INSERT INTO accreditation_types (event_id, name, capacity, access_enabled, created_at) VALUES (?, 'Invitado Especial', 2, 1, ?)", (event_id, server.now_iso()))

            sala_principal = int(db.execute("INSERT INTO spaces (event_id, name, capacity, responsible, created_at) VALUES (?, 'Sala Principal', 10, 'Produccion', ?)", (event_id, server.now_iso())).lastrowid)
            sala_taller = int(db.execute("INSERT INTO spaces (event_id, name, capacity, responsible, created_at) VALUES (?, 'Sala Taller', 5, 'Taller', ?)", (event_id, server.now_iso())).lastrowid)
            apertura = int(db.execute("INSERT INTO activities (event_id, space_id, title, starts_at, ends_at, capacity, reservation_mode, requiere_asistencia, porcentaje_minimo_asistencia, habilita_certificado, status, created_at) VALUES (?, ?, 'Apertura', '2026-07-20T09:30:00', '2026-07-20T10:00:00', 10, 'none', 1, 80, 1, 'published', ?)", (event_id, sala_principal, server.now_iso())).lastrowid)
            taller = int(db.execute("INSERT INTO activities (event_id, space_id, title, starts_at, ends_at, capacity, reservation_mode, requiere_asistencia, porcentaje_minimo_asistencia, habilita_certificado, status, created_at) VALUES (?, ?, 'Taller con cupo', '2026-07-20T10:15:00', '2026-07-20T11:15:00', 5, 'required', 1, 80, 1, 'published', ?)", (event_id, sala_taller, server.now_iso())).lastrowid)
            cierre = int(db.execute("INSERT INTO activities (event_id, space_id, title, starts_at, ends_at, capacity, reservation_mode, requiere_asistencia, porcentaje_minimo_asistencia, habilita_certificado, status, created_at) VALUES (?, ?, 'Cierre', '2026-07-20T12:00:00', '2026-07-20T12:30:00', 10, 'none', 1, 80, 1, 'published', ?)", (event_id, sala_principal, server.now_iso())).lastrowid)
            server.ensure_capacity_bags(db, event_id, taller)

            accreditations = []
            for index in range(1, 11):
                source = "public" if index <= 6 else "admin" if index <= 8 else "import"
                acc_type = "Invitado Especial" if index in {2, 7} else "Participante General"
                accreditations.append(insert_participant(db, event_id, index, source, acc_type))

            for acc_id in accreditations[:5]:
                db.execute("INSERT INTO reservations (event_id, activity_id, bag_id, accreditation_id, status, created_at) VALUES (?, ?, NULL, ?, 'confirmed', ?)", (event_id, taller, acc_id, server.now_iso()))
            db.execute("INSERT INTO reservations (event_id, activity_id, bag_id, accreditation_id, status, created_at) VALUES (?, ?, NULL, ?, 'waitlist', ?)", (event_id, taller, accreditations[5], server.now_iso()))
            db.execute("UPDATE reservations SET status = 'cancelled' WHERE activity_id = ? AND accreditation_id = ?", (taller, accreditations[4]))
            db.execute("UPDATE reservations SET status = 'confirmed' WHERE activity_id = ? AND accreditation_id = ?", (taller, accreditations[5]))

            access_results = []
            for acc_id in accreditations:
                token = db.execute("SELECT token FROM accreditations WHERE id = ?", (acc_id,)).fetchone()["token"]
                access_results.append(server.access_validation_service().validate(db, token, "Acceso", "Acceso general", None))
            duplicate = server.access_validation_service().validate(db, "EVT-LIVE1001", "Acceso", "Acceso general", None)
            invalid = server.access_validation_service().validate(db, "EVT-LIVE10ALTERADO", "Acceso", "Acceso general", None)

            for activity_id in [apertura, taller, cierre]:
                for acc_id in accreditations[:6]:
                    token = db.execute("SELECT token FROM accreditations WHERE id = ?", (acc_id,)).fetchone()["token"]
                    server.attendance_service().register_entry(db, token, activity_id, "Acceso")
            server.release_available_certificates(db, event_id)

            rows = server.communication_audience_rows(db, event_id, "all")
            email = server.queue_communication(db, event_id=event_id, actor="Comunicaciones", audience="all", channel="email", template_code="demo_live_10", subject="Demo Live 10", content="Hola {{nombre}}, tu QR es {{qr}}", rows=rows, process_now=True)
            whatsapp = server.queue_communication(db, event_id=event_id, actor="Comunicaciones", audience="all", channel="whatsapp", template_code="demo_live_10", subject="Demo Live 10", content="Hola {{nombre}}, portal {{portal_participante}}", rows=rows, process_now=True)

            backup = server.event_backup_service().create_event_bundle(event_id, "QA")
            preview = server.event_restore_service().inspect_bytes(backup.read_bytes(), backup.name)
            restored = server.event_restore_service().restore_bytes(backup.read_bytes(), mode="new_event", actor="QA", new_event_name="BITORA Demo Live 10 - Restaurado")
            restored_event_id = int(restored["event_id"])

            summary = {
                "ok": True,
                "event_id": event_id,
                "restored_event_id": restored_event_id,
                "participants": count(db, "SELECT COUNT(*) AS c FROM accreditations WHERE event_id = ?", (event_id,)),
                "activities": count(db, "SELECT COUNT(*) AS c FROM activities WHERE event_id = ?", (event_id,)),
                "reservations_confirmed": count(db, "SELECT COUNT(*) AS c FROM reservations WHERE event_id = ? AND status = 'confirmed'", (event_id,)),
                "reservations_cancelled": count(db, "SELECT COUNT(*) AS c FROM reservations WHERE event_id = ? AND status = 'cancelled'", (event_id,)),
                "access_granted": sum(1 for item in access_results if item["result"] == "granted"),
                "access_rejected": sum(1 for item in [duplicate, invalid] if item["result"] == "rejected"),
                "access_result_details": access_results,
                "duplicate_access_status": duplicate["result"],
                "invalid_access_status": invalid["result"],
                "attendance": count(db, "SELECT COUNT(*) AS c FROM activity_attendance WHERE event_id = ?", (event_id,)),
                "certificates": count(db, "SELECT COUNT(*) AS c FROM certificate_eligibility WHERE event_id = ?", (event_id,)),
                "communication_logs": count(db, "SELECT COUNT(*) AS c FROM communication_logs WHERE event_id = ?", (event_id,)),
                "email": email,
                "whatsapp": whatsapp,
                "backup_name": backup.name,
                "backup_preview_ok": preview["ok"],
                "restored_participants": count(db, "SELECT COUNT(*) AS c FROM accreditations WHERE event_id = ?", (restored_event_id,)),
                "restored_activities": count(db, "SELECT COUNT(*) AS c FROM activities WHERE event_id = ?", (restored_event_id,)),
                "restored_queue_inactive": count(db, "SELECT COUNT(*) AS c FROM communication_queue WHERE event_id = ? AND status = 'restored_inactive'", (restored_event_id,)),
            }
            (output_dir / "demo_live_10_result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            assert summary["participants"] == 10
            assert summary["activities"] == 3
            assert summary["reservations_confirmed"] == 5
            assert summary["access_granted"] == 10
            assert summary["access_rejected"] >= 2
            assert summary["attendance"] >= 18
            assert summary["backup_preview_ok"]
            assert summary["restored_participants"] == 10
            assert summary["restored_activities"] == 3
            assert summary["restored_queue_inactive"] >= 1
            print("OK: Demo Live 10 automatizada validada")
    finally:
        server.DB_PATH = original_path
        try:
            os.remove(db_file)
        except OSError:
            pass


if __name__ == "__main__":
    main()
