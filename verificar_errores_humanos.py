from __future__ import annotations

import server
from qa2_utils import (
    Harness,
    QA2Error,
    accreditation_id_for,
    create_activity,
    create_event,
    first_space_id,
    register,
    request,
    reserve,
    validate,
)


def assert_message(body, label: str) -> None:
    text = str(body)
    if not text or text == "{}":
        raise QA2Error(f"{label}: mensaje vacio")


def main() -> None:
    h = Harness("qa2-humanos-")
    try:
        h.start()
        event_id = create_event(h.base, "QA2 Errores Humanos", waitlist=True)
        space_id = first_space_id(h.base, event_id)
        activity_id = create_activity(h.base, event_id, space_id, "Curso humano", capacity=1)

        reg = register(h.base, event_id, 1, "human")
        acc_id = accreditation_id_for(reg["token"])
        reserve(h.base, event_id, activity_id, acc_id)

        wrong_status, wrong_body = validate(h.base, "TOKEN-EQUIVOCADO")
        if wrong_status not in (200, 400, 404):
            raise QA2Error("QR equivocado no fue rechazado")
        if wrong_status == 200 and wrong_body.get("result") != "rejected":
            raise QA2Error("QR equivocado no fue rechazado")
        assert_message(wrong_body.get("reason") or wrong_body.get("error") or wrong_body, "QR equivocado")

        early_status, early_body = request(
            h.base,
            "POST",
            "/api/events",
            {
                "actor": "Admin",
                "name": "QA2 Anticipado",
                "status": "published",
                "capacity": 100,
                "waitlist_enabled": True,
                "activity_access_open_minutes_before": 10,
            },
        )
        if early_status != 201:
            raise QA2Error("no se pudo crear evento anticipado")
        early_event = int(early_body["id"])
        early_space = first_space_id(h.base, early_event)
        early_activity = create_activity(h.base, early_event, early_space, "Curso futuro", capacity=5, start="2027-12-10T10:00")
        early_reg = register(h.base, early_event, 2, "human-early")
        early_acc = accreditation_id_for(early_reg["token"])
        reserve(h.base, early_event, early_activity, early_acc)
        status, body = request(h.base, "POST", "/api/validate", {"operator": "Acceso", "checkpoint": "Anticipado", "token": early_reg["token"], "activity_id": early_activity})
        if status != 200 or body.get("result") != "rejected":
            raise QA2Error("QR anticipado no fue rechazado")
        assert_message(body.get("reason"), "QR anticipado")

        first = validate(h.base, reg["token"])
        second = validate(h.base, reg["token"])
        if first[1].get("result") != "granted" or second[1].get("result") != "rejected":
            raise QA2Error("QR repetido no quedo controlado")

        status, body = request(h.base, "POST", "/api/accreditations/status", {"actor": "Recepcion", "id": acc_id, "status": "cancelled"})
        if status != 200:
            raise QA2Error("cancelacion de acreditacion fallo")
        cancelled = validate(h.base, reg["token"])
        if cancelled[1].get("result") != "rejected":
            raise QA2Error("acreditacion cancelada pudo ingresar")
        status, body = request(h.base, "POST", "/api/accreditations/status", {"actor": "Recepcion", "id": acc_id, "status": "active"})
        if status != 200:
            raise QA2Error("reactivacion de acreditacion fallo")

        duplicate = request(
            h.base,
            "POST",
            "/api/register",
            {
                "actor": "public",
                "event_id": event_id,
                "first_name": "Nombre1",
                "last_name": "Apellido1",
                "email": "human.1@example.test",
                "type": "General",
            },
        )
        if duplicate[0] not in (200, 201) or not duplicate[1].get("existing"):
            raise QA2Error("inscripcion duplicada no fue reconocida como existente")

        status, search = request(h.base, "GET", f"/api/accreditations?event_id={event_id}&q=human.1@example.test")
        if status != 200 or not search:
            raise QA2Error("persona sin QR no pudo buscarse por recepcion")

        with server.connect() as db:
            new_space = db.execute(
                "INSERT INTO spaces (event_id, name, capacity, responsible, transition_minutes, status, created_at) VALUES (?, 'Sala cambio', 100, '', 10, 'active', ?)",
                (event_id, server.now_iso()),
            ).lastrowid
            db.execute("UPDATE activities SET space_id = ? WHERE id = ?", (new_space, activity_id))
            server.audit(db, "Admin", "activity.room_changed", "activity", activity_id, {"event_id": event_id, "space_id": int(new_space)})
            db.execute("UPDATE activities SET status = 'cancelled' WHERE id = ?", (activity_id,))
            server.audit(db, "Admin", "activity.cancelled", "activity", activity_id, {"event_id": event_id})

        bad_import = request(h.base, "POST", "/api/import-accreditations", {"actor": "Recepcion", "event_id": event_id, "rows": [{"Nombre": "", "Email": ""}]})
        if bad_import[0] not in (200, 400):
            raise QA2Error("CSV con errores no respondio de forma controlada")
        bad_agenda = request(h.base, "POST", "/api/agenda/import", {"actor": "Admin", "event_id": event_id, "csv": "Sala,Actividad,Fecha\n,,\n"})
        if bad_agenda[0] != 200 or not bad_agenda[1].get("errors"):
            raise QA2Error("agenda con errores no informo errores")

        audit = request(h.base, "GET", f"/api/audit?event_id={event_id}")[1]
        actions = {row["action"] for row in audit}
        expected = {"accreditation.status_changed", "activity.room_changed", "activity.cancelled"}
        if not expected.issubset(actions):
            raise QA2Error(f"auditoria incompleta: {actions}")

        print("OK: errores humanos controlados")
    finally:
        h.cleanup()


if __name__ == "__main__":
    main()
