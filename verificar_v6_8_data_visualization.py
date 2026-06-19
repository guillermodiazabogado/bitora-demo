from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import server


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="bitora-v68-visualization-"))
    old_db = server.DB_PATH
    try:
        server.DB_PATH = tmp / "visualization.sqlite3"
        server.init_db()
        server.seed_if_empty()
        now = server.now_iso()
        with server.connect() as db:
            event_id = db.execute(
                """
                INSERT INTO events (
                    name, description, venue, capacity, status, starts_at, ends_at, created_at
                ) VALUES ('Demo Data Visualization', 'demo analytics', 'Centro BITORA', 500,
                          'published', '2026-06-18T08:00:00+00:00',
                          '2026-06-19T20:00:00+00:00', ?)
                """,
                (now,),
            ).lastrowid
            space_id = db.execute(
                "INSERT INTO spaces (event_id, name, capacity, created_at) VALUES (?, 'Sala Analytics', 100, ?)",
                (event_id, now),
            ).lastrowid
            activity_id = db.execute(
                """
                INSERT INTO activities (
                    event_id, space_id, title, starts_at, ends_at, capacity,
                    reservation_mode, status, created_at
                ) VALUES (?, ?, 'Visualizacion Operativa', '2026-06-18T10:00:00+00:00',
                          '2026-06-18T11:00:00+00:00', 100, 'free', 'published', ?)
                """,
                (event_id, space_id, now),
            ).lastrowid

            accreditation_ids = []
            for index in range(12):
                person_id = db.execute(
                    """
                    INSERT INTO people (first_name, last_name, email, company, created_at)
                    VALUES (?, 'Analytics', ?, 'BITORA QA', ?)
                    """,
                    (f"Persona {index}", f"visual-{index}@example.test", now),
                ).lastrowid
                checked = now if index < 8 else None
                accreditation_id = db.execute(
                    """
                    INSERT INTO accreditations (
                        event_id, person_id, token, type, source, status,
                        checked_in_at, created_at
                    ) VALUES (?, ?, ?, 'General', ?, 'confirmed', ?, ?)
                    """,
                    (event_id, person_id, f"VIZ-{index}", "linkedin" if index < 7 else "landing", checked, now),
                ).lastrowid
                accreditation_ids.append(accreditation_id)
                db.execute(
                    """
                    INSERT INTO captation_events (
                        event_id, source, device_type, action, accreditation_id,
                        person_id, created_at
                    ) VALUES (?, ?, 'desktop', 'landing_opened', ?, ?, ?)
                    """,
                    (event_id, "linkedin" if index < 7 else "landing", accreditation_id, person_id, now),
                )
                if index < 10:
                    reservation_id = db.execute(
                        """
                        INSERT INTO reservations (
                            event_id, activity_id, accreditation_id, status, created_at
                        ) VALUES (?, ?, ?, 'confirmed', ?)
                        """,
                        (event_id, activity_id, accreditation_id, now),
                    ).lastrowid
                    if index < 7:
                        db.execute(
                            """
                            INSERT INTO activity_attendance (
                                event_id, activity_id, accreditation_id, reservation_id,
                                entry_at, exit_at, attended_minutes, attendance_percentage,
                                status, eligibility_status, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, 55, 92, 'Completa', 'Elegible', ?, ?)
                            """,
                            (event_id, activity_id, accreditation_id, reservation_id, now, now, now, now),
                        )
                        db.execute(
                            """
                            INSERT INTO certificate_eligibility (
                                event_id, activity_id, accreditation_id, porcentaje,
                                elegible, estado, fecha_calculo, certificate_generated_at
                            ) VALUES (?, ?, ?, 92, 1, 'Elegible', ?, ?)
                            """,
                            (event_id, activity_id, accreditation_id, now, now),
                        )
                if index < 8:
                    db.execute(
                        """
                        INSERT INTO access_logs (
                            accreditation_id, event_id, token, operator, checkpoint,
                            access_point, result, reason, created_at
                        ) VALUES (?, ?, ?, 'Operador QA', 'Acceso Norte', 'Acceso Norte',
                                  'granted', 'OK', ?)
                        """,
                        (accreditation_id, event_id, f"VIZ-{index}", now),
                    )
                db.execute(
                    """
                    INSERT INTO communication_logs (
                        event_id, person_id, accreditation_id, canal, fecha, tipo,
                        asunto, contenido, estado
                    ) VALUES (?, ?, ?, 'email', ?, 'confirmacion', 'BITORA',
                              'Mensaje de prueba', 'entregado')
                    """,
                    (event_id, person_id, accreditation_id, now),
                )

            data = server.DATA_VISUALIZATION.collect(
                db,
                event_id,
                dashboard="operational",
                period="event",
                force=True,
            )
            assert data and data["version"] == "6.8"
            assert data["heatmaps"]["rooms"][0]["percentage"] == 7
            assert data["heatmaps"]["activities"][0]["value"] == 10
            assert data["series"]["registrations"]
            assert data["series"]["accesses"]
            assert data["series"]["communications"]
            assert data["series"]["certificates"]
            assert [stage["label"] for stage in data["funnel"]] == [
                "Landing",
                "Inscripcion",
                "Acreditacion",
                "Ingreso",
                "Asistencia",
                "Certificado",
            ]
            assert data["funnel"][1]["value"] == 12
            assert data["funnel"][3]["value"] == 8
            assert data["funnel"][5]["value"] == 7
            assert data["rankings"]["activities"][0]["value"] == 10
            assert data["scatter"]["attendance_vs_registration"][0]["x"] == 10
            assert data["forecast"]["current_registrations"] == 12
            assert "access_rate_per_minute" in data["forecast"]

            layout = server.DATA_VISUALIZATION.save_layout(
                db,
                event_id,
                "Admin",
                {
                    "name": "Operacion principal",
                    "dashboard": "operational",
                    "period": "today",
                    "mode": "tv",
                    "widgets": ",".join(data["widgets"]),
                    "is_default": True,
                },
                now,
            )
            assert layout["name"] == "Operacion principal"
            assert server.DATA_VISUALIZATION.list_layouts(db, event_id, "Admin")[0]["is_default"] == 1

        frontend = (Path("frontend") / "index.html").read_text(encoding="utf-8")
        app_js = (Path("frontend") / "app.js").read_text(encoding="utf-8")
        noc_js = (Path("frontend") / "noc.js").read_text(encoding="utf-8")
        control_room = (Path("frontend") / "reports-display.html").read_text(encoding="utf-8")
        assert 'id="visualization"' in frontend
        assert "Data Visualization" in frontend
        assert "/api/data-visualization" in app_js
        assert "/api/data-visualization" in noc_js
        assert "/api/data-visualization" in control_room
        print("OK: V6.8 heatmaps, series, funnel, rankings, forecast, layouts e integraciones")
    finally:
        server.DB_PATH = old_db
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
