from __future__ import annotations

import shutil

from backend.application.vouchers import (
    VOUCHER_ROUTE_CONTRACTS,
    VoucherApplicationContract,
    VoucherContractError,
    VoucherScope,
)
from verificar_v5_1_access_state_engine_shadow import backfill, create_event, credential, register, setup_db

import server


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main() -> None:
    temp_root = setup_db()
    try:
        with server.connect() as db:
            event_id, _activity_id, _future_id = create_event(db, "Voucher API main")
            other_event_id, _other_activity_id, _ = create_event(db, "Voucher API other")
            registration = register(db, event_id, "voucher-contract@example.test")
            backfill(db, event_id)
            entity_id = int(credential(db, event_id, registration["id"])["entity_id"])

            contract = VoucherApplicationContract(server.entitlements_vouchers_service())
            scope = VoucherScope(organization_id=1, event_id=event_id, actor="contract-verifier")
            assigned = contract.assign(
                db,
                scope,
                {
                    "entity_id": entity_id,
                    "entitlement_type": "MEAL",
                    "allocated": 1,
                    "consumable": True,
                    "idempotency_key": "contract-grant-meal",
                },
            )
            require(assigned["ok"] and assigned["entitlement"]["allocated"] == 1, "assignment failed")

            try:
                contract.consume(db, scope, {"token": registration["token"], "entitlement_type": "MEAL"})
                raise AssertionError("consumption without idempotency key was accepted")
            except VoucherContractError as exc:
                require(exc.code == "IDEMPOTENCY_KEY_REQUIRED", "wrong missing-idempotency error")

            request = {
                "token": registration["token"],
                "entitlement_type": "MEAL",
                "quantity": 1,
                "idempotency_key": "contract-consume-meal",
            }
            consumed = contract.consume(db, scope, request)
            duplicate = contract.consume(db, scope, request)
            require(consumed["ok"] and consumed["reason_code"] == "VALID", "consumption failed")
            require(duplicate["ok"] and duplicate["duplicate"], "duplicate was not idempotent")
            require(duplicate["reason_code"] == "DUPLICATE", "duplicate reason missing")

            cross_event = contract.consume(
                db,
                VoucherScope(organization_id=1, event_id=other_event_id),
                {**request, "idempotency_key": "contract-cross-event"},
            )
            require(not cross_event["ok"] and cross_event["reason_code"] == "UNKNOWN_CREDENTIAL", "cross-event isolation failed")

            db.execute(
                "INSERT INTO organizations (public_id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                ("voucher-contract-org-2", "Voucher Org 2", server.now_iso(), server.now_iso()),
            )
            org2 = int(db.execute("SELECT id FROM organizations WHERE public_id = ?", ("voucher-contract-org-2",)).fetchone()["id"])
            try:
                contract.consume(db, VoucherScope(organization_id=org2, event_id=event_id), {**request, "idempotency_key": "contract-cross-org"})
                raise AssertionError("cross-organization event scope was accepted")
            except VoucherContractError as exc:
                require(exc.code == "EVENT_SCOPE_ERROR", "wrong cross-organization error")

            serialized = repr((assigned, consumed, duplicate, cross_event))
            require(registration["token"] not in serialized, "response leaked credential token")
            require("metadata_json" not in serialized and "idempotency_key" not in serialized, "response leaked internal fields")
            require(len(VOUCHER_ROUTE_CONTRACTS) == 4, "route contract incomplete")

        print("V5.4 voucher application contract: OK")
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
