from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "tmp" / "android_a1_1_pairing_lab.json"
QR_DIR = ROOT / "android" / "artifacts" / "a3" / "qr"
A4_QR_DIR = ROOT / "android" / "artifacts" / "a4" / "qr"
A5_QR_DIR = ROOT / "android" / "artifacts" / "a5" / "qr"
A6_QR_DIR = ROOT / "android" / "artifacts" / "a6" / "qr"
A7_QR_DIR = ROOT / "android" / "artifacts" / "a7" / "qr"
A8_QR_DIR = ROOT / "android" / "artifacts" / "a8" / "qr"
TTL_SECONDS = 10 * 60
SIGNING_KEY = b"BITORA-A2-LAB-SIGNING-KEY"


def now() -> float:
    return time.time()


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sign(value: str) -> str:
    return hmac.new(SIGNING_KEY, value.encode("utf-8"), hashlib.sha256).hexdigest()


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"pairings": {}, "devices": {}}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def profile_caps(profile: str) -> list[str]:
    if profile == "DISPLAY":
        return ["DISPLAY_CONTENT", "SYNC_DATASET"]
    if profile == "RECEPTION":
        return ["CHECK_IN", "SCAN_QR", "VIEW_PARTICIPANT", "PRINT_BADGE", "SYNC_DATASET"]
    if profile == "SERVICE":
        return ["CONSUME_ENTITLEMENT", "SCAN_QR", "SYNC_DATASET"]
    if profile == "LEAD_RETRIEVAL":
        return ["SCAN_QR", "VIEW_PARTICIPANT", "SYNC_DATASET"]
    if profile == "LOGISTICS":
        return ["VALIDATE_ACCESS", "SCAN_QR", "SYNC_DATASET"]
    if profile == "SELF_SERVICE":
        return ["CHECK_IN", "SCAN_QR", "VIEW_PARTICIPANT", "PRINT_BADGE", "SYNC_DATASET"]
    return ["VALIDATE_ACCESS", "SCAN_QR", "SYNC_DATASET"]


