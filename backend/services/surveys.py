from __future__ import annotations

import csv
import hashlib
import hmac
import json
import os
import re
import secrets
from collections import Counter
from collections.abc import Callable
from io import StringIO

from backend.services.audit import AuditService


SURVEY_TYPE_STATUSES = {"ACTIVE", "DISABLED", "RETIRED"}
SURVEY_STATUSES = {"DRAFT", "PUBLISHED", "OPEN", "CLOSED", "ARCHIVED"}
SURVEY_VERSION_STATUSES = {"DRAFT", "PUBLISHED", "RETIRED"}
SURVEY_ASSIGNMENT_STATUSES = {"DRAFT", "OPEN", "CLOSED", "DISABLED", "ARCHIVED"}
SURVEY_SESSION_STATUSES = {"IN_PROGRESS", "SUBMITTED", "EXPIRED", "CANCELLED"}
SURVEY_RESPONSE_MODES = {"IDENTIFIED", "ANONYMOUS"}
SURVEY_DUPLICATE_POLICIES = {"ONE_PER_PARTICIPANT", "ONE_PER_TOKEN", "ALLOW_MULTIPLE"}
SURVEY_ACCESS_POLICIES = {"EVENT_PARTICIPANTS", "TOKEN"}
SURVEY_QUESTION_TYPES = {"SHORT_TEXT", "LONG_TEXT", "SINGLE_CHOICE", "MULTIPLE_CHOICE", "SCALE", "YES_NO"}


