from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta
from typing import Any, Callable


DEMO_ORGANIZATION = "BITORA Demo"
DEMO_EVENT = "BITORA Demo Full 2026"
DEMO_RUN_ID = "DEMO-FULL-V4-0-4"


DEMO_USERS = [
    ("superadmin-demo-online", "Super Admin", "Super Admin Demo"),
    ("coordinador-demo-online", "Coordinador", "Coordinador Demo"),
    ("productor-demo-online", "Productor", "Productor Demo"),
    ("recepcion-demo-online", "Operador de recepcion", "Recepcion Demo"),
    ("acceso-demo-online", "Operador de acceso", "Acceso Demo"),
    ("visualizador-demo-online", "Visualizador", "Visualizador Demo"),
    ("comunicaciones-demo-online", "Comunicaciones", "Comunicaciones Demo"),
    ("soporte-demo-online", "Soporte tecnico", "Soporte Demo"),
]

DEMO_FLAGS = [
    "attendance_v4_enabled",
    "attendance_closure_eligibility_v4_enabled",
    "certificates_v4_enabled",
    "surveys_v4_enabled",
    "speakers_v4_enabled",
    "operations_center_v4_enabled",
    "communications_v4_enabled",
    "communications_automation_v4_enabled",
    "analytics_v4_enabled",
]


def demo_password() -> str:
    left = secrets.choice(["Demo", "Bito", "Vivo", "Full"])
    middle = secrets.choice(["Azul", "Verde", "Claro", "Norte"])
    number = secrets.randbelow(89) + 10
    symbol = secrets.choice(["!", "#", "_", "%"])
    return f"{left}{middle}{number}{symbol}"


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def clean_phone(index: int) -> str:
    return f"54911004{index:05d}"


def row_dict(row: Any) -> dict[str, Any]:
    return dict(row) if row else {}


