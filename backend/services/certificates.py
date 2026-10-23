from __future__ import annotations

import hashlib
import json
import re
import secrets
from collections.abc import Callable
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from backend.services.audit import AuditService


CERTIFICATE_RENDERER_VERSION = "bitora_certificate_renderer_v1"
CERTIFICATE_TYPE_STATUSES = {"ACTIVE", "DISABLED", "RETIRED"}
CERTIFICATE_TEMPLATE_STATUSES = {"DRAFT", "PUBLISHED", "RETIRED"}
CERTIFICATE_VERSION_STATUSES = {"DRAFT", "PUBLISHED", "RETIRED"}
CERTIFICATE_ISSUANCE_STATUSES = {"PENDING", "PROCESSING", "ISSUED", "FAILED", "REVOKED", "REISSUED"}
CERTIFICATE_BATCH_STATUSES = {"DRAFT", "PROCESSING", "COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED", "CANCELLED"}
CERTIFICATE_ALLOWED_KINDS = {"PARTICIPATION", "ATTENDANCE", "COMPLETION", "SPEAKER", "ORGANIZER", "SPECIAL_RECOGNITION"}
CERTIFICATE_ALLOWED_VARIABLES = {
    "participant_name",
    "event_name",
    "activity_name",
    "certificate_type",
    "issuance_date",
    "certificate_number",
    "organization_name",
    "location",
    "eligibility_result",
    "closure_reference",
    "template_version",
    "verification_code",
}
CERTIFICATE_ALLOWED_CONTENT_KEYS = {
    "title",
    "subtitle",
    "body",
    "footer",
    "location",
    "signatures",
}
CERTIFICATE_ELIGIBLE_RESULTS = {"ELIGIBLE", "MANUALLY_APPROVED"}


