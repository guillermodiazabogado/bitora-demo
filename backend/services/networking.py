from __future__ import annotations

import hashlib
import json
import re
import secrets
from collections.abc import Callable
from urllib.parse import quote


FUNCTIONS = {
    "EXECUTIVE",
    "COMMERCIAL",
    "PROCUREMENT",
    "BUSINESS_DEVELOPMENT",
    "TECHNOLOGY",
    "OPERATIONS",
    "MARKETING",
    "FINANCE",
    "HUMAN_RESOURCES",
    "INSTITUTIONAL",
    "PROFESSIONAL_TECHNICAL",
    "OTHER",
}
SENIORITIES = {"EXECUTIVE", "MANAGEMENT", "PROFESSIONAL", "OPERATIONAL"}
MODES = {"COMMERCIAL", "BUSINESS_ALLIANCES", "SERVICES_SOLUTIONS"}
DIRECTIONS = {"SEEKING", "OFFERING", "BOTH"}
CONTACT_OPENNESS = {"DIRECT", "CONNECT_FIRST", "CORPORATE_ROUTE"}
CHANNEL_TYPES = {"whatsapp", "phone", "email", "website", "instagram", "linkedin", "facebook", "tiktok", "x", "youtube", "other"}
CHANNEL_VISIBILITY = {"PUBLIC", "CONTACTS", "HIDDEN"}


def networking_schema_sql() -> str:
    return """
    CREATE TABLE IF NOT EXISTS networking_organizations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        canonical_key TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        website TEXT NOT NULL DEFAULT '',
        logo_url TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        visibility TEXT NOT NULL DEFAULT 'VISIBLE',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS networking_event_participations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
        accreditation_id INTEGER REFERENCES accreditations(id) ON DELETE SET NULL,
        organization_id INTEGER REFERENCES networking_organizations(id) ON DELETE SET NULL,
        source_system TEXT NOT NULL DEFAULT 'BITORA',
        source_external_id TEXT NOT NULL DEFAULT '',
        source_fingerprint TEXT NOT NULL DEFAULT '',
        participation_state TEXT NOT NULL DEFAULT 'PASSIVE',
        public_profile_id TEXT NOT NULL UNIQUE,
        owner_token_hash TEXT NOT NULL DEFAULT '',
        owner_token_hint TEXT NOT NULL DEFAULT '',
        title TEXT NOT NULL DEFAULT '',
        normalized_function TEXT NOT NULL DEFAULT 'OTHER',
        normalized_seniority TEXT NOT NULL DEFAULT 'PROFESSIONAL',
        profile_photo_url TEXT NOT NULL DEFAULT '',
        organization_logo_url TEXT NOT NULL DEFAULT '',
        source_payload_json TEXT NOT NULL DEFAULT '{}',
        imported_at TEXT NOT NULL DEFAULT '',
        onboarded_at TEXT,
        revoked_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(event_id, person_id),
        UNIQUE(event_id, source_system, source_external_id)
    );

    CREATE TABLE IF NOT EXISTS networking_intents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        participation_id INTEGER NOT NULL UNIQUE REFERENCES networking_event_participations(id) ON DELETE CASCADE,
        modes_json TEXT NOT NULL DEFAULT '[]',
        direction TEXT NOT NULL DEFAULT 'BOTH',
        contact_openness TEXT NOT NULL DEFAULT 'CONNECT_FIRST',
        discoverable INTEGER NOT NULL DEFAULT 0,
        profile_visible INTEGER NOT NULL DEFAULT 0,
        channels_visible_default TEXT NOT NULL DEFAULT 'CONTACTS',
        representative_visible INTEGER NOT NULL DEFAULT 1,
        bio TEXT NOT NULL DEFAULT '',
        offers_text TEXT NOT NULL DEFAULT '',
        seeks_text TEXT NOT NULL DEFAULT '',
        interests_text TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS networking_contact_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        participation_id INTEGER NOT NULL REFERENCES networking_event_participations(id) ON DELETE CASCADE,
        channel_type TEXT NOT NULL,
        label TEXT NOT NULL DEFAULT '',
        value TEXT NOT NULL,
        url TEXT NOT NULL DEFAULT '',
        visibility TEXT NOT NULL DEFAULT 'CONTACTS',
        source TEXT NOT NULL DEFAULT 'import',
        updated_at TEXT NOT NULL,
        UNIQUE(participation_id, channel_type, value)
    );

    CREATE TABLE IF NOT EXISTS networking_taxonomy_concepts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        concept_type TEXT NOT NULL,
        label TEXT NOT NULL,
        taxonomy_version TEXT NOT NULL DEFAULT 'v1',
        active INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS networking_classifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        participation_id INTEGER NOT NULL REFERENCES networking_event_participations(id) ON DELETE CASCADE,
        concept_code TEXT NOT NULL REFERENCES networking_taxonomy_concepts(code) ON DELETE RESTRICT,
        source TEXT NOT NULL DEFAULT 'declared',
        provenance TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        UNIQUE(participation_id, concept_code, source)
    );

    CREATE TABLE IF NOT EXISTS networking_contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        owner_participation_id INTEGER NOT NULL REFERENCES networking_event_participations(id) ON DELETE CASCADE,
        target_participation_id INTEGER NOT NULL REFERENCES networking_event_participations(id) ON DELETE CASCADE,
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(owner_participation_id, target_participation_id)
    );

    CREATE TABLE IF NOT EXISTS networking_interaction_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        actor_participation_id INTEGER REFERENCES networking_event_participations(id) ON DELETE SET NULL,
        target_participation_id INTEGER REFERENCES networking_event_participations(id) ON DELETE SET NULL,
        event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_networking_participations_event_state ON networking_event_participations(event_id, participation_state);
    CREATE INDEX IF NOT EXISTS idx_networking_participations_public ON networking_event_participations(public_profile_id);
    CREATE INDEX IF NOT EXISTS idx_networking_channels_participation ON networking_contact_channels(participation_id);
    CREATE INDEX IF NOT EXISTS idx_networking_contacts_owner ON networking_contacts(owner_participation_id, status);
    """


