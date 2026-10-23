from __future__ import annotations

import re
import unicodedata


class HistoryAutocompleteError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class HistoryAutocompleteService:
    def __init__(self, audit_service, now=None) -> None:
        self.audit_service = audit_service
        self.now = now or (lambda: "")

    def entity_history(self, db, *, organization_id: int, event_id: int, entity_type: str, entity_id: int, include_sensitive: bool = False, limit: int = 100) -> dict:
        self._validate_event(db, organization_id, event_id)
        entity_type = self._normalize_entity_type(entity_type)
        rows = db.execute(
            """
            SELECT * FROM audit_logs
            WHERE event_id = ?
              AND (entity_type = ? AND entity_id = ? OR payload LIKE ?)
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (event_id, entity_type, int(entity_id), f'%"{entity_type}_id": {int(entity_id)}%', min(max(int(limit or 100), 1), 200)),
        ).fetchall()
        return {"ok": True, "items": [self._history_payload(row, include_sensitive=include_sensitive) for row in rows]}

    def event_history(self, db, *, organization_id: int, event_id: int, include_sensitive: bool = False, limit: int = 100) -> dict:
        self._validate_event(db, organization_id, event_id)
        rows = db.execute("SELECT * FROM audit_logs WHERE event_id = ? ORDER BY created_at DESC, id DESC LIMIT ?", (event_id, min(max(int(limit or 100), 1), 200))).fetchall()
        return {"ok": True, "items": [self._history_payload(row, include_sensitive=include_sensitive) for row in rows]}

    def autocomplete_participants(self, db, *, organization_id: int, query: str, event_id: int | None = None, include_private: bool = False, limit: int = 10) -> dict:
        q = self.normalize_text(query)
        if len(q) < 2:
            return {"ok": True, "items": []}
        params: list[object] = [organization_id, f"%{q}%", f"%{q}%", f"{q}%"]
        sql = """
            SELECT DISTINCT p.id, p.first_name, p.last_name, p.email, p.dni, p.company, a.event_id
            FROM people p
            JOIN accreditations a ON a.person_id = p.id
            JOIN events e ON e.id = a.event_id
            WHERE e.organization_id = ?
              AND (LOWER(p.first_name || ' ' || p.last_name) LIKE ? OR LOWER(p.email) LIKE ? OR LOWER(COALESCE(p.dni, '')) LIKE ?)
        """
        if event_id:
            sql += " AND a.event_id = ?"
            params.append(int(event_id))
        sql += """
            ORDER BY p.last_name, p.first_name
            LIMIT ?
        """
        params.append(min(max(int(limit or 10), 1), 25))
        rows = db.execute(sql, params).fetchall()
        items = []
        for row in rows:
            item = {"person_id": int(row["id"]), "label": f"{row['first_name']} {row['last_name']}".strip(), "event_id": int(row["event_id"])}
            if include_private:
                item["email"] = row["email"]
                item["document"] = row["dni"]
                item["company"] = row["company"]
            else:
                item["email_hint"] = self._mask_email(row["email"])
            items.append(item)
        return {"ok": True, "items": items}

    def autocomplete_speakers(self, db, *, organization_id: int, query: str, include_private: bool = False, limit: int = 10) -> dict:
        q = self.normalize_text(query)
        if len(q) < 2:
            return {"ok": True, "items": []}
        rows = db.execute(
            """
            SELECT sp.*, spd.email
            FROM speaker_profiles sp
            LEFT JOIN speaker_private_details spd ON spd.speaker_profile_id = sp.id
            WHERE sp.organization_id = ?
              AND LOWER(sp.display_name || ' ' || sp.company || ' ' || sp.title) LIKE ?
            ORDER BY sp.display_name
            LIMIT ?
            """,
            (organization_id, f"%{q}%", min(max(int(limit or 10), 1), 25)),
        ).fetchall()
        items = []
        for row in rows:
            item = {"speaker_id": int(row["id"]), "label": row["display_name"], "company": row["company"], "status": row["status"]}
            if include_private:
                item["email"] = row["email"]
            items.append(item)
        return {"ok": True, "items": items}

    def autocomplete_values(self, db, *, organization_id: int, field: str, query: str, limit: int = 10) -> dict:
        field = field.lower().strip()
        allowed = {
            "organizations": ("people", "p.company", "accreditations a JOIN people p ON p.id = a.person_id JOIN events e ON e.id = a.event_id", "e.organization_id"),
            "cities": ("speaker_profiles", "city", "speaker_profiles", "organization_id"),
            "roles": ("speaker_activity_assignments", "role", "speaker_activity_assignments", "organization_id"),
        }
        if field not in allowed:
            raise HistoryAutocompleteError("AUTOCOMPLETE_FIELD_INVALID", "Campo invalido", 400)
        _table, column, source, org_column = allowed[field]
        q = self.normalize_text(query)
        rows = db.execute(
            f"""
            SELECT DISTINCT {column} AS value
            FROM {source}
            WHERE {org_column} = ? AND LOWER({column}) LIKE ? AND {column} IS NOT NULL AND {column} <> ''
            ORDER BY {column}
            LIMIT ?
            """,
            (organization_id, f"%{q}%", min(max(int(limit or 10), 1), 25)),
        ).fetchall()
        return {"ok": True, "items": [{"value": row["value"]} for row in rows]}

    def duplicate_candidates(self, db, *, organization_id: int, first_name: str = "", last_name: str = "", email: str = "", document: str = "") -> dict:
        normalized_email = self.normalize_email(email)
        normalized_doc = self.normalize_document(document)
        candidates = []
        if normalized_email:
            rows = db.execute(
                """
                SELECT DISTINCT p.*
                FROM people p
                JOIN accreditations a ON a.person_id = p.id
                JOIN events e ON e.id = a.event_id
                WHERE e.organization_id = ? AND LOWER(p.email) = ?
                LIMIT 10
                """,
                (organization_id, normalized_email),
            ).fetchall()
            candidates.extend((row, "PROBABLE_MATCH", 0.95) for row in rows)
        if normalized_doc:
            rows = db.execute(
                """
                SELECT DISTINCT p.*
                FROM people p
                JOIN accreditations a ON a.person_id = p.id
                JOIN events e ON e.id = a.event_id
                WHERE e.organization_id = ? AND LOWER(COALESCE(p.dni, '')) = ?
                LIMIT 10
                """,
                (organization_id, normalized_doc),
            ).fetchall()
            candidates.extend((row, "PROBABLE_MATCH", 0.9) for row in rows)
        name_key = self.normalize_text(f"{first_name} {last_name}")
        if name_key:
            rows = db.execute(
                """
                SELECT DISTINCT p.*
                FROM people p
                JOIN accreditations a ON a.person_id = p.id
                JOIN events e ON e.id = a.event_id
                WHERE e.organization_id = ? AND LOWER(p.first_name || ' ' || p.last_name) LIKE ?
                LIMIT 10
                """,
                (organization_id, f"%{name_key}%"),
            ).fetchall()
            candidates.extend((row, "POSSIBLE_MATCH", 0.55) for row in rows)
        seen = set()
        items = []
        for row, status, confidence in candidates:
            if int(row["id"]) in seen:
                continue
            seen.add(int(row["id"]))
            items.append({"person_id": int(row["id"]), "label": f"{row['first_name']} {row['last_name']}".strip(), "status": status, "confidence": confidence, "email_hint": self._mask_email(row["email"])})
        return {"ok": True, "items": items}

    def record_duplicate_decision(self, db, *, organization_id: int, actor: str, candidate_person_id: int, decision: str, reason: str = "", event_id: int | None = None) -> dict:
        decision = decision.upper().strip()
        if decision not in {"CONFIRMED_MATCH", "DISMISSED"}:
            raise HistoryAutocompleteError("DUPLICATE_DECISION_INVALID", "Decision invalida", 400)
        row = db.execute(
            """
            SELECT p.id, MIN(a.event_id) AS event_id
            FROM people p
            JOIN accreditations a ON a.person_id = p.id
            JOIN events e ON e.id = a.event_id
            WHERE p.id = ? AND e.organization_id = ?
              AND (? = 0 OR a.event_id = ?)
            GROUP BY p.id
            LIMIT 1
            """,
            (candidate_person_id, organization_id, int(event_id or 0), int(event_id or 0)),
        ).fetchone()
        if not row:
            raise HistoryAutocompleteError("DUPLICATE_SCOPE_MISMATCH", "Candidato fuera de alcance", 403)
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO duplicate_resolution_decisions (
                organization_id, event_id, candidate_person_id, decision, reason, actor, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (organization_id, int(row["event_id"] or event_id or 0), candidate_person_id, decision, self._clean_text(reason, 500), actor, now),
        )
        decision_id = int(getattr(cur, "lastrowid", 0) or 0)
        self.audit_service.record(db, actor, "duplicates.decision.recorded", "duplicate_resolution_decision", decision_id, {"organization_id": organization_id, "event_id": int(row["event_id"] or event_id or 0), "candidate_person_id": candidate_person_id, "decision": decision})
        return {"ok": True, "item": {"id": decision_id, "candidate_person_id": candidate_person_id, "decision": decision}}

    def normalize_email(self, value: str) -> str:
        return str(value or "").strip().lower()

    def normalize_document(self, value: str) -> str:
        return re.sub(r"[^a-zA-Z0-9]+", "", str(value or "")).lower()

    def normalize_text(self, value: str) -> str:
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        return re.sub(r"\s+", " ", text.strip().lower())

    def _validate_event(self, db, organization_id: int, event_id: int) -> None:
        row = db.execute("SELECT id FROM events WHERE id = ? AND organization_id = ?", (event_id, organization_id)).fetchone()
        if not row:
            raise HistoryAutocompleteError("HISTORY_SCOPE_MISMATCH", "Evento fuera de alcance", 403)

    def _normalize_entity_type(self, value: str) -> str:
        entity = re.sub(r"[^a-z_]+", "", str(value or "").lower())
        if entity not in {"event", "person", "accreditation", "activity", "attendance", "certificate", "survey", "speaker", "zone"}:
            raise HistoryAutocompleteError("HISTORY_ENTITY_INVALID", "Entidad invalida", 400)
        return entity

    def _history_payload(self, row, *, include_sensitive: bool) -> dict:
        item = {"id": int(row["id"]), "created_at": row["created_at"], "actor": row["actor"], "action": row["action"], "entity_type": row["entity_type"], "entity_id": row["entity_id"], "summary": self._safe_summary(row["action"], row["payload"])}
        if include_sensitive:
            item["payload"] = row["payload"]
        return item

    def _safe_summary(self, action: str, payload: str) -> str:
        return self._clean_text(f"{action} registrado", 180)

    def _clean_text(self, value, limit: int) -> str:
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or "")).strip()
        if len(text) > limit:
            text = text[:limit]
        return text

    def _mask_email(self, email: str) -> str:
        text = str(email or "")
        if "@" not in text:
            return ""
        left, right = text.split("@", 1)
        return f"{left[:2]}***@{right}"
