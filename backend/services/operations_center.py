from __future__ import annotations

import re


class OperationsCenterError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class OperationsCenterService:
    """Read model and narrowly scoped operational actions for one event."""

    def __init__(self, audit_service, now=None) -> None:
        self.audit_service = audit_service
        self.now = now or (lambda: "")

    def center(self, db, *, organization_id: int, event_id: int, actor: str) -> dict:
        event = self._event(db, organization_id, event_id)
        checks = self._readiness(db, organization_id, event_id)
        self._sync_alerts(db, organization_id, event_id, checks, actor)
        return {
            "ok": True,
            "event": {"id": int(event["id"]), "organization_id": int(event["organization_id"]), "name": event["name"], "status": event["status"]},
            "operational_status": self._operational_status(checks),
            "readiness": {"items": checks, "ready": not any(item["status"] == "BLOCKED" for item in checks), "score": self._score(checks)},
            "metrics": self.metrics(db, organization_id=organization_id, event_id=event_id),
            "alerts": self.alerts(db, organization_id=organization_id, event_id=event_id),
            "incidents": self.incidents(db, organization_id=organization_id, event_id=event_id),
            "tasks": self.tasks(db, organization_id=organization_id, event_id=event_id),
            "updated_at": self.now(),
        }

    def metrics(self, db, *, organization_id: int, event_id: int) -> dict:
        self._event(db, organization_id, event_id)
        def count(sql: str, params=(event_id,)) -> int:
            return int(db.execute(sql, params).fetchone()["c"] or 0)
        registered = count("SELECT COUNT(*) AS c FROM accreditations WHERE event_id = ? AND status <> 'cancelled'")
        checked = count("SELECT COUNT(*) AS c FROM accreditations WHERE event_id = ? AND status <> 'cancelled' AND checked_in_at IS NOT NULL")
        return {
            "registered": {"value": registered, "source": "accreditations", "scope": "event"},
            "confirmed": {"value": count("SELECT COUNT(*) AS c FROM accreditations WHERE event_id = ? AND status IN ('active','confirmed')"), "source": "accreditations", "scope": "event"},
            "accredited": {"value": checked, "source": "accreditations.checked_in_at", "scope": "event"},
            "absent": {"value": max(registered - checked, 0), "source": "accreditations", "scope": "event"},
            "activities": {"value": count("SELECT COUNT(*) AS c FROM activities WHERE event_id = ? AND status <> 'cancelled'"), "source": "activities", "scope": "event"},
            "reservations": {"value": count("SELECT COUNT(*) AS c FROM reservations WHERE event_id = ? AND status <> 'cancelled'"), "source": "reservations", "scope": "event"},
            "waitlist": {"value": count("SELECT COUNT(*) AS c FROM reservations WHERE event_id = ? AND status = 'waitlisted'"), "source": "reservations", "scope": "event"},
            "access_allowed": {"value": count("SELECT COUNT(*) AS c FROM access_logs WHERE event_id = ? AND result IN ('allowed','ok','valid')"), "source": "access_logs", "scope": "event"},
            "access_denied": {"value": count("SELECT COUNT(*) AS c FROM access_logs WHERE event_id = ? AND result IN ('rejected','denied','invalid')"), "source": "access_logs", "scope": "event"},
            "speakers_confirmed": {"value": count("SELECT COUNT(*) AS c FROM speaker_event_assignments WHERE event_id = ? AND status = 'CONFIRMED'"), "source": "speaker_event_assignments", "scope": "event"},
            "certificates_issued": {"value": count("SELECT COUNT(*) AS c FROM certificate_issuances WHERE event_id = ? AND status NOT IN ('REVOKED','revoked')"), "source": "certificate_issuances", "scope": "event"},
            "surveys_active": {"value": count("SELECT COUNT(*) AS c FROM surveys WHERE event_id = ? AND status IN ('OPEN','open','PUBLISHED','published')"), "source": "surveys", "scope": "event"},
            "alerts_open": {"value": count("SELECT COUNT(*) AS c FROM operations_center_alerts WHERE event_id = ? AND status = 'OPEN'"), "source": "operations_center_alerts", "scope": "event"},
            "incidents_open": {"value": count("SELECT COUNT(*) AS c FROM operations_center_incidents WHERE event_id = ? AND status NOT IN ('RESOLVED','CLOSED')"), "source": "operations_center_incidents", "scope": "event"},
            "tasks_overdue": {"value": count("SELECT COUNT(*) AS c FROM operations_center_tasks WHERE event_id = ? AND status NOT IN ('COMPLETED','CANCELLED') AND due_at <> '' AND due_at < ?", (event_id, self.now())), "source": "operations_center_tasks", "scope": "event"},
        }

    def readiness(self, db, *, organization_id: int, event_id: int, actor: str) -> dict:
        self._event(db, organization_id, event_id)
        checks = self._readiness(db, organization_id, event_id)
        self._sync_alerts(db, organization_id, event_id, checks, actor)
        return {"ok": True, "items": checks, "ready": not any(item["status"] == "BLOCKED" for item in checks), "score": self._score(checks), "updated_at": self.now()}

    def alerts(self, db, *, organization_id: int, event_id: int) -> list[dict]:
        self._event(db, organization_id, event_id)
        rows = db.execute("SELECT * FROM operations_center_alerts WHERE organization_id = ? AND event_id = ? ORDER BY CASE severity WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END, id DESC", (organization_id, event_id)).fetchall()
        return [dict(row) for row in rows]

    def incidents(self, db, *, organization_id: int, event_id: int) -> list[dict]:
        self._event(db, organization_id, event_id)
        return [dict(row) for row in db.execute("SELECT * FROM operations_center_incidents WHERE organization_id = ? AND event_id = ? ORDER BY id DESC", (organization_id, event_id)).fetchall()]

    def tasks(self, db, *, organization_id: int, event_id: int) -> list[dict]:
        self._event(db, organization_id, event_id)
        return [dict(row) for row in db.execute("SELECT * FROM operations_center_tasks WHERE organization_id = ? AND event_id = ? ORDER BY CASE priority WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1 ELSE 2 END, id DESC", (organization_id, event_id)).fetchall()]

    def create_incident(self, db, *, organization_id: int, event_id: int, actor: str, data: dict) -> dict:
        self._event(db, organization_id, event_id)
        title = self._text(data.get("title"), 180)
        if not title:
            raise OperationsCenterError("INCIDENT_TITLE_REQUIRED", "Titulo obligatorio")
        now = self.now()
        cur = db.execute("INSERT INTO operations_center_incidents (organization_id,event_id,title,description,category,severity,status,reporter,assignee,related_entity,resolution,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (organization_id,event_id,title,self._text(data.get("description"),4000),self._choice(data.get("category") or "GENERAL", {"GENERAL","ACCESS","CAPACITY","COMMUNICATION","TECHNICAL","SECURITY"}),self._choice(data.get("severity") or "MEDIUM", {"LOW","MEDIUM","HIGH","CRITICAL"}),"OPEN",actor,self._text(data.get("assignee"),160),self._text(data.get("related_entity"),300),"",now,now))
        item_id = int(cur.lastrowid)
        self.audit_service.record(db, actor, "operations.incident.created", "operations_center_incident", item_id, {"organization_id": organization_id, "event_id": event_id})
        return {"ok": True, "item": dict(db.execute("SELECT * FROM operations_center_incidents WHERE id = ?", (item_id,)).fetchone())}

    def update_incident(self, db, *, organization_id: int, event_id: int, incident_id: int, actor: str, data: dict) -> dict:
        self._event(db, organization_id, event_id)
        row = db.execute("SELECT * FROM operations_center_incidents WHERE id = ? AND organization_id = ? AND event_id = ?", (incident_id, organization_id, event_id)).fetchone()
        if not row:
            raise OperationsCenterError("INCIDENT_NOT_FOUND", "Incidente inexistente", 404)
        allowed = {"status": {"OPEN","INVESTIGATING","MITIGATED","RESOLVED","CLOSED"}, "severity": {"LOW","MEDIUM","HIGH","CRITICAL"}}
        updates = {}
        for key, choices in allowed.items():
            if key in data:
                updates[key] = self._choice(data[key], choices)
        for key, limit in (("assignee",160),("resolution",4000)):
            if key in data:
                updates[key] = self._text(data[key], limit)
        if updates:
            updates["updated_at"] = self.now()
            db.execute(f"UPDATE operations_center_incidents SET {', '.join(f'{k} = ?' for k in updates)} WHERE id = ? AND organization_id = ? AND event_id = ?", [*updates.values(), incident_id, organization_id, event_id])
            self.audit_service.record(db, actor, "operations.incident.updated", "operations_center_incident", incident_id, {"organization_id": organization_id, "event_id": event_id, "fields": sorted(updates)})
        return {"ok": True, "item": dict(db.execute("SELECT * FROM operations_center_incidents WHERE id = ?", (incident_id,)).fetchone())}

    def create_task(self, db, *, organization_id: int, event_id: int, actor: str, data: dict) -> dict:
        self._event(db, organization_id, event_id)
        title = self._text(data.get("title"), 180)
        if not title:
            raise OperationsCenterError("TASK_TITLE_REQUIRED", "Titulo obligatorio")
        now = self.now()
        cur = db.execute("INSERT INTO operations_center_tasks (organization_id,event_id,title,description,priority,status,assignee,due_at,alert_id,incident_id,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (organization_id,event_id,title,self._text(data.get("description"),4000),self._choice(data.get("priority") or "MEDIUM", {"LOW","MEDIUM","HIGH","CRITICAL"}),"OPEN",self._text(data.get("assignee"),160),self._text(data.get("due_at"),40),int(data.get("alert_id") or 0) or None,int(data.get("incident_id") or 0) or None,actor,now,now))
        item_id = int(cur.lastrowid)
        self.audit_service.record(db, actor, "operations.task.created", "operations_center_task", item_id, {"organization_id": organization_id, "event_id": event_id})
        return {"ok": True, "item": dict(db.execute("SELECT * FROM operations_center_tasks WHERE id = ?", (item_id,)).fetchone())}

    def update_task(self, db, *, organization_id: int, event_id: int, task_id: int, actor: str, data: dict) -> dict:
        self._event(db, organization_id, event_id)
        row = db.execute("SELECT * FROM operations_center_tasks WHERE id = ? AND organization_id = ? AND event_id = ?", (task_id, organization_id, event_id)).fetchone()
        if not row:
            raise OperationsCenterError("TASK_NOT_FOUND", "Tarea inexistente", 404)
        updates = {}
        if "status" in data: updates["status"] = self._choice(data["status"], {"OPEN","IN_PROGRESS","COMPLETED","CANCELLED"})
        if "priority" in data: updates["priority"] = self._choice(data["priority"], {"LOW","MEDIUM","HIGH","CRITICAL"})
        for key, limit in (("assignee",160),("due_at",40)):
            if key in data: updates[key] = self._text(data[key], limit)
        if updates:
            updates["updated_at"] = self.now()
            db.execute(f"UPDATE operations_center_tasks SET {', '.join(f'{k} = ?' for k in updates)} WHERE id = ? AND organization_id = ? AND event_id = ?", [*updates.values(), task_id, organization_id, event_id])
            self.audit_service.record(db, actor, "operations.task.updated", "operations_center_task", task_id, {"organization_id": organization_id, "event_id": event_id, "fields": sorted(updates)})
        return {"ok": True, "item": dict(db.execute("SELECT * FROM operations_center_tasks WHERE id = ?", (task_id,)).fetchone())}

    def set_alert_status(self, db, *, organization_id: int, event_id: int, alert_id: int, actor: str, status: str) -> dict:
        self._event(db, organization_id, event_id)
        if status not in {"ACKNOWLEDGED", "RESOLVED", "DISMISSED"}:
            raise OperationsCenterError("ALERT_STATUS_INVALID", "Estado de alerta invalido")
        row = db.execute("SELECT * FROM operations_center_alerts WHERE id = ? AND organization_id = ? AND event_id = ?", (alert_id, organization_id, event_id)).fetchone()
        if not row:
            raise OperationsCenterError("ALERT_NOT_FOUND", "Alerta inexistente", 404)
        now = self.now()
        db.execute("UPDATE operations_center_alerts SET status = ?, acknowledged_at = CASE WHEN ? = 'ACKNOWLEDGED' THEN ? ELSE acknowledged_at END, resolved_at = CASE WHEN ? IN ('RESOLVED','DISMISSED') THEN ? ELSE resolved_at END, actor = ? WHERE id = ?", (status,status,now,status,now,actor,alert_id))
        self.audit_service.record(db, actor, f"operations.alert.{status.lower()}", "operations_center_alert", alert_id, {"organization_id": organization_id, "event_id": event_id})
        return {"ok": True, "item": dict(db.execute("SELECT * FROM operations_center_alerts WHERE id = ?", (alert_id,)).fetchone())}

    def _readiness(self, db, organization_id: int, event_id: int) -> list[dict]:
        event = self._event(db, organization_id, event_id)
        checks = []
        def add(code, category, status, message, source, recommendation=""):
            checks.append({"code": code, "category": category, "status": status, "severity": "CRITICAL" if status == "BLOCKED" else ("WARNING" if status == "WARNING" else "INFO"), "message": message, "source": source, "recommendation": recommendation, "updated_at": self.now()})
        add("event.exists", "configuration", "READY", "Evento identificado", "events")
        add("event.dates", "dates", "READY" if event["starts_at"] and event["ends_at"] else "WARNING", "Fechas configuradas" if event["starts_at"] and event["ends_at"] else "Faltan fechas", "events", "Completar inicio y fin")
        activity_count = int(db.execute("SELECT COUNT(*) AS c FROM activities WHERE event_id = ? AND status <> 'cancelled'", (event_id,)).fetchone()["c"] or 0)
        add("agenda.activities", "activities", "READY" if activity_count else "BLOCKED", f"{activity_count} actividad(es)", "activities", "Crear al menos una actividad")
        participant_count = int(db.execute("SELECT COUNT(*) AS c FROM accreditations WHERE event_id = ? AND status <> 'cancelled'", (event_id,)).fetchone()["c"] or 0)
        add("participants.registered", "registrations", "READY" if participant_count else "WARNING", f"{participant_count} participante(s)", "accreditations")
        add("backup.available", "backup", "READY" if bool(__import__('pathlib').Path("backups").exists()) else "WARNING", "Storage de backups disponible", "BDF", "Generar un backup antes de operar")
        return checks

    def _sync_alerts(self, db, organization_id, event_id, checks, actor):
        for item in checks:
            if item["status"] not in {"BLOCKED", "WARNING"}:
                continue
            key = f"readiness:{item['code']}"
            existing = db.execute("SELECT id FROM operations_center_alerts WHERE organization_id = ? AND event_id = ? AND dedupe_key = ? AND status IN ('OPEN','ACKNOWLEDGED')", (organization_id,event_id,key)).fetchone()
            if existing:
                continue
            cur = db.execute("INSERT INTO operations_center_alerts (organization_id,event_id,alert_type,severity,status,source,dedupe_key,message,entity_type,entity_id,correlation_id,created_at,actor) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (organization_id,event_id,"READINESS",item["severity"],"OPEN",item["source"],key,item["message"],"event",event_id,f"ops:{event_id}:{item['code']}",self.now(),actor))
            self.audit_service.record(db, actor, "operations.alert.generated", "operations_center_alert", int(cur.lastrowid), {"organization_id": organization_id, "event_id": event_id, "code": item["code"]})

    def _event(self, db, organization_id, event_id):
        row = db.execute("SELECT * FROM events WHERE id = ? AND organization_id = ?", (event_id, organization_id)).fetchone()
        if not row:
            raise OperationsCenterError("OPERATIONS_SCOPE_MISMATCH", "Evento fuera de alcance", 403)
        return row

    def _operational_status(self, checks):
        if any(item["status"] == "BLOCKED" for item in checks): return "DEGRADED"
        if any(item["status"] == "WARNING" for item in checks): return "PREPARATION"
        return "READY"

    def _score(self, checks):
        if not checks: return 0
        weights = {"READY": 1.0, "WARNING": 0.5, "PENDING": 0.25, "NOT_APPLICABLE": 1.0, "BLOCKED": 0.0}
        return round(sum(weights.get(item["status"], 0) for item in checks) / len(checks) * 100)

    def _text(self, value, limit):
        value = re.sub(r"[\x00-\x1f]", "", str(value or "")).strip()
        if len(value) > limit or re.search(r"<\s*script|javascript:|data:text/html", value, re.I):
            raise OperationsCenterError("OPERATIONS_TEXT_INVALID", "Texto invalido")
        return value

    def _choice(self, value, choices):
        value = str(value or "").upper()
        if value not in choices:
            raise OperationsCenterError("OPERATIONS_CHOICE_INVALID", "Valor invalido")
        return value
