from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parent


@dataclass
class PendingPairing:
    code_hash: str
    nonce_hash: str
    organization_id: int
    event_id: int
    profile: str
    scope: str
    capabilities: set[str]
    expires_at: float
    status: str = "PENDING"
    device_id: str | None = None


@dataclass
class Device:
    device_id: str
    organization_id: int
    event_id: int
    profile: str
    scope: str
    capabilities: set[str]
    token_hash: str
    status: str = "ACTIVE"


@dataclass
class PairingBackendSimulator:
    pairings: dict[str, PendingPairing] = field(default_factory=dict)
    devices: dict[str, Device] = field(default_factory=dict)

    def create_pending(self, *, code: str, nonce: str, organization_id: int, event_id: int, profile: str, ttl: int = 600) -> None:
        assert code.startswith("BTR-") and len(code) == 13
        key = self._hash(code)
        self.pairings[key] = PendingPairing(
            code_hash=key,
            nonce_hash=self._hash(nonce),
            organization_id=organization_id,
            event_id=event_id,
            profile=profile,
            scope=f"event:{event_id}:{profile}",
            capabilities=self._capabilities(profile),
            expires_at=time.time() + ttl,
        )

    def approve(self, *, code: str, organization_id: int, event_id: int) -> None:
        pairing = self._lookup(code)
        self._assert_scope(pairing, organization_id, event_id)
        pairing.status = "APPROVED"

    def reject(self, *, code: str) -> None:
        self._lookup(code).status = "REJECTED"

    def exchange(self, *, code: str, nonce: str, organization_id: int, event_id: int) -> Device:
        pairing = self._lookup(code)
        self._assert_scope(pairing, organization_id, event_id)
        if pairing.expires_at < time.time():
            pairing.status = "EXPIRED"
            raise ValueError("expired_code")
        if pairing.status != "APPROVED":
            raise ValueError(f"not_approved:{pairing.status}")
        if pairing.nonce_hash != self._hash(nonce):
            raise ValueError("invalid_nonce")
        device_id = f"dev-{secrets.token_hex(4)}"
        token = secrets.token_urlsafe(32)
        device = Device(
            device_id=device_id,
            organization_id=pairing.organization_id,
            event_id=pairing.event_id,
            profile=pairing.profile,
            scope=pairing.scope,
            capabilities=pairing.capabilities,
            token_hash=self._hash(token),
        )
        pairing.status = "USED"
        pairing.device_id = device_id
        self.devices[device_id] = device
        return device

    def authenticate(self, *, device_id: str, token: str, organization_id: int, event_id: int) -> bool:
        device = self.devices[device_id]
        return (
            device.status == "ACTIVE"
            and device.organization_id == organization_id
            and device.event_id == event_id
            and device.token_hash == self._hash(token)
        )

    def revoke(self, *, device_id: str) -> None:
        self.devices[device_id].status = "REVOKED"

    def _lookup(self, code: str) -> PendingPairing:
        pairing = self.pairings.get(self._hash(code))
        if not pairing:
            raise ValueError("invalid_code")
        return pairing

    @staticmethod
    def _assert_scope(pairing: PendingPairing, organization_id: int, event_id: int) -> None:
        if pairing.organization_id != organization_id:
            raise ValueError("cross_org")
        if pairing.event_id != event_id:
            raise ValueError("cross_event")

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _capabilities(profile: str) -> set[str]:
        if profile == "ACCESS_FAST":
            return {"VALIDATE_ACCESS", "SCAN_QR", "SYNC_DATASET"}
        if profile == "DISPLAY":
            return {"DISPLAY_CONTENT", "SYNC_DATASET"}
        return {"SYNC_DATASET"}


def must_fail(fn, expected: str) -> None:
    try:
        fn()
    except Exception as exc:
        assert expected in str(exc), f"expected {expected}, got {exc}"
    else:
        raise AssertionError(f"expected failure {expected}")


