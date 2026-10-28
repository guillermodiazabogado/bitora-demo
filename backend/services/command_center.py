from __future__ import annotations

from datetime import datetime, timedelta
from html import escape
import json
import time
from typing import Any, Callable


class CommandCenterError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class CommandCenterService:
    def __init__(self, *, enterprise_core=None, edge_sync=None, event_edge=None, entitlements=None, leads=None, vehicles=None, now=None) -> None:
        self.enterprise_core = enterprise_core
        self.edge_sync = edge_sync
        self.event_edge = event_edge
        self.entitlements = entitlements
        self.leads = leads
        self.vehicles = vehicles
        self.now = now or (lambda: datetime.utcnow().replace(microsecond=0).isoformat())

    def snapshot(self, db, *, organization_id: int, event_id: int, actor: str = "command-center", simulate_failures: set[str] | None = None) -> dict:
        self._event(db, organization_id, event_id)
        start = time.perf_counter()
        failures = simulate_failures or set()
        sections = {
            "overview": self._section("overview", lambda: self._overview(db, organization_id, event_id), failures),
            "access": self._section("access", lambda: self._access(db, organization_id, event_id), failures),
            "occupancy": self._section("occupancy", lambda: self._occupancy(db, organization_id, event_id), failures),
            "zones": self._section("zones", lambda: self._zones(db, organization_id, event_id), failures),
            "doors": self._section("doors", lambda: self._doors(db, organization_id, event_id), failures),
            "devices": self._section("devices", lambda: self._devices(db, organization_id, event_id), failures),
            "edge": self._section("edge", lambda: self._edge(db, organization_id, event_id), failures),
            "conflicts": self._section("conflicts", lambda: self._conflicts(db, organization_id, event_id), failures),
            "entitlements": self._section("entitlements", lambda: self._entitlements(db, organization_id, event_id), failures),
            "vehicles": self._section("vehicles", lambda: self._vehicles(db, organization_id, event_id), failures),
            "leads": self._section("leads", lambda: self._leads(db, organization_id, event_id), failures),
            "system_health": self._section("system_health", lambda: self._system_health(db, organization_id, event_id), failures),
        }
        metrics = self._alert_metrics(sections)
        self.evaluate_alerts(db, organization_id=organization_id, event_id=event_id, metrics=metrics)
        sections["alerts"] = self._section("alerts", lambda: self._alerts(db, organization_id, event_id), failures)
        payload = {
            "schema": "bitora.command_center.v5.7.snapshot",
            "organization_id": organization_id,
            "event_id": event_id,
            "generated_at": self.now(),
            "actor": actor,
            "data_contract": "AGGREGATED_NO_PII",
            "sections": sections,
            "freshness": self._freshness(sections),
            "observability": {"latency_ms": round((time.perf_counter() - start) * 1000, 3), "failed_sections": [k for k, v in sections.items() if v["status"] != "OK"]},
        }
        self._domain(db, organization_id, event_id, "COMMAND_CENTER_SNAPSHOT_VIEWED", {"latency_ms": payload["observability"]["latency_ms"]})
        return payload

    def acknowledge_alert(self, db, *, organization_id: int, event_id: int, alert_id: int, actor: str) -> dict:
        row = self._alert(db, organization_id, event_id, alert_id)
        now = self.now()
        db.execute("UPDATE enterprise_operational_alerts SET status = 'ACKNOWLEDGED', acknowledged_at = ?, acknowledged_by = ?, updated_at = ? WHERE id = ?", (now, actor[:120], now, row["id"]))
        self._domain(db, organization_id, event_id, "COMMAND_CENTER_ALERT_ACKNOWLEDGED", {"alert_id": alert_id})
        return dict(db.execute("SELECT * FROM enterprise_operational_alerts WHERE id = ?", (alert_id,)).fetchone())

    def resolve_alert(self, db, *, organization_id: int, event_id: int, alert_id: int, actor: str = "") -> dict:
        row = self._alert(db, organization_id, event_id, alert_id)
        now = self.now()
        db.execute("UPDATE enterprise_operational_alerts SET status = 'RESOLVED', resolved_at = ?, updated_at = ? WHERE id = ?", (now, now, row["id"]))
        self._domain(db, organization_id, event_id, "COMMAND_CENTER_ALERT_RESOLVED", {"alert_id": alert_id, "actor": actor[:120]})
        return dict(db.execute("SELECT * FROM enterprise_operational_alerts WHERE id = ?", (alert_id,)).fetchone())

    def evaluate_alerts(self, db, *, organization_id: int, event_id: int, metrics: dict[str, Any]) -> dict:
        rules = self._rules(db, organization_id, event_id)
        def configured_candidate(key, alert_type, fallback_severity, value, title):
            rule = rules[key]
            return self._candidate(key, alert_type, rule.get("severity") or fallback_severity, value, rule["threshold"], title)
        candidates = [
            configured_candidate("queue_backlog", "EDGE_QUEUE_BACKLOG", "WARNING", metrics.get("queue_depth", 0), "Cola edge con operaciones pendientes"),
            configured_candidate("conflict_backlog", "EDGE_CONFLICTS", "CRITICAL", metrics.get("conflicts", 0), "Conflictos edge pendientes de revisión"),
            configured_candidate("stale_devices", "DEVICE_STALE", "WARNING", metrics.get("stale_devices", 0), "Dispositivos sin heartbeat reciente"),
            configured_candidate("occupancy_warning", "OCCUPANCY_WARNING", "WARNING", metrics.get("occupancy_pct", 0), "Ocupación elevada"),
            configured_candidate("occupancy_critical", "OCCUPANCY_CRITICAL", "CRITICAL", metrics.get("occupancy_pct", 0), "Ocupación crítica"),
        ]
        active_keys = set()
        for candidate in candidates:
            if not candidate:
                continue
            active_keys.add(candidate["alert_key"])
            self._upsert_alert(db, organization_id, event_id, candidate)
        for row in db.execute("SELECT * FROM enterprise_operational_alerts WHERE organization_id = ? AND event_id = ? AND status IN ('OPEN','ACKNOWLEDGED')", (organization_id, event_id)).fetchall():
            if row["alert_key"] not in active_keys:
                db.execute("UPDATE enterprise_operational_alerts SET status = 'RESOLVED', resolved_at = ?, updated_at = ? WHERE id = ?", (self.now(), self.now(), row["id"]))
        return {"ok": True, "active": len(active_keys)}

    def render_dashboard_html(self, snapshot: dict) -> str:
        sections = snapshot["sections"]
        overview = sections["overview"].get("data") or {}
        cards = overview.get("cards", [])
        alerts = sections["alerts"].get("data", {}).get("open", [])
        devices = sections["devices"].get("data", {}).get("items", [])
        card_html = "".join(f"<article><strong>{escape(str(c['value']))}</strong><span>{escape(c['label'])}</span></article>" for c in cards)
        alert_html = "".join(f"<li class='{escape(a['severity'].lower())}'><b>{escape(a['severity'])}</b> {escape(a['title'])}</li>" for a in alerts) or "<li>Sin alertas abiertas</li>"
        device_html = "".join(f"<article><b>{escape(d['display_name'])}</b><span>{escape(d['status'])} · {escape(d['sync_state'])}</span></article>" for d in devices) or "<article><b>Sin dispositivos</b><span>No hay terminales registrados</span></article>"
        return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BITORA Command Center</title>
