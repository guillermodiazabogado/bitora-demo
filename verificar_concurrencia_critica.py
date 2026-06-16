from __future__ import annotations

from qa2_utils import (
    Harness,
    QA2Error,
    accreditation_id_for,
    create_activity,
    create_event,
    first_space_id,
    parallel,
    register,
    request,
    summarize,
    timed,
    validate,
)


def main() -> None:
    h = Harness("qa2-concurrency-")
    try:
        h.start()
        event_id = create_event(h.base, "QA2 Concurrencia", waitlist=True)
        space_id = first_space_id(h.base, event_id)
        activity_id = create_activity(h.base, event_id, space_id, "Ultimo cupo", capacity=1)

        reg = register(h.base, event_id, 1, "conc")
        same_qr = parallel(100, range(100), lambda _: timed(lambda: validate(h.base, reg["token"])))
        granted = sum(1 for row in same_qr if row["status"] == 200 and row["body"].get("result") == "granted")
        rejected = sum(1 for row in same_qr if row["status"] == 200 and row["body"].get("result") == "rejected")
        if granted != 1 or rejected != 99:
            raise QA2Error(f"mismo QR inseguro: granted={granted} rejected={rejected}")

        regs = [register(h.base, event_id, i + 100, "conc-res") for i in range(100)]
        acc_ids = [accreditation_id_for(row["token"]) for row in regs]
        reserve_results = parallel(
            100,
            acc_ids,
            lambda acc_id: timed(lambda acc_id=acc_id: request(h.base, "POST", "/api/reservations", {"actor": "Recepcion", "event_id": event_id, "activity_id": activity_id, "accreditation_id": acc_id})),
        )
        confirmed = sum(1 for row in reserve_results if row["status"] == 201 and row["body"].get("status") == "confirmed")
        waitlisted = sum(1 for row in reserve_results if row["status"] == 201 and row["body"].get("status") == "waitlisted")
        if confirmed != 1 or waitlisted != 99:
            raise QA2Error(f"ultimo cupo inseguro: confirmed={confirmed} waitlisted={waitlisted}")

        dashboard = parallel(100, range(100), lambda _: timed(lambda: request(h.base, "GET", f"/api/reports/visual-summary?event_id={event_id}")))
        dash_summary = summarize(dashboard, lambda row: row["status"] == 200 and "event_health" in row["body"])
        if dash_summary["errors"]:
            raise QA2Error(f"dashboard concurrente fallo: {dash_summary}")

        csv_payload = "Sala,Actividad,Fecha,Hora inicio,Hora fin\nSala Import,Importada,2026-12-10,13:00,14:00"
        imports = parallel(10, range(10), lambda _: timed(lambda: request(h.base, "POST", "/api/agenda/import", {"actor": "Admin", "event_id": event_id, "csv": csv_payload})))
        import_ok = sum(1 for row in imports if row["status"] == 200)
        if import_ok != 10:
            raise QA2Error("importaciones concurrentes no respondieron de forma controlada")

        double_clicks = parallel(
            100,
            range(100),
            lambda _: timed(lambda: request(h.base, "POST", "/api/register", {"actor": "public", "event_id": event_id, "first_name": "Click", "last_name": "Masivo", "email": "double.click@example.test", "type": "General"})),
        )
        created = sum(1 for row in double_clicks if row["status"] == 201 and not row["body"].get("existing"))
        existing = sum(1 for row in double_clicks if row["status"] in (200, 201) and row["body"].get("existing"))
        if created != 1 or existing < 90:
            raise QA2Error(f"doble click masivo inseguro: created={created} existing={existing}")

        print("OK: concurrencia critica")
        print(f"mismo_qr=1_concedido_99_rechazados ultimo_cupo=1_confirmado_99_espera dashboards={dash_summary['ok']}")
    finally:
        h.cleanup()


if __name__ == "__main__":
    main()