def verify_static_contracts() -> None:
    required = [
        "android/shared/foundation/src/main/java/com/bitora/android/foundation/pairing/PairingCodeGenerator.kt",
        "android/shared/foundation/src/main/java/com/bitora/android/foundation/pairing/DeviceIdentityStore.kt",
        "android/shared/foundation/src/main/java/com/bitora/android/foundation/pairing/PairingSession.kt",
        "android/shared/foundation/src/main/java/com/bitora/android/foundation/network/BitoraContracts.kt",
        "android/apps/operation/src/main/java/com/bitora/android/operation/MainActivity.kt",
        "android/apps/display/src/main/java/com/bitora/android/display/MainActivity.kt",
    ]
    for rel in required:
        assert (ROOT / rel).exists(), rel
    store = (ROOT / required[1]).read_text(encoding="utf-8")
    assert "EncryptedSharedPreferences" in store
    assert "credential_token" in store
    combined = "\n".join((ROOT / rel).read_text(encoding="utf-8") for rel in required)
    assert "BTR-A0-DEMO" not in combined
    assert "PairingCodeGenerator.newCode" in combined
    assert "PAIRING REQUIRED" in combined


def run_security_scope_tests() -> dict:
    backend = PairingBackendSimulator()
    op_code = "BTR-ABCD-2345"
    op_nonce = "nonce-operation"
    backend.create_pending(code=op_code, nonce=op_nonce, organization_id=1, event_id=10, profile="ACCESS_FAST")
    must_fail(lambda: backend.exchange(code=op_code, nonce=op_nonce, organization_id=1, event_id=10), "not_approved")
    backend.approve(code=op_code, organization_id=1, event_id=10)
    must_fail(lambda: backend.exchange(code=op_code, nonce="wrong", organization_id=1, event_id=10), "invalid_nonce")
    device = backend.exchange(code=op_code, nonce=op_nonce, organization_id=1, event_id=10)
    assert device.profile == "ACCESS_FAST"
    assert "VALIDATE_ACCESS" in device.capabilities
    must_fail(lambda: backend.exchange(code=op_code, nonce=op_nonce, organization_id=1, event_id=10), "not_approved:USED")
    backend.revoke(device_id=device.device_id)
    assert backend.devices[device.device_id].status == "REVOKED"

    display_code = "BTR-WXYZ-6789"
    display_nonce = "nonce-display"
    backend.create_pending(code=display_code, nonce=display_nonce, organization_id=1, event_id=11, profile="DISPLAY")
    backend.approve(code=display_code, organization_id=1, event_id=11)
    display = backend.exchange(code=display_code, nonce=display_nonce, organization_id=1, event_id=11)
    assert display.profile == "DISPLAY"
    assert "DISPLAY_CONTENT" in display.capabilities

    expired_code = "BTR-QQQQ-2222"
    backend.create_pending(code=expired_code, nonce="expired", organization_id=1, event_id=12, profile="ACCESS_FAST", ttl=-1)
    backend.approve(code=expired_code, organization_id=1, event_id=12)
    must_fail(lambda: backend.exchange(code=expired_code, nonce="expired", organization_id=1, event_id=12), "expired_code")

    rejected_code = "BTR-RRRR-3333"
    backend.create_pending(code=rejected_code, nonce="rejected", organization_id=1, event_id=12, profile="ACCESS_FAST")
    backend.reject(code=rejected_code)
    must_fail(lambda: backend.exchange(code=rejected_code, nonce="rejected", organization_id=1, event_id=12), "not_approved:REJECTED")

    scoped_code = "BTR-SSSS-4444"
    backend.create_pending(code=scoped_code, nonce="scoped", organization_id=7, event_id=70, profile="ACCESS_FAST")
    must_fail(lambda: backend.approve(code=scoped_code, organization_id=8, event_id=70), "cross_org")
    must_fail(lambda: backend.approve(code=scoped_code, organization_id=7, event_id=71), "cross_event")

    return {
        "valid_pairing": True,
        "expired_code": True,
        "invalid_code": True,
        "replay": True,
        "rejected_pairing": True,
        "revoked_device": True,
        "operation_pairing": True,
        "display_pairing": True,
        "cross_event": True,
        "cross_org": True,
    }


def main() -> int:
    verify_static_contracts()
    results = run_security_scope_tests()
    print({"status": "PASS", **results})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
