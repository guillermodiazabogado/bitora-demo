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
PRESENTATION_MODES = {"ORGANIZATION_FIRST", "PERSON_FIRST", "AUTO"}
CHANNEL_SCOPES = {"PERSONAL", "ORGANIZATION"}
SEMANTIC_TYPES = {"INDUSTRY", "SPECIALTY", "OFFER", "SEEK", "INTEREST"}
SEMANTIC_OWNER_TYPES = {"ORGANIZATION", "PERSON", "PARTICIPATION"}
SEMANTIC_SOURCES = {"SOURCE", "USER", "ADMIN", "SYSTEM"}
SEMANTIC_VISIBILITY = {"PUBLIC", "CONTACTS", "HIDDEN", "ADMIN"}
READINESS_DIMENSIONS = {
    "person.identity",
    "person.role",
    "person.bio",
    "organization.identity",
    "organization.activity",
    "organization.description",
    "networking.intent",
    "networking.offers_seeks",
    "semantic.offer",
    "semantic.seek",
    "semantic.specialty",
    "semantic.interest",
    "contact.permitted_route",
    "contact.organization_route",
}
READINESS_LABELS = {
    "person.identity": "identidad de la persona",
    "person.role": "rol o funcion",
    "person.bio": "descripcion profesional",
    "organization.identity": "organizacion",
    "organization.activity": "actividad o especialidad",
    "organization.description": "descripcion de la organizacion",
    "networking.intent": "intencion de networking",
    "networking.offers_seeks": "ofertas o busquedas",
    "semantic.offer": "oferta estructurada",
    "semantic.seek": "busqueda estructurada",
    "semantic.specialty": "especialidad estructurada",
    "semantic.interest": "interes u objetivo estructurado",
    "contact.permitted_route": "canal de contacto permitido",
    "contact.organization_route": "ruta corporativa permitida",
}
READINESS_DEFAULTS = {
    "ORGANIZATION_FIRST": {
        "required": [
            "organization.identity",
            "organization.activity",
            "networking.intent",
            "networking.offers_seeks",
            "semantic.offer",
            "contact.permitted_route",
        ],
        "recommended": ["organization.description", "person.identity", "person.role", "semantic.specialty", "semantic.seek", "contact.organization_route"],
    },
    "PERSON_FIRST": {
        "required": ["person.identity", "person.role", "person.bio", "networking.intent", "contact.permitted_route"],
        "recommended": ["organization.identity", "networking.offers_seeks", "semantic.offer", "semantic.seek", "semantic.interest"],
    },
}


def networking_schema_sql() -> str:
    return """
    CREATE TABLE IF NOT EXISTS networking_organizations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        canonical_key TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        activity TEXT NOT NULL DEFAULT '',
        specialty TEXT NOT NULL DEFAULT '',
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
        completed_title TEXT NOT NULL DEFAULT '',
        completed_function TEXT NOT NULL DEFAULT '',
        completed_seniority TEXT NOT NULL DEFAULT '',
        completed_organization_activity TEXT NOT NULL DEFAULT '',
        completed_organization_specialty TEXT NOT NULL DEFAULT '',
        completed_organization_description TEXT NOT NULL DEFAULT '',
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
        scope TEXT NOT NULL DEFAULT 'PERSONAL',
        source TEXT NOT NULL DEFAULT 'import',
        updated_at TEXT NOT NULL,
        UNIQUE(participation_id, channel_type, value)
    );

    CREATE TABLE IF NOT EXISTS networking_taxonomy_concepts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        concept_type TEXT NOT NULL,
        label TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        parent_code TEXT NOT NULL DEFAULT '',
        aliases_json TEXT NOT NULL DEFAULT '[]',
        taxonomy_version TEXT NOT NULL DEFAULT 'v1',
        active INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS networking_event_taxonomy_concepts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        concept_code TEXT NOT NULL REFERENCES networking_taxonomy_concepts(code) ON DELETE CASCADE,
        enabled INTEGER NOT NULL DEFAULT 1,
        label_override TEXT NOT NULL DEFAULT '',
        sort_order INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(event_id, concept_code)
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

    CREATE TABLE IF NOT EXISTS networking_semantic_classifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        owner_type TEXT NOT NULL,
        owner_id INTEGER NOT NULL,
        participation_id INTEGER REFERENCES networking_event_participations(id) ON DELETE CASCADE,
        concept_code TEXT NOT NULL REFERENCES networking_taxonomy_concepts(code) ON DELETE RESTRICT,
        semantic_role TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'USER',
        provenance TEXT NOT NULL DEFAULT '',
        visibility TEXT NOT NULL DEFAULT 'PUBLIC',
        free_text TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(event_id, owner_type, owner_id, concept_code, semantic_role, source)
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
    CREATE INDEX IF NOT EXISTS idx_networking_event_taxonomy_event ON networking_event_taxonomy_concepts(event_id, enabled);
    CREATE INDEX IF NOT EXISTS idx_networking_semantic_owner ON networking_semantic_classifications(event_id, owner_type, owner_id);
    CREATE INDEX IF NOT EXISTS idx_networking_semantic_participation ON networking_semantic_classifications(participation_id);
    """


