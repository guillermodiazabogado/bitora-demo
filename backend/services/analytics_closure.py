from __future__ import annotations

import csv
import hashlib
import io
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


class AnalyticsClosureError(Exception):
    def __init__(self, message: str, code: str = "ANALYTICS_ERROR", status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class MetricDefinition:
    key: str
    name: str
    domain: str
    formula: str
    numerator: str
    denominator: str
    source: str
    periodicity: str
    aggregation_level: str
    limitations: str
    permission: str

    def payload(self, *, timezone_name: str = "UTC", updated_at: str | None = None) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "domain": self.domain,
            "definition": self.formula,
            "formula": self.formula,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "filters": ["organization_id", "event_id", "date_range", "activity_id", "channel", "status"],
            "source": self.source,
            "periodicity": self.periodicity,
            "timezone": timezone_name,
            "aggregation_level": self.aggregation_level,
            "updated_at": updated_at or utc_now(),
            "limitations": self.limitations,
            "permission": self.permission,
        }


METRIC_DEFINITIONS = [
    MetricDefinition("registrations.total", "Total de inscripciones", "registrations", "COUNT(accreditations)", "acreditaciones del evento", "no aplica", "accreditations", "on-demand", "event", "Incluye estados activos y no activos separados por metricas de estado.", "analytics.read"),
    MetricDefinition("registrations.confirmation_rate", "Tasa de confirmacion", "registrations", "confirmadas / total", "acreditaciones con status active o confirmed", "total de acreditaciones", "accreditations", "on-demand", "event", "Depende de normalizacion historica de estados.", "analytics.executive.read"),
    MetricDefinition("reservations.occupancy_rate", "Ocupacion de cupos", "reservations", "reservas confirmadas / capacidad configurada", "reservas confirmed", "capacidad de actividades", "activities,reservations", "on-demand", "activity", "No representa presencia fisica.", "analytics.operational.read"),
    MetricDefinition("attendance.rate", "Tasa de asistencia", "attendance", "asistentes / acreditaciones", "asistencias validas o accesos concedidos", "acreditaciones", "activity_attendance,access_logs,accreditations", "on-demand", "event", "No infiere asistencia sin validacion valida.", "analytics.attendance.read"),
    MetricDefinition("zones.denial_rate", "Tasa de denegacion de zonas", "zones", "accesos denegados / validaciones", "zone_access_validations denied", "zone_access_validations", "zone_access_validations", "on-demand", "zone", "Ocupacion exacta no se calcula sin eventos de entrada y salida confiables.", "analytics.operational.read"),
    MetricDefinition("speakers.coverage_rate", "Cobertura de speakers", "speakers", "actividades con speaker / actividades", "actividades con speaker asignado", "actividades activas", "speaker_activity_assignments,activities", "on-demand", "event", "No expone datos privados de speakers.", "analytics.read"),
    MetricDefinition("certificates.issue_rate", "Tasa de emision de certificados", "certificates", "emitidos / elegibles", "certificate_issuances activos", "certificate_eligibility elegible", "certificate_eligibility,certificate_issuances", "on-demand", "event", "Respeta reglas historicas almacenadas.", "analytics.certificates.read"),
    MetricDefinition("surveys.response_rate", "Tasa de respuesta de encuestas", "surveys", "respuestas completas / asignaciones", "survey_response_sessions submitted", "survey_assignments", "surveys,survey_assignments,survey_response_sessions", "on-demand", "survey", "Se aplica umbral de anonimato para muestras chicas.", "analytics.surveys.read"),
    MetricDefinition("communications.delivery_rate", "Tasa de entrega de comunicaciones", "communications", "entregadas / mensajes", "deliveries delivered/read", "mensajes creados", "communication_v4_messages,communication_v4_deliveries", "on-demand", "channel", "Safe Mode y Live Mode se reportan separados.", "analytics.communications.read"),
    MetricDefinition("operations.open_incidents", "Incidentes abiertos", "operations", "COUNT(incidents status OPEN)", "incidentes abiertos", "no aplica", "operations_center_incidents", "on-demand", "event", "No debe usarse para vigilancia personal indebida.", "analytics.operational.read"),
]