class NetworkingService:
    def __init__(self, now: Callable[[], str]) -> None:
        self.now = now

    def ensure_schema(self, db) -> None:
        db.executescript(networking_schema_sql())
        self.ensure_taxonomy(db)

    def ensure_taxonomy(self, db) -> None:
        for code in sorted(FUNCTIONS):
            db.execute(
                "INSERT OR IGNORE INTO networking_taxonomy_concepts (code, concept_type, label, taxonomy_version, active) VALUES (?, 'function', ?, 'v1', 1)",
                (f"FUNCTION_{code}", code.replace("_", " ").title()),
            )
        for code in sorted(SENIORITIES):
            db.execute(
                "INSERT OR IGNORE INTO networking_taxonomy_concepts (code, concept_type, label, taxonomy_version, active) VALUES (?, 'seniority', ?, 'v1', 1)",
                (f"SENIORITY_{code}", code.replace("_", " ").title()),
            )

    def preview_import(self, db, event_id: int, rows: list[dict], source_system: str = "external") -> dict:
        event = db.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            return {"ok": False, "error": "Evento inexistente", "status_code": 404}
        summary = {"valid": 0, "errors": 0, "existing": 0, "rows": []}
        for index, row in enumerate(rows, start=1):
            item, error = self._normalize_import_row(row, source_system)
            if error:
                summary["errors"] += 1
                summary["rows"].append({"row": index, "ok": False, "error": error})
                continue
            existing = self._find_existing_participation(db, event_id, item)
            summary["valid"] += 1
            summary["existing"] += 1 if existing else 0
            summary["rows"].append({"row": index, "ok": True, "email": item["email"], "existing": bool(existing)})
        return {"ok": summary["errors"] == 0, **summary}

    def import_profiles(self, db, event_id: int, rows: list[dict], source_system: str = "external", actor: str = "system") -> dict:
        preview = self.preview_import(db, event_id, rows, source_system)
        if not preview.get("ok"):
            return preview
        summary = {"created": 0, "updated": 0, "errors": 0, "rows": []}
        for index, row in enumerate(rows, start=1):
            item, error = self._normalize_import_row(row, source_system)
            if error:
                summary["errors"] += 1
                summary["rows"].append({"row": index, "ok": False, "error": error})
                continue
            result = self.upsert_participation(db, event_id, item, actor=actor, activate=False)
            summary["created"] += 1 if result["created"] else 0
            summary["updated"] += 0 if result["created"] else 1
            summary["rows"].append({"row": index, "ok": True, "participation_id": result["participation_id"], "state": result["state"], "created": result["created"]})
        self.record_event(db, event_id, None, None, "import", {"actor": actor, "source_system": source_system, "summary": summary})
        return {"ok": summary["errors"] == 0, **summary}

    def external_register(self, db, event_id: int, data: dict) -> dict:
        event = db.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            return {"ok": False, "error": "Evento inexistente", "status_code": 404}
        item, error = self._normalize_import_row(data, "external_form")
        if error:
            return {"ok": False, "error": error, "status_code": 400}
        result = self.upsert_participation(db, event_id, item, actor="public", activate=False, issue_owner_token=True)
        participation = self.get_participation(db, result["participation_id"])
        return {
            "ok": True,
            "participation_id": result["participation_id"],
            "state": participation["participation_state"],
            "owner_token": result.get("owner_token", ""),
            "access_url": f"/networking.html?token={quote(result.get('owner_token') or '')}" if result.get("owner_token") else "",
        }

    def upsert_participation(self, db, event_id: int, item: dict, *, actor: str, activate: bool = False, issue_owner_token: bool = False) -> dict:
        person_id = self._upsert_person(db, item)
        organization_id = self._upsert_networking_org(db, item)
        accreditation = db.execute("SELECT * FROM accreditations WHERE event_id = ? AND person_id = ?", (event_id, person_id)).fetchone()
        existing = self._find_existing_participation(db, event_id, item, person_id=person_id)
        now = self.now()
        public_profile_id = existing["public_profile_id"] if existing else self._new_public_profile_id(db)
        owner_token = ""
        owner_hash = existing["owner_token_hash"] if existing else ""
        owner_hint = existing["owner_token_hint"] if existing else ""
        if issue_owner_token and not owner_hash:
            owner_token = self._new_owner_token()
            owner_hash = self._hash_token(owner_token)
            owner_hint = owner_token[-6:]
        source_payload = self._safe_json(item)
        if existing:
            db.execute(
                """
                UPDATE networking_event_participations
                SET accreditation_id = COALESCE(?, accreditation_id),
                    organization_id = ?,
                    source_fingerprint = ?,
                    title = ?,
                    normalized_function = ?,
                    normalized_seniority = ?,
                    profile_photo_url = ?,
                    organization_logo_url = ?,
                    source_payload_json = ?,
                    imported_at = ?,
                    owner_token_hash = COALESCE(NULLIF(owner_token_hash, ''), ?),
                    owner_token_hint = COALESCE(NULLIF(owner_token_hint, ''), ?),
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    accreditation["id"] if accreditation else None,
                    organization_id,
                    self._fingerprint(item),
                    item["title"],
                    item["function"],
                    item["seniority"],
                    item["photo_url"],
                    item["organization_logo_url"],
                    source_payload,
                    now,
                    owner_hash,
                    owner_hint,
                    now,
                    existing["id"],
                ),
            )
            participation_id = int(existing["id"])
            created = False
        else:
            cur = db.execute(
                """
                INSERT INTO networking_event_participations (
                    event_id, person_id, accreditation_id, organization_id, source_system, source_external_id,
                    source_fingerprint, participation_state, public_profile_id, owner_token_hash, owner_token_hint,
                    title, normalized_function, normalized_seniority, profile_photo_url, organization_logo_url,
                    source_payload_json, imported_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    person_id,
                    accreditation["id"] if accreditation else None,
                    organization_id,
                    item["source_system"],
                    item["source_external_id"],
                    self._fingerprint(item),
                    "ACTIVE" if activate else "PASSIVE",
                    public_profile_id,
                    owner_hash,
                    owner_hint,
                    item["title"],
                    item["function"],
                    item["seniority"],
                    item["photo_url"],
                    item["organization_logo_url"],
                    source_payload,
                    now,
                    now,
                    now,
                ),
            )
            participation_id = int(cur.lastrowid)
            created = True
            db.execute(
                """
                INSERT INTO networking_intents (participation_id, bio, offers_text, seeks_text, interests_text, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (participation_id, item["bio"], item["offers"], item["seeks"], item["interests"], now),
            )
        self._upsert_channels(db, participation_id, item, preserve_user_visibility=not created)
        self._upsert_classification(db, participation_id, f"FUNCTION_{item['function']}", "import")
        self._upsert_classification(db, participation_id, f"SENIORITY_{item['seniority']}", "import")
        self.record_event(db, event_id, participation_id, None, "profile_imported", {"actor": actor, "source_system": item["source_system"], "created": created})
        return {"ok": True, "participation_id": participation_id, "created": created, "state": "ACTIVE" if activate else (existing["participation_state"] if existing else "PASSIVE"), "owner_token": owner_token}

    def onboard(self, db, owner_token: str, data: dict) -> dict:
        participation = self.resolve_owner(db, owner_token, int(data.get("event_id") or 0) or None)
        if not participation:
            return {"ok": False, "error": "Acceso Networking invalido", "status_code": 404}
        modes = self._normalize_modes(data.get("modes") or data.get("networking_modes") or [])
        direction = self._choice(data.get("direction"), DIRECTIONS, "BOTH")
        openness = self._choice(data.get("contact_openness"), CONTACT_OPENNESS, "CONNECT_FIRST")
        now = self.now()
        db.execute(
            """
            UPDATE networking_intents
            SET modes_json = ?, direction = ?, contact_openness = ?, discoverable = 1,
                profile_visible = 1, channels_visible_default = ?, representative_visible = ?,
                bio = COALESCE(NULLIF(?, ''), bio),
                offers_text = COALESCE(NULLIF(?, ''), offers_text),
                seeks_text = COALESCE(NULLIF(?, ''), seeks_text),
                interests_text = COALESCE(NULLIF(?, ''), interests_text),
                updated_at = ?
            WHERE participation_id = ?
            """,
            (
                json.dumps(modes),
                direction,
                openness,
                self._choice(data.get("channels_visible_default"), CHANNEL_VISIBILITY, "CONTACTS"),
                1 if self._truthy(data.get("representative_visible", True)) else 0,
                str(data.get("bio") or "").strip(),
                str(data.get("offers") or data.get("offers_text") or "").strip(),
                str(data.get("seeks") or data.get("seeks_text") or "").strip(),
                str(data.get("interests") or data.get("interests_text") or "").strip(),
                now,
                participation["id"],
            ),
        )
        db.execute(
            """
            UPDATE networking_event_participations
            SET participation_state = 'ACTIVE',
                normalized_function = ?,
                normalized_seniority = ?,
                title = COALESCE(NULLIF(?, ''), title),
                onboarded_at = COALESCE(onboarded_at, ?),
                updated_at = ?
            WHERE id = ?
            """,
            (
                self._choice(data.get("function"), FUNCTIONS, participation["normalized_function"]),
                self._choice(data.get("seniority"), SENIORITIES, participation["normalized_seniority"]),
                str(data.get("title") or "").strip(),
                now,
                now,
                participation["id"],
            ),
        )
        self._apply_channel_visibility_updates(db, int(participation["id"]), data.get("channel_visibility") or {})
        self.record_event(db, int(participation["event_id"]), int(participation["id"]), None, "onboarded", {"modes": modes, "direction": direction, "contact_openness": openness})
        return {"ok": True, "participation": self.participation_payload(db, int(participation["id"]), viewer_id=int(participation["id"]), full=True)}

    def session(self, db, owner_token: str, event_id: int | None = None) -> dict:
        participation = self.resolve_owner(db, owner_token, event_id)
        if not participation:
            return {"ok": False, "error": "Acceso Networking invalido", "status_code": 404}
        return {"ok": True, "participation": self.participation_payload(db, int(participation["id"]), viewer_id=int(participation["id"]), full=True)}

    def scan(self, db, owner_token: str, public_profile_id: str) -> dict:
        owner = self.resolve_owner(db, owner_token)
        if not owner:
            return {"ok": False, "error": "Acceso Networking invalido", "status_code": 404}
        if owner["participation_state"] != "ACTIVE":
            return {"ok": False, "error": "Completa el onboarding antes de escanear", "status_code": 409}
        target = db.execute("SELECT * FROM networking_event_participations WHERE public_profile_id = ?", (str(public_profile_id or "").strip(),)).fetchone()
        if not target or int(target["event_id"]) != int(owner["event_id"]):
            return {"ok": False, "error": "Perfil Networking inexistente", "status_code": 404}
        if int(target["id"]) == int(owner["id"]):
            return {"ok": False, "error": "No podes agregarte a vos mismo", "status_code": 409}
        if target["participation_state"] != "ACTIVE":
            return {"ok": False, "error": "El perfil todavia no esta activo en Networking", "status_code": 409}
        now = self.now()
        existing = db.execute(
            "SELECT * FROM networking_contacts WHERE owner_participation_id = ? AND target_participation_id = ?",
            (owner["id"], target["id"]),
        ).fetchone()
        created = False
        if existing:
            db.execute("UPDATE networking_contacts SET status = 'ACTIVE', updated_at = ? WHERE id = ?", (now, existing["id"]))
            contact_id = int(existing["id"])
        else:
            contact_id = int(db.execute(
                """
                INSERT INTO networking_contacts (event_id, owner_participation_id, target_participation_id, status, created_at, updated_at)
                VALUES (?, ?, ?, 'ACTIVE', ?, ?)
                """,
                (owner["event_id"], owner["id"], target["id"], now, now),
            ).lastrowid)
            created = True
        self.record_event(db, int(owner["event_id"]), int(owner["id"]), int(target["id"]), "scan_contact", {"created": created})
        return {"ok": True, "created": created, "contact_id": contact_id, "profile": self.participation_payload(db, int(target["id"]), viewer_id=int(owner["id"]), full=True)}

    def contacts(self, db, owner_token: str) -> dict:
        owner = self.resolve_owner(db, owner_token)
        if not owner:
            return {"ok": False, "error": "Acceso Networking invalido", "status_code": 404}
        rows = db.execute(
            """
            SELECT c.*, p.id AS target_id
            FROM networking_contacts c
            JOIN networking_event_participations p ON p.id = c.target_participation_id
            WHERE c.owner_participation_id = ? AND c.status = 'ACTIVE'
            ORDER BY c.updated_at DESC, c.id DESC
            """,
            (owner["id"],),
        ).fetchall()
        contacts = [
            {
                "contact_id": int(row["id"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "profile": self.participation_payload(db, int(row["target_id"]), viewer_id=int(owner["id"]), full=False),
            }
            for row in rows
        ]
        return {"ok": True, "contacts": contacts, "items": [item["profile"] for item in contacts]}

    def public_profile(self, db, public_profile_id: str, viewer_token: str = "") -> dict:
        row = db.execute("SELECT * FROM networking_event_participations WHERE public_profile_id = ?", (str(public_profile_id or "").strip(),)).fetchone()
        if not row:
            return {"ok": False, "error": "Perfil Networking inexistente", "status_code": 404}
        viewer = self.resolve_owner(db, viewer_token) if viewer_token else None
        if row["participation_state"] != "ACTIVE":
            return {"ok": False, "error": "Perfil Networking no activo", "status_code": 404}
        return {"ok": True, "profile": self.participation_payload(db, int(row["id"]), viewer_id=int(viewer["id"]) if viewer else None, full=bool(viewer))}

    def participation_payload(self, db, participation_id: int, *, viewer_id: int | None, full: bool) -> dict:
        row = db.execute(
            """
            SELECT nep.*, p.first_name, p.last_name, p.email, p.phone, p.company,
                   no.name AS organization_name, no.website AS organization_website, no.visibility AS organization_visibility,
                   ni.modes_json, ni.direction, ni.contact_openness, ni.discoverable, ni.profile_visible,
                   ni.channels_visible_default, ni.representative_visible, ni.bio, ni.offers_text, ni.seeks_text, ni.interests_text
            FROM networking_event_participations nep
            JOIN people p ON p.id = nep.person_id
            LEFT JOIN networking_organizations no ON no.id = nep.organization_id
            LEFT JOIN networking_intents ni ON ni.participation_id = nep.id
            WHERE nep.id = ?
            """,
            (participation_id,),
        ).fetchone()
        if not row:
            return {}
        data = dict(row)
        is_self = viewer_id is not None and int(viewer_id) == int(participation_id)
        is_contact = False
        if viewer_id and not is_self:
            is_contact = bool(db.execute(
                "SELECT 1 FROM networking_contacts WHERE owner_participation_id = ? AND target_participation_id = ? AND status = 'ACTIVE'",
                (viewer_id, participation_id),
            ).fetchone())
        representative_visible = int(data.get("representative_visible") or 0) == 1 or is_self
        organization_visible = is_self or data.get("organization_visibility") != "HIDDEN"
        organization_name = data.get("organization_name") or data.get("company") or ""
        profile = {
            "participation_id": participation_id if (is_self or full) else None,
            "public_profile_id": data["public_profile_id"],
            "event_id": data["event_id"],
            "state": data["participation_state"],
            "active": data["participation_state"] == "ACTIVE",
            "requires_onboarding": data["participation_state"] == "PASSIVE",
            "name": f"{data['first_name']} {data['last_name']}".strip() if representative_visible else "",
            "organization": organization_name if organization_visible else "",
            "organization_visible": organization_visible,
            "role": (data.get("title") or "") if representative_visible else "",
            "function": (data.get("normalized_function") or "OTHER") if representative_visible else "",
            "seniority": (data.get("normalized_seniority") or "PROFESSIONAL") if representative_visible else "",
            "bio": data.get("bio") or "",
            "offers": data.get("offers_text") or "",
            "seeks": data.get("seeks_text") or "",
            "interests": data.get("interests_text") or "",
            "photo": (data.get("profile_photo_url") or "") if representative_visible else "",
            "logo": (data.get("organization_logo_url") or "") if organization_visible else "",
            "modes": json.loads(data.get("modes_json") or "[]"),
            "direction": data.get("direction") or "BOTH",
            "contact_openness": data.get("contact_openness") or "CONNECT_FIRST",
            "channels": self.visible_channels(db, participation_id, is_self=is_self, is_contact=is_contact),
        }
        if is_self:
            profile["owner_token_hint"] = data.get("owner_token_hint") or ""
            profile["email"] = data.get("email") or ""
        return profile

    def visible_channels(self, db, participation_id: int, *, is_self: bool, is_contact: bool) -> list[dict]:
        channels = []
        for row in db.execute("SELECT * FROM networking_contact_channels WHERE participation_id = ? ORDER BY channel_type, id", (participation_id,)).fetchall():
            visibility = row["visibility"]
            if not is_self and visibility == "HIDDEN":
                continue
            if not is_self and visibility == "CONTACTS" and not is_contact:
                continue
            channels.append({"type": row["channel_type"], "label": row["label"], "value": row["value"], "url": row["url"] or self._channel_url(row["channel_type"], row["value"]), "visibility": visibility if is_self else None})
        return channels

    def resolve_owner(self, db, owner_token: str, event_id: int | None = None):
        token = str(owner_token or "").strip()
        if not token:
            return None
        owner_hash = self._hash_token(token)
        row = db.execute("SELECT * FROM networking_event_participations WHERE owner_token_hash = ?", (owner_hash,)).fetchone()
        if row and (not event_id or int(row["event_id"]) == int(event_id)):
            return row
        acc = db.execute("SELECT * FROM accreditations WHERE token = ?", (token.upper(),)).fetchone()
        if not acc:
            return None
        if event_id and int(acc["event_id"]) != int(event_id):
            return None
        return db.execute(
            "SELECT * FROM networking_event_participations WHERE event_id = ? AND person_id = ?",
            (acc["event_id"], acc["person_id"]),
        ).fetchone()

    def get_participation(self, db, participation_id: int):
        return db.execute("SELECT * FROM networking_event_participations WHERE id = ?", (participation_id,)).fetchone()

    def record_event(self, db, event_id: int, actor_id: int | None, target_id: int | None, event_type: str, payload: dict) -> None:
        db.execute(
            """
            INSERT INTO networking_interaction_events (event_id, actor_participation_id, target_participation_id, event_type, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_id, actor_id, target_id, event_type, self._safe_json(payload), self.now()),
        )

    def _normalize_import_row(self, row: dict, source_system: str) -> tuple[dict, str]:
        email = str(row.get("email") or row.get("mail") or "").strip().lower()
        first = str(row.get("first_name") or row.get("nombre") or row.get("name") or "").strip()
        last = str(row.get("last_name") or row.get("apellido") or "").strip()
        if not first or not email:
            return {}, "Nombre/email son obligatorios"
        if not last and " " in first:
            first, last = first.split(" ", 1)
        source_external_id = str(row.get("source_external_id") or row.get("external_id") or email).strip().lower()
        item = {
            "source_system": str(row.get("source_system") or source_system or "external").strip().upper(),
            "source_external_id": source_external_id,
            "first_name": first,
            "last_name": last,
            "email": email,
            "phone": str(row.get("phone") or row.get("telefono") or "").strip(),
            "dni": str(row.get("dni") or "").strip(),
            "company": str(row.get("company") or row.get("empresa") or row.get("organization") or row.get("organizacion") or "").strip(),
            "organization_visibility": self._organization_visibility(row),
            "organization_website": str(row.get("organization_website") or row.get("website") or "").strip(),
            "organization_description": str(row.get("organization_description") or "").strip(),
            "title": str(row.get("title") or row.get("position") or row.get("cargo") or "").strip(),
            "function": self._choice(row.get("function") or row.get("funcion"), FUNCTIONS, "OTHER"),
            "seniority": self._choice(row.get("seniority") or row.get("senioridad"), SENIORITIES, "PROFESSIONAL"),
            "photo_url": str(row.get("photo_url") or row.get("foto") or "").strip(),
            "organization_logo_url": str(row.get("organization_logo_url") or row.get("logo") or "").strip(),
            "bio": str(row.get("bio") or row.get("description") or row.get("descripcion") or "").strip(),
            "offers": str(row.get("offers") or row.get("offers_text") or "").strip(),
            "seeks": str(row.get("seeks") or row.get("seeks_text") or "").strip(),
            "interests": str(row.get("interests") or row.get("interests_text") or "").strip(),
            "channels": row.get("channels") if isinstance(row.get("channels"), list) else [],
        }
        for channel in CHANNEL_TYPES:
            if row.get(channel):
                item["channels"].append({"type": channel, "value": str(row.get(channel)).strip()})
        return item, ""

    def _upsert_person(self, db, item: dict) -> int:
        row = db.execute("SELECT * FROM people WHERE email = ?", (item["email"],)).fetchone()
        now = self.now()
        if row:
            db.execute(
                """
                UPDATE people
                SET first_name = ?, last_name = ?, phone = COALESCE(NULLIF(?, ''), phone),
                    dni = COALESCE(NULLIF(?, ''), dni), company = COALESCE(NULLIF(?, ''), company),
                    position = COALESCE(NULLIF(?, ''), position)
                WHERE id = ?
                """,
                (item["first_name"], item["last_name"], item["phone"], item["dni"], item["company"], item["title"], row["id"]),
            )
            return int(row["id"])
        return int(db.execute(
            """
            INSERT INTO people (first_name, last_name, email, phone, dni, company, position, source, device_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'networking', 'mobile', ?)
            """,
            (item["first_name"], item["last_name"], item["email"], item["phone"], item["dni"], item["company"], item["title"], now),
        ).lastrowid)

    def _upsert_networking_org(self, db, item: dict) -> int | None:
        name = item.get("company", "").strip()
        if not name:
            return None
        key = self._canonical_key(name)
        now = self.now()
        row = db.execute("SELECT * FROM networking_organizations WHERE canonical_key = ?", (key,)).fetchone()
        if row:
            db.execute(
                "UPDATE networking_organizations SET name = ?, visibility = COALESCE(NULLIF(?, ''), visibility), website = COALESCE(NULLIF(?, ''), website), logo_url = COALESCE(NULLIF(?, ''), logo_url), description = COALESCE(NULLIF(?, ''), description), updated_at = ? WHERE id = ?",
                (name, item.get("organization_visibility", ""), item.get("organization_website", ""), item.get("organization_logo_url", ""), item.get("organization_description", ""), now, row["id"]),
            )
            return int(row["id"])
        return int(db.execute(
            "INSERT INTO networking_organizations (canonical_key, name, visibility, website, logo_url, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (key, name, item.get("organization_visibility") or "PUBLIC", item.get("organization_website", ""), item.get("organization_logo_url", ""), item.get("organization_description", ""), now, now),
        ).lastrowid)

    def _upsert_channels(self, db, participation_id: int, item: dict, *, preserve_user_visibility: bool) -> None:
        now = self.now()
        for raw in item.get("channels") or []:
            channel_type = str(raw.get("type") or raw.get("channel_type") or "").strip().lower()
            value = str(raw.get("value") or "").strip()
            if channel_type not in CHANNEL_TYPES or not value:
                continue
            visibility = self._choice(raw.get("visibility"), CHANNEL_VISIBILITY, "CONTACTS")
            existing = db.execute(
                "SELECT * FROM networking_contact_channels WHERE participation_id = ? AND channel_type = ? AND value = ?",
                (participation_id, channel_type, value),
            ).fetchone()
            if existing:
                if preserve_user_visibility:
                    db.execute("UPDATE networking_contact_channels SET label = ?, url = COALESCE(NULLIF(?, ''), url), updated_at = ? WHERE id = ?", (str(raw.get("label") or ""), str(raw.get("url") or ""), now, existing["id"]))
                else:
                    db.execute("UPDATE networking_contact_channels SET label = ?, url = ?, visibility = ?, updated_at = ? WHERE id = ?", (str(raw.get("label") or ""), str(raw.get("url") or ""), visibility, now, existing["id"]))
            else:
                if preserve_user_visibility:
                    prior = db.execute(
                        "SELECT visibility FROM networking_contact_channels WHERE participation_id = ? AND channel_type = ? ORDER BY updated_at DESC, id DESC LIMIT 1",
                        (participation_id, channel_type),
                    ).fetchone()
                    if prior:
                        visibility = prior["visibility"]
                db.execute(
                    "INSERT INTO networking_contact_channels (participation_id, channel_type, label, value, url, visibility, source, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (participation_id, channel_type, str(raw.get("label") or ""), value, str(raw.get("url") or ""), visibility, str(raw.get("source") or "import"), now),
                )

    def _apply_channel_visibility_updates(self, db, participation_id: int, visibility_map: dict) -> None:
        if not isinstance(visibility_map, dict):
            return
        for channel_type, visibility in visibility_map.items():
            channel = str(channel_type).strip().lower()
            if channel not in CHANNEL_TYPES:
                continue
            db.execute(
                "UPDATE networking_contact_channels SET visibility = ?, updated_at = ? WHERE participation_id = ? AND channel_type = ?",
                (self._choice(visibility, CHANNEL_VISIBILITY, "CONTACTS"), self.now(), participation_id, channel),
            )

    def _upsert_classification(self, db, participation_id: int, concept_code: str, source: str) -> None:
        db.execute(
            "INSERT OR IGNORE INTO networking_classifications (participation_id, concept_code, source, provenance, created_at) VALUES (?, ?, ?, 'networking_v1', ?)",
            (participation_id, concept_code, source, self.now()),
        )

    def _find_existing_participation(self, db, event_id: int, item: dict, person_id: int | None = None):
        if person_id:
            row = db.execute("SELECT * FROM networking_event_participations WHERE event_id = ? AND person_id = ?", (event_id, person_id)).fetchone()
            if row:
                return row
        if item.get("source_external_id"):
            row = db.execute(
                "SELECT * FROM networking_event_participations WHERE event_id = ? AND source_system = ? AND source_external_id = ?",
                (event_id, item["source_system"], item["source_external_id"]),
            ).fetchone()
            if row:
                return row
        return db.execute(
            """
            SELECT nep.*
            FROM networking_event_participations nep
            JOIN people p ON p.id = nep.person_id
            WHERE nep.event_id = ? AND p.email = ?
            """,
            (event_id, item["email"]),
        ).fetchone()

    def _normalize_modes(self, raw) -> list[str]:
        if isinstance(raw, str):
            raw = [part.strip() for part in raw.split(",")]
        result = [self._choice(item, MODES, "") for item in (raw or [])]
        result = [item for item in result if item]
        return sorted(set(result)) or ["COMMERCIAL"]

    def _choice(self, raw, allowed: set[str], default: str) -> str:
        value = str(raw or "").strip().upper().replace(" ", "_").replace("/", "_")
        aliases = {
            "BUSINESS_ALLIANCE": "BUSINESS_ALLIANCES",
            "SERVICES": "SERVICES_SOLUTIONS",
            "SOLUTIONS": "SERVICES_SOLUTIONS",
            "BUSINESS_DEVELOPMENT": "BUSINESS_DEVELOPMENT",
            "PROFESSIONAL/TECHNICAL": "PROFESSIONAL_TECHNICAL",
            "CONNECT": "CONNECT_FIRST",
        }
        value = aliases.get(value, value)
        return value if value in allowed else default

    def _organization_visibility(self, row: dict) -> str:
        if "organization_visibility" in row:
            return self._choice(row.get("organization_visibility"), {"PUBLIC", "HIDDEN"}, "")
        if "organization_visible" in row:
            return "PUBLIC" if self._truthy(row.get("organization_visible")) else "HIDDEN"
        return ""

    def _canonical_key(self, value: str) -> str:
        key = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return key or hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]

    def _fingerprint(self, item: dict) -> str:
        payload = json.dumps({k: v for k, v in item.items() if k != "channels"}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _safe_json(self, value) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def _new_public_profile_id(self, db) -> str:
        value = "NET-" + secrets.token_urlsafe(12).replace("-", "").replace("_", "").upper()[:16]
        while db.execute("SELECT 1 FROM networking_event_participations WHERE public_profile_id = ?", (value,)).fetchone():
            value = "NET-" + secrets.token_urlsafe(12).replace("-", "").replace("_", "").upper()[:16]
        return value

    def _new_owner_token(self) -> str:
        return "NETOWN-" + secrets.token_urlsafe(24)

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()

    def _truthy(self, value) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"1", "true", "si", "sí", "yes", "on"}

    def _channel_url(self, channel_type: str, value: str) -> str:
        clean = str(value or "").strip()
        if channel_type == "email":
            return f"mailto:{clean}"
        if channel_type in {"phone", "whatsapp"}:
            digits = re.sub(r"[^0-9+]", "", clean)
            return f"https://wa.me/{digits.lstrip('+')}" if channel_type == "whatsapp" else f"tel:{digits}"
        if channel_type in {"website", "linkedin", "instagram", "facebook", "tiktok", "x", "youtube", "other"}:
            if clean.startswith(("http://", "https://")):
                return clean
            if channel_type == "linkedin":
                return f"https://www.linkedin.com/in/{clean.lstrip('@')}"
            if channel_type == "instagram":
                return f"https://www.instagram.com/{clean.lstrip('@')}"
            if channel_type == "facebook":
                return f"https://www.facebook.com/{clean.lstrip('@')}"
            if channel_type == "tiktok":
                return f"https://www.tiktok.com/@{clean.lstrip('@')}"
            if channel_type == "x":
                return f"https://x.com/{clean.lstrip('@')}"
            if channel_type == "youtube":
                return f"https://www.youtube.com/{clean.lstrip('@')}"
            return f"https://{clean}"
        return clean