class CertificateDomainError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class CertificateService:
    def __init__(self, audit_service: AuditService, storage, now: Callable[[], str]) -> None:
        self.audit_service = audit_service
        self.storage = storage
        self.now = now

    def create_certificate_type(
        self,
        db,
        *,
        organization_id: int,
        event_id: int | None,
        actor: str,
        code: str,
        name: str,
        description: str = "",
        kind: str = "ATTENDANCE",
        requires_eligibility: bool = True,
        requires_closure: bool = True,
        allow_override: bool = True,
        allow_batch: bool = True,
        allow_reissue: bool = True,
        requires_numbering: bool = True,
    ) -> dict:
        event_id = self._validate_optional_event(db, organization_id, event_id)
        code = self._normalize_code(code, "CERTIFICATE_TYPE_INVALID")
        name = self._clean_text(name, 120)
        if not name:
            raise CertificateDomainError("CERTIFICATE_TYPE_INVALID", "Nombre de tipo obligatorio", 400)
        kind = self._normalize_choice(kind, CERTIFICATE_ALLOWED_KINDS, "CERTIFICATE_TYPE_INVALID")
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO certificate_types (
                organization_id, event_id, code, name, description, kind, status,
                requires_eligibility, requires_closure, allow_override, allow_batch,
                allow_reissue, requires_numbering, created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                organization_id,
                event_id,
                code,
                name,
                self._clean_text(description, 500),
                kind,
                1 if requires_eligibility else 0,
                1 if requires_closure else 0,
                1 if allow_override else 0,
                1 if allow_batch else 0,
                1 if allow_reissue else 0,
                1 if requires_numbering else 0,
                actor,
                now,
                now,
            ),
        )
        item = self._get_type(db, int(cur.lastrowid), organization_id)
        self.audit_service.record(db, actor, "certificates.type.created", "certificate_type", int(item["id"]), {"organization_id": organization_id, "event_id": event_id, "code": code, "kind": kind})
        return {"ok": True, "item": self._type_payload(item)}

    def create_template(
        self,
        db,
        *,
        organization_id: int,
        event_id: int | None,
        actor: str,
        certificate_type_id: int,
        name: str,
    ) -> dict:
        event_id = self._validate_optional_event(db, organization_id, event_id)
        cert_type = self._get_type(db, certificate_type_id, organization_id)
        self._ensure_same_optional_event(event_id, cert_type["event_id"])
        name = self._clean_text(name, 120)
        if not name:
            raise CertificateDomainError("CERTIFICATE_TEMPLATE_INVALID", "Nombre de plantilla obligatorio", 400)
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO certificate_templates (
                organization_id, event_id, certificate_type_id, name, status,
                current_version_id, created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'DRAFT', NULL, ?, ?, ?)
            """,
            (organization_id, event_id, int(cert_type["id"]), name, actor, now, now),
        )
        item = self._get_template(db, int(cur.lastrowid), organization_id)
        self.audit_service.record(db, actor, "certificates.template.created", "certificate_template", int(item["id"]), {"organization_id": organization_id, "event_id": event_id, "certificate_type_id": int(cert_type["id"])})
        return {"ok": True, "item": self._template_payload(item)}

    def create_template_version(
        self,
        db,
        *,
        organization_id: int,
        template_id: int,
        actor: str,
        content_schema: dict,
    ) -> dict:
        template = self._get_template(db, template_id, organization_id)
        if str(template["status"]) == "RETIRED":
            raise CertificateDomainError("CERTIFICATE_TEMPLATE_NOT_REISSUABLE", "Plantilla retirada", 409)
        content = self._normalize_template_schema(content_schema)
        content_hash = self._stable_hash(content)
        version_number = int(
            db.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 AS n FROM certificate_template_versions WHERE template_id = ?",
                (template_id,),
            ).fetchone()["n"]
        )
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO certificate_template_versions (
                template_id, organization_id, event_id, version_number, content_schema,
                content_hash, renderer_version, status, created_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?)
            """,
            (
                template_id,
                organization_id,
                template["event_id"],
                version_number,
                json.dumps(content, ensure_ascii=True, sort_keys=True),
                content_hash,
                CERTIFICATE_RENDERER_VERSION,
                actor,
                now,
            ),
        )
        item = self._get_template_version(db, int(cur.lastrowid), organization_id, template_id=template_id)
        self.audit_service.record(db, actor, "certificates.template.version_created", "certificate_template_version", int(item["id"]), {"organization_id": organization_id, "event_id": template["event_id"], "template_id": template_id, "content_hash": content_hash})
        return {"ok": True, "item": self._version_payload(item)}

    def publish_template_version(
        self,
        db,
        *,
        organization_id: int,
        template_id: int,
        version_id: int,
        actor: str,
        idempotency_key: str,
        correlation_id: str = "",
    ) -> dict:
        key = self._validate_idempotency_key(idempotency_key)
        request_hash = self._stable_hash({"organization_id": organization_id, "template_id": template_id, "version_id": version_id, "action": "publish"})
        existing = self._idempotency_lookup(db, organization_id, key, request_hash, "certificate_template_versions")
        if existing:
            return {"ok": True, "idempotent": True, "item": self._version_payload(self._get_template_version(db, int(existing["id"]), organization_id, template_id=template_id))}
        template = self._get_template(db, template_id, organization_id)
        version = self._get_template_version(db, version_id, organization_id, template_id=template_id)
        if str(version["status"]) != "DRAFT":
            raise CertificateDomainError("CERTIFICATE_TEMPLATE_VERSION_NOT_PUBLISHED", "La version no esta en borrador", 409)
        now = self.now()
        db.execute(
            """
            UPDATE certificate_template_versions
            SET status = 'PUBLISHED', published_at = ?, published_by = ?,
                idempotency_key = ?, request_hash = ?
            WHERE id = ?
            """,
            (now, actor, key, request_hash, version_id),
        )
        db.execute(
            """
            UPDATE certificate_templates
            SET status = 'PUBLISHED', current_version_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (version_id, now, template_id),
        )
        item = self._get_template_version(db, version_id, organization_id, template_id=template_id)
        self.audit_service.record(db, actor, "certificates.template.published", "certificate_template_version", version_id, {"organization_id": organization_id, "event_id": template["event_id"], "template_id": template_id, "content_hash": item["content_hash"], "correlation_id": correlation_id})
        return {"ok": True, "item": self._version_payload(item)}

    def preview_template_version(self, db, *, organization_id: int, template_id: int, version_id: int) -> dict:
        version = self._get_template_version(db, version_id, organization_id, template_id=template_id)
        content = self._json(version["content_schema"])
        payload = self._render_payload(
            participant_name="Participante de prueba",
            event_name="Evento de prueba",
            activity_name="",
            certificate_type="ATTENDANCE",
            issuance_date="2026-01-01T00:00:00+00:00",
            certificate_number="BITORA-PREVIEW-000001",
            organization_name="Organizacion de prueba",
            location=content.get("location", ""),
            eligibility_result="ELIGIBLE",
            closure_reference="preview",
            template_version=str(version["version_number"]),
            verification_code="preview",
        )
        logical_hash = self._stable_hash({"content": content, "payload": payload, "renderer": CERTIFICATE_RENDERER_VERSION})
        return {"ok": True, "item": {"template_version_id": int(version["id"]), "content_hash": version["content_hash"], "logical_hash": logical_hash, "payload": payload}}

    def issue_certificate(
        self,
        db,
        *,
        organization_id: int,
        event_id: int,
        actor: str,
        participant_id: int,
        certificate_type_id: int,
        template_version_id: int,
        eligibility_decision_id: int | None = None,
        batch_id: int | None = None,
        idempotency_key: str = "",
        correlation_id: str = "",
        supersedes_issuance_id: int | None = None,
    ) -> dict:
        key = self._validate_idempotency_key(idempotency_key)
        participant = self._get_participant(db, organization_id, event_id, participant_id)
        cert_type = self._get_type(db, certificate_type_id, organization_id)
        if cert_type["event_id"] is not None and int(cert_type["event_id"]) != event_id:
            raise CertificateDomainError("CERTIFICATE_SCOPE_MISMATCH", "Tipo fuera de alcance", 403)
        template_version = self._get_template_version(db, template_version_id, organization_id)
        if str(template_version["status"]) != "PUBLISHED":
            raise CertificateDomainError("CERTIFICATE_TEMPLATE_VERSION_NOT_PUBLISHED", "La version debe estar publicada", 409)
        template = self._get_template(db, int(template_version["template_id"]), organization_id)
        if int(template["certificate_type_id"]) != int(certificate_type_id):
            raise CertificateDomainError("CERTIFICATE_SCOPE_MISMATCH", "Plantilla y tipo no coinciden", 403)
        if template["event_id"] is not None and int(template["event_id"]) != event_id:
            raise CertificateDomainError("CERTIFICATE_SCOPE_MISMATCH", "Plantilla fuera de alcance", 403)
        if batch_id:
            self._get_batch(db, batch_id, organization_id, event_id)
        if supersedes_issuance_id:
            previous = self._get_issuance(db, supersedes_issuance_id, organization_id, event_id)
            if not int(cert_type["allow_reissue"] or 0):
                raise CertificateDomainError("CERTIFICATE_NOT_REISSUABLE", "El tipo no admite reemision", 409)
            if int(previous["participant_id"]) != participant_id or int(previous["certificate_type_id"]) != int(certificate_type_id):
                raise CertificateDomainError("CERTIFICATE_SCOPE_MISMATCH", "Reemision incompatible", 403)
        decision = None
        evaluation_id = None
        closure_id = None
        if int(cert_type["requires_eligibility"] or 0):
            if not eligibility_decision_id:
                raise CertificateDomainError("CERTIFICATE_ELIGIBILITY_REQUIRED", "La elegibilidad es obligatoria", 409)
            decision = self._get_eligibility_decision(db, organization_id, event_id, participant_id, eligibility_decision_id)
            if str(decision["effective_result"]) not in CERTIFICATE_ELIGIBLE_RESULTS:
                raise CertificateDomainError("CERTIFICATE_PARTICIPANT_NOT_ELIGIBLE", "Participante no elegible", 409)
            evaluation_id = int(decision["evaluation_id"])
            closure_id = int(decision["closure_id"])
            closure = db.execute(
                "SELECT * FROM attendance_closures WHERE id = ? AND organization_id = ? AND event_id = ?",
                (closure_id, organization_id, event_id),
            ).fetchone()
            if not closure or str(closure["status"]) != "CLOSED":
                raise CertificateDomainError("CERTIFICATE_ELIGIBILITY_REQUIRED", "El cierre no esta vigente", 409)
        request_hash = self._stable_hash(
            {
                "organization_id": organization_id,
                "event_id": event_id,
                "participant_id": participant_id,
                "certificate_type_id": certificate_type_id,
                "template_version_id": template_version_id,
                "eligibility_decision_id": eligibility_decision_id,
                "batch_id": batch_id,
                "supersedes_issuance_id": supersedes_issuance_id,
            }
        )
        existing = self._idempotency_lookup(db, organization_id, key, request_hash, "certificate_issuances")
        if existing:
            return {"ok": True, "idempotent": True, "item": self._issuance_detail(db, int(existing["id"]), organization_id, event_id)}
        duplicate = db.execute(
            """
            SELECT id FROM certificate_issuances
            WHERE organization_id = ? AND event_id = ? AND participant_id = ?
              AND certificate_type_id = ? AND status IN ('PROCESSING', 'ISSUED', 'REISSUED')
              AND COALESCE(supersedes_issuance_id, 0) = COALESCE(?, 0)
            """,
            (organization_id, event_id, participant_id, certificate_type_id, supersedes_issuance_id),
        ).fetchone()
        if duplicate and not supersedes_issuance_id:
            raise CertificateDomainError("CERTIFICATE_ISSUANCE_ALREADY_EXISTS", "Ya existe una emision para este participante y tipo", 409)
        issued_at = self.now()
        certificate_number = self._next_certificate_number(db, organization_id, event_id, str(cert_type["code"]))
        verification_token = secrets.token_urlsafe(32)
        token_hash = self._token_hash(verification_token)
        content = self._json(template_version["content_schema"])
        event = db.execute("SELECT e.*, o.name AS organization_name FROM events e JOIN organizations o ON o.id = e.organization_id WHERE e.id = ? AND e.organization_id = ?", (event_id, organization_id)).fetchone()
        payload = self._render_payload(
            participant_name=self._participant_name(participant),
            event_name=str(event["name"] or ""),
            activity_name="",
            certificate_type=str(cert_type["kind"] or cert_type["code"]),
            issuance_date=issued_at,
            certificate_number=certificate_number,
            organization_name=str(event["organization_name"] or ""),
            location=str(content.get("location") or ""),
            eligibility_result=str(decision["effective_result"] if decision else ""),
            closure_reference=str(closure_id or ""),
            template_version=str(template_version["version_number"]),
            verification_code=verification_token[:10],
        )
        logical_hash = self._stable_hash({"content": content, "payload": payload, "renderer": CERTIFICATE_RENDERER_VERSION})
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO certificate_issuances (
                organization_id, event_id, participant_id, certificate_type_id, template_version_id,
                eligibility_decision_id, attendance_closure_id, evaluation_id, batch_id,
                certificate_number, status, issued_at, issued_by, idempotency_key, request_hash,
                correlation_id, supersedes_issuance_id, logical_hash, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PROCESSING', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                organization_id,
                event_id,
                participant_id,
                certificate_type_id,
                template_version_id,
                eligibility_decision_id,
                closure_id,
                evaluation_id,
                batch_id,
                certificate_number,
                issued_at,
                actor,
                key,
                request_hash,
                correlation_id,
                supersedes_issuance_id,
                logical_hash,
                now,
                now,
            ),
        )
        issuance_id = int(cur.lastrowid)
        try:
            pdf = self._render_pdf(content, payload)
            document_hash = hashlib.sha256(pdf).hexdigest()
            storage_name = f"{certificate_number.lower()}-{issuance_id}.pdf"
            record = self.storage.save_event(event_id, "certificates", storage_name, pdf)
            db.execute(
                """
                INSERT INTO certificate_documents (
                    issuance_id, organization_id, event_id, storage_key, mime_type,
                    file_size, sha256_hash, logical_hash, renderer_version, generated_at, created_at
                )
                VALUES (?, ?, ?, ?, 'application/pdf', ?, ?, ?, ?, ?, ?)
                """,
                (issuance_id, organization_id, event_id, record["key"], int(record["size"]), document_hash, logical_hash, CERTIFICATE_RENDERER_VERSION, issued_at, now),
            )
            db.execute(
                """
                INSERT INTO certificate_verification_tokens (
                    issuance_id, organization_id, event_id, token_hash, token_hint,
                    status, created_at
                )
                VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?)
                """,
                (issuance_id, organization_id, event_id, token_hash, verification_token[:8], now),
            )
            db.execute("UPDATE certificate_issuances SET status = 'ISSUED', updated_at = ? WHERE id = ?", (self.now(), issuance_id))
            if supersedes_issuance_id:
                db.execute("UPDATE certificate_issuances SET status = 'REISSUED', updated_at = ? WHERE id = ?", (self.now(), supersedes_issuance_id))
                db.execute(
                    "INSERT INTO certificate_reissuances (previous_issuance_id, new_issuance_id, organization_id, event_id, reason, reissued_by, reissued_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (supersedes_issuance_id, issuance_id, organization_id, event_id, "Reemision controlada", actor, now, now),
                )
            self.audit_service.record(db, actor, "certificates.issued", "certificate_issuance", issuance_id, {"organization_id": organization_id, "event_id": event_id, "participant_id": participant_id, "certificate_number": certificate_number, "document_hash": document_hash, "correlation_id": correlation_id})
        except Exception as exc:
            db.execute("UPDATE certificate_issuances SET status = 'FAILED', updated_at = ?, failure_code = ?, failure_message = ? WHERE id = ?", (self.now(), "CERTIFICATE_RENDER_FAILED", self._clean_text(str(exc), 180), issuance_id))
            self.audit_service.record(db, actor, "certificates.issue_failed", "certificate_issuance", issuance_id, {"organization_id": organization_id, "event_id": event_id, "code": "CERTIFICATE_RENDER_FAILED"})
            raise CertificateDomainError("CERTIFICATE_RENDER_FAILED", "No se pudo generar el documento", 500) from exc
        return {"ok": True, "idempotent": False, "item": self._issuance_detail(db, issuance_id, organization_id, event_id), "verification_token": verification_token}

    def create_batch(
        self,
        db,
        *,
        organization_id: int,
        event_id: int,
        actor: str,
        certificate_type_id: int,
        template_version_id: int,
        participant_ids: list[int] | None = None,
        idempotency_key: str = "",
        correlation_id: str = "",
    ) -> dict:
        key = self._validate_idempotency_key(idempotency_key)
        cert_type = self._get_type(db, certificate_type_id, organization_id)
        if not int(cert_type["allow_batch"] or 0):
            raise CertificateDomainError("CERTIFICATE_BATCH_NOT_ALLOWED", "El tipo no admite emision masiva", 409)
        request_hash = self._stable_hash({"event_id": event_id, "certificate_type_id": certificate_type_id, "template_version_id": template_version_id, "participant_ids": sorted(participant_ids or [])})
        existing = self._idempotency_lookup(db, organization_id, key, request_hash, "certificate_batches")
        if existing:
            return {"ok": True, "idempotent": True, "item": self._batch_payload(self._get_batch(db, int(existing["id"]), organization_id, event_id))}
        candidates = self._batch_candidates(db, organization_id, event_id, participant_ids or [])
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO certificate_batches (
                organization_id, event_id, certificate_type_id, template_version_id,
                status, total_count, success_count, failure_count, idempotency_key,
                request_hash, correlation_id, created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'PROCESSING', ?, 0, 0, ?, ?, ?, ?, ?, ?)
            """,
            (organization_id, event_id, certificate_type_id, template_version_id, len(candidates), key, request_hash, correlation_id, actor, now, now),
        )
        batch_id = int(cur.lastrowid)
        successes = 0
        failures = 0
        for candidate in candidates:
            try:
                decision_id = int(candidate["decision_id"])
                self.issue_certificate(
                    db,
                    organization_id=organization_id,
                    event_id=event_id,
                    actor=actor,
                    participant_id=int(candidate["participant_id"]),
                    certificate_type_id=certificate_type_id,
                    template_version_id=template_version_id,
                    eligibility_decision_id=decision_id,
                    batch_id=batch_id,
                    idempotency_key=f"{key}:p:{candidate['participant_id']}",
                    correlation_id=correlation_id,
                )
                successes += 1
            except CertificateDomainError:
                failures += 1
        status = "COMPLETED" if failures == 0 else "COMPLETED_WITH_ERRORS" if successes else "FAILED"
        db.execute(
            "UPDATE certificate_batches SET status = ?, success_count = ?, failure_count = ?, updated_at = ? WHERE id = ?",
            (status, successes, failures, self.now(), batch_id),
        )
        item = self._get_batch(db, batch_id, organization_id, event_id)
        self.audit_service.record(db, actor, "certificates.batch.completed", "certificate_batch", batch_id, {"organization_id": organization_id, "event_id": event_id, "success": successes, "failures": failures})
        return {"ok": True, "item": self._batch_payload(item)}

    def revoke_certificate(self, db, *, organization_id: int, event_id: int, issuance_id: int, actor: str, reason: str) -> dict:
        reason = self._clean_text(reason, 500)
        if not reason:
            raise CertificateDomainError("CERTIFICATE_REVOCATION_REASON_REQUIRED", "Motivo obligatorio", 400)
        issuance = self._get_issuance(db, issuance_id, organization_id, event_id)
        if str(issuance["status"]) == "REVOKED":
            raise CertificateDomainError("CERTIFICATE_ALREADY_REVOKED", "Certificado ya revocado", 409)
        now = self.now()
        db.execute("UPDATE certificate_issuances SET status = 'REVOKED', updated_at = ? WHERE id = ?", (now, issuance_id))
        db.execute("UPDATE certificate_verification_tokens SET status = 'REVOKED' WHERE issuance_id = ?", (issuance_id,))
        db.execute(
            "INSERT INTO certificate_revocations (issuance_id, organization_id, event_id, reason, revoked_at, revoked_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (issuance_id, organization_id, event_id, reason, now, actor, now),
        )
        self.audit_service.record(db, actor, "certificates.revoked", "certificate_issuance", issuance_id, {"organization_id": organization_id, "event_id": event_id, "reason": reason})
        return {"ok": True, "item": self._issuance_detail(db, issuance_id, organization_id, event_id)}

    def reissue_certificate(self, db, *, organization_id: int, event_id: int, issuance_id: int, actor: str, reason: str, idempotency_key: str, correlation_id: str = "") -> dict:
        previous = self._get_issuance(db, issuance_id, organization_id, event_id)
        if str(previous["status"]) not in {"ISSUED", "REVOKED"}:
            raise CertificateDomainError("CERTIFICATE_NOT_REISSUABLE", "Estado no reemitible", 409)
        result = self.issue_certificate(
            db,
            organization_id=organization_id,
            event_id=event_id,
            actor=actor,
            participant_id=int(previous["participant_id"]),
            certificate_type_id=int(previous["certificate_type_id"]),
            template_version_id=int(previous["template_version_id"]),
            eligibility_decision_id=int(previous["eligibility_decision_id"] or 0) or None,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            supersedes_issuance_id=issuance_id,
        )
        self.audit_service.record(db, actor, "certificates.reissued", "certificate_issuance", int(result["item"]["id"]), {"organization_id": organization_id, "event_id": event_id, "previous_issuance_id": issuance_id, "reason": self._clean_text(reason, 300)})
        return result

    def verify_public(self, db, *, token: str) -> dict:
        token_hash = self._token_hash(str(token or ""))
        row = db.execute(
            """
            SELECT vt.*, ci.certificate_number, ci.status AS issuance_status, ci.issued_at,
                   ci.supersedes_issuance_id, p.first_name, p.last_name,
                   e.name AS event_name, o.name AS organization_name, ct.name AS certificate_type_name
            FROM certificate_verification_tokens vt
            JOIN certificate_issuances ci ON ci.id = vt.issuance_id
            JOIN people p ON p.id = ci.participant_id
            JOIN events e ON e.id = ci.event_id
            JOIN organizations o ON o.id = ci.organization_id
            JOIN certificate_types ct ON ct.id = ci.certificate_type_id
            WHERE vt.token_hash = ?
            """,
            (token_hash,),
        ).fetchone()
        if not row:
            return {"ok": True, "valid": False, "status": "invalid"}
        status = str(row["issuance_status"])
        valid = status == "ISSUED" and str(row["status"]) == "ACTIVE"
        return {
            "ok": True,
            "valid": valid,
            "status": "valid" if valid else status.lower(),
            "certificate_number": row["certificate_number"],
            "participant": self._visible_name(row["first_name"], row["last_name"]),
            "event": row["event_name"],
            "organization": row["organization_name"],
            "certificate_type": row["certificate_type_name"],
            "issued_at": row["issued_at"],
            "replaced": bool(row["supersedes_issuance_id"]),
        }

    def list_types(self, db, *, organization_id: int, event_id: int | None = None) -> dict:
        rows = db.execute(
            "SELECT * FROM certificate_types WHERE organization_id = ? AND (event_id IS NULL OR event_id = ?) ORDER BY id",
            (organization_id, event_id),
        ).fetchall()
        return {"items": [self._type_payload(row) for row in rows]}

    def list_templates(self, db, *, organization_id: int, event_id: int | None = None) -> dict:
        rows = db.execute(
            "SELECT * FROM certificate_templates WHERE organization_id = ? AND (event_id IS NULL OR event_id = ?) ORDER BY id",
            (organization_id, event_id),
        ).fetchall()
        return {"items": [self._template_payload(row) for row in rows]}

    def list_issuances(self, db, *, organization_id: int, event_id: int) -> dict:
        rows = db.execute("SELECT * FROM certificate_issuances WHERE organization_id = ? AND event_id = ? ORDER BY id DESC", (organization_id, event_id)).fetchall()
        return {"items": [self._issuance_payload(row) for row in rows]}

    def get_issuance_detail(self, db, *, organization_id: int, event_id: int, issuance_id: int) -> dict:
        return self._issuance_detail(db, issuance_id, organization_id, event_id)

    def document_bytes(self, db, *, organization_id: int, event_id: int, issuance_id: int) -> tuple[dict, bytes]:
        issuance = self._get_issuance(db, issuance_id, organization_id, event_id)
        document = db.execute("SELECT * FROM certificate_documents WHERE issuance_id = ? AND organization_id = ? AND event_id = ?", (issuance_id, organization_id, event_id)).fetchone()
        if not document:
            raise CertificateDomainError("CERTIFICATE_DOCUMENT_NOT_FOUND", "Documento inexistente", 404)
        key = str(document["storage_key"])
        prefix = f"events/{event_id}/certificates/"
        if not key.startswith(prefix):
            raise CertificateDomainError("CERTIFICATE_SCOPE_MISMATCH", "Documento fuera de alcance", 403)
        name = key[len(prefix):]
        content = self.storage.read_event(event_id, "certificates", name)
        if hashlib.sha256(content).hexdigest() != str(document["sha256_hash"]):
            raise CertificateDomainError("CERTIFICATE_DOCUMENT_HASH_MISMATCH", "Hash de documento invalido", 409)
        return self._issuance_detail(db, issuance_id, organization_id, event_id), content

    def _batch_candidates(self, db, organization_id: int, event_id: int, participant_ids: list[int]) -> list[dict]:
        params: list = [organization_id, event_id]
        where = ""
        if participant_ids:
            clean_ids = sorted({int(item) for item in participant_ids if int(item) > 0})
            placeholders = ", ".join(["?"] * len(clean_ids))
            where = f" AND d.participant_id IN ({placeholders})"
            params.extend(clean_ids)
        return [
            dict(row)
            for row in db.execute(
                f"""
                SELECT d.id AS decision_id, d.participant_id
                FROM attendance_eligibility_decisions d
                JOIN attendance_closures c ON c.id = d.closure_id
                WHERE d.organization_id = ? AND d.event_id = ? AND c.status = 'CLOSED'
                  AND d.effective_result IN ('ELIGIBLE', 'MANUALLY_APPROVED')
                  {where}
                ORDER BY d.participant_id, d.id DESC
                """,
                params,
            ).fetchall()
        ]

    def _get_type(self, db, certificate_type_id: int, organization_id: int):
        row = db.execute("SELECT * FROM certificate_types WHERE id = ? AND organization_id = ?", (certificate_type_id, organization_id)).fetchone()
        if not row:
            raise CertificateDomainError("CERTIFICATE_TYPE_NOT_FOUND", "Tipo inexistente", 404)
        return row

    def _get_template(self, db, template_id: int, organization_id: int):
        row = db.execute("SELECT * FROM certificate_templates WHERE id = ? AND organization_id = ?", (template_id, organization_id)).fetchone()
        if not row:
            raise CertificateDomainError("CERTIFICATE_TEMPLATE_NOT_FOUND", "Plantilla inexistente", 404)
        return row

    def _get_template_version(self, db, version_id: int, organization_id: int, template_id: int | None = None):
        if template_id:
            row = db.execute("SELECT * FROM certificate_template_versions WHERE id = ? AND template_id = ? AND organization_id = ?", (version_id, template_id, organization_id)).fetchone()
        else:
            row = db.execute("SELECT * FROM certificate_template_versions WHERE id = ? AND organization_id = ?", (version_id, organization_id)).fetchone()
        if not row:
            raise CertificateDomainError("CERTIFICATE_TEMPLATE_VERSION_NOT_PUBLISHED", "Version inexistente", 404)
        return row

    def _get_batch(self, db, batch_id: int, organization_id: int, event_id: int):
        row = db.execute("SELECT * FROM certificate_batches WHERE id = ? AND organization_id = ? AND event_id = ?", (batch_id, organization_id, event_id)).fetchone()
        if not row:
            raise CertificateDomainError("CERTIFICATE_NOT_FOUND", "Batch inexistente", 404)
        return row

    def _get_issuance(self, db, issuance_id: int, organization_id: int, event_id: int):
        row = db.execute("SELECT * FROM certificate_issuances WHERE id = ? AND organization_id = ? AND event_id = ?", (issuance_id, organization_id, event_id)).fetchone()
        if not row:
            raise CertificateDomainError("CERTIFICATE_NOT_FOUND", "Certificado inexistente", 404)
        return row

    def _get_eligibility_decision(self, db, organization_id: int, event_id: int, participant_id: int, decision_id: int):
        row = db.execute(
            """
            SELECT * FROM attendance_eligibility_decisions
            WHERE id = ? AND organization_id = ? AND event_id = ? AND participant_id = ?
            """,
            (decision_id, organization_id, event_id, participant_id),
        ).fetchone()
        if not row:
            raise CertificateDomainError("CERTIFICATE_ELIGIBILITY_REQUIRED", "Decision de elegibilidad inexistente", 404)
        return row

    def _get_participant(self, db, organization_id: int, event_id: int, participant_id: int):
        row = db.execute(
            """
            SELECT p.*, a.id AS accreditation_id
            FROM people p
            JOIN accreditations a ON a.person_id = p.id
            JOIN events e ON e.id = a.event_id
            WHERE p.id = ? AND a.event_id = ? AND e.organization_id = ?
            """,
            (participant_id, event_id, organization_id),
        ).fetchone()
        if not row:
            raise CertificateDomainError("CERTIFICATE_SCOPE_MISMATCH", "Participante fuera de alcance", 403)
        return row

    def _validate_optional_event(self, db, organization_id: int, event_id: int | None) -> int | None:
        if not event_id:
            return None
        event = db.execute("SELECT id FROM events WHERE id = ? AND organization_id = ?", (int(event_id), organization_id)).fetchone()
        if not event:
            raise CertificateDomainError("CERTIFICATE_SCOPE_MISMATCH", "Evento fuera de alcance", 403)
        return int(event_id)

    def _ensure_same_optional_event(self, expected: int | None, actual: int | None) -> None:
        if expected and actual and int(expected) != int(actual):
            raise CertificateDomainError("CERTIFICATE_SCOPE_MISMATCH", "Evento fuera de alcance", 403)

    def _next_certificate_number(self, db, organization_id: int, event_id: int, code: str) -> str:
        scope = f"ORG-{organization_id}-EVT-{event_id}-{code}"
        row = db.execute("SELECT * FROM certificate_number_sequences WHERE organization_id = ? AND scope_key = ?", (organization_id, scope)).fetchone()
        now = self.now()
        if not row:
            db.execute("INSERT INTO certificate_number_sequences (organization_id, event_id, scope_key, next_value, created_at, updated_at) VALUES (?, ?, ?, 2, ?, ?)", (organization_id, event_id, scope, now, now))
            value = 1
        else:
            value = int(row["next_value"])
            db.execute("UPDATE certificate_number_sequences SET next_value = ?, updated_at = ? WHERE id = ?", (value + 1, now, int(row["id"])))
        return f"BITORA-{organization_id:03d}-{event_id:04d}-{code}-{value:06d}"

    def _idempotency_lookup(self, db, organization_id: int, key: str, request_hash: str, table: str):
        row = db.execute(f"SELECT * FROM {table} WHERE organization_id = ? AND idempotency_key = ?", (organization_id, key)).fetchone()
        if not row:
            return None
        if str(row["request_hash"]) != request_hash:
            raise CertificateDomainError("CERTIFICATE_IDEMPOTENCY_CONFLICT", "La clave de idempotencia ya fue usada con otro payload", 409)
        return row

    def _normalize_template_schema(self, content: dict) -> dict:
        if not isinstance(content, dict):
            raise CertificateDomainError("CERTIFICATE_TEMPLATE_INVALID", "Plantilla invalida", 400)
        unknown_keys = set(content) - CERTIFICATE_ALLOWED_CONTENT_KEYS
        if unknown_keys:
            raise CertificateDomainError("CERTIFICATE_TEMPLATE_INVALID", "La plantilla contiene campos no permitidos", 400)
        normalized: dict = {}
        for key in CERTIFICATE_ALLOWED_CONTENT_KEYS:
            value = content.get(key)
            if key == "signatures":
                if value is None:
                    normalized[key] = []
                elif isinstance(value, list):
                    normalized[key] = [self._sanitize_template_text(str(item), 90) for item in value[:3]]
                else:
                    raise CertificateDomainError("CERTIFICATE_TEMPLATE_INVALID", "Firmas invalidas", 400)
            else:
                normalized[key] = self._sanitize_template_text(str(value or ""), 1200)
        variables = set(re.findall(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}", json.dumps(normalized, ensure_ascii=True)))
        if not variables.issubset(CERTIFICATE_ALLOWED_VARIABLES):
            raise CertificateDomainError("CERTIFICATE_TEMPLATE_INVALID", "La plantilla contiene variables no permitidas", 400)
        return {key: normalized[key] for key in sorted(normalized)}

    def _sanitize_template_text(self, value: str, limit: int) -> str:
        text = self._clean_text(value, limit)
        lowered = text.lower()
        forbidden = ["<script", "</script", "javascript:", "file://", "<iframe", "<object", "<embed", "onload=", "onerror=", "@import", "http://", "https://", "data:"]
        if any(item in lowered for item in forbidden):
            raise CertificateDomainError("CERTIFICATE_TEMPLATE_INVALID", "Contenido de plantilla no permitido", 400)
        if "<" in text or ">" in text:
            raise CertificateDomainError("CERTIFICATE_TEMPLATE_INVALID", "HTML no permitido en esta version", 400)
        return text

    def _render_payload(self, **kwargs) -> dict:
        return {key: str(kwargs.get(key) or "") for key in sorted(CERTIFICATE_ALLOWED_VARIABLES)}

    def _render_pdf(self, content: dict, payload: dict) -> bytes:
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=landscape(A4), bottomup=1, pageCompression=0, invariant=1)
        width, height = landscape(A4)
        pdf.setTitle(payload["certificate_number"])
        pdf.setAuthor("BITORA")
        pdf.setCreator(CERTIFICATE_RENDERER_VERSION)
        pdf.setFillColor(colors.HexColor("#172033"))
        pdf.rect(12 * mm, 12 * mm, width - 24 * mm, height - 24 * mm, stroke=1, fill=0)
        pdf.setFont("Helvetica-Bold", 26)
        pdf.drawCentredString(width / 2, height - 38 * mm, self._apply_template(content.get("title") or "Certificado {{certificate_type}}", payload))
        pdf.setFont("Helvetica", 14)
        pdf.drawCentredString(width / 2, height - 52 * mm, self._apply_template(content.get("subtitle") or "{{organization_name}}", payload))
        pdf.setFont("Helvetica", 18)
        pdf.drawCentredString(width / 2, height - 82 * mm, payload["participant_name"])
        pdf.setFont("Helvetica", 12)
        body = self._apply_template(content.get("body") or "Por su participacion en {{event_name}}.", payload)
        for index, line in enumerate(self._wrap(body, 96)[:8]):
            pdf.drawCentredString(width / 2, height - (102 + index * 7) * mm, line)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(24 * mm, 28 * mm, f"Numero: {payload['certificate_number']}")
        pdf.drawString(24 * mm, 22 * mm, f"Validacion: {payload['verification_code']}")
        pdf.drawRightString(width - 24 * mm, 28 * mm, f"Emitido: {payload['issuance_date'][:10]}")
        pdf.drawRightString(width - 24 * mm, 22 * mm, self._apply_template(content.get("footer") or "BITORA STAGING / QA CONTROLADO", payload))
        pdf.showPage()
        pdf.save()
        return buffer.getvalue()

    def _apply_template(self, value: str, payload: dict) -> str:
        def repl(match):
            key = match.group(1).strip()
            return payload.get(key, "")
        return re.sub(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}", repl, value)

    def _wrap(self, text: str, width: int) -> list[str]:
        words = text.split()
        lines: list[str] = []
        line: list[str] = []
        for word in words:
            candidate = " ".join([*line, word])
            if len(candidate) > width and line:
                lines.append(" ".join(line))
                line = [word]
            else:
                line.append(word)
        if line:
            lines.append(" ".join(line))
        return lines or [""]

    def _type_payload(self, row) -> dict:
        data = dict(row)
        for key in ("requires_eligibility", "requires_closure", "allow_override", "allow_batch", "allow_reissue", "requires_numbering"):
            data[key] = bool(data.get(key))
        return data

    def _template_payload(self, row) -> dict:
        return dict(row)

    def _version_payload(self, row) -> dict:
        data = dict(row)
        data["content_schema"] = self._json(data.get("content_schema") or "{}")
        return data

    def _issuance_payload(self, row) -> dict:
        return dict(row)

    def _batch_payload(self, row) -> dict:
        return dict(row)

    def _issuance_detail(self, db, issuance_id: int, organization_id: int, event_id: int) -> dict:
        issuance = self._get_issuance(db, issuance_id, organization_id, event_id)
        data = self._issuance_payload(issuance)
        document = db.execute("SELECT * FROM certificate_documents WHERE issuance_id = ?", (issuance_id,)).fetchone()
        data["document"] = dict(document) if document else None
        data["verification"] = {"token_hint": ""}
        token = db.execute("SELECT token_hint, status FROM certificate_verification_tokens WHERE issuance_id = ?", (issuance_id,)).fetchone()
        if token:
            data["verification"] = dict(token)
        return data

    def _participant_name(self, row) -> str:
        return self._visible_name(row["first_name"], row["last_name"])

    def _visible_name(self, first_name: str, last_name: str) -> str:
        name = f"{first_name or ''} {last_name or ''}".strip()
        return self._clean_text(name or "Participante", 120)

    def _normalize_code(self, value: str, error_code: str) -> str:
        code = re.sub(r"[^A-Z0-9_]", "_", str(value or "").strip().upper())
        code = re.sub(r"_+", "_", code).strip("_")
        if not code or len(code) > 40:
            raise CertificateDomainError(error_code, "Codigo invalido", 400)
        return code

    def _normalize_choice(self, value: str, allowed: set[str], error_code: str) -> str:
        normalized = str(value or "").strip().upper()
        if normalized not in allowed:
            raise CertificateDomainError(error_code, "Valor invalido", 400)
        return normalized

    def _validate_idempotency_key(self, key: str) -> str:
        text = str(key or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{8,160}", text):
            raise CertificateDomainError("CERTIFICATE_IDEMPOTENCY_CONFLICT", "Idempotency-Key invalida", 400)
        return text

    def _clean_text(self, value: str, limit: int) -> str:
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or "")).strip()
        return text[:limit]

    def _json(self, value: str) -> dict:
        try:
            parsed = json.loads(value or "{}")
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}

    def _stable_hash(self, payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def _token_hash(self, token: str) -> str:
        return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()
