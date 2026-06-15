from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from backend.services.audit import AuditService


class AttendanceService:
    """Owns activity attendance and certificate eligibility rules."""

    def __init__(self, audit_service: AuditService, now: Callable[[], str]) -> None:
        self.audit_service = audit_service
        self.now = now

    def register_entry(self, db, token: str, activity_id: int, operator: str) -> dict:
        context = self._context(db, token, activity_id)
        if not context:
            return {"ok": False, "error": "Actividad o participante inexistente"}
        event, activity, accreditation, reservation = context
        if not int(event["controlar_asistencia"] or 0) or not int(activity["requiere_asistencia"] or 0):
            return {"ok": True, "ignored": True, "status": "No requerida", "eligibility_status": "Pendiente", "percentage": 0}
        current = db.execute(
            "SELECT * FROM activity_attendance WHERE activity_id = ? AND accreditation_id = ?",
            (activity_id, accreditation["id"]),
        ).fetchone()
        now = self.now()
        if current:
            if current["entry_at"]:
                return self._recalculate(db, current["id"], operator, "attendance.entry_repeated")
            db.execute(
                """
                UPDATE activity_attendance
                SET entry_at = ?, entry_operator = ?, updated_at = ?
                WHERE id = ?
                """,
                (now, operator, now, current["id"]),
            )
            attendance_id = int(current["id"])
        else:
            cur = db.execute(
                """
                INSERT INTO activity_attendance (
                    event_id, activity_id, accreditation_id, reservation_id,
                    entry_at, entry_operator, status, eligibility_status,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'presente', 'Pendiente', ?, ?)
                """,
                (
                    event["id"],
                    activity["id"],
                    accreditation["id"],
                    reservation["id"] if reservation else None,
                    now,
                    operator,
                    now,
                    now,
                ),
            )
            attendance_id = int(cur.lastrowid)
        result = self._recalculate(db, attendance_id, operator, "attendance.entry_registered")
        self.audit_service.record(
            db,
            operator,
            "attendance.entry_registered",
            "activity_attendance",
            attendance_id,
            {"event_id": event["id"], "activity_id": activity["id"], "accreditation_id": accreditation["id"]},
        )
        return result

    def register_exit(self, db, token: str, activity_id: int, operator: str) -> dict:
        context = self._context(db, token, activity_id)
        if not context:
            return {"ok": False, "error": "Actividad o participante inexistente"}
        event, activity, accreditation, _reservation = context
        if not int(event["controlar_asistencia"] or 0) or not int(activity["requiere_asistencia"] or 0):
            return {"ok": True, "ignored": True, "status": "No requerida", "eligibility_status": "Pendiente", "percentage": 0}
        row = db.execute(
            "SELECT * FROM activity_attendance WHERE activity_id = ? AND accreditation_id = ?",
            (activity_id, accreditation["id"]),
        ).fetchone()
        if not row or not row["entry_at"]:
            return {"ok": False, "error": "Primero debe registrarse el ingreso"}
        now = self.now()
        db.execute(
            """
            UPDATE activity_attendance
            SET exit_at = ?, exit_operator = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, operator, now, row["id"]),
        )
        result = self._recalculate(db, int(row["id"]), operator, "attendance.exit_registered")
        self.audit_service.record(
            db,
            operator,
            "attendance.exit_registered",
            "activity_attendance",
            int(row["id"]),
            {"event_id": event["id"], "activity_id": activity["id"], "accreditation_id": accreditation["id"]},
        )
        return result

    def manual_update(self, db, attendance_id: int, operator: str, status: str, percentage: int | None, reason: str) -> dict:
        row = db.execute(
            """
            SELECT at.*, act.porcentaje_minimo_asistencia, act.habilita_certificado, e.generar_certificados
            FROM activity_attendance at
            JOIN activities act ON act.id = at.activity_id
            JOIN events e ON e.id = at.event_id
            WHERE at.id = ?
            """,
            (attendance_id,),
        ).fetchone()
        if not row:
            return {"ok": False, "error": "Asistencia inexistente"}
        status = self._normalize_status(status)
        now = self.now()
        pct = max(0, min(100, int(percentage if percentage is not None else row["attendance_percentage"] or 0)))
        certificate_enabled = int(row["habilita_certificado"] or 0) and int(row["generar_certificados"] or 0)
        eligibility = self._eligibility(status, pct, row["porcentaje_minimo_asistencia"], certificate_enabled)
        db.execute(
            """
            UPDATE activity_attendance
            SET status = ?, attendance_percentage = ?, eligibility_status = ?,
                corrected_by = ?, correction_reason = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, pct, eligibility, operator, reason, now, attendance_id),
        )
        self._upsert_certificate(db, row["event_id"], row["activity_id"], row["accreditation_id"], pct, eligibility)
        action = "attendance.annulled" if status == "Anulada" else "attendance.manual_corrected"
        self.audit_service.record(
            db,
            operator,
            action,
            "activity_attendance",
            attendance_id,
            {"event_id": row["event_id"], "activity_id": row["activity_id"], "percentage": pct, "status": status, "reason": reason},
        )
        return {"ok": True, "id": attendance_id, "status": status, "percentage": pct, "eligibility_status": eligibility}

    def ensure_absences(self, db, event_id: int) -> None:
        rows = db.execute(
            """
            SELECT r.event_id, r.activity_id, r.accreditation_id, r.id AS reservation_id,
                   a.ends_at, a.porcentaje_minimo_asistencia, a.habilita_certificado,
                   e.generar_certificados
            FROM reservations r
            JOIN activities a ON a.id = r.activity_id
            JOIN events e ON e.id = r.event_id
            LEFT JOIN activity_attendance at ON at.activity_id = r.activity_id AND at.accreditation_id = r.accreditation_id
            WHERE r.event_id = ? AND r.status = 'confirmed' AND a.requiere_asistencia = 1 AND at.id IS NULL
            """,
            (event_id,),
        ).fetchall()
        now = self.now()
        for row in rows:
            finished = self._activity_finished(row["ends_at"])
            status = "Ausente" if finished else "Pendiente"
            certificate_enabled = int(row["habilita_certificado"] or 0) and int(row["generar_certificados"] or 0)
            eligibility = self._eligibility(status, 0, row["porcentaje_minimo_asistencia"], certificate_enabled)
            db.execute(
                """
                INSERT INTO activity_attendance (
                    event_id, activity_id, accreditation_id, reservation_id,
                    status, eligibility_status, attendance_percentage, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (row["event_id"], row["activity_id"], row["accreditation_id"], row["reservation_id"], status, eligibility, now, now),
            )
            self._upsert_certificate(db, row["event_id"], row["activity_id"], row["accreditation_id"], 0, eligibility)

    def _recalculate(self, db, attendance_id: int, operator: str, action: str) -> dict:
        row = db.execute(
            """
            SELECT at.*, e.attendance_mode AS event_attendance_mode, e.generar_certificados,
                   a.starts_at, a.ends_at, a.porcentaje_minimo_asistencia, a.habilita_certificado, a.attendance_mode
            FROM activity_attendance at
            JOIN events e ON e.id = at.event_id
            JOIN activities a ON a.id = at.activity_id
            WHERE at.id = ?
            """,
            (attendance_id,),
        ).fetchone()
        mode = row["attendance_mode"] or row["event_attendance_mode"] or "entry_only"
        percentage = 0
        minutes = 0
        status = "Pendiente"
        if row["entry_at"]:
            if mode == "entry_exit" and row["exit_at"]:
                minutes = self._minutes_between(row["entry_at"], row["exit_at"])
                total = max(1, self._minutes_between(row["starts_at"], row["ends_at"]))
                percentage = max(0, min(100, round((minutes / total) * 100)))
                status = "Completa" if percentage >= int(row["porcentaje_minimo_asistencia"] or 80) else "Parcial"
            elif mode == "entry_exit":
                status = "Presente"
                percentage = 0
            else:
                total = max(1, self._minutes_between(row["starts_at"], row["ends_at"]))
                minutes = total
                percentage = 100
                status = "Completa"
        certificate_enabled = int(row["habilita_certificado"] or 0) and int(row["generar_certificados"] or 0)
        eligibility = self._eligibility(status, percentage, row["porcentaje_minimo_asistencia"], certificate_enabled)
        now = self.now()
        db.execute(
            """
            UPDATE activity_attendance
            SET attended_minutes = ?, attendance_percentage = ?, status = ?, eligibility_status = ?, updated_at = ?
            WHERE id = ?
            """,
            (minutes, percentage, status, eligibility, now, attendance_id),
        )
        self._upsert_certificate(db, row["event_id"], row["activity_id"], row["accreditation_id"], percentage, eligibility)
        return {"ok": True, "id": attendance_id, "status": status, "percentage": percentage, "eligibility_status": eligibility}

    def _context(self, db, token: str, activity_id: int):
        row = db.execute(
            """
            SELECT ac.*, e.id AS event_id
            FROM accreditations ac
            JOIN events e ON e.id = ac.event_id
            WHERE ac.token = ?
            """,
            (token.strip().upper(),),
        ).fetchone()
        if not row:
            return None
        activity = db.execute("SELECT * FROM activities WHERE id = ? AND event_id = ?", (activity_id, row["event_id"])).fetchone()
        event = db.execute("SELECT * FROM events WHERE id = ?", (row["event_id"],)).fetchone()
        if not activity or not event:
            return None
        reservation = db.execute(
            "SELECT * FROM reservations WHERE activity_id = ? AND accreditation_id = ? AND status = 'confirmed'",
            (activity_id, row["id"]),
        ).fetchone()
        return event, activity, row, reservation

    def _eligibility(self, status: str, percentage: int, minimum: int, enabled: int) -> str:
        if not int(enabled or 0) or status in {"Pendiente", "Presente"}:
            return "Pendiente"
        if status in {"Ausente", "Anulada"}:
            return "No elegible"
        return "Elegible" if int(percentage or 0) >= int(minimum or 80) else "No elegible"

    def _upsert_certificate(self, db, event_id: int, activity_id: int, accreditation_id: int, percentage: int, eligibility: str) -> None:
        now = self.now()
        db.execute(
            """
            INSERT INTO certificate_eligibility (
                event_id, activity_id, accreditation_id, porcentaje, elegible, estado, fecha_calculo
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(activity_id, accreditation_id)
            DO UPDATE SET porcentaje = excluded.porcentaje,
                          elegible = excluded.elegible,
                          estado = excluded.estado,
                          fecha_calculo = excluded.fecha_calculo
            """,
            (event_id, activity_id, accreditation_id, int(percentage or 0), 1 if eligibility == "Elegible" else 0, eligibility, now),
        )

    def _minutes_between(self, start: str, end: str) -> int:
        try:
            start_dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            return max(0, round((end_dt - start_dt).total_seconds() / 60))
        except ValueError:
            return 0

    def _normalize_status(self, status: str) -> str:
        mapping = {
            "pendiente": "Pendiente",
            "presente": "Presente",
            "ausente": "Ausente",
            "parcial": "Parcial",
            "completa": "Completa",
            "anulada": "Anulada",
        }
        return mapping.get(status.strip().lower(), "Pendiente")

    def _activity_finished(self, ends_at: str) -> bool:
        try:
            end_dt = datetime.fromisoformat(str(ends_at).replace("Z", "+00:00"))
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            return end_dt < datetime.now(timezone.utc)
        except ValueError:
            return False
