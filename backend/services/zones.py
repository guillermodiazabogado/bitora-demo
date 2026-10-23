from __future__ import annotations

import re


ZONE_STATUSES = {"ACTIVE", "INACTIVE", "ARCHIVED"}
ZONE_ACCESS_MODES = {"MANUAL", "TOKEN", "QR"}
ZONE_ASSIGNMENT_STATUSES = {"ACTIVE", "REVOKED", "EXPIRED"}
ZONE_DECISIONS = {"ALLOWED", "DENIED", "EXPIRED", "REVOKED", "INVALID_CREDENTIAL", "WRONG_EVENT", "WRONG_ZONE", "OUTSIDE_TIME_WINDOW", "FEATURE_DISABLED"}
ZONE_OVERRIDE_TYPES = {"ALLOW_OVERRIDE", "DENY_OVERRIDE"}


class ZoneDomainError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ZonePermissionService:
    def __init__(self, audit_service, now=None) -> None:
        self.audit_service = audit_service
        self.now = now or (lambda: "")

    def create_zone(self, db, *, organization_id: int, event_id: int, actor: str, code: str, name: str, description: str = "", parent_zone_id: int | None = None, capacity: int | None = None, access_mode: str = "QR", valid_from: str = "", valid_until: str = "") -> dict:
        self._validate_event(db, organization_id, event_id)
        if parent_zone_id:
            self._get_zone(db, organization_id, event_id, int(parent_zone_id))
        code = self._normalize_code(code)
        name = self._clean_text(name, 160)
        if not name:
            raise ZoneDomainError("ZONE_INVALID", "Nombre de zona obligatorio", 400)
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO event_zones (
                organization_id, event_id, parent_zone_id, code, name, description, status,
                capacity, access_mode, valid_from, valid_until, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?, ?, ?)
            """,
            (organization_id, event_id, parent_zone_id, code, name, self._clean_text(description, 1000), capacity, self._choice(access_mode, ZONE_ACCESS_MODES, "ZONE_ACCESS_MODE_INVALID"), valid_from, valid_until, actor, now, now),
        )
        zone_id = int(getattr(cur, "lastrowid", 0) or 0)
        self.audit_service.record(db, actor, "zones.created", "event_zone", zone_id, {"organization_id": organization_id, "event_id": event_id, "code": code})
        return {"ok": True, "item": self._zone_payload(self._get_zone(db, organization_id, event_id, zone_id))}

    def list_zones(self, db, *, organization_id: int, event_id: int) -> dict:
        self._validate_event(db, organization_id, event_id)
        rows = db.execute("SELECT * FROM event_zones WHERE organization_id = ? AND event_id = ? ORDER BY parent_zone_id, code", (organization_id, event_id)).fetchall()
        return {"ok": True, "items": [self._zone_payload(row) for row in rows]}

    def assign_access(self, db, *, organization_id: int, event_id: int, zone_id: int, actor: str, person_id: int | None = None, accreditation_id: int | None = None, valid_from: str = "", valid_until: str = "", source: str = "manual") -> dict:
        self._get_zone(db, organization_id, event_id, zone_id)
        person_id, accreditation_id = self._resolve_subject(db, event_id, person_id, accreditation_id)
        now = self.now()
        existing = db.execute(
            "SELECT * FROM zone_access_assignments WHERE organization_id = ? AND event_id = ? AND zone_id = ? AND person_id = ? AND accreditation_id = ?",
            (organization_id, event_id, zone_id, person_id, accreditation_id),
        ).fetchone()
        if existing:
            db.execute("UPDATE zone_access_assignments SET status = 'ACTIVE', valid_from = ?, valid_until = ?, updated_at = ? WHERE id = ?", (valid_from, valid_until, now, existing["id"]))
            assignment_id = int(existing["id"])
        else:
            cur = db.execute(
                """
                INSERT INTO zone_access_assignments (
                    organization_id, event_id, zone_id, person_id, accreditation_id, status,
                    valid_from, valid_until, source, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?, ?)
                """,
                (organization_id, event_id, zone_id, person_id, accreditation_id, valid_from, valid_until, self._clean_text(source, 80), actor, now, now),
            )
            assignment_id = int(getattr(cur, "lastrowid", 0) or 0)
        self.audit_service.record(db, actor, "zones.access.assigned", "zone_access_assignment", assignment_id, {"organization_id": organization_id, "event_id": event_id, "zone_id": zone_id, "person_id": person_id})
        return {"ok": True, "item": self._assignment_payload(self._get_assignment(db, organization_id, event_id, assignment_id))}

    def create_override(self, db, *, organization_id: int, event_id: int, zone_id: int, actor: str, override_type: str, reason: str, person_id: int | None = None, accreditation_id: int | None = None, valid_until: str = "") -> dict:
        self._get_zone(db, organization_id, event_id, zone_id)
        person_id, accreditation_id = self._resolve_subject(db, event_id, person_id, accreditation_id)
        override_type = self._choice(override_type, ZONE_OVERRIDE_TYPES, "ZONE_OVERRIDE_INVALID")
        reason = self._clean_text(reason, 500)
        if not reason:
            raise ZoneDomainError("ZONE_OVERRIDE_REASON_REQUIRED", "Motivo obligatorio", 400)
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO zone_access_overrides (
                organization_id, event_id, zone_id, person_id, accreditation_id, override_type,
                reason, valid_until, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (organization_id, event_id, zone_id, person_id, accreditation_id, override_type, reason, valid_until, actor, now),
        )
        override_id = int(getattr(cur, "lastrowid", 0) or 0)
        self.audit_service.record(db, actor, "zones.override.created", "zone_access_override", override_id, {"organization_id": organization_id, "event_id": event_id, "zone_id": zone_id, "override_type": override_type})
        return {"ok": True, "item": self._override_payload(self._get_override(db, organization_id, event_id, override_id))}

    def validate_access(self, db, *, organization_id: int, event_id: int, zone_id: int, actor: str, token: str = "", person_id: int | None = None, accreditation_id: int | None = None, idempotency_key: str = "") -> dict:
        zone = self._get_zone(db, organization_id, event_id, zone_id)
        now = self.now()
        decision = "DENIED"
        reason = ""
        accreditation = None
        if token:
            accreditation = db.execute("SELECT * FROM accreditations WHERE token = ?", (str(token or ""),)).fetchone()
            if not accreditation:
                decision, reason = "INVALID_CREDENTIAL", "Credencial inexistente"
            elif int(accreditation["event_id"]) != int(event_id):
                decision, reason = "WRONG_EVENT", "Credencial de otro evento"
        elif accreditation_id:
            accreditation = db.execute("SELECT * FROM accreditations WHERE id = ?", (int(accreditation_id),)).fetchone()
            if not accreditation:
                decision, reason = "INVALID_CREDENTIAL", "Credencial inexistente"
            elif int(accreditation["event_id"]) != int(event_id):
                decision, reason = "WRONG_EVENT", "Credencial de otro evento"
        elif person_id:
            accreditation = db.execute("SELECT * FROM accreditations WHERE event_id = ? AND person_id = ? AND status = 'active' ORDER BY id LIMIT 1", (event_id, int(person_id))).fetchone()
            if not accreditation:
                decision, reason = "INVALID_CREDENTIAL", "Participante sin acreditacion activa"
        else:
            decision, reason = "INVALID_CREDENTIAL", "Falta credencial"

        if accreditation and not reason:
            person_id = int(accreditation["person_id"])
            accreditation_id = int(accreditation["id"])
            if str(accreditation["status"]) != "active":
                decision, reason = "INVALID_CREDENTIAL", "Credencial inactiva"
            elif str(zone["status"]) != "ACTIVE":
                decision, reason = "WRONG_ZONE", "Zona inactiva"
            elif zone["valid_from"] and str(zone["valid_from"]) > now:
                decision, reason = "OUTSIDE_TIME_WINDOW", "Zona aun no vigente"
            elif zone["valid_until"] and now > str(zone["valid_until"]):
                decision, reason = "EXPIRED", "Zona vencida"
            else:
                override = self._active_override(db, organization_id, event_id, zone_id, person_id, accreditation_id)
                if override and override["override_type"] == "DENY_OVERRIDE":
                    decision, reason = "DENIED", "Override de denegacion"
                elif override and override["override_type"] == "ALLOW_OVERRIDE":
                    decision, reason = "ALLOWED", "Override de autorizacion"
                else:
                    assignment = db.execute(
                        """
                        SELECT * FROM zone_access_assignments
                        WHERE organization_id = ? AND event_id = ? AND zone_id = ?
                          AND person_id = ? AND accreditation_id = ?
                        ORDER BY id DESC LIMIT 1
                        """,
                        (organization_id, event_id, zone_id, person_id, accreditation_id),
                    ).fetchone()
                    if not assignment:
                        decision, reason = "DENIED", "Sin permiso de zona"
                    elif str(assignment["status"]) == "REVOKED":
                        decision, reason = "REVOKED", "Permiso revocado"
                    elif assignment["valid_from"] and str(assignment["valid_from"]) > now:
                        decision, reason = "OUTSIDE_TIME_WINDOW", "Permiso aun no vigente"
                    elif assignment["valid_until"] and now > str(assignment["valid_until"]):
                        decision, reason = "EXPIRED", "Permiso vencido"
                    else:
                        decision, reason = "ALLOWED", "Acceso autorizado"
        if decision not in ZONE_DECISIONS:
            decision = "DENIED"
        key = idempotency_key or f"{zone_id}:{accreditation_id or 0}:{now}"
        existing = db.execute("SELECT * FROM zone_access_validations WHERE organization_id = ? AND idempotency_key = ?", (organization_id, key)).fetchone()
        if existing:
            return {"ok": True, "idempotent": True, "item": self._validation_payload(existing)}
        cur = db.execute(
            """
            INSERT INTO zone_access_validations (
                organization_id, event_id, zone_id, person_id, accreditation_id, decision,
                reason, actor, idempotency_key, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (organization_id, event_id, zone_id, person_id, accreditation_id, decision, reason, actor, key, now),
        )
        validation_id = int(getattr(cur, "lastrowid", 0) or 0)
        self.audit_service.record(db, actor, "zones.access.validated", "zone_access_validation", validation_id, {"organization_id": organization_id, "event_id": event_id, "zone_id": zone_id, "decision": decision})
        return {"ok": True, "item": self._validation_payload(self._get_validation(db, organization_id, event_id, validation_id))}

    def _resolve_subject(self, db, event_id: int, person_id: int | None, accreditation_id: int | None) -> tuple[int, int]:
        if accreditation_id:
            row = db.execute("SELECT * FROM accreditations WHERE id = ? AND event_id = ?", (int(accreditation_id), event_id)).fetchone()
            if not row:
                raise ZoneDomainError("ZONE_CREDENTIAL_INVALID", "Acreditacion fuera de alcance", 403)
            return int(row["person_id"]), int(row["id"])
        if person_id:
            row = db.execute("SELECT * FROM accreditations WHERE person_id = ? AND event_id = ? AND status = 'active' ORDER BY id LIMIT 1", (int(person_id), event_id)).fetchone()
            if not row:
                raise ZoneDomainError("ZONE_CREDENTIAL_INVALID", "Participante sin acreditacion del evento", 403)
            return int(row["person_id"]), int(row["id"])
        raise ZoneDomainError("ZONE_CREDENTIAL_INVALID", "Participante o acreditacion obligatoria", 400)

    def _active_override(self, db, organization_id: int, event_id: int, zone_id: int, person_id: int, accreditation_id: int):
        now = self.now()
        return db.execute(
            """
            SELECT * FROM zone_access_overrides
            WHERE organization_id = ? AND event_id = ? AND zone_id = ? AND person_id = ? AND accreditation_id = ?
              AND (valid_until IS NULL OR valid_until = '' OR valid_until >= ?)
            ORDER BY id DESC LIMIT 1
            """,
            (organization_id, event_id, zone_id, person_id, accreditation_id, now),
        ).fetchone()

    def _validate_event(self, db, organization_id: int, event_id: int) -> None:
        row = db.execute("SELECT id FROM events WHERE id = ? AND organization_id = ?", (event_id, organization_id)).fetchone()
        if not row:
            raise ZoneDomainError("ZONE_SCOPE_MISMATCH", "Evento fuera de alcance", 403)

    def _get_zone(self, db, organization_id: int, event_id: int, zone_id: int):
        row = db.execute("SELECT * FROM event_zones WHERE id = ? AND organization_id = ? AND event_id = ?", (zone_id, organization_id, event_id)).fetchone()
        if not row:
            raise ZoneDomainError("ZONE_NOT_FOUND", "Zona inexistente", 404)
        return row

    def _get_assignment(self, db, organization_id: int, event_id: int, assignment_id: int):
        row = db.execute("SELECT * FROM zone_access_assignments WHERE id = ? AND organization_id = ? AND event_id = ?", (assignment_id, organization_id, event_id)).fetchone()
        if not row:
            raise ZoneDomainError("ZONE_ASSIGNMENT_NOT_FOUND", "Asignacion inexistente", 404)
        return row

    def _get_override(self, db, organization_id: int, event_id: int, override_id: int):
        row = db.execute("SELECT * FROM zone_access_overrides WHERE id = ? AND organization_id = ? AND event_id = ?", (override_id, organization_id, event_id)).fetchone()
        if not row:
            raise ZoneDomainError("ZONE_OVERRIDE_NOT_FOUND", "Override inexistente", 404)
        return row

    def _get_validation(self, db, organization_id: int, event_id: int, validation_id: int):
        row = db.execute("SELECT * FROM zone_access_validations WHERE id = ? AND organization_id = ? AND event_id = ?", (validation_id, organization_id, event_id)).fetchone()
        if not row:
            raise ZoneDomainError("ZONE_VALIDATION_NOT_FOUND", "Validacion inexistente", 404)
        return row

    def _zone_payload(self, row) -> dict:
        return {"id": int(row["id"]), "organization_id": int(row["organization_id"]), "event_id": int(row["event_id"]), "parent_zone_id": row["parent_zone_id"], "code": row["code"], "name": row["name"], "description": row["description"], "status": row["status"], "capacity": row["capacity"], "access_mode": row["access_mode"], "valid_from": row["valid_from"], "valid_until": row["valid_until"]}

    def _assignment_payload(self, row) -> dict:
        return {"id": int(row["id"]), "zone_id": int(row["zone_id"]), "person_id": int(row["person_id"]), "accreditation_id": int(row["accreditation_id"]), "status": row["status"], "valid_from": row["valid_from"], "valid_until": row["valid_until"]}

    def _override_payload(self, row) -> dict:
        return {"id": int(row["id"]), "zone_id": int(row["zone_id"]), "person_id": int(row["person_id"]), "accreditation_id": int(row["accreditation_id"]), "override_type": row["override_type"], "reason": row["reason"], "valid_until": row["valid_until"]}

    def _validation_payload(self, row) -> dict:
        return {"id": int(row["id"]), "zone_id": int(row["zone_id"]), "person_id": row["person_id"], "accreditation_id": row["accreditation_id"], "decision": row["decision"], "reason": row["reason"], "created_at": row["created_at"]}

    def _normalize_code(self, value: str) -> str:
        code = re.sub(r"[^A-Z0-9_]+", "_", str(value or "").upper()).strip("_")
        if not code or len(code) > 80:
            raise ZoneDomainError("ZONE_CODE_INVALID", "Codigo invalido", 400)
        return code

    def _clean_text(self, value, limit: int) -> str:
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or "")).strip()
        if len(text) > limit:
            raise ZoneDomainError("ZONE_TEXT_TOO_LONG", "Texto demasiado extenso", 400)
        if re.search(r"<\s*script|javascript:|data:text/html", text, re.IGNORECASE):
            raise ZoneDomainError("ZONE_TEXT_UNSAFE", "Contenido no permitido", 400)
        return text

    def _choice(self, value, allowed: set[str], code: str) -> str:
        normalized = str(value or "").strip().upper()
        if normalized not in allowed:
            raise ZoneDomainError(code, "Valor invalido", 400)
        return normalized