class NetworkingService:
    def __init__(self, now: Callable[[], str]) -> None:
        self.now = now

    def ensure_schema(self, db) -> None:
        db.executescript(networking_schema_sql())
        self.ensure_v1_1_schema(db)
        self.ensure_v1_2_schema(db)
        self.ensure_v1_3_schema(db)
        self.ensure_taxonomy(db)

    def ensure_v1_1_schema(self, db) -> None:
        event_columns = {row["name"] for row in db.execute("PRAGMA table_info(events)").fetchall()}
        if "networking_profile_mode" not in event_columns:
            db.execute("ALTER TABLE events ADD COLUMN networking_profile_mode TEXT NOT NULL DEFAULT 'AUTO'")
        org_columns = {row["name"] for row in db.execute("PRAGMA table_info(networking_organizations)").fetchall()}
        if "activity" not in org_columns:
            db.execute("ALTER TABLE networking_organizations ADD COLUMN activity TEXT NOT NULL DEFAULT ''")
        if "specialty" not in org_columns:
            db.execute("ALTER TABLE networking_organizations ADD COLUMN specialty TEXT NOT NULL DEFAULT ''")
        channel_columns = {row["name"] for row in db.execute("PRAGMA table_info(networking_contact_channels)").fetchall()}
        if "scope" not in channel_columns:
            db.execute("ALTER TABLE networking_contact_channels ADD COLUMN scope TEXT NOT NULL DEFAULT 'PERSONAL'")

    def ensure_v1_2_schema(self, db) -> None:
        event_columns = {row["name"] for row in db.execute("PRAGMA table_info(events)").fetchall()}
        if "networking_readiness_required" not in event_columns:
            db.execute("ALTER TABLE events ADD COLUMN networking_readiness_required TEXT NOT NULL DEFAULT ''")
        if "networking_readiness_recommended" not in event_columns:
            db.execute("ALTER TABLE events ADD COLUMN networking_readiness_recommended TEXT NOT NULL DEFAULT ''")
        intent_columns = {row["name"] for row in db.execute("PRAGMA table_info(networking_intents)").fetchall()}
        for column in [
            "completed_title",
            "completed_function",
            "completed_seniority",
            "completed_organization_activity",
            "completed_organization_specialty",
            "completed_organization_description",
        ]:
            if column not in intent_columns:
                db.execute(f"ALTER TABLE networking_intents ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")

    def ensure_v1_3_schema(self, db) -> None:
        concept_columns = {row["name"] for row in db.execute("PRAGMA table_info(networking_taxonomy_concepts)").fetchall()}
        for column, ddl in {
            "description": "TEXT NOT NULL DEFAULT ''",
            "parent_code": "TEXT NOT NULL DEFAULT ''",
            "aliases_json": "TEXT NOT NULL DEFAULT '[]'",
        }.items():
            if column not in concept_columns:
                db.execute(f"ALTER TABLE networking_taxonomy_concepts ADD COLUMN {column} {ddl}")
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS networking_event_taxonomy_concepts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                concept_code TEXT NOT NULL REFERENCES networking_taxonomy_concepts(code) ON DELETE CASCADE,
                enabled INTEGER NOT NULL DEFAULT 1,
                label_override TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(event_id, concept_code)
            );
            CREATE TABLE IF NOT EXISTS networking_semantic_classifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                owner_type TEXT NOT NULL,
                owner_id INTEGER NOT NULL,
                participation_id INTEGER REFERENCES networking_event_participations(id) ON DELETE CASCADE,
                concept_code TEXT NOT NULL REFERENCES networking_taxonomy_concepts(code) ON DELETE RESTRICT,
                semantic_role TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'USER',
                provenance TEXT NOT NULL DEFAULT '',
                visibility TEXT NOT NULL DEFAULT 'PUBLIC',
                free_text TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(event_id, owner_type, owner_id, concept_code, semantic_role, source)
            );
            CREATE INDEX IF NOT EXISTS idx_networking_event_taxonomy_event ON networking_event_taxonomy_concepts(event_id, enabled);
            CREATE INDEX IF NOT EXISTS idx_networking_semantic_owner ON networking_semantic_classifications(event_id, owner_type, owner_id);
            CREATE INDEX IF NOT EXISTS idx_networking_semantic_participation ON networking_semantic_classifications(participation_id);
            """
        )

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

    def get_event_config(self, db, event_id: int) -> dict:
        row = db.execute("SELECT id, name, networking_profile_mode, networking_readiness_required, networking_readiness_recommended FROM events WHERE id = ?", (event_id,)).fetchone()
        if not row:
            return {"ok": False, "error": "Evento inexistente", "status_code": 404}
        readiness = self.readiness_config(row)
        return {
            "ok": True,
            "event_id": int(row["id"]),
            "event_name": row["name"],
            "networking_profile_mode": self._presentation_mode(row["networking_profile_mode"]),
            "networking_readiness_required": readiness["required"],
            "networking_readiness_recommended": readiness["recommended"],
            "networking_readiness_available": sorted(READINESS_DIMENSIONS),
            "semantic_taxonomy": self.event_taxonomy_payload(db, event_id).get("concepts", []),
        }

    def event_taxonomy_payload(self, db, event_id: int) -> dict:
        if not db.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone():
            return {"ok": False, "error": "Evento inexistente", "status_code": 404}
        rows = db.execute(
            """
            SELECT tc.code, tc.concept_type, tc.label, tc.description, tc.parent_code, tc.aliases_json,
                   tc.taxonomy_version, tc.active, etc.enabled, etc.label_override, etc.sort_order
            FROM networking_event_taxonomy_concepts etc
            JOIN networking_taxonomy_concepts tc ON tc.code = etc.concept_code
            WHERE etc.event_id = ?
            ORDER BY tc.concept_type, etc.sort_order, COALESCE(NULLIF(etc.label_override, ''), tc.label)
            """,
            (event_id,),
        ).fetchall()
        concepts = []
        for row in rows:
            concepts.append({
                "code": row["code"],
                "type": row["concept_type"],
                "label": row["label_override"] or row["label"],
                "canonical_label": row["label"],
                "description": row["description"],
                "parent_code": row["parent_code"],
                "aliases": json.loads(row["aliases_json"] or "[]"),
                "taxonomy_version": row["taxonomy_version"],
                "enabled": bool(row["enabled"]) and bool(row["active"]),
                "sort_order": int(row["sort_order"] or 0),
            })
        return {"ok": True, "event_id": event_id, "concepts": concepts}

    def update_event_taxonomy(self, db, event_id: int, data: dict, actor: str = "Admin") -> dict:
        if not db.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone():
            return {"ok": False, "error": "Evento inexistente", "status_code": 404}
        now = self.now()
        changed = []
        for raw in data.get("concepts") if isinstance(data.get("concepts"), list) else []:
            concept_type = self._choice(raw.get("type") or raw.get("concept_type"), SEMANTIC_TYPES, "")
            label = str(raw.get("label") or "").strip()
            if not concept_type or not label:
                continue
            code = self._upsert_taxonomy_concept(
                db,
                concept_type,
                label,
                code=str(raw.get("code") or "").strip(),
                explicit_code=bool(str(raw.get("code") or "").strip()),
                description=str(raw.get("description") or "").strip(),
                aliases=self._semantic_values(raw.get("aliases")),
                parent_code=str(raw.get("parent_code") or "").strip(),
            )
            enabled = 1 if self._truthy(raw.get("enabled", True)) else 0
            db.execute(
                """
                INSERT INTO networking_event_taxonomy_concepts (event_id, concept_code, enabled, label_override, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id, concept_code) DO UPDATE SET
                    enabled = excluded.enabled,
                    label_override = excluded.label_override,
                    sort_order = excluded.sort_order,
                    updated_at = excluded.updated_at
                """,
                (event_id, code, enabled, str(raw.get("label_override") or "").strip(), int(raw.get("sort_order") or 0), now, now),
            )
            changed.append(code)
        for code in self._semantic_values(data.get("disable")):
            db.execute("UPDATE networking_event_taxonomy_concepts SET enabled = 0, updated_at = ? WHERE event_id = ? AND concept_code = ?", (now, event_id, code))
            changed.append(code)
        for code in self._semantic_values(data.get("enable")):
            if db.execute("SELECT 1 FROM networking_taxonomy_concepts WHERE code = ?", (code,)).fetchone():
                db.execute(
                    """
                    INSERT INTO networking_event_taxonomy_concepts (event_id, concept_code, enabled, created_at, updated_at)
                    VALUES (?, ?, 1, ?, ?)
                    ON CONFLICT(event_id, concept_code) DO UPDATE SET enabled = 1, updated_at = excluded.updated_at
                    """,
                    (event_id, code, now, now),
                )
                changed.append(code)
        self.record_event(db, event_id, None, None, "taxonomy_config_updated", {"actor": actor, "changed": sorted(set(changed))})
        return self.event_taxonomy_payload(db, event_id)

    def update_event_config(self, db, event_id: int, data: dict, actor: str = "Admin") -> dict:
        if not db.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone():
            return {"ok": False, "error": "Evento inexistente", "status_code": 404}
        mode = self._presentation_mode(data.get("networking_profile_mode") or data.get("profile_mode") or data.get("mode"))
        existing = db.execute("SELECT networking_readiness_required, networking_readiness_recommended FROM events WHERE id = ?", (event_id,)).fetchone()
        if "networking_readiness_required" in data or "readiness_required" in data:
            required = self._readiness_keys(data.get("networking_readiness_required") if "networking_readiness_required" in data else data.get("readiness_required"))
        else:
            required = self._readiness_keys(existing["networking_readiness_required"] if existing else "")
        if "networking_readiness_recommended" in data or "readiness_recommended" in data:
            recommended = self._readiness_keys(data.get("networking_readiness_recommended") if "networking_readiness_recommended" in data else data.get("readiness_recommended"))
        else:
            recommended = self._readiness_keys(existing["networking_readiness_recommended"] if existing else "")
        recommended = [key for key in recommended if key not in required]
        db.execute(
            "UPDATE events SET networking_profile_mode = ?, networking_readiness_required = ?, networking_readiness_recommended = ? WHERE id = ?",
            (mode, ",".join(required), ",".join(recommended), event_id),
        )
        self.record_event(db, event_id, None, None, "event_config_updated", {"actor": actor, "networking_profile_mode": mode, "readiness_required": required, "readiness_recommended": recommended})
        row = db.execute("SELECT id, name, networking_profile_mode, networking_readiness_required, networking_readiness_recommended FROM events WHERE id = ?", (event_id,)).fetchone()
        readiness = self.readiness_config(row)
        return {"ok": True, "event_id": event_id, "networking_profile_mode": mode, "networking_readiness_required": readiness["required"], "networking_readiness_recommended": readiness["recommended"]}

    def preview_import(self, db, event_id: int, rows: list[dict], source_system: str = "external") -> dict:
        event = db.execute("SELECT id, networking_profile_mode, networking_readiness_required, networking_readiness_recommended FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            return {"ok": False, "error": "Evento inexistente", "status_code": 404}
        summary = {"valid": 0, "errors": 0, "existing": 0, "complete": 0, "incomplete": 0, "unknown_concepts": 0, "semantic_unknown_concepts": 0, "common_missing": {}, "rows": []}
        for index, row in enumerate(rows, start=1):
            item, error = self._normalize_import_row(row, source_system)
            if error:
                summary["errors"] += 1
                summary["rows"].append({"row": index, "ok": False, "error": error})
                continue
            existing = self._find_existing_participation(db, event_id, item)
            readiness = self.evaluate_import_readiness(item, event)
            semantic = self.semantic_import_diagnostics(db, event_id, item)
            summary["valid"] += 1
            summary["existing"] += 1 if existing else 0
            if readiness["status"] == "READY":
                summary["complete"] += 1
            else:
                summary["incomplete"] += 1
                for key in readiness["missing_required"]:
                    summary["common_missing"][key] = int(summary["common_missing"].get(key, 0)) + 1
            if semantic["unknown"]:
                summary["unknown_concepts"] += len(semantic["unknown"])
                summary["semantic_unknown_concepts"] = summary["unknown_concepts"]
            summary["rows"].append({"row": index, "ok": True, "email": item["email"], "existing": bool(existing), "readiness": readiness, "semantic": semantic})
        summary["common_missing"] = dict(sorted(summary["common_missing"].items(), key=lambda item: (-item[1], item[0])))
        return {"ok": summary["errors"] == 0, **summary}

    def import_profiles(self, db, event_id: int, rows: list[dict], source_system: str = "external", actor: str = "system") -> dict:
        preview = self.preview_import(db, event_id, rows, source_system)
        if preview.get("status_code"):
            return preview
        preview_by_row = {int(item.get("row") or 0): item for item in preview.get("rows", []) if item.get("ok")}
        summary = {"created": 0, "updated": 0, "errors": 0, "unknown_concepts": int(preview.get("unknown_concepts") or 0), "semantic_unknown_concepts": int(preview.get("semantic_unknown_concepts") or 0), "rows": []}
        for index, row in enumerate(rows, start=1):
            item, error = self._normalize_import_row(row, source_system)
            if error:
                summary["errors"] += 1
                summary["rows"].append({"row": index, "ok": False, "error": error})
                continue
            result = self.upsert_participation(db, event_id, item, actor=actor, activate=False)
            summary["created"] += 1 if result["created"] else 0
            summary["updated"] += 0 if result["created"] else 1
            preview_row = preview_by_row.get(index) or {}
            summary["rows"].append({"row": index, "ok": True, "participation_id": result["participation_id"], "state": result["state"], "created": result["created"], "semantic": preview_row.get("semantic") or {"known": [], "unknown": []}})
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
        source_payload = self._safe_source_payload(item)
        if existing:
            db.execute(
                """
                UPDATE networking_event_participations
                SET accreditation_id = COALESCE(?, accreditation_id),
                    organization_id = COALESCE(?, organization_id),
                    source_fingerprint = ?,
                    title = COALESCE(NULLIF(?, ''), title),
                    normalized_function = CASE WHEN ? = 1 THEN ? ELSE normalized_function END,
                    normalized_seniority = CASE WHEN ? = 1 THEN ? ELSE normalized_seniority END,
                    profile_photo_url = COALESCE(NULLIF(?, ''), profile_photo_url),
                    organization_logo_url = COALESCE(NULLIF(?, ''), organization_logo_url),
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
                    1 if item.get("function_declared") else 0,
                    item["function"],
                    1 if item.get("seniority_declared") else 0,
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
        self._sync_semantic_classifications(db, event_id, participation_id, item, source="SOURCE", provenance=item["source_system"])
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
                completed_title = COALESCE(NULLIF(?, ''), completed_title),
                completed_function = COALESCE(NULLIF(?, ''), completed_function),
                completed_seniority = COALESCE(NULLIF(?, ''), completed_seniority),
                completed_organization_activity = COALESCE(NULLIF(?, ''), completed_organization_activity),
                completed_organization_specialty = COALESCE(NULLIF(?, ''), completed_organization_specialty),
                completed_organization_description = COALESCE(NULLIF(?, ''), completed_organization_description),
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
                str(data.get("completed_title") or data.get("title") or "").strip(),
                self._choice(data.get("completed_function") or data.get("function"), FUNCTIONS, ""),
                self._choice(data.get("completed_seniority") or data.get("seniority"), SENIORITIES, ""),
                str(data.get("completed_organization_activity") or data.get("organization_activity") or "").strip(),
                str(data.get("completed_organization_specialty") or data.get("organization_specialty") or "").strip(),
                str(data.get("completed_organization_description") or data.get("organization_description") or "").strip(),
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
        self._upsert_channels(db, int(participation["id"]), self._completion_item(data), preserve_user_visibility=False)
        self._sync_semantic_classifications(db, int(participation["event_id"]), int(participation["id"]), data, source="USER", provenance="onboarding")
        self._apply_channel_visibility_updates(db, int(participation["id"]), data.get("channel_visibility") or {})
        self.record_event(db, int(participation["event_id"]), int(participation["id"]), None, "onboarded", {"modes": modes, "direction": direction, "contact_openness": openness})
        return {"ok": True, "participation": self.participation_payload(db, int(participation["id"]), viewer_id=int(participation["id"]), full=True)}

    def complete_profile(self, db, owner_token: str, data: dict) -> dict:
        participation = self.resolve_owner(db, owner_token, int(data.get("event_id") or 0) or None)
        if not participation:
            return {"ok": False, "error": "Acceso Networking invalido", "status_code": 404}
        now = self.now()
        db.execute(
            """
            UPDATE networking_intents
            SET bio = COALESCE(NULLIF(?, ''), bio),
                offers_text = COALESCE(NULLIF(?, ''), offers_text),
                seeks_text = COALESCE(NULLIF(?, ''), seeks_text),
                interests_text = COALESCE(NULLIF(?, ''), interests_text),
                completed_title = COALESCE(NULLIF(?, ''), completed_title),
                completed_function = COALESCE(NULLIF(?, ''), completed_function),
                completed_seniority = COALESCE(NULLIF(?, ''), completed_seniority),
                completed_organization_activity = COALESCE(NULLIF(?, ''), completed_organization_activity),
                completed_organization_specialty = COALESCE(NULLIF(?, ''), completed_organization_specialty),
                completed_organization_description = COALESCE(NULLIF(?, ''), completed_organization_description),
                updated_at = ?
            WHERE participation_id = ?
            """,
            (
                str(data.get("bio") or "").strip(),
                str(data.get("offers") or data.get("offers_text") or "").strip(),
                str(data.get("seeks") or data.get("seeks_text") or "").strip(),
                str(data.get("interests") or data.get("interests_text") or "").strip(),
                str(data.get("completed_title") or data.get("title") or "").strip(),
                self._choice(data.get("completed_function") or data.get("function"), FUNCTIONS, ""),
                self._choice(data.get("completed_seniority") or data.get("seniority"), SENIORITIES, ""),
                str(data.get("completed_organization_activity") or data.get("organization_activity") or "").strip(),
                str(data.get("completed_organization_specialty") or data.get("organization_specialty") or "").strip(),
                str(data.get("completed_organization_description") or data.get("organization_description") or "").strip(),
                now,
                participation["id"],
            ),
        )
        self._upsert_channels(db, int(participation["id"]), self._completion_item(data), preserve_user_visibility=False)
        self._sync_semantic_classifications(db, int(participation["event_id"]), int(participation["id"]), data, source="USER", provenance="completion")
        self.record_event(db, int(participation["event_id"]), int(participation["id"]), None, "profile_completed", {"missing_before": data.get("missing_required") or []})
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
                   e.networking_profile_mode, e.networking_readiness_required, e.networking_readiness_recommended,
                   no.name AS organization_name, no.activity AS organization_activity, no.specialty AS organization_specialty,
                   no.website AS organization_website, no.logo_url AS organization_logo,
                   no.description AS organization_description, no.visibility AS organization_visibility,
                   ni.modes_json, ni.direction, ni.contact_openness, ni.discoverable, ni.profile_visible,
                   ni.channels_visible_default, ni.representative_visible, ni.bio, ni.offers_text, ni.seeks_text, ni.interests_text,
                   ni.completed_title, ni.completed_function, ni.completed_seniority,
                   ni.completed_organization_activity, ni.completed_organization_specialty, ni.completed_organization_description
            FROM networking_event_participations nep
            JOIN events e ON e.id = nep.event_id
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
        effective_title = data.get("completed_title") or data.get("title") or ""
        effective_function = data.get("completed_function") or data.get("normalized_function") or "OTHER"
        effective_seniority = data.get("completed_seniority") or data.get("normalized_seniority") or "PROFESSIONAL"
        person_bio = data.get("bio") or ""
        person_seeks = data.get("seeks_text") or ""
        person_interests = data.get("interests_text") or ""
        organization_description = data.get("completed_organization_description") or data.get("organization_description") or ""
        organization_activity = data.get("completed_organization_activity") or data.get("organization_activity") or ""
        organization_specialty = data.get("completed_organization_specialty") or data.get("organization_specialty") or ""
        organization_offers = data.get("offers_text") or ""
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
            "role": effective_title if representative_visible else "",
            "function": effective_function if representative_visible else "",
            "seniority": effective_seniority if representative_visible else "",
            "bio": person_bio if representative_visible else "",
            "offers": organization_offers if organization_visible else "",
            "seeks": person_seeks if representative_visible else "",
            "interests": person_interests if representative_visible else "",
            "photo": (data.get("profile_photo_url") or "") if representative_visible else "",
            "logo": (data.get("organization_logo_url") or data.get("organization_logo") or "") if organization_visible else "",
            "organization_activity": organization_activity if organization_visible else "",
            "organization_specialty": organization_specialty if organization_visible else "",
            "organization_description": organization_description if organization_visible else "",
            "modes": json.loads(data.get("modes_json") or "[]"),
            "direction": data.get("direction") or "BOTH",
            "contact_openness": data.get("contact_openness") or "CONNECT_FIRST",
            "channels": self.visible_channels(
                db,
                participation_id,
                is_self=is_self,
                is_contact=is_contact,
                representative_visible=representative_visible,
                organization_visible=organization_visible,
            ),
        }
        profile["presentation"] = self.presentation_payload(
            profile,
            requested_mode=data.get("networking_profile_mode") or "AUTO",
            representative_visible=representative_visible,
            organization_visible=organization_visible,
        )
        external_representative_visible = int(data.get("representative_visible") or 0) == 1
        external_organization_visible = data.get("organization_visibility") != "HIDDEN"
        readiness_profile = dict(profile)
        if not external_representative_visible:
            readiness_profile.update({"name": "", "role": "", "function": "", "seniority": "", "bio": "", "seeks": "", "interests": "", "photo": ""})
        if not external_organization_visible:
            readiness_profile.update({"organization": "", "organization_visible": False, "logo": "", "offers": "", "organization_activity": "", "organization_specialty": "", "organization_description": ""})
        readiness_profile["channels"] = self.visible_channels(
            db,
            participation_id,
            is_self=False,
            is_contact=True,
            representative_visible=external_representative_visible,
            organization_visible=external_organization_visible,
        )
        readiness_profile["presentation"] = self.presentation_payload(
            readiness_profile,
            requested_mode=data.get("networking_profile_mode") or "AUTO",
            representative_visible=external_representative_visible,
            organization_visible=external_organization_visible,
        )
        profile["semantic"] = self.semantic_profile(
            db,
            int(data["event_id"]),
            participation_id,
            person_id=int(data["person_id"]),
            organization_id=int(data["organization_id"]) if data.get("organization_id") else None,
            representative_visible=representative_visible,
            organization_visible=organization_visible,
        )
        readiness_profile["semantic"] = self.semantic_profile(
            db,
            int(data["event_id"]),
            participation_id,
            person_id=int(data["person_id"]),
            organization_id=int(data["organization_id"]) if data.get("organization_id") else None,
            representative_visible=external_representative_visible,
            organization_visible=external_organization_visible,
        )
        profile["readiness"] = self.evaluate_profile_readiness(readiness_profile, data)
        if is_self:
            profile["owner_token_hint"] = data.get("owner_token_hint") or ""
            profile["email"] = data.get("email") or ""
        return profile

    def visible_channels(self, db, participation_id: int, *, is_self: bool, is_contact: bool, representative_visible: bool = True, organization_visible: bool = True) -> list[dict]:
        channels = []
        for row in db.execute("SELECT * FROM networking_contact_channels WHERE participation_id = ? ORDER BY channel_type, id", (participation_id,)).fetchall():
            visibility = row["visibility"]
            scope = row["scope"] if "scope" in row.keys() else "PERSONAL"
            if not is_self and visibility == "HIDDEN":
                continue
            if not is_self and visibility == "CONTACTS" and not is_contact:
                continue
            if not is_self and scope != "ORGANIZATION" and not representative_visible:
                continue
            if not is_self and scope == "ORGANIZATION" and not organization_visible:
                continue
            channels.append({"type": row["channel_type"], "label": row["label"], "value": row["value"], "url": row["url"] or self._channel_url(row["channel_type"], row["value"]), "scope": scope, "visibility": visibility if is_self else None})
        return channels

    def presentation_payload(self, profile: dict, *, requested_mode: str, representative_visible: bool, organization_visible: bool) -> dict:
        mode = self._effective_presentation_mode(requested_mode, profile)
        personal_channels = [channel for channel in profile.get("channels") or [] if channel.get("scope") != "ORGANIZATION"]
        organization_channels = [channel for channel in profile.get("channels") or [] if channel.get("scope") == "ORGANIZATION"]
        person = {
            "visible": bool(representative_visible and (profile.get("name") or profile.get("role") or profile.get("photo"))),
            "name": profile.get("name") or "",
            "role": profile.get("role") or "",
            "function": profile.get("function") or "",
            "photo": profile.get("photo") or "",
            "channels": personal_channels if representative_visible else [],
        }
        organization = {
            "visible": bool(organization_visible and (profile.get("organization") or profile.get("logo"))),
            "name": profile.get("organization") or "",
            "logo": profile.get("logo") or "",
            "activity": profile.get("organization_activity") or "",
            "specialty": profile.get("organization_specialty") or "",
            "description": profile.get("organization_description") or "",
            "offers": profile.get("offers") or "",
            "channels": organization_channels,
        }
        if mode == "ORGANIZATION_FIRST" and organization["visible"]:
            primary = {
                "kind": "organization",
                "title": organization["name"],
                "subtitle": " / ".join([part for part in [organization["activity"], organization["specialty"]] if part]),
                "media": organization["logo"],
                "description": organization["description"] or organization["offers"] or profile.get("bio") or "",
                "actions": organization["channels"],
            }
            secondary = {
                "kind": "representative",
                "title": person["name"] if person["visible"] else "",
                "subtitle": person["role"] if person["visible"] else "",
                "media": person["photo"] if person["visible"] else "",
                "description": profile.get("bio") if person["visible"] else "",
                "actions": person["channels"] if person["visible"] else [],
            }
        else:
            primary = {
                "kind": "person",
                "title": person["name"] or organization["name"] or "Oportunidad disponible",
                "subtitle": " / ".join([part for part in [person["role"], organization["name"]] if part]),
                "media": person["photo"] or organization["logo"],
                "description": profile.get("bio") or profile.get("offers") or organization["description"] or "",
                "actions": person["channels"],
            }
            secondary = {
                "kind": "organization",
                "title": organization["name"] if organization["visible"] else "",
                "subtitle": " / ".join([part for part in [organization["activity"], organization["specialty"]] if part]),
                "media": organization["logo"] if organization["visible"] else "",
                "description": (organization["description"] or organization["offers"]) if organization["visible"] else "",
                "actions": organization["channels"] if organization["visible"] else [],
            }
        return {"mode": mode, "primary": primary, "secondary": secondary, "person": person, "organization": organization}

    def readiness_config(self, event_row) -> dict:
        mode = self._effective_readiness_mode(event_row)
        defaults = READINESS_DEFAULTS.get(mode, READINESS_DEFAULTS["PERSON_FIRST"])
        required = self._readiness_keys(event_row["networking_readiness_required"] if event_row and "networking_readiness_required" in event_row.keys() else "")
        recommended = self._readiness_keys(event_row["networking_readiness_recommended"] if event_row and "networking_readiness_recommended" in event_row.keys() else "")
        if not required:
            required = list(defaults["required"])
        if not recommended:
            recommended = list(defaults["recommended"])
        recommended = [key for key in recommended if key not in required]
        return {"mode": mode, "required": required, "recommended": recommended}

    def evaluate_profile_readiness(self, profile: dict, event_row) -> dict:
        config = self.readiness_config(event_row)
        completed = self._completed_readiness_dimensions(profile)
        required = config["required"]
        recommended = config["recommended"]
        missing_required = [key for key in required if key not in completed]
        missing_recommended = [key for key in recommended if key not in completed]
        relevant = required + recommended
        done = len([key for key in relevant if key in completed])
        status = "READY" if not missing_required else "INCOMPLETE"
        active = profile.get("state") == "ACTIVE"
        return {
            "status": status,
            "ready_participation": bool(active and status == "READY"),
            "profile_complete": status == "READY",
            "participation_state": profile.get("state") or "",
            "mode": config["mode"],
            "completed": done,
            "relevant": len(relevant),
            "percentage": round(done * 100 / len(relevant)) if relevant else 100,
            "missing_required": missing_required,
            "missing_recommended": missing_recommended,
            "missing_labels": {key: READINESS_LABELS.get(key, key) for key in missing_required + missing_recommended},
            "next_actions": [READINESS_LABELS.get(key, key) for key in missing_required[:3]],
        }

    def evaluate_import_readiness(self, item: dict, event_row) -> dict:
        profile = {
            "state": "PASSIVE",
            "name": f"{item.get('first_name', '')} {item.get('last_name', '')}".strip(),
            "role": item.get("title") or "",
            "function": item.get("function") or "OTHER",
            "bio": item.get("bio") or "",
            "organization": item.get("company") if item.get("organization_visibility") != "HIDDEN" else "",
            "organization_activity": item.get("organization_activity") or "",
            "organization_specialty": item.get("organization_specialty") or "",
            "organization_description": item.get("organization_description") or "",
            "offers": item.get("offers") or "",
            "seeks": item.get("seeks") or "",
            "interests": item.get("interests") or "",
            "modes": [],
            "direction": "",
            "contact_openness": "",
            "channels": [
                {
                    "type": channel.get("type") or channel.get("channel_type"),
                    "scope": self._choice(channel.get("scope"), CHANNEL_SCOPES, "PERSONAL"),
                }
                for channel in item.get("channels") or []
                if self._choice(channel.get("visibility"), CHANNEL_VISIBILITY, "CONTACTS") != "HIDDEN"
            ],
        }
        return self.evaluate_profile_readiness(profile, event_row)

    def readiness_summary(self, db, event_id: int, *, include_participants: bool = False) -> dict:
        if not db.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone():
            return {"ok": False, "error": "Evento inexistente", "status_code": 404}
        rows = db.execute("SELECT id FROM networking_event_participations WHERE event_id = ? ORDER BY updated_at DESC, id DESC", (event_id,)).fetchall()
        summary = {"total": 0, "passive": 0, "active": 0, "ready": 0, "incomplete": 0, "common_missing": {}, "participants": []}
        for row in rows:
            profile = self.participation_payload(db, int(row["id"]), viewer_id=None, full=True)
            readiness = profile.get("readiness") or {}
            summary["total"] += 1
            if profile.get("state") == "ACTIVE":
                summary["active"] += 1
            elif profile.get("state") == "PASSIVE":
                summary["passive"] += 1
            if readiness.get("status") == "READY":
                summary["ready"] += 1
            else:
                summary["incomplete"] += 1
            for key in readiness.get("missing_required") or []:
                summary["common_missing"][key] = int(summary["common_missing"].get(key, 0)) + 1
            if include_participants and readiness.get("status") != "READY":
                summary["participants"].append({
                    "participation_id": profile.get("participation_id"),
                    "display_name": profile.get("name") or profile.get("organization") or "Perfil sin nombre visible",
                    "state": profile.get("state"),
                    "readiness": {
                        "status": readiness.get("status"),
                        "percentage": readiness.get("percentage"),
                        "missing_required": readiness.get("missing_required") or [],
                        "missing_recommended": readiness.get("missing_recommended") or [],
                        "missing_labels": readiness.get("missing_labels") or {},
                    },
                })
        summary["common_missing"] = dict(sorted(summary["common_missing"].items(), key=lambda item: (-item[1], item[0])))
        return {"ok": True, "event_id": event_id, **summary}

    def _completed_readiness_dimensions(self, profile: dict) -> set[str]:
        completed = set()
        channels = profile.get("channels") or []
        if profile.get("name"):
            completed.add("person.identity")
        if profile.get("role") or (profile.get("function") and profile.get("function") != "OTHER"):
            completed.add("person.role")
        if profile.get("bio") or profile.get("interests"):
            completed.add("person.bio")
        if profile.get("organization"):
            completed.add("organization.identity")
        if profile.get("organization_activity") or profile.get("organization_specialty"):
            completed.add("organization.activity")
        if profile.get("organization_description") or profile.get("offers"):
            completed.add("organization.description")
        if profile.get("modes") and profile.get("direction") and profile.get("contact_openness"):
            completed.add("networking.intent")
        if profile.get("offers") or profile.get("seeks") or profile.get("interests"):
            completed.add("networking.offers_seeks")
        semantic = profile.get("semantic") or {}
        if (semantic.get("offers") or semantic.get("organization_offers")):
            completed.add("semantic.offer")
        if semantic.get("seeks"):
            completed.add("semantic.seek")
        if semantic.get("specialties"):
            completed.add("semantic.specialty")
        if semantic.get("interests"):
            completed.add("semantic.interest")
        if channels:
            completed.add("contact.permitted_route")
        if any(channel.get("scope") == "ORGANIZATION" for channel in channels):
            completed.add("contact.organization_route")
        return completed

    def semantic_import_diagnostics(self, db, event_id: int, item: dict) -> dict:
        known = []
        unknown = []
        for entry in self._semantic_inputs(item):
            for value in entry["values"]:
                concept = self._resolve_event_concept(db, event_id, entry["type"], value)
                if concept:
                    known.append({"field": entry["field"], "value": value, "concept_code": concept["code"], "type": entry["type"], "role": entry["role"]})
                else:
                    unknown.append({"field": entry["field"], "value": value, "type": entry["type"], "role": entry["role"], "code": "UNKNOWN_CONCEPT", "reason": "UNKNOWN_CONCEPT"})
        return {"known": known, "unknown": unknown}

    def semantic_profile(self, db, event_id: int, participation_id: int, *, person_id: int, organization_id: int | None, representative_visible: bool, organization_visible: bool) -> dict:
        clauses = []
        params = [event_id]
        if representative_visible:
            clauses.append("(sc.owner_type = 'PARTICIPATION' AND sc.owner_id = ?)")
            params.append(participation_id)
        if representative_visible:
            clauses.append("(sc.owner_type = 'PERSON' AND sc.owner_id = ?)")
            params.append(person_id)
        if organization_visible and organization_id:
            clauses.append("(sc.owner_type = 'ORGANIZATION' AND sc.owner_id = ?)")
            params.append(organization_id)
        if not clauses:
            return {"industries": [], "specialties": [], "organization_offers": [], "offers": [], "seeks": [], "interests": [], "summary": []}
        rows = db.execute(
            f"""
            SELECT sc.owner_type, sc.semantic_role, sc.source, sc.free_text, tc.code, tc.concept_type,
                   COALESCE(NULLIF(etc.label_override, ''), tc.label) AS label
            FROM networking_semantic_classifications sc
            JOIN networking_taxonomy_concepts tc ON tc.code = sc.concept_code
            LEFT JOIN networking_event_taxonomy_concepts etc ON etc.event_id = sc.event_id AND etc.concept_code = sc.concept_code
            WHERE sc.event_id = ? AND sc.visibility != 'HIDDEN' AND ({' OR '.join(clauses)})
            ORDER BY sc.owner_type, sc.semantic_role, label
            """,
            params,
        ).fetchall()
        result = {"industries": [], "specialties": [], "organization_offers": [], "offers": [], "seeks": [], "interests": []}
        for row in rows:
            item = {"code": row["code"], "label": row["label"], "source": row["source"], "text": row["free_text"] or ""}
            role = row["semantic_role"]
            owner = row["owner_type"]
            if role == "INDUSTRY":
                result["industries"].append(item)
            elif role == "SPECIALTY":
                result["specialties"].append(item)
            elif role == "OFFER" and owner == "ORGANIZATION":
                result["organization_offers"].append(item)
            elif role == "OFFER":
                result["offers"].append(item)
            elif role == "SEEK":
                result["seeks"].append(item)
            elif role == "INTEREST":
                result["interests"].append(item)
        result["summary"] = [item["label"] for key in ("industries", "specialties", "organization_offers", "offers", "seeks", "interests") for item in result[key]][:6]
        return result

    def _sync_semantic_classifications(self, db, event_id: int, participation_id: int, data: dict, *, source: str, provenance: str) -> None:
        source = self._choice(source, SEMANTIC_SOURCES, "USER")
        participation = db.execute("SELECT person_id, organization_id FROM networking_event_participations WHERE id = ?", (participation_id,)).fetchone()
        if not participation:
            return
        inputs = self._semantic_inputs(data)
        resolved = []
        for entry in inputs:
            for value in entry["values"]:
                concept = self._resolve_event_concept(db, event_id, entry["type"], value)
                if not concept:
                    continue
                owner_type, owner_id = self._semantic_owner(participation, entry["role"], source)
                if not owner_id:
                    owner_type, owner_id = "PARTICIPATION", participation_id
                resolved.append((entry, concept, owner_type, owner_id))
        if source == "SOURCE":
            db.execute("DELETE FROM networking_semantic_classifications WHERE participation_id = ? AND source = 'SOURCE'", (participation_id,))
        roles = sorted({entry["role"] for entry, _concept, _owner_type, _owner_id in resolved})
        if source == "USER" and roles:
            db.execute(
                "DELETE FROM networking_semantic_classifications WHERE participation_id = ? AND source = 'USER' AND semantic_role IN ({})".format(",".join("?" for _ in roles)),
                [participation_id, *roles],
            )
        for entry, concept, owner_type, owner_id in resolved:
            now = self.now()
            db.execute(
                """
                INSERT INTO networking_semantic_classifications (
                    event_id, owner_type, owner_id, participation_id, concept_code, semantic_role,
                    source, provenance, visibility, free_text, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PUBLIC', ?, ?, ?)
                ON CONFLICT(event_id, owner_type, owner_id, concept_code, semantic_role, source)
                DO UPDATE SET participation_id = excluded.participation_id,
                              provenance = excluded.provenance,
                              free_text = COALESCE(NULLIF(excluded.free_text, ''), networking_semantic_classifications.free_text),
                              updated_at = excluded.updated_at
                """,
                (event_id, owner_type, owner_id, participation_id, concept["code"], entry["role"], source, provenance, str(data.get(entry.get("text_field", "")) or "").strip(), now, now),
            )

    def _semantic_owner(self, participation, role: str, source: str) -> tuple[str, int | None]:
        organization_id = int(participation["organization_id"]) if participation["organization_id"] else None
        person_id = int(participation["person_id"]) if participation["person_id"] else None
        if role in {"INDUSTRY", "SPECIALTY"}:
            return "ORGANIZATION", organization_id
        if role == "OFFER" and organization_id:
            return "ORGANIZATION", organization_id
        if role == "INTEREST" and person_id:
            return "PERSON", person_id
        return "PARTICIPATION", None

    def _semantic_inputs(self, data: dict) -> list[dict]:
        return [
            {"field": "organization_activity", "type": "INDUSTRY", "role": "INDUSTRY", "values": self._semantic_values(data.get("industry_concepts") or data.get("organization_activity_concepts") or data.get("organization_activity") or data.get("activity"))},
            {"field": "organization_specialty", "type": "SPECIALTY", "role": "SPECIALTY", "values": self._semantic_values(data.get("specialty_concepts") or data.get("organization_specialty_concepts") or data.get("organization_specialties") or data.get("organization_specialty") or data.get("specialty"))},
            {"field": "offer_concepts", "type": "OFFER", "role": "OFFER", "values": self._semantic_values(data.get("offer_concepts") or data.get("offers_concepts") or data.get("semantic_offers"))},
            {"field": "seek_concepts", "type": "SEEK", "role": "SEEK", "values": self._semantic_values(data.get("seek_concepts") or data.get("seeks_concepts") or data.get("semantic_seeks"))},
            {"field": "interest_concepts", "type": "INTEREST", "role": "INTEREST", "values": self._semantic_values(data.get("interest_concepts") or data.get("interests_concepts") or data.get("semantic_interests"))},
        ]

    def _resolve_event_concept(self, db, event_id: int, concept_type: str, value: str):
        concept_type = self._choice(concept_type, SEMANTIC_TYPES, "")
        clean = str(value or "").strip()
        if not concept_type or not clean:
            return None
        clean_key = self._canonical_key(clean)
        clean_code = clean.upper().replace(" ", "_").replace("-", "_")
        rows = db.execute(
            """
            SELECT tc.*, etc.label_override
            FROM networking_event_taxonomy_concepts etc
            JOIN networking_taxonomy_concepts tc ON tc.code = etc.concept_code
            WHERE etc.event_id = ? AND etc.enabled = 1 AND tc.active = 1 AND tc.concept_type = ?
            """,
            (event_id, concept_type),
        ).fetchall()
        for row in rows:
            labels = [row["code"], row["label"], row["label_override"] or ""]
            labels.extend(json.loads(row["aliases_json"] or "[]"))
            if clean_code == str(row["code"]).upper() or clean_key in {self._canonical_key(label) for label in labels if label}:
                return row
        return None

    def _upsert_taxonomy_concept(self, db, concept_type: str, label: str, *, code: str = "", explicit_code: bool = False, description: str = "", aliases: list[str] | None = None, parent_code: str = "") -> str:
        concept_type = self._choice(concept_type, SEMANTIC_TYPES, "")
        if not concept_type or not label:
            return ""
        generated = f"{concept_type}_{self._canonical_key(label).upper().replace('-', '_')}"
        code = str(code or generated).strip().upper().replace(" ", "_").replace("-", "_")
        existing = db.execute("SELECT code FROM networking_taxonomy_concepts WHERE code = ?", (code,)).fetchone()
        aliases_json = self._safe_json(sorted(set(aliases or [])))
        if existing:
            db.execute(
                """
                UPDATE networking_taxonomy_concepts
                SET concept_type = ?, label = COALESCE(NULLIF(?, ''), label),
                    description = COALESCE(NULLIF(?, ''), description),
                    parent_code = COALESCE(NULLIF(?, ''), parent_code),
                    aliases_json = ?, active = 1
                WHERE code = ?
                """,
                (concept_type, label, description, parent_code, aliases_json, code),
            )
            return code
        same_label = db.execute("SELECT code FROM networking_taxonomy_concepts WHERE concept_type = ? AND lower(label) = lower(?)", (concept_type, label)).fetchone()
        if same_label and not explicit_code:
            return same_label["code"]
        db.execute(
            """
            INSERT INTO networking_taxonomy_concepts (code, concept_type, label, description, parent_code, aliases_json, taxonomy_version, active)
            VALUES (?, ?, ?, ?, ?, ?, 'v1', 1)
            """,
            (code, concept_type, label, description, parent_code, aliases_json),
        )
        return code

    def _semantic_values(self, raw) -> list[str]:
        if raw is None:
            return []
        if isinstance(raw, str):
            raw = [part.strip() for part in re.split(r"[,;|]", raw)]
        result = []
        for value in raw or []:
            clean = str(value or "").strip()
            if clean and clean not in result:
                result.append(clean)
        return result

    def _completion_item(self, data: dict) -> dict:
        channels = data.get("channels") if isinstance(data.get("channels"), list) else []
        for channel in CHANNEL_TYPES:
            if data.get(channel):
                scope = "ORGANIZATION" if channel == "website" else "PERSONAL"
                channels.append({"type": channel, "value": str(data.get(channel)).strip(), "scope": scope, "visibility": data.get("channel_visibility_default") or "CONTACTS", "source": "participant"})
        return {"channels": channels}

    def _effective_readiness_mode(self, event_row) -> str:
        mode = self._presentation_mode(event_row["networking_profile_mode"] if event_row and "networking_profile_mode" in event_row.keys() else "AUTO")
        return "PERSON_FIRST" if mode == "AUTO" else mode

    def _readiness_keys(self, raw) -> list[str]:
        if raw is None:
            return []
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    raw = parsed
                else:
                    raw = [part.strip() for part in raw.split(",")]
            except json.JSONDecodeError:
                raw = [part.strip() for part in raw.split(",")]
        result = []
        for item in raw or []:
            key = str(item or "").strip()
            if key in READINESS_DIMENSIONS and key not in result:
                result.append(key)
        return result

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
            "organization_activity": str(row.get("organization_activity") or row.get("activity") or row.get("actividad") or row.get("sector") or "").strip(),
            "organization_specialty": str(row.get("organization_specialty") or row.get("specialty") or row.get("especialidad") or "").strip(),
            "organization_website": str(row.get("organization_website") or row.get("website") or "").strip(),
            "organization_description": str(row.get("organization_description") or "").strip(),
            "title": str(row.get("title") or row.get("position") or row.get("cargo") or "").strip(),
            "function_declared": "function" in row or "funcion" in row,
            "function": self._choice(row.get("function") or row.get("funcion"), FUNCTIONS, "OTHER"),
            "seniority_declared": "seniority" in row or "senioridad" in row,
            "seniority": self._choice(row.get("seniority") or row.get("senioridad"), SENIORITIES, "PROFESSIONAL"),
            "photo_url": str(row.get("photo_url") or row.get("foto") or "").strip(),
            "organization_logo_url": str(row.get("organization_logo_url") or row.get("logo") or "").strip(),
            "bio": str(row.get("bio") or row.get("description") or row.get("descripcion") or "").strip(),
            "offers": str(row.get("offers") or row.get("offers_text") or "").strip(),
            "seeks": str(row.get("seeks") or row.get("seeks_text") or "").strip(),
            "interests": str(row.get("interests") or row.get("interests_text") or "").strip(),
            "industry_concepts": row.get("industry_concepts") or row.get("organization_activity_concepts"),
            "specialty_concepts": row.get("specialty_concepts") or row.get("organization_specialty_concepts") or row.get("organization_specialties"),
            "offer_concepts": row.get("offer_concepts") or row.get("offers_concepts") or row.get("semantic_offers"),
            "seek_concepts": row.get("seek_concepts") or row.get("seeks_concepts") or row.get("semantic_seeks"),
            "interest_concepts": row.get("interest_concepts") or row.get("interests_concepts") or row.get("semantic_interests"),
            "channels": row.get("channels") if isinstance(row.get("channels"), list) else [],
        }
        visibility_map = row.get("channel_visibility") if isinstance(row.get("channel_visibility"), dict) else {}
        for channel in CHANNEL_TYPES:
            if row.get(channel):
                scope = "ORGANIZATION" if channel == "website" and item["company"] else "PERSONAL"
                item["channels"].append({"type": channel, "value": str(row.get(channel)).strip(), "scope": scope, "visibility": visibility_map.get(channel)})
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
                "UPDATE networking_organizations SET name = ?, visibility = COALESCE(NULLIF(?, ''), visibility), activity = COALESCE(NULLIF(?, ''), activity), specialty = COALESCE(NULLIF(?, ''), specialty), website = COALESCE(NULLIF(?, ''), website), logo_url = COALESCE(NULLIF(?, ''), logo_url), description = COALESCE(NULLIF(?, ''), description), updated_at = ? WHERE id = ?",
                (name, item.get("organization_visibility", ""), item.get("organization_activity", ""), item.get("organization_specialty", ""), item.get("organization_website", ""), item.get("organization_logo_url", ""), item.get("organization_description", ""), now, row["id"]),
            )
            return int(row["id"])
        return int(db.execute(
            "INSERT INTO networking_organizations (canonical_key, name, visibility, activity, specialty, website, logo_url, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (key, name, item.get("organization_visibility") or "PUBLIC", item.get("organization_activity", ""), item.get("organization_specialty", ""), item.get("organization_website", ""), item.get("organization_logo_url", ""), item.get("organization_description", ""), now, now),
        ).lastrowid)

    def _upsert_channels(self, db, participation_id: int, item: dict, *, preserve_user_visibility: bool) -> None:
        now = self.now()
        for raw in item.get("channels") or []:
            channel_type = str(raw.get("type") or raw.get("channel_type") or "").strip().lower()
            value = str(raw.get("value") or "").strip()
            if channel_type not in CHANNEL_TYPES or not value:
                continue
            visibility = self._choice(raw.get("visibility"), CHANNEL_VISIBILITY, "CONTACTS")
            scope = self._choice(raw.get("scope"), CHANNEL_SCOPES, "PERSONAL")
            existing = db.execute(
                "SELECT * FROM networking_contact_channels WHERE participation_id = ? AND channel_type = ? AND value = ?",
                (participation_id, channel_type, value),
            ).fetchone()
            if existing:
                if preserve_user_visibility:
                    db.execute("UPDATE networking_contact_channels SET label = ?, url = COALESCE(NULLIF(?, ''), url), scope = COALESCE(NULLIF(?, ''), scope), updated_at = ? WHERE id = ?", (str(raw.get("label") or ""), str(raw.get("url") or ""), scope, now, existing["id"]))
                else:
                    db.execute("UPDATE networking_contact_channels SET label = ?, url = ?, visibility = ?, scope = ?, updated_at = ? WHERE id = ?", (str(raw.get("label") or ""), str(raw.get("url") or ""), visibility, scope, now, existing["id"]))
            else:
                if preserve_user_visibility:
                    prior = db.execute(
                        "SELECT visibility FROM networking_contact_channels WHERE participation_id = ? AND channel_type = ? ORDER BY updated_at DESC, id DESC LIMIT 1",
                        (participation_id, channel_type),
                    ).fetchone()
                    if prior:
                        visibility = prior["visibility"]
                db.execute(
                    "INSERT INTO networking_contact_channels (participation_id, channel_type, label, value, url, visibility, scope, source, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (participation_id, channel_type, str(raw.get("label") or ""), value, str(raw.get("url") or ""), visibility, scope, str(raw.get("source") or "import"), now),
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

    def _presentation_mode(self, raw) -> str:
        return self._choice(raw, PRESENTATION_MODES, "AUTO")

    def _effective_presentation_mode(self, raw, profile: dict) -> str:
        mode = self._presentation_mode(raw)
        if mode == "AUTO":
            return "PERSON_FIRST"
        if mode == "ORGANIZATION_FIRST" and not profile.get("organization"):
            return "PERSON_FIRST"
        return mode

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

    def _safe_source_payload(self, item: dict) -> str:
        payload = {key: value for key, value in item.items() if key != "channels"}
        payload["channels"] = [
            {
                "type": channel.get("type") or channel.get("channel_type"),
                "scope": channel.get("scope") or "PERSONAL",
                "visibility": channel.get("visibility") or "CONTACTS",
                "source": channel.get("source") or item.get("source_system") or "import",
            }
            for channel in item.get("channels") or []
        ]
        return self._safe_json(payload)

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
