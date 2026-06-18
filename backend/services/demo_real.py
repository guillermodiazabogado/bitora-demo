from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Callable


class DemoRealService:
    EVENT_NAME = "Congreso de Innovacion Neuquen 2027"

    def __init__(
        self,
        now: Callable[[], str],
        make_token: Callable[[], str],
        hash_pin: Callable[[str], str],
    ) -> None:
        self.now = now
        self.make_token = make_token
        self.hash_pin = hash_pin

    def create(self, db: sqlite3.Connection, actor: str) -> dict:
        self._clear_operational_data(db)
        event_id = self._create_event(db)
        self._create_types(db, event_id)
        spaces = self._create_spaces(db, event_id)
        activities = self._create_activities(db, event_id, spaces)
        self._create_bags(db, event_id, activities)
        accreditations = self._create_participants(db, event_id)
        reservation_summary = self._create_reservations(db, event_id, activities, accreditations)
        self._create_display(db, event_id, activities)
        self._create_announcements(db, event_id)
        self._create_communications(db, event_id, accreditations)
        peak_summary = self._simulate_peak_operations(db, event_id, spaces, activities, accreditations)
        examples = self.examples(db, event_id)
        return {
            "event_id": event_id,
            "event_name": self.EVENT_NAME,
            "participants": len(accreditations),
            "spaces": len(spaces),
            "activities": len(activities),
            "reservations": reservation_summary,
            "peak": peak_summary,
            "examples": examples,
            "actor": actor,
        }

    def examples(self, db: sqlite3.Connection, event_id: int) -> list[dict]:
        rows = db.execute(
            """
            SELECT a.id, a.token, a.type, a.status, a.checked_in_at,
                   p.first_name, p.last_name, p.email, p.company
            FROM accreditations a
            JOIN people p ON p.id = a.person_id
            WHERE a.event_id = ? AND a.status <> 'cancelled'
            ORDER BY a.id
            LIMIT 5
            """,
            (event_id,),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "token": row["token"],
                "name": f"{row['first_name']} {row['last_name']}",
                "type": row["type"],
                "email": row["email"],
                "company": row["company"],
                "portal_url": f"/p.html?token={row['token']}",
                "qr_url": f"/api/qr.svg?token={row['token']}",
            }
            for row in rows
        ]

    def guide(self) -> list[str]:
        return [
            "Abrir landing publica.",
            "Inscribir nuevo participante.",
            "Abrir portal.",
            "Inscribirse a una actividad disponible.",
            "Intentar reservar actividad completa.",
            "Entrar en lista de espera.",
            "Cancelar reserva confirmada.",
            "Ver promocion automatica.",
            "Imprimir credencial.",
            "Escanear QR en acceso general.",
            "Escanear QR repetido.",
            "Escanear QR para actividad reservada.",
            "Escanear QR para actividad no reservada.",
            "Ver pantalla publica.",
            "Ver dashboard operativo.",
        ]

    def _clear_operational_data(self, db: sqlite3.Connection) -> None:
        for table in [
            "communication_logs",
            "participant_communication_preferences",
            "participant_announcements",
            "public_display_items",
            "public_display_config",
            "reservations",
            "capacity_bags",
            "activities",
            "spaces",
            "access_logs",
            "accreditations",
            "people",
            "accreditation_types",
            "events",
        ]:
            db.execute(f"DELETE FROM {table}")

    def _create_event(self, db: sqlite3.Connection) -> int:
        start = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        end = start.replace(hour=20)
        cur = db.execute(
            """
            INSERT INTO events (name, description, venue, starts_at, ends_at, status, capacity, activity_selection_mode, created_at)
            VALUES (?, ?, ?, ?, ?, 'published', 1000, 'optional_later', ?)
            """,
            (
                self.EVENT_NAME,
                "Demo realista de operacion integral con acreditaciones, QR, reservas, cupos y comunicaciones demo.",
                "Centro de Convenciones Neuquen",
                start.strftime("%Y-%m-%dT%H:%M"),
                end.strftime("%Y-%m-%dT%H:%M"),
                self.now(),
            ),
        )
        return int(cur.lastrowid)

    def _create_types(self, db: sqlite3.Connection, event_id: int) -> None:
        for name, capacity, enabled in [
            ("General", 480, 1),
            ("VIP", 70, 1),
            ("Prensa", 50, 1),
            ("Staff", 45, 1),
            ("Sponsor", 35, 1),
            ("Disertante", 20, 1),
        ]:
            db.execute(
                """
                INSERT INTO accreditation_types (event_id, name, capacity, access_enabled, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_id, name, capacity, enabled, self.now()),
            )

    def _create_spaces(self, db: sqlite3.Connection, event_id: int) -> dict[str, int]:
        spaces: dict[str, int] = {}
        for name, capacity in [
            ("Auditorio principal", 300),
            ("Sala A", 120),
            ("Sala B", 80),
            ("Sala Workshop", 40),
            ("Sala VIP", 30),
        ]:
            cur = db.execute(
                """
                INSERT INTO spaces (event_id, name, capacity, responsible, transition_minutes, status, created_at)
                VALUES (?, ?, ?, '', 15, 'active', ?)
                """,
                (event_id, name, capacity, self.now()),
            )
            spaces[name] = int(cur.lastrowid)
        return spaces

    def _create_activities(self, db: sqlite3.Connection, event_id: int, spaces: dict[str, int]) -> list[dict]:
        base = datetime.now().replace(second=0, microsecond=0)
        specs = [
            ("Auditorio principal", "Apertura oficial", "charla", -180, 45, 260, "free", "published"),
            ("Auditorio principal", "Panel energia e IA", "panel", -90, 50, 220, "optional", "published"),
            ("Auditorio principal", "Keynote innovacion publica", "charla", 30, 45, 260, "free", "published"),
            ("Auditorio principal", "Demo startups patagonicas", "presentacion comercial", 120, 45, 200, "optional", "published"),
            ("Auditorio principal", "Cierre institucional", "charla", 240, 45, 260, "free", "published"),
            ("Sala A", "Workshop datos abiertos", "workshop", -150, 45, 60, "required", "published"),
            ("Sala A", "Panel ciudades inteligentes", "panel", -45, 45, 80, "optional", "published"),
            ("Sala A", "Charla ciberseguridad", "charla", 60, 45, 80, "required", "published"),
            ("Sala A", "Networking GovTech", "networking", 165, 45, 90, "optional", "published"),
            ("Sala B", "Presentacion comercial cloud", "presentacion comercial", -130, 45, 50, "optional", "published"),
            ("Sala B", "Mesa salud digital", "panel", -25, 45, 70, "required", "published"),
            ("Sala B", "Charla blockchain aplicada", "charla", 80, 45, 70, "optional", "published"),
            ("Sala B", "Actividad demorada: conectividad rural", "charla", 185, 45, 60, "optional", "published"),
            ("Sala Workshop", "Laboratorio IA aplicada", "workshop", -110, 45, 35, "required", "published"),
            ("Sala Workshop", "Taller automatizacion", "workshop", -5, 45, 35, "required", "published"),
            ("Sala Workshop", "Workshop BIM publico", "workshop", 100, 45, 35, "required", "published"),
            ("Sala Workshop", "Actividad cancelada: sensores IoT", "workshop", 205, 45, 35, "required", "cancelled"),
            ("Sala VIP", "Desayuno VIP", "networking", -160, 45, 25, "invited", "published"),
            ("Sala VIP", "Ronda sponsors", "networking", -55, 45, 25, "invited", "published"),
            ("Sala VIP", "Encuentro prensa", "coffee break", 50, 45, 25, "optional", "published"),
        ]
        activities: list[dict] = []
        for idx, (space_name, title, activity_type, offset, duration, capacity, mode, status) in enumerate(specs, start=1):
            start = base + timedelta(minutes=offset)
            end = start + timedelta(minutes=duration)
            cur = db.execute(
                """
                INSERT INTO activities (
                    event_id, space_id, title, description, speaker, activity_type,
                    starts_at, ends_at, capacity, reservation_mode, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    spaces[space_name],
                    title,
                    "Actividad demo V4.0.5",
                    f"Disertante {idx}",
                    activity_type,
                    start.strftime("%Y-%m-%dT%H:%M"),
                    end.strftime("%Y-%m-%dT%H:%M"),
                    capacity,
                    mode,
                    status,
                    self.now(),
                ),
            )
            activities.append({"id": int(cur.lastrowid), "title": title, "capacity": capacity, "status": status, "mode": mode})
        return activities

    def _create_bags(self, db: sqlite3.Connection, event_id: int, activities: list[dict]) -> None:
        bag_codes = [
            ("Online", "online", 10, 1, 1, 1),
            ("Mostrador", "mostrador", 20, 0, 0, 1),
            ("Empresas", "empresas", 30, 0, 0, 1),
            ("Invitaciones", "invitaciones", 40, 0, 0, 1),
            ("Sponsors", "sponsors", 50, 0, 0, 1),
            ("Prensa", "prensa", 60, 0, 0, 1),
            ("Backup operativo", "backup_operativo", 90, 0, 0, 1),
        ]
        for idx, activity in enumerate(activities):
            if activity["status"] == "cancelled":
                online_capacity = 0
            elif idx % 5 == 0:
                online_capacity = max(1, int(activity["capacity"] * 0.3))
            elif idx % 5 == 1:
                online_capacity = max(1, int(activity["capacity"] * 0.7))
            elif idx % 5 == 2:
                online_capacity = max(1, int(activity["capacity"] * 0.95))
            else:
                online_capacity = max(1, min(activity["capacity"], 25))
            for name, code, priority, visible, public_registration, reception in bag_codes:
                assigned = online_capacity if code == "online" else 0
                db.execute(
                    """
                    INSERT INTO capacity_bags (
                        event_id, activity_id, name, code, assigned_capacity, priority,
                        public_visible, public_registration, reception_enabled, release_enabled, status, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'active', ?)
                    """,
                    (event_id, activity["id"], name, code, assigned, priority, visible, public_registration, reception, self.now()),
                )

    def _create_participants(self, db: sqlite3.Connection, event_id: int) -> list[dict]:
        first_names = ["Ana", "Luis", "Marta", "Diego", "Sofia", "Carlos", "Valeria", "Pablo", "Lucia", "Jorge"]
        last_names = ["Perez", "Gomez", "Diaz", "Rojas", "Silva", "Farias", "Mendez", "Arias", "Castro", "Vega"]
        types = ["General"] * 700 + ["VIP"] * 120 + ["Prensa"] * 80 + ["Staff"] * 50 + ["Sponsor"] * 35 + ["Disertante"] * 15
        accreditations: list[dict] = []
        for i in range(1000):
            first = first_names[i % len(first_names)]
            last = f"{last_names[(i // len(first_names)) % len(last_names)]} {i + 1:03d}"
            email = f"participante{i + 1:03d}@demo.local"
            phone = f"549299{1000000 + i:07d}"
            cur = db.execute(
                """
                INSERT INTO people (first_name, last_name, email, phone, dni, company, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (first, last, email, phone, f"900{i + 1:05d}", f"Empresa Demo {i % 35 + 1} - Cargo Demo", self.now()),
            )
            person_id = int(cur.lastrowid)
            token = self._unique_token(db)
            acc_type = types[i]
            status = "cancelled" if i % 31 == 0 else "active"
            checked_in_at = None
            checked_in_by = None
            cur = db.execute(
                """
                INSERT INTO accreditations (event_id, person_id, type, token, status, checked_in_at, checked_in_by, access_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (event_id, person_id, acc_type, token, status, checked_in_at, checked_in_by, 1 if checked_in_at else 0, self.now()),
            )
            accreditation_id = int(cur.lastrowid)
            acepta_email = 1 if i % 7 != 0 else 0
            acepta_whatsapp = 1 if i % 5 != 0 else 0
            db.execute(
                """
                INSERT INTO participant_communication_preferences (
                    person_id, email, phone, acepta_email, acepta_whatsapp,
                    canal_preferido, fecha_consentimiento, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (person_id, email, phone, acepta_email, acepta_whatsapp, "whatsapp" if acepta_whatsapp else "email", self.now(), self.now()),
            )
            accreditations.append({"id": accreditation_id, "person_id": person_id, "token": token, "status": status})
        return accreditations

    def _create_reservations(self, db: sqlite3.Connection, event_id: int, activities: list[dict], accreditations: list[dict]) -> dict:
        active = [row for row in accreditations if row["status"] != "cancelled"]
        cursor = 0
        confirmed = 0
        waitlisted = 0
        for idx, activity in enumerate([a for a in activities if a["status"] != "cancelled"]):
            online_bag = db.execute("SELECT * FROM capacity_bags WHERE activity_id = ? AND code = 'online'", (activity["id"],)).fetchone()
            assigned = int(online_bag["assigned_capacity"] or 0)
            if idx % 6 == 0:
                confirmed_target = max(1, int(assigned * 0.3))
                wait_target = 0
            elif idx % 6 == 1:
                confirmed_target = max(1, int(assigned * 0.7))
                wait_target = 0
            elif idx % 6 == 2:
                confirmed_target = max(1, int(assigned * 0.95))
                wait_target = 0
            elif idx % 6 == 3:
                confirmed_target = assigned
                wait_target = 0
            else:
                confirmed_target = assigned
                wait_target = 5
            for status, amount in [("confirmed", confirmed_target), ("waitlisted", wait_target)]:
                for _ in range(amount):
                    acc = active[cursor % len(active)]
                    cursor += 1
                    db.execute(
                        """
                        INSERT OR IGNORE INTO reservations (event_id, activity_id, bag_id, accreditation_id, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (event_id, activity["id"], online_bag["id"] if status == "confirmed" else None, acc["id"], status, self.now()),
                    )
                    if status == "confirmed":
                        confirmed += 1
                    else:
                        waitlisted += 1
        return {"confirmed": confirmed, "waitlisted": waitlisted}

    def _create_display(self, db: sqlite3.Connection, event_id: int, activities: list[dict]) -> None:
        db.execute(
            """
            INSERT INTO public_display_config (event_id, mode, refresh_seconds, paused, message, room_filter, status_filter, updated_at)
            VALUES (?, 'airport', 10, 0, 'Bienvenidos al Congreso de Innovacion Neuquen 2027', '', '', ?)
            """,
            (event_id, self.now()),
        )
        for order, activity in enumerate([row for row in activities if row["status"] != "cancelled"][:14]):
            db.execute(
                """
                INSERT INTO public_display_items (event_id, activity_id, sort_order, visible, created_at)
                VALUES (?, ?, ?, 1, ?)
                """,
                (event_id, activity["id"], order, self.now()),
            )

    def _create_announcements(self, db: sqlite3.Connection, event_id: int) -> None:
        for title, content in [
            ("Cambio operativo demo", "La actividad de conectividad rural figura demorada."),
            ("Credenciales", "Recorda tener tu QR listo en el acceso."),
            ("Networking", "La ronda de sponsors abre cupos de mostrador durante el dia."),
        ]:
            db.execute(
                "INSERT INTO participant_announcements (event_id, title, content, status, created_at) VALUES (?, ?, ?, 'published', ?)",
                (event_id, title, content, self.now()),
            )

    def _create_communications(self, db: sqlite3.Connection, event_id: int, accreditations: list[dict]) -> None:
        for acc in accreditations[:60]:
            db.execute(
                """
                INSERT INTO communication_logs (event_id, person_id, accreditation_id, canal, fecha, tipo, asunto, contenido, estado)
                VALUES (?, ?, ?, ?, ?, 'confirmacion', 'Inscripcion confirmada', 'Comunicacion demo registrada', 'demo')
                """,
                (event_id, acc["person_id"], acc["id"], "email" if acc["id"] % 2 else "whatsapp", self.now()),
            )

    def _simulate_peak_operations(
        self,
        db: sqlite3.Connection,
        event_id: int,
        spaces: dict[str, int],
        activities: list[dict],
        accreditations: list[dict],
    ) -> dict:
        active = [row for row in accreditations if row["status"] != "cancelled"]
        entered = active[:650]
        operators = [f"Terminal QR {idx:02d}" for idx in range(1, 31)]
        now = datetime.now(timezone.utc).replace(microsecond=0)
        access_times: list[datetime] = []

        windows = [
            (400, now - timedelta(hours=3, minutes=30), now - timedelta(minutes=61)),
            (130, now - timedelta(minutes=60), now - timedelta(minutes=16)),
            (120, now - timedelta(minutes=10), now - timedelta(seconds=20)),
        ]
        for amount, start, end in windows:
            span_seconds = max(1, int((end - start).total_seconds()))
            for index in range(amount):
                ratio = index / max(amount - 1, 1)
                curve = ratio * ratio
                access_times.append(start + timedelta(seconds=int(span_seconds * curve)))
        access_times.sort()

        for index, (acc, stamp) in enumerate(zip(entered, access_times)):
            operator = operators[index % len(operators)]
            stamp_iso = self._iso_at(stamp)
            db.execute(
                """
                UPDATE accreditations
                SET checked_in_at = ?, checked_in_by = ?, access_count = 1
                WHERE id = ?
                """,
                (stamp_iso, operator, acc["id"]),
            )
            db.execute(
                """
                INSERT INTO access_logs (
                    accreditation_id, event_id, activity_id, token, operator,
                    checkpoint, access_point, access_context, result, reason, created_at
                )
                VALUES (?, ?, NULL, ?, ?, ?, ?, 'event_entry', 'granted', 'Acceso concedido', ?)
                """,
                (acc["id"], event_id, acc["token"], operator, f"Acceso {index % 10 + 1}", operator, stamp_iso),
            )

        rejection_reasons = [
            "QR repetido",
            "QR anticipado",
            "Sin inscripcion a actividad",
            "Acreditacion cancelada",
            "Sala incorrecta",
            "QR invalido",
        ]
        for index in range(20):
            acc = active[(650 + index) % len(active)]
            stamp = now - timedelta(minutes=14) + timedelta(seconds=index * 40)
            reason = rejection_reasons[index % len(rejection_reasons)]
            token = acc["token"] if reason != "QR invalido" else f"QR-INVALIDO-{index:02d}"
            db.execute(
                """
                INSERT INTO access_logs (
                    accreditation_id, event_id, activity_id, token, operator,
                    checkpoint, access_point, access_context, result, reason, created_at
                )
                VALUES (?, ?, NULL, ?, ?, ?, ?, 'event_entry', 'rejected', ?, ?)
                """,
                (
                    acc["id"] if reason != "QR invalido" else None,
                    event_id,
                    token,
                    operators[index % len(operators)],
                    f"Acceso {index % 10 + 1}",
                    operators[index % len(operators)],
                    reason,
                    self._iso_at(stamp),
                ),
            )

        public_activities = [row for row in activities if row["status"] != "cancelled"]
        attendance_targets = [260, 95, 32, 22, 0, 18]
        cursor = 0
        attendance_total = 0
        for activity, target in zip(public_activities, attendance_targets):
            capacity = int(activity["capacity"] or 0)
            target = min(target, capacity, len(active) - cursor)
            for _ in range(max(0, target)):
                acc = active[cursor % len(active)]
                cursor += 1
                reservation = db.execute(
                    "SELECT id FROM reservations WHERE activity_id = ? AND accreditation_id = ? LIMIT 1",
                    (activity["id"], acc["id"]),
                ).fetchone()
                stamp = now - timedelta(minutes=25, seconds=cursor * 3)
                db.execute(
                    """
                    INSERT OR IGNORE INTO activity_attendance (
                        event_id, activity_id, accreditation_id, reservation_id,
                        entry_at, entry_operator, exit_at, exit_operator,
                        attended_minutes, attendance_percentage, status,
                        eligibility_status, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, NULL, '', 45, 100, 'Completa', 'Elegible', ?, ?)
                    """,
                    (
                        event_id,
                        activity["id"],
                        acc["id"],
                        reservation["id"] if reservation else None,
                        self._iso_at(stamp),
                        operators[cursor % len(operators)],
                        self._iso_at(stamp),
                        self._iso_at(stamp),
                    ),
                )
                db.execute(
                    """
                    INSERT OR IGNORE INTO certificate_eligibility (
                        event_id, activity_id, accreditation_id, porcentaje,
                        elegible, estado, fecha_calculo, certificate_generated_at
                    )
                    VALUES (?, ?, ?, 100, 1, 'Elegible', ?, ?)
                    """,
                    (event_id, activity["id"], acc["id"], self._iso_at(stamp), self._iso_at(now)),
                )
                attendance_total += 1

        for title, content in [
            ("Pico operativo activo", "Ingreso alto en los ultimos 15 minutos con multiples terminales."),
            ("Terminal a revisar", "Terminal QR 27 sin confirmacion manual de supervisor."),
            ("Rechazos QR elevados", "Se detectaron rechazos mezclados con accesos validos durante el pico."),
        ]:
            db.execute(
                "INSERT INTO participant_announcements (event_id, title, content, status, created_at) VALUES (?, ?, ?, 'published', ?)",
                (event_id, title, content, self._iso_at(now)),
            )

        return {
            "entered": len(entered),
            "last_60_minutes": 250,
            "last_15_minutes": 120,
            "active_terminals": len(operators),
            "recent_rejections": 20,
            "attendance_records": attendance_total,
        }

    def _unique_token(self, db: sqlite3.Connection) -> str:
        token = self.make_token()
        while db.execute("SELECT 1 FROM accreditations WHERE token = ?", (token,)).fetchone():
            token = self.make_token()
        return token

    @staticmethod
    def _iso_at(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat(timespec="seconds")
