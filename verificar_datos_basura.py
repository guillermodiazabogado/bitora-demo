from __future__ import annotations

from qa2_utils import Harness, QA2Error, create_activity, create_event, first_space_id, request


def main() -> None:
    h = Harness("qa2-trash-")
    try:
        h.start()
        event_id = create_event(h.base, "QA2 Datos Basura")
        space_id = first_space_id(h.base, event_id)
        spaces = request(h.base, "GET", f"/api/spaces?event_id={event_id}")[1]
        space_name = next(row["name"] for row in spaces if int(row["id"]) == space_id)

        weird = request(
            h.base,
            "POST",
            "/api/register",
            {
                "actor": "public",
                "event_id": event_id,
                "first_name": "A" * 240 + " !@#$%",
                "last_name": "Nunez Test",
                "email": "basura.weird@example.test",
                "dni": "DNI-@@@",
                "phone": "1",
                "type": "General",
            },
        )
        if weird[0] != 201:
            raise QA2Error("nombre raro/largo no fue controlado")

        dup = request(
            h.base,
            "POST",
            "/api/register",
            {
                "actor": "public",
                "event_id": event_id,
                "first_name": "Otro",
                "last_name": "DNI",
                "email": "basura.dup@example.test",
                "dni": "DNI-@@@",
                "type": "General",
            },
        )
        if dup[0] != 201:
            raise QA2Error("DNI duplicado produjo error duro")

        invalid_email = request(
            h.base,
            "POST",
            "/api/register",
            {"actor": "public", "event_id": event_id, "first_name": "Mail", "last_name": "Malo", "email": "no-es-email", "type": "General"},
        )
        if invalid_email[0] not in (201, 400):
            raise QA2Error("email invalido no fue controlado")

        missing_csv = request(h.base, "POST", "/api/import-accreditations", {"actor": "Recepcion", "event_id": event_id, "rows": [{"Nombre": "Sin columnas"}]})
        if missing_csv[0] not in (200, 400):
            raise QA2Error("CSV con columnas faltantes rompio endpoint")

        extra_csv = request(
            h.base,
            "POST",
            "/api/import-accreditations",
            {"actor": "Recepcion", "event_id": event_id, "rows": [{"Nombre": "Extra", "Apellido": "Ok", "Email": "extra@example.test", "ColumnaRara": "x"}]},
        )
        if extra_csv[0] not in (200, 201):
            raise QA2Error("CSV con columnas extra no fue tolerado")

        create_activity(h.base, event_id, space_id, "Solape base", capacity=10, start="2026-12-10T10:00")
        overlap = request(
            h.base,
            "POST",
            "/api/agenda/import",
            {"actor": "Admin", "event_id": event_id, "csv": f"Sala,Actividad,Fecha,Hora inicio,Hora fin\n{space_name},Solape,2026-12-10,10:15,10:45"},
        )
        if overlap[0] != 200 or not overlap[1].get("errors"):
            raise QA2Error("agenda solapada no informo error")

        no_room = request(
            h.base,
            "POST",
            "/api/agenda/import",
            {"actor": "Admin", "event_id": event_id, "csv": "Sala,Actividad,Fecha,Hora inicio,Hora fin\n,Sin sala,2026-12-10,12:00,13:00"},
        )
        if no_room[0] != 200 or not no_room[1].get("errors"):
            raise QA2Error("agenda sin sala no informo error")

        no_time = request(
            h.base,
            "POST",
            "/api/agenda/import",
            {"actor": "Admin", "event_id": event_id, "csv": "Sala,Actividad,Fecha,Hora inicio,Hora fin\nGeneral,Sin hora,2026-12-10,,"},
        )
        if no_time[0] != 200 or not no_time[1].get("errors"):
            raise QA2Error("agenda sin horario no informo error")

        no_name = request(h.base, "POST", "/api/activities", {"actor": "Admin", "event_id": event_id, "space_id": space_id, "title": "", "starts_at": "2026-12-10T14:00", "ends_at": "2026-12-10T15:00"})
        if no_name[0] != 400:
            raise QA2Error("actividad sin nombre no fue rechazada")

        bad_ics = request(h.base, "POST", "/api/agenda/import", {"actor": "Admin", "event_id": event_id, "ics": "BEGIN:VCALENDAR\nBROKEN"})
        if bad_ics[0] != 200:
            raise QA2Error("ICS corrupto rompio endpoint")

        print("OK: datos basura controlados")
    finally:
        h.cleanup()


if __name__ == "__main__":
    main()
