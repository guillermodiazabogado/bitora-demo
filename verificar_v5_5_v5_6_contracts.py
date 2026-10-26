from __future__ import annotations

from backend.contracts.v5_5_lead_retrieval import EventScope as LeadScope, LeadRetrievalContract
from backend.contracts.v5_6_vehicle_logistics import EventScope as VehicleScope, VehicleLogisticsContract
from backend.services.lead_retrieval import LeadRetrievalError
from backend.services.vehicle_logistics import VehicleLogisticsError


class Spy:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.calls.append((name, kwargs))
            if name == "list_leads":
                return []
            if name == "dashboard":
                return {"inside": 0}
            return {"ok": True}
        return call


class ConsentDb:
    class Cursor:
        def fetchone(self):
            return {"id": 9}

    def execute(self, *_args, **_kwargs):
        return self.Cursor()


def expect_error(fn, error_type, code):
    try:
        fn()
    except error_type as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"Se esperaba {code}")


def main():
    lead_spy = Spy()
    leads = LeadRetrievalContract(lead_spy)
    scope = LeadScope(7, 11)
    leads.capture(ConsentDb(), scope, {"company_id": 3, "token": " qr-token ", "user_email": "USER@EXAMPLE.COM", "idempotency_key": " capture 1 "})
    name, kwargs = lead_spy.calls[-1]
    assert name == "capture"
    assert (kwargs["organization_id"], kwargs["event_id"]) == (7, 11)
    assert kwargs["user_email"] == "user@example.com"
    assert kwargs["idempotency_key"] == "capture_1"
    expect_error(lambda: leads.capture(None, scope, {"company_id": 3, "token": "x"}), LeadRetrievalError, "IDEMPOTENCY_KEY_REQUIRED")
    expect_error(lambda: leads.offline_sync(None, scope, {"device_id": 2, "device_secret": "s", "operation": {"idempotency_key": "o1", "payload": {}}}), LeadRetrievalError, "CONSENT_REQUIRED")

    vehicle_spy = Spy()
    vehicles = VehicleLogisticsContract(vehicle_spy)
    vehicles.access(None, VehicleScope(7, 11), {"plate": "ab-123 cd", "direction": "entry", "idempotency_key": " gate 1 "})
    name, kwargs = vehicle_spy.calls[-1]
    assert name == "record_access"
    assert (kwargs["organization_id"], kwargs["event_id"]) == (7, 11)
    assert kwargs["plate"] == "AB123CD"
    assert kwargs["direction"] == "ENTRY"
    assert kwargs["override"] is False
    expect_error(lambda: vehicles.access(None, VehicleScope(7, 11), {"plate": "AA1", "direction": "SIDE", "idempotency_key": "x"}), VehicleLogisticsError, "DIRECTION_INVALID")
    expect_error(lambda: vehicles.access(None, VehicleScope(7, 11), {"plate": "AA1"}), VehicleLogisticsError, "IDEMPOTENCY_KEY_REQUIRED")
    print("OK: contratos V5.5/V5.6 scope, sanitizacion, consentimiento e idempotencia")


if __name__ == "__main__":
    main()
