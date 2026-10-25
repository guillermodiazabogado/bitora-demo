from __future__ import annotations

from datetime import datetime
import hashlib
from html import escape
import json
import re
from typing import Any


LAYERS = {"ZONES", "DOORS", "AUDITORIUMS", "ACTIVITIES", "STANDS", "SERVICE_POINTS", "DEVICES", "VEHICLES", "OCCUPANCY", "ALERTS"}
ELEMENT_TYPES = {"ZONE", "DOOR", "AUDITORIUM", "ACTIVITY", "STAND", "SERVICE_POINT", "DEVICE", "VEHICLE_DESTINATION", "LABEL"}
EVENT_MODES = {"PRE_EVENT", "LIVE", "POST_EVENT"}


class VenueMapError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class VenueMapService:
    def __init__(self, now=None) -> None:
        self.now = now or (lambda: datetime.utcnow().replace(microsecond=0).isoformat())

    def ensure_venue(self, db, *, organization_id: int, code: str, name: str, address: str = "") -> dict:
        code = self._key(code)
        if not code:
            raise VenueMapError("VENUE_CODE_REQUIRED", "Codigo de venue requerido")
        now = self.now()
        row = db.execute("SELECT * FROM enterprise_venues WHERE organization_id = ? AND code = ?", (organization_id, code)).fetchone()
        if row:
            db.execute("UPDATE enterprise_venues SET name = ?, address = ?, updated_at = ? WHERE id = ?", (self._text(name, 160), self._text(address, 240), now, row["id"]))
            venue_id = int(row["id"])
        else:
            cur = db.execute("INSERT INTO enterprise_venues (organization_id, code, name, address, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)", (organization_id, code, self._text(name, 160), self._text(address, 240), now, now))
            venue_id = int(cur.lastrowid)
        return self._row(db, "enterprise_venues", venue_id)

    def create_map(self, db, *, organization_id: int, venue_id: int, version: str, svg_text: str = "", asset_ref: str = "", map_type: str = "SVG") -> dict:
        self._venue(db, organization_id, venue_id)
        clean_svg = self.sanitize_svg(svg_text) if svg_text else ""
        checksum = hashlib.sha256((clean_svg or asset_ref).encode("utf-8")).hexdigest()
        now = self.now()
        row = db.execute("SELECT * FROM enterprise_venue_maps WHERE organization_id = ? AND venue_id = ? AND version = ?", (organization_id, venue_id, version)).fetchone()
        if row:
            db.execute("UPDATE enterprise_venue_maps SET map_type = ?, asset_ref = ?, svg_text = ?, checksum = ?, updated_at = ? WHERE id = ?", (self._key(map_type), asset_ref[:500], clean_svg, checksum, now, row["id"]))
            map_id = int(row["id"])
        else:
            cur = db.execute("INSERT INTO enterprise_venue_maps (organization_id, venue_id, version, map_type, asset_ref, svg_text, checksum, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (organization_id, venue_id, version[:80], self._key(map_type), asset_ref[:500], clean_svg, checksum, now, now))
            map_id = int(cur.lastrowid)
        return self._row(db, "enterprise_venue_maps", map_id)

    def upsert_element(self, db, *, organization_id: int, venue_id: int, venue_map_id: int, element_key: str, element_type: str, label: str = "", layer: str = "", geometry: dict | None = None, reference_table: str = "", reference_id: int | None = None, metadata: dict | None = None) -> dict:
        self._venue(db, organization_id, venue_id)
        self._map(db, organization_id, venue_map_id)
        element_type = self._choice(element_type, ELEMENT_TYPES, "ELEMENT_TYPE_INVALID")
        layer = self._choice(layer or element_type + "S", LAYERS, "LAYER_INVALID")
        key = self._key(element_key)
        now = self.now()
        payload = (json.dumps(geometry or {}, sort_keys=True), json.dumps(metadata or {}, sort_keys=True))
        row = db.execute("SELECT * FROM enterprise_venue_map_elements WHERE organization_id = ? AND venue_map_id = ? AND element_key = ?", (organization_id, venue_map_id, key)).fetchone()
        if row:
            db.execute("UPDATE enterprise_venue_map_elements SET element_type = ?, reference_table = ?, reference_id = ?, label = ?, geometry_json = ?, layer = ?, metadata_json = ?, updated_at = ? WHERE id = ?", (element_type, self._key(reference_table), reference_id, self._text(label, 160), payload[0], layer, payload[1], now, row["id"]))
            element_id = int(row["id"])
        else:
            cur = db.execute("INSERT INTO enterprise_venue_map_elements (organization_id, venue_id, venue_map_id, element_key, element_type, reference_table, reference_id, label, geometry_json, layer, metadata_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (organization_id, venue_id, venue_map_id, key, element_type, self._key(reference_table), reference_id, self._text(label, 160), payload[0], layer, payload[1], now, now))
            element_id = int(cur.lastrowid)
        return self._row(db, "enterprise_venue_map_elements", element_id)

    def bind_event(self, db, *, organization_id: int, event_id: int, venue_id: int, venue_map_id: int, mode: str = "AUTO", active_layers: list[str] | None = None, overrides: dict | None = None) -> dict:
        self._event(db, organization_id, event_id)
        self._venue(db, organization_id, venue_id)
        self._map(db, organization_id, venue_map_id)
        mode = self.resolve_event_mode(db, organization_id=organization_id, event_id=event_id) if mode == "AUTO" else self._choice(mode, EVENT_MODES, "EVENT_MODE_INVALID")
        layers = [self._choice(layer, LAYERS, "LAYER_INVALID") for layer in (active_layers or sorted(LAYERS))]
        now = self.now()
        row = db.execute("SELECT * FROM enterprise_event_map_configurations WHERE organization_id = ? AND event_id = ?", (organization_id, event_id)).fetchone()
        payload = (json.dumps(layers, sort_keys=True), json.dumps(overrides or {}, sort_keys=True))
        if row:
            db.execute("UPDATE enterprise_event_map_configurations SET venue_id = ?, venue_map_id = ?, mode = ?, active_layers_json = ?, overrides_json = ?, updated_at = ? WHERE id = ?", (venue_id, venue_map_id, mode, payload[0], payload[1], now, row["id"]))
            config_id = int(row["id"])
        else:
            cur = db.execute("INSERT INTO enterprise_event_map_configurations (organization_id, event_id, venue_id, venue_map_id, mode, active_layers_json, overrides_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (organization_id, event_id, venue_id, venue_map_id, mode, payload[0], payload[1], now, now))
            config_id = int(cur.lastrowid)
        return self._row(db, "enterprise_event_map_configurations", config_id)

    def operational_model(self, db, *, organization_id: int, event_id: int, command_snapshot: dict | None = None, requested_mode: str | None = None) -> dict:
        self._event(db, organization_id, event_id)
        config = db.execute("SELECT * FROM enterprise_event_map_configurations WHERE organization_id = ? AND event_id = ? AND status = 'ACTIVE'", (organization_id, event_id)).fetchone()
        mode = self._choice(requested_mode, EVENT_MODES, "EVENT_MODE_INVALID") if requested_mode else (config["mode"] if config else self.resolve_event_mode(db, organization_id=organization_id, event_id=event_id))
        venue = self._row(db, "enterprise_venues", int(config["venue_id"])) if config else None
        venue_map = self._row(db, "enterprise_venue_maps", int(config["venue_map_id"])) if config else None
        layers = json.loads(config["active_layers_json"] or "[]") if config else []
        elements = [self._element_payload(db, dict(r), mode, command_snapshot or {}) for r in db.execute("SELECT * FROM enterprise_venue_map_elements WHERE organization_id = ? AND venue_map_id = ? AND status = 'ACTIVE' ORDER BY id", (organization_id, int(config["venue_map_id"]) if config else 0)).fetchall()]
        return {"schema": "bitora.enterprise_ui.v5.7.1.venue_map", "organization_id": organization_id, "event_id": event_id, "mode": mode, "occupancy_policy": {"projected": "reservations/pre-event demand", "access": "real access counter", "camera": "unavailable unless configured"}, "venue": venue, "map": venue_map, "layers": layers, "elements": elements}

    def render_enterprise_dashboard_html(self, *, snapshot: dict, venue_model: dict, phase: str) -> str:
        cards = (snapshot.get("sections", {}).get("overview", {}).get("data", {}) or {}).get("cards", [])
        alerts = (snapshot.get("sections", {}).get("alerts", {}).get("data", {}) or {}).get("open", [])
        devices = (snapshot.get("sections", {}).get("devices", {}).get("data", {}) or {}).get("items", [])
        elements = venue_model.get("elements", [])
        card_html = "".join(f"<article class='metric'><span>{self._esc(c['label'])}</span><strong>{self._esc(c['value'])}</strong><small>{self._esc(c.get('secondary','')) or 'Snapshot real'}</small></article>" for c in cards[:6])
        alert_html = "".join(f"<article class='alert {self._esc(a['severity']).lower()}'><b>{self._esc(a['severity'])}</b><span>{self._esc(a['title'])}</span><small>{self._esc(a['status'])}</small></article>" for a in alerts[:4]) or "<article class='alert neutral'><b>OK</b><span>Sin alertas abiertas</span><small>Operación normal</small></article>"
        device_html = "".join(f"<article class='device'><b>{self._esc(d['display_name'])}</b><span>{self._esc(d['device_type'])}</span><small>{self._esc(d['status'])} · {self._esc(d['sync_state'])}</small></article>" for d in devices[:6])
        overlay_html = "".join(self._overlay_html(item) for item in elements[:24])
        phase_copy = {"PRE_EVENT": "Demanda proyectada y preparación", "LIVE": "Operación en vivo", "POST_EVENT": "Análisis posterior"}.get(phase, phase)
        return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BITORA Enterprise Command Center</title>
<link rel="stylesheet" href="V5_7_1_DESIGN_SYSTEM.css"></head><body>
<div class="app-shell"><aside class="sidebar"><div class="brand">BITORA</div><nav><b>OPERACION</b><a class="active">Command Center</a><a>Personas</a><a>Accesos</a><b>EVENTO</b><a>Actividades</a><a>Servicios</a><b>LOGISTICA</b><a>Vehiculos</a><a>Dispositivos</a></nav></aside>
<main><header class="topbar"><div><small>BITORA Enterprise</small><h1>Command Center</h1></div><div class="phase">{self._esc(phase)}<span>{self._esc(phase_copy)}</span></div><div class="health">Sistema operativo</div></header>
<section class="alerts">{alert_html}</section><section class="metrics">{card_html}</section>
<section class="workspace"><div class="map-panel"><div class="panel-head"><h2>Master Venue Map</h2><div class="toolbar"><button>Fit</button><button>Zoom</button><button>Layers</button></div></div><div class="venue-map">{overlay_html}</div><div class="legend"><span>PROJECTED</span><span>ACCESS</span><span>CAMERA UNAVAILABLE</span></div></div>
<aside class="side-panel"><h2>Dispositivos</h2>{device_html}<h2>Actividad</h2><p>El tablero usa snapshot agregado V5.7 y separa projected/access/camera.</p></aside></section>
</main></div></body></html>"""

    def sanitize_svg(self, svg_text: str) -> str:
        text = str(svg_text or "")
        lowered = text.lower()
        if "<script" in lowered or "javascript:" in lowered or "onload=" in lowered or "onerror=" in lowered or "<foreignobject" in lowered:
            raise VenueMapError("UNSAFE_SVG", "SVG inseguro rechazado", 400)
        if len(text.encode("utf-8")) > 500_000:
            raise VenueMapError("SVG_TOO_LARGE", "SVG excede el tamano permitido", 400)
        return text

    def resolve_event_mode(self, db, *, organization_id: int, event_id: int) -> str:
        row = db.execute("SELECT starts_at, ends_at FROM events WHERE id = ? AND organization_id = ?", (event_id, organization_id)).fetchone()
        if not row:
            raise VenueMapError("EVENT_SCOPE_ERROR", "Evento fuera de alcance", 403)
        now = self.now()
        start, end = row["starts_at"] or "", row["ends_at"] or ""
        if start and now < start:
            return "PRE_EVENT"
        if end and now > end:
            return "POST_EVENT"
        return "LIVE"

    def _element_payload(self, db, row: dict, mode: str, snapshot: dict) -> dict:
        meta = json.loads(row.get("metadata_json") or "{}")
        geometry = json.loads(row.get("geometry_json") or "{}")
        projected = meta.get("projected") if mode == "PRE_EVENT" else None
        access = meta.get("access")
        camera = {"status": "UNAVAILABLE", "value": None}
        return {"id": int(row["id"]), "key": row["element_key"], "type": row["element_type"], "label": row["label"], "layer": row["layer"], "geometry": geometry, "status": row["status"], "projected": projected, "access": access, "camera": camera}

    def _overlay_html(self, item: dict) -> str:
        geo = item.get("geometry") or {}
        x, y, w, h = int(geo.get("x", 8)), int(geo.get("y", 8)), int(geo.get("w", 140)), int(geo.get("h", 70))
        return f"<button class='map-item {self._esc(item['type']).lower()}' style='left:{x}px;top:{y}px;width:{w}px;height:{h}px'><b>{self._esc(item['label'])}</b><span>{self._esc(item['type'])}</span></button>"

    def _event(self, db, organization_id, event_id):
        row = db.execute("SELECT id FROM events WHERE id = ? AND organization_id = ?", (event_id, organization_id)).fetchone()
        if not row:
            raise VenueMapError("EVENT_SCOPE_ERROR", "Evento fuera de alcance", 403)

    def _venue(self, db, organization_id, venue_id):
        row = db.execute("SELECT id FROM enterprise_venues WHERE id = ? AND organization_id = ?", (venue_id, organization_id)).fetchone()
        if not row:
            raise VenueMapError("VENUE_SCOPE_ERROR", "Venue fuera de alcance", 403)

    def _map(self, db, organization_id, venue_map_id):
        row = db.execute("SELECT id FROM enterprise_venue_maps WHERE id = ? AND organization_id = ?", (venue_map_id, organization_id)).fetchone()
        if not row:
            raise VenueMapError("MAP_SCOPE_ERROR", "Mapa fuera de alcance", 403)

    def _row(self, db, table, row_id):
        row = db.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
        if not row:
            raise VenueMapError("ROW_NOT_FOUND", "Registro no encontrado", 404)
        return dict(row)

    def _choice(self, value, allowed, code):
        item = self._key(value)
        if item not in allowed:
            raise VenueMapError(code, code, 400)
        return item

    def _key(self, value):
        return re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(value or "").strip().upper()).strip("_")

    def _text(self, value, limit):
        return str(value or "").strip()[:limit]

    def _esc(self, value):
        return escape(str(value or ""))