class DemoFullService:
    def __init__(
        self,
        *,
        now: Callable[[], str],
        hash_pin: Callable[[str], str],
        make_public_id: Callable[[str], str],
        public_link: Callable[[str], str],
    ) -> None:
        self.now = now
        self.hash_pin = hash_pin
        self.make_public_id = make_public_id
        self.public_link = public_link

    def prepare(self, db: Any, *, actor: str = "demo-full") -> dict[str, Any]:
        now = self.now()
        passwords: dict[str, str] = {}
        org_id = self.ensure_organization(db, now)
        event_id = self.ensure_event(db, org_id, now)
        self.ensure_flags(db, org_id, event_id, now, actor)
        users = self.ensure_users(db, org_id, event_id, now, passwords)
        spaces = self.ensure_spaces(db, event_id, now)
        activities = self.ensure_activities(db, event_id, spaces, now)
        participants = self.ensure_participants(db, event_id, activities, now)
        speakers = self.ensure_speakers(db, org_id, event_id, activities, now)
        surveys = self.ensure_surveys(db, org_id, event_id, participants, now)
        notifications = self.ensure_notifications(db, event_id, participants, now)
        self.ensure_communications(db, org_id, event_id, participants, now)
        self.ensure_operations(db, org_id, event_id, now)
        self.ensure_audit(db, event_id, actor, now)
        participant = participants[0]
        return {
            "ok": True,
            "run_id": DEMO_RUN_ID,
            "organization": {"id": org_id, "name": DEMO_ORGANIZATION},
            "event": {"id": event_id, "name": DEMO_EVENT},
            "users": [
                {"username": username, "role": role, "password": passwords[username]}
                for username, role, _full_name in DEMO_USERS
            ],
            "participant": {
                "name": f"{participant['first_name']} {participant['last_name']}",
                "email": participant["email"],
                "portal_url": self.public_link(f"/p.html?token={participant['token']}"),
            },
            "counts": self.counts(db, org_id, event_id),
            "safe_mode": "ON",
            "live_mode": "OFF",
            "real_whatsapp": 0,
            "real_email": 0,
            "real_personal_data": 0,
        }

    def ensure_organization(self, db: Any, now: str) -> int:
        public_id = "org-bitora-demo"
        db.execute(
            """
            INSERT INTO organizations (
                public_id, name, legal_name, trade_name, contact_email, status, plan,
                safe_mode_email, safe_mode_whatsapp, force_email_recipient, force_whatsapp_recipient,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'demo@bitora.test', 'active', 'standard', 1, 1, 'demo@bitora.test', '5491100000000', ?, ?)
            ON CONFLICT(public_id) DO UPDATE SET
                name = excluded.name,
                legal_name = excluded.legal_name,
                trade_name = excluded.trade_name,
                status = 'active',
                safe_mode_email = 1,
                safe_mode_whatsapp = 1,
                force_email_recipient = 'demo@bitora.test',
                force_whatsapp_recipient = '5491100000000',
                updated_at = excluded.updated_at
            """,
            (public_id, DEMO_ORGANIZATION, DEMO_ORGANIZATION, DEMO_ORGANIZATION, now, now),
        )
        return int(db.execute("SELECT id FROM organizations WHERE public_id = ?", (public_id,)).fetchone()["id"])

    def ensure_event(self, db: Any, org_id: int, now: str) -> int:
        starts = datetime(2026, 9, 15, 9, 0)
        ends = starts + timedelta(hours=9)
        row = db.execute(
            "SELECT id FROM events WHERE organization_id = ? AND name = ?",
            (org_id, DEMO_EVENT),
        ).fetchone()
        if row:
            event_id = int(row["id"])
            db.execute(
                """
                UPDATE events
                SET description = ?, venue = ?, starts_at = ?, ends_at = ?, status = 'published',
                    project_type = 'conference', capacity = 120, activities_enabled = 1,
                    capacity_control_enabled = 1, waitlist_enabled = 1
                WHERE id = ?
                """,
                (
                    "DEMO / DATOS FICTICIOS - evento integral para mostrar BITORA de punta a punta.",
                    "Centro de Convenciones Demo",
                    starts.isoformat(),
                    ends.isoformat(),
                    event_id,
                ),
            )
            return event_id
        cur = db.execute(
            """
            INSERT INTO events (
                organization_id, name, description, venue, starts_at, ends_at, status, project_type,
                capacity, activities_enabled, capacity_control_enabled, waitlist_enabled, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'published', 'conference', 120, 1, 1, 1, ?)
            """,
            (
                org_id,
                DEMO_EVENT,
                "DEMO / DATOS FICTICIOS - evento integral para mostrar BITORA de punta a punta.",
                "Centro de Convenciones Demo",
                starts.isoformat(),
                ends.isoformat(),
                now,
            ),
        )
        return int(cur.lastrowid)

    def ensure_flags(self, db: Any, org_id: int, event_id: int, now: str, actor: str) -> None:
        for flag in DEMO_FLAGS:
            db.execute(
                """
                INSERT INTO feature_flags (flag_key, scope_type, scope_id, enabled, updated_by, updated_at)
                VALUES (?, 'event', ?, 1, ?, ?)
                ON CONFLICT(flag_key, scope_type, scope_id)
                DO UPDATE SET enabled = 1, updated_by = excluded.updated_by, updated_at = excluded.updated_at
                """,
                (flag, event_id, actor, now),
            )
        for flag in ("communications_v4_enabled", "analytics_v4_enabled"):
            db.execute(
                """
                INSERT INTO feature_flags (flag_key, scope_type, scope_id, enabled, updated_by, updated_at)
                VALUES (?, 'organization', ?, 1, ?, ?)
                ON CONFLICT(flag_key, scope_type, scope_id)
                DO UPDATE SET enabled = 1, updated_by = excluded.updated_by, updated_at = excluded.updated_at
                """,
                (flag, org_id, actor, now),
            )

    def ensure_users(self, db: Any, org_id: int, event_id: int, now: str, passwords: dict[str, str]) -> list[dict[str, Any]]:
        users: list[dict[str, Any]] = []
        for username, role, full_name in DEMO_USERS:
            password = demo_password()
            passwords[username] = password
            db.execute(
                """
                INSERT INTO users (name, role, pin_hash, email, full_name, must_change_password, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 0, 1, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    role = excluded.role,
                    pin_hash = excluded.pin_hash,
                    email = excluded.email,
                    full_name = excluded.full_name,
                    must_change_password = 0,
                    active = 1,
                    updated_at = excluded.updated_at,
                    disabled_at = NULL
                """,
                (username, role, self.hash_pin(password), f"{username}@bitora.test", full_name, now, now),
            )
            user_id = int(db.execute("SELECT id FROM users WHERE name = ?", (username,)).fetchone()["id"])
            org_role = "organization_owner" if role == "Super Admin" else "organization_admin" if role in {"Productor", "Coordinador"} else "viewer"
            db.execute(
                """
                INSERT INTO organization_users (organization_id, user_id, role, status, accepted_at, created_at, updated_at)
                VALUES (?, ?, ?, 'active', ?, ?, ?)
                ON CONFLICT(organization_id, user_id) DO UPDATE SET
                    role = excluded.role,
                    status = 'active',
                    accepted_at = excluded.accepted_at,
                    updated_at = excluded.updated_at
                """,
                (org_id, user_id, org_role, now, now, now),
            )
            db.execute(
                """
                INSERT INTO user_event_roles (user_id, event_id, role, active, created_at)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(user_id, event_id) DO UPDATE SET role = excluded.role, active = 1
                """,
                (user_id, event_id, role, now),
            )
            users.append({"id": user_id, "username": username, "role": role})
        return users

    def ensure_spaces(self, db: Any, event_id: int, now: str) -> list[int]:
        spaces = [("Auditorio Principal", 120), ("Sala Norte", 60), ("Sala Sur", 50)]
        ids: list[int] = []
        for name, capacity in spaces:
            db.execute(
                """
                INSERT INTO spaces (event_id, name, capacity, responsible, status, created_at)
                VALUES (?, ?, ?, 'Equipo Demo', 'active', ?)
                ON CONFLICT(event_id, name) DO UPDATE SET capacity = excluded.capacity, responsible = excluded.responsible, status = 'active'
                """,
                (event_id, name, capacity, now),
            )
            ids.append(int(db.execute("SELECT id FROM spaces WHERE event_id = ? AND name = ?", (event_id, name)).fetchone()["id"]))
        return ids

    def ensure_activities(self, db: Any, event_id: int, spaces: list[int], now: str) -> list[dict[str, Any]]:
        base = datetime(2026, 9, 15, 9, 0)
        rows = [
            ("Apertura del evento", 0, 45, spaces[0], "Plenaria", 120),
            ("Inteligencia Artificial aplicada a eventos", 60, 60, spaces[0], "Charla", 90),
            ("Experiencias inmersivas", 150, 50, spaces[1], "Workshop", 45),
            ("Marketing y tecnologia", 240, 60, spaces[2], "Charla", 50),
            ("Operacion de acreditaciones en vivo", 330, 50, spaces[1], "Demo", 40),
            ("Analytics para decisiones del evento", 420, 50, spaces[2], "Charla", 50),
            ("Comunicaciones seguras en Safe Mode", 500, 45, spaces[1], "Demo", 40),
            ("Cierre y certificados", 570, 45, spaces[0], "Plenaria", 120),
        ]
        out: list[dict[str, Any]] = []
        for title, offset, duration, space_id, activity_type, capacity in rows:
            starts = base + timedelta(minutes=offset)
            ends = starts + timedelta(minutes=duration)
            row = db.execute("SELECT id FROM activities WHERE event_id = ? AND title = ?", (event_id, title)).fetchone()
            if row:
                db.execute(
                    """
                    UPDATE activities
                    SET space_id = ?, description = 'DEMO / DATOS FICTICIOS', speaker = '',
                        activity_type = ?, starts_at = ?, ends_at = ?, capacity = ?,
                        reservation_mode = 'free', status = 'published'
                    WHERE id = ?
                    """,
                    (space_id, activity_type, starts.isoformat(), ends.isoformat(), capacity, int(row["id"])),
                )
            else:
                db.execute(
                    """
                    INSERT INTO activities (
                        event_id, space_id, title, description, speaker, activity_type,
                        starts_at, ends_at, capacity, reservation_mode, status, created_at
                    )
                    VALUES (?, ?, ?, 'DEMO / DATOS FICTICIOS', '', ?, ?, ?, ?, 'free', 'published', ?)
                    """,
                    (event_id, space_id, title, activity_type, starts.isoformat(), ends.isoformat(), capacity, now),
                )
            row = db.execute("SELECT * FROM activities WHERE event_id = ? AND title = ?", (event_id, title)).fetchone()
            out.append(row_dict(row))
        return out

    def ensure_participants(self, db: Any, event_id: int, activities: list[dict[str, Any]], now: str) -> list[dict[str, Any]]:
        names = [
            ("Juan", "Demo"), ("Ana", "Demo"), ("Carlos", "Ejemplo"), ("Lucia", "Prueba"),
            ("Martin", "Muestra"), ("Sofia", "Test"), ("Valentina", "Ficticia"), ("Diego", "Ensayo"),
        ]
        participants: list[dict[str, Any]] = []
        for index in range(52):
            first, last = names[index % len(names)]
            first_name = first if index == 0 else f"{first}{index:02d}"
            email = "juan.demo@bitora.test" if index == 0 else f"participante{index:02d}.demo@bitora.test"
            db.execute(
                """
                INSERT INTO people (first_name, last_name, email, phone, dni, company, position, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    phone = excluded.phone,
                    dni = excluded.dni,
                    company = excluded.company,
                    position = excluded.position
                """,
                (first_name, last, email, clean_phone(index), f"900{index:05d}", "Empresa Demo", "Visitante Demo", now),
            )
            person_id = int(db.execute("SELECT id FROM people WHERE email = ?", (email,)).fetchone()["id"])
            token = f"DEMO-FULL-2026-{index:03d}-{token_hash(email)[:10]}"
            db.execute(
                """
                INSERT INTO accreditations (event_id, person_id, type, token, status, checked_in_at, checked_in_by, created_at)
                VALUES (?, ?, 'General Demo', ?, 'active', ?, ?, ?)
                ON CONFLICT(event_id, person_id) DO UPDATE SET
                    type = excluded.type,
                    token = excluded.token,
                    status = 'active',
                    checked_in_at = excluded.checked_in_at,
                    checked_in_by = excluded.checked_in_by
                """,
                (event_id, person_id, token, now if index < 18 else None, "Recepcion Demo" if index < 18 else "", now),
            )
            acc = row_dict(db.execute("SELECT * FROM accreditations WHERE event_id = ? AND person_id = ?", (event_id, person_id)).fetchone())
            db.execute(
                """
                INSERT INTO participant_communication_preferences (
                    person_id, email, phone, acepta_email, acepta_whatsapp, canal_preferido, fecha_consentimiento, updated_at
                )
                VALUES (?, ?, ?, 1, 1, 'email', ?, ?)
                ON CONFLICT(person_id) DO UPDATE SET
                    email = excluded.email,
                    phone = excluded.phone,
                    acepta_email = 1,
                    acepta_whatsapp = 1,
                    canal_preferido = 'email',
                    updated_at = excluded.updated_at
                """,
                (person_id, email, clean_phone(index), now, now),
            )
            for activity in activities[: 2 + (index % 3)]:
                status = "waitlisted" if index % 11 == 0 and activity == activities[2] else "confirmed"
                db.execute(
                    """
                    INSERT INTO reservations (event_id, activity_id, accreditation_id, status, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(activity_id, accreditation_id) DO UPDATE SET status = excluded.status
                    """,
                    (event_id, int(activity["id"]), int(acc["id"]), status, now),
                )
                reservation = db.execute(
                    "SELECT id FROM reservations WHERE activity_id = ? AND accreditation_id = ?",
                    (int(activity["id"]), int(acc["id"])),
                ).fetchone()
                if index < 24 and status == "confirmed":
                    pct = 100 if index % 4 else 55
                    eligibility = "Elegible" if pct >= 70 else "No elegible"
                    db.execute(
                        """
                        INSERT INTO activity_attendance (
                            event_id, activity_id, accreditation_id, reservation_id,
                            entry_at, entry_operator, exit_at, exit_operator, attended_minutes,
                            attendance_percentage, status, eligibility_status, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, 'Acceso Demo', ?, 'Acceso Demo', ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(activity_id, accreditation_id) DO UPDATE SET
                            reservation_id = excluded.reservation_id,
                            entry_at = excluded.entry_at,
                            exit_at = excluded.exit_at,
                            attended_minutes = excluded.attended_minutes,
                            attendance_percentage = excluded.attendance_percentage,
                            status = excluded.status,
                            eligibility_status = excluded.eligibility_status,
                            updated_at = excluded.updated_at
                        """,
                        (
                            event_id,
                            int(activity["id"]),
                            int(acc["id"]),
                            int(reservation["id"]) if reservation else None,
                            now,
                            now,
                            50,
                            pct,
                            "Presente" if pct >= 70 else "Parcial",
                            eligibility,
                            now,
                            now,
                        ),
                    )
                    db.execute(
                        """
                        INSERT INTO certificate_eligibility (
                            event_id, activity_id, accreditation_id, porcentaje, elegible,
                            estado, fecha_calculo, certificate_generated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(activity_id, accreditation_id) DO UPDATE SET
                            porcentaje = excluded.porcentaje,
                            elegible = excluded.elegible,
                            estado = excluded.estado,
                            fecha_calculo = excluded.fecha_calculo,
                            certificate_generated_at = excluded.certificate_generated_at
                        """,
                        (
                            event_id,
                            int(activity["id"]),
                            int(acc["id"]),
                            pct,
                            1 if pct >= 70 else 0,
                            eligibility,
                            now,
                            now if pct >= 70 and index < 8 else None,
                        ),
                    )
            participant = row_dict(db.execute(
                """
                SELECT p.*, a.id AS accreditation_id, a.token
                FROM people p JOIN accreditations a ON a.person_id = p.id
                WHERE a.event_id = ? AND p.email = ?
                """,
                (event_id, email),
            ).fetchone())
            participants.append(participant)
        return participants

    def ensure_speakers(self, db: Any, org_id: int, event_id: int, activities: list[dict[str, Any]], now: str) -> int:
        speakers = [
            ("oradora-ana-demo", "Ana Demo", "Especialista en experiencias digitales"),
            ("orador-carlos-ejemplo", "Carlos Ejemplo", "Consultor en operaciones de eventos"),
            ("oradora-lucia-prueba", "Lucia Prueba", "Investigadora en analitica aplicada"),
            ("orador-martin-muestra", "Martin Muestra", "Productor tecnico"),
            ("oradora-sofia-test", "Sofia Test", "Disenadora de comunicaciones"),
        ]
        count = 0
        for idx, (public_id, display, title) in enumerate(speakers):
            db.execute(
                """
                INSERT INTO speaker_profiles (
                    organization_id, public_id, display_name, first_name, last_name, title,
                    company, short_bio, status, visibility, created_by, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 'Demo', ?, 'BITORA Demo', 'Perfil ficticio para demo full.', 'PUBLISHED', 'EVENT', 'demo-full', ?, ?)
                ON CONFLICT(organization_id, public_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    title = excluded.title,
                    status = 'PUBLISHED',
                    visibility = 'EVENT',
                    updated_at = excluded.updated_at
                """,
                (org_id, public_id, display, display.split()[0], title, now, now),
            )
            profile_id = int(db.execute("SELECT id FROM speaker_profiles WHERE organization_id = ? AND public_id = ?", (org_id, public_id)).fetchone()["id"])
            db.execute(
                """
                INSERT INTO speaker_event_assignments (organization_id, event_id, speaker_profile_id, roles_json, status, visibility, created_by, created_at, updated_at)
                VALUES (?, ?, ?, '["SPEAKER"]', 'CONFIRMED', 'PUBLIC', 'demo-full', ?, ?)
                ON CONFLICT(organization_id, event_id, speaker_profile_id) DO UPDATE SET status = 'CONFIRMED', visibility = 'PUBLIC', updated_at = excluded.updated_at
                """,
                (org_id, event_id, profile_id, now, now),
            )
            activity = activities[idx % len(activities)]
            db.execute(
                """
                INSERT INTO speaker_activity_assignments (organization_id, event_id, activity_id, speaker_profile_id, role, status, visibility, sort_order, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'SPEAKER', 'CONFIRMED', 'PUBLIC', ?, 'demo-full', ?, ?)
                ON CONFLICT(organization_id, event_id, activity_id, speaker_profile_id, role)
                DO UPDATE SET status = 'CONFIRMED', visibility = 'PUBLIC', sort_order = excluded.sort_order, updated_at = excluded.updated_at
                """,
                (org_id, event_id, int(activity["id"]), profile_id, idx, now, now),
            )
            count += 1
        return count

    def ensure_surveys(self, db: Any, org_id: int, event_id: int, participants: list[dict[str, Any]], now: str) -> int:
        count = 0
        for code, name in [("general", "Evaluacion general del evento"), ("actividad", "Evaluacion de actividad")]:
            db.execute(
                """
                INSERT INTO survey_types (organization_id, event_id, code, name, description, status, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'DEMO / DATOS FICTICIOS', 'ACTIVE', 'demo-full', ?, ?)
                ON CONFLICT(organization_id, event_id, code) DO UPDATE SET name = excluded.name, status = 'ACTIVE', updated_at = excluded.updated_at
                """,
                (org_id, event_id, code, name, now, now),
            )
            type_id = int(db.execute("SELECT id FROM survey_types WHERE organization_id = ? AND event_id = ? AND code = ?", (org_id, event_id, code)).fetchone()["id"])
            db.execute(
                """
                INSERT INTO surveys (organization_id, event_id, survey_type_id, name, description, status, response_mode, access_policy, duplicate_policy, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'Encuesta ficticia para demo full.', 'PUBLISHED', 'IDENTIFIED', 'EVENT_PARTICIPANTS', 'ONE_PER_PARTICIPANT', 'demo-full', ?, ?)
                ON CONFLICT(organization_id, event_id, name) DO UPDATE SET status = 'PUBLISHED', updated_at = excluded.updated_at
                """,
                (org_id, event_id, type_id, name, now, now),
            )
            survey_id = int(db.execute("SELECT id FROM surveys WHERE organization_id = ? AND event_id = ? AND name = ?", (org_id, event_id, name)).fetchone()["id"])
            content_hash = token_hash(f"{DEMO_RUN_ID}:{survey_id}:{code}")
            db.execute(
                """
                INSERT INTO survey_versions (survey_id, organization_id, event_id, version_number, title, description, instructions, content_hash, status, published_at, published_by, created_by, idempotency_key, created_at, updated_at)
                VALUES (?, ?, ?, 1, ?, 'Version demo publicada.', 'Responder con datos ficticios.', ?, 'PUBLISHED', ?, 'demo-full', 'demo-full', ?, ?, ?)
                ON CONFLICT(survey_id, version_number) DO UPDATE SET status = 'PUBLISHED', published_at = excluded.published_at, updated_at = excluded.updated_at
                """,
                (survey_id, org_id, event_id, name, content_hash, now, f"{DEMO_RUN_ID}-{code}-v1", now, now),
            )
            version_id = int(db.execute("SELECT id FROM survey_versions WHERE survey_id = ? AND version_number = 1", (survey_id,)).fetchone()["id"])
            db.execute("UPDATE surveys SET current_version_id = ? WHERE id = ?", (version_id, survey_id))
            for q_index, prompt in enumerate(["Valoracion general", "Comentario demo"]):
                qtype = "rating" if q_index == 0 else "text"
                qkey = f"q{q_index + 1}"
                db.execute(
                    """
                    INSERT INTO survey_questions (version_id, survey_id, organization_id, event_id, question_key, prompt, question_type, required, sort_order, config_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, '{}', ?)
                    ON CONFLICT(version_id, question_key) DO UPDATE SET prompt = excluded.prompt, question_type = excluded.question_type
                    """,
                    (version_id, survey_id, org_id, event_id, qkey, prompt, qtype, q_index, now),
                )
            assignment = db.execute(
                """
                SELECT id FROM survey_assignments
                WHERE survey_id = ? AND version_id = ? AND organization_id = ? AND event_id = ?
                ORDER BY id
                """,
                (survey_id, version_id, org_id, event_id),
            ).fetchone()
            if assignment:
                assignment_id = int(assignment["id"])
                db.execute(
                    """
                    UPDATE survey_assignments
                    SET status = 'PUBLISHED', access_mode = 'EVENT_PARTICIPANTS', updated_at = ?
                    WHERE id = ?
                    """,
                    (now, assignment_id),
                )
            else:
                cur = db.execute(
                    """
                    INSERT INTO survey_assignments (survey_id, version_id, organization_id, event_id, status, access_mode, created_by, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'PUBLISHED', 'EVENT_PARTICIPANTS', 'demo-full', ?, ?)
                    """,
                    (survey_id, version_id, org_id, event_id, now, now),
                )
                assignment_id = int(cur.lastrowid)
            questions = db.execute("SELECT id, question_type FROM survey_questions WHERE version_id = ? ORDER BY sort_order", (version_id,)).fetchall()
            for participant in participants[:12]:
                idem = f"{DEMO_RUN_ID}-{code}-{participant['id']}"
                db.execute(
                    """
                    INSERT INTO survey_response_sessions (assignment_id, survey_id, version_id, organization_id, event_id, response_mode, participant_id, status, started_at, submitted_at, idempotency_key, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'IDENTIFIED', ?, 'SUBMITTED', ?, ?, ?, ?, ?)
                    ON CONFLICT(organization_id, idempotency_key) DO UPDATE SET status = 'SUBMITTED', submitted_at = excluded.submitted_at, updated_at = excluded.updated_at
                    """,
                    (assignment_id, survey_id, version_id, org_id, event_id, int(participant["id"]), now, now, idem, now, now),
                )
                session_id = int(db.execute("SELECT id FROM survey_response_sessions WHERE organization_id = ? AND idempotency_key = ?", (org_id, idem)).fetchone()["id"])
                for question in questions:
                    db.execute(
                        """
                        INSERT INTO survey_answers (session_id, assignment_id, survey_id, version_id, question_id, organization_id, event_id, answer_text, answer_number, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(session_id, question_id) DO UPDATE SET answer_text = excluded.answer_text, answer_number = excluded.answer_number
                        """,
                        (
                            session_id,
                            assignment_id,
                            survey_id,
                            version_id,
                            int(question["id"]),
                            org_id,
                            event_id,
                            "Respuesta demo positiva" if question["question_type"] != "rating" else None,
                            4.5 if question["question_type"] == "rating" else None,
                            now,
                        ),
                    )
            count += 1
        return count

    def ensure_notifications(self, db: Any, event_id: int, participants: list[dict[str, Any]], now: str) -> int:
        titles = [
            ("Bienvenida", "Bienvenido a BITORA Demo Full 2026."),
            ("Reserva confirmada", "Tus charlas demo quedaron reservadas."),
            ("Cambio de sala", "Marketing y tecnologia pasa a Sala Sur."),
            ("Actividad por comenzar", "Tenes una actividad demo por comenzar."),
            ("Encuesta disponible", "Ya podes completar la encuesta demo."),
            ("Certificado disponible", "Tu certificado demo esta disponible."),
        ]
        demo_titles = [title for title, _content in titles]
        placeholders = ",".join("?" for _title in demo_titles)
        db.execute(
            f"DELETE FROM participant_announcements WHERE event_id = ? AND title IN ({placeholders})",
            (event_id, *demo_titles),
        )
        for title, content in titles:
            db.execute(
                "INSERT INTO participant_announcements (event_id, title, content, status, created_at) VALUES (?, ?, ?, 'published', ?)",
                (event_id, title, content, now),
            )
        db.execute(
            "DELETE FROM communication_logs WHERE event_id = ? AND tipo = 'demo' AND asunto = 'Mensaje demo Safe Mode'",
            (event_id,),
        )
        for participant in participants[:10]:
            db.execute(
                """
                INSERT INTO communication_logs (event_id, person_id, accreditation_id, canal, fecha, tipo, asunto, contenido, estado)
                VALUES (?, ?, ?, 'email', ?, 'demo', 'Mensaje demo Safe Mode', 'DEMO / sin envio real', 'demo')
                """,
                (event_id, int(participant["id"]), int(participant["accreditation_id"]), now),
            )
        return len(titles)

    def ensure_communications(self, db: Any, org_id: int, event_id: int, participants: list[dict[str, Any]], now: str) -> None:
        integration = db.execute(
            "SELECT id FROM organization_integrations WHERE organization_id = ? AND name = 'Email Demo Safe Mode'",
            (org_id,),
        ).fetchone()
        if integration:
            integration_id = int(integration["id"])
            db.execute(
                """
                UPDATE organization_integrations
                SET provider = 'demo', integration_type = 'email_provider', mode = 'platform_managed',
                    status = 'connected', configuration_encrypted = '',
                    metadata_json = '{"safe_mode":true}', updated_by = 'demo-full', updated_at = ?
                WHERE id = ?
                """,
                (now, integration_id),
            )
        else:
            cur = db.execute(
                """
                INSERT INTO organization_integrations (
                    organization_id, provider, integration_type, name, mode, status,
                    configuration_encrypted, metadata_json, created_by, updated_by, created_at, updated_at
                )
                VALUES (?, 'demo', 'email_provider', 'Email Demo Safe Mode', 'platform_managed', 'connected', '', '{"safe_mode":true}', 'demo-full', 'demo-full', ?, ?)
                """,
                (org_id, now, now),
            )
            integration_id = int(cur.lastrowid)
        db.execute(
            """
            INSERT INTO event_integrations (event_id, channel, organization_integration_id, is_default, enabled, created_at, updated_at)
            VALUES (?, 'email', ?, 1, 1, ?, ?)
            ON CONFLICT(event_id, channel) DO UPDATE SET organization_integration_id = excluded.organization_integration_id, enabled = 1, updated_at = excluded.updated_at
            """,
            (event_id, integration_id, now, now),
        )
        first = participants[0]
        idempotency_key = f"{DEMO_RUN_ID}-communication-safe-mode"
        queued = db.execute("SELECT id FROM communication_queue WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
        if queued:
            db.execute(
                """
                UPDATE communication_queue
                SET event_id = ?, organization_id = ?, integration_id = ?, person_id = ?,
                    accreditation_id = ?, channel = 'email', audience = 'demo_full',
                    template_code = 'demo_full', subject = 'BITORA DEMO FULL',
                    content = 'DEMO / Safe Mode / no envio real', recipient = 'demo@bitora.test',
                    status = 'demo', provider = 'demo', provider_message_id = 'demo-full-local'
                WHERE id = ?
                """,
                (event_id, org_id, integration_id, int(first["id"]), int(first["accreditation_id"]), int(queued["id"])),
            )
        else:
            db.execute(
                """
                INSERT INTO communication_queue (
                    event_id, organization_id, integration_id, person_id, accreditation_id,
                    channel, audience, template_code, subject, content, recipient, status,
                    provider, provider_message_id, idempotency_key, created_by, created_at
                )
                VALUES (?, ?, ?, ?, ?, 'email', 'demo_full', 'demo_full', 'BITORA DEMO FULL', 'DEMO / Safe Mode / no envio real', 'demo@bitora.test', 'demo',
                        'demo', 'demo-full-local', ?, 'demo-full', ?)
                """,
                (event_id, org_id, integration_id, int(first["id"]), int(first["accreditation_id"]), idempotency_key, now),
            )

    def ensure_operations(self, db: Any, org_id: int, event_id: int, now: str) -> None:
        db.execute(
            """
            INSERT INTO operations_center_alerts (
                organization_id, event_id, alert_type, severity, status, source,
                dedupe_key, message, entity_type, entity_id, correlation_id, created_at, actor
            )
            VALUES (?, ?, 'DEMO_FULL', 'LOW', 'OPEN', 'demo-full', ?, 'Demo Full lista con datos ficticios.', 'event', ?, ?, ?, 'demo-full')
            ON CONFLICT(organization_id, event_id, dedupe_key, status) DO NOTHING
            """,
            (org_id, event_id, f"{DEMO_RUN_ID}-ready", event_id, DEMO_RUN_ID, now),
        )

    def ensure_audit(self, db: Any, event_id: int, actor: str, now: str) -> None:
        db.execute(
            "INSERT INTO audit_logs (event_id, actor, action, entity_type, entity_id, payload, created_at) VALUES (?, ?, 'demo_full.prepared', 'event', ?, ?, ?)",
            (event_id, actor, event_id, json.dumps({"run_id": DEMO_RUN_ID, "real_sends": 0}), now),
        )

    def counts(self, db: Any, org_id: int, event_id: int) -> dict[str, int]:
        def count(sql: str, params: tuple[Any, ...]) -> int:
            return int(db.execute(sql, params).fetchone()["c"] or 0)

        return {
            "users": count("SELECT COUNT(*) AS c FROM user_event_roles WHERE event_id = ? AND active = 1", (event_id,)),
            "participants": count("SELECT COUNT(*) AS c FROM accreditations WHERE event_id = ? AND status = 'active'", (event_id,)),
            "activities": count("SELECT COUNT(*) AS c FROM activities WHERE event_id = ? AND status = 'published'", (event_id,)),
            "speakers": count("SELECT COUNT(*) AS c FROM speaker_event_assignments WHERE organization_id = ? AND event_id = ?", (org_id, event_id)),
            "surveys": count("SELECT COUNT(*) AS c FROM surveys WHERE organization_id = ? AND event_id = ? AND status = 'PUBLISHED'", (org_id, event_id)),
            "notifications": count("SELECT COUNT(*) AS c FROM participant_announcements WHERE event_id = ? AND status = 'published'", (event_id,)),
            "certificates": count("SELECT COUNT(*) AS c FROM certificate_eligibility WHERE event_id = ? AND certificate_generated_at IS NOT NULL", (event_id,)),
            "real_email": count("SELECT COUNT(*) AS c FROM communication_queue WHERE event_id = ? AND provider <> 'demo'", (event_id,)),
            "real_whatsapp": count("SELECT COUNT(*) AS c FROM communication_queue WHERE event_id = ? AND channel = 'whatsapp' AND provider <> 'demo'", (event_id,)),
        }

    def verify(self, db: Any) -> dict[str, Any]:
        org = db.execute("SELECT id, name, safe_mode_email, safe_mode_whatsapp FROM organizations WHERE public_id = 'org-bitora-demo'").fetchone()
        if not org:
            return {"ok": False, "score": "0/10", "error": "Organizacion demo inexistente"}
        event = db.execute("SELECT id, name, status FROM events WHERE organization_id = ? AND name = ?", (int(org["id"]), DEMO_EVENT)).fetchone()
        if not event:
            return {"ok": False, "score": "1/10", "error": "Evento demo inexistente"}
        event_id = int(event["id"])
        counts = self.counts(db, int(org["id"]), event_id)
        checks = {
            "organization_demo": org["name"] == DEMO_ORGANIZATION,
            "event_demo": event["name"] == DEMO_EVENT and event["status"] == "published",
            "safe_mode": int(org["safe_mode_email"] or 0) == 1 and int(org["safe_mode_whatsapp"] or 0) == 1,
            "demo_users": counts["users"] >= 8,
            "participants": counts["participants"] >= 40,
            "activities": counts["activities"] >= 6,
            "speakers": counts["speakers"] >= 4,
            "surveys": counts["surveys"] >= 2,
            "notifications": counts["notifications"] >= 6,
            "certificates": counts["certificates"] >= 1,
            "real_communications_zero": counts["real_email"] == 0 and counts["real_whatsapp"] == 0,
        }
        passed = sum(1 for value in checks.values() if value)
        total = len(checks)
        participant = db.execute(
            """
            SELECT p.first_name, p.last_name, p.email, a.token
            FROM people p JOIN accreditations a ON a.person_id = p.id
            WHERE a.event_id = ? AND p.email = 'juan.demo@bitora.test'
            """,
            (event_id,),
        ).fetchone()
        return {
            "ok": passed == total,
            "score": f"{passed}/{total}",
            "checks": checks,
            "organization": {"id": int(org["id"]), "name": org["name"]},
            "event": {"id": event_id, "name": event["name"]},
            "counts": counts,
            "participant": {
                "name": f"{participant['first_name']} {participant['last_name']}" if participant else "",
                "email": participant["email"] if participant else "",
                "portal_url": self.public_link(f"/p.html?token={participant['token']}") if participant else "",
            },
        }
