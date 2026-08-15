from __future__ import annotations

import hashlib
import csv
import io
import json
import re
import secrets
import unicodedata
from collections.abc import Callable
from urllib.parse import quote, urlparse


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
VOCABULARY_DIMENSIONS = {"INDUSTRY", "SPECIALTY", "OFFER", "SEEK", "INTEREST", "COMPANY_TYPE", "FUNCTION"}
VOCABULARY_STATUSES = {"CONFIGURED", "CANONICAL", "CANDIDATE", "DISABLED"}
DISCOVERY_MAX_BATCH = 5
NETWORKING_LAUNCH_STATES = {"DRAFT", "LIVE", "DISABLED"}
NETWORKING_BRAND_MODES = {"BITORA", "POWERED_BY_BITORA", "EVENT_BRANDED"}
DEFAULT_BRAND_PRIMARY = "#13243a"
DEFAULT_BRAND_ACCENT = "#d7a63f"
LOCAL_PUBLIC_HOSTS = {"localhost", "127.0.0.1", "::1", ""}
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
        discovery_completed INTEGER NOT NULL DEFAULT 0,
        discovery_diversity INTEGER NOT NULL DEFAULT 1,
        desired_functions_json TEXT NOT NULL DEFAULT '[]',
        desired_company_types_json TEXT NOT NULL DEFAULT '[]',
        discovery_objectives_json TEXT NOT NULL DEFAULT '[]',
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

    CREATE TABLE IF NOT EXISTS networking_event_vocabulary_candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        dimension TEXT NOT NULL,
        raw_value TEXT NOT NULL,
        normalized_key TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'CANDIDATE',
        concept_code TEXT REFERENCES networking_taxonomy_concepts(code) ON DELETE SET NULL,
        source TEXT NOT NULL DEFAULT 'USER',
        provenance TEXT NOT NULL DEFAULT '',
        usage_count INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(event_id, dimension, normalized_key)
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
    CREATE INDEX IF NOT EXISTS idx_networking_vocabulary_event_dimension ON networking_event_vocabulary_candidates(event_id, dimension, status);
    """


class NetworkingService:
    def __init__(self, now: Callable[[], str]) -> None:
        self.now = now

    def ensure_schema(self, db) -> None:
        db.executescript(networking_schema_sql())
        self.ensure_v1_1_schema(db)
        self.ensure_v1_2_schema(db)
        self.ensure_v1_3_schema(db)
        self.ensure_discovery_schema(db)
        self.ensure_v2_schema(db)
        self.ensure_v2_3_schema(db)
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

    def ensure_discovery_schema(self, db) -> None:
        intent_columns = {row["name"] for row in db.execute("PRAGMA table_info(networking_intents)").fetchall()}
        for column, ddl in {
            "discovery_completed": "INTEGER NOT NULL DEFAULT 0",
            "discovery_diversity": "INTEGER NOT NULL DEFAULT 1",
            "desired_functions_json": "TEXT NOT NULL DEFAULT '[]'",
            "desired_company_types_json": "TEXT NOT NULL DEFAULT '[]'",
            "discovery_objectives_json": "TEXT NOT NULL DEFAULT '[]'",
        }.items():
            if column not in intent_columns:
                db.execute(f"ALTER TABLE networking_intents ADD COLUMN {column} {ddl}")
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS networking_event_vocabulary_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                dimension TEXT NOT NULL,
                raw_value TEXT NOT NULL,
                normalized_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'CANDIDATE',
                concept_code TEXT REFERENCES networking_taxonomy_concepts(code) ON DELETE SET NULL,
                source TEXT NOT NULL DEFAULT 'USER',
                provenance TEXT NOT NULL DEFAULT '',
                usage_count INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(event_id, dimension, normalized_key)
            );
            CREATE INDEX IF NOT EXISTS idx_networking_vocabulary_event_dimension ON networking_event_vocabulary_candidates(event_id, dimension, status);
            """
        )

    def ensure_v2_schema(self, db) -> None:
        event_columns = {row["name"] for row in db.execute("PRAGMA table_info(events)").fetchall()}
        for column, ddl in {
            "networking_discovery_enabled": "INTEGER NOT NULL DEFAULT 1",
            "networking_discovery_exploration_frequency": "INTEGER NOT NULL DEFAULT 4",
            "networking_discovery_batch_size": "INTEGER NOT NULL DEFAULT 3",
        }.items():
            if column not in event_columns:
                db.execute(f"ALTER TABLE events ADD COLUMN {column} {ddl}")
        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_networking_interactions_actor_type
            ON networking_interaction_events(event_id, actor_participation_id, event_type, target_participation_id)
            """
        )

    def ensure_v2_3_schema(self, db) -> None:
        event_columns = {row["name"] for row in db.execute("PRAGMA table_info(events)").fetchall()}
        for column, ddl in {
            "landing_logo_data": "TEXT NOT NULL DEFAULT ''",
            "landing_primary_color": "TEXT NOT NULL DEFAULT ''",
            "landing_secondary_color": "TEXT NOT NULL DEFAULT ''",
            "networking_brand_title": "TEXT NOT NULL DEFAULT ''",
            "networking_brand_welcome": "TEXT NOT NULL DEFAULT ''",
            "networking_brand_mode": "TEXT NOT NULL DEFAULT 'POWERED_BY_BITORA'",
            "networking_public_base_url": "TEXT NOT NULL DEFAULT ''",
            "networking_launch_state": "TEXT NOT NULL DEFAULT 'DRAFT'",
            "networking_launched_at": "TEXT NOT NULL DEFAULT ''",
            "networking_launch_updated_at": "TEXT NOT NULL DEFAULT ''",
        }.items():
            if column not in event_columns:
                db.execute(f"ALTER TABLE events ADD COLUMN {column} {ddl}")

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
        row = db.execute(
            """
            SELECT id, name, networking_profile_mode, networking_readiness_required, networking_readiness_recommended,
                   networking_discovery_enabled, networking_discovery_exploration_frequency, networking_discovery_batch_size,
                   networking_launch_state, networking_public_base_url, networking_brand_title, networking_brand_welcome,
                   networking_brand_mode, landing_logo_data, landing_primary_color, landing_secondary_color
            FROM events
            WHERE id = ?
            """,
            (event_id,),
        ).fetchone()
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
            "networking_discovery_enabled": bool(int(row["networking_discovery_enabled"] if "networking_discovery_enabled" in row.keys() else 1)),
            "networking_discovery_exploration_frequency": max(2, int(row["networking_discovery_exploration_frequency"] if "networking_discovery_exploration_frequency" in row.keys() else 4)),
            "networking_discovery_batch_size": max(1, min(DISCOVERY_MAX_BATCH, int(row["networking_discovery_batch_size"] if "networking_discovery_batch_size" in row.keys() else 3))),
            "networking_launch_state": self._launch_state(row["networking_launch_state"] if "networking_launch_state" in row.keys() else ""),
            "networking_public_base_url": str(row["networking_public_base_url"] if "networking_public_base_url" in row.keys() else "").strip(),
            "networking_branding": self.event_branding(row),
            "semantic_taxonomy": self.event_taxonomy_payload(db, event_id).get("concepts", []),
        }

    def event_branding(self, event_row) -> dict:
        event_name = str(event_row["name"] if event_row and "name" in event_row.keys() else "").strip() or "Evento BITORA"
        title = str(event_row["networking_brand_title"] if event_row and "networking_brand_title" in event_row.keys() else "").strip() or event_name
        welcome = str(event_row["networking_brand_welcome"] if event_row and "networking_brand_welcome" in event_row.keys() else "").strip()
        mode = str(event_row["networking_brand_mode"] if event_row and "networking_brand_mode" in event_row.keys() else "").strip().upper() or "POWERED_BY_BITORA"
        if mode not in NETWORKING_BRAND_MODES:
            mode = "POWERED_BY_BITORA"
        primary = self._safe_hex_color(event_row["landing_primary_color"] if event_row and "landing_primary_color" in event_row.keys() else "", DEFAULT_BRAND_PRIMARY)
        accent = self._safe_hex_color(event_row["landing_secondary_color"] if event_row and "landing_secondary_color" in event_row.keys() else "", DEFAULT_BRAND_ACCENT)
        logo = str(event_row["landing_logo_data"] if event_row and "landing_logo_data" in event_row.keys() else "").strip()
        return {
            "title": title,
            "event_name": event_name,
            "welcome": welcome,
            "mode": mode,
            "logo": logo,
            "primary_color": primary,
            "accent_color": accent,
            "powered_by_bitora": mode in {"BITORA", "POWERED_BY_BITORA"},
            "has_custom_logo": bool(logo),
            "has_custom_primary": primary != DEFAULT_BRAND_PRIMARY,
        }

    def get_event_brand(self, db, event_id: int, *, fallback_base_url: str = "", app_env: str = "development") -> dict:
        row = self._event_launch_row(db, event_id)
        if not row:
            return {"ok": False, "error": "Evento inexistente", "status_code": 404}
        brand = self.event_branding(row)
        return {
            "ok": True,
            "event_id": int(row["id"]),
            "event_name": row["name"],
            "branding": brand,
            "networking_launch_state": self._launch_state(row["networking_launch_state"]),
            "networking_public_base_url": str(row["networking_public_base_url"] or "").strip(),
            "effective_public_base_url": self._event_public_base_url(row, fallback_base_url),
            "public_url_validation": self.validate_public_base_url(str(row["networking_public_base_url"] or "").strip() or fallback_base_url, app_env=app_env),
        }

    def update_event_brand(self, db, event_id: int, data: dict, actor: str = "Admin") -> dict:
        row = self._event_launch_row(db, event_id)
        if not row:
            return {"ok": False, "error": "Evento inexistente", "status_code": 404}
        title = self._compact_text(data.get("networking_brand_title") or data.get("brand_title"), 96)
        welcome = self._compact_text(data.get("networking_brand_welcome") or data.get("brand_welcome"), 220)
        mode = str(data.get("networking_brand_mode") or data.get("brand_mode") or row["networking_brand_mode"] or "POWERED_BY_BITORA").strip().upper()
        if mode not in NETWORKING_BRAND_MODES:
            mode = "POWERED_BY_BITORA"
        public_base_url = self._normalize_base_url(data.get("networking_public_base_url") if "networking_public_base_url" in data else row["networking_public_base_url"])
        primary = self._safe_hex_color(data.get("landing_primary_color") if "landing_primary_color" in data else row["landing_primary_color"], "")
        secondary = self._safe_hex_color(data.get("landing_secondary_color") if "landing_secondary_color" in data else row["landing_secondary_color"], "")
        logo = str(data.get("landing_logo_data") if "landing_logo_data" in data else row["landing_logo_data"] or "").strip()
        if logo and not (logo.startswith("data:image/") or logo.startswith("/") or logo.startswith("http://") or logo.startswith("https://")):
            return {"ok": False, "error": "Logo invalido: usa data:image, una ruta local o una URL segura", "status_code": 400}
        db.execute(
            """
            UPDATE events
            SET networking_brand_title = ?,
                networking_brand_welcome = ?,
                networking_brand_mode = ?,
                networking_public_base_url = ?,
                landing_primary_color = ?,
                landing_secondary_color = ?,
                landing_logo_data = ?
            WHERE id = ?
            """,
            (title, welcome, mode, public_base_url, primary, secondary, logo, event_id),
        )
        self.record_event(db, event_id, None, None, "launch_brand_updated", {"actor": actor, "brand_mode": mode, "public_base_url_configured": bool(public_base_url)})
        return self.get_event_brand(db, event_id)

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

    def launch_readiness(self, db, event_id: int, *, fallback_base_url: str = "", app_env: str = "development") -> dict:
        event = self._event_launch_row(db, event_id)
        if not event:
            return {"ok": False, "error": "Evento inexistente", "status_code": 404}
        operations = self.operations_summary(db, event_id, include_launch=False)
        checks = []

        def add(key: str, severity: str, message: str, action: str = ""):
            checks.append({"key": key, "severity": severity, "message": message, "action": action})

        brand = self.event_branding(event)
        launch_state = self._launch_state(event["networking_launch_state"])
        public_base_url = self._event_public_base_url(event, fallback_base_url)
        url_validation = self.validate_public_base_url(public_base_url, app_env=app_env)
        participant_total = int((operations.get("participants") or {}).get("total") or 0) if operations.get("ok") else 0
        discovery_enabled = bool((operations.get("discovery") or {}).get("enabled")) if operations.get("ok") else False
        vocabulary = operations.get("vocabulary") or {}
        pool = ((operations.get("discovery") or {}).get("pool") or {}) if operations.get("ok") else {}

        add("EVENT_CONFIGURED", "INFO", f"Evento configurado: {event['name']}.")
        if not brand["has_custom_logo"]:
            add("BRAND_LOGO_MISSING", "WARNING", "No hay logo de evento configurado; se usara la marca BITORA por defecto.", "Cargar logo si el evento requiere identidad propia.")
        else:
            add("BRAND_LOGO_CONFIGURED", "INFO", "Logo de evento configurado.")
        if not url_validation["ok"]:
            add(url_validation["code"], "BLOCKING", url_validation["message"], "Configurar una URL publica valida para Networking.")
        else:
            add("PUBLIC_URL_VALID", "INFO", url_validation["message"])
        sample_profile = db.execute(
            """
            SELECT public_profile_id
            FROM networking_event_participations
            WHERE event_id = ? AND participation_state = 'ACTIVE'
            ORDER BY id
            LIMIT 1
            """,
            (event_id,),
        ).fetchone()
        if sample_profile:
            add("QR_DEEP_LINK_READY", "INFO", "Los QR pueden generar un enlace publico de Networking.")
        else:
            add("QR_DEEP_LINK_NO_ACTIVE_PROFILE", "WARNING", "Todavia no hay perfiles ACTIVE para verificar un QR real.", "Activar al menos un participante de prueba.")
        if participant_total <= 0:
            add("NO_PARTICIPANTS", "BLOCKING", "No hay participantes importados para lanzar Networking.", "Importar participantes antes del lanzamiento.")
        elif participant_total < 2:
            add("VERY_SMALL_EVENT", "WARNING", "Hay muy pocos participantes; el intercambio de contactos sera limitado.")
        else:
            add("PARTICIPANTS_IMPORTED", "INFO", f"{participant_total} participantes disponibles para preparar Networking.")
        incomplete = int((operations.get("participants") or {}).get("incomplete") or 0) if operations.get("ok") else 0
        if incomplete:
            add("INCOMPLETE_PROFILES", "WARNING", f"{incomplete} perfiles tienen gaps de readiness.", "Revisar preparacion antes del lanzamiento si esos perfiles seran invitados.")
        if discovery_enabled:
            if int(vocabulary.get("active_concepts") or 0) + int(vocabulary.get("represented_concepts") or 0) <= 0:
                add("DISCOVERY_VOCABULARY_WEAK", "WARNING", "Discovery esta habilitado pero no hay vocabulario util todavia.", "Configurar vocabulario o importar datos semanticos.")
            if int(pool.get("discoverable_participants") or 0) < 2 and participant_total > 1:
                add("DISCOVERY_POOL_SMALL", "WARNING", "Discovery tiene pocas oportunidades visibles con la configuracion actual.", "Revisar privacidad, activacion y datos de participantes.")
            add("DISCOVERY_CONFIGURED", "INFO", "Discovery esta habilitado como feature opcional.")
        else:
            add("DISCOVERY_DISABLED", "INFO", "Discovery esta deshabilitado; la credencial, QR y contactos pueden lanzarse igualmente.")

        status = "READY"
        if any(item["severity"] == "BLOCKING" for item in checks):
            status = "NOT_READY"
        elif any(item["severity"] == "WARNING" for item in checks):
            status = "READY_WITH_WARNINGS"
        return {
            "ok": True,
            "event": {"id": int(event["id"]), "name": event["name"]},
            "launch_state": launch_state,
            "status": status,
            "status_label": {"READY": "Listo", "READY_WITH_WARNINGS": "Listo con advertencias", "NOT_READY": "No listo"}[status],
            "blocking": [item for item in checks if item["severity"] == "BLOCKING"],
            "warnings": [item for item in checks if item["severity"] == "WARNING"],
            "checks": checks,
            "branding": brand,
            "public_url": {
                "configured_base_url": str(event["networking_public_base_url"] or "").strip(),
                "effective_base_url": public_base_url,
                "sample_profile_url": f"{public_base_url}/n/{sample_profile['public_profile_id']}" if sample_profile and public_base_url else "",
                "validation": url_validation,
            },
            "operations_status": operations.get("status") if operations.get("ok") else "UNKNOWN",
        }

    def update_launch_state(self, db, event_id: int, action: str, *, actor: str = "Admin", fallback_base_url: str = "", app_env: str = "development") -> dict:
        event = self._event_launch_row(db, event_id)
        if not event:
            return {"ok": False, "error": "Evento inexistente", "status_code": 404}
        action_key = str(action or "").strip().upper()
        if action_key in {"LAUNCH", "LIVE", "ENABLE", "REENABLE"}:
            readiness = self.launch_readiness(db, event_id, fallback_base_url=fallback_base_url, app_env=app_env)
            if readiness.get("blocking"):
                return {"ok": False, "error": "Networking no esta listo para lanzar", "status_code": 409, "readiness": readiness}
            state = "LIVE"
        elif action_key in {"DISABLE", "DISABLED", "CLOSE"}:
            readiness = self.launch_readiness(db, event_id, fallback_base_url=fallback_base_url, app_env=app_env)
            state = "DISABLED"
        elif action_key in {"DRAFT", "PRELAUNCH", "RESET"}:
            readiness = self.launch_readiness(db, event_id, fallback_base_url=fallback_base_url, app_env=app_env)
            state = "DRAFT"
        else:
            return {"ok": False, "error": "Accion de lanzamiento invalida", "status_code": 400}
        now = self.now()
        launched_at = now if state == "LIVE" and not str(event["networking_launched_at"] or "").strip() else str(event["networking_launched_at"] or "")
        db.execute(
            "UPDATE events SET networking_launch_state = ?, networking_launched_at = ?, networking_launch_updated_at = ? WHERE id = ?",
            (state, launched_at, now, event_id),
        )
        self.record_event(db, event_id, None, None, "launch_state_updated", {"actor": actor, "state": state})
        readiness = self.launch_readiness(db, event_id, fallback_base_url=fallback_base_url, app_env=app_env)
        return {"ok": True, "event_id": event_id, "networking_launch_state": state, "readiness": readiness}

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
        existing = db.execute(
            """
            SELECT networking_readiness_required, networking_readiness_recommended,
                   networking_discovery_enabled, networking_discovery_exploration_frequency, networking_discovery_batch_size
            FROM events
            WHERE id = ?
            """,
            (event_id,),
        ).fetchone()
        if "networking_readiness_required" in data or "readiness_required" in data:
            required = self._readiness_keys(data.get("networking_readiness_required") if "networking_readiness_required" in data else data.get("readiness_required"))
        else:
            required = self._readiness_keys(existing["networking_readiness_required"] if existing else "")
        if "networking_readiness_recommended" in data or "readiness_recommended" in data:
            recommended = self._readiness_keys(data.get("networking_readiness_recommended") if "networking_readiness_recommended" in data else data.get("readiness_recommended"))
        else:
            recommended = self._readiness_keys(existing["networking_readiness_recommended"] if existing else "")
        recommended = [key for key in recommended if key not in required]
        if "networking_discovery_enabled" in data or "discovery_enabled" in data:
            discovery_enabled = 1 if self._truthy(data.get("networking_discovery_enabled") if "networking_discovery_enabled" in data else data.get("discovery_enabled")) else 0
        else:
            discovery_enabled = int(existing["networking_discovery_enabled"] if existing and "networking_discovery_enabled" in existing.keys() else 1)
        exploration_frequency = int(data.get("networking_discovery_exploration_frequency") or data.get("discovery_exploration_frequency") or (existing["networking_discovery_exploration_frequency"] if existing and "networking_discovery_exploration_frequency" in existing.keys() else 4) or 4)
        exploration_frequency = max(2, min(12, exploration_frequency))
        batch_size = int(data.get("networking_discovery_batch_size") or data.get("discovery_batch_size") or (existing["networking_discovery_batch_size"] if existing and "networking_discovery_batch_size" in existing.keys() else 3) or 3)
        batch_size = max(1, min(DISCOVERY_MAX_BATCH, batch_size))
        db.execute(
            """
            UPDATE events
            SET networking_profile_mode = ?,
                networking_readiness_required = ?,
                networking_readiness_recommended = ?,
                networking_discovery_enabled = ?,
                networking_discovery_exploration_frequency = ?,
                networking_discovery_batch_size = ?
            WHERE id = ?
            """,
            (mode, ",".join(required), ",".join(recommended), discovery_enabled, exploration_frequency, batch_size, event_id),
        )
        self.record_event(db, event_id, None, None, "event_config_updated", {"actor": actor, "networking_profile_mode": mode, "readiness_required": required, "readiness_recommended": recommended, "discovery_enabled": bool(discovery_enabled)})
        row = db.execute(
            """
            SELECT id, name, networking_profile_mode, networking_readiness_required, networking_readiness_recommended,
                   networking_discovery_enabled, networking_discovery_exploration_frequency, networking_discovery_batch_size
            FROM events
            WHERE id = ?
            """,
            (event_id,),
        ).fetchone()
        readiness = self.readiness_config(row)
        return {
            "ok": True,
            "event_id": event_id,
            "networking_profile_mode": mode,
            "networking_readiness_required": readiness["required"],
            "networking_readiness_recommended": readiness["recommended"],
            "networking_discovery_enabled": bool(int(row["networking_discovery_enabled"] if "networking_discovery_enabled" in row.keys() else 1)),
            "networking_discovery_exploration_frequency": max(2, int(row["networking_discovery_exploration_frequency"] if "networking_discovery_exploration_frequency" in row.keys() else 4)),
            "networking_discovery_batch_size": max(1, min(DISCOVERY_MAX_BATCH, int(row["networking_discovery_batch_size"] if "networking_discovery_batch_size" in row.keys() else 3))),
        }

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
        self._harvest_vocabulary_candidates(db, event_id, item, source="SOURCE", provenance=item["source_system"])
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
        self._harvest_vocabulary_candidates(db, int(participation["event_id"]), data, source="USER", provenance="onboarding")
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
        self._harvest_vocabulary_candidates(db, int(participation["event_id"]), data, source="USER", provenance="completion")
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
        contact = self._create_or_refresh_contact(db, owner, target)
        contact_id = contact["contact_id"]
        created = contact["created"]
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
        is_self = viewer and int(viewer["id"]) == int(row["id"])
        event = self._event_launch_row(db, int(row["event_id"]))
        launch_state = self._launch_state(event["networking_launch_state"] if event else "")
        same_event_viewer = viewer and int(viewer["event_id"]) == int(row["event_id"])
        if self._launch_gate_configured(event) and not (is_self or same_event_viewer) and launch_state != "LIVE":
            return {
                "ok": False,
                "error": "Networking todavia no esta disponible para este evento",
                "status": "NOT_LIVE" if launch_state == "DRAFT" else "DISABLED",
                "status_code": 404,
            }
        intent = db.execute("SELECT profile_visible FROM networking_intents WHERE participation_id = ?", (row["id"],)).fetchone()
        if intent and not is_self and not int(intent["profile_visible"] or 0):
            return {"ok": False, "error": "Perfil Networking no visible", "status_code": 404}
        return {"ok": True, "profile": self.participation_payload(db, int(row["id"]), viewer_id=int(viewer["id"]) if viewer else None, full=bool(viewer))}

    def participation_payload(self, db, participation_id: int, *, viewer_id: int | None, full: bool) -> dict:
        row = db.execute(
            """
            SELECT nep.*, p.first_name, p.last_name, p.email, p.phone, p.company,
                   e.name AS event_name, e.networking_profile_mode, e.networking_readiness_required, e.networking_readiness_recommended,
                   e.networking_launch_state, e.networking_public_base_url, e.networking_brand_title, e.networking_brand_welcome,
                   e.networking_brand_mode, e.landing_logo_data, e.landing_primary_color, e.landing_secondary_color,
                   no.name AS organization_name, no.activity AS organization_activity, no.specialty AS organization_specialty,
                   no.website AS organization_website, no.logo_url AS organization_logo,
                   no.description AS organization_description, no.visibility AS organization_visibility,
                   ni.modes_json, ni.direction, ni.contact_openness, ni.discoverable, ni.profile_visible,
                   ni.channels_visible_default, ni.representative_visible, ni.bio, ni.offers_text, ni.seeks_text, ni.interests_text,
                   ni.discovery_completed, ni.discovery_diversity, ni.desired_functions_json, ni.desired_company_types_json, ni.discovery_objectives_json,
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
            "credential": {
                "type": "DIGITAL_EVENT_CREDENTIAL",
                "public_path": f"/n/{data['public_profile_id']}",
                "public_url": self._profile_public_url(data, data["public_profile_id"]),
                "qr_kind": "HTTPS_DEEP_LINK",
            },
            "event_id": data["event_id"],
            "event_name": data.get("event_name") or "",
            "event_branding": self.event_branding(data),
            "networking_launch_state": self._launch_state(data.get("networking_launch_state") or ""),
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
        profile["discovery"] = self.discovery_payload(profile, data)
        if is_self:
            profile["owner_token_hint"] = data.get("owner_token_hint") or ""
            profile["email"] = data.get("email") or ""
        return profile

    def discovery_payload(self, profile: dict, data: dict) -> dict:
        desired_functions = self._json_list(data.get("desired_functions_json"))
        desired_company_types = self._json_list(data.get("desired_company_types_json"))
        objectives = self._json_list(data.get("discovery_objectives_json"))
        completed = bool(int(data.get("discovery_completed") or 0))
        missing = []
        if not (profile.get("semantic", {}).get("seeks") or profile.get("seeks")):
            missing.append("seeks")
        if not (profile.get("semantic", {}).get("offers") or profile.get("semantic", {}).get("organization_offers") or profile.get("offers")):
            missing.append("offers")
        if not desired_company_types:
            missing.append("company_types")
        if not desired_functions:
            missing.append("functions")
        status = "READY" if completed and not missing else "NOT_CONFIGURED"
        return {
            "status": status,
            "ready": status == "READY",
            "completed": completed,
            "diversity": bool(int(data.get("discovery_diversity") if data.get("discovery_diversity") is not None else 1)),
            "desired_functions": desired_functions,
            "desired_company_types": desired_company_types,
            "objectives": objectives,
            "missing": missing,
            "entry_label": "Discovery listo" if status == "READY" else "Activar Discovery",
        }

    def live_vocabulary(self, db, event_id: int, *, include_candidates: bool = False) -> dict:
        if not db.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone():
            return {"ok": False, "error": "Evento inexistente", "status_code": 404}
        result = {dimension: [] for dimension in sorted(VOCABULARY_DIMENSIONS)}
        configured = db.execute(
            """
            SELECT tc.code, tc.concept_type, COALESCE(NULLIF(etc.label_override, ''), tc.label) AS label,
                   etc.enabled, etc.sort_order,
                   COALESCE((
                       SELECT COUNT(*)
                       FROM networking_semantic_classifications sc
                       WHERE sc.event_id = etc.event_id AND sc.concept_code = tc.code
                   ), 0) AS usage_count
            FROM networking_event_taxonomy_concepts etc
            JOIN networking_taxonomy_concepts tc ON tc.code = etc.concept_code
            WHERE etc.event_id = ? AND etc.enabled = 1 AND tc.active = 1
            ORDER BY usage_count DESC, etc.sort_order, label
            """,
            (event_id,),
        ).fetchall()
        seen: dict[str, set[str]] = {dimension: set() for dimension in result}
        for row in configured:
            dimension = self._vocabulary_dimension(row["concept_type"])
            if dimension not in result:
                continue
            key = str(row["code"])
            seen[dimension].add(key)
            result[dimension].append({"value": key, "label": row["label"], "kind": "concept", "source": "configured", "usage_count": int(row["usage_count"] or 0)})
        candidates = db.execute(
            """
            SELECT *
            FROM networking_event_vocabulary_candidates
            WHERE event_id = ? AND status != 'DISABLED'
            ORDER BY usage_count DESC, raw_value
            """,
            (event_id,),
        ).fetchall() if include_candidates else []
        for row in candidates:
            dimension = self._vocabulary_dimension(row["dimension"])
            if dimension not in result:
                continue
            value = row["concept_code"] or f"CANDIDATE:{row['id']}"
            if value in seen[dimension]:
                continue
            seen[dimension].add(value)
            result[dimension].append({
                "value": value,
                "label": row["raw_value"],
                "kind": "candidate" if not row["concept_code"] else "concept",
                "source": row["source"],
                "status": row["status"],
                "usage_count": int(row["usage_count"] or 0),
            })
        result["FUNCTION"] = [
            {"value": code, "label": code.replace("_", " ").title(), "kind": "function", "source": "system", "usage_count": 0}
            for code in sorted(FUNCTIONS)
        ]
        return {"ok": True, "event_id": event_id, "vocabulary": result}

    def discovery_onboarding(self, db, owner_token: str, data: dict) -> dict:
        participation = self.resolve_owner(db, owner_token, int(data.get("event_id") or 0) or None)
        if not participation:
            return {"ok": False, "error": "Acceso Networking invalido", "status_code": 404}
        event_id = int(participation["event_id"])
        participation_id = int(participation["id"])
        desired_functions = [self._choice(value, FUNCTIONS, "") for value in self._semantic_values(data.get("desired_functions") or data.get("functions"))]
        desired_functions = [value for value in desired_functions if value]
        desired_company_types = self._discovery_values(db, event_id, "COMPANY_TYPE", data.get("desired_company_types") or data.get("company_types"))
        objectives = self._discovery_values(db, event_id, "INTEREST", data.get("objectives") or data.get("interests"))
        semantic_data = {
            "seek_concepts": self._discovery_values(db, event_id, "SEEK", data.get("seek_concepts") or data.get("seeks")),
            "offer_concepts": self._discovery_values(db, event_id, "OFFER", data.get("offer_concepts") or data.get("offers")),
            "interest_concepts": objectives,
        }
        if data.get("seeks_text"):
            semantic_data["seeks"] = str(data.get("seeks_text") or "").strip()
        if data.get("offers_text"):
            semantic_data["offers"] = str(data.get("offers_text") or "").strip()
        self._sync_semantic_classifications(db, event_id, participation_id, semantic_data, source="USER", provenance="discovery")
        self._harvest_vocabulary_candidates(db, event_id, semantic_data, source="USER", provenance="discovery")
        for value in desired_company_types:
            self._upsert_vocabulary_candidate(db, event_id, "COMPANY_TYPE", value, source="USER", provenance="discovery")
        for value in objectives:
            self._upsert_vocabulary_candidate(db, event_id, "INTEREST", value, source="USER", provenance="discovery")
        db.execute(
            """
            UPDATE networking_intents
            SET discovery_completed = 1,
                discovery_diversity = ?,
                desired_functions_json = ?,
                desired_company_types_json = ?,
                discovery_objectives_json = ?,
                updated_at = ?
            WHERE participation_id = ?
            """,
            (
                1 if self._truthy(data.get("discovery_diversity", True)) else 0,
                self._safe_json(desired_functions),
                self._safe_json(desired_company_types),
                self._safe_json(objectives),
                self.now(),
                participation_id,
            ),
        )
        self.record_event(db, event_id, participation_id, None, "discovery_onboarded", {"desired_functions": desired_functions, "desired_company_types": desired_company_types, "objectives": objectives})
        profile = self.participation_payload(db, participation_id, viewer_id=participation_id, full=True)
        return {
            "ok": True,
            "participation": profile,
            "discovery": {
                "ok": True,
                "status": profile.get("discovery", {}).get("status") or "READY",
                "ready": bool(profile.get("discovery", {}).get("ready")),
                "message": "Discovery listo. BITORA va a mostrar oportunidades una por una.",
                "items": [],
                "exhausted": False,
            },
        }

    def discovery_shell(self, db, owner_token: str) -> dict:
        participation = self.resolve_owner(db, owner_token)
        if not participation:
            return {"ok": False, "error": "Acceso Networking invalido", "status_code": 404}
        profile = self.participation_payload(db, int(participation["id"]), viewer_id=int(participation["id"]), full=True)
        discovery = profile.get("discovery") or {}
        event_config = self.discovery_event_config(db, int(participation["event_id"]))
        if not event_config["enabled"]:
            return {
                "ok": True,
                "status": "DISABLED",
                "ready": False,
                "message": "Discovery no esta habilitado para este evento.",
                "profile": profile,
                "items": [],
                "exhausted": True,
            }
        if discovery.get("ready"):
            stream = self.discovery_stream(db, owner_token)
            stream["profile"] = profile
            return stream
        return {
            "ok": True,
            "status": discovery.get("status") or "NOT_CONFIGURED",
            "ready": bool(discovery.get("ready")),
            "message": "Completa el Golden Ticket para preparar Discovery.",
            "profile": profile,
            "items": [],
            "exhausted": False,
        }

    def discovery_event_config(self, db, event_id: int) -> dict:
        row = db.execute(
            """
            SELECT networking_discovery_enabled, networking_discovery_exploration_frequency, networking_discovery_batch_size
            FROM events
            WHERE id = ?
            """,
            (event_id,),
        ).fetchone()
        return {
            "enabled": bool(int(row["networking_discovery_enabled"] if row and "networking_discovery_enabled" in row.keys() else 1)),
            "exploration_frequency": max(2, min(12, int(row["networking_discovery_exploration_frequency"] if row and "networking_discovery_exploration_frequency" in row.keys() else 4))),
            "batch_size": max(1, min(DISCOVERY_MAX_BATCH, int(row["networking_discovery_batch_size"] if row and "networking_discovery_batch_size" in row.keys() else 3))),
        }

    def discovery_stream(self, db, owner_token: str, *, limit: int | None = None) -> dict:
        owner = self.resolve_owner(db, owner_token)
        if not owner:
            return {"ok": False, "error": "Acceso Networking invalido", "status_code": 404}
        if owner["participation_state"] != "ACTIVE":
            return {"ok": False, "error": "Activa tu credencial antes de usar Discovery", "status_code": 409}
        config = self.discovery_event_config(db, int(owner["event_id"]))
        if not config["enabled"]:
            return {
                "ok": True,
                "status": "DISABLED",
                "ready": False,
                "message": "Discovery no esta habilitado para este evento.",
                "items": [],
                "exhausted": True,
            }
        owner_profile = self.participation_payload(db, int(owner["id"]), viewer_id=int(owner["id"]), full=True)
        if not (owner_profile.get("discovery") or {}).get("ready"):
            return {
                "ok": True,
                "status": "NOT_CONFIGURED",
                "ready": False,
                "message": "Completa el Golden Ticket para preparar Discovery.",
                "items": [],
                "exhausted": False,
            }
        batch_size = max(1, min(DISCOVERY_MAX_BATCH, int(limit or config["batch_size"])))
        recent_targets = self._recent_discovery_target_ids(db, int(owner["event_id"]), int(owner["id"]), limit=3)
        recent_orgs = self._recent_discovery_organizations(db, int(owner["event_id"]), int(owner["id"]), limit=4)
        candidates = self._discovery_candidates(db, owner, owner_profile, mode="fresh", recent_target_ids=recent_targets)
        stream_phase = "fresh"
        if not candidates:
            candidates = self._discovery_candidates(db, owner, owner_profile, mode="recycle", recent_target_ids=recent_targets)
            stream_phase = "recycle" if candidates else "exhausted"
        scored = [item for item in (self._score_discovery_candidate(owner_profile, candidate, config) for candidate in candidates) if item["relevance"] > 0 or owner_profile.get("discovery", {}).get("diversity")]
        ordered = self._order_discovery_candidates(scored, owner_profile, config, recent_orgs=recent_orgs)
        fresh = ordered[:batch_size]
        for item in fresh[:1]:
            event_type = "discovery_recycled" if stream_phase == "recycle" else "discovery_shown"
            self.record_event(db, int(owner["event_id"]), int(owner["id"]), int(item["profile"]["participation_id"]), event_type, {"reasons": [reason["code"] for reason in item["reasons"]], "bucket": item["bucket"], "phase": stream_phase})
        public_items = [self._public_discovery_item(item, phase=stream_phase) for item in fresh]
        exhausted = not fresh
        message = "Estas viendo oportunidades nuevas del evento segun tus preferencias."
        if stream_phase == "recycle" and not exhausted:
            message = "Ya viste las oportunidades nuevas. Te mostramos algunas que quizas quieras reconsiderar."
        if exhausted:
            message = "Ya recorriste las oportunidades disponibles por ahora."
            self._record_discovery_exhausted_once(db, int(owner["event_id"]), int(owner["id"]))
        return {
            "ok": True,
            "status": "READY" if stream_phase == "fresh" and not exhausted else ("RECYCLE" if stream_phase == "recycle" and not exhausted else "EXHAUSTED"),
            "ready": True,
            "message": message,
            "items": public_items,
            "exhausted": exhausted,
            "phase": stream_phase,
            "actions": {"empty": ["adjust_preferences", "return_credential"] if exhausted else []},
        }

    def discovery_action(self, db, owner_token: str, data: dict) -> dict:
        owner = self.resolve_owner(db, owner_token, int(data.get("event_id") or 0) or None)
        if not owner:
            return {"ok": False, "error": "Acceso Networking invalido", "status_code": 404}
        if owner["participation_state"] != "ACTIVE":
            return {"ok": False, "error": "Activa tu credencial antes de usar Discovery", "status_code": 409}
        action = str(data.get("action") or "").strip().lower().replace("-", "_")
        if action not in {"skip", "save", "open_profile", "channel_opened"}:
            return {"ok": False, "error": "Accion Discovery invalida", "status_code": 400}
        target = self._resolve_discovery_target(db, owner, data)
        if not target:
            return {"ok": False, "error": "Perfil Discovery no disponible", "status_code": 404}
        event_type = {
            "skip": "discovery_skipped",
            "save": "discovery_saved",
            "open_profile": "discovery_profile_opened",
            "channel_opened": "discovery_channel_opened",
        }[action]
        payload = {"source": "discovery"}
        result = {"ok": True, "action": action}
        if action == "save":
            contact = self._create_or_refresh_contact(db, owner, target)
            payload["contact_id"] = contact["contact_id"]
            payload["created"] = contact["created"]
            result.update(contact)
        should_record = True
        if action == "skip":
            should_record = not bool(db.execute(
                """
                SELECT 1
                FROM networking_interaction_events
                WHERE event_id = ? AND actor_participation_id = ? AND target_participation_id = ? AND event_type = 'discovery_skipped'
                """,
                (owner["event_id"], owner["id"], target["id"]),
            ).fetchone())
        if should_record:
            self.record_event(db, int(owner["event_id"]), int(owner["id"]), int(target["id"]), event_type, payload)
        result["profile"] = self.participation_payload(db, int(target["id"]), viewer_id=int(owner["id"]), full=True)
        result["next"] = self.discovery_stream(db, owner_token)
        return result

    def _discovery_candidates(self, db, owner, owner_profile: dict, *, mode: str, recent_target_ids: set[int]) -> list[dict]:
        preference_epoch = self._last_discovery_preference_at(db, int(owner["event_id"]), int(owner["id"]))
        recent_clause = ""
        params: list = [owner["event_id"], owner["id"], owner["id"]]
        if recent_target_ids:
            recent_clause = "AND nep.id NOT IN ({})".format(",".join("?" for _ in recent_target_ids))
            params.extend(sorted(recent_target_ids))
        if mode == "fresh":
            history_clause = """
              AND NOT EXISTS (
                  SELECT 1
                  FROM networking_interaction_events ie
                  WHERE ie.event_id = nep.event_id
                    AND ie.actor_participation_id = ?
                    AND ie.target_participation_id = nep.id
                    AND ie.event_type IN ('discovery_shown', 'discovery_recycled', 'discovery_skipped', 'discovery_saved')
              )
            """
            params.append(owner["id"])
            order_clause = "ORDER BY nep.updated_at DESC, nep.id DESC"
        else:
            history_clause = """
              AND EXISTS (
                  SELECT 1
                  FROM networking_interaction_events skipped
                  WHERE skipped.event_id = nep.event_id
                    AND skipped.actor_participation_id = ?
                    AND skipped.target_participation_id = nep.id
                    AND skipped.event_type = 'discovery_skipped'
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM networking_interaction_events saved
                  WHERE saved.event_id = nep.event_id
                    AND saved.actor_participation_id = ?
                    AND saved.target_participation_id = nep.id
                    AND saved.event_type = 'discovery_saved'
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM networking_interaction_events recycled
                  WHERE recycled.event_id = nep.event_id
                    AND recycled.actor_participation_id = ?
                    AND recycled.target_participation_id = nep.id
                    AND recycled.event_type = 'discovery_recycled'
                    AND recycled.created_at >= ?
              )
            """
            params.extend([owner["id"], owner["id"], owner["id"], preference_epoch])
            order_clause = """
            ORDER BY (
                SELECT MIN(skipped.created_at)
                FROM networking_interaction_events skipped
                WHERE skipped.event_id = nep.event_id
                  AND skipped.actor_participation_id = ?
                  AND skipped.target_participation_id = nep.id
                  AND skipped.event_type = 'discovery_skipped'
            ) ASC, nep.id ASC
            """
            params.append(owner["id"])
        rows = db.execute(
            f"""
            SELECT nep.id
            FROM networking_event_participations nep
            JOIN networking_intents ni ON ni.participation_id = nep.id
            WHERE nep.event_id = ?
              AND nep.id != ?
              AND nep.participation_state = 'ACTIVE'
              AND ni.discoverable = 1
              AND ni.profile_visible = 1
              AND NOT EXISTS (
                  SELECT 1
                  FROM networking_contacts c
                  WHERE c.owner_participation_id = ? AND c.target_participation_id = nep.id AND c.status = 'ACTIVE'
              )
              {recent_clause}
              {history_clause}
            {order_clause}
            LIMIT 60
            """,
            params,
        ).fetchall()
        candidates = []
        for row in rows:
            profile = self.participation_payload(db, int(row["id"]), viewer_id=int(owner["id"]), full=True)
            presentation = profile.get("presentation") or {}
            primary = presentation.get("primary") or {}
            meaningful = bool(primary.get("title") or profile.get("organization") or profile.get("name"))
            if meaningful:
                candidates.append(profile)
        return candidates

    def _score_discovery_candidate(self, owner_profile: dict, candidate_profile: dict, config: dict) -> dict:
        reasons = []
        score = 0
        owner_seek = self._semantic_key_set(owner_profile, "seeks")
        owner_offer = self._semantic_key_set(owner_profile, "offers", "organization_offers")
        candidate_offer = self._semantic_key_set(candidate_profile, "offers", "organization_offers")
        candidate_seek = self._semantic_key_set(candidate_profile, "seeks")
        common = owner_seek & candidate_offer
        if common:
            score += 80
            reasons.append(self._reason("SEEK_OFFER_MATCH", "Ofrece algo que estas buscando", candidate_profile, common, "offers", "organization_offers"))
        reverse_common = owner_offer & candidate_seek
        if reverse_common:
            score += 50
            reasons.append(self._reason("OFFER_SEEK_MATCH", "Busca algo que podes ofrecer", candidate_profile, reverse_common, "seeks"))

        desired_company_types = self._preference_key_set((owner_profile.get("discovery") or {}).get("desired_company_types") or [])
        candidate_sector = self._semantic_key_set(candidate_profile, "industries", "specialties")
        candidate_sector.update(self._text_key_set([candidate_profile.get("organization_activity"), candidate_profile.get("organization_specialty")]))
        sector_common = desired_company_types & candidate_sector
        if sector_common:
            score += 30
            reasons.append(self._reason("PREFERRED_SECTOR", "Pertenece a un rubro que elegiste", candidate_profile, sector_common, "industries", "specialties"))

        desired_functions = {str(value or "").strip().upper() for value in (owner_profile.get("discovery") or {}).get("desired_functions") or [] if value}
        candidate_function = str(candidate_profile.get("function") or "").strip().upper()
        if candidate_function and candidate_function in desired_functions:
            score += 30
            reasons.append({"code": "DESIRED_FUNCTION", "label": "Trabaja en un area que queres contactar", "supporting_label": candidate_function.replace("_", " ").title()})

        objectives = self._preference_key_set((owner_profile.get("discovery") or {}).get("objectives") or [])
        candidate_interests = self._semantic_key_set(candidate_profile, "interests")
        interest_common = objectives & candidate_interests
        if interest_common:
            score += 18
            reasons.append(self._reason("SHARED_OBJECTIVE", "Comparte un objetivo del evento", candidate_profile, interest_common, "interests"))

        if not reasons:
            if (owner_profile.get("discovery") or {}).get("diversity"):
                score += 5
                reasons.append({"code": "EXPLORATION", "label": "Oportunidad fuera de tus preferencias", "supporting_label": ""})
            else:
                reasons.append({"code": "GENERAL_EVENT", "label": "Perfil disponible en este evento", "supporting_label": ""})
        return {
            "profile": candidate_profile,
            "reasons": reasons[:3],
            "bucket": "aligned" if score >= 18 else "exploration",
            "relevance": score,
        }

    def _order_discovery_candidates(self, scored: list[dict], owner_profile: dict, config: dict, *, recent_orgs: list[str]) -> list[dict]:
        scored = sorted(scored, key=lambda item: (-int(item["relevance"]), self._canonical_key(item["profile"].get("public_profile_id") or "")))
        recent_org_keys = {self._canonical_key(org) for org in recent_orgs if org}
        if recent_org_keys and any(self._canonical_key(item["profile"].get("organization") or "") not in recent_org_keys for item in scored):
            scored = sorted(
                scored,
                key=lambda item: (
                    1 if self._canonical_key(item["profile"].get("organization") or "") in recent_org_keys else 0,
                    -int(item["relevance"]),
                    self._canonical_key(item["profile"].get("public_profile_id") or ""),
                ),
            )
        aligned = [item for item in scored if item["bucket"] == "aligned"]
        exploration = [item for item in scored if item["bucket"] != "aligned"]
        if not (owner_profile.get("discovery") or {}).get("diversity"):
            return aligned
        frequency = max(2, int(config.get("exploration_frequency") or 4))
        result = []
        aligned_index = 0
        exploration_index = 0
        while aligned_index < len(aligned) or exploration_index < len(exploration):
            if exploration_index < len(exploration) and result and len(result) % frequency == frequency - 1:
                result.append(exploration[exploration_index])
                exploration_index += 1
            elif aligned_index < len(aligned):
                result.append(aligned[aligned_index])
                aligned_index += 1
            elif exploration_index < len(exploration):
                result.append(exploration[exploration_index])
                exploration_index += 1
        return self._avoid_adjacent_organization_repetition(result)

    def _avoid_adjacent_organization_repetition(self, items: list[dict]) -> list[dict]:
        result = []
        pending = list(items)
        last_org = None
        while pending:
            pick_index = 0
            if last_org:
                for index, item in enumerate(pending):
                    org = item["profile"].get("organization") or ""
                    if org != last_org:
                        pick_index = index
                        break
            item = pending.pop(pick_index)
            result.append(item)
            last_org = item["profile"].get("organization") or ""
        return result

    def _public_discovery_item(self, item: dict, *, phase: str) -> dict:
        return {
            "profile": item["profile"],
            "reasons": item["reasons"],
            "bucket": item["bucket"],
            "phase": phase,
        }

    def _last_discovery_preference_at(self, db, event_id: int, owner_id: int) -> str:
        row = db.execute(
            """
            SELECT MAX(created_at) AS last_at
            FROM networking_interaction_events
            WHERE event_id = ? AND actor_participation_id = ? AND event_type = 'discovery_onboarded'
            """,
            (event_id, owner_id),
        ).fetchone()
        return row["last_at"] if row and row["last_at"] else ""

    def _record_discovery_exhausted_once(self, db, event_id: int, owner_id: int) -> None:
        preference_epoch = self._last_discovery_preference_at(db, event_id, owner_id)
        exists = db.execute(
            """
            SELECT 1
            FROM networking_interaction_events
            WHERE event_id = ?
              AND actor_participation_id = ?
              AND event_type = 'discovery_exhausted'
              AND created_at >= ?
            """,
            (event_id, owner_id, preference_epoch),
        ).fetchone()
        if not exists:
            self.record_event(db, event_id, owner_id, None, "discovery_exhausted", {"preference_epoch": preference_epoch})

    def _recent_discovery_target_ids(self, db, event_id: int, owner_id: int, *, limit: int) -> set[int]:
        rows = db.execute(
            """
            SELECT target_participation_id
            FROM networking_interaction_events
            WHERE event_id = ?
              AND actor_participation_id = ?
              AND target_participation_id IS NOT NULL
              AND event_type IN ('discovery_shown', 'discovery_recycled', 'discovery_skipped')
            ORDER BY id DESC
            LIMIT ?
            """,
            (event_id, owner_id, max(1, int(limit))),
        ).fetchall()
        return {int(row["target_participation_id"]) for row in rows if row["target_participation_id"]}

    def _recent_discovery_organizations(self, db, event_id: int, owner_id: int, *, limit: int) -> list[str]:
        rows = db.execute(
            """
            SELECT COALESCE(no.name, p.company, '') AS organization
            FROM networking_interaction_events ie
            JOIN networking_event_participations nep ON nep.id = ie.target_participation_id
            JOIN people p ON p.id = nep.person_id
            LEFT JOIN networking_organizations no ON no.id = nep.organization_id
            WHERE ie.event_id = ?
              AND ie.actor_participation_id = ?
              AND ie.target_participation_id IS NOT NULL
              AND ie.event_type IN ('discovery_shown', 'discovery_recycled', 'discovery_skipped')
            ORDER BY ie.id DESC
            LIMIT ?
            """,
            (event_id, owner_id, max(1, int(limit))),
        ).fetchall()
        result = []
        for row in rows:
            org = str(row["organization"] or "").strip()
            if org and org not in result:
                result.append(org)
        return result

    def _resolve_discovery_target(self, db, owner, data: dict):
        public_id = str(data.get("public_profile_id") or data.get("profile_id") or "").strip().upper()
        target_id = int(data.get("target_participation_id") or 0)
        params = [owner["event_id"], owner["id"]]
        selector = "nep.id = ?"
        params.append(target_id)
        if public_id:
            selector = "nep.public_profile_id = ?"
            params[-1] = public_id
        if not public_id and not target_id:
            return None
        return db.execute(
            f"""
            SELECT nep.*
            FROM networking_event_participations nep
            JOIN networking_intents ni ON ni.participation_id = nep.id
            WHERE nep.event_id = ?
              AND nep.id != ?
              AND {selector}
              AND nep.participation_state = 'ACTIVE'
              AND ni.discoverable = 1
              AND ni.profile_visible = 1
            """,
            params,
        ).fetchone()

    def _create_or_refresh_contact(self, db, owner, target) -> dict:
        now = self.now()
        existing = db.execute(
            "SELECT * FROM networking_contacts WHERE owner_participation_id = ? AND target_participation_id = ?",
            (owner["id"], target["id"]),
        ).fetchone()
        if existing:
            db.execute("UPDATE networking_contacts SET status = 'ACTIVE', updated_at = ? WHERE id = ?", (now, existing["id"]))
            return {"created": False, "contact_id": int(existing["id"])}
        contact_id = int(db.execute(
            """
            INSERT INTO networking_contacts (event_id, owner_participation_id, target_participation_id, status, created_at, updated_at)
            VALUES (?, ?, ?, 'ACTIVE', ?, ?)
            """,
            (owner["event_id"], owner["id"], target["id"], now, now),
        ).lastrowid)
        return {"created": True, "contact_id": contact_id}

    def _semantic_key_set(self, profile: dict, *groups: str) -> set[str]:
        semantic = profile.get("semantic") or {}
        keys: set[str] = set()
        for group in groups:
            for item in semantic.get(group) or []:
                keys.update(self._text_key_set([item.get("code"), item.get("label"), item.get("text")]))
        text_fields = {
            "offers": [profile.get("offers")],
            "organization_offers": [profile.get("offers")],
            "seeks": [profile.get("seeks")],
            "interests": [profile.get("interests")],
            "industries": [profile.get("organization_activity")],
            "specialties": [profile.get("organization_specialty")],
        }
        for group in groups:
            keys.update(self._text_key_set(text_fields.get(group) or []))
        return keys

    def _preference_key_set(self, values: list) -> set[str]:
        return self._text_key_set(values)

    def _text_key_set(self, values: list) -> set[str]:
        keys: set[str] = set()
        for value in values or []:
            for part in self._semantic_values(value):
                keys.add(self._canonical_key(part))
        return {key for key in keys if key}

    def _reason(self, code: str, label: str, candidate_profile: dict, common_keys: set[str], *groups: str) -> dict:
        supporting = ""
        semantic = candidate_profile.get("semantic") or {}
        for group in groups:
            for item in semantic.get(group) or []:
                item_keys = self._text_key_set([item.get("code"), item.get("label"), item.get("text")])
                if common_keys & item_keys:
                    supporting = item.get("label") or item.get("text") or ""
                    break
            if supporting:
                break
        if not supporting:
            for value in [candidate_profile.get("organization_activity"), candidate_profile.get("organization_specialty"), candidate_profile.get("offers"), candidate_profile.get("seeks"), candidate_profile.get("interests")]:
                if common_keys & self._text_key_set([value]):
                    supporting = str(value or "").strip()
                    break
        return {"code": code, "label": label, "supporting_label": supporting}

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

    def operations_summary(self, db, event_id: int, *, include_launch: bool = True, fallback_base_url: str = "", app_env: str = "development") -> dict:
        event = db.execute(
            """
            SELECT id, name, status, networking_profile_mode,
                   networking_discovery_enabled, networking_discovery_exploration_frequency, networking_discovery_batch_size,
                   networking_launch_state, networking_public_base_url, networking_brand_title, networking_brand_welcome,
                   networking_brand_mode, landing_logo_data, landing_primary_color, landing_secondary_color
            FROM events
            WHERE id = ?
            """,
            (event_id,),
        ).fetchone()
        if not event:
            return {"ok": False, "error": "Evento inexistente", "status_code": 404}

        readiness = self.readiness_summary(db, event_id, include_participants=False)
        state_rows = db.execute(
            """
            SELECT participation_state, COUNT(*) AS total
            FROM networking_event_participations
            WHERE event_id = ?
            GROUP BY participation_state
            """,
            (event_id,),
        ).fetchall()
        states = {str(row["participation_state"] or "UNKNOWN").upper(): int(row["total"] or 0) for row in state_rows}
        participants_total = int(readiness.get("total") or 0)

        discovery_config = self.discovery_event_config(db, event_id)
        discovery_counts = db.execute(
            """
            SELECT
                COUNT(DISTINCT CASE WHEN ni.discovery_completed = 1 THEN nep.id END) AS configured,
                COUNT(DISTINCT CASE WHEN ie.event_type IN (
                    'discovery_shown', 'discovery_recycled', 'discovery_skipped', 'discovery_saved',
                    'discovery_profile_opened', 'discovery_channel_opened', 'discovery_exhausted'
                ) THEN ie.actor_participation_id END) AS users,
                SUM(CASE WHEN ie.event_type IN ('discovery_shown', 'discovery_recycled') THEN 1 ELSE 0 END) AS shown,
                SUM(CASE WHEN ie.event_type = 'discovery_skipped' THEN 1 ELSE 0 END) AS skipped,
                SUM(CASE WHEN ie.event_type = 'discovery_saved' THEN 1 ELSE 0 END) AS saved,
                SUM(CASE WHEN ie.event_type = 'discovery_exhausted' THEN 1 ELSE 0 END) AS exhausted_events,
                COUNT(DISTINCT CASE WHEN ie.event_type = 'discovery_exhausted' THEN ie.actor_participation_id END) AS exhausted_users
            FROM networking_event_participations nep
            LEFT JOIN networking_intents ni ON ni.participation_id = nep.id
            LEFT JOIN networking_interaction_events ie ON ie.event_id = nep.event_id AND ie.actor_participation_id = nep.id
            WHERE nep.event_id = ?
            """,
            (event_id,),
        ).fetchone()

        contact_counts = db.execute(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(DISTINCT owner_participation_id) AS owners,
                COUNT(DISTINCT target_participation_id) AS targets
            FROM networking_contacts
            WHERE event_id = ? AND status = 'ACTIVE'
            """,
            (event_id,),
        ).fetchone()
        interaction_contact_counts = db.execute(
            """
            SELECT
                SUM(CASE WHEN event_type = 'scan_contact' THEN 1 ELSE 0 END) AS scan_events,
                SUM(CASE WHEN event_type = 'discovery_saved' THEN 1 ELSE 0 END) AS discovery_saved_events
            FROM networking_interaction_events
            WHERE event_id = ?
            """,
            (event_id,),
        ).fetchone()

        pool = db.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN nep.participation_state = 'ACTIVE'
                          AND COALESCE(ni.discoverable, 0) = 1
                          AND COALESCE(ni.profile_visible, 0) = 1 THEN 1 ELSE 0 END) AS discoverable,
                SUM(CASE WHEN nep.participation_state != 'ACTIVE'
                          OR COALESCE(ni.discoverable, 0) = 0
                          OR COALESCE(ni.profile_visible, 0) = 0 THEN 1 ELSE 0 END) AS blocked,
                COUNT(DISTINCT CASE WHEN nep.participation_state = 'ACTIVE'
                          AND COALESCE(ni.discoverable, 0) = 1
                          AND COALESCE(ni.profile_visible, 0) = 1
                          THEN COALESCE(CAST(nep.organization_id AS TEXT), NULLIF(TRIM(p.company), ''), 'person-' || nep.id) END) AS organizations
            FROM networking_event_participations nep
            JOIN people p ON p.id = nep.person_id
            LEFT JOIN networking_intents ni ON ni.participation_id = nep.id
            WHERE nep.event_id = ?
            """,
            (event_id,),
        ).fetchone()

        vocabulary = db.execute(
            """
            SELECT
                (SELECT COUNT(*)
                 FROM networking_event_taxonomy_concepts etc
                 JOIN networking_taxonomy_concepts tc ON tc.code = etc.concept_code
                 WHERE etc.event_id = ? AND etc.enabled = 1 AND tc.active = 1) AS active_concepts,
                (SELECT COUNT(DISTINCT concept_code)
                 FROM networking_semantic_classifications
                 WHERE event_id = ? AND concept_code IS NOT NULL) AS represented_concepts,
                (SELECT COUNT(*)
                 FROM networking_event_vocabulary_candidates
                 WHERE event_id = ? AND status = 'CANDIDATE') AS unresolved_candidates,
                (SELECT COUNT(*)
                 FROM networking_event_vocabulary_candidates
                 WHERE event_id = ? AND status = 'CANONICAL') AS canonical_candidates,
                (SELECT COUNT(*)
                 FROM networking_semantic_classifications
                 WHERE event_id = ? AND semantic_role IN ('OFFER', 'ORG_OFFER')) AS offers,
                (SELECT COUNT(*)
                 FROM networking_semantic_classifications
                 WHERE event_id = ? AND semantic_role = 'SEEK') AS seeks
            """,
            (event_id, event_id, event_id, event_id, event_id, event_id),
        ).fetchone()

        warnings = self._operations_warnings(
            total=participants_total,
            readiness=readiness,
            discovery_enabled=bool(discovery_config["enabled"]),
            discovery_configured=int(discovery_counts["configured"] or 0),
            active=int(states.get("ACTIVE", 0)),
            discoverable=int(pool["discoverable"] or 0),
            vocabulary=vocabulary,
        )
        status = "READY"
        if any(item["severity"] == "CRITICAL" for item in warnings):
            status = "NOT_READY"
        elif any(item["severity"] == "WARNING" for item in warnings):
            status = "NEEDS_ATTENTION"

        summary = {
            "ok": True,
            "event": {
                "id": int(event["id"]),
                "name": event["name"],
                "status": event["status"],
            },
            "status": status,
            "status_label": {"READY": "Listo", "NEEDS_ATTENTION": "Necesita atencion", "NOT_READY": "No listo"}[status],
            "configuration": {
                "profile_mode": event["networking_profile_mode"],
                "discovery_enabled": bool(discovery_config["enabled"]),
                "discovery_batch_size": int(discovery_config["batch_size"]),
                "discovery_exploration_frequency": int(discovery_config["exploration_frequency"]),
                "networking_launch_state": self._launch_state(event["networking_launch_state"] if "networking_launch_state" in event.keys() else ""),
                "networking_public_base_url": str(event["networking_public_base_url"] if "networking_public_base_url" in event.keys() else "").strip(),
            },
            "participants": {
                "total": participants_total,
                "passive": int(states.get("PASSIVE", 0)),
                "active": int(states.get("ACTIVE", 0)),
                "paused": int(states.get("PAUSED", 0)),
                "revoked": int(states.get("REVOKED", 0)),
                "ready": int(readiness.get("ready") or 0),
                "incomplete": int(readiness.get("incomplete") or 0),
                "common_missing": readiness.get("common_missing") or {},
            },
            "networking": {
                "contacts_total": int(contact_counts["total"] or 0),
                "contact_owners": int(contact_counts["owners"] or 0),
                "contact_targets": int(contact_counts["targets"] or 0),
                "scan_contact_events": int(interaction_contact_counts["scan_events"] or 0),
                "discovery_saved_events": int(interaction_contact_counts["discovery_saved_events"] or 0),
            },
            "discovery": {
                "enabled": bool(discovery_config["enabled"]),
                "configured_participants": int(discovery_counts["configured"] or 0),
                "users": int(discovery_counts["users"] or 0),
                "profiles_shown": int(discovery_counts["shown"] or 0),
                "skips": int(discovery_counts["skipped"] or 0),
                "saved": int(discovery_counts["saved"] or 0),
                "exhausted_users": int(discovery_counts["exhausted_users"] or 0),
                "exhausted_events": int(discovery_counts["exhausted_events"] or 0),
                "pool": {
                    "participants_total": int(pool["total"] or 0),
                    "discoverable_participants": int(pool["discoverable"] or 0),
                    "blocked_by_state_or_privacy": int(pool["blocked"] or 0),
                    "organizations_represented": int(pool["organizations"] or 0),
                },
            },
            "vocabulary": {
                "active_concepts": int(vocabulary["active_concepts"] or 0),
                "represented_concepts": int(vocabulary["represented_concepts"] or 0),
                "unresolved_candidates": int(vocabulary["unresolved_candidates"] or 0),
                "canonical_candidates": int(vocabulary["canonical_candidates"] or 0),
                "offers": int(vocabulary["offers"] or 0),
                "seeks": int(vocabulary["seeks"] or 0),
            },
            "warnings": warnings,
            "funnel": {
                "imported": participants_total,
                "active": int(states.get("ACTIVE", 0)),
                "basic_ready": int(readiness.get("ready") or 0),
                "discovery_configured": int(discovery_counts["configured"] or 0),
                "discovery_used": int(discovery_counts["users"] or 0),
                "contacts_created": int(contact_counts["total"] or 0),
            },
            "definitions": self._operations_metric_definitions(),
        }
        if include_launch:
            summary["launch"] = self.launch_readiness(db, event_id, fallback_base_url=fallback_base_url, app_env=app_env)
        return summary

    def operations_export_csv(self, db, event_id: int, *, fallback_base_url: str = "", app_env: str = "development") -> str:
        summary = self.operations_summary(db, event_id, fallback_base_url=fallback_base_url, app_env=app_env)
        if not summary.get("ok"):
            return ""
        output = io.StringIO()
        headers = [
            "event_id", "event_name", "status", "launch_state", "launch_status", "participants_total", "participants_active",
            "profiles_ready", "profiles_incomplete", "discovery_enabled", "discovery_configured",
            "discovery_users", "discovery_profiles_shown", "discovery_skips", "discovery_saved",
            "discovery_exhausted_users", "contacts_total", "scan_contact_events",
            "discovery_saved_events", "active_vocabulary_concepts", "unresolved_vocabulary_candidates",
            "warning_count", "critical_warning_count",
        ]
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerow({
            "event_id": summary["event"]["id"],
            "event_name": self._csv_safe(summary["event"]["name"]),
            "status": self._csv_safe(summary["status"]),
            "launch_state": self._csv_safe((summary.get("launch") or {}).get("launch_state") or summary.get("configuration", {}).get("networking_launch_state", "DRAFT")),
            "launch_status": self._csv_safe((summary.get("launch") or {}).get("status") or ""),
            "participants_total": summary["participants"]["total"],
            "participants_active": summary["participants"]["active"],
            "profiles_ready": summary["participants"]["ready"],
            "profiles_incomplete": summary["participants"]["incomplete"],
            "discovery_enabled": int(bool(summary["discovery"]["enabled"])),
            "discovery_configured": summary["discovery"]["configured_participants"],
            "discovery_users": summary["discovery"]["users"],
            "discovery_profiles_shown": summary["discovery"]["profiles_shown"],
            "discovery_skips": summary["discovery"]["skips"],
            "discovery_saved": summary["discovery"]["saved"],
            "discovery_exhausted_users": summary["discovery"]["exhausted_users"],
            "contacts_total": summary["networking"]["contacts_total"],
            "scan_contact_events": summary["networking"]["scan_contact_events"],
            "discovery_saved_events": summary["networking"]["discovery_saved_events"],
            "active_vocabulary_concepts": summary["vocabulary"]["active_concepts"],
            "unresolved_vocabulary_candidates": summary["vocabulary"]["unresolved_candidates"],
            "warning_count": len(summary["warnings"]),
            "critical_warning_count": sum(1 for item in summary["warnings"] if item["severity"] == "CRITICAL"),
        })
        return output.getvalue()

    def _csv_safe(self, value) -> str:
        text = str(value if value is not None else "")
        stripped = text.lstrip()
        if stripped.startswith(("=", "+", "-", "@")):
            return "'" + text
        return text

    def _operations_warnings(self, *, total: int, readiness: dict, discovery_enabled: bool, discovery_configured: int, active: int, discoverable: int, vocabulary, ) -> list[dict]:
        warnings = []
        if total == 0:
            warnings.append({"severity": "WARNING", "code": "NO_PARTICIPANTS", "message": "Importa participantes para comenzar la preparacion de Networking."})
            return warnings
        incomplete = int(readiness.get("incomplete") or 0)
        if incomplete:
            warnings.append({"severity": "WARNING", "code": "INCOMPLETE_PROFILES", "message": f"{incomplete} perfiles necesitan completar datos obligatorios para Networking."})
        if active == 0:
            warnings.append({"severity": "INFO", "code": "NO_ACTIVE_PARTICIPANTS", "message": "Todavia no hay participantes activos. Es esperable antes del evento."})
        if discovery_enabled:
            if discoverable < 2 and total > 1:
                warnings.append({"severity": "WARNING", "code": "DISCOVERY_SMALL_POOL", "message": "Discovery tiene muy pocas oportunidades disponibles con el estado actual."})
            if discovery_configured == 0 and active > 0:
                warnings.append({"severity": "INFO", "code": "DISCOVERY_NOT_USED_YET", "message": "Discovery esta habilitado, pero aun nadie completo el Golden Ticket."})
            if int(vocabulary["active_concepts"] or 0) == 0 and int(vocabulary["represented_concepts"] or 0) == 0:
                warnings.append({"severity": "WARNING", "code": "DISCOVERY_EMPTY_VOCABULARY", "message": "Discovery esta activo pero el vocabulario del evento todavia no tiene conceptos utiles."})
            if int(vocabulary["offers"] or 0) == 0:
                warnings.append({"severity": "WARNING", "code": "DISCOVERY_NO_OFFERS", "message": "Discovery esta activo pero casi no hay ofertas estructuradas para alimentar oportunidades."})
            if int(vocabulary["seeks"] or 0) == 0:
                warnings.append({"severity": "INFO", "code": "DISCOVERY_NO_SEEKS", "message": "Aun hay pocas busquedas declaradas; el Golden Ticket puede mejorar la demanda del evento."})
        else:
            warnings.append({"severity": "INFO", "code": "DISCOVERY_DISABLED", "message": "Discovery esta deshabilitado. La credencial, QR y contactos siguen disponibles."})
        unresolved = int(vocabulary["unresolved_candidates"] or 0)
        if unresolved:
            warnings.append({"severity": "INFO", "code": "VOCABULARY_UNRESOLVED", "message": f"Hay {unresolved} valores de vocabulario vivo pendientes de normalizar."})
        return warnings

    def _operations_metric_definitions(self) -> dict:
        return {
            "participants.total": "EventParticipations del evento.",
            "participants.active": "EventParticipations con estado ACTIVE; no equivale a READY.",
            "participants.ready": "Perfiles READY segun el evaluador de readiness V1.2.",
            "discovery.configured_participants": "Participantes con preferencias Discovery completadas.",
            "discovery.users": "Participantes con interacciones Discovery registradas.",
            "discovery.profiles_shown": "Eventos discovery_shown y discovery_recycled.",
            "networking.contacts_total": "Contactos canonicos ACTIVE del evento.",
            "networking.discovery_saved_events": "Acciones Discovery Guardar registradas; historico segun eventos disponibles.",
            "vocabulary.unresolved_candidates": "Valores vivos CANDIDATE pendientes de normalizacion.",
        }

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

    def _harvest_vocabulary_candidates(self, db, event_id: int, data: dict, *, source: str, provenance: str) -> None:
        for entry in self._semantic_inputs(data):
            for value in entry["values"]:
                concept = self._resolve_event_concept(db, event_id, entry["type"], value)
                self._upsert_vocabulary_candidate(
                    db,
                    event_id,
                    self._vocabulary_dimension(entry["role"]),
                    value,
                    source=source,
                    provenance=provenance,
                    concept_code=concept["code"] if concept else "",
                    status="CANONICAL" if concept else "CANDIDATE",
                )
        for dimension, raw in {
            "OFFER": data.get("offers") or data.get("offers_text"),
            "SEEK": data.get("seeks") or data.get("seeks_text"),
            "INTEREST": data.get("interests") or data.get("interests_text"),
        }.items():
            for value in self._semantic_values(raw):
                self._upsert_vocabulary_candidate(db, event_id, dimension, value, source=source, provenance=provenance)

    def _upsert_vocabulary_candidate(self, db, event_id: int, dimension: str, raw_value: str, *, source: str, provenance: str, concept_code: str = "", status: str = "CANDIDATE") -> None:
        dimension = self._vocabulary_dimension(dimension)
        status = self._choice(status, VOCABULARY_STATUSES, "CANDIDATE")
        raw_value = str(raw_value or "").strip()
        if not event_id or dimension not in VOCABULARY_DIMENSIONS or not raw_value:
            return
        key = self._canonical_key(raw_value)
        now = self.now()
        db.execute(
            """
            INSERT INTO networking_event_vocabulary_candidates (
                event_id, dimension, raw_value, normalized_key, status, concept_code,
                source, provenance, usage_count, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, NULLIF(?, ''), ?, ?, 1, ?, ?)
            ON CONFLICT(event_id, dimension, normalized_key)
            DO UPDATE SET raw_value = COALESCE(NULLIF(excluded.raw_value, ''), networking_event_vocabulary_candidates.raw_value),
                          status = CASE
                              WHEN networking_event_vocabulary_candidates.status = 'DISABLED' THEN 'DISABLED'
                              WHEN excluded.status = 'CANONICAL' THEN 'CANONICAL'
                              ELSE networking_event_vocabulary_candidates.status
                          END,
                          concept_code = COALESCE(excluded.concept_code, networking_event_vocabulary_candidates.concept_code),
                          source = excluded.source,
                          provenance = excluded.provenance,
                          usage_count = networking_event_vocabulary_candidates.usage_count + 1,
                          updated_at = excluded.updated_at
            """,
            (event_id, dimension, raw_value, key, status, concept_code, source, provenance, now, now),
        )

    def _discovery_values(self, db, event_id: int, dimension: str, raw) -> list[str]:
        result = []
        for value in self._semantic_values(raw):
            text = str(value or "").strip()
            if not text:
                continue
            if text.startswith("CANDIDATE:"):
                candidate_id = int(text.split(":", 1)[1] or 0)
                row = db.execute("SELECT raw_value FROM networking_event_vocabulary_candidates WHERE id = ? AND event_id = ?", (candidate_id, event_id)).fetchone()
                text = row["raw_value"] if row else ""
            elif text.upper() in FUNCTIONS and dimension == "FUNCTION":
                text = text.upper()
            else:
                concept = self._resolve_event_concept(db, event_id, self._vocabulary_dimension(dimension), text)
                text = concept["code"] if concept else text
            if text and text not in result:
                result.append(text)
        return result

    def _vocabulary_dimension(self, value: str) -> str:
        value = str(value or "").strip().upper()
        aliases = {
            "ACTIVITY": "INDUSTRY",
            "SECTOR": "INDUSTRY",
            "RUBRO": "INDUSTRY",
            "OBJECTIVE": "INTEREST",
            "OBJECTIVES": "INTEREST",
            "COMPANY": "COMPANY_TYPE",
            "COMPANY_TYPES": "COMPANY_TYPE",
            "FUNCTIONS": "FUNCTION",
        }
        return aliases.get(value, value)

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

    def _event_launch_row(self, db, event_id: int):
        return db.execute(
            """
            SELECT id, name, status, networking_profile_mode, networking_readiness_required, networking_readiness_recommended,
                   networking_discovery_enabled, networking_discovery_exploration_frequency, networking_discovery_batch_size,
                   networking_launch_state, networking_public_base_url, networking_brand_title, networking_brand_welcome,
                   networking_brand_mode, networking_launched_at, networking_launch_updated_at,
                   landing_logo_data, landing_primary_color, landing_secondary_color
            FROM events
            WHERE id = ?
            """,
            (event_id,),
        ).fetchone()

    def _event_public_base_url(self, event_row, fallback_base_url: str = "") -> str:
        configured = str(event_row["networking_public_base_url"] if event_row and "networking_public_base_url" in event_row.keys() else "").strip()
        return self._normalize_base_url(configured or fallback_base_url or "")

    def _profile_public_url(self, data: dict, public_profile_id: str) -> str:
        base_url = self._event_public_base_url(data, "")
        return f"{base_url}/n/{public_profile_id}" if base_url else f"/n/{public_profile_id}"

    def _launch_state(self, raw) -> str:
        state = str(raw or "").strip().upper()
        return state if state in NETWORKING_LAUNCH_STATES else "DRAFT"

    def _launch_gate_configured(self, event_row) -> bool:
        if not event_row:
            return False
        if self._launch_state(event_row["networking_launch_state"] if "networking_launch_state" in event_row.keys() else "") != "DRAFT":
            return True
        return any(
            str(event_row[key] if key in event_row.keys() else "").strip()
            for key in ("networking_public_base_url", "networking_brand_title", "networking_launch_updated_at", "networking_launched_at")
        )

    def _normalize_base_url(self, value) -> str:
        return str(value or "").strip().rstrip("/")

    def _safe_hex_color(self, value, default: str = "") -> str:
        raw = str(value or "").strip()
        if re.fullmatch(r"#[0-9a-fA-F]{6}", raw):
            return raw.lower()
        if re.fullmatch(r"[0-9a-fA-F]{6}", raw):
            return f"#{raw.lower()}"
        return default

    def _compact_text(self, value, limit: int) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip())[:limit]

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

    def public_profile_link(self, db, public_profile_id: str, *, fallback_base_url: str = "") -> dict:
        row = db.execute(
            """
            SELECT nep.public_profile_id, e.*
            FROM networking_event_participations nep
            JOIN events e ON e.id = nep.event_id
            WHERE nep.public_profile_id = ?
            """,
            (str(public_profile_id or "").strip().upper(),),
        ).fetchone()
        if not row:
            return {"ok": False, "error": "Perfil Networking inexistente", "status_code": 404}
        base_url = self._event_public_base_url(row, fallback_base_url)
        return {"ok": True, "url": f"{base_url}/n/{row['public_profile_id']}", "launch_state": self._launch_state(row["networking_launch_state"])}

    def validate_public_base_url(self, value: str, *, app_env: str = "development") -> dict:
        raw = self._normalize_base_url(value)
        if not raw:
            return {"ok": False, "code": "PUBLIC_URL_MISSING", "message": "Falta configurar la URL publica usada por los QR de Networking."}
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return {"ok": False, "code": "PUBLIC_URL_INVALID", "message": "La URL publica debe incluir esquema y host, por ejemplo https://evento.example.com."}
        host = (parsed.hostname or "").strip().lower()
        env = str(app_env or "development").strip().lower()
        production_like = env in {"production", "staging", "online", "prod"}
        if production_like and parsed.scheme != "https":
            return {"ok": False, "code": "PUBLIC_URL_NOT_HTTPS", "message": "En entorno publico, los QR de Networking deben usar HTTPS."}
        if production_like and (host in LOCAL_PUBLIC_HOSTS or host.startswith("192.168.") or host.startswith("10.") or host.endswith(".local")):
            return {"ok": False, "code": "PUBLIC_URL_LOCAL_ONLY", "message": "La URL publica no puede usar localhost, IP privada o host local en un lanzamiento publico."}
        return {"ok": True, "code": "PUBLIC_URL_VALID", "message": f"URL publica valida para enlaces Networking: {raw}."}

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
        normalized = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
        key = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
        return key or hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:16]

    def _fingerprint(self, item: dict) -> str:
        payload = json.dumps({k: v for k, v in item.items() if k != "channels"}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _safe_json(self, value) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def _json_list(self, raw) -> list:
        if raw is None:
            return []
        if isinstance(raw, list):
            return raw
        try:
            parsed = json.loads(str(raw or "[]"))
            return parsed if isinstance(parsed, list) else []
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

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
