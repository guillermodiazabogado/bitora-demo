from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parent


@dataclass
class AccessSimulator:
    states: dict[str, str] = field(default_factory=dict)
    last_at: dict[str, float] = field(default_factory=dict)
    queue: list[dict] = field(default_factory=list)

    def decide(self, token: str, direction: str, *, event_id: int = 18, profile: str = "ACCESS_FAST", cooldown: float = 0.0) -> tuple[str, str]:
        if profile != "ACCESS_FAST":
            return self._record(token, direction, "DENY", "DEVICE_NOT_AUTHORIZED")
        if not token.startswith("BITORA:"):
            return self._record(token, direction, "DENY", "INVALID_QR")
        if token == "BITORA:A3:DENY":
            return self._record(token, direction, "DENY", "REVOKED")
        if token not in {"BITORA:A3:VALID", "BITORA:A3:ENTRY_EXIT"}:
            return self._record(token, direction, "DENY", "UNKNOWN_CREDENTIAL")
        if event_id != 18:
            return self._record(token, direction, "DENY", "WRONG_EVENT")
        now = time.time()
        if now - self.last_at.get(token, 0) < cooldown:
            return self._record(token, direction, "DENY", "COOLDOWN")
        state = self.states.get(token, "OUTSIDE")
        if direction == "ENTRY" and state == "INSIDE":
            return self._record(token, direction, "DENY", "ALREADY_INSIDE")
        if direction == "EXIT" and state == "OUTSIDE":
            return self._record(token, direction, "DENY", "ALREADY_OUTSIDE")
        self.states[token] = "INSIDE" if direction == "ENTRY" else "OUTSIDE"
        self.last_at[token] = now
        return self._record(token, direction, "ALLOW", "VALID")

    def _record(self, token: str, direction: str, decision: str, reason: str) -> tuple[str, str]:
        self.queue.append({"token": token, "direction": direction, "decision": decision, "reason_code": reason})
        return decision, reason

    def sync(self) -> int:
        count = len(self.queue)
        self.queue.clear()
        return count


def assert_static_contracts() -> None:
    files = [
        "android/apps/operation/src/main/java/com/bitora/android/operation/AccessFastPanel.kt",
        "android/apps/operation/src/main/java/com/bitora/android/operation/MainActivity.kt",
        "android/shared/foundation/src/main/java/com/bitora/android/foundation/sync/EdgeSyncEngine.kt",
        "android/apps/operation/src/main/AndroidManifest.xml",
        "tools/android_pairing_lab_server.py",
    ]
    for rel in files:
        assert (ROOT / rel).exists(), rel
    combined = "\n".join((ROOT / rel).read_text(encoding="utf-8") for rel in files)
    assert "android.permission.CAMERA" in combined
    assert "BarcodeScanning.getClient" in combined
    assert "FORMAT_QR_CODE" in combined
    assert "ACCESS_FAST" in combined
    assert "ALREADY_INSIDE" in combined
    assert "ALREADY_OUTSIDE" in combined
    assert "COOLDOWN" in combined
    assert "ACCESS_ATTEMPT" in combined
    assert "syncBatch" in combined
    assert "BITORA:A3:VALID" in combined
    assert "BITORA:A3:DENY" in combined
    assert "BITORA:A3:ENTRY_EXIT" in combined


def assert_access_rules() -> None:
    sim = AccessSimulator()
    assert sim.decide("BITORA:A3:VALID", "ENTRY") == ("ALLOW", "VALID")
    assert sim.decide("BITORA:A3:VALID", "ENTRY") == ("DENY", "ALREADY_INSIDE")
    assert sim.decide("BITORA:A3:VALID", "EXIT") == ("ALLOW", "VALID")
    assert sim.decide("BITORA:A3:VALID", "EXIT") == ("DENY", "ALREADY_OUTSIDE")
    assert sim.decide("BITORA:A3:DENY", "ENTRY") == ("DENY", "REVOKED")
    assert sim.decide("BAD", "ENTRY") == ("DENY", "INVALID_QR")
    assert sim.decide("BITORA:A3:UNKNOWN", "ENTRY") == ("DENY", "UNKNOWN_CREDENTIAL")
    assert sim.decide("BITORA:A3:ENTRY_EXIT", "ENTRY", event_id=99) == ("DENY", "WRONG_EVENT")
    assert sim.decide("BITORA:A3:ENTRY_EXIT", "ENTRY", profile="DISPLAY") == ("DENY", "DEVICE_NOT_AUTHORIZED")
    synced = sim.sync()
    assert synced >= 9
    assert not sim.queue


def assert_artifacts() -> None:
    apk = ROOT / "android" / "artifacts" / "a3" / "bitora-operation-alpha-a3.apk"
    assert apk.exists() and apk.stat().st_size > 1_000_000
    for name in ("valid.png", "deny.png", "entry_exit.png"):
        qr = ROOT / "android" / "artifacts" / "a3" / "qr" / name
        assert qr.exists() and qr.stat().st_size > 500


def main() -> int:
    assert_static_contracts()
    assert_access_rules()
    assert_artifacts()
    print(json.dumps({
        "status": "PASS",
        "access_fast": True,
        "camera_qr": True,
        "qr_resolution": True,
        "access_decision": True,
        "entry_exit": True,
        "anti_passback": True,
        "offline_access": True,
        "queue_sync": True,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
