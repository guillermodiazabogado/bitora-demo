from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import secrets
from datetime import datetime, timedelta
from typing import Any


COMPANY_TYPES = {"EXHIBITOR", "SPONSOR", "PRESS", "SUPPLIER", "CONTRACTOR", "INSTITUTION", "PARTNER"}
PARTICIPATION_STATUSES = {"INVITED", "PENDING", "APPROVED", "ACTIVE", "SUSPENDED", "REJECTED", "CLOSED"}
COMPANY_USER_ROLES = {"COMPANY_ADMIN", "DELEGATION_MANAGER", "VIEWER"}
INVITATION_STATUSES = {"PENDING", "OPENED", "COMPLETED", "EXPIRED", "REVOKED"}
APPROVAL_STATUSES = {"SUBMITTED", "PENDING_REVIEW", "APPROVED", "REJECTED"}


class CompanyDelegationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class CompanyDelegationService:
    def __init__(self, enterprise_core=None, audit_service=None, now=None) -> None:
        self.enterprise_core = enterprise_core
        self.audit_service = audit_service
        self.now = now or (lambda: "")

    def create_company(self, db, *, organization_id: int, name: str, company_type: str = "EXHIBITOR", tax_id: str = "", actor: str = "", metadata: dict | None = None) -> dict:
        name = self._clean_text(name, 220)
        if not name:
            raise CompanyDelegationError("COMPANY_NAME_REQUIRED", "Nombre de empresa obligatorio")
        company_type = self._choice(company_type, COMPANY_TYPES, "COMPANY_TYPE_INVALID")
        now = self.now()
        row = db.execute("SELECT * FROM enterprise_companies WHERE organization_id = ? AND name = ?", (organization_id, name)).fetchone()
        if row:
            db.execute("UPDATE enterprise_companies SET company_type = ?, tax_id = ?, metadata_json = ?, updated_at = ? WHERE id = ?", (company_type, self._clean_text(tax_id, 80), self._json(metadata or {}), now, row["id"]))
            company_id = int(row["id"])
        else:
            cur = db.execute(
                "INSERT INTO enterprise_companies (organization_id, name, company_type, tax_id, status, metadata_json, created_at, updated_at) VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?, ?)",
                (organization_id, name, company_type, self._clean_text(tax_id, 80), self._json(metadata or {}), now, now),
            )
            company_id = int(getattr(cur, "lastrowid", 0) or 0)
            self._audit(db, actor, "company.created", "enterprise_company", company_id, {"organization_id": organization_id})
        return self._row(db, "enterprise_companies", company_id)

    def link_company_to_event(self, db, *, organization_id: int, event_id: int, company_id: int, role_type: str = "EXHIBITOR", status: str = "INVITED", approval_mode: str = "AUTO_APPROVE", actor: str = "", metadata: dict | None = None) -> dict:
        self._validate_company(db, organization_id, company_id)
        self._validate_event(db, organization_id, event_id)
        role_type = self._choice(role_type, COMPANY_TYPES, "COMPANY_ROLE_INVALID")
        status = self._choice(status, PARTICIPATION_STATUSES, "PARTICIPATION_STATUS_INVALID")
        approval_mode = self._choice(approval_mode, {"AUTO_APPROVE", "REQUIRES_APPROVAL"}, "APPROVAL_MODE_INVALID")
        company = self._row(db, "enterprise_companies", company_id)
        entity_id = None
        if self.enterprise_core:
            entity = self.enterprise_core.ensure_entity(db, organization_id=organization_id, event_id=event_id, entity_type="COMPANY", legacy_table="enterprise_companies", legacy_id=company_id, external_key=self._slug(company["name"]), actor=actor, metadata={"company_id": company_id})
            entity_id = int(entity["id"])
        now = self.now()
        row = db.execute("SELECT * FROM enterprise_company_event_participation WHERE organization_id = ? AND event_id = ? AND company_id = ?", (organization_id, event_id, company_id)).fetchone()
        if row:
            db.execute("UPDATE enterprise_company_event_participation SET entity_id = ?, role_type = ?, status = ?, approval_mode = ?, metadata_json = ?, updated_at = ? WHERE id = ?", (entity_id, role_type, status, approval_mode, self._json(metadata or {}), now, row["id"]))
            participation_id = int(row["id"])
        else:
            cur = db.execute(
                "INSERT INTO enterprise_company_event_participation (organization_id, event_id, company_id, entity_id, role_type, status, approval_mode, metadata_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (organization_id, event_id, company_id, entity_id, role_type, status, approval_mode, self._json(metadata or {}), now, now),
            )
            participation_id = int(getattr(cur, "lastrowid", 0) or 0)
            self._audit(db, actor, "company.event_linked", "enterprise_company_event_participation", participation_id, {"organization_id": organization_id, "event_id": event_id, "company_id": company_id})
            self._domain(db, organization_id, event_id, "COMPANY_EVENT_LINKED", entity_id=entity_id, metadata={"company_id": company_id, "participation_id": participation_id})
        return self._row(db, "enterprise_company_event_participation", participation_id)

    def create_delegation(self, db, *, organization_id: int, event_id: int, company_id: int, name: str, delegation_type: str = "GENERAL", actor: str = "") -> dict:
        participation = self._participation(db, organization_id, event_id, company_id)
        name = self._clean_text(name, 180)
        if not name:
            raise CompanyDelegationError("DELEGATION_NAME_REQUIRED", "Nombre de delegacion obligatorio")
        entity_id = None
        if self.enterprise_core:
            entity = self.enterprise_core.ensure_entity(db, organization_id=organization_id, event_id=event_id, entity_type="DELEGATION", legacy_table="enterprise_delegations", legacy_id=0, external_key=f"{company_id}:{self._slug(name)}", actor=actor, metadata={"company_id": company_id, "name": name})
            entity_id = int(entity["id"])
        now = self.now()
        row = db.execute("SELECT * FROM enterprise_delegations WHERE organization_id = ? AND event_id = ? AND company_id = ? AND name = ?", (organization_id, event_id, company_id, name)).fetchone()
        if row:
            db.execute("UPDATE enterprise_delegations SET entity_id = ?, delegation_type = ?, updated_at = ? WHERE id = ?", (entity_id, self._clean_key(delegation_type, 80), now, row["id"]))
            delegation_id = int(row["id"])
        else:
            cur = db.execute(
                "INSERT INTO enterprise_delegations (organization_id, event_id, company_id, participation_id, entity_id, name, delegation_type, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?)",
                (organization_id, event_id, company_id, participation["id"], entity_id, name, self._clean_key(delegation_type, 80) or "GENERAL", now, now),
            )
            delegation_id = int(getattr(cur, "lastrowid", 0) or 0)
            self._audit(db, actor, "delegation.created", "enterprise_delegation", delegation_id, {"organization_id": organization_id, "event_id": event_id, "company_id": company_id})
        return self._row(db, "enterprise_delegations", delegation_id)

    def set_quota(self, db, *, organization_id: int, event_id: int, company_id: int, quota_type: str, allocated: int, delegation_id: int | None = None, actor: str = "") -> dict:
        self._participation(db, organization_id, event_id, company_id)
        if delegation_id:
            self._delegation(db, organization_id, event_id, company_id, delegation_id)
        quota_type = self._clean_key(quota_type, 80) or "TOTAL"
        allocated = max(0, int(allocated or 0))
        now = self.now()
        row = db.execute(
            "SELECT * FROM enterprise_company_quotas WHERE organization_id = ? AND event_id = ? AND company_id = ? AND COALESCE(delegation_id, 0) = COALESCE(?, 0) AND quota_type = ?",
            (organization_id, event_id, company_id, delegation_id, quota_type),
        ).fetchone()
        if row:
            db.execute("UPDATE enterprise_company_quotas SET allocated = ?, updated_at = ? WHERE id = ?", (allocated, now, row["id"]))
            quota_id = int(row["id"])
        else:
            cur = db.execute(
                "INSERT INTO enterprise_company_quotas (organization_id, event_id, company_id, delegation_id, quota_type, allocated, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (organization_id, event_id, company_id, delegation_id, quota_type, allocated, now, now),
            )
            quota_id = int(getattr(cur, "lastrowid", 0) or 0)
        self._audit(db, actor, "quota.changed", "enterprise_company_quota", quota_id, {"allocated": allocated, "quota_type": quota_type})
        return self._quota_payload(db, quota_id)

    def consume_quota(self, db, *, organization_id: int, event_id: int, company_id: int, quota_type: str = "TOTAL", delegation_id: int | None = None, amount: int = 1) -> dict:
        quota = self._find_quota(db, organization_id, event_id, company_id, quota_type, delegation_id)
        amount = max(1, int(amount or 1))
        available = int(quota["allocated"]) - int(quota["reserved"]) - int(quota["consumed"])
        if available < amount:
            raise CompanyDelegationError("QUOTA_EXCEEDED", "Cupo insuficiente", 409)
        cur = db.execute("UPDATE enterprise_company_quotas SET consumed = consumed + ?, updated_at = ? WHERE id = ? AND allocated - reserved - consumed >= ?", (amount, self.now(), quota["id"], amount))
        if getattr(cur, "rowcount", 0) < 1:
            raise CompanyDelegationError("QUOTA_RACE_LOST", "Cupo consumido por otra operacion", 409)
        return self._quota_payload(db, int(quota["id"]))

    def grant_company_user(self, db, *, organization_id: int, event_id: int, company_id: int, email: str, role: str = "VIEWER", permissions: list[str] | None = None, actor: str = "") -> dict:
        self._participation(db, organization_id, event_id, company_id)
        email = self._email(email)
        role = self._choice(role, COMPANY_USER_ROLES, "COMPANY_USER_ROLE_INVALID")
        permissions = permissions or self._default_permissions(role)
        now = self.now()
        row = db.execute("SELECT * FROM enterprise_company_users WHERE organization_id = ? AND event_id = ? AND company_id = ? AND email = ?", (organization_id, event_id, company_id, email)).fetchone()
        if row:
            db.execute("UPDATE enterprise_company_users SET role = ?, permissions_json = ?, updated_at = ? WHERE id = ?", (role, self._json(permissions), now, row["id"]))
            user_id = int(row["id"])
        else:
            cur = db.execute("INSERT INTO enterprise_company_users (organization_id, event_id, company_id, email, role, permissions_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (organization_id, event_id, company_id, email, role, self._json(permissions), now, now))
            user_id = int(getattr(cur, "lastrowid", 0) or 0)
            self._audit(db, actor, "company_user.granted", "enterprise_company_user", user_id, {"email": email, "role": role})
        return self._row(db, "enterprise_company_users", user_id)

    def authorize_company_user(self, db, *, organization_id: int, event_id: int, company_id: int, email: str, permission: str) -> bool:
        row = db.execute(
            "SELECT * FROM enterprise_company_users WHERE organization_id = ? AND event_id = ? AND company_id = ? AND email = ? AND status = 'ACTIVE'",
            (organization_id, event_id, company_id, self._email(email)),
        ).fetchone()
        if not row:
            return False
        permissions = self._loads(row["permissions_json"], [])
        return permission in permissions or "*" in permissions

    def create_invitation(self, db, *, organization_id: int, event_id: int, company_id: int, email: str, delegation_id: int | None = None, quota_type: str = "TOTAL", expires_in_days: int = 7, idempotency_key: str = "", actor: str = "") -> dict:
        self._participation(db, organization_id, event_id, company_id)
        if delegation_id:
            self._delegation(db, organization_id, event_id, company_id, delegation_id)
        if idempotency_key:
            existing = db.execute("SELECT * FROM enterprise_invitations WHERE organization_id = ? AND idempotency_key = ?", (organization_id, idempotency_key)).fetchone()
            if existing:
                return {"ok": True, "idempotent": True, "invitation": dict(existing), "token": ""}
        self.consume_quota(db, organization_id=organization_id, event_id=event_id, company_id=company_id, quota_type=quota_type, delegation_id=delegation_id)
        token = secrets.token_urlsafe(32)
        token_hash = self._hash(token)
        now = self.now()
        expires_at = (datetime.fromisoformat(now) + timedelta(days=max(1, int(expires_in_days or 7)))).isoformat(timespec="seconds") if now else ""
        cur = db.execute(
            "INSERT INTO enterprise_invitations (organization_id, event_id, company_id, delegation_id, invitation_token_hash, token_hint, email, quota_type, status, expires_at, idempotency_key, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?, ?)",
            (organization_id, event_id, company_id, delegation_id, token_hash, token[:10], self._email(email), self._clean_key(quota_type, 80) or "TOTAL", expires_at, idempotency_key, now, now),
        )
        invitation_id = int(getattr(cur, "lastrowid", 0) or 0)
        self._audit(db, actor, "invitation.created", "enterprise_invitation", invitation_id, {"company_id": company_id, "event_id": event_id})
        return {"ok": True, "invitation": self._row(db, "enterprise_invitations", invitation_id), "token": token}

    def revoke_invitation(self, db, *, organization_id: int, event_id: int, invitation_id: int, actor: str = "") -> dict:
        row = self._invitation(db, organization_id, event_id, invitation_id)
        db.execute("UPDATE enterprise_invitations SET status = 'REVOKED', revoked_at = ?, updated_at = ? WHERE id = ?", (self.now(), self.now(), invitation_id))
        self._audit(db, actor, "invitation.revoked", "enterprise_invitation", invitation_id, {"company_id": row["company_id"]})
        return self._row(db, "enterprise_invitations", invitation_id)

    def register_from_invitation(self, db, *, organization_id: int, token: str, first_name: str, last_name: str, dni: str, email: str, phone: str = "", actor: str = "company-portal") -> dict:
        token_hash = self._hash(token)
        inv = db.execute("SELECT * FROM enterprise_invitations WHERE organization_id = ? AND invitation_token_hash = ?", (organization_id, token_hash)).fetchone()
        if not inv:
            raise CompanyDelegationError("INVITATION_NOT_FOUND", "Invitacion inexistente", 404)
        if inv["status"] != "PENDING":
            raise CompanyDelegationError("INVITATION_NOT_USABLE", "Invitacion no disponible", 409)
        if inv["expires_at"] and inv["expires_at"] < self.now():
            db.execute("UPDATE enterprise_invitations SET status = 'EXPIRED', updated_at = ? WHERE id = ?", (self.now(), inv["id"]))
            raise CompanyDelegationError("INVITATION_EXPIRED", "Invitacion vencida", 410)
        email = self._email(email or inv["email"])
        person = db.execute("SELECT * FROM people WHERE lower(email) = lower(?)", (email,)).fetchone()
        now = self.now()
        if person:
            person_id = int(person["id"])
        else:
            cur = db.execute(
                "INSERT INTO people (first_name, last_name, dni, email, phone, company, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (self._clean_text(first_name, 120), self._clean_text(last_name, 120), self._clean_text(dni, 80), email, self._clean_text(phone, 80), self._company_name(db, int(inv["company_id"])), now),
            )
            person_id = int(getattr(cur, "lastrowid", 0) or 0)
        token_value = f"INV-{secrets.token_urlsafe(10)}"
        cur = db.execute(
            "INSERT INTO accreditations (event_id, person_id, token, type, status, created_at) VALUES (?, ?, ?, ?, 'active', ?)",
            (inv["event_id"], person_id, token_value, inv["quota_type"] or "General", now),
        )
        accreditation_id = int(getattr(cur, "lastrowid", 0) or 0)
        entity_id = None
        if self.enterprise_core:
            entity = self.enterprise_core.ensure_entity(db, organization_id=organization_id, event_id=int(inv["event_id"]), entity_type="PERSON", legacy_table="people", legacy_id=person_id, actor=actor, metadata={"source": "company_invitation"})
            entity_id = int(entity["id"])
        member = self.add_member(db, organization_id=organization_id, event_id=int(inv["event_id"]), company_id=int(inv["company_id"]), delegation_id=inv["delegation_id"], person_id=person_id, accreditation_id=accreditation_id, entity_id=entity_id, member_role=inv["quota_type"] or "GUEST", source="INVITATION")
        db.execute("UPDATE enterprise_invitations SET status = 'COMPLETED', completed_at = ?, person_id = ?, accreditation_id = ?, updated_at = ? WHERE id = ?", (now, person_id, accreditation_id, now, inv["id"]))
        self._domain(db, organization_id, int(inv["event_id"]), "DELEGATION_MEMBER_REGISTERED", entity_id=entity_id, metadata={"company_id": inv["company_id"], "delegation_id": inv["delegation_id"], "member_id": member["id"]})
        return {"ok": True, "person_id": person_id, "accreditation_id": accreditation_id, "member": member}

    def add_member(self, db, *, organization_id: int, event_id: int, company_id: int, person_id: int, delegation_id: int | None = None, accreditation_id: int | None = None, entity_id: int | None = None, member_role: str = "GUEST", source: str = "") -> dict:
        self._participation(db, organization_id, event_id, company_id)
        if delegation_id:
            self._delegation(db, organization_id, event_id, company_id, delegation_id)
        person = db.execute("SELECT id FROM people WHERE id = ?", (person_id,)).fetchone()
        if not person:
            raise CompanyDelegationError("PERSON_NOT_FOUND", "Persona fuera de alcance", 404)
        if accreditation_id:
            acc = db.execute("SELECT id FROM accreditations WHERE id = ? AND event_id = ? AND person_id = ?", (accreditation_id, event_id, person_id)).fetchone()
            if not acc:
                raise CompanyDelegationError("ACCREDITATION_SCOPE_ERROR", "Acreditacion fuera de alcance", 403)
        now = self.now()
        cur = db.execute(
            "INSERT OR IGNORE INTO enterprise_delegation_members (organization_id, event_id, company_id, delegation_id, person_id, accreditation_id, entity_id, member_role, status, source, joined_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?)",
            (organization_id, event_id, company_id, delegation_id, person_id, accreditation_id, entity_id, self._clean_key(member_role, 80) or "GUEST", self._clean_key(source, 80), now, now),
        )
        member_id = int(getattr(cur, "lastrowid", 0) or 0)
        if not member_id:
            row = db.execute("SELECT * FROM enterprise_delegation_members WHERE organization_id = ? AND event_id = ? AND company_id = ? AND COALESCE(delegation_id, 0) = COALESCE(?, 0) AND person_id = ? AND member_role = ?", (organization_id, event_id, company_id, delegation_id, person_id, self._clean_key(member_role, 80) or "GUEST")).fetchone()
            member_id = int(row["id"])
        return self._row(db, "enterprise_delegation_members", member_id)

    def submit_approval(self, db, *, organization_id: int, event_id: int, company_id: int, person_id: int, accreditation_id: int | None = None, delegation_id: int | None = None, source: str = "company-portal") -> dict:
        now = self.now()
        cur = db.execute(
            "INSERT INTO enterprise_approval_requests (organization_id, event_id, company_id, delegation_id, person_id, accreditation_id, status, source, submitted_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'PENDING_REVIEW', ?, ?, ?)",
            (organization_id, event_id, company_id, delegation_id, person_id, accreditation_id, self._clean_key(source, 80), now, now),
        )
        return self._row(db, "enterprise_approval_requests", int(getattr(cur, "lastrowid", 0) or 0))

    def review_approval(self, db, *, organization_id: int, event_id: int, approval_id: int, approve: bool, reviewer: str, reason: str = "") -> dict:
        row = db.execute("SELECT * FROM enterprise_approval_requests WHERE id = ? AND organization_id = ? AND event_id = ?", (approval_id, organization_id, event_id)).fetchone()
        if not row:
            raise CompanyDelegationError("APPROVAL_NOT_FOUND", "Solicitud fuera de alcance", 404)
        status = "APPROVED" if approve else "REJECTED"
        db.execute("UPDATE enterprise_approval_requests SET status = ?, reviewer = ?, reason = ?, reviewed_at = ?, updated_at = ? WHERE id = ?", (status, self._clean_text(reviewer, 120), self._clean_text(reason, 240), self.now(), self.now(), approval_id))
        self._audit(db, reviewer, f"approval.{status.lower()}", "enterprise_approval_request", approval_id, {"event_id": event_id})
        return self._row(db, "enterprise_approval_requests", approval_id)

    def preview_csv_import(self, db, *, organization_id: int, event_id: int, company_id: int, csv_text: str, delegation_id: int | None = None) -> dict:
        self._participation(db, organization_id, event_id, company_id)
        errors, valid, seen = [], [], set()
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        required = {"first_name", "last_name", "email"}
        if not reader.fieldnames or not required.issubset({f.strip() for f in reader.fieldnames}):
            return {"ok": False, "valid_rows": [], "errors": [{"row": 0, "error": "MISSING_REQUIRED_COLUMNS"}]}
        for index, row in enumerate(reader, start=2):
            if not any(str(v or "").strip() for v in row.values()):
                continue
            email = str(row.get("email") or "").strip().lower()
            row_errors = []
            if not self._valid_email(email):
                row_errors.append("INVALID_EMAIL")
            if email in seen:
                row_errors.append("DUPLICATE_IN_FILE")
            seen.add(email)
            if db.execute("SELECT id FROM people WHERE lower(email) = lower(?)", (email,)).fetchone():
                row_errors.append("EXISTING_PERSON_REUSE")
            if row_errors:
                errors.append({"row": index, "email": email, "errors": row_errors})
            else:
                valid.append({"row": index, "first_name": row.get("first_name", ""), "last_name": row.get("last_name", ""), "email": email, "dni": row.get("dni", ""), "quota_type": row.get("quota_type", "TOTAL") or "TOTAL", "delegation_id": delegation_id})
        return {"ok": not any("INVALID_EMAIL" in e["errors"] or "DUPLICATE_IN_FILE" in e["errors"] for e in errors), "valid_rows": valid, "errors": errors, "summary": {"valid": len(valid), "errors": len(errors)}}

    def confirm_csv_import(self, db, *, organization_id: int, event_id: int, company_id: int, csv_text: str, import_id: str, delegation_id: int | None = None) -> dict:
        existing = db.execute("SELECT * FROM enterprise_import_jobs WHERE organization_id = ? AND event_id = ? AND company_id = ? AND import_id = ?", (organization_id, event_id, company_id, import_id)).fetchone()
        if existing and existing["status"] == "IMPORTED":
            return {"ok": True, "idempotent": True, "summary": self._loads(existing["summary_json"], {})}
        preview = self.preview_csv_import(db, organization_id=organization_id, event_id=event_id, company_id=company_id, csv_text=csv_text, delegation_id=delegation_id)
        if not preview["ok"]:
            self._record_import_job(db, organization_id, event_id, company_id, delegation_id, import_id, "REJECTED", preview["summary"], preview["errors"])
            return {"ok": False, "summary": preview["summary"], "errors": preview["errors"]}
        created, reused, rejected = 0, 0, 0
        for row in preview["valid_rows"]:
            try:
                invitation = self.create_invitation(db, organization_id=organization_id, event_id=event_id, company_id=company_id, email=row["email"], delegation_id=delegation_id, quota_type=row["quota_type"], idempotency_key=f"{import_id}:{row['email']}")
                self.register_from_invitation(db, organization_id=organization_id, token=invitation["token"], first_name=row["first_name"], last_name=row["last_name"], dni=row["dni"], email=row["email"])
                created += 1
            except CompanyDelegationError:
                rejected += 1
        summary = {"created": created, "reused": reused, "rejected": rejected, "errors": len(preview["errors"])}
        self._record_import_job(db, organization_id, event_id, company_id, delegation_id, import_id, "IMPORTED", summary, preview["errors"])
        return {"ok": rejected == 0, "summary": summary, "errors": preview["errors"]}

    def dashboard(self, db, *, organization_id: int, event_id: int, company_id: int) -> dict:
        self._participation(db, organization_id, event_id, company_id)
        quotas = [self._quota_dict(row) for row in db.execute("SELECT * FROM enterprise_company_quotas WHERE organization_id = ? AND event_id = ? AND company_id = ? ORDER BY quota_type", (organization_id, event_id, company_id)).fetchall()]
        count = lambda sql, p: int(db.execute(sql, p).fetchone()["c"])
        return {
            "company": dict(self._row(db, "enterprise_companies", company_id)),
            "event_id": event_id,
            "quotas": quotas,
            "people": count("SELECT COUNT(*) AS c FROM enterprise_delegation_members WHERE organization_id = ? AND event_id = ? AND company_id = ?", (organization_id, event_id, company_id)),
            "pending": count("SELECT COUNT(*) AS c FROM enterprise_approval_requests WHERE organization_id = ? AND event_id = ? AND company_id = ? AND status = 'PENDING_REVIEW'", (organization_id, event_id, company_id)),
            "approved": count("SELECT COUNT(*) AS c FROM enterprise_approval_requests WHERE organization_id = ? AND event_id = ? AND company_id = ? AND status = 'APPROVED'", (organization_id, event_id, company_id)),
            "rejected": count("SELECT COUNT(*) AS c FROM enterprise_approval_requests WHERE organization_id = ? AND event_id = ? AND company_id = ? AND status = 'REJECTED'", (organization_id, event_id, company_id)),
        }

    def _record_import_job(self, db, organization_id, event_id, company_id, delegation_id, import_id, status, summary, errors):
        now = self.now()
        db.execute(
            "INSERT INTO enterprise_import_jobs (organization_id, event_id, company_id, delegation_id, import_id, status, summary_json, errors_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(organization_id, event_id, company_id, import_id) DO UPDATE SET status = excluded.status, summary_json = excluded.summary_json, errors_json = excluded.errors_json, updated_at = excluded.updated_at",
            (organization_id, event_id, company_id, delegation_id, import_id, status, self._json(summary), self._json(errors), now, now),
        )

    def _find_quota(self, db, organization_id, event_id, company_id, quota_type, delegation_id=None):
        row = db.execute("SELECT * FROM enterprise_company_quotas WHERE organization_id = ? AND event_id = ? AND company_id = ? AND COALESCE(delegation_id, 0) = COALESCE(?, 0) AND quota_type = ?", (organization_id, event_id, company_id, delegation_id, self._clean_key(quota_type, 80) or "TOTAL")).fetchone()
        if not row:
            raise CompanyDelegationError("QUOTA_NOT_FOUND", "Cupo no configurado", 404)
        return row

    def _quota_payload(self, db, quota_id):
        return self._quota_dict(self._row(db, "enterprise_company_quotas", quota_id))

    def _quota_dict(self, row):
        data = dict(row)
        data["available"] = int(data["allocated"]) - int(data["reserved"]) - int(data["consumed"])
        return data

    def _participation(self, db, organization_id, event_id, company_id):
        row = db.execute("SELECT * FROM enterprise_company_event_participation WHERE organization_id = ? AND event_id = ? AND company_id = ?", (organization_id, event_id, company_id)).fetchone()
        if not row:
            raise CompanyDelegationError("COMPANY_EVENT_SCOPE_ERROR", "Empresa fuera de evento", 403)
        return row

    def _delegation(self, db, organization_id, event_id, company_id, delegation_id):
        row = db.execute("SELECT * FROM enterprise_delegations WHERE id = ? AND organization_id = ? AND event_id = ? AND company_id = ?", (delegation_id, organization_id, event_id, company_id)).fetchone()
        if not row:
            raise CompanyDelegationError("DELEGATION_SCOPE_ERROR", "Delegacion fuera de alcance", 403)
        return row

    def _invitation(self, db, organization_id, event_id, invitation_id):
        row = db.execute("SELECT * FROM enterprise_invitations WHERE id = ? AND organization_id = ? AND event_id = ?", (invitation_id, organization_id, event_id)).fetchone()
        if not row:
            raise CompanyDelegationError("INVITATION_NOT_FOUND", "Invitacion fuera de alcance", 404)
        return row

    def _validate_company(self, db, organization_id, company_id):
        row = db.execute("SELECT id FROM enterprise_companies WHERE id = ? AND organization_id = ?", (company_id, organization_id)).fetchone()
        if not row:
            raise CompanyDelegationError("COMPANY_NOT_FOUND", "Empresa fuera de alcance", 404)

    def _validate_event(self, db, organization_id, event_id):
        row = db.execute("SELECT id FROM events WHERE id = ? AND organization_id = ?", (event_id, organization_id)).fetchone()
        if not row:
            raise CompanyDelegationError("EVENT_SCOPE_ERROR", "Evento fuera de alcance", 403)

    def _company_name(self, db, company_id):
        row = db.execute("SELECT name FROM enterprise_companies WHERE id = ?", (company_id,)).fetchone()
        return row["name"] if row else ""

    def _row(self, db, table, row_id):
        row = db.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
        if not row:
            raise CompanyDelegationError("ROW_NOT_FOUND", "Registro no encontrado", 404)
        return dict(row)

    def _audit(self, db, actor, action, target_type, target_id, metadata):
        if self.audit_service:
            self.audit_service.record(db, actor or "company-delegation", action, target_type, target_id, metadata)

    def _domain(self, db, organization_id, event_id, event_type, entity_id=None, metadata=None):
        if self.enterprise_core:
            self.enterprise_core.record_domain_event(db, organization_id=organization_id, event_id=event_id, event_type=event_type, entity_id=entity_id, metadata=metadata or {})

    def _default_permissions(self, role):
        if role == "COMPANY_ADMIN":
            return ["company.view", "delegations.manage", "people.manage", "invitations.manage", "imports.manage"]
        if role == "DELEGATION_MANAGER":
            return ["company.view", "people.manage", "invitations.manage"]
        return ["company.view"]

    def _choice(self, value: str, allowed: set[str], code: str) -> str:
        normalized = str(value or "").strip().upper()
        if normalized not in allowed:
            raise CompanyDelegationError(code, "Valor invalido", 400)
        return normalized

    def _clean_key(self, value: str, limit: int) -> str:
        text = re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(value or "").strip()).strip("_")
        return text[:limit]

    def _clean_text(self, value: str, limit: int) -> str:
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or "")).strip()[:limit]

    def _email(self, value: str) -> str:
        email = str(value or "").strip().lower()
        if not self._valid_email(email):
            raise CompanyDelegationError("EMAIL_INVALID", "Email invalido", 400)
        return email

    def _valid_email(self, value: str) -> bool:
        return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(value or "")))

    def _json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=True, sort_keys=True)

    def _loads(self, value: str, default):
        try:
            return json.loads(value or "")
        except Exception:
            return default

    def _hash(self, value: str) -> str:
        return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()

    def _slug(self, value: str) -> str:
        return self._clean_key(str(value or "").lower(), 160)
