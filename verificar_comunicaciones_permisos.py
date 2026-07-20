import json
import os
import tempfile

os.environ.setdefault("QR_REQUIRE_LOGIN", "0")

import server


def seed_event(db, name):
    cur = db.execute(
        """
        INSERT INTO events (name, description, venue, starts_at, ends_at, status, project_type, capacity, created_at)
        VALUES (?, '', 'Demo', '', '', 'published', 'conference', 100, ?)
        """,
        (name, server.now_iso()),
    )
    event_id = int(cur.lastrowid)
    server.ensure_default_types(db, event_id)
    server.ensure_super_admin_event_access(db, event_id)
    suffix = str(cur.lastrowid)
    person_id = db.execute(
        "INSERT INTO people (first_name, last_name, email, phone, company, created_at) VALUES ('Ana', 'Demo', ?, ?, 'BITORA', ?)",
        (f"ana.demo.{suffix}@example.com", f"5492994522{suffix.zfill(2)[-2:]}", server.now_iso()),
    ).lastrowid
    acc_id = db.execute(
        """
        INSERT INTO accreditations (event_id, person_id, type, token, status, checked_in_at, created_at)
        VALUES (?, ?, 'General', ?, 'active', NULL, ?)
        """,
        (event_id, person_id, f"EVT-{event_id}-TEST", server.now_iso()),
    ).lastrowid
    server.upsert_communication_preference(
        db,
        int(person_id),
        {"email": f"ana.demo.{suffix}@example.com", "phone": f"5492994522{suffix.zfill(2)[-2:]}", "acepta_email": 1, "acepta_whatsapp": 1},
    )
    return event_id, int(acc_id)


def main():
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    original_path = server.DB_PATH
    server.DB_PATH = server.Path(path)
    try:
        server.init_db()
        with server.connect() as db:
            productor = server.user_by_name(db, "Productor")
            recepcion = server.user_by_name(db, "Recepcion")
            soporte = server.user_by_name(db, "Soporte")
            assert productor and recepcion and soporte
            event_a, acc_a = seed_event(db, "Evento A")
            event_b, _ = seed_event(db, "Evento B")
            server.assign_user_to_event(db, int(productor["id"]), event_a, "Productor")
            server.assign_user_to_event(db, int(recepcion["id"]), event_a, "Operador de recepcion")
            server.assign_user_to_event(db, int(soporte["id"]), event_a, "Soporte tecnico")

            productor_session = {"id": int(productor["id"]), "name": "Productor", "role": "Productor"}
            recepcion_session = {"id": int(recepcion["id"]), "name": "Recepcion", "role": "Operador de recepcion"}
            soporte_session = {"id": int(soporte["id"]), "name": "Soporte", "role": "Soporte tecnico"}

            assert server.user_has_permission(db, productor_session, event_a, "communications.send")
            assert not server.user_has_permission(db, productor_session, event_b, "communications.send")
            assert server.user_has_permission(db, recepcion_session, event_a, "communications.resend_individual")
            assert not server.user_has_permission(db, recepcion_session, event_a, "communications.send")
            assert server.user_has_permission(db, soporte_session, event_a, "communications.view_technical_logs")
            assert not server.user_has_permission(db, soporte_session, event_a, "communications.view_personal_data")

            rows = server.communication_audience_rows(db, event_a, "all")
            result = server.queue_communication(
                db,
                event_id=event_a,
                actor="Productor",
                audience="all",
                channel="email",
                template_code="manual",
                subject="Prueba",
                content="Hola {{nombre}}",
                rows=rows,
                process_now=False,
            )
            assert result["queued"] == 1, "Productor debe poder crear borrador/cola"
            assert result["sent"] == 0, "Borrador no debe procesar envio"

            individual = [row for row in rows if int(row["accreditation_id"]) == acc_a]
            result = server.queue_communication(
                db,
                event_id=event_a,
                actor="Recepcion",
                audience="individual",
                channel="whatsapp",
                template_code="qr_resend",
                subject="QR",
                content="Tu QR {{portal_participante}}",
                rows=individual,
                process_now=False,
            )
            assert result["queued"] == 1, "Recepcion debe poder reenviar individual si backend lo autoriza antes"

            masked = server.mask_communication_personal_data({"email": "ana.demo@example.com", "phone": "5492994522126", "recipient": "ana.demo@example.com"})
            assert masked["email"] != "ana.demo@example.com"
            assert masked["phone"] != "5492994522126"
            assert masked["recipient"] != "ana.demo@example.com"

        print(json.dumps({"ok": True, "event_a": event_a, "event_b": event_b}, ensure_ascii=False))
    finally:
        server.DB_PATH = original_path
        try:
            os.remove(path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
