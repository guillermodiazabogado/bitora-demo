from __future__ import annotations

import sqlite3

from backend.contracts.v5_5_lead_retrieval import ActorContext, EventScope, LeadRetrievalContract
from backend.services.lead_retrieval import LeadRetrievalError


class LeadSpy:
    def list_leads(self, _db, **kwargs):
        return [{"company_id": kwargs["company_id"]}]

    def export_csv(self, _db, **kwargs):
        return {"ok": True, "exported_by": kwargs["exported_by"]}


def expect_denied(call) -> None:
    try:
        call()
    except LeadRetrievalError as exc:
        assert exc.code == "COMPANY_ACCESS_DENIED", exc.code
        assert exc.status_code == 403
    else:
        raise AssertionError("Se esperaba COMPANY_ACCESS_DENIED")


def main() -> None:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL);
        CREATE TABLE enterprise_company_event_participation (
          id INTEGER PRIMARY KEY, organization_id INTEGER, event_id INTEGER,
          company_id INTEGER, status TEXT
        );
        CREATE TABLE enterprise_company_users (
          id INTEGER PRIMARY KEY, organization_id INTEGER, event_id INTEGER,
          company_id INTEGER, user_id INTEGER, email TEXT, status TEXT,
          permissions_json TEXT
        );
        INSERT INTO users VALUES (10, 'a@example.com'), (20, 'b@example.com');
        INSERT INTO enterprise_company_event_participation VALUES
          (1, 7, 11, 100, 'ACTIVE'), (2, 7, 11, 200, 'ACTIVE');
        INSERT INTO enterprise_company_users VALUES
          (1, 7, 11, 100, 10, 'a@example.com', 'ACTIVE', '["leads.read","leads.export"]'),
          (2, 7, 11, 200, NULL, 'b@example.com', 'ACTIVE', '["leads.read"]');
        """
    )
    contract = LeadRetrievalContract(LeadSpy())
    scope = EventScope(7, 11)
    actor_a = ActorContext(10, "Operador A", "Expositor")
    actor_b = ActorContext(20, "Operador B", "Expositor")

    assert contract.list_company(db, scope, 100, actor_a)["items"][0]["company_id"] == 100
    expect_denied(lambda: contract.list_company(db, scope, 200, actor_a))
    assert contract.list_company(db, scope, 200, actor_b)["ok"]
    expect_denied(lambda: contract.export_company(db, scope, 200, {"fields": [], "idempotency_key": "x", "exported_by": "forged"}, actor_b))

    exported = contract.export_company(
        db, scope, 100, {"fields": [], "idempotency_key": "export-1", "exported_by": "forged"}, actor_a
    )
    assert exported["exported_by"] == "Operador A"
    assert contract.list_company(db, scope, 200, ActorContext(99, "Productor", "Productor"))["ok"]
    print("OK: Lead Retrieval impide fuga entre companies y no confia en exported_by")


if __name__ == "__main__":
    main()
