from __future__ import annotations

import random
import time

from qa2_utils import (
    Harness,
    QA2Error,
    accreditation_id_for,
    bulk_seed,
    create_event,
    db_counts,
    integrity_check,
    parallel,
    request,
    reserve,
    summarize,
    timed,
    validate,
)


PARTICIPANTS = 20000
ACTIVITIES = 50
ROOMS = 10
QR_OPERATORS = 50
SCANS = 10000
SIMULTANEOUS_REGISTRATIONS = 1000


def main() -> None:
    h = Harness("qa2-stress-")
    started = time.perf_counter()
    try:
        h.start()
        event_id = create_event(h.base, "QA2 Stress Extremo", capacity=50000, waitlist=True)
        seeded = bulk_seed(event_id, PARTICIPANTS, rooms=ROOMS, activities=ACTIVITIES)
        tokens = seeded["tokens"]
        activities = seeded["activities"]

        sample_tokens = tokens[:SCANS]
        scan_results = parallel(
            QR_OPERATORS,
            sample_tokens,
            lambda token: timed(lambda token=token: validate(h.base, token, checkpoint=f"Operador {random.randint(1, QR_OPERATORS)}")),
        )
        scan_summary = summarize(scan_results, lambda r: r["status"] == 200 and r["body"].get("result") == "granted")
        if scan_summary["errors"]:
            raise QA2Error(f"escaneos con errores: {scan_summary}")

        duplicate_token = tokens[SCANS + 1]
        dup_results = parallel(100, range(100), lambda _: timed(lambda: validate(h.base, duplicate_token, checkpoint="Duplicado")))
        granted = sum(1 for row in dup_results if row["status"] == 200 and row["body"].get("result") == "granted")
        already_used = sum(1 for row in dup_results if row["status"] == 200 and row["body"].get("result") == "rejected")
        if granted != 1 or already_used != 99:
            raise QA2Error(f"QR duplicado simultaneo inseguro: granted={granted} rejected={already_used}")

        registration_results = parallel(
            80,
            range(SIMULTANEOUS_REGISTRATIONS),
            lambda i: timed(
                lambda i=i: request(
                    h.base,
                    "POST",
                    "/api/register",
                    {
                        "actor": "public",
                        "event_id": event_id,
                        "first_name": f"Sim{i}",
                        "last_name": "Registro",
                        "email": f"qa2.concurrent.{i}@example.test",
                        "dni": str(70000000 + i),
                        "type": "General",
                    },
                )
            ),
        )
        registration_summary = summarize(registration_results, lambda r: r["status"] == 201)
        if registration_summary["errors"]:
            raise QA2Error(f"inscripciones simultaneas con errores: {registration_summary}")

        target_activity = activities[0]
        reservation_ids = [accreditation_id_for(token) for token in tokens[12000:13000]]
        reservation_results = parallel(
            80,
            reservation_ids,
            lambda acc_id: timed(lambda acc_id=acc_id: request(h.base, "POST", "/api/reservations", {"actor": "Recepcion", "event_id": event_id, "activity_id": target_activity, "accreditation_id": acc_id})),
        )
        reservation_summary = summarize(reservation_results, lambda r: r["status"] == 201 and r["body"].get("status") in {"confirmed", "waitlisted"})
        if reservation_summary["errors"]:
            raise QA2Error(f"reservas simultaneas con errores: {reservation_summary}")

        with __import__("server").connect() as db:
            counts = db.execute(
                """
                SELECT
                    SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) AS confirmed,
                    SUM(CASE WHEN status = 'waitlisted' THEN 1 ELSE 0 END) AS waitlisted,
                    COUNT(*) AS total
                FROM reservations
                WHERE activity_id = ?
                """,
                (target_activity,),
            ).fetchone()
        if int(counts["confirmed"] or 0) > 200:
            raise QA2Error(f"sobrecupo detectado: {dict(counts)}")
        if int(counts["total"] or 0) != 1000:
            raise QA2Error(f"reservas perdidas: {dict(counts)}")

        status, dashboard = request(h.base, "GET", f"/api/reports/visual-summary?event_id={event_id}")
        if status != 200 or "event_health" not in dashboard:
            raise QA2Error("dashboard no respondio bajo carga")

        integrity_check()
        counts_after = db_counts()
        if counts_after["duplicate_tokens"]:
            raise QA2Error("tokens duplicados en base")

        elapsed = time.perf_counter() - started
        print("OK: stress extremo")
        print(f"participantes={PARTICIPANTS} actividades={ACTIVITIES} salas={ROOMS}")
        print(f"escaneos={scan_summary['ok']} avg={scan_summary['avg']:.3f}s p95={scan_summary['p95']:.3f}s max={scan_summary['max']:.3f}s")
        print(f"inscripciones_simultaneas={registration_summary['ok']} reservas={reservation_summary['ok']} confirmed={counts['confirmed']} waitlisted={counts['waitlisted']}")
        print(f"duplicado_simultaneo=1_concedido_99_rechazados duracion={elapsed:.1f}s")
    finally:
        h.cleanup()


if __name__ == "__main__":
    main()