class SurveyDomainError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class SurveyService:
    def __init__(self, audit_service: AuditService, now: Callable[[], str], token_factory: Callable[[], str] | None = None, secret: str = "") -> None:
        self.audit_service = audit_service
        self.now = now
        self.token_factory = token_factory or (lambda: secrets.token_urlsafe(32))
        self.secret = secret or "bitora-surveys-local-secret"

    def create_type(self, db, *, organization_id: int, event_id: int | None, actor: str, code: str, name: str, description: str = "") -> dict:
        event_id = self._validate_optional_event(db, organization_id, event_id)
        code = self._normalize_code(code, "SURVEY_TYPE_INVALID")
        name = self._clean_text(name, 120)
        if not name:
            raise SurveyDomainError("SURVEY_TYPE_INVALID", "Nombre de tipo obligatorio", 400)
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO survey_types (
                organization_id, event_id, code, name, description, status, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?)
            """,
            (organization_id, event_id, code, name, self._clean_text(description, 500), actor, now, now),
        )
        item = self._get_type(db, int(cur.lastrowid), organization_id)
        self.audit_service.record(db, actor, "surveys.type.created", "survey_type", int(item["id"]), {"organization_id": organization_id, "event_id": event_id, "code": code})
        return {"ok": True, "item": self._type_payload(item)}

    def list_types(self, db, *, organization_id: int, event_id: int | None) -> dict:
        rows = db.execute(
            """
            SELECT * FROM survey_types
            WHERE organization_id = ? AND (event_id IS NULL OR event_id = ?)
            ORDER BY id
            """,
            (organization_id, event_id),
        ).fetchall()
        return {"items": [self._type_payload(row) for row in rows]}

    def create_survey(
        self,
        db,
        *,
        organization_id: int,
        event_id: int,
        actor: str,
        survey_type_id: int,
        name: str,
        description: str = "",
        response_mode: str = "IDENTIFIED",
        access_policy: str = "EVENT_PARTICIPANTS",
        duplicate_policy: str = "ONE_PER_PARTICIPANT",
        opens_at: str = "",
        closes_at: str = "",
    ) -> dict:
        self._validate_event(db, organization_id, event_id)
        survey_type = self._get_type(db, survey_type_id, organization_id)
        self._ensure_optional_event_matches(event_id, survey_type["event_id"])
        response_mode = self._normalize_choice(response_mode, SURVEY_RESPONSE_MODES, "SURVEY_MODE_INVALID")
        access_policy = self._normalize_choice(access_policy, SURVEY_ACCESS_POLICIES, "SURVEY_ACCESS_INVALID")
        duplicate_policy = self._normalize_choice(duplicate_policy, SURVEY_DUPLICATE_POLICIES, "SURVEY_DUPLICATE_POLICY_INVALID")
        if response_mode == "ANONYMOUS" and duplicate_policy == "ONE_PER_PARTICIPANT":
            duplicate_policy = "ONE_PER_TOKEN"
        name = self._clean_text(name, 160)
        if not name:
            raise SurveyDomainError("SURVEY_INVALID", "Nombre de encuesta obligatorio", 400)
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO surveys (
                organization_id, event_id, survey_type_id, name, description, status,
                response_mode, access_policy, duplicate_policy, opens_at, closes_at,
                created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (organization_id, event_id, survey_type_id, name, self._clean_text(description, 1000), response_mode, access_policy, duplicate_policy, opens_at or None, closes_at or None, actor, now, now),
        )
        item = self._get_survey(db, int(cur.lastrowid), organization_id, event_id)
        self.audit_service.record(db, actor, "surveys.created", "survey", int(item["id"]), {"organization_id": organization_id, "event_id": event_id, "response_mode": response_mode})
        return {"ok": True, "item": self._survey_payload(item)}

    def update_survey_draft(self, db, *, organization_id: int, event_id: int, survey_id: int, actor: str, name: str | None = None, description: str | None = None) -> dict:
        survey = self._get_survey(db, survey_id, organization_id, event_id)
        if str(survey["status"]) not in {"DRAFT", "PUBLISHED"}:
            raise SurveyDomainError("SURVEY_NOT_EDITABLE", "La encuesta no admite edicion directa", 409)
        updates = {}
        if name is not None:
            clean_name = self._clean_text(name, 160)
            if not clean_name:
                raise SurveyDomainError("SURVEY_INVALID", "Nombre de encuesta obligatorio", 400)
            updates["name"] = clean_name
        if description is not None:
            updates["description"] = self._clean_text(description, 1000)
        if updates:
            updates["updated_at"] = self.now()
            assignments = ", ".join(f"{key} = ?" for key in updates)
            db.execute(f"UPDATE surveys SET {assignments} WHERE id = ?", [updates[key] for key in updates] + [survey_id])
            self.audit_service.record(db, actor, "surveys.updated", "survey", survey_id, {"organization_id": organization_id, "event_id": event_id})
        return {"ok": True, "item": self._survey_payload(self._get_survey(db, survey_id, organization_id, event_id))}

    def create_version(self, db, *, organization_id: int, event_id: int, survey_id: int, actor: str, title: str, description: str = "", instructions: str = "", questions: list[dict] | None = None) -> dict:
        survey = self._get_survey(db, survey_id, organization_id, event_id)
        if str(survey["status"]) == "ARCHIVED":
            raise SurveyDomainError("SURVEY_ARCHIVED", "La encuesta esta archivada", 409)
        normalized_questions = self._normalize_questions(questions or [])
        title = self._clean_text(title, 180)
        if not title:
            raise SurveyDomainError("SURVEY_VERSION_INVALID", "Titulo obligatorio", 400)
        content_hash = self._stable_hash({"title": title, "description": description, "instructions": instructions, "questions": normalized_questions})
        version_number = int(db.execute("SELECT COALESCE(MAX(version_number), 0) + 1 AS n FROM survey_versions WHERE survey_id = ?", (survey_id,)).fetchone()["n"])
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO survey_versions (
                survey_id, organization_id, event_id, version_number, title, description,
                instructions, content_hash, status, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?)
            """,
            (survey_id, organization_id, event_id, version_number, title, self._clean_text(description, 1000), self._clean_text(instructions, 1000), content_hash, actor, now, now),
        )
        version_id = int(cur.lastrowid)
        self._insert_questions(db, organization_id, event_id, survey_id, version_id, normalized_questions)
        item = self._get_version(db, version_id, organization_id, survey_id=survey_id)
        self.audit_service.record(db, actor, "surveys.version.created", "survey_version", version_id, {"organization_id": organization_id, "event_id": event_id, "survey_id": survey_id, "content_hash": content_hash})
        return {"ok": True, "item": self._version_payload(db, item)}

    def publish_version(self, db, *, organization_id: int, event_id: int, survey_id: int, version_id: int, actor: str, idempotency_key: str) -> dict:
        key = self._validate_idempotency_key(idempotency_key)
        version = self._get_version(db, version_id, organization_id, survey_id=survey_id)
        if int(version["event_id"]) != int(event_id):
            raise SurveyDomainError("SURVEY_SCOPE_MISMATCH", "La version no pertenece al evento", 403)
        if str(version["status"]) == "PUBLISHED":
            return {"ok": True, "idempotent": True, "item": self._version_payload(db, version)}
        if str(version["status"]) != "DRAFT":
            raise SurveyDomainError("SURVEY_VERSION_NOT_PUBLISHABLE", "La version no esta en borrador", 409)
        required_count = int(db.execute("SELECT COUNT(*) AS c FROM survey_questions WHERE version_id = ?", (version_id,)).fetchone()["c"] or 0)
        if required_count <= 0:
            raise SurveyDomainError("SURVEY_VERSION_EMPTY", "La version no tiene preguntas", 409)
        now = self.now()
        db.execute("UPDATE survey_versions SET status = 'PUBLISHED', published_at = ?, published_by = ?, updated_at = ?, idempotency_key = ? WHERE id = ?", (now, actor, now, key, version_id))
        db.execute("UPDATE surveys SET status = 'PUBLISHED', current_version_id = ?, updated_at = ? WHERE id = ?", (version_id, now, survey_id))
        self.audit_service.record(db, actor, "surveys.version.published", "survey_version", version_id, {"organization_id": organization_id, "event_id": event_id, "survey_id": survey_id})
        return {"ok": True, "item": self._version_payload(db, self._get_version(db, version_id, organization_id, survey_id=survey_id))}

    def assign_survey(
        self,
        db,
        *,
        organization_id: int,
        event_id: int,
        survey_id: int,
        actor: str,
        version_id: int | None = None,
        activity_id: int | None = None,
        opens_at: str = "",
        closes_at: str = "",
        access_mode: str = "EVENT_PARTICIPANTS",
    ) -> dict:
        survey = self._get_survey(db, survey_id, organization_id, event_id)
        version_id = int(version_id or survey["current_version_id"] or 0)
        version = self._get_version(db, version_id, organization_id, survey_id=survey_id)
        if str(version["status"]) != "PUBLISHED":
            raise SurveyDomainError("SURVEY_VERSION_NOT_PUBLISHED", "La version no esta publicada", 409)
        if activity_id:
            self._validate_activity(db, organization_id, event_id, activity_id)
        access_mode = self._normalize_choice(access_mode, SURVEY_ACCESS_POLICIES, "SURVEY_ACCESS_INVALID")
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO survey_assignments (
                survey_id, version_id, organization_id, event_id, activity_id,
                status, access_mode, opens_at, closes_at, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?)
            """,
            (survey_id, version_id, organization_id, event_id, activity_id, access_mode, opens_at or survey["opens_at"], closes_at or survey["closes_at"], actor, now, now),
        )
        db.execute("UPDATE surveys SET status = 'OPEN', updated_at = ? WHERE id = ?", (now, survey_id))
        item = self._get_assignment(db, int(cur.lastrowid), organization_id, event_id)
        self.audit_service.record(db, actor, "surveys.assigned", "survey_assignment", int(item["id"]), {"organization_id": organization_id, "event_id": event_id, "survey_id": survey_id, "version_id": version_id})
        return {"ok": True, "item": self._assignment_payload(item)}

    def create_access_token(self, db, *, organization_id: int, event_id: int, assignment_id: int, participant_id: int | None = None, expires_at: str = "") -> dict:
        assignment = self._get_assignment(db, assignment_id, organization_id, event_id)
        if participant_id:
            self._validate_participant(db, event_id, participant_id)
        token = self.token_factory()
        token_hash = self._token_hash(token)
        subject_hash = self._anonymous_subject_hash(assignment_id, participant_id or token_hash)
        now = self.now()
        db.execute(
            """
            INSERT INTO survey_access_tokens (
                assignment_id, survey_id, version_id, organization_id, event_id,
                participant_id, anonymous_subject_hash, token_hash, token_hint,
                status, expires_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?)
            """,
            (assignment_id, assignment["survey_id"], assignment["version_id"], organization_id, event_id, participant_id, subject_hash, token_hash, token[:8], expires_at or None, now),
        )
        return {"ok": True, "token": token, "token_hint": token[:8]}

    def start_response(self, db, *, organization_id: int, event_id: int, assignment_id: int, participant_id: int | None = None, token: str = "", idempotency_key: str = "") -> dict:
        key = self._validate_idempotency_key(idempotency_key)
        assignment = self._get_assignment(db, assignment_id, organization_id, event_id)
        survey = self._get_survey(db, int(assignment["survey_id"]), organization_id, event_id)
        self._ensure_assignment_open(assignment, survey)
        token_row = None
        subject_hash = ""
        if str(survey["response_mode"]) == "ANONYMOUS" or str(assignment["access_mode"]) == "TOKEN":
            token_row = self._get_token(db, organization_id, event_id, assignment_id, token)
            subject_hash = str(token_row["anonymous_subject_hash"])
            if token_row["expires_at"] and self._timestamp_gt(self.now(), str(token_row["expires_at"])):
                raise SurveyDomainError("SURVEY_TOKEN_EXPIRED", "Token vencido", 403)
            if str(token_row["status"]) != "ACTIVE":
                raise SurveyDomainError("SURVEY_TOKEN_INVALID", "Token no disponible", 403)
            if str(survey["duplicate_policy"]) == "ONE_PER_TOKEN" and db.execute("SELECT 1 FROM survey_response_sessions WHERE assignment_id = ? AND token_hash = ? AND status = 'SUBMITTED'", (assignment_id, token_row["token_hash"])).fetchone():
                raise SurveyDomainError("SURVEY_DUPLICATE_RESPONSE", "Respuesta duplicada", 409)
        else:
            if not participant_id:
                raise SurveyDomainError("SURVEY_PARTICIPANT_REQUIRED", "Participante obligatorio", 400)
            self._validate_participant(db, event_id, participant_id)
            subject_hash = self._anonymous_subject_hash(assignment_id, participant_id)
            if str(survey["duplicate_policy"]) == "ONE_PER_PARTICIPANT" and db.execute("SELECT 1 FROM survey_response_sessions WHERE assignment_id = ? AND participant_id = ? AND status = 'SUBMITTED'", (assignment_id, participant_id)).fetchone():
                raise SurveyDomainError("SURVEY_DUPLICATE_RESPONSE", "Respuesta duplicada", 409)
        existing = db.execute("SELECT * FROM survey_response_sessions WHERE organization_id = ? AND idempotency_key = ?", (organization_id, key)).fetchone()
        if existing:
            return {"ok": True, "idempotent": True, "item": self._session_payload(existing)}
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO survey_response_sessions (
                assignment_id, survey_id, version_id, organization_id, event_id,
                response_mode, participant_id, anonymous_subject_hash, token_hash,
                status, started_at, idempotency_key, request_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'IN_PROGRESS', ?, ?, ?, ?, ?)
            """,
            (
                assignment_id,
                assignment["survey_id"],
                assignment["version_id"],
                organization_id,
                event_id,
                survey["response_mode"],
                None if str(survey["response_mode"]) == "ANONYMOUS" else participant_id,
                subject_hash,
                token_row["token_hash"] if token_row else "",
                now,
                key,
                self._stable_hash({"assignment_id": assignment_id, "participant_id": participant_id or "", "token": bool(token)}),
                now,
                now,
            ),
        )
        item = db.execute("SELECT * FROM survey_response_sessions WHERE id = ?", (int(cur.lastrowid),)).fetchone()
        return {"ok": True, "item": self._session_payload(item)}

    def submit_response(self, db, *, organization_id: int, event_id: int, session_id: int, answers: list[dict], token: str = "") -> dict:
        session = self._get_session(db, session_id, organization_id, event_id)
        if str(session["status"]) == "SUBMITTED":
            if answers:
                raise SurveyDomainError("SURVEY_SESSION_CLOSED", "La respuesta ya fue enviada", 409)
            return {"ok": True, "idempotent": True, "item": self._session_payload(session)}
        if str(session["status"]) != "IN_PROGRESS":
            raise SurveyDomainError("SURVEY_SESSION_CLOSED", "Sesion cerrada", 409)
        assignment = self._get_assignment(db, int(session["assignment_id"]), organization_id, event_id)
        survey = self._get_survey(db, int(session["survey_id"]), organization_id, event_id)
        self._ensure_assignment_open(assignment, survey)
        if str(session["response_mode"]) == "ANONYMOUS":
            token_row = self._get_token(db, organization_id, event_id, int(session["assignment_id"]), token)
            if not hmac.compare_digest(str(token_row["token_hash"]), str(session["token_hash"])):
                raise SurveyDomainError("SURVEY_TOKEN_INVALID", "Token invalido", 403)
        normalized = self._normalize_answers(db, session, answers)
        self._replace_answers(db, session, normalized)
        now = self.now()
        db.execute("UPDATE survey_response_sessions SET status = 'SUBMITTED', submitted_at = ?, updated_at = ? WHERE id = ?", (now, now, session_id))
        if str(session["token_hash"] or ""):
            db.execute("UPDATE survey_access_tokens SET status = 'USED', used_at = ? WHERE assignment_id = ? AND token_hash = ?", (now, session["assignment_id"], session["token_hash"]))
        updated = self._get_session(db, session_id, organization_id, event_id)
        return {"ok": True, "item": self._session_payload(updated)}

    def close_assignment(self, db, *, organization_id: int, event_id: int, assignment_id: int, actor: str) -> dict:
        assignment = self._get_assignment(db, assignment_id, organization_id, event_id)
        now = self.now()
        db.execute("UPDATE survey_assignments SET status = 'CLOSED', closed_at = ?, updated_at = ? WHERE id = ?", (now, now, assignment_id))
        self.audit_service.record(db, actor, "surveys.closed", "survey_assignment", assignment_id, {"organization_id": organization_id, "event_id": event_id, "survey_id": assignment["survey_id"]})
        return {"ok": True, "item": self._assignment_payload(self._get_assignment(db, assignment_id, organization_id, event_id))}

    def archive_survey(self, db, *, organization_id: int, event_id: int, survey_id: int, actor: str) -> dict:
        self._get_survey(db, survey_id, organization_id, event_id)
        now = self.now()
        db.execute("UPDATE surveys SET status = 'ARCHIVED', archived_at = ?, updated_at = ? WHERE id = ?", (now, now, survey_id))
        db.execute("UPDATE survey_assignments SET status = 'ARCHIVED', updated_at = ? WHERE survey_id = ?", (now, survey_id))
        self.audit_service.record(db, actor, "surveys.archived", "survey", survey_id, {"organization_id": organization_id, "event_id": event_id})
        return {"ok": True, "item": self._survey_payload(self._get_survey(db, survey_id, organization_id, event_id))}

    def list_surveys(self, db, *, organization_id: int, event_id: int) -> dict:
        rows = db.execute("SELECT * FROM surveys WHERE organization_id = ? AND event_id = ? ORDER BY id", (organization_id, event_id)).fetchall()
        return {"items": [self._survey_payload(row) for row in rows]}

    def get_survey_detail(self, db, *, organization_id: int, event_id: int, survey_id: int) -> dict:
        survey = self._get_survey(db, survey_id, organization_id, event_id)
        versions = db.execute("SELECT * FROM survey_versions WHERE survey_id = ? ORDER BY version_number", (survey_id,)).fetchall()
        assignments = db.execute("SELECT * FROM survey_assignments WHERE survey_id = ? ORDER BY id", (survey_id,)).fetchall()
        return {"survey": self._survey_payload(survey), "versions": [self._version_payload(db, row) for row in versions], "assignments": [self._assignment_payload(row) for row in assignments]}

    def public_access(self, db, *, token: str) -> dict:
        token_hash = self._token_hash(token)
        row = db.execute(
            """
            SELECT sat.*, s.name, s.description, s.response_mode, sa.status AS assignment_status,
                   sv.title, sv.instructions, e.name AS event_name
            FROM survey_access_tokens sat
            JOIN surveys s ON s.id = sat.survey_id
            JOIN survey_assignments sa ON sa.id = sat.assignment_id
            JOIN survey_versions sv ON sv.id = sat.version_id
            JOIN events e ON e.id = sat.event_id
            WHERE sat.token_hash = ?
            """,
            (token_hash,),
        ).fetchone()
        if not row or str(row["status"]) != "ACTIVE":
            return {"ok": True, "valid": False, "status": "invalid"}
        if not self._feature_enabled(db, int(row["organization_id"]), int(row["event_id"])):
            raise SurveyDomainError("SURVEY_FEATURE_DISABLED", "Encuestas V4 deshabilitado", 404)
        assignment = self._get_assignment(db, int(row["assignment_id"]), int(row["organization_id"]), int(row["event_id"]))
        survey = self._get_survey(db, int(row["survey_id"]), int(row["organization_id"]), int(row["event_id"]))
        self._ensure_assignment_open(assignment, survey)
        questions = self._questions_payload(db, int(row["version_id"]))
        return {
            "ok": True,
            "valid": True,
            "survey": {
                "name": row["name"],
                "description": row["description"],
                "title": row["title"],
                "instructions": row["instructions"],
                "event": row["event_name"],
                "response_mode": row["response_mode"],
                "questions": questions,
            },
        }

    def results(self, db, *, organization_id: int, event_id: int, survey_id: int) -> dict:
        survey = self._get_survey(db, survey_id, organization_id, event_id)
        versions = db.execute("SELECT * FROM survey_versions WHERE survey_id = ? ORDER BY version_number, id", (survey_id,)).fetchall()
        version_results = [self._results_for_version(db, survey_id=survey_id, version=version) for version in versions]
        total = sum(int(item["total_responses"]) for item in version_results)
        current_version_id = int(survey["current_version_id"] or 0)
        current = next((item for item in version_results if int(item["version_id"]) == current_version_id), None)
        return {
            "ok": True,
            "total_responses": total,
            "items": current["items"] if current else [],
            "versions": version_results,
        }

    def export_csv(self, db, *, organization_id: int, event_id: int, survey_id: int) -> str:
        survey = self._get_survey(db, survey_id, organization_id, event_id)
        versions = db.execute("SELECT * FROM survey_versions WHERE survey_id = ? ORDER BY version_number, id", (survey_id,)).fetchall()
        questions_by_version = {
            int(version["id"]): db.execute("SELECT * FROM survey_questions WHERE survey_id = ? AND version_id = ? ORDER BY sort_order, id", (survey_id, version["id"])).fetchall()
            for version in versions
        }
        version_numbers = {int(version["id"]): int(version["version_number"]) for version in versions}
        multi_version = len(versions) > 1
        sessions = db.execute("SELECT * FROM survey_response_sessions WHERE survey_id = ? AND status = 'SUBMITTED' ORDER BY id", (survey_id,)).fetchall()
        output = StringIO()
        headers = ["session_id", "submitted_at", "mode", "version"]
        if str(survey["response_mode"]) != "ANONYMOUS":
            headers.append("participant_id")
        for version in versions:
            prefix = f"v{int(version['version_number'])}." if multi_version else ""
            headers.extend([f"{prefix}{str(q['question_key'])}" for q in questions_by_version[int(version["id"])]])
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        for session in sessions:
            session_version_id = int(session["version_id"])
            row = {"session_id": session["id"], "submitted_at": session["submitted_at"], "mode": session["response_mode"], "version": version_numbers.get(session_version_id)}
            if str(survey["response_mode"]) != "ANONYMOUS":
                row["participant_id"] = session["participant_id"]
            answers = self._answers_for_session(db, int(session["id"]))
            for version in versions:
                version_id = int(version["id"])
                prefix = f"v{int(version['version_number'])}." if multi_version else ""
                for question in questions_by_version[version_id]:
                    header = f"{prefix}{str(question['question_key'])}"
                    row[header] = self._csv_safe(answers.get(int(question["id"]), "")) if version_id == session_version_id else ""
            writer.writerow(row)
        return output.getvalue()

    def _results_for_version(self, db, *, survey_id: int, version) -> dict:
        version_id = int(version["id"])
        questions = db.execute("SELECT * FROM survey_questions WHERE survey_id = ? AND version_id = ? ORDER BY sort_order, id", (survey_id, version_id)).fetchall()
        total = int(db.execute("SELECT COUNT(*) AS c FROM survey_response_sessions WHERE survey_id = ? AND version_id = ? AND status = 'SUBMITTED'", (survey_id, version_id)).fetchone()["c"] or 0)
        items = []
        for question in questions:
            qtype = str(question["question_type"])
            base = {"question_id": int(question["id"]), "key": question["question_key"], "prompt": question["prompt"], "type": qtype, "responses": 0}
            if qtype in {"SINGLE_CHOICE", "MULTIPLE_CHOICE"}:
                rows = db.execute(
                    """
                    SELECT sqo.option_key, sqo.label, COUNT(sao.id) AS c
                    FROM survey_question_options sqo
                    LEFT JOIN survey_answer_options sao ON sao.option_id = sqo.id
                    LEFT JOIN survey_response_sessions srs ON srs.id = sao.session_id AND srs.status = 'SUBMITTED' AND srs.version_id = ?
                    WHERE sqo.question_id = ?
                    GROUP BY sqo.id
                    ORDER BY sqo.sort_order, sqo.id
                    """,
                    (version_id, question["id"]),
                ).fetchall()
                dist = []
                response_count = 0
                for row in rows:
                    count = int(row["c"] or 0)
                    response_count += count
                    dist.append({"option_key": row["option_key"], "label": row["label"], "count": count, "percentage": round((count / total) * 100, 2) if total else 0.0})
                base["responses"] = response_count
                base["distribution"] = dist
            elif qtype == "SCALE":
                row = db.execute(
                    """
                    SELECT COUNT(*) AS c, AVG(answer_number) AS avg_value, MIN(answer_number) AS min_value, MAX(answer_number) AS max_value
                    FROM survey_answers sa
                    JOIN survey_response_sessions srs ON srs.id = sa.session_id
                    WHERE sa.question_id = ? AND srs.version_id = ? AND srs.status = 'SUBMITTED'
                    """,
                    (question["id"], version_id),
                ).fetchone()
                base.update({"responses": int(row["c"] or 0), "average": float(row["avg_value"] or 0), "min": row["min_value"], "max": row["max_value"]})
            elif qtype == "YES_NO":
                rows = db.execute(
                    """
                    SELECT answer_bool, COUNT(*) AS c
                    FROM survey_answers sa
                    JOIN survey_response_sessions srs ON srs.id = sa.session_id
                    WHERE sa.question_id = ? AND srs.version_id = ? AND srs.status = 'SUBMITTED'
                    GROUP BY answer_bool
                    """,
                    (question["id"], version_id),
                ).fetchall()
                counts = {str(bool(row["answer_bool"])): int(row["c"] or 0) for row in rows}
                base.update({"responses": sum(counts.values()), "yes": counts.get("True", 0), "no": counts.get("False", 0)})
            else:
                rows = db.execute(
                    """
                    SELECT answer_text
                    FROM survey_answers sa
                    JOIN survey_response_sessions srs ON srs.id = sa.session_id
                    WHERE sa.question_id = ? AND srs.version_id = ? AND srs.status = 'SUBMITTED'
                    ORDER BY sa.id
                    LIMIT 50
                    """,
                    (question["id"], version_id),
                ).fetchall()
                base.update({"responses": len(rows), "items": [row["answer_text"] for row in rows]})
            items.append(base)
        return {"version_id": version_id, "version_number": int(version["version_number"]), "status": version["status"], "total_responses": total, "items": items}

    def _normalize_questions(self, questions: list[dict]) -> list[dict]:
        if not questions or len(questions) > 80:
            raise SurveyDomainError("SURVEY_QUESTIONS_INVALID", "Cantidad de preguntas invalida", 400)
        normalized = []
        seen = set()
        for index, raw in enumerate(questions, start=1):
            key = self._normalize_code(str(raw.get("key") or raw.get("question_key") or f"Q{index}"), "SURVEY_QUESTION_INVALID")
            if key in seen:
                raise SurveyDomainError("SURVEY_QUESTION_INVALID", "Pregunta duplicada", 400)
            seen.add(key)
            qtype = self._normalize_choice(str(raw.get("type") or raw.get("question_type") or ""), SURVEY_QUESTION_TYPES, "SURVEY_QUESTION_INVALID")
            prompt = self._clean_text(str(raw.get("prompt") or ""), 500)
            if not prompt:
                raise SurveyDomainError("SURVEY_QUESTION_INVALID", "Texto de pregunta obligatorio", 400)
            config = raw.get("config") if isinstance(raw.get("config"), dict) else {}
            options = raw.get("options") if isinstance(raw.get("options"), list) else []
            if qtype in {"SINGLE_CHOICE", "MULTIPLE_CHOICE"}:
                if len(options) < 2 or len(options) > 30:
                    raise SurveyDomainError("SURVEY_OPTIONS_INVALID", "Opciones invalidas", 400)
            elif options:
                raise SurveyDomainError("SURVEY_OPTIONS_INVALID", "Este tipo no admite opciones", 400)
            if qtype == "SCALE":
                minimum = int(config.get("min", 1))
                maximum = int(config.get("max", 5))
                if minimum >= maximum or maximum - minimum > 20:
                    raise SurveyDomainError("SURVEY_SCALE_INVALID", "Escala invalida", 400)
                config = {"min": minimum, "max": maximum}
            norm_options = []
            option_seen = set()
            for option_index, option in enumerate(options, start=1):
                option_key = self._normalize_code(str(option.get("key") or f"O{option_index}"), "SURVEY_OPTIONS_INVALID")
                if option_key in option_seen:
                    raise SurveyDomainError("SURVEY_OPTIONS_INVALID", "Opcion duplicada", 400)
                option_seen.add(option_key)
                label = self._clean_text(str(option.get("label") or ""), 250)
                if not label:
                    raise SurveyDomainError("SURVEY_OPTIONS_INVALID", "Etiqueta de opcion obligatoria", 400)
                norm_options.append({"key": option_key, "label": label, "value": self._clean_text(str(option.get("value") or option_key), 250), "sort_order": option_index})
            normalized.append({"key": key, "prompt": prompt, "type": qtype, "required": bool(raw.get("required", False)), "sort_order": int(raw.get("sort_order") or index), "config": config, "options": norm_options})
        return normalized

    def _insert_questions(self, db, organization_id: int, event_id: int, survey_id: int, version_id: int, questions: list[dict]) -> None:
        for question in questions:
            cur = db.execute(
                """
                INSERT INTO survey_questions (
                    version_id, survey_id, organization_id, event_id, question_key,
                    prompt, question_type, required, sort_order, config_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (version_id, survey_id, organization_id, event_id, question["key"], question["prompt"], question["type"], 1 if question["required"] else 0, question["sort_order"], json.dumps(question["config"], ensure_ascii=True, sort_keys=True), self.now()),
            )
            question_id = int(cur.lastrowid)
            for option in question["options"]:
                db.execute(
                    """
                    INSERT INTO survey_question_options (
                        question_id, version_id, survey_id, organization_id, event_id,
                        option_key, label, value, sort_order, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (question_id, version_id, survey_id, organization_id, event_id, option["key"], option["label"], option["value"], option["sort_order"], self.now()),
                )

    def _normalize_answers(self, db, session, answers: list[dict]) -> list[dict]:
        if not isinstance(answers, list) or len(answers) > 100:
            raise SurveyDomainError("SURVEY_ANSWERS_INVALID", "Respuestas invalidas", 400)
        questions = {int(row["id"]): row for row in db.execute("SELECT * FROM survey_questions WHERE version_id = ?", (session["version_id"],)).fetchall()}
        by_question = {}
        for raw in answers:
            question_id = int(raw.get("question_id") or 0)
            if question_id not in questions:
                raise SurveyDomainError("SURVEY_QUESTION_SCOPE_MISMATCH", "Pregunta invalida", 403)
            if question_id in by_question:
                raise SurveyDomainError("SURVEY_ANSWERS_INVALID", "Respuesta duplicada para pregunta", 400)
            by_question[question_id] = raw
        missing = [row["question_key"] for row in questions.values() if int(row["required"] or 0) and int(row["id"]) not in by_question]
        if missing:
            raise SurveyDomainError("SURVEY_REQUIRED_ANSWER_MISSING", "Faltan respuestas obligatorias", 400)
        normalized = []
        for question_id, raw in by_question.items():
            question = questions[question_id]
            qtype = str(question["question_type"])
            value = raw.get("value")
            item = {"question_id": question_id, "type": qtype, "text": None, "number": None, "bool": None, "options": []}
            if qtype == "SHORT_TEXT":
                text = self._clean_text(str(value or ""), 250)
                if int(question["required"] or 0) and not text:
                    raise SurveyDomainError("SURVEY_REQUIRED_ANSWER_MISSING", "Respuesta obligatoria vacia", 400)
                item["text"] = text
            elif qtype == "LONG_TEXT":
                text = self._clean_text(str(value or ""), 4000)
                item["text"] = text
            elif qtype == "SCALE":
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    raise SurveyDomainError("SURVEY_SCALE_INVALID", "Valor de escala invalido", 400)
                config = self._json(question["config_json"])
                if number < float(config.get("min", 1)) or number > float(config.get("max", 5)):
                    raise SurveyDomainError("SURVEY_SCALE_INVALID", "Valor fuera de escala", 400)
                item["number"] = number
            elif qtype == "YES_NO":
                if not isinstance(value, bool):
                    raise SurveyDomainError("SURVEY_BOOLEAN_INVALID", "Valor booleano invalido", 400)
                item["bool"] = value
            elif qtype in {"SINGLE_CHOICE", "MULTIPLE_CHOICE"}:
                option_values = value if isinstance(value, list) else [value]
                if qtype == "SINGLE_CHOICE" and len(option_values) != 1:
                    raise SurveyDomainError("SURVEY_OPTION_INVALID", "Debe seleccionar una opcion", 400)
                if qtype == "MULTIPLE_CHOICE" and (not option_values or len(option_values) > 10 or len(set(option_values)) != len(option_values)):
                    raise SurveyDomainError("SURVEY_OPTION_INVALID", "Seleccion multiple invalida", 400)
                option_rows = db.execute("SELECT * FROM survey_question_options WHERE question_id = ?", (question_id,)).fetchall()
                options_by_key = {row["option_key"]: int(row["id"]) for row in option_rows}
                selected = []
                for option_key in option_values:
                    normalized_key = self._normalize_code(str(option_key or ""), "SURVEY_OPTION_INVALID")
                    if normalized_key not in options_by_key:
                        raise SurveyDomainError("SURVEY_OPTION_INVALID", "Opcion invalida", 400)
                    selected.append(options_by_key[normalized_key])
                item["options"] = selected
            normalized.append(item)
        return normalized

    def _replace_answers(self, db, session, answers: list[dict]) -> None:
        db.execute("DELETE FROM survey_answer_options WHERE session_id = ?", (session["id"],))
        db.execute("DELETE FROM survey_answers WHERE session_id = ?", (session["id"],))
        for answer in answers:
            cur = db.execute(
                """
                INSERT INTO survey_answers (
                    session_id, assignment_id, survey_id, version_id, question_id,
                    organization_id, event_id, answer_text, answer_number, answer_bool, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session["id"], session["assignment_id"], session["survey_id"], session["version_id"], answer["question_id"], session["organization_id"], session["event_id"], answer["text"], answer["number"], 1 if answer["bool"] is True else 0 if answer["bool"] is False else None, self.now()),
            )
            answer_id = int(cur.lastrowid)
            for option_id in answer["options"]:
                db.execute(
                    "INSERT INTO survey_answer_options (answer_id, session_id, option_id, question_id, survey_id, version_id, organization_id, event_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (answer_id, session["id"], option_id, answer["question_id"], session["survey_id"], session["version_id"], session["organization_id"], session["event_id"], self.now()),
                )

    def _answers_for_session(self, db, session_id: int) -> dict[int, str]:
        answers = {}
        for row in db.execute("SELECT * FROM survey_answers WHERE session_id = ?", (session_id,)).fetchall():
            question_id = int(row["question_id"])
            options = db.execute(
                "SELECT sqo.label FROM survey_answer_options sao JOIN survey_question_options sqo ON sqo.id = sao.option_id WHERE sao.answer_id = ? ORDER BY sqo.sort_order",
                (row["id"],),
            ).fetchall()
            if options:
                answers[question_id] = "; ".join(str(option["label"]) for option in options)
            elif row["answer_text"] is not None:
                answers[question_id] = str(row["answer_text"])
            elif row["answer_number"] is not None:
                answers[question_id] = str(row["answer_number"])
            elif row["answer_bool"] is not None:
                answers[question_id] = "si" if int(row["answer_bool"]) else "no"
        return answers

    def _ensure_assignment_open(self, assignment, survey) -> None:
        if str(survey["status"]) == "ARCHIVED" or str(assignment["status"]) != "OPEN":
            raise SurveyDomainError("SURVEY_NOT_OPEN", "Encuesta no disponible", 409)
        now = self.now()
        if assignment["opens_at"] and self._timestamp_gt(str(assignment["opens_at"]), now):
            raise SurveyDomainError("SURVEY_NOT_OPEN_YET", "Encuesta aun no abierta", 409)
        if assignment["closes_at"] and self._timestamp_gt(now, str(assignment["closes_at"])):
            raise SurveyDomainError("SURVEY_CLOSED", "Encuesta cerrada", 409)

    def _questions_payload(self, db, version_id: int) -> list[dict]:
        rows = db.execute("SELECT * FROM survey_questions WHERE version_id = ? ORDER BY sort_order, id", (version_id,)).fetchall()
        return [self._question_payload(db, row) for row in rows]

    def _question_payload(self, db, row) -> dict:
        options = db.execute("SELECT option_key, label, sort_order FROM survey_question_options WHERE question_id = ? ORDER BY sort_order, id", (row["id"],)).fetchall()
        return {"id": int(row["id"]), "key": row["question_key"], "prompt": row["prompt"], "type": row["question_type"], "required": bool(row["required"]), "sort_order": int(row["sort_order"]), "config": self._json(row["config_json"]), "options": [dict(option) for option in options]}

    def _get_type(self, db, type_id: int, organization_id: int):
        row = db.execute("SELECT * FROM survey_types WHERE id = ? AND organization_id = ?", (type_id, organization_id)).fetchone()
        if not row:
            raise SurveyDomainError("SURVEY_TYPE_NOT_FOUND", "Tipo de encuesta inexistente", 404)
        return row

    def _get_survey(self, db, survey_id: int, organization_id: int, event_id: int):
        row = db.execute("SELECT * FROM surveys WHERE id = ? AND organization_id = ? AND event_id = ?", (survey_id, organization_id, event_id)).fetchone()
        if not row:
            raise SurveyDomainError("SURVEY_NOT_FOUND", "Encuesta inexistente", 404)
        return row

    def _get_version(self, db, version_id: int, organization_id: int, survey_id: int | None = None):
        if survey_id is None:
            row = db.execute("SELECT * FROM survey_versions WHERE id = ? AND organization_id = ?", (version_id, organization_id)).fetchone()
        else:
            row = db.execute("SELECT * FROM survey_versions WHERE id = ? AND organization_id = ? AND survey_id = ?", (version_id, organization_id, survey_id)).fetchone()
        if not row:
            raise SurveyDomainError("SURVEY_VERSION_NOT_FOUND", "Version inexistente", 404)
        return row

    def _get_assignment(self, db, assignment_id: int, organization_id: int, event_id: int):
        row = db.execute("SELECT * FROM survey_assignments WHERE id = ? AND organization_id = ? AND event_id = ?", (assignment_id, organization_id, event_id)).fetchone()
        if not row:
            raise SurveyDomainError("SURVEY_ASSIGNMENT_NOT_FOUND", "Asignacion inexistente", 404)
        return row

    def _get_session(self, db, session_id: int, organization_id: int, event_id: int):
        row = db.execute("SELECT * FROM survey_response_sessions WHERE id = ? AND organization_id = ? AND event_id = ?", (session_id, organization_id, event_id)).fetchone()
        if not row:
            raise SurveyDomainError("SURVEY_SESSION_NOT_FOUND", "Sesion inexistente", 404)
        return row

    def _get_token(self, db, organization_id: int, event_id: int, assignment_id: int, token: str):
        token_hash = self._token_hash(str(token or ""))
        row = db.execute("SELECT * FROM survey_access_tokens WHERE organization_id = ? AND event_id = ? AND assignment_id = ? AND token_hash = ?", (organization_id, event_id, assignment_id, token_hash)).fetchone()
        if not row:
            raise SurveyDomainError("SURVEY_TOKEN_INVALID", "Token invalido", 403)
        return row

    def _validate_event(self, db, organization_id: int, event_id: int) -> None:
        row = db.execute("SELECT id FROM events WHERE id = ? AND organization_id = ?", (event_id, organization_id)).fetchone()
        if not row:
            raise SurveyDomainError("SURVEY_SCOPE_MISMATCH", "Evento fuera de alcance", 403)

    def _validate_optional_event(self, db, organization_id: int, event_id: int | None) -> int | None:
        if event_id:
            self._validate_event(db, organization_id, int(event_id))
            return int(event_id)
        return None

    def _validate_activity(self, db, organization_id: int, event_id: int, activity_id: int) -> None:
        row = db.execute("SELECT id FROM activities WHERE id = ? AND event_id = ?", (activity_id, event_id)).fetchone()
        if not row:
            raise SurveyDomainError("SURVEY_SCOPE_MISMATCH", "Actividad fuera de alcance", 403)

    def _validate_participant(self, db, event_id: int, participant_id: int) -> None:
        row = db.execute("SELECT 1 FROM accreditations WHERE event_id = ? AND person_id = ?", (event_id, participant_id)).fetchone()
        if not row:
            raise SurveyDomainError("SURVEY_PARTICIPANT_NOT_ALLOWED", "Participante no habilitado", 403)

    def _ensure_optional_event_matches(self, event_id: int | None, owned_event_id) -> None:
        if owned_event_id is not None and event_id is not None and int(owned_event_id) != int(event_id):
            raise SurveyDomainError("SURVEY_SCOPE_MISMATCH", "Entidad de otro evento", 403)

    def _type_payload(self, row) -> dict:
        return {"id": int(row["id"]), "organization_id": int(row["organization_id"]), "event_id": row["event_id"], "code": row["code"], "name": row["name"], "description": row["description"], "status": row["status"]}

    def _survey_payload(self, row) -> dict:
        return {"id": int(row["id"]), "organization_id": int(row["organization_id"]), "event_id": int(row["event_id"]), "survey_type_id": int(row["survey_type_id"]), "name": row["name"], "description": row["description"], "status": row["status"], "response_mode": row["response_mode"], "access_policy": row["access_policy"], "duplicate_policy": row["duplicate_policy"], "current_version_id": row["current_version_id"], "opens_at": row["opens_at"], "closes_at": row["closes_at"]}

    def _version_payload(self, db, row) -> dict:
        return {"id": int(row["id"]), "survey_id": int(row["survey_id"]), "version_number": int(row["version_number"]), "title": row["title"], "description": row["description"], "instructions": row["instructions"], "content_hash": row["content_hash"], "status": row["status"], "published_at": row["published_at"], "questions": self._questions_payload(db, int(row["id"]))}

    def _assignment_payload(self, row) -> dict:
        return {"id": int(row["id"]), "survey_id": int(row["survey_id"]), "version_id": int(row["version_id"]), "organization_id": int(row["organization_id"]), "event_id": int(row["event_id"]), "activity_id": row["activity_id"], "status": row["status"], "access_mode": row["access_mode"], "opens_at": row["opens_at"], "closes_at": row["closes_at"]}

    def _session_payload(self, row) -> dict:
        payload = {"id": int(row["id"]), "assignment_id": int(row["assignment_id"]), "survey_id": int(row["survey_id"]), "version_id": int(row["version_id"]), "event_id": int(row["event_id"]), "response_mode": row["response_mode"], "status": row["status"], "submitted_at": row["submitted_at"]}
        if str(row["response_mode"]) != "ANONYMOUS":
            payload["participant_id"] = row["participant_id"]
        return payload

    def _normalize_code(self, value: str, code: str) -> str:
        normalized = re.sub(r"[^A-Z0-9_]+", "_", str(value or "").strip().upper()).strip("_")
        if not normalized or len(normalized) > 80:
            raise SurveyDomainError(code, "Codigo invalido", 400)
        return normalized

    def _normalize_choice(self, value: str, allowed: set[str], code: str) -> str:
        normalized = str(value or "").strip().upper()
        if normalized not in allowed:
            raise SurveyDomainError(code, "Valor invalido", 400)
        return normalized

    def _clean_text(self, value: str, limit: int) -> str:
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or "")).strip()
        if len(text) > limit:
            raise SurveyDomainError("SURVEY_TEXT_TOO_LONG", "Texto demasiado extenso", 400)
        if re.search(r"<\s*script|javascript:|data:text/html", text, re.IGNORECASE):
            raise SurveyDomainError("SURVEY_TEXT_UNSAFE", "Contenido no permitido", 400)
        return text

    def _validate_idempotency_key(self, value: str) -> str:
        key = str(value or "").strip()
        if not key:
            key = self.token_factory()
        if len(key) > 160:
            raise SurveyDomainError("SURVEY_IDEMPOTENCY_INVALID", "Clave de idempotencia invalida", 400)
        return key

    def _stable_hash(self, value) -> str:
        return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True, default=str).encode("utf-8")).hexdigest()

    def _token_hash(self, token: str) -> str:
        return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()

    def _anonymous_subject_hash(self, assignment_id: int, value) -> str:
        return hmac.new(self.secret.encode("utf-8"), f"{assignment_id}:{value}".encode("utf-8"), hashlib.sha256).hexdigest()

    def _timestamp_gt(self, left: str, right: str) -> bool:
        return str(left or "") > str(right or "")

    def _json(self, raw: str | None) -> dict:
        try:
            return json.loads(raw or "{}")
        except (TypeError, json.JSONDecodeError):
            return {}

    def _csv_safe(self, value) -> str:
        text = str(value or "")
        if text.startswith(("=", "+", "-", "@")):
            return "'" + text
        return text

    def _feature_enabled(self, db, organization_id: int, event_id: int) -> bool:
        if os.environ.get("BITORA_SURVEYS_V4_ENABLED", "").strip().lower() in {"1", "true", "yes", "si"}:
            return True
        rows = db.execute(
            "SELECT scope_type, scope_id FROM feature_flags WHERE flag_key = 'surveys_v4_enabled' AND enabled = 1"
        ).fetchall()
        for row in rows:
            scope_type = str(row["scope_type"] or "").lower()
            scope_id = int(row["scope_id"] or 0)
            if scope_type == "platform":
                return True
            if scope_type == "organization" and scope_id == organization_id:
                return True
            if scope_type == "event" and scope_id == event_id:
                return True
        return False
