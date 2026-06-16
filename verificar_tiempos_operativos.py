from __future__ import annotations

from pathlib import Path

from qa2_utils import Harness, QA2Error, accreditation_id_for, create_activity, create_event, first_space_id, quote, request, timed, validate


REPORT = Path("BITORA_PERFORMANCE_REPORT.md")


def main() -> None:
    h = Harness("qa2-performance-")
    metrics: list[tuple[str, dict]] = []
    try:
        h.start()
        event_id = create_event(h.base, "QA2 Tiempos")
        space_id = first_space_id(h.base, event_id)
        activity_id = create_activity(h.base, event_id, space_id, "Performance", capacity=100)

        reg_metric = timed(lambda: request(h.base, "POST", "/api/register", {"actor": "public", "event_id": event_id, "first_name": "Perf", "last_name": "Uno", "email": "perf.1@example.test", "type": "General"}))
        metrics.append(("inscripcion", reg_metric))
        token = reg_metric["body"]["token"]
        acc_id = accreditation_id_for(token)

        metrics.append(("busqueda_recepcion", timed(lambda: request(h.base, "GET", f"/api/accreditations?event_id={event_id}&q=perf.1@example.test"))))
        metrics.append(("generacion_qr", timed(lambda: request(h.base, "GET", f"/api/credential.png?token={quote(token)}", parse_json=False))))
        metrics.append(("validacion_qr", timed(lambda: validate(h.base, token))))
        metrics.append(("dashboard", timed(lambda: request(h.base, "GET", f"/api/summary?event_id={event_id}"))))
        metrics.append(("portal", timed(lambda: request(h.base, "GET", f"/api/portal?token={token}"))))
        metrics.append(("exportacion_csv", timed(lambda: request(h.base, "GET", f"/api/export.csv?event_id={event_id}", parse_json=False))))
        metrics.append(("backup", timed(lambda: request(h.base, "GET", f"/api/backup?event_id={event_id}", parse_json=False))))

        bad = [name for name, row in metrics if row["status"] != 200 and name != "inscripcion" or row["seconds"] > 5]
        if bad:
            raise QA2Error(f"tiempos fuera de rango: {bad}")

        lines = [
            "# BITORA Performance Report",
            "",
            "Fecha: 2026-06-16",
            "",
            "| Operacion | HTTP | Tiempo s |",
            "| --- | ---: | ---: |",
        ]
        for name, row in metrics:
            lines.append(f"| {name} | {row['status']} | {row['seconds']:.3f} |")
        lines.extend(
            [
                "",
                "Resultado: OK para demo. Todas las operaciones medidas respondieron por debajo de 5 segundos en entorno local/demo.",
            ]
        )
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("OK: tiempos operativos")
        for name, row in metrics:
            print(f"{name}={row['seconds']:.3f}s status={row['status']}")
    finally:
        h.cleanup()


if __name__ == "__main__":
    main()
