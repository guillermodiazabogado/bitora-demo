from __future__ import annotations

import csv
import io
import json
import re
import uuid
from typing import Any


class VehicleLogisticsError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class VehicleLogisticsService:
    def __init__(self, enterprise_core=None, audit_service=None, edge_sync=None, now=None) -> None:
        self.enterprise_core = enterprise_core
        self.audit_service = audit_service
        self.edge_sync = edge_sync
        self.now = now or (lambda: "")

    def normalize_plate(self, plate: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", str(plate or "").upper())

    def ensure_vehicle(self, db, *, organization_id: int, plate: str, vehicle_type: str = "CAR", make: str = "", model: str = "", color: str = "") -> dict:
        norm = self.normalize_plate(plate)
        if not norm:
            raise VehicleLogisticsError("PLATE_REQUIRED", "Patente obligatoria")
        now = self.now()
        row = db.execute("SELECT * FROM enterprise_vehicles WHERE organization_id = ? AND normalized_plate = ?", (organization_id, norm)).fetchone()
        entity_id = None
        if row:
            db.execute("UPDATE enterprise_vehicles SET plate = ?, vehicle_type = ?, make = ?, model = ?, color = ?, updated_at = ? WHERE id = ?", (plate, self._key(vehicle_type), make, model, color, now, row["id"]))
            vehicle_id = int(row["id"])
        else:
            if self.enterprise_core:
                event = db.execute("SELECT id FROM events WHERE organization_id = ? ORDER BY id LIMIT 1", (organization_id,)).fetchone()
                if event:
                    entity = self.enterprise_core.ensure_entity(db, organization_id=organization_id, event_id=int(event["id"]), entity_type="VEHICLE", legacy_table="enterprise_vehicles", legacy_id=0, external_key=norm, metadata={"plate": plate})
                    entity_id = int(entity["id"])
            cur = db.execute("INSERT INTO enterprise_vehicles (organization_id, entity_id, plate, normalized_plate, vehicle_type, make, model, color, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (organization_id, entity_id, plate, norm, self._key(vehicle_type), make, model, color, now, now))
            vehicle_id = int(cur.lastrowid)
        return self._row(db, "enterprise_vehicles", vehicle_id)

    def link_event(self, db, *, organization_id: int, event_id: int, vehicle_id: int, company_id: int, driver_entity_id: int | None = None, purpose: str = "SERVICE", status: str = "APPROVED") -> dict:
        self._event(db, organization_id, event_id)
        self._vehicle(db, organization_id, vehicle_id)
        now = self.now()
        row = db.execute("SELECT * FROM enterprise_vehicle_event_participation WHERE organization_id = ? AND event_id = ? AND vehicle_id = ?", (organization_id, event_id, vehicle_id)).fetchone()
        if row:
            db.execute("UPDATE enterprise_vehicle_event_participation SET company_id = ?, driver_entity_id = ?, purpose = ?, status = ?, updated_at = ? WHERE id = ?", (company_id, driver_entity_id, self._key(purpose), self._key(status), now, row["id"]))
            pid = int(row["id"])
        else:
            cur = db.execute("INSERT INTO enterprise_vehicle_event_participation (organization_id, event_id, vehicle_id, company_id, driver_entity_id, purpose, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (organization_id, event_id, vehicle_id, company_id, driver_entity_id, self._key(purpose), self._key(status), now, now))
            pid = int(cur.lastrowid)
        return self._row(db, "enterprise_vehicle_event_participation", pid)

    def ensure_destination(self, db, *, organization_id: int, event_id: int, code: str, name: str, stand_id: int | None = None, capacity: int = 0) -> dict:
        self._event(db, organization_id, event_id)
        code = self._key(code)
        now = self.now()
        row = db.execute("SELECT * FROM enterprise_logistics_destinations WHERE organization_id = ? AND event_id = ? AND code = ?", (organization_id, event_id, code)).fetchone()
        if row:
            db.execute("UPDATE enterprise_logistics_destinations SET name = ?, stand_id = ?, capacity = ?, updated_at = ? WHERE id = ?", (name, stand_id, capacity, now, row["id"]))
            did = int(row["id"])
        else:
            cur = db.execute("INSERT INTO enterprise_logistics_destinations (organization_id, event_id, stand_id, code, name, capacity, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (organization_id, event_id, stand_id, code, name, int(capacity), now, now))
            did = int(cur.lastrowid)
        return self._row(db, "enterprise_logistics_destinations", did)

    def create_slot(self, db, *, organization_id: int, event_id: int, vehicle_id: int, company_id: int, gate_id: int, destination_id: int, driver_entity_id: int | None = None, purpose: str = "SERVICE", valid_from: str = "", valid_until: str = "", entry_limit: int = 1, status: str = "APPROVED") -> dict:
        self.link_event(db, organization_id=organization_id, event_id=event_id, vehicle_id=vehicle_id, company_id=company_id, driver_entity_id=driver_entity_id, purpose=purpose, status="APPROVED")
        now = self.now()
        cur = db.execute("INSERT INTO enterprise_vehicle_access_slots (organization_id, event_id, vehicle_id, company_id, driver_entity_id, gate_id, destination_id, purpose, valid_from, valid_until, status, entry_limit, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (organization_id, event_id, vehicle_id, company_id, driver_entity_id, gate_id, destination_id, self._key(purpose), valid_from, valid_until, self._key(status), int(entry_limit), now, now))
        return self._row(db, "enterprise_vehicle_access_slots", int(cur.lastrowid))

    def evaluate(self, db, *, organization_id: int, event_id: int, plate: str, direction: str = "ENTRY", gate_id: int | None = None, destination_id: int | None = None, driver_entity_id: int | None = None, device_id: int | None = None) -> dict:
        direction = self._key(direction)
        vehicle = db.execute("SELECT * FROM enterprise_vehicles WHERE organization_id = ? AND normalized_plate = ?", (organization_id, self.normalize_plate(plate))).fetchone()
        if not vehicle:
            return self._decision("DENY", "UNKNOWN_VEHICLE")
        if vehicle["status"] != "ACTIVE":
            return self._decision("DENY", "INACTIVE_VEHICLE", vehicle)
        if device_id and not self._device_allowed(db, organization_id, event_id, device_id):
            return self._decision("DENY", "DEVICE_NOT_ALLOWED", vehicle)
        part = db.execute("SELECT * FROM enterprise_vehicle_event_participation WHERE organization_id = ? AND event_id = ? AND vehicle_id = ? AND status IN ('APPROVED','ACTIVE')", (organization_id, event_id, vehicle["id"])).fetchone()
        if not part:
            return self._decision("DENY", "WRONG_EVENT", vehicle)
        if driver_entity_id and part["driver_entity_id"] and int(part["driver_entity_id"]) != int(driver_entity_id):
            return self._decision("DENY", "DRIVER_NOT_AUTHORIZED", vehicle)
        if direction == "EXIT":
            state = self._state(db, organization_id, event_id, int(vehicle["id"]))
            if state != "INSIDE":
                return self._decision("DENY", "RULE_DENIED", vehicle)
            return self._decision("ALLOW", "VALID", vehicle, part)
        if self._state(db, organization_id, event_id, int(vehicle["id"])) == "INSIDE":
            return self._decision("DENY", "ANTI_PASSBACK", vehicle, part)
        slot = self._active_slot(db, organization_id, event_id, int(vehicle["id"]), gate_id, destination_id)
        if not slot:
            return self._decision("DENY", "NO_ACTIVE_SLOT", vehicle, part)
        now = self.now()
        if slot["status"] == "REVOKED":
            return self._decision("DENY", "SLOT_REVOKED", vehicle, part, slot)
        if slot["valid_from"] and slot["valid_from"] > now:
            return self._decision("DENY", "OUTSIDE_TIME_WINDOW", vehicle, part, slot)
        if slot["valid_until"] and slot["valid_until"] < now:
            return self._decision("DENY", "SLOT_EXPIRED", vehicle, part, slot)
        if gate_id and slot["gate_id"] and int(slot["gate_id"]) != int(gate_id):
            return self._decision("DENY", "WRONG_GATE", vehicle, part, slot)
        if destination_id and slot["destination_id"] and int(slot["destination_id"]) != int(destination_id):
            return self._decision("DENY", "WRONG_DESTINATION", vehicle, part, slot)
        if int(slot["entry_limit"]) >= 0 and int(slot["entries_used"]) >= int(slot["entry_limit"]):
            return self._decision("DENY", "ENTRY_LIMIT_REACHED", vehicle, part, slot)
        return self._decision("ALLOW", "VALID", vehicle, part, slot)

    def record_access(self, db, *, organization_id: int, event_id: int, plate: str, direction: str = "ENTRY", gate_id: int | None = None, destination_id: int | None = None, driver_entity_id: int | None = None, device_id: int | None = None, idempotency_key: str = "", correlation_id: str = "", override: bool = False, reason: str = "") -> dict:
        if idempotency_key:
            existing = db.execute("SELECT * FROM enterprise_vehicle_access_events WHERE organization_id = ? AND idempotency_key = ?", (organization_id, idempotency_key)).fetchone()
            if existing:
                return {"ok": existing["decision"] == "ALLOW", "duplicate": True, "event": dict(existing)}
        decision = self.evaluate(db, organization_id=organization_id, event_id=event_id, plate=plate, direction=direction, gate_id=gate_id, destination_id=destination_id, driver_entity_id=driver_entity_id, device_id=device_id)
        if override:
            decision = {**decision, "decision": "ALLOW", "reason_code": "VALID", "override_reason": reason, "original_reason_code": decision["reason_code"]}
        now = self.now()
        cur = db.execute("INSERT INTO enterprise_vehicle_access_events (organization_id, event_id, vehicle_id, driver_entity_id, company_id, slot_id, gate_id, destination_id, device_id, direction, decision, reason_code, occurred_at, server_received_at, correlation_id, idempotency_key, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (organization_id, event_id, decision.get("vehicle_id"), driver_entity_id or decision.get("driver_entity_id"), decision.get("company_id"), decision.get("slot_id"), gate_id or decision.get("gate_id"), destination_id or decision.get("destination_id"), device_id, self._key(direction), decision["decision"], decision["reason_code"], now, now, correlation_id or f"veh-{uuid.uuid4().hex}", idempotency_key, json.dumps({"override": override, "reason": reason, "original_reason_code": decision.get("original_reason_code", "")}, sort_keys=True), now))
        event_id_row = int(cur.lastrowid)
        if decision["decision"] == "ALLOW" and decision.get("vehicle_id"):
            if self._key(direction) == "ENTRY":
                db.execute("UPDATE enterprise_vehicle_access_slots SET entries_used = entries_used + 1, status = CASE WHEN entries_used + 1 >= entry_limit THEN 'USED' ELSE status END, updated_at = ? WHERE id = ?", (now, decision.get("slot_id")))
                self._upsert_state(db, organization_id, event_id, int(decision["vehicle_id"]), "INSIDE", destination_id or decision.get("destination_id"), now, event_id_row, gate_id, device_id)
            elif self._key(direction) == "EXIT":
                self._upsert_state(db, organization_id, event_id, int(decision["vehicle_id"]), "OUTSIDE", None, now, event_id_row, gate_id, device_id)
        self._domain(db, organization_id, event_id, "VEHICLE_" + self._key(direction), metadata={"decision": decision["decision"], "reason_code": decision["reason_code"]})
        return {"ok": decision["decision"] == "ALLOW", "decision": decision, "event": self._row(db, "enterprise_vehicle_access_events", event_id_row)}

    def preview_csv(self, csv_text: str) -> dict:
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        required = {"plate", "company", "purpose", "from", "until", "gate", "destination"}
        if not reader.fieldnames or not required.issubset({f.strip() for f in reader.fieldnames}):
            return {"ok": False, "valid_rows": [], "errors": [{"row": 0, "error": "MISSING_COLUMNS"}]}
        valid, errors, seen = [], [], set()
        for index, row in enumerate(reader, start=2):
            norm = self.normalize_plate(row.get("plate", ""))
            row_errors = []
            if not norm:
                row_errors.append("INVALID_PLATE")
            if norm in seen:
                row_errors.append("DUPLICATE_PLATE")
            seen.add(norm)
            if row_errors:
                errors.append({"row": index, "errors": row_errors})
            else:
                valid.append(row)
        return {"ok": not errors, "valid_rows": valid, "errors": errors, "summary": {"valid": len(valid), "errors": len(errors)}}

    def dashboard(self, db, *, organization_id: int, event_id: int) -> dict:
        q = lambda sql, p: int(db.execute(sql, p).fetchone()["c"])
        return {
            "expected": q("SELECT COUNT(*) c FROM enterprise_vehicle_access_slots WHERE organization_id = ? AND event_id = ?", (organization_id, event_id)),
            "inside": q("SELECT COUNT(*) c FROM enterprise_vehicle_state_snapshots WHERE organization_id = ? AND event_id = ? AND current_state = 'INSIDE'", (organization_id, event_id)),
            "entries": q("SELECT COUNT(*) c FROM enterprise_vehicle_access_events WHERE organization_id = ? AND event_id = ? AND direction = 'ENTRY' AND decision = 'ALLOW'", (organization_id, event_id)),
            "exits": q("SELECT COUNT(*) c FROM enterprise_vehicle_access_events WHERE organization_id = ? AND event_id = ? AND direction = 'EXIT' AND decision = 'ALLOW'", (organization_id, event_id)),
            "rejected": q("SELECT COUNT(*) c FROM enterprise_vehicle_access_events WHERE organization_id = ? AND event_id = ? AND decision = 'DENY'", (organization_id, event_id)),
        }

    def reconcile_offline(self, db, *, organization_id: int, event_id: int, device_id: int, secret: str, operation: dict) -> dict:
        if self.edge_sync and not self.edge_sync.authenticate_device(db, organization_id=organization_id, event_id=event_id, device_id=device_id, secret=secret, capability="VALIDATE_VEHICLE").ok:
            return {"ok": False, "conflict_type": "DEVICE_NOT_ALLOWED"}
        payload = operation.get("payload", {})
        result = self.record_access(db, organization_id=organization_id, event_id=event_id, plate=payload.get("plate", ""), direction=payload.get("direction", "ENTRY"), gate_id=payload.get("gate_id"), destination_id=payload.get("destination_id"), device_id=device_id, idempotency_key=operation.get("idempotency_key", ""))
        conflict = "NO_CONFLICT"
        if operation.get("local_decision", {}).get("decision") == "ALLOW" and not result["ok"]:
            conflict = "VEHICLE_ANTI_PASSBACK_CONFLICT" if result["decision"]["reason_code"] == "ANTI_PASSBACK" else result["decision"]["reason_code"]
            self._domain(db, organization_id, event_id, "VEHICLE_CONFLICT_DETECTED", metadata={"conflict_type": conflict})
        return {"ok": True, "server_result": result, "conflict_type": conflict}

    def _active_slot(self, db, organization_id, event_id, vehicle_id, gate_id=None, destination_id=None):
        rows = db.execute("SELECT * FROM enterprise_vehicle_access_slots WHERE organization_id = ? AND event_id = ? AND vehicle_id = ? AND status IN ('APPROVED','ACTIVE') ORDER BY id", (organization_id, event_id, vehicle_id)).fetchall()
        for row in rows:
            if gate_id and row["gate_id"] and int(row["gate_id"]) != int(gate_id):
                continue
            if destination_id and row["destination_id"] and int(row["destination_id"]) != int(destination_id):
                continue
            return row
        return None

    def _state(self, db, organization_id, event_id, vehicle_id):
        row = db.execute("SELECT current_state FROM enterprise_vehicle_state_snapshots WHERE organization_id = ? AND event_id = ? AND vehicle_id = ?", (organization_id, event_id, vehicle_id)).fetchone()
        return row["current_state"] if row else "OUTSIDE"

    def _upsert_state(self, db, organization_id, event_id, vehicle_id, state, destination_id, now, access_event_id, gate_id, device_id):
        db.execute("INSERT INTO enterprise_vehicle_state_snapshots (organization_id, event_id, vehicle_id, current_state, current_destination_id, entered_at, last_event_id, last_gate_id, last_device_id, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(organization_id, event_id, vehicle_id) DO UPDATE SET current_state = excluded.current_state, current_destination_id = excluded.current_destination_id, entered_at = excluded.entered_at, last_event_id = excluded.last_event_id, last_gate_id = excluded.last_gate_id, last_device_id = excluded.last_device_id, updated_at = excluded.updated_at", (organization_id, event_id, vehicle_id, state, destination_id, now if state == "INSIDE" else None, access_event_id, gate_id, device_id, now))

    def _decision(self, decision, reason, vehicle=None, part=None, slot=None):
        return {"decision": decision, "reason_code": reason, "vehicle_id": vehicle["id"] if vehicle else None, "company_id": part["company_id"] if part else None, "driver_entity_id": part["driver_entity_id"] if part else None, "slot_id": slot["id"] if slot else None, "gate_id": slot["gate_id"] if slot else None, "destination_id": slot["destination_id"] if slot else None}

    def _device_allowed(self, db, organization_id, event_id, device_id):
        row = db.execute("SELECT capabilities_json FROM enterprise_devices WHERE id = ? AND organization_id = ? AND event_id = ? AND status = 'ACTIVE'", (device_id, organization_id, event_id)).fetchone()
        return bool(row and "VALIDATE_VEHICLE" in json.loads(row["capabilities_json"] or "[]"))

    def _vehicle(self, db, organization_id, vehicle_id):
        row = db.execute("SELECT * FROM enterprise_vehicles WHERE id = ? AND organization_id = ?", (vehicle_id, organization_id)).fetchone()
        if not row:
            raise VehicleLogisticsError("VEHICLE_NOT_FOUND", "Vehiculo fuera de alcance", 404)
        return row

    def _event(self, db, organization_id, event_id):
        row = db.execute("SELECT id FROM events WHERE id = ? AND organization_id = ?", (event_id, organization_id)).fetchone()
        if not row:
            raise VehicleLogisticsError("EVENT_SCOPE_ERROR", "Evento fuera de alcance", 403)

    def _row(self, db, table, row_id):
        row = db.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
        if not row:
            raise VehicleLogisticsError("ROW_NOT_FOUND", "Registro no encontrado", 404)
        return dict(row)

    def _domain(self, db, organization_id, event_id, event_type, metadata=None):
        if self.enterprise_core:
            self.enterprise_core.record_domain_event(db, organization_id=organization_id, event_id=event_id, event_type=event_type, metadata=metadata or {})

    def _key(self, value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(value or "").strip().upper()).strip("_")