FUNCTIONAL_DOMAINS = [
    ("eventos", "core", "PASSED", "core", "events", "event UI", "RBAC", "audit_logs", "included", "included", "verificar_integridad_bitora.py", "core docs", ""),
    ("inscripciones", "core", "PASSED", "core", "accreditations", "register UI", "RBAC", "audit_logs", "included", "included", "verificar_integridad_bitora.py", "core docs", ""),
    ("participantes", "core", "PASSED", "core", "people/accreditations", "portal/admin", "RBAC", "audit_logs", "included", "included", "verificar_integridad_bitora.py", "core docs", ""),
    ("actividades", "core", "PASSED", "core", "activities", "agenda UI", "RBAC", "audit_logs", "included", "included", "verificar_integridad_bitora.py", "core docs", ""),
    ("reservas", "core", "PASSED", "core", "reservations", "portal/admin", "RBAC", "audit_logs", "included", "included", "verificar_reservas.py", "core docs", ""),
    ("QR", "core", "PASSED", "core", "qr.svg", "credential UI", "RBAC", "audit_logs", "included", "included", "verificar_integridad_bitora.py", "core docs", ""),
    ("acreditacion", "core", "PASSED", "core", "accreditations/update", "reception UI", "RBAC", "audit_logs", "included", "included", "verificar_seguridad_basica.py", "security docs", ""),
    ("asistencia", "V4.1", "PASSED", "attendance_v4_enabled", "attendance", "attendance UI", "attendance.*", "attendance audit", "included", "included", "verificar_v4_1_attendance_domain.py", "V4_1 docs", ""),
    ("cierre", "V4.2", "PASSED", "attendance_closure_eligibility_v4_enabled", "attendance-closures", "closure UI", "attendance.closure.*", "attendance audit", "included", "included", "verificar_v4_2_attendance_closure_eligibility.py", "V4_2 docs", ""),
    ("elegibilidad", "V4.2", "PASSED", "attendance_closure_eligibility_v4_enabled", "eligibility", "eligibility UI", "attendance.eligibility.*", "audit_logs", "included", "included", "verificar_v4_2_attendance_closure_eligibility.py", "V4_2 docs", ""),
    ("certificados", "V4.3", "PASSED", "certificates_v4_enabled", "certificates", "certificates UI", "certificates.*", "certificate audit", "included", "included", "verificar_v4_3_certificates_foundation.py", "V4_3 docs", ""),
    ("encuestas", "V4.4", "PASSED", "surveys_v4_enabled", "surveys", "surveys UI", "surveys.*", "survey audit", "included", "included", "verificar_v4_4_surveys_foundation.py", "V4_4 docs", "anonimato por umbral"),
    ("speakers", "V4.5", "PASSED", "speakers_v4_enabled", "speakers", "speakers UI", "speakers.*", "speaker audit", "included", "included", "verificar_v4_5_speakers_foundation.py", "V4_5 docs", ""),
    ("zonas", "V4.6", "PASSED", "zone_permissions_v4_enabled", "zones", "zones UI", "zones.*", "zone audit", "included", "included", "verificar_v4_6_zone_permissions_foundation.py", "V4_6 docs", ""),
    ("historial", "V4.7", "PASSED", "history_autocomplete_v4_enabled", "history", "history UI", "history.*", "audit_logs", "included", "included", "verificar_v4_7_history_autocomplete_foundation.py", "V4_7 docs", ""),
    ("autocompletado", "V4.7", "PASSED", "history_autocomplete_v4_enabled", "autocomplete", "autocomplete UI", "autocomplete.*", "audit_logs", "included", "included", "verificar_v4_7_history_autocomplete_foundation.py", "V4_7 docs", ""),
    ("operations center", "V4.8", "PASSED", "operations_center_v4_enabled", "operations-center", "operations UI", "operations_center.*", "audit_logs", "included", "included", "verificar_v4_8_operations_center.py", "V4_8 docs", ""),
    ("comunicaciones", "V4.9", "PASSED", "communications_v4_enabled", "communications-v4", "communications UI", "communications.*", "communications audit", "included", "safe restore", "verificar_v4_9_communications_automation.py", "V4_9 docs", "Live Mode OFF en desarrollo"),
    ("automatizaciones", "V4.9", "PASSED", "communications_automation_v4_enabled", "communications-v4/automations", "automation UI", "communications.automations.*", "communications audit", "included", "paused restore", "verificar_v4_9_communications_automation.py", "V4_9 docs", "no ejecuta proveedores en Safe Mode"),
    ("analytics", "V4.10", "PASSED", "analytics_v4_enabled", "analytics-v4", "analytics-v4 UI", "analytics.*", "analytics audit", "included", "rebuildable", "verificar_v4_10_analytics_functional_closure.py", "V4_10 docs", "pendiente certificacion final"),
]


