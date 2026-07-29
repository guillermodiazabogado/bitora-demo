from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from pathlib import Path


SPEAKER_ROLES = {"SPEAKER", "MODERATOR", "PANELIST", "HOST", "TRAINER", "SPECIAL_GUEST"}
SPEAKER_STATUSES = {"DRAFT", "PENDING_REVIEW", "PUBLISHED", "ARCHIVED"}
SPEAKER_VISIBILITY = {"PRIVATE", "EVENT", "PUBLIC"}
SPEAKER_ASSIGNMENT_STATUSES = {"INVITED", "CONFIRMED", "DECLINED", "CANCELLED"}
SPEAKER_DOCUMENT_TYPES = {"PHOTO", "PRESENTATION", "TECHNICAL_SHEET", "AUTHORIZATION", "MATERIAL"}
SPEAKER_DOCUMENT_STATUS = {"PENDING", "APPROVED", "REJECTED"}
SPEAKER_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".ppt", ".pptx"}
SPEAKER_ALLOWED_MIME = {
    "image/jpeg",
    "image/png",
    "application/pdf",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


class SpeakerDomainError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class SpeakerService:
    def __init__(self, audit_service, storage=None, now=None, token_factory=None, secret: str = "bitora-speakers-local-secret") -> None:
        self.audit_service = audit_service
        self.storage = storage
        self.now = now or (lambda: "")
        self.token_factory = token_factory or (lambda: secrets.token_urlsafe(32))
        self.secret = secret or "bitora-speakers-local-secret"

    def create_profile(self, db, *, organization_id: int, actor: str, data: dict) -> dict:
        now = self.now()
        display_name = self._clean_text(data.get("display_name") or "", 180)
        first_name = self._clean_text(data.get("first_name") or "", 120)
        last_name = self._clean_text(data.get("last_name") or "", 120)
        if not display_name:
            display_name = " ".join(part for part in [first_name, last_name] if part).strip()
        if not display_name:
            raise SpeakerDomainError("SPEAKER_PROFILE_INVALID", "Nombre visible obligatorio", 400)
        public_id = self._public_id(db, organization_id, display_name)
        cur = db.execute(
            """
            INSERT INTO speaker_profiles (
                organization_id, public_id, display_name, first_name, last_name, professional_name,
                title, position, company, short_bio, long_bio, photo_storage_key, country, city,
                links_json, status, visibility, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?, ?)
            """,
            (
                organization_id,
                public_id,
                display_name,
                first_name,
                last_name,
                self._clean_text(data.get("professional_name") or "", 180),
                self._clean_text(data.get("title") or "", 180),
                self._clean_text(data.get("position") or "", 180),
                self._clean_text(data.get("company") or "", 180),
                self._clean_text(data.get("short_bio") or "", 500),
                self._clean_text(data.get("long_bio") or "", 4000),
                "",
                self._clean_text(data.get("country") or "", 120),
                self._clean_text(data.get("city") or "", 120),
                self._json_links(data.get("links") if isinstance(data.get("links"), list) else []),
                self._normalize_choice(data.get("visibility") or "EVENT", SPEAKER_VISIBILITY, "SPEAKER_VISIBILITY_INVALID"),
                actor,
                now,
                now,
            ),
        )
        profile_id = int(getattr(cur, "lastrowid", 0) or 0)
        self._upsert_private_details(db, organization_id=organization_id, profile_id=profile_id, actor=actor, data=data)
        self.audit_service.record(db, actor, "speakers.profile.created", "speaker_profile", profile_id, {"organization_id": organization_id})
        return {"ok": True, "item": self._profile_payload(self._get_profile(db, organization_id, profile_id), include_private=True, private=self._get_private_details(db, organization_id, profile_id))}

    def update_profile(self, db, *, organization_id: int, profile_id: int, actor: str, data: dict) -> dict:
        profile = self._get_profile(db, organization_id, profile_id)
        if str(profile["status"]) == "ARCHIVED":
            raise SpeakerDomainError("SPEAKER_ARCHIVED", "Perfil archivado", 409)
        allowed = {
            "display_name": 180,
            "first_name": 120,
            "last_name": 120,
            "professional_name": 180,
            "title": 180,
            "position": 180,
            "company": 180,
            "short_bio": 500,
            "long_bio": 4000,
            "country": 120,
            "city": 120,
        }
        updates = {key: self._clean_text(data[key], limit) for key, limit in allowed.items() if key in data}
        if "visibility" in data:
            updates["visibility"] = self._normalize_choice(data.get("visibility") or "", SPEAKER_VISIBILITY, "SPEAKER_VISIBILITY_INVALID")
        if "links" in data:
            updates["links_json"] = self._json_links(data.get("links") if isinstance(data.get("links"), list) else [])
        if updates:
            updates["status"] = "PENDING_REVIEW" if str(profile["status"]) == "PUBLISHED" else str(profile["status"])
            updates["updated_at"] = self.now()
            assignments = ", ".join(f"{key} = ?" for key in updates)
            db.execute(f"UPDATE speaker_profiles SET {assignments} WHERE id = ?", [updates[key] for key in updates] + [profile_id])
        self._upsert_private_details(db, organization_id=organization_id, profile_id=profile_id, actor=actor, data=data)
        self.audit_service.record(db, actor, "speakers.profile.updated", "speaker_profile", profile_id, {"organization_id": organization_id})
        return {"ok": True, "item": self._profile_payload(self._get_profile(db, organization_id, profile_id), include_private=True, private=self._get_private_details(db, organization_id, profile_id))}

    def publish_profile(self, db, *, organization_id: int, profile_id: int, actor: str, notes: str = "") -> dict:
        profile = self._get_profile(db, organization_id, profile_id)
        if str(profile["status"]) == "ARCHIVED":
            raise SpeakerDomainError("SPEAKER_ARCHIVED", "Perfil archivado", 409)
        version_number = int(db.execute("SELECT COALESCE(MAX(version_number), 0) + 1 AS n FROM speaker_profile_versions WHERE speaker_profile_id = ?", (profile_id,)).fetchone()["n"])
        snapshot = self._public_snapshot(profile)
        content_hash = self._stable_hash(snapshot)
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO speaker_profile_versions (
                speaker_profile_id, organization_id, version_number, snapshot_json, content_hash,
                status, published_at, published_by, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, 'PUBLISHED', ?, ?, ?, ?)
            """,
            (profile_id, organization_id, version_number, json.dumps(snapshot, ensure_ascii=True, sort_keys=True), content_hash, now, actor, self._clean_text(notes, 1000), now),
        )
        version_id = int(getattr(cur, "lastrowid", 0) or 0)
        db.execute("UPDATE speaker_profiles SET status = 'PUBLISHED', current_version_id = ?, updated_at = ? WHERE id = ?", (version_id, now, profile_id))
        self.audit_service.record(db, actor, "speakers.profile.published", "speaker_profile", profile_id, {"organization_id": organization_id, "version_id": version_id})
        return {"ok": True, "item": self._version_payload(self._get_version(db, organization_id, version_id))}

    def archive_profile(self, db, *, organization_id: int, profile_id: int, actor: str) -> dict:
        self._get_profile(db, organization_id, profile_id)
        now = self.now()
        db.execute("UPDATE speaker_profiles SET status = 'ARCHIVED', archived_at = ?, updated_at = ? WHERE id = ?", (now, now, profile_id))
        db.execute("UPDATE speaker_event_assignments SET status = 'CANCELLED', updated_at = ? WHERE speaker_profile_id = ?", (now, profile_id))
        db.execute("UPDATE speaker_activity_assignments SET status = 'CANCELLED', updated_at = ? WHERE speaker_profile_id = ?", (now, profile_id))
        self.audit_service.record(db, actor, "speakers.profile.archived", "speaker_profile", profile_id, {"organization_id": organization_id})
        return {"ok": True, "item": self._profile_payload(self._get_profile(db, organization_id, profile_id))}

    def assign_to_event(self, db, *, organization_id: int, event_id: int, profile_id: int, actor: str, roles: list[str], visibility: str = "PUBLIC", notes: str = "") -> dict:
        self._validate_event(db, organization_id, event_id)
        self._get_profile(db, organization_id, profile_id)
        roles_json = self._json_roles(roles)
        visibility = self._normalize_choice(visibility or "PUBLIC", SPEAKER_VISIBILITY, "SPEAKER_VISIBILITY_INVALID")
        now = self.now()
        existing = db.execute("SELECT * FROM speaker_event_assignments WHERE organization_id = ? AND event_id = ? AND speaker_profile_id = ?", (organization_id, event_id, profile_id)).fetchone()
        if existing:
            db.execute("UPDATE speaker_event_assignments SET roles_json = ?, visibility = ?, status = 'CONFIRMED', internal_notes = ?, updated_at = ? WHERE id = ?", (roles_json, visibility, self._clean_text(notes, 1000), now, existing["id"]))
            assignment_id = int(existing["id"])
        else:
            cur = db.execute(
                """
                INSERT INTO speaker_event_assignments (
                    organization_id, event_id, speaker_profile_id, roles_json, status, visibility,
                    internal_notes, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'CONFIRMED', ?, ?, ?, ?, ?)
                """,
                (organization_id, event_id, profile_id, roles_json, visibility, self._clean_text(notes, 1000), actor, now, now),
            )
            assignment_id = int(getattr(cur, "lastrowid", 0) or 0)
        self.audit_service.record(db, actor, "speakers.event.assigned", "speaker_event_assignment", assignment_id, {"organization_id": organization_id, "event_id": event_id, "speaker_profile_id": profile_id})
        return {"ok": True, "item": self._event_assignment_payload(self._get_event_assignment(db, organization_id, event_id, assignment_id))}

    def assign_to_activity(self, db, *, organization_id: int, event_id: int, profile_id: int, activity_id: int, actor: str, role: str, sort_order: int = 0, visibility: str = "PUBLIC", notes: str = "") -> dict:
        self._validate_event(db, organization_id, event_id)
        self._validate_activity(db, event_id, activity_id)
        self._get_profile(db, organization_id, profile_id)
        role = self._normalize_choice(role or "SPEAKER", SPEAKER_ROLES, "SPEAKER_ROLE_INVALID")
        visibility = self._normalize_choice(visibility or "PUBLIC", SPEAKER_VISIBILITY, "SPEAKER_VISIBILITY_INVALID")
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO speaker_activity_assignments (
                organization_id, event_id, activity_id, speaker_profile_id, role, status,
                visibility, sort_order, internal_notes, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'CONFIRMED', ?, ?, ?, ?, ?, ?)
            """,
            (organization_id, event_id, activity_id, profile_id, role, visibility, int(sort_order or 0), self._clean_text(notes, 1000), actor, now, now),
        )
        assignment_id = int(getattr(cur, "lastrowid", 0) or 0)
        self.audit_service.record(db, actor, "speakers.activity.assigned", "speaker_activity_assignment", assignment_id, {"organization_id": organization_id, "event_id": event_id, "activity_id": activity_id, "speaker_profile_id": profile_id})
        return {"ok": True, "item": self._activity_assignment_payload(self._get_activity_assignment(db, organization_id, event_id, assignment_id))}

    def create_access_token(self, db, *, organization_id: int, profile_id: int, actor: str, scope: str = "PROFILE_SELF_SERVICE", expires_at: str = "") -> dict:
        self._get_profile(db, organization_id, profile_id)
        token = self.token_factory()
        token_hash = self._token_hash(token)
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO speaker_access_tokens (
                organization_id, speaker_profile_id, scope, token_hash, token_hint, status,
                expires_at, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?)
            """,
            (organization_id, profile_id, self._clean_text(scope, 80) or "PROFILE_SELF_SERVICE", token_hash, token[:8], expires_at or "", actor, now),
        )
        token_id = int(getattr(cur, "lastrowid", 0) or 0)
        self.audit_service.record(db, actor, "speakers.access_token.created", "speaker_access_token", token_id, {"organization_id": organization_id, "speaker_profile_id": profile_id, "token_hint": token[:8]})
        return {"ok": True, "token": token, "item": {"id": token_id, "token_hint": token[:8], "status": "ACTIVE", "expires_at": expires_at or ""}}

    def self_service_profile(self, db, *, token: str) -> dict:
        token_row = self._active_token(db, token)
        profile = self._get_profile(db, int(token_row["organization_id"]), int(token_row["speaker_profile_id"]))
        return {"ok": True, "profile": self._profile_payload(profile, include_private=False)}

    def self_service_update(self, db, *, token: str, data: dict) -> dict:
        token_row = self._active_token(db, token)
        organization_id = int(token_row["organization_id"])
        profile_id = int(token_row["speaker_profile_id"])
        result = self.update_profile(db, organization_id=organization_id, profile_id=profile_id, actor="speaker-self-service", data={key: data[key] for key in data if key in {"display_name", "professional_name", "title", "position", "company", "short_bio", "long_bio", "country", "city", "links"}})
        self.audit_service.record(db, "speaker-self-service", "speakers.self_service.updated", "speaker_profile", profile_id, {"organization_id": organization_id})
        return result

    def revoke_access_token(self, db, *, organization_id: int, token_id: int, actor: str) -> dict:
        row = db.execute("SELECT * FROM speaker_access_tokens WHERE id = ? AND organization_id = ?", (token_id, organization_id)).fetchone()
        if not row:
            raise SpeakerDomainError("SPEAKER_TOKEN_NOT_FOUND", "Token inexistente", 404)
        db.execute("UPDATE speaker_access_tokens SET status = 'REVOKED', revoked_at = ? WHERE id = ?", (self.now(), token_id))
        self.audit_service.record(db, actor, "speakers.access_token.revoked", "speaker_access_token", token_id, {"organization_id": organization_id})
        return {"ok": True}

    def add_document(self, db, *, organization_id: int, event_id: int, profile_id: int, actor: str, filename: str, mime_type: str, content: bytes, document_type: str = "MATERIAL", visibility: str = "PRIVATE") -> dict:
        self._validate_event(db, organization_id, event_id)
        self._get_profile(db, organization_id, profile_id)
        document_type = self._normalize_choice(document_type or "MATERIAL", SPEAKER_DOCUMENT_TYPES, "SPEAKER_DOCUMENT_TYPE_INVALID")
        visibility = self._normalize_choice(visibility or "PRIVATE", SPEAKER_VISIBILITY, "SPEAKER_VISIBILITY_INVALID")
        safe_name = self._safe_filename(filename)
        extension = Path(safe_name).suffix.lower()
        if extension not in SPEAKER_ALLOWED_EXTENSIONS or mime_type not in SPEAKER_ALLOWED_MIME:
            raise SpeakerDomainError("SPEAKER_DOCUMENT_INVALID", "Tipo de documento no permitido", 400)
        if len(content or b"") <= 0 or len(content or b"") > 8 * 1024 * 1024:
            raise SpeakerDomainError("SPEAKER_DOCUMENT_INVALID", "Tamano de documento invalido", 400)
        stored_name = f"speakers/{profile_id}/{secrets.token_hex(8)}-{safe_name}"
        if not self.storage:
            raise SpeakerDomainError("SPEAKER_STORAGE_UNAVAILABLE", "Storage no disponible", 503)
        record = self.storage.save_event(event_id, "attachments", stored_name, content)
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO speaker_documents (
                organization_id, event_id, speaker_profile_id, document_type, filename, mime_type,
                storage_key, sha256, size_bytes, status, visibility, uploaded_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?, ?)
            """,
            (organization_id, event_id, profile_id, document_type, safe_name, mime_type, record["key"], record["sha256"], int(record["size"]), visibility, actor, now, now),
        )
        document_id = int(getattr(cur, "lastrowid", 0) or 0)
        if document_type == "PHOTO" and visibility in {"EVENT", "PUBLIC"}:
            db.execute("UPDATE speaker_profiles SET photo_storage_key = ?, updated_at = ? WHERE id = ?", (record["key"], now, profile_id))
        self.audit_service.record(db, actor, "speakers.document.uploaded", "speaker_document", document_id, {"organization_id": organization_id, "event_id": event_id, "speaker_profile_id": profile_id, "document_type": document_type})
        return {"ok": True, "item": self._document_payload(self._get_document(db, organization_id, event_id, document_id), include_storage=False)}

    def list_profiles(self, db, *, organization_id: int, event_id: int | None = None, include_private: bool = False) -> dict:
        if event_id:
            self._validate_event(db, organization_id, event_id)
            rows = db.execute(
                """
                SELECT sp.*
                FROM speaker_profiles sp
                JOIN speaker_event_assignments sea ON sea.speaker_profile_id = sp.id
                WHERE sea.organization_id = ? AND sea.event_id = ? AND sea.status <> 'CANCELLED'
                ORDER BY sp.display_name
                """,
                (organization_id, event_id),
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM speaker_profiles WHERE organization_id = ? ORDER BY display_name", (organization_id,)).fetchall()
        return {"ok": True, "items": [self._profile_payload(row, include_private=include_private, private=self._get_private_details(db, organization_id, int(row["id"])) if include_private else None) for row in rows]}

    def get_profile_detail(self, db, *, organization_id: int, profile_id: int, include_private: bool = False) -> dict:
        profile = self._get_profile(db, organization_id, profile_id)
        versions = db.execute("SELECT * FROM speaker_profile_versions WHERE organization_id = ? AND speaker_profile_id = ? ORDER BY version_number", (organization_id, profile_id)).fetchall()
        event_assignments = db.execute("SELECT * FROM speaker_event_assignments WHERE organization_id = ? AND speaker_profile_id = ? ORDER BY id", (organization_id, profile_id)).fetchall()
        activity_assignments = db.execute("SELECT * FROM speaker_activity_assignments WHERE organization_id = ? AND speaker_profile_id = ? ORDER BY id", (organization_id, profile_id)).fetchall()
        documents = db.execute("SELECT * FROM speaker_documents WHERE organization_id = ? AND speaker_profile_id = ? ORDER BY id", (organization_id, profile_id)).fetchall()
        return {
            "ok": True,
            "profile": self._profile_payload(profile, include_private=include_private, private=self._get_private_details(db, organization_id, profile_id) if include_private else None),
            "versions": [self._version_payload(row) for row in versions],
            "event_assignments": [self._event_assignment_payload(row) for row in event_assignments],
            "activity_assignments": [self._activity_assignment_payload(row) for row in activity_assignments],
            "documents": [self._document_payload(row, include_storage=include_private) for row in documents],
        }

    def public_event_speakers(self, db, *, event_id: int) -> dict:
        org_row = db.execute("SELECT organization_id FROM events WHERE id = ?", (event_id,)).fetchone()
        if not org_row:
            raise SpeakerDomainError("SPEAKER_EVENT_NOT_FOUND", "Evento inexistente", 404)
        rows = db.execute(
            """
            SELECT spv.snapshot_json
            FROM speaker_profiles sp
            JOIN speaker_event_assignments sea ON sea.speaker_profile_id = sp.id
            JOIN speaker_profile_versions spv ON spv.id = sp.current_version_id
            WHERE sea.event_id = ? AND sea.visibility = 'PUBLIC' AND sea.status = 'CONFIRMED'
              AND sp.status <> 'ARCHIVED' AND sp.current_version_id IS NOT NULL
            ORDER BY sp.display_name
            """,
            (event_id,),
        ).fetchall()
        return {"ok": True, "items": [self._json(row["snapshot_json"]) for row in rows]}

    def public_profile(self, db, *, public_id: str) -> dict:
        row = db.execute(
            """
            SELECT spv.snapshot_json
            FROM speaker_profiles sp
            JOIN speaker_profile_versions spv ON spv.id = sp.current_version_id
            WHERE sp.public_id = ? AND sp.status <> 'ARCHIVED' AND sp.visibility = 'PUBLIC'
              AND sp.current_version_id IS NOT NULL
            """,
            (public_id,),
        ).fetchone()
        if not row:
            raise SpeakerDomainError("SPEAKER_NOT_FOUND", "Perfil inexistente", 404)
        return {"ok": True, "profile": self._json(row["snapshot_json"])}

    def _upsert_private_details(self, db, *, organization_id: int, profile_id: int, actor: str, data: dict) -> None:
        private_keys = {"email", "phone", "document_id", "internal_notes", "technical_needs", "logistics_notes", "documentation_status"}
        if not any(key in data for key in private_keys):
            return
        now = self.now()
        values = {
            "email": self._clean_text(data.get("email") or "", 180),
            "phone": self._clean_text(data.get("phone") or "", 80),
            "document_id": self._clean_text(data.get("document_id") or "", 120),
            "internal_notes": self._clean_text(data.get("internal_notes") or "", 2000),
            "technical_needs": self._clean_text(data.get("technical_needs") or "", 2000),
            "logistics_notes": self._clean_text(data.get("logistics_notes") or "", 2000),
            "documentation_status": self._clean_text(data.get("documentation_status") or "PENDING", 80),
        }
        existing = self._get_private_details(db, organization_id, profile_id)
        if existing:
            db.execute(
                """
                UPDATE speaker_private_details
                SET email = ?, phone = ?, document_id = ?, internal_notes = ?, technical_needs = ?,
                    logistics_notes = ?, documentation_status = ?, updated_at = ?
                WHERE id = ?
                """,
                (*values.values(), now, existing["id"]),
            )
        else:
            db.execute(
                """
                INSERT INTO speaker_private_details (
                    organization_id, speaker_profile_id, email, phone, document_id, internal_notes,
                    technical_needs, logistics_notes, documentation_status, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (organization_id, profile_id, *values.values(), actor, now, now),
            )

    def _active_token(self, db, token: str):
        row = db.execute("SELECT * FROM speaker_access_tokens WHERE token_hash = ?", (self._token_hash(token),)).fetchone()
        if not row or str(row["status"]) != "ACTIVE":
            raise SpeakerDomainError("SPEAKER_TOKEN_INVALID", "Token invalido", 403)
        if row["expires_at"] and str(row["expires_at"]) < self.now():
            raise SpeakerDomainError("SPEAKER_TOKEN_EXPIRED", "Token vencido", 403)
        return row

    def _get_profile(self, db, organization_id: int, profile_id: int):
        row = db.execute("SELECT * FROM speaker_profiles WHERE id = ? AND organization_id = ?", (profile_id, organization_id)).fetchone()
        if not row:
            raise SpeakerDomainError("SPEAKER_NOT_FOUND", "Disertante inexistente", 404)
        return row

    def _get_private_details(self, db, organization_id: int, profile_id: int):
        return db.execute("SELECT * FROM speaker_private_details WHERE organization_id = ? AND speaker_profile_id = ?", (organization_id, profile_id)).fetchone()

    def _get_version(self, db, organization_id: int, version_id: int):
        row = db.execute("SELECT * FROM speaker_profile_versions WHERE id = ? AND organization_id = ?", (version_id, organization_id)).fetchone()
        if not row:
            raise SpeakerDomainError("SPEAKER_VERSION_NOT_FOUND", "Version inexistente", 404)
        return row

    def _get_event_assignment(self, db, organization_id: int, event_id: int, assignment_id: int):
        row = db.execute("SELECT * FROM speaker_event_assignments WHERE id = ? AND organization_id = ? AND event_id = ?", (assignment_id, organization_id, event_id)).fetchone()
        if not row:
            raise SpeakerDomainError("SPEAKER_ASSIGNMENT_NOT_FOUND", "Asignacion inexistente", 404)
        return row

    def _get_activity_assignment(self, db, organization_id: int, event_id: int, assignment_id: int):
        row = db.execute("SELECT * FROM speaker_activity_assignments WHERE id = ? AND organization_id = ? AND event_id = ?", (assignment_id, organization_id, event_id)).fetchone()
        if not row:
            raise SpeakerDomainError("SPEAKER_ASSIGNMENT_NOT_FOUND", "Asignacion inexistente", 404)
        return row

    def _get_document(self, db, organization_id: int, event_id: int, document_id: int):
        row = db.execute("SELECT * FROM speaker_documents WHERE id = ? AND organization_id = ? AND event_id = ?", (document_id, organization_id, event_id)).fetchone()
        if not row:
            raise SpeakerDomainError("SPEAKER_DOCUMENT_NOT_FOUND", "Documento inexistente", 404)
        return row

    def _validate_event(self, db, organization_id: int, event_id: int) -> None:
        row = db.execute("SELECT id FROM events WHERE id = ? AND organization_id = ?", (event_id, organization_id)).fetchone()
        if not row:
            raise SpeakerDomainError("SPEAKER_SCOPE_MISMATCH", "Evento fuera de alcance", 403)

    def _validate_activity(self, db, event_id: int, activity_id: int) -> None:
        row = db.execute("SELECT id FROM activities WHERE id = ? AND event_id = ?", (activity_id, event_id)).fetchone()
        if not row:
            raise SpeakerDomainError("SPEAKER_SCOPE_MISMATCH", "Actividad fuera de alcance", 403)

    def _profile_payload(self, row, *, include_private: bool = False, private=None) -> dict:
        payload = {
            "id": int(row["id"]),
            "organization_id": int(row["organization_id"]),
            "public_id": row["public_id"],
            "display_name": row["display_name"],
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "professional_name": row["professional_name"],
            "title": row["title"],
            "position": row["position"],
            "company": row["company"],
            "short_bio": row["short_bio"],
            "long_bio": row["long_bio"],
            "country": row["country"],
            "city": row["city"],
            "links": self._json(row["links_json"]),
            "status": row["status"],
            "visibility": row["visibility"],
            "current_version_id": row["current_version_id"],
        }
        if include_private and private:
            payload["private"] = {
                "email": private["email"],
                "phone": private["phone"],
                "document_id": private["document_id"],
                "internal_notes": private["internal_notes"],
                "technical_needs": private["technical_needs"],
                "logistics_notes": private["logistics_notes"],
                "documentation_status": private["documentation_status"],
            }
        return payload

    def _public_profile_payload(self, row) -> dict:
        return {
            "public_id": row["public_id"],
            "display_name": row["display_name"],
            "professional_name": row["professional_name"],
            "title": row["title"],
            "position": row["position"],
            "company": row["company"],
            "short_bio": row["short_bio"],
            "long_bio": row["long_bio"],
            "country": row["country"],
            "city": row["city"],
            "links": self._json(row["links_json"]),
        }

    def _version_payload(self, row) -> dict:
        return {"id": int(row["id"]), "speaker_profile_id": int(row["speaker_profile_id"]), "version_number": int(row["version_number"]), "content_hash": row["content_hash"], "status": row["status"], "published_at": row["published_at"], "snapshot": self._json(row["snapshot_json"])}

    def _event_assignment_payload(self, row) -> dict:
        return {"id": int(row["id"]), "organization_id": int(row["organization_id"]), "event_id": int(row["event_id"]), "speaker_profile_id": int(row["speaker_profile_id"]), "roles": self._json(row["roles_json"]), "status": row["status"], "visibility": row["visibility"], "internal_notes": row["internal_notes"]}

    def _activity_assignment_payload(self, row) -> dict:
        return {"id": int(row["id"]), "organization_id": int(row["organization_id"]), "event_id": int(row["event_id"]), "activity_id": int(row["activity_id"]), "speaker_profile_id": int(row["speaker_profile_id"]), "role": row["role"], "status": row["status"], "visibility": row["visibility"], "sort_order": int(row["sort_order"] or 0)}

    def _document_payload(self, row, *, include_storage: bool = False) -> dict:
        payload = {"id": int(row["id"]), "event_id": int(row["event_id"]), "speaker_profile_id": int(row["speaker_profile_id"]), "document_type": row["document_type"], "filename": row["filename"], "mime_type": row["mime_type"], "sha256": row["sha256"], "size_bytes": int(row["size_bytes"] or 0), "status": row["status"], "visibility": row["visibility"]}
        if include_storage:
            payload["storage_key"] = row["storage_key"]
        return payload

    def _public_snapshot(self, row) -> dict:
        return self._public_profile_payload(row)

    def _json(self, value):
        try:
            return json.loads(value or "[]")
        except (TypeError, ValueError):
            return []

    def _json_links(self, links: list) -> str:
        safe = []
        for item in links[:10]:
            label = self._clean_text((item or {}).get("label") or "", 80)
            url = self._clean_text((item or {}).get("url") or "", 400)
            if url and not re.match(r"^https://", url):
                raise SpeakerDomainError("SPEAKER_LINK_INVALID", "Solo se permiten enlaces https", 400)
            if label and url:
                safe.append({"label": label, "url": url})
        return json.dumps(safe, ensure_ascii=True, sort_keys=True)

    def _json_roles(self, roles: list[str]) -> str:
        normalized = sorted({self._normalize_choice(role, SPEAKER_ROLES, "SPEAKER_ROLE_INVALID") for role in (roles or ["SPEAKER"])})
        if not normalized:
            normalized = ["SPEAKER"]
        return json.dumps(normalized)

    def _clean_text(self, value, limit: int) -> str:
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or "")).strip()
        if len(text) > limit:
            raise SpeakerDomainError("SPEAKER_TEXT_TOO_LONG", "Texto demasiado extenso", 400)
        if re.search(r"<\s*script|javascript:|data:text/html", text, re.IGNORECASE):
            raise SpeakerDomainError("SPEAKER_TEXT_UNSAFE", "Contenido no permitido", 400)
        return text

    def _normalize_choice(self, value, allowed: set[str], code: str) -> str:
        normalized = str(value or "").strip().upper()
        if normalized not in allowed:
            raise SpeakerDomainError(code, "Valor invalido", 400)
        return normalized

    def _safe_filename(self, value: str) -> str:
        raw = str(value or "").strip()
        safe = Path(raw).name
        if not safe or safe != raw or "/" in raw or "\\" in raw or safe in {".", ".."}:
            raise SpeakerDomainError("SPEAKER_DOCUMENT_INVALID", "Nombre de archivo invalido", 400)
        return safe

    def _public_id(self, db, organization_id: int, display_name: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", display_name.lower()).strip("-")[:64] or "speaker"
        value = base
        index = 1
        while db.execute("SELECT id FROM speaker_profiles WHERE organization_id = ? AND public_id = ?", (organization_id, value)).fetchone():
            index += 1
            value = f"{base}-{index}"
        return value

    def _stable_hash(self, value) -> str:
        return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True, default=str).encode("utf-8")).hexdigest()

    def _token_hash(self, token: str) -> str:
        return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()

    def anonymous_link_hash(self, profile_id: int, value: str) -> str:
        return hmac.new(self.secret.encode("utf-8"), f"{profile_id}:{value}".encode("utf-8"), hashlib.sha256).hexdigest()