<style>
body{{margin:0;font-family:Arial,sans-serif;background:#eef3f3;color:#071b2c}}header{{background:#071923;color:white;padding:16px 24px;display:flex;justify-content:space-between}}main{{max-width:1180px;margin:0 auto;padding:22px}}.grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}}article,.panel{{background:white;border:1px solid #ccd9df;border-radius:8px;padding:14px}}strong{{font-size:30px;display:block}}span{{color:#466070}}.layout{{display:grid;grid-template-columns:2fr 1fr;gap:14px;margin-top:14px}}.map{{height:220px;background:linear-gradient(135deg,#dfeaea,#f7fbfb);position:relative}}.flow{{display:flex;gap:8px;align-items:center}}.flow b{{background:#07898d;color:white;padding:10px;border-radius:6px}}li{{margin:8px 0}}.critical{{color:#b42318}}.warning{{color:#9a6700}}@media(max-width:800px){{.grid,.layout{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<header><h1>BITORA Command Center</h1><div>Evento {escape(str(snapshot['event_id']))} · {escape(snapshot['generated_at'])}</div></header>
<main>
<section class="grid">{card_html}</section>
<section class="layout">
<div class="panel"><h2>Mapa operativo</h2><div class="map"></div><h2>Flujo de accesos</h2><div class="flow"><b>Entradas</b><span>→</span><b>Adentro</b><span>→</span><b>Salidas</b></div></div>
<aside class="panel"><h2>Alertas</h2><ul>{alert_html}</ul></aside>
</section>
<section class="layout"><div class="panel"><h2>Dispositivos</h2>{device_html}</div><div class="panel"><h2>Ocupación</h2><strong>{escape(str(overview.get('people_inside', 0)))}</strong><span>personas dentro según accesos</span></div></section>
</main>
</body>
</html>"""

    def _overview(self, db, org, event):
        people_inside = self._count(db, "SELECT COUNT(*) c FROM enterprise_access_state_snapshots WHERE organization_id = ? AND event_id = ? AND current_state = 'INSIDE'", (org, event))
        access_entries = self._count(db, "SELECT COUNT(*) c FROM enterprise_access_events WHERE organization_id = ? AND event_id = ? AND direction = 'ENTRY' AND decision = 'ALLOW'", (org, event))
        access_exits = self._count(db, "SELECT COUNT(*) c FROM enterprise_access_events WHERE organization_id = ? AND event_id = ? AND direction = 'EXIT' AND decision = 'ALLOW'", (org, event))
        denials = self._count(db, "SELECT COUNT(*) c FROM enterprise_access_events WHERE organization_id = ? AND event_id = ? AND decision = 'DENY'", (org, event))
        devices = self._device_counts(db, org, event)
        edge = self._edge_counts(db, org, event)
        vehicles_inside = self._count(db, "SELECT COUNT(*) c FROM enterprise_vehicle_state_snapshots WHERE organization_id = ? AND event_id = ? AND current_state = 'INSIDE'", (org, event)) if self._table_exists(db, "enterprise_vehicle_state_snapshots") else 0
        leads = self._count(db, "SELECT COUNT(*) c FROM enterprise_leads WHERE organization_id = ? AND event_id = ?", (org, event)) if self._table_exists(db, "enterprise_leads") else 0
        return {
            "people_inside": people_inside,
            "cards": [
                {"label": "Personas dentro", "value": people_inside},
                {"label": "Entradas", "value": access_entries},
                {"label": "Rechazos", "value": denials},
                {"label": "Dispositivos activos", "value": devices["active"]},
                {"label": "Cola edge", "value": edge["queue_depth"]},
                {"label": "Conflictos", "value": edge["conflicts"]},
                {"label": "Vehículos dentro", "value": vehicles_inside},
                {"label": "Leads", "value": leads},
            ],
            "entries": access_entries,
            "exits": access_exits,
            "denials": denials,
            "devices": devices,
            "edge": edge,
        }

    def _access(self, db, org, event):
        by_reason = [dict(r) for r in db.execute("SELECT reason_code, COUNT(*) count FROM enterprise_access_events WHERE organization_id = ? AND event_id = ? AND decision = 'DENY' GROUP BY reason_code ORDER BY count DESC", (org, event)).fetchall()]
        recent = [self._safe_access_event(r) for r in db.execute("SELECT id, direction, decision, reason_code, occurred_at, source FROM enterprise_access_events WHERE organization_id = ? AND event_id = ? ORDER BY id DESC LIMIT 12", (org, event)).fetchall()]
        return {"entries": self._count(db, "SELECT COUNT(*) c FROM enterprise_access_events WHERE organization_id = ? AND event_id = ? AND direction = 'ENTRY' AND decision = 'ALLOW'", (org, event)), "exits": self._count(db, "SELECT COUNT(*) c FROM enterprise_access_events WHERE organization_id = ? AND event_id = ? AND direction = 'EXIT' AND decision = 'ALLOW'", (org, event)), "denials": self._count(db, "SELECT COUNT(*) c FROM enterprise_access_events WHERE organization_id = ? AND event_id = ? AND decision = 'DENY'", (org, event)), "denials_by_reason": by_reason, "recent": recent}

    def _occupancy(self, db, org, event):
        access_inside = self._count(db, "SELECT COUNT(*) c FROM enterprise_access_state_snapshots WHERE organization_id = ? AND event_id = ? AND current_state = 'INSIDE'", (org, event))
        capacity = self._event_capacity(db, org, event)
        pct = round((access_inside / capacity) * 100, 2) if capacity else 0
        return {"access_counter": {"inside": access_inside, "capacity": capacity, "occupancy_pct": pct, "status": "OK"}, "camera_counter": {"status": "UNAVAILABLE", "reason": "CAMERA_SOURCE_NOT_CONFIGURED"}, "source_policy": "ACCESS_COUNTER_AND_CAMERA_COUNTER_ARE_SEPARATE"}

    def _zones(self, db, org, event):
        rows = []
        if self._table_exists(db, "event_zones"):
            for row in db.execute("SELECT id, code, name, status FROM event_zones WHERE organization_id = ? AND event_id = ? ORDER BY id", (org, event)).fetchall():
                zone_id = int(row["id"])
                rows.append({"id": zone_id, "code": row["code"], "name": row["name"], "status": row["status"], "inside": self._count(db, "SELECT COUNT(*) c FROM enterprise_access_state_snapshots WHERE organization_id = ? AND event_id = ? AND current_zone_id = ? AND current_state = 'INSIDE'", (org, event, zone_id))})
        return {"items": rows}

    def _doors(self, db, org, event):
        rows = []
        for row in db.execute("SELECT id, code, name, status FROM enterprise_doors WHERE organization_id = ? AND event_id = ? ORDER BY id", (org, event)).fetchall():
            door_id = int(row["id"])
            rows.append({"id": door_id, "code": row["code"], "name": row["name"], "status": row["status"], "entries": self._count(db, "SELECT COUNT(*) c FROM enterprise_access_events WHERE organization_id = ? AND event_id = ? AND door_id = ? AND direction = 'ENTRY' AND decision = 'ALLOW'", (org, event, door_id)), "denials": self._count(db, "SELECT COUNT(*) c FROM enterprise_access_events WHERE organization_id = ? AND event_id = ? AND door_id = ? AND decision = 'DENY'", (org, event, door_id))})
        return {"items": rows}

    def _devices(self, db, org, event):
        items = []
        for row in db.execute("SELECT id, device_type, display_name, status, last_seen_at, version, dataset_revision, sync_state, capabilities_json FROM enterprise_devices WHERE organization_id = ? AND event_id = ? ORDER BY id", (org, event)).fetchall():
            derived = self._derived_device_status(row)
            items.append({"id": int(row["id"]), "device_type": row["device_type"], "display_name": row["display_name"], "status": derived, "admin_status": row["status"], "last_seen_at": row["last_seen_at"], "software_version": row["version"], "dataset_revision": row["dataset_revision"], "sync_state": row["sync_state"], "capabilities": json.loads(row["capabilities_json"] or "[]")})
        return {"items": items, "counts": self._device_counts(db, org, event)}

    def _edge(self, db, org, event):
        data = self._edge_counts(db, org, event)
        if self.event_edge and self._table_exists(db, "enterprise_event_edges"):
            edge = db.execute("SELECT * FROM enterprise_event_edges WHERE organization_id = ? AND event_id = ? ORDER BY id LIMIT 1", (org, event)).fetchone()
            if edge:
                readiness = self.event_edge.live_readiness(db, organization_id=org, event_id=event, cloud_state=edge["cloud_connectivity"] or "UNKNOWN")
                operation = self.event_edge.event_operation_status(db, organization_id=org, event_id=event, cloud_state=edge["cloud_connectivity"] or "UNKNOWN")
                data.update({
                    "event_edge": {
                        "id": int(edge["id"]),
                        "name": edge["name"],
                        "status": edge["status"],
                        "cloud": edge["cloud_connectivity"],
                        "dataset_revision": edge["dataset_revision"],
                        "last_cloud_sync": edge["last_cloud_sync"] or "",
                        "clock_status": edge["clock_status"],
                        "storage_status": edge["storage_status"],
                    },
                    "readiness": readiness,
                    "event_operation": operation,
                })
        return data

    def _conflicts(self, db, org, event):
        rows = [dict(r) for r in db.execute("SELECT conflict_type, COUNT(*) count FROM enterprise_edge_reconciliations WHERE organization_id = ? AND event_id = ? AND conflict_type <> 'NO_CONFLICT' GROUP BY conflict_type ORDER BY count DESC", (org, event)).fetchall()] if self._table_exists(db, "enterprise_edge_reconciliations") else []
        vehicle_conflicts = self._count(db, "SELECT COUNT(*) c FROM enterprise_domain_events WHERE organization_id = ? AND event_id = ? AND event_type = 'VEHICLE_CONFLICT_DETECTED'", (org, event)) if self._table_exists(db, "enterprise_domain_events") else 0
        return {"edge_conflicts": rows, "vehicle_conflicts": vehicle_conflicts}

    def _entitlements(self, db, org, event):
        if not self._table_exists(db, "enterprise_entitlements"):
            return {"status": "NOT_CONFIGURED"}
        return {"active_entitlements": self._count(db, "SELECT COUNT(*) c FROM enterprise_entitlements WHERE organization_id = ? AND event_id = ? AND status = 'ACTIVE'", (org, event)), "consumptions": self._count(db, "SELECT COUNT(*) c FROM enterprise_entitlement_consumptions WHERE organization_id = ? AND event_id = ?", (org, event)) if self._table_exists(db, "enterprise_entitlement_consumptions") else 0, "service_points": self._count(db, "SELECT COUNT(*) c FROM enterprise_service_points WHERE organization_id = ? AND event_id = ?", (org, event)) if self._table_exists(db, "enterprise_service_points") else 0}

    def _vehicles(self, db, org, event):
        if self.vehicles:
            return self.vehicles.dashboard(db, organization_id=org, event_id=event)
        return {"expected": 0, "inside": 0, "entries": 0, "exits": 0, "rejected": 0}

    def _leads(self, db, org, event):
        if self.leads:
            return self.leads.analytics(db, organization_id=org, event_id=event)
        return {"licensed_companies": 0, "stands": 0, "scans": 0, "unique_leads": 0, "exports": 0}

    def _system_health(self, db, org, event):
        jobs_pending = self._count(db, "SELECT COUNT(*) c FROM jobs WHERE status IN ('queued','running','retry')", ()) if self._table_exists(db, "jobs") else 0
        jobs_failed = self._count(db, "SELECT COUNT(*) c FROM jobs WHERE status = 'failed'", ()) if self._table_exists(db, "jobs") else 0
        return {"db": "OK", "storage": "NOT_CHECKED", "jobs": {"pending": jobs_pending, "failed": jobs_failed}, "safe_mode": "NOT_CHECKED", "live_mode": "NOT_CHECKED"}

    def _alerts(self, db, org, event):
        rows = db.execute("SELECT id, alert_key, alert_type, severity, status, title, detail, metric_value, first_seen_at, last_seen_at FROM enterprise_operational_alerts WHERE organization_id = ? AND event_id = ? AND status IN ('OPEN','ACKNOWLEDGED') ORDER BY CASE severity WHEN 'CRITICAL' THEN 0 WHEN 'WARNING' THEN 1 ELSE 2 END, id", (org, event)).fetchall()
        return {"open": [dict(r) for r in rows], "counts": {"open": self._count(db, "SELECT COUNT(*) c FROM enterprise_operational_alerts WHERE organization_id = ? AND event_id = ? AND status = 'OPEN'", (org, event)), "acknowledged": self._count(db, "SELECT COUNT(*) c FROM enterprise_operational_alerts WHERE organization_id = ? AND event_id = ? AND status = 'ACKNOWLEDGED'", (org, event))}}

    def _alert_metrics(self, sections):
        overview = sections["overview"].get("data") or {}
        occupancy = sections["occupancy"].get("data") or {}
        access_counter = occupancy.get("access_counter") or {}
        devices = overview.get("devices") or {}
        edge = overview.get("edge") or {}
        return {"queue_depth": edge.get("queue_depth", 0), "conflicts": edge.get("conflicts", 0), "stale_devices": devices.get("stale", 0), "occupancy_pct": access_counter.get("occupancy_pct", 0)}

    def _rules(self, db, org, event):
        defaults = {"queue_backlog": 10, "conflict_backlog": 1, "stale_devices": 1, "occupancy_warning": 80, "occupancy_critical": 95}
        now = self.now()
        for key, value in defaults.items():
            db.execute("INSERT OR IGNORE INTO enterprise_alert_rules (organization_id, event_id, rule_key, severity, threshold_value, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (org, event, key, "CRITICAL" if "critical" in key or "conflict" in key else "WARNING", value, now, now))
        rows = db.execute("SELECT rule_key, severity, threshold_value FROM enterprise_alert_rules WHERE organization_id = ? AND event_id = ? AND enabled = 1", (org, event)).fetchall()
        return {r["rule_key"]: {"severity": r["severity"], "threshold": float(r["threshold_value"])} for r in rows}

    def _candidate(self, key, alert_type, severity, value, threshold, title):
        if float(value or 0) >= float(threshold or 0) and float(threshold or 0) > 0:
            return {"alert_key": key, "alert_type": alert_type, "severity": severity, "title": title, "detail": f"{value} >= {threshold}", "metric_value": float(value or 0)}
        return None

    def _upsert_alert(self, db, org, event, candidate):
        now = self.now()
        row = db.execute("SELECT id FROM enterprise_operational_alerts WHERE organization_id = ? AND event_id = ? AND alert_key = ? AND status IN ('OPEN','ACKNOWLEDGED') ORDER BY id DESC LIMIT 1", (org, event, candidate["alert_key"])).fetchone()
        if row:
            db.execute("UPDATE enterprise_operational_alerts SET severity = ?, detail = ?, metric_value = ?, last_seen_at = ?, updated_at = ? WHERE id = ?", (candidate["severity"], candidate["detail"], candidate["metric_value"], now, now, row["id"]))
        else:
            db.execute("INSERT INTO enterprise_operational_alerts (organization_id, event_id, alert_key, alert_type, severity, status, title, detail, metric_value, first_seen_at, last_seen_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?)", (org, event, candidate["alert_key"], candidate["alert_type"], candidate["severity"], candidate["title"], candidate["detail"], candidate["metric_value"], now, now, now, now))
            self._domain(db, org, event, "COMMAND_CENTER_ALERT_OPENED", {"alert_key": candidate["alert_key"], "severity": candidate["severity"]})

    def _section(self, name: str, fn: Callable[[], dict], failures: set[str]) -> dict:
        if name in failures:
            return {"status": "UNAVAILABLE", "updated_at": self.now(), "stale": True, "error": "SIMULATED_FAILURE", "data": {}}
        try:
            return {"status": "OK", "updated_at": self.now(), "stale": False, "data": fn()}
        except Exception as exc:
            return {"status": "UNAVAILABLE", "updated_at": self.now(), "stale": True, "error": type(exc).__name__, "data": {}}

    def _freshness(self, sections):
        return {name: {"updated_at": section["updated_at"], "stale": bool(section["stale"]), "status": section["status"]} for name, section in sections.items()}

    def _device_counts(self, db, org, event):
        active = stale = revoked = 0
        for row in db.execute("SELECT status, last_seen_at FROM enterprise_devices WHERE organization_id = ? AND event_id = ?", (org, event)).fetchall():
            status = self._derived_device_status(row)
            if status == "ACTIVE":
                active += 1
            elif status == "STALE":
                stale += 1
            elif status == "REVOKED":
                revoked += 1
        return {"active": active, "stale": stale, "revoked": revoked}

    def _edge_counts(self, db, org, event):
        oldest = db.execute("SELECT queued_at FROM enterprise_edge_queue WHERE organization_id = ? AND event_id = ? AND status IN ('PENDING','RETRY','CONFLICT') ORDER BY queued_at LIMIT 1", (org, event)).fetchone() if self._table_exists(db, "enterprise_edge_queue") else None
        return {"queue_depth": self._count(db, "SELECT COUNT(*) c FROM enterprise_edge_queue WHERE organization_id = ? AND event_id = ? AND status IN ('PENDING','RETRY','CONFLICT')", (org, event)) if self._table_exists(db, "enterprise_edge_queue") else 0, "oldest_pending": oldest["queued_at"] if oldest else "", "conflicts": self._count(db, "SELECT COUNT(*) c FROM enterprise_edge_reconciliations WHERE organization_id = ? AND event_id = ? AND conflict_type <> 'NO_CONFLICT'", (org, event)) if self._table_exists(db, "enterprise_edge_reconciliations") else 0}

    def _derived_device_status(self, row):
        if row["status"] == "REVOKED":
            return "REVOKED"
        last = row["last_seen_at"] or ""
        if not last:
            return "STALE"
        try:
            age = datetime.fromisoformat(self.now().replace("Z", "+00:00")).replace(tzinfo=None) - datetime.fromisoformat(last.replace("Z", "+00:00")).replace(tzinfo=None)
            return "STALE" if age > timedelta(minutes=15) else "ACTIVE"
        except ValueError:
            return "STALE"

    def _event_capacity(self, db, org, event):
        columns = {r["name"] for r in db.execute("PRAGMA table_info(events)").fetchall()}
        wanted = [name for name in ("capacity", "cupo", "capacity_general") if name in columns]
        if not wanted:
            return 0
        row = db.execute(f"SELECT {', '.join(wanted)} FROM events WHERE id = ? AND organization_id = ?", (event, org)).fetchone()
        if not row:
            return 0
        for key in wanted:
            try:
                value = int(row[key] or 0)
                if value > 0:
                    return value
            except Exception:
                continue
        return 0

    def _safe_access_event(self, row):
        return {"id": int(row["id"]), "direction": row["direction"], "decision": row["decision"], "reason_code": row["reason_code"], "occurred_at": row["occurred_at"], "source": row["source"]}

    def _alert(self, db, org, event, alert_id):
        row = db.execute("SELECT * FROM enterprise_operational_alerts WHERE id = ? AND organization_id = ? AND event_id = ?", (alert_id, org, event)).fetchone()
        if not row:
            raise CommandCenterError("ALERT_NOT_FOUND", "Alerta fuera de alcance", 404)
        return row

    def _event(self, db, organization_id, event_id):
        row = db.execute("SELECT id FROM events WHERE id = ? AND organization_id = ?", (event_id, organization_id)).fetchone()
        if not row:
            raise CommandCenterError("EVENT_SCOPE_ERROR", "Evento fuera de alcance", 403)

    def _count(self, db, sql, params):
        return int((db.execute(sql, params).fetchone() or {"c": 0})["c"] or 0)

    def _table_exists(self, db, name):
        try:
            return bool(db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (name,)).fetchone())
        except Exception:
            return bool(db.execute("SELECT table_name AS name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = ?", (name,)).fetchone())

    def _domain(self, db, organization_id, event_id, event_type, metadata=None):
        if self.enterprise_core:
            self.enterprise_core.record_domain_event(db, organization_id=organization_id, event_id=event_id, event_type=event_type, metadata=metadata or {})