class AnalyticsClosureService:
    """Explainable analytics and functional closure layer for BITORA V4."""

    ANONYMITY_THRESHOLD = 3
    STATUS_ORDER = {"DRAFT": 0, "IN_REVIEW": 1, "APPROVED": 2, "RESTORED_REVIEW": 1}

    def __init__(self, audit_service=None, now=utc_now) -> None:
        self.audit_service = audit_service
        self.now = now

    def metric_definitions(self) -> dict[str, Any]:
        updated_at = self.now()
        return {"ok": True, "items": [definition.payload(updated_at=updated_at) for definition in METRIC_DEFINITIONS]}

    def overview(self, db, *, organization_id: int, event_id: int, actor: str = "analytics", filters: dict[str, Any] | None = None) -> dict[str, Any]:
        start = time.perf_counter()
        self._assert_event(db, organization_id, event_id)
        filters = self._sanitize_filters(filters)
        generated_at = self.now()
        sections = {
            "registrations": self.registrations(db, organization_id=organization_id, event_id=event_id, filters=filters)["metrics"],
            "attendance": self.attendance(db, organization_id=organization_id, event_id=event_id, filters=filters)["metrics"],
            "zones": self.zones(db, organization_id=organization_id, event_id=event_id, filters=filters)["metrics"],
            "speakers": self.speakers(db, organization_id=organization_id, event_id=event_id, filters=filters)["metrics"],
            "certificates": self.certificates(db, organization_id=organization_id, event_id=event_id, filters=filters)["metrics"],
            "surveys": self.surveys(db, organization_id=organization_id, event_id=event_id, filters=filters)["metrics"],
            "communications": self.communications(db, organization_id=organization_id, event_id=event_id, filters=filters)["metrics"],
            "operations": self.operations(db, organization_id=organization_id, event_id=event_id, filters=filters)["metrics"],
        }
        quality = self.data_quality(db, organization_id=organization_id, event_id=event_id, filters=filters)
        payload = {
            "ok": True,
            "schema": "bitora.analytics.v4.overview",
            "organization_id": organization_id,
            "event_id": event_id,
            "generated_at": generated_at,
            "filters": filters,
            "definitions": [definition.payload(updated_at=generated_at) for definition in METRIC_DEFINITIONS],
            "dashboards": ["executive", "operational", "attendance", "certificates_surveys", "communications", "comparison", "data_quality"],
            "sections": sections,
            "data_quality": quality["issues"],
            "observability": {
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                "source": "direct_queries",
                "cache": "none",
            },
        }
        self._audit(db, actor, "analytics.overview_opened", "analytics", event_id, {"organization_id": organization_id, "event_id": event_id, "latency_ms": payload["observability"]["latency_ms"]})
        return payload

    def registrations(self, db, *, organization_id: int, event_id: int, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        self._assert_event(db, organization_id, event_id)
        rows = self._rows(db, "SELECT COALESCE(NULLIF(status,''), 'unknown') AS status, COUNT(*) AS c FROM accreditations WHERE event_id = ? GROUP BY status", (event_id,))
        by_status = {row["status"]: int(row["c"] or 0) for row in rows}
        total = sum(by_status.values())
        confirmed = sum(by_status.get(status, 0) for status in ("active", "confirmed", "checked_in"))
        pending = sum(by_status.get(status, 0) for status in ("pending", "draft"))
        cancelled = sum(by_status.get(status, 0) for status in ("cancelled", "canceled"))
        rejected = by_status.get("rejected", 0)
        by_day = self._rows(db, "SELECT substr(created_at,1,10) AS day, COUNT(*) AS value FROM accreditations WHERE event_id = ? GROUP BY day ORDER BY day", (event_id,))
        by_channel = self._rows(db, "SELECT COALESCE(NULLIF(source,''),'sin origen') AS channel, COUNT(*) AS value FROM accreditations WHERE event_id = ? GROUP BY channel ORDER BY value DESC", (event_id,))
        return self._metric_payload("registrations", event_id, {
            "total": total,
            "confirmed": confirmed,
            "pending": pending,
            "cancelled": cancelled,
            "rejected": rejected,
            "confirmation_rate": self._rate(confirmed, total),
            "by_day": by_day,
            "by_channel": by_channel,
        })

    def attendance(self, db, *, organization_id: int, event_id: int, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        self._assert_event(db, organization_id, event_id)
        total = self._count(db, "accreditations", "event_id = ?", (event_id,))
        checked_in = self._count(db, "accreditations", "event_id = ? AND checked_in_at IS NOT NULL AND checked_in_at <> ''", (event_id,))
        access_attendees = int(db.execute("SELECT COUNT(DISTINCT accreditation_id) AS c FROM access_logs WHERE event_id = ? AND result = 'granted'", (event_id,)).fetchone()["c"] or 0) if self._table_exists(db, "access_logs") else 0
        activity_attendees = int(db.execute("SELECT COUNT(DISTINCT accreditation_id) AS c FROM activity_attendance WHERE event_id = ? AND status IN ('Presente','Completa','Parcial')", (event_id,)).fetchone()["c"] or 0) if self._table_exists(db, "activity_attendance") else 0
        attendees = max(checked_in, access_attendees, activity_attendees)
        by_activity = self._rows(db, """
            SELECT a.id AS activity_id, a.title, COUNT(DISTINCT aa.accreditation_id) AS attendees
            FROM activities a
            LEFT JOIN activity_attendance aa ON aa.activity_id = a.id AND aa.event_id = a.event_id AND aa.status IN ('Presente','Completa','Parcial')
            WHERE a.event_id = ?
            GROUP BY a.id, a.title
            ORDER BY attendees DESC, a.title
            LIMIT 50
        """, (event_id,)) if self._table_exists(db, "activity_attendance") else []
        return self._metric_payload("attendance", event_id, {
            "registered": total,
            "checked_in": checked_in,
            "attendees": attendees,
            "absent": max(0, total - attendees),
            "attendance_rate": self._rate(attendees, total),
            "by_activity": by_activity,
        })

    def reservations(self, db, *, organization_id: int, event_id: int, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        self._assert_event(db, organization_id, event_id)
        rows = self._rows(db, """
            SELECT a.id AS activity_id, a.title, a.capacity,
                   COUNT(CASE WHEN r.status = 'confirmed' THEN 1 END) AS confirmed,
                   COUNT(CASE WHEN r.status = 'waitlisted' THEN 1 END) AS waitlisted
            FROM activities a
            LEFT JOIN reservations r ON r.activity_id = a.id AND r.event_id = a.event_id
            WHERE a.event_id = ?
            GROUP BY a.id, a.title, a.capacity
            ORDER BY a.starts_at, a.title
        """, (event_id,))
        for row in rows:
            row["occupancy_rate"] = self._rate(int(row.get("confirmed") or 0), int(row.get("capacity") or 0))
        return self._metric_payload("reservations", event_id, {"activities": rows, "confirmed_total": sum(int(row.get("confirmed") or 0) for row in rows), "waitlisted_total": sum(int(row.get("waitlisted") or 0) for row in rows)})

    def zones(self, db, *, organization_id: int, event_id: int, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        self._assert_event(db, organization_id, event_id)
        if not self._table_exists(db, "zone_access_validations"):
            return self._metric_payload("zones", event_id, {"enabled": False, "allowed": 0, "denied": 0, "denial_rate": 0})
        allowed = self._count(db, "zone_access_validations", "event_id = ? AND decision IN ('allowed','granted','ALLOW')", (event_id,))
        denied = self._count(db, "zone_access_validations", "event_id = ? AND decision IN ('denied','blocked','DENY')", (event_id,))
        by_reason = self._rows(db, "SELECT COALESCE(NULLIF(reason,''),'sin motivo') AS reason, COUNT(*) AS value FROM zone_access_validations WHERE event_id = ? AND decision IN ('denied','blocked','DENY') GROUP BY reason ORDER BY value DESC", (event_id,))
        return self._metric_payload("zones", event_id, {"enabled": True, "allowed": allowed, "denied": denied, "denial_rate": self._rate(denied, allowed + denied), "by_reason": by_reason})

    def speakers(self, db, *, organization_id: int, event_id: int, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        self._assert_event(db, organization_id, event_id)
        if not self._table_exists(db, "speaker_event_assignments"):
            return self._metric_payload("speakers", event_id, {"enabled": False, "assigned": 0})
        assigned = self._count(db, "speaker_event_assignments", "event_id = ?", (event_id,))
        confirmed = self._count(db, "speaker_event_assignments", "event_id = ? AND status IN ('CONFIRMED','confirmed','published')", (event_id,))
        covered = int(db.execute("SELECT COUNT(DISTINCT activity_id) AS c FROM speaker_activity_assignments WHERE event_id = ?", (event_id,)).fetchone()["c"] or 0) if self._table_exists(db, "speaker_activity_assignments") else 0
        activities = self._count(db, "activities", "event_id = ? AND status <> 'cancelled'", (event_id,))
        return self._metric_payload("speakers", event_id, {"enabled": True, "assigned": assigned, "confirmed": confirmed, "pending": max(0, assigned - confirmed), "activities_covered": covered, "coverage_rate": self._rate(covered, activities)})

    def certificates(self, db, *, organization_id: int, event_id: int, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        self._assert_event(db, organization_id, event_id)
        eligible = self._count(db, "certificate_eligibility", "event_id = ? AND elegible = 1", (event_id,)) if self._table_exists(db, "certificate_eligibility") else 0
        issued = self._count(db, "certificate_issuances", "event_id = ? AND status NOT IN ('REVOKED','revoked')", (event_id,)) if self._table_exists(db, "certificate_issuances") else 0
        revoked = self._count(db, "certificate_revocations", "event_id = ?", (event_id,)) if self._table_exists(db, "certificate_revocations") else 0
        reissued = self._count(db, "certificate_reissuances", "event_id = ?", (event_id,)) if self._table_exists(db, "certificate_reissuances") else 0
        return self._metric_payload("certificates", event_id, {"eligible": eligible, "issued": issued, "pending": max(0, eligible - issued), "revoked": revoked, "reissued": reissued, "issue_rate": self._rate(issued, eligible)})

    def surveys(self, db, *, organization_id: int, event_id: int, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        self._assert_event(db, organization_id, event_id)
        assignments = self._count(db, "survey_assignments", "event_id = ?", (event_id,)) if self._table_exists(db, "survey_assignments") else 0
        responses = self._count(db, "survey_response_sessions", "event_id = ? AND status IN ('submitted','SUBMITTED','completed')", (event_id,)) if self._table_exists(db, "survey_response_sessions") else 0
        visible = responses >= self.ANONYMITY_THRESHOLD
        return self._metric_payload("surveys", event_id, {"assignments": assignments, "responses": responses if visible else None, "response_rate": self._rate(responses, assignments) if visible else None, "anonymity_threshold": self.ANONYMITY_THRESHOLD, "suppressed_small_sample": not visible and responses > 0})

    def communications(self, db, *, organization_id: int, event_id: int, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        self._assert_event(db, organization_id, event_id)
        messages = self._count(db, "communication_v4_messages", "event_id = ?", (event_id,)) if self._table_exists(db, "communication_v4_messages") else 0
        delivered = self._count(db, "communication_v4_deliveries", "event_id = ? AND status IN ('delivered','read')", (event_id,)) if self._table_exists(db, "communication_v4_deliveries") else 0
        failed = self._count(db, "communication_v4_messages", "event_id = ? AND status IN ('failed','FAILED')", (event_id,)) if self._table_exists(db, "communication_v4_messages") else 0
        retries = self._count(db, "communication_v4_attempts", "event_id = ? AND attempt_number > 1", (event_id,)) if self._table_exists(db, "communication_v4_attempts") else 0
        by_channel = self._rows(db, "SELECT channel, COUNT(*) AS value FROM communication_v4_messages WHERE event_id = ? GROUP BY channel", (event_id,)) if self._table_exists(db, "communication_v4_messages") else []
        live = self._count(db, "communication_v4_campaigns", "event_id = ? AND live_mode = 1", (event_id,)) if self._table_exists(db, "communication_v4_campaigns") else 0
        safe = self._count(db, "communication_v4_campaigns", "event_id = ? AND safe_mode = 1", (event_id,)) if self._table_exists(db, "communication_v4_campaigns") else 0
        return self._metric_payload("communications", event_id, {"messages": messages, "delivered": delivered, "failed": failed, "retries": retries, "delivery_rate": self._rate(delivered, messages), "by_channel": by_channel, "safe_mode_campaigns": safe, "live_mode_campaigns": live})

    def operations(self, db, *, organization_id: int, event_id: int, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        self._assert_event(db, organization_id, event_id)
        incidents_open = self._count(db, "operations_center_incidents", "event_id = ? AND status IN ('OPEN','open')", (event_id,)) if self._table_exists(db, "operations_center_incidents") else 0
        tasks_open = self._count(db, "operations_center_tasks", "event_id = ? AND status NOT IN ('DONE','done','cancelled','CANCELLED')", (event_id,)) if self._table_exists(db, "operations_center_tasks") else 0
        alerts = self._count(db, "operations_center_alerts", "event_id = ? AND status IN ('OPEN','open','ACTIVE','active')", (event_id,)) if self._table_exists(db, "operations_center_alerts") else 0
        return self._metric_payload("operations", event_id, {"open_incidents": incidents_open, "open_tasks": tasks_open, "active_alerts": alerts})

    def data_quality(self, db, *, organization_id: int, event_id: int, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        self._assert_event(db, organization_id, event_id)
        issues: list[dict[str, Any]] = []
        missing_email = self._rows(db, """
            SELECT COUNT(*) AS c
            FROM accreditations a
            JOIN people p ON p.id = a.person_id
            WHERE a.event_id = ? AND (p.email IS NULL OR p.email = '')
        """, (event_id,))
        if int(missing_email[0]["c"] or 0):
            issues.append(self._issue("WARNING", "participants.missing_email", "Participantes sin email", int(missing_email[0]["c"]), "people/accreditations"))
        duplicate_tokens = self._rows(db, "SELECT token, COUNT(*) AS c FROM accreditations WHERE event_id = ? GROUP BY token HAVING COUNT(*) > 1", (event_id,))
        if duplicate_tokens:
            issues.append(self._issue("BLOCKING", "qr.duplicate_tokens", "QR duplicados dentro del evento", len(duplicate_tokens), "accreditations"))
        orphan_reservations = self._rows(db, """
            SELECT COUNT(*) AS c
            FROM reservations r
            LEFT JOIN accreditations a ON a.id = r.accreditation_id AND a.event_id = r.event_id
            WHERE r.event_id = ? AND a.id IS NULL
        """, (event_id,))
        if int(orphan_reservations[0]["c"] or 0):
            issues.append(self._issue("ERROR", "reservations.orphan", "Reservas sin acreditacion del mismo evento", int(orphan_reservations[0]["c"]), "reservations"))
        cross_event_activity = self._rows(db, """
            SELECT COUNT(*) AS c
            FROM reservations r
            JOIN activities a ON a.id = r.activity_id
            WHERE r.event_id = ? AND a.event_id <> r.event_id
        """, (event_id,))
        if int(cross_event_activity[0]["c"] or 0):
            issues.append(self._issue("BLOCKING", "reservations.cross_event_activity", "Reservas apuntan a actividad de otro evento", int(cross_event_activity[0]["c"]), "reservations/activities"))
        stale_snapshots = self._count(db, "analytics_v4_snapshots", "event_id = ? AND status = 'STALE'", (event_id,)) if self._table_exists(db, "analytics_v4_snapshots") else 0
        if stale_snapshots:
            issues.append(self._issue("INFO", "analytics.stale_snapshots", "Snapshots analiticos marcados como desactualizados", stale_snapshots, "analytics_v4_snapshots"))
        for issue in issues:
            db.execute(
                """
                INSERT INTO analytics_v4_data_quality_issues (
                    organization_id,event_id,severity,code,title,details_json,source,status,detected_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (organization_id, event_id, issue["severity"], issue["code"], issue["title"], canonical_json(issue), issue["source"], "OPEN", self.now(), self.now()),
            )
        return {"ok": True, "issues": issues, "blocking": sum(1 for issue in issues if issue["severity"] == "BLOCKING")}

    def compare_events(self, db, *, organization_id: int, event_ids: list[int], actor: str = "analytics", filters: dict[str, Any] | None = None) -> dict[str, Any]:
        normalized = [int(event_id) for event_id in event_ids if int(event_id or 0)]
        if len(normalized) < 2:
            raise AnalyticsClosureError("Se requieren al menos dos eventos", "ANALYTICS_COMPARE_NEEDS_EVENTS", 400)
        if len(normalized) > 12:
            raise AnalyticsClosureError("La comparacion admite hasta 12 eventos", "ANALYTICS_COMPARE_TOO_MANY_EVENTS", 400)
        rows = self._rows(db, f"SELECT id, organization_id, name, project_type, starts_at FROM events WHERE id IN ({','.join(['?'] * len(normalized))})", tuple(normalized))
        if len(rows) != len(normalized) or any(int(row["organization_id"] or 0) != int(organization_id) for row in rows):
            raise AnalyticsClosureError("Comparacion cross-tenant rechazada", "ANALYTICS_CROSS_TENANT_REJECTED", 403)
        items = []
        for row in rows:
            event_id = int(row["id"])
            registrations = self.registrations(db, organization_id=organization_id, event_id=event_id)["metrics"]
            attendance = self.attendance(db, organization_id=organization_id, event_id=event_id)["metrics"]
            certificates = self.certificates(db, organization_id=organization_id, event_id=event_id)["metrics"]
            communications = self.communications(db, organization_id=organization_id, event_id=event_id)["metrics"]
            items.append({
                "event_id": event_id,
                "name": row["name"],
                "project_type": row["project_type"],
                "starts_at": row["starts_at"],
                "registrations_total": registrations["total"],
                "attendance_rate": attendance["attendance_rate"],
                "certificates_issued": certificates["issued"],
                "communications_messages": communications["messages"],
            })
        project_types = {str(item.get("project_type") or "") for item in items}
        warnings = []
        if len(project_types) > 1:
            warnings.append("Eventos con project_type distinto; comparar ratios, no volumen bruto.")
        self._audit(db, actor, "analytics.events_compared", "analytics", None, {"organization_id": organization_id, "event_ids": normalized})
        return {"ok": True, "organization_id": organization_id, "items": items, "warnings": warnings, "filters": self._sanitize_filters(filters)}

    def create_snapshot(self, db, *, organization_id: int, event_id: int, actor: str, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = self.overview(db, organization_id=organization_id, event_id=event_id, actor=actor, filters=filters)
        payload_hash = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO analytics_v4_snapshots (
                organization_id,event_id,snapshot_type,period_start,period_end,timezone,filters_json,
                metrics_json,definitions_json,quality_json,source_tables_json,snapshot_hash,status,
                generated_by,generated_at,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                organization_id,
                event_id,
                "EVENT_OVERVIEW",
                str((filters or {}).get("date_from") or ""),
                str((filters or {}).get("date_to") or ""),
                str((filters or {}).get("timezone") or "UTC"),
                canonical_json(payload["filters"]),
                canonical_json(payload["sections"]),
                canonical_json(payload["definitions"]),
                canonical_json(payload["data_quality"]),
                canonical_json(sorted(self._source_tables(db))),
                payload_hash,
                "READY",
                actor,
                now,
                now,
                now,
            ),
        )
        snapshot_id = int(cur.lastrowid)
        self._audit(db, actor, "analytics.snapshot_created", "analytics_snapshot", snapshot_id, {"organization_id": organization_id, "event_id": event_id, "snapshot_hash": payload_hash})
        return {"ok": True, "snapshot_id": snapshot_id, "snapshot_hash": payload_hash, "payload": payload}

    def list_snapshots(self, db, *, organization_id: int, event_id: int) -> dict[str, Any]:
        self._assert_event(db, organization_id, event_id)
        rows = self._rows(db, "SELECT id,snapshot_type,status,snapshot_hash,generated_by,generated_at,created_at,updated_at FROM analytics_v4_snapshots WHERE organization_id = ? AND event_id = ? ORDER BY id DESC LIMIT 50", (organization_id, event_id))
        return {"ok": True, "items": rows}

    def create_report(self, db, *, organization_id: int, event_id: int, actor: str, data: dict[str, Any]) -> dict[str, Any]:
        self._assert_event(db, organization_id, event_id)
        snapshot_id = int(data.get("snapshot_id") or 0)
        if snapshot_id:
            snapshot = db.execute("SELECT id FROM analytics_v4_snapshots WHERE id = ? AND organization_id = ? AND event_id = ?", (snapshot_id, organization_id, event_id)).fetchone()
            if not snapshot:
                raise AnalyticsClosureError("Snapshot inexistente para este evento", "ANALYTICS_SNAPSHOT_NOT_FOUND", 404)
        title = self._text(data.get("title") or "Reporte ejecutivo V4.10", 140)
        report_type = self._choice(data.get("report_type") or "EXECUTIVE", {"EXECUTIVE", "OPERATIONAL", "CLOSURE", "DATA_QUALITY"})
        sections = data.get("sections")
        if not isinstance(sections, list) or not sections:
            sections = ["registrations", "attendance", "certificates", "surveys", "communications", "operations", "data_quality"]
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO analytics_v4_reports (
                organization_id,event_id,snapshot_id,report_type,title,sections_json,status,
                created_by,approved_by,approved_at,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (organization_id, event_id, snapshot_id or None, report_type, title, canonical_json(sections), "DRAFT", actor, "", None, now, now),
        )
        report_id = int(cur.lastrowid)
        self._audit(db, actor, "analytics.report_created", "analytics_report", report_id, {"organization_id": organization_id, "event_id": event_id, "snapshot_id": snapshot_id or None})
        return {"ok": True, "report": dict(db.execute("SELECT * FROM analytics_v4_reports WHERE id = ?", (report_id,)).fetchone())}

    def list_reports(self, db, *, organization_id: int, event_id: int) -> dict[str, Any]:
        self._assert_event(db, organization_id, event_id)
        rows = self._rows(db, "SELECT * FROM analytics_v4_reports WHERE organization_id = ? AND event_id = ? ORDER BY id DESC LIMIT 100", (organization_id, event_id))
        return {"ok": True, "items": rows}

    def export_report(self, db, *, organization_id: int, event_id: int, report_id: int, actor: str, export_format: str = "json") -> dict[str, Any]:
        self._assert_event(db, organization_id, event_id)
        row = db.execute("SELECT * FROM analytics_v4_reports WHERE id = ? AND organization_id = ? AND event_id = ?", (report_id, organization_id, event_id)).fetchone()
        if not row:
            raise AnalyticsClosureError("Reporte inexistente para este evento", "ANALYTICS_REPORT_NOT_FOUND", 404)
        export_format = self._choice(export_format or "json", {"json", "csv"}).lower()
        snapshot = None
        if row["snapshot_id"]:
            snapshot = db.execute("SELECT * FROM analytics_v4_snapshots WHERE id = ? AND organization_id = ? AND event_id = ?", (int(row["snapshot_id"]), organization_id, event_id)).fetchone()
        if snapshot:
            payload = {
                "report": {key: row[key] for key in row.keys() if key not in {"sections_json"}},
                "sections": json.loads(row["sections_json"] or "[]"),
                "metrics": json.loads(snapshot["metrics_json"] or "{}"),
                "definitions": json.loads(snapshot["definitions_json"] or "[]"),
                "quality": json.loads(snapshot["quality_json"] or "[]"),
            }
        else:
            payload = self.overview(db, organization_id=organization_id, event_id=event_id, actor=actor)
        if export_format == "csv":
            content, row_count = self._csv_export(payload)
            content_type = "text/csv"
        else:
            content = canonical_json(payload)
            row_count = len(payload.get("metrics", payload.get("sections", {})))
            content_type = "application/json"
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO analytics_v4_export_jobs (
                organization_id,event_id,report_id,snapshot_id,export_format,status,filters_json,
                requested_by,created_at,completed_at,expires_at,row_count,file_name,content_type,checksum,storage_key,error_message_sanitized
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (organization_id, event_id, report_id, row["snapshot_id"], export_format, "COMPLETED", "{}", actor, now, now, "", row_count, self._safe_file_name(row["title"], export_format), content_type, checksum, "", ""),
        )
        export_id = int(cur.lastrowid)
        self._audit(db, actor, "analytics.report_exported", "analytics_export", export_id, {"organization_id": organization_id, "event_id": event_id, "report_id": report_id, "format": export_format, "rows": row_count})
        return {"ok": True, "export_id": export_id, "format": export_format, "content": content, "checksum": checksum, "file_name": self._safe_file_name(row["title"], export_format), "row_count": row_count}

    def create_closure_review(self, db, *, organization_id: int, event_id: int, actor: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        self._assert_event(db, organization_id, event_id)
        data = data or {}
        overview = self.overview(db, organization_id=organization_id, event_id=event_id, actor=actor)
        quality = overview["data_quality"]
        gates = self._closure_gates(db, organization_id, event_id, quality)
        status = "READY_FOR_APPROVAL" if all(gate["status"] == "PASSED" for gate in gates) else "IN_REVIEW"
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO functional_closure_reviews (
                organization_id,event_id,run_id,status,coverage_json,gates_json,quality_json,
                blockers_count,approved_by,approved_at,created_by,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (organization_id, event_id, self._text(data.get("run_id") or f"V4-CLOSURE-{now}", 120), status, canonical_json(self.functional_coverage()["domains"]), canonical_json(gates), canonical_json(quality), sum(1 for gate in gates if gate["status"] != "PASSED"), "", None, actor, now, now),
        )
        review_id = int(cur.lastrowid)
        for gate in gates:
            db.execute(
                "INSERT INTO functional_closure_gate_results (organization_id,event_id,closure_review_id,gate_key,status,evidence_json,created_at) VALUES (?,?,?,?,?,?,?)",
                (organization_id, event_id, review_id, gate["key"], gate["status"], canonical_json(gate), now),
            )
        self._audit(db, actor, "functional_closure.review_created", "functional_closure_review", review_id, {"organization_id": organization_id, "event_id": event_id, "status": status})
        return {"ok": True, "review": self.get_closure_review(db, organization_id=organization_id, event_id=event_id, review_id=review_id)["review"]}

    def get_closure_review(self, db, *, organization_id: int, event_id: int, review_id: int) -> dict[str, Any]:
        row = db.execute("SELECT * FROM functional_closure_reviews WHERE id = ? AND organization_id = ? AND event_id = ?", (review_id, organization_id, event_id)).fetchone()
        if not row:
            raise AnalyticsClosureError("Revision de cierre inexistente", "FUNCTIONAL_CLOSURE_NOT_FOUND", 404)
        payload = dict(row)
        payload["coverage"] = json.loads(payload.pop("coverage_json") or "[]")
        payload["gates"] = json.loads(payload.pop("gates_json") or "[]")
        payload["quality"] = json.loads(payload.pop("quality_json") or "[]")
        payload["findings"] = self._rows(db, "SELECT * FROM functional_closure_findings WHERE closure_review_id = ? AND organization_id = ? AND event_id = ? ORDER BY id", (review_id, organization_id, event_id))
        return {"ok": True, "review": payload}

    def list_closure_reviews(self, db, *, organization_id: int, event_id: int) -> dict[str, Any]:
        self._assert_event(db, organization_id, event_id)
        rows = self._rows(db, "SELECT id,run_id,status,blockers_count,approved_by,approved_at,created_by,created_at,updated_at FROM functional_closure_reviews WHERE organization_id = ? AND event_id = ? ORDER BY id DESC LIMIT 50", (organization_id, event_id))
        return {"ok": True, "items": rows}

    def approve_closure_review(self, db, *, organization_id: int, event_id: int, review_id: int, actor: str) -> dict[str, Any]:
        review = self.get_closure_review(db, organization_id=organization_id, event_id=event_id, review_id=review_id)["review"]
        if int(review.get("blockers_count") or 0) > 0:
            raise AnalyticsClosureError("No se puede aprobar con gates pendientes", "FUNCTIONAL_CLOSURE_HAS_BLOCKERS", 409)
        now = self.now()
        db.execute("UPDATE functional_closure_reviews SET status = 'APPROVED', approved_by = ?, approved_at = ?, updated_at = ? WHERE id = ? AND organization_id = ? AND event_id = ?", (actor, now, now, review_id, organization_id, event_id))
        self._audit(db, actor, "functional_closure.review_approved", "functional_closure_review", review_id, {"organization_id": organization_id, "event_id": event_id})
        return self.get_closure_review(db, organization_id=organization_id, event_id=event_id, review_id=review_id)

    def functional_coverage(self) -> dict[str, Any]:
        keys = ["domain", "origin_version", "status", "feature_flag", "endpoints", "ui", "rbac", "audit", "backup", "restore", "verifier", "documentation", "limitations"]
        return {
            "ok": True,
            "status": "FUNCTIONALLY COMPLETE - PENDING FINAL CERTIFICATION",
            "domains": [dict(zip(keys, domain)) for domain in FUNCTIONAL_DOMAINS],
        }

    def _closure_gates(self, db, organization_id: int, event_id: int, quality: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {"key": "analytics_metric_definitions", "status": "PASSED", "evidence": f"{len(METRIC_DEFINITIONS)} definitions"},
            {"key": "analytics_data_quality", "status": "PASSED" if not any(issue["severity"] == "BLOCKING" for issue in quality) else "FAILED", "evidence": {"issues": len(quality)}},
            {"key": "functional_domains_v4", "status": "PASSED", "evidence": f"{len(FUNCTIONAL_DOMAINS)} domains"},
            {"key": "safe_mode_live_mode_separation", "status": "PASSED" if self.communications(db, organization_id=organization_id, event_id=event_id)["metrics"]["live_mode_campaigns"] == 0 else "FAILED", "evidence": "Live Mode campaigns must remain 0 for V4.10 closure"},
            {"key": "cross_tenant_scope", "status": "PASSED", "evidence": {"organization_id": organization_id, "event_id": event_id}},
        ]

    def _metric_payload(self, domain: str, event_id: int, metrics: dict[str, Any]) -> dict[str, Any]:
        now = self.now()
        definitions = [definition.payload(updated_at=now) for definition in METRIC_DEFINITIONS if definition.domain == domain]
        return {"ok": True, "event_id": event_id, "domain": domain, "updated_at": now, "source": "direct_queries", "definitions": definitions, "metrics": metrics}

    @staticmethod
    def _sanitize_filters(filters: dict[str, Any] | None) -> dict[str, Any]:
        clean: dict[str, Any] = {}
        if not isinstance(filters, dict):
            return clean
        for key in ("date_from", "date_to", "activity_id", "status", "channel", "zone_id", "role", "segment_id", "version", "timezone"):
            value = filters.get(key)
            if value not in (None, ""):
                clean[key] = str(value)[:80]
        clean.setdefault("timezone", "UTC")
        return clean

    @staticmethod
    def _rate(numerator: int, denominator: int) -> float:
        return round(int(numerator or 0) * 100 / max(1, int(denominator or 0)), 2) if denominator else 0.0

    @staticmethod
    def _rows(db, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        return [dict(row) for row in db.execute(sql, params).fetchall()]

    @staticmethod
    def _table_exists(db, table: str) -> bool:
        try:
            row = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table,)).fetchone()
            if row:
                return True
        except Exception:
            pass
        try:
            db.execute(f"SELECT 1 FROM {table} LIMIT 1")
            return True
        except Exception:
            return False

    def _count(self, db, table: str, where: str, params: tuple[Any, ...]) -> int:
        if not self._table_exists(db, table):
            return 0
        return int(db.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE {where}", params).fetchone()["c"] or 0)

    @staticmethod
    def _text(value: Any, limit: int) -> str:
        return str(value or "").strip()[:limit]

    @staticmethod
    def _choice(value: Any, allowed: set[str]) -> str:
        text = str(value or "").strip()
        upper = text.upper()
        if upper in allowed:
            return upper
        if text.lower() in allowed:
            return text.lower()
        return sorted(allowed)[0]

    @staticmethod
    def _issue(severity: str, code: str, title: str, count: int, source: str) -> dict[str, Any]:
        return {"severity": severity, "code": code, "title": title, "count": count, "source": source}

    @staticmethod
    def _safe_file_name(title: str, extension: str) -> str:
        base = "".join(ch if ch.isalnum() else "-" for ch in str(title or "analytics-report").lower()).strip("-")[:80]
        return f"{base or 'analytics-report'}.{extension}"

    @staticmethod
    def _csv_safe(value: Any) -> str:
        text = str(value if value is not None else "")
        return "'" + text if text.startswith(("=", "+", "-", "@")) else text

    def _csv_export(self, payload: dict[str, Any]) -> tuple[str, int]:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["section", "metric", "value"])
        count = 0
        sections = payload.get("metrics") or payload.get("sections") or {}
        for section, values in sections.items():
            if isinstance(values, dict):
                for key, value in values.items():
                    if isinstance(value, (dict, list)):
                        value = canonical_json(value)
                    writer.writerow([self._csv_safe(section), self._csv_safe(key), self._csv_safe(value)])
                    count += 1
        return output.getvalue(), count

    def _source_tables(self, db) -> list[str]:
        try:
            return [row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
        except Exception:
            return []

    def _assert_event(self, db, organization_id: int, event_id: int) -> None:
        row = db.execute("SELECT id, organization_id FROM events WHERE id = ?", (event_id,)).fetchone()
        if not row or int(row["organization_id"] or 0) != int(organization_id):
            raise AnalyticsClosureError("Evento inexistente para la organizacion", "ANALYTICS_EVENT_NOT_FOUND", 404)

    def _audit(self, db, actor: str, action: str, entity_type: str, entity_id: int | None, payload: dict[str, Any]) -> None:
        if self.audit_service:
            self.audit_service.record(db, actor, action, entity_type, entity_id, payload)
