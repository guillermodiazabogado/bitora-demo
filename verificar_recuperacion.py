from __future__ import annotations

import shutil

from qa2_utils import (
    Harness,
    QA2Error,
    accreditation_id_for,
    create_activity,
    create_event,
    first_space_id,
    integrity_check,
    register,
    request,
    reserve,
    validate,
)


def main() -> None:
    h = Harness("qa2-recovery-")
    try:
        h.start()
        event_id = create_event(h.base, "QA2 Recuperacion")
        space_id = first_space_id(h.base, event_id)
        activity_id = create_activity(h.base, event_id, space_id, "Recuperacion", capacity=20)
        reg = register(h.base, event_id, 1, "recovery")
        acc_id = accreditation_id_for(reg["token"])
        reserve(h.base, event_id, activity_id, acc_id)

        granted = validate(h.base, reg["token"])
        if granted[1].get("result") != "granted":
            raise QA2Error("validacion inicial fallo")

        h.restart()
        repeated = validate(h.base, reg["token"])
        if repeated[1].get("result") != "rejected":
            raise QA2Error("reinicio permitio doble acceso")

        partial_registration = request(h.base, "POST", "/api/register", {"actor": "public", "event_id": event_id, "first_name": "Corte", "email": ""})
        if partial_registration[0] not in (400, 409):
            raise QA2Error("inscripcion incompleta no fue rechazada")

        partial_validation = request(h.base, "POST", "/api/validate", {"operator": "Acceso", "checkpoint": "Corte", "token": ""})
        if partial_validation[0] == 200 and partial_validation[1].get("result") != "rejected":
            raise QA2Error("validacion incompleta no fue rechazada")

        bad_import = request(h.base, "POST", "/api/agenda/import", {"actor": "Admin", "event_id": event_id, "csv": "Sala,Actividad,Fecha,Hora inicio,Hora fin\nSala X,,2026-12-10,10:00,11:00"})
        if bad_import[0] != 200 or not bad_import[1].get("errors"):
            raise QA2Error("importacion incompleta no dejo errores claros")

        backup_status, backup_body = request(h.base, "GET", f"/api/backup?event_id={event_id}", parse_json=False)
        if backup_status != 200 or not backup_body:
            raise QA2Error("backup no respondio")
        backup_files = list((h.tmp / "backups").glob("*.sqlite3"))
        if not backup_files:
            raise QA2Error("backup no genero archivo")
        restored = h.tmp / "restored.sqlite3"
        shutil.copy2(backup_files[-1], restored)
        if restored.stat().st_size <= 0:
            raise QA2Error("backup invalido")

        integrity_check()
        h.restart()
        status, summary = request(h.base, "GET", f"/api/summary?event_id={event_id}")
        if status != 200 or "accreditation" not in summary or int(summary["accreditation"].get("total") or 0) < 1:
            raise QA2Error("servidor no recupero dashboard tras reinicio")

        print("OK: recuperacion, reinicio, backup e integridad")
    finally:
        h.cleanup()


if __name__ == "__main__":
    main()