def public_pairing(pairing: dict) -> dict:
    expires_at = pairing.get("expires_at", 0)
    status = pairing.get("status", "PENDING")
    if status == "PENDING" and expires_at < now():
        status = "EXPIRED"
        pairing["status"] = status
    return {
        "pairingCode": pairing.get("pairing_code"),
        "deviceKind": pairing.get("device_kind"),
        "requestedProfile": pairing.get("requested_profile"),
        "softwareVersion": pairing.get("software_version"),
        "status": status,
        "eventId": pairing.get("event_id"),
        "eventName": pairing.get("event_name"),
        "profile": pairing.get("profile"),
        "scope": pairing.get("scope"),
        "capabilities": pairing.get("capabilities", []),
        "createdAt": pairing.get("created_at"),
        "expiresAt": pairing.get("expires_at"),
        "usedDeviceId": pairing.get("used_device_id"),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "BitoraAndroidPairingLab/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/admin/pairing":
            self.html(self.render_admin())
            return
        if parsed.path == "/api/device-pairing/status":
            params = parse_qs(parsed.query)
            code = (params.get("pairingCode") or [""])[0]
            nonce = (params.get("nonce") or [""])[0]
            self.json(self.status_payload(code, nonce))
            return
        if parsed.path == "/api/admin/pairing/pending":
            state = load_state()
            self.json({"ok": True, "items": [public_pairing(p) for p in state["pairings"].values()]})
            return
        if parsed.path == "/api/admin/telemetry":
            params = parse_qs(parsed.query)
            device_id = (params.get("deviceId") or [""])[0]
            self.json(self.telemetry_payload(device_id))
            return
        if parsed.path == "/api/edge/dataset":
            params = parse_qs(parsed.query)
            self.json(self.dataset(params))
            return
        if parsed.path == "/qr-tests":
            self.html(self.render_qr_tests())
            return
        if parsed.path.startswith("/qr/") and parsed.path.endswith(".png"):
            qr_dir = A8_QR_DIR if parsed.path.startswith("/qr/a8/") else A7_QR_DIR if parsed.path.startswith("/qr/a7/") else A6_QR_DIR if parsed.path.startswith("/qr/a6/") else A5_QR_DIR if parsed.path.startswith("/qr/a5/") else A4_QR_DIR if parsed.path.startswith("/qr/a4/") else QR_DIR
            target = qr_dir / Path(parsed.path).name
            if target.exists():
                self.bytes(target.read_bytes(), "image/png")
                return
            self.send_error(404)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        body = self.read_json()
        if parsed.path == "/api/device-pairing/request":
            self.json(self.register_request(body))
            return
        if parsed.path == "/api/device-pairing/exchange":
            self.json(self.exchange(body))
            return
        if parsed.path == "/api/admin/pairing/approve":
            self.json(self.approve(body))
            return
        if parsed.path == "/api/admin/pairing/reject":
            self.json(self.reject(body))
            return
        if parsed.path == "/api/admin/device/revoke":
            self.json(self.revoke(body))
            return
        if parsed.path == "/api/edge/heartbeat":
            self.json(self.heartbeat(body))
            return
        if parsed.path == "/api/edge/sync":
            self.json(self.sync(body))
            return
        self.send_error(404)

    def register_request(self, body: dict) -> dict:
        code = str(body.get("pairingCode", "")).strip().upper()
        nonce = str(body.get("nonce", ""))
        if not code.startswith("BTR-") or len(code) != 13:
            return {"ok": False, "error": "invalid_code"}
        if not nonce:
            return {"ok": False, "error": "invalid_nonce"}
        state = load_state()
        key = sha(code)
        existing = state["pairings"].get(key)
        if existing and existing.get("status") in {"APPROVED", "USED"}:
            return {"ok": True, **public_pairing(existing)}
        state["pairings"][key] = {
            "pairing_code": code,
            "nonce_hash": sha(nonce),
            "device_kind": str(body.get("deviceKind", "OPERATION"))[:40],
            "requested_profile": str(body.get("requestedProfile", "ACCESS_FAST"))[:80],
            "software_version": str(body.get("softwareVersion", ""))[:120],
            "status": "PENDING",
            "created_at": now(),
            "expires_at": now() + TTL_SECONDS,
        }
        save_state(state)
        return {"ok": True, **public_pairing(state["pairings"][key])}

    def status_payload(self, code: str, nonce: str) -> dict:
        state = load_state()
        pairing = state["pairings"].get(sha(code.strip().upper()))
        if not pairing:
            return {"ok": False, "decision": "UNKNOWN", "error": "invalid_code"}
        if pairing.get("nonce_hash") != sha(nonce):
            return {"ok": False, "decision": "UNKNOWN", "error": "invalid_nonce"}
        save_state(state)
        return {"ok": True, "decision": public_pairing(pairing)["status"], **public_pairing(pairing)}

    def approve(self, body: dict) -> dict:
        state = load_state()
        code = str(body.get("pairingCode", "")).strip().upper()
        pairing = state["pairings"].get(sha(code))
        if not pairing:
            return {"ok": False, "error": "invalid_code"}
        if pairing.get("status") == "USED":
            return {"ok": False, "error": "already_used"}
        profile = str(body.get("profile") or pairing.get("requested_profile") or "ACCESS_FAST")
        caps = body.get("capabilities") or profile_caps(profile)
        pairing.update(
            {
                "status": "APPROVED",
                "event_id": int(body.get("eventId") or 18),
                "event_name": str(body.get("eventName") or "BITORA LAB"),
                "profile": profile,
                "scope": str(body.get("scope") or f"event:{body.get('eventId') or 18}:{profile}"),
                "capabilities": caps,
                "approved_at": now(),
            }
        )
        save_state(state)
        return {"ok": True, **public_pairing(pairing)}

    def reject(self, body: dict) -> dict:
        state = load_state()
        pairing = state["pairings"].get(sha(str(body.get("pairingCode", "")).strip().upper()))
        if not pairing:
            return {"ok": False, "error": "invalid_code"}
        pairing["status"] = "REJECTED"
        save_state(state)
        return {"ok": True, **public_pairing(pairing)}

    def exchange(self, body: dict) -> dict:
        state = load_state()
        code = str(body.get("pairingCode", "")).strip().upper()
        nonce = str(body.get("nonce", ""))
        pairing = state["pairings"].get(sha(code))
        if not pairing:
            return {"ok": False, "error": "invalid_code"}
        if pairing.get("nonce_hash") != sha(nonce):
            return {"ok": False, "error": "invalid_nonce"}
        if pairing.get("expires_at", 0) < now():
            pairing["status"] = "EXPIRED"
            save_state(state)
            return {"ok": False, "error": "expired"}
        if pairing.get("status") != "APPROVED":
            return {"ok": False, "error": f"not_approved:{pairing.get('status')}"}
        device_id = pairing.get("used_device_id") or f"lab-{secrets.token_hex(5)}"
        token = secrets.token_urlsafe(32)
        state["devices"][device_id] = {
            "device_id": device_id,
            "organization_id": 1,
            "event_id": pairing["event_id"],
            "event_name": pairing["event_name"],
            "profile": pairing["profile"],
            "scope": pairing["scope"],
            "capabilities": pairing["capabilities"],
            "edge_base_url": self.public_base(),
            "dataset_revision": f"LAB-A2-{pairing['event_id']}-001",
            "credential_hash": sha(token),
            "status": "ACTIVE",
        }
        pairing["status"] = "USED"
        pairing["used_device_id"] = device_id
        save_state(state)
        return {
            "ok": True,
            "deviceId": device_id,
            "organizationId": 1,
            "eventId": pairing["event_id"],
            "eventName": pairing["event_name"],
            "profile": pairing["profile"],
            "scope": pairing["scope"],
            "capabilities": pairing["capabilities"],
            "edgeBaseUrl": self.public_base(),
            "datasetRevision": f"LAB-A2-{pairing['event_id']}-001",
            "credentialToken": token,
        }

    def dataset(self, params: dict) -> dict:
        organization_id = int((params.get("organizationId") or ["1"])[0])
        event_id = int((params.get("eventId") or ["18"])[0])
        device_id = str((params.get("deviceId") or [""])[0])
        device = load_state().get("devices", {}).get(device_id, {})
        device_profile = str(device.get("profile") or "ACCESS_FAST")
        revision = f"LAB-A9-{event_id}-010"
        payload = {
            "event": {"organization_id": organization_id, "event_id": event_id, "name": "V5.9.1 Railway Certification"},
            "doors": [{"id": "main", "name": "Main", "direction": "ENTRY"}],
            "device": {"profile": device_profile, "door": "main", "zone": "general", "direction": "ENTRY"},
            "zones": [{"id": "general", "name": "General"}],
            "credentials": [
                {"token": "BITORA:A3:VALID", "event_id": event_id, "status": "ACTIVE", "name": "Test Valid", "entitlements": ["ACCESS_FAST"], "doors": ["main"], "zones": ["general"]},
                {"token": "BITORA:A3:DENY", "event_id": event_id, "status": "REVOKED", "name": "Test Deny", "entitlements": [], "doors": [], "zones": []},
                {"token": "BITORA:A3:ENTRY_EXIT", "event_id": event_id, "status": "ACTIVE", "name": "Test Entry Exit", "entitlements": ["ACCESS_FAST"], "doors": ["main"], "zones": ["general"]},
            ],
            "participants": [
                {"token": "BITORA:A8:VALID", "event_id": event_id, "status": "ACTIVE", "display_name": "Test Self Service", "checked_in": False},
                {"token": "BITORA:A8:OFFLINE", "event_id": event_id, "status": "ACTIVE", "display_name": "Test Self Service Offline", "checked_in": False},
                {"token": "BITORA:A8:DENY", "event_id": event_id, "status": "CANCELLED", "display_name": "Test Self Service Deny", "checked_in": False},
                {"token": "BITORA:A4:VALID", "event_id": event_id, "status": "ACTIVE", "display_name": "Test Reception", "checked_in": False},
                {"token": "BITORA:A4:OFFLINE", "event_id": event_id, "status": "ACTIVE", "display_name": "Test Offline", "checked_in": False},
                {"token": "BITORA:A4:DENY", "event_id": event_id, "status": "CANCELLED", "display_name": "Test Cancelled", "checked_in": False},
                {"token": "BITORA:A4:CHECKED", "event_id": event_id, "status": "ACTIVE", "display_name": "Test Checked", "checked_in": True},
            ],
            "service_entitlements": [
                {"token": "BITORA:A5:VALID", "event_id": event_id, "status": "ACTIVE", "type": "COFFEE", "service_point": "coffee-main", "available": 1, "display_name": "Test Service"},
                {"token": "BITORA:A5:OFFLINE", "event_id": event_id, "status": "ACTIVE", "type": "COFFEE", "service_point": "coffee-main", "available": 1, "display_name": "Test Service Offline"},
                {"token": "BITORA:A5:OFFLINE2", "event_id": event_id, "status": "ACTIVE", "type": "COFFEE", "service_point": "coffee-main", "available": 1, "display_name": "Test Service Offline Retest"},
                {"token": "BITORA:A5:OFFLINE3", "event_id": event_id, "status": "ACTIVE", "type": "COFFEE", "service_point": "coffee-main", "available": 1, "display_name": "Test Service Offline Final"},
                {"token": "BITORA:A5:DENY", "event_id": event_id, "status": "REVOKED", "type": "COFFEE", "service_point": "coffee-main", "available": 0, "display_name": "Test Service Deny"},
            ],
            "lead_participants": [
                {"token": "BITORA:A6:VALID", "event_id": event_id, "status": "ACTIVE", "display_name": "Test Lead", "lead_consent": True},
                {"token": "BITORA:A6:OFFLINE", "event_id": event_id, "status": "ACTIVE", "display_name": "Test Lead Offline", "lead_consent": True},
                {"token": "BITORA:A6:DENY", "event_id": event_id, "status": "ACTIVE", "display_name": "Test No Consent", "lead_consent": False},
            ],
            "vehicle_permits": [
                {"token": "BITORA:A7:VALID", "event_id": event_id, "status": "ACTIVE", "display_label": "Vehicle LAB 01", "checkpoint": "logistics-main"},
                {"token": "BITORA:A7:OFFLINE", "event_id": event_id, "status": "ACTIVE", "display_label": "Vehicle Offline", "checkpoint": "logistics-main"},
                {"token": "BITORA:A7:OFFLINE2", "event_id": event_id, "status": "ACTIVE", "display_label": "Vehicle Offline Final", "checkpoint": "logistics-main"},
                {"token": "BITORA:A7:DENY", "event_id": event_id, "status": "REVOKED", "display_label": "Vehicle Revoked", "checkpoint": "logistics-main"},
            ],
            "capabilities": profile_caps(device_profile),
            "configuration": {"offline_policy": "EDGE_LOCAL_SAFE_ONLY", "cooldown_seconds": 2},
            "display_content": {"title": "BITORA LIVE", "message": "Bienvenidos al Evento 18", "screen": "MAIN_HALL", "duration_seconds": 10},
        }
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        checksum = sha(payload_json)
        expires = int(now() + 3600)
        signature = sign(f"{organization_id}|{event_id}|{revision}|{checksum}|{expires}")
        return {
            "ok": True,
            "organizationId": organization_id,
            "eventId": event_id,
            "revision": revision,
            "schemaVersion": "v5.8",
            "generatedAt": now(),
            "expiresAtEpochSeconds": expires,
            "payloadJson": payload_json,
            "checksum": checksum,
            "signature": signature,
            "signingKeyId": "LAB-A2",
        }

    def heartbeat(self, body: dict) -> dict:
        state = load_state()
        device_id = str(body.get("deviceId", ""))
        if device_id in state["devices"]:
            state["devices"][device_id]["last_seen"] = now()
            state["devices"][device_id]["dataset_revision"] = str(body.get("datasetRevision", ""))
            raw_telemetry = body.get("telemetry") or {}
            state["devices"][device_id]["telemetry"] = {
                key: raw_telemetry.get(key)
                for key in ("deviceKind", "softwareVersion", "environment", "queuePending", "syncDurationMs")
            }
            save_state(state)
            return {"ok": True, "edgeStatus": "ONLINE", "lastSeen": now()}
        return {"ok": False, "error": "unknown_device"}

    def telemetry_payload(self, requested_device_id: str = "") -> dict:
        devices = load_state().get("devices", {})
        items = []
        for device_id, device in devices.items():
            if requested_device_id and device_id != requested_device_id:
                continue
            last_seen = float(device.get("last_seen") or 0)
            age_seconds = max(0, int(now() - last_seen)) if last_seen else None
            telemetry = device.get("telemetry") or {}
            alerts = []
            if age_seconds is None or age_seconds > 20 * 60:
                alerts.append("HEARTBEAT_STALE")
            if not str(device.get("dataset_revision") or ""):
                alerts.append("DATASET_MISSING")
            if int(telemetry.get("queuePending") or 0) > 100:
                alerts.append("QUEUE_DEPTH_HIGH")
            items.append({
                "deviceId": device_id,
                "profile": device.get("profile"),
                "status": device.get("status"),
                "lastSeen": last_seen,
                "heartbeatAgeSeconds": age_seconds,
                "datasetRevision": device.get("dataset_revision"),
                "telemetry": telemetry,
                "alerts": alerts,
            })
        return {
            "ok": True,
            "status": "HEALTHY" if items and not any(item["alerts"] for item in items) else "ALERT",
            "items": items,
        }

    def sync(self, body: dict) -> dict:
        operations = body.get("operations") or []
        results = []
        seen = set()
        for op in operations:
            idem = str(op.get("idempotencyKey") or op.get("idempotency_key") or op.get("operationId"))
            if idem in seen:
                results.append({"operationId": op.get("operationId"), "status": "DUPLICATE", "conflict": "DUPLICATE"})
            else:
                seen.add(idem)
                results.append({"operationId": op.get("operationId"), "status": "ACKNOWLEDGED", "conflict": "NO_CONFLICT"})
        return {"ok": True, "results": results, "checkpoint": f"LAB-CHK-{int(now())}"}

    def render_qr_tests(self) -> str:
        return """<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>BITORA A3 QR Tests</title>
<style>body{font-family:Arial,sans-serif;background:#f5f8f8;color:#071923;padding:24px}.card{background:white;border:1px solid #d8e1e4;border-radius:8px;padding:16px;margin:12px 0}img{width:260px;max-width:90vw;height:auto}code{font-size:18px}</style></head>
<body><h1>BITORA A3 QR Tests</h1>
<div class="card"><h2>QR_TEST_VALID</h2><img src="/qr/valid.png"><p><code>BITORA:A3:VALID</code></p></div>
<div class="card"><h2>QR_TEST_DENY</h2><img src="/qr/deny.png"><p><code>BITORA:A3:DENY</code></p></div>
<div class="card"><h2>QR_TEST_ENTRY_EXIT</h2><img src="/qr/entry_exit.png"><p><code>BITORA:A3:ENTRY_EXIT</code></p></div>
</body></html>"""

    def revoke(self, body: dict) -> dict:
        state = load_state()
        device_id = str(body.get("deviceId", ""))
        if device_id in state["devices"]:
            state["devices"][device_id]["status"] = "REVOKED"
            save_state(state)
            return {"ok": True}
        return {"ok": False, "error": "invalid_device"}

    def render_admin(self) -> str:
        state = load_state()
        items = [public_pairing(p) for p in state["pairings"].values()]
        rows = "".join(
            f"""
            <tr>
              <td><code>{i['pairingCode']}</code></td><td>{i['deviceKind']}</td><td>{i['requestedProfile']}</td><td>{i['status']}</td>
              <td>
                <form method="post" action="/api/admin/pairing/approve" onsubmit="return approvePairing(event, '{i['pairingCode']}')">
                  <input name="displayName" placeholder="Device name" value="{i['deviceKind']} LAB">
                  <input name="eventName" value="V5.9.1 Railway Certification">
                  <select name="profile"><option>ACCESS_FAST</option><option>RECEPTION</option><option>DISPLAY</option><option>SERVICE</option><option>LEAD_RETRIEVAL</option><option>LOGISTICS</option><option>SELF_SERVICE</option></select>
                  <button>APPROVE</button>
                </form>
                <button onclick="rejectPairing('{i['pairingCode']}')">REJECT</button>
              </td>
            </tr>
            """
            for i in items
        ) or "<tr><td colspan='5'>No pending pairings yet.</td></tr>"
        return f"""<!doctype html>
<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>BITORA Pairing LAB</title>
<style>body{{font-family:Arial,sans-serif;background:#f5f8f8;color:#071923;padding:24px}}table{{width:100%;border-collapse:collapse;background:white}}td,th{{border:1px solid #d8e1e4;padding:10px}}button{{background:#0c8f72;color:white;border:0;border-radius:6px;padding:8px 12px}}input,select{{padding:7px;margin:2px}}</style></head>
<body><h1>BITORA Pairing LAB</h1><p>Approve Android Operation / Display devices.</p><table><thead><tr><th>Code</th><th>Type</th><th>Requested</th><th>Status</th><th>Actions</th></tr></thead><tbody>{rows}</tbody></table>
<script>
async function approvePairing(e, code){{e.preventDefault(); const fd=new FormData(e.target); const profile=fd.get('profile'); await fetch('/api/admin/pairing/approve',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{pairingCode:code,eventId:18,eventName:fd.get('eventName'),profile,scope:'event:18:'+profile}})}}); location.reload();}}
async function rejectPairing(code){{await fetch('/api/admin/pairing/reject',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{pairingCode:code}})}}); location.reload();}}
setTimeout(()=>location.reload(), 8000);
</script></body></html>"""

    def public_base(self) -> str:
        return self.headers.get("X-Forwarded-Proto", "http") + "://" + self.headers.get("Host", "127.0.0.1")

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def json(self, data: dict) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def html(self, data: str) -> None:
        payload = data.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def bytes(self, payload: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8811)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(json.dumps({"status": "LISTENING", "host": args.host, "port": args.port, "admin": f"http://{args.host}:{args.port}/admin/pairing"}), flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
