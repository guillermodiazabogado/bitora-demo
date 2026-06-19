from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.verticals import normalize_project_type, vertical_config

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DataVisualizationService:
    """Central aggregation layer for operational and executive dashboards."""

    PERIOD_DAYS = {"today": 0, "7d": 7, "30d": 30, "event": None}

    def __init__(self, cache_seconds: int = 8) -> None:
        self.cache_seconds = max(1, cache_seconds)
        self._cache: dict[tuple[int, str, str], tuple[float, dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def collect(
        self,
        db,
        event_id: int,
        *,
        period: str = "event",
        dashboard: str = "operational",
        force: bool = False,
    ) -> dict[str, Any] | None:
        period = period if period in self.PERIOD_DAYS else "event"
        dashboard = dashboard if dashboard in {"operational", "executive", "commercial", "academic"} else "operational"
        key = (int(event_id), period, dashboard)
        if not force:
            with self._lock:
                cached = self._cache.get(key)
                if cached and cached[0] > time.time():
                    return cached[1]

        event_row = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event_row:
            return None
        event = dict(event_row)
        project_type = normalize_project_type(event.get("project_type"))
        since = self._period_start(period)
        payload = {
            "engine": "BITORA Data Visualization Engine",
            "version": "6.8",
            "generated_at": utc_now(),
            "period": period,
            "dashboard": dashboard,
            "event": {key: event.get(key) for key in ("id", "name", "venue", "starts_at", "ends_at", "capacity", "status")},
            "project_type": project_type,
            "vertical": vertical_config(project_type),
            "heatmaps": self._heatmaps(db, event_id, since),
            "series": self._series(db, event_id, since),
            "funnel": self._funnel(db, event_id, since),
            "rankings": self._rankings(db, event_id, since),
            "scatter": self._scatter(db, event_id),
        }
        payload["forecast"] = self._forecast(event, payload)
        payload["predictive_alerts"] = self._predictive_alerts(payload)
        payload["widgets"] = self._widgets_for_dashboard(dashboard, project_type)
        with self._lock:
            self._cache[key] = (time.time() + self.cache_seconds, payload)
        return payload

    def invalidate(self, event_id: int | None = None) -> None:
        with self._lock:
            if event_id is None:
                self._cache.clear()
            else:
                self._cache = {key: value for key, value in self._cache.items() if key[0] != int(event_id)}

    def list_layouts(self, db, event_id: int, owner: str) -> list[dict[str, Any]]:
        rows = db.execute(
            """
            SELECT id, event_id, owner, name, dashboard, period, widgets, mode, is_default, updated_at
            FROM visualization_layouts
            WHERE event_id = ? AND owner = ?
            ORDER BY is_default DESC, updated_at DESC, id DESC
            """,
            (event_id, owner),
        ).fetchall()
        return [dict(row) for row in rows]

    def save_layout(self, db, event_id: int, owner: str, data: dict[str, Any], now: str) -> dict[str, Any]:
        name = str(data.get("name") or "Mi tablero").strip()[:80]
        dashboard = str(data.get("dashboard") or "operational")
        period = str(data.get("period") or "event")
        widgets = str(data.get("widgets") or "")
        mode = str(data.get("mode") or "monitor")
        is_default = 1 if data.get("is_default") else 0
        layout_id = int(data.get("id") or 0)
        if dashboard not in {"operational", "executive", "commercial", "academic"}:
            dashboard = "operational"
        if period not in self.PERIOD_DAYS:
            period = "event"
        if mode not in {"monitor", "tv"}:
            mode = "monitor"
        if is_default:
            db.execute(
                "UPDATE visualization_layouts SET is_default = 0 WHERE event_id = ? AND owner = ?",
                (event_id, owner),
            )
        if layout_id:
            db.execute(
                """
                UPDATE visualization_layouts
                SET name = ?, dashboard = ?, period = ?, widgets = ?, mode = ?,
                    is_default = ?, updated_at = ?
                WHERE id = ? AND event_id = ? AND owner = ?
                """,
                (name, dashboard, period, widgets, mode, is_default, now, layout_id, event_id, owner),
            )
        else:
            cursor = db.execute(
                """
                INSERT INTO visualization_layouts (
                    event_id, owner, name, dashboard, period, widgets, mode,
                    is_default, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (event_id, owner, name, dashboard, period, widgets, mode, is_default, now, now),
            )
            layout_id = int(cursor.lastrowid)
        row = db.execute("SELECT * FROM visualization_layouts WHERE id = ?", (layout_id,)).fetchone()
        return dict(row)

    def _period_start(self, period: str) -> str | None:
        days = self.PERIOD_DAYS[period]
        now = datetime.now(timezone.utc)
        if days is None:
            return None
        if days == 0:
            return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
        return (now - timedelta(days=days)).isoformat(timespec="seconds")

    @staticmethod
    def _time_clause(column: str, since: str | None) -> tuple[str, tuple[Any, ...]]:
        return (f" AND {column} >= ?", (since,)) if since else ("", ())

    @staticmethod
    def _rows(db, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        return [dict(row) for row in db.execute(sql, params).fetchall()]

    def _series_query(
        self,
        db,
        *,
        table: str,
        event_id: int,
        column: str,
        since: str | None,
        extra: str = "",
        minute: bool = False,
    ) -> list[dict[str, Any]]:
        clause, params = self._time_clause(column, since)
        length = 16 if minute else 13
        suffix = "" if minute else ":00"
        return self._rows(
            db,
            f"""
            SELECT substr({column}, 1, {length}) || '{suffix}' AS label, COUNT(*) AS value
            FROM {table}
            WHERE event_id = ? AND {column} IS NOT NULL AND {column} <> '' {extra} {clause}
            GROUP BY label
            ORDER BY label
            LIMIT 240
            """,
            (event_id, *params),
        )

    def _series(self, db, event_id: int, since: str | None) -> dict[str, list[dict[str, Any]]]:
        return {
            "registrations": self._series_query(db, table="accreditations", event_id=event_id, column="created_at", since=since),
            "accreditations": self._series_query(
                db, table="accreditations", event_id=event_id, column="checked_in_at", since=since
            ),
            "accesses": self._series_query(
                db,
                table="access_logs",
                event_id=event_id,
                column="created_at",
                since=since,
                extra="AND result = 'granted'",
                minute=True,
            ),
            "communications": self._series_query(
                db, table="communication_logs", event_id=event_id, column="fecha", since=since
            ),
            "certificates": self._series_query(
                db,
                table="certificate_eligibility",
                event_id=event_id,
                column="certificate_generated_at",
                since=since,
            ),
        }

    def _heatmaps(self, db, event_id: int, since: str | None) -> dict[str, list[dict[str, Any]]]:
        rooms = self._rows(
            db,
            """
            SELECT s.name AS label, s.capacity,
                   COUNT(DISTINCT CASE WHEN at.status IN ('Presente', 'Completa', 'Parcial') THEN at.id END) AS value
            FROM spaces s
            LEFT JOIN activities a ON a.space_id = s.id AND a.status <> 'cancelled'
            LEFT JOIN activity_attendance at ON at.activity_id = a.id
            WHERE s.event_id = ? AND s.status <> 'cancelled'
            GROUP BY s.id, s.name, s.capacity
            ORDER BY s.name
            """,
            (event_id,),
        )
        for row in rooms:
            capacity = int(row.get("capacity") or 0)
            value = int(row.get("value") or 0)
            row["percentage"] = min(100, round(value * 100 / capacity)) if capacity else 0

        activities = self._rows(
            db,
            """
            SELECT a.title AS label, a.capacity,
                   COUNT(DISTINCT CASE WHEN r.status = 'confirmed' THEN r.id END) AS value
            FROM activities a
            LEFT JOIN reservations r ON r.activity_id = a.id
            WHERE a.event_id = ? AND a.status <> 'cancelled'
            GROUP BY a.id, a.title, a.capacity
            ORDER BY value DESC, a.starts_at
            LIMIT 30
            """,
            (event_id,),
        )
        for row in activities:
            capacity = int(row.get("capacity") or 0)
            value = int(row.get("value") or 0)
            row["percentage"] = min(100, round(value * 100 / capacity)) if capacity else 0

        access_clause, access_params = self._time_clause("created_at", since)
        hours = self._rows(
            db,
            f"""
            SELECT substr(created_at, 12, 2) || ':00' AS label, COUNT(*) AS value
            FROM access_logs
            WHERE event_id = ? AND result = 'granted' {access_clause}
            GROUP BY label ORDER BY label
            """,
            (event_id, *access_params),
        )
        points = self._rows(
            db,
            f"""
            SELECT COALESCE(NULLIF(checkpoint, ''), NULLIF(access_point, ''), 'Acceso general') AS label,
                   COUNT(*) AS value
            FROM access_logs
            WHERE event_id = ? AND result = 'granted' {access_clause}
            GROUP BY label ORDER BY value DESC LIMIT 20
            """,
            (event_id, *access_params),
        )
        return {"rooms": rooms, "activities": activities, "hours": hours, "access_points": points}

    def _funnel(self, db, event_id: int, since: str | None) -> list[dict[str, Any]]:
        acc_clause, acc_params = self._time_clause("created_at", since)
        access_clause, access_params = self._time_clause("created_at", since)
        capt_clause, capt_params = self._time_clause("created_at", since)
        stages = [
            (
                "Landing",
                int(
                    db.execute(
                        f"SELECT COUNT(*) AS c FROM captation_events WHERE event_id = ? AND action = 'landing_opened' {capt_clause}",
                        (event_id, *capt_params),
                    ).fetchone()["c"]
                    or 0
                ),
            ),
            (
                "Inscripcion",
                int(
                    db.execute(
                        f"SELECT COUNT(*) AS c FROM accreditations WHERE event_id = ? {acc_clause}",
                        (event_id, *acc_params),
                    ).fetchone()["c"]
                    or 0
                ),
            ),
            (
                "Acreditacion",
                int(
                    db.execute(
                        f"SELECT COUNT(*) AS c FROM accreditations WHERE event_id = ? AND checked_in_at IS NOT NULL {acc_clause}",
                        (event_id, *acc_params),
                    ).fetchone()["c"]
                    or 0
                ),
            ),
            (
                "Ingreso",
                int(
                    db.execute(
                        f"SELECT COUNT(DISTINCT accreditation_id) AS c FROM access_logs WHERE event_id = ? AND result = 'granted' {access_clause}",
                        (event_id, *access_params),
                    ).fetchone()["c"]
                    or 0
                ),
            ),
            (
                "Asistencia",
                int(
                    db.execute(
                        "SELECT COUNT(DISTINCT accreditation_id) AS c FROM activity_attendance WHERE event_id = ? AND status IN ('Presente', 'Completa', 'Parcial')",
                        (event_id,),
                    ).fetchone()["c"]
                    or 0
                ),
            ),
            (
                "Certificado",
                int(
                    db.execute(
                        "SELECT COUNT(DISTINCT accreditation_id) AS c FROM certificate_eligibility WHERE event_id = ? AND elegible = 1",
                        (event_id,),
                    ).fetchone()["c"]
                    or 0
                ),
            ),
        ]
        if stages[0][1] == 0:
            stages[0] = ("Landing", stages[1][1])
        result = []
        previous = stages[0][1]
        base = max(stages[0][1], 1)
        for label, value in stages:
            result.append(
                {
                    "label": label,
                    "value": value,
                    "conversion": round(value * 100 / base, 1),
                    "loss": max(0, previous - value),
                }
            )
            previous = value
        return result

    def _rankings(self, db, event_id: int, since: str | None) -> dict[str, list[dict[str, Any]]]:
        activities = self._rows(
            db,
            """
            SELECT a.title AS label, COUNT(r.id) AS value
            FROM activities a
            LEFT JOIN reservations r ON r.activity_id = a.id AND r.status = 'confirmed'
            WHERE a.event_id = ? AND a.status <> 'cancelled'
            GROUP BY a.id, a.title ORDER BY value DESC LIMIT 10
            """,
            (event_id,),
        )
        rooms = sorted(self._heatmaps(db, event_id, since)["rooms"], key=lambda row: row["percentage"], reverse=True)[:10]
        hours = sorted(self._heatmaps(db, event_id, since)["hours"], key=lambda row: int(row["value"]), reverse=True)[:10]
        sources = self._rows(
            db,
            """
            SELECT COALESCE(NULLIF(source, ''), 'sin origen') AS label, COUNT(*) AS value
            FROM accreditations WHERE event_id = ?
            GROUP BY label ORDER BY value DESC LIMIT 10
            """,
            (event_id,),
        )
        return {"activities": activities, "rooms": rooms, "hours": hours, "sources": sources}

    def _scatter(self, db, event_id: int) -> dict[str, list[dict[str, Any]]]:
        occupancy = self._rows(
            db,
            """
            SELECT a.title AS label, substr(a.starts_at, 12, 5) AS hour, a.capacity AS x,
                   COUNT(DISTINCT CASE WHEN r.status = 'confirmed' THEN r.id END) AS registered,
                   COUNT(DISTINCT CASE WHEN at.status IN ('Presente', 'Completa', 'Parcial') THEN at.id END) AS y
            FROM activities a
            LEFT JOIN reservations r ON r.activity_id = a.id
            LEFT JOIN activity_attendance at ON at.activity_id = a.id
            WHERE a.event_id = ? AND a.status <> 'cancelled'
            GROUP BY a.id, a.title, a.starts_at, a.capacity
            ORDER BY a.starts_at
            """,
            (event_id,),
        )
        attendance = [
            {"label": row["label"], "x": int(row.get("registered") or 0), "y": int(row.get("y") or 0)}
            for row in occupancy
        ]
        by_source = self._rows(
            db,
            """
            SELECT COALESCE(NULLIF(a.source, ''), 'sin origen') AS label,
                   COUNT(DISTINCT a.id) AS x,
                   COUNT(DISTINCT CASE WHEN at.status IN ('Presente', 'Completa', 'Parcial') THEN at.accreditation_id END) AS y
            FROM accreditations a
            LEFT JOIN activity_attendance at ON at.accreditation_id = a.id
            WHERE a.event_id = ?
            GROUP BY label
            """,
            (event_id,),
        )
        return {"occupancy_vs_capacity": occupancy, "attendance_vs_registration": attendance, "participation_by_source": by_source}

    def _forecast(self, event: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        registrations = payload["series"]["registrations"]
        recent = registrations[-6:]
        hourly_rate = round(sum(int(row.get("value") or 0) for row in recent) / max(len(recent), 1), 1)
        registered = sum(int(row.get("value") or 0) for row in registrations)
        capacity = int(event.get("capacity") or 0)
        remaining_hours = 0.0
        try:
            end = datetime.fromisoformat(str(event.get("ends_at") or "").replace("Z", "+00:00"))
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            remaining_hours = max(0.0, (end - datetime.now(timezone.utc)).total_seconds() / 3600)
        except ValueError:
            remaining_hours = 0.0
        projected = int(round(registered + hourly_rate * min(remaining_hours, 72)))
        if capacity:
            projected = min(projected, capacity)
        accesses = payload["series"]["accesses"]
        recent_access = [int(row.get("value") or 0) for row in accesses[-15:]]
        access_rate = round(sum(recent_access) / max(len(recent_access), 1), 1)
        rooms = payload["heatmaps"]["rooms"]
        estimated_occupancy = round(sum(int(row.get("percentage") or 0) for row in rooms) / max(len(rooms), 1))
        hours_to_capacity = round(max(0, capacity - registered) / hourly_rate, 1) if capacity and hourly_rate > 0 else None
        return {
            "registration_rate_per_hour": hourly_rate,
            "expected_final_registrations": projected,
            "access_rate_per_minute": access_rate,
            "estimated_room_occupancy": estimated_occupancy,
            "hours_to_capacity": hours_to_capacity,
            "capacity": capacity,
            "current_registrations": registered,
        }

    def _predictive_alerts(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        forecast = payload["forecast"]
        alerts: list[dict[str, str]] = []
        if forecast["hours_to_capacity"] is not None and forecast["hours_to_capacity"] <= 4:
            alerts.append({"level": "critical", "title": "Cupo proximo a agotarse", "message": f"Proyeccion: {forecast['hours_to_capacity']} h"})
        if forecast["access_rate_per_minute"] >= 10:
            alerts.append({"level": "warning", "title": "Pico de accesos proyectado", "message": f"{forecast['access_rate_per_minute']} accesos/min"})
        for room in payload["heatmaps"]["rooms"]:
            if int(room.get("percentage") or 0) >= 90:
                alerts.append({"level": "critical", "title": "Sala proxima a saturacion", "message": f"{room['label']}: {room['percentage']}%"})
        funnel = payload["funnel"]
        for index in range(1, len(funnel)):
            previous = max(1, int(funnel[index - 1]["value"]))
            loss_rate = int(funnel[index]["loss"]) * 100 / previous
            if loss_rate >= 50:
                alerts.append({"level": "warning", "title": "Perdida en funnel", "message": f"{funnel[index - 1]['label']} -> {funnel[index]['label']}: {round(loss_rate)}%"})
        return alerts[:8]

    @staticmethod
    def _widgets_for_dashboard(dashboard: str, project_type: str = "conference") -> list[str]:
        if project_type == "ticketing":
            return ["ticketing_placeholder", "forecast", "communications"]
        widgets = {
            "operational": ["forecast", "access_series", "room_heatmap", "funnel", "alerts", "activity_ranking"],
            "executive": ["funnel", "registration_series", "forecast", "source_ranking", "attendance_scatter"],
            "commercial": ["registration_series", "source_ranking", "funnel", "forecast"],
            "academic": ["activity_heatmap", "activity_ranking", "attendance_scatter", "certificate_series"],
        }
        return widgets[dashboard]
