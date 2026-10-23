from pathlib import Path


ROOT = Path(__file__).resolve().parent
PANEL = ROOT / "android/apps/operation/src/main/java/com/bitora/android/operation/ServicePanel.kt"
MAIN = ROOT / "android/apps/operation/src/main/java/com/bitora/android/operation/MainActivity.kt"
LAB = ROOT / "tools/android_pairing_lab_server.py"


def main() -> None:
    panel = PANEL.read_text(encoding="utf-8")
    main_source = MAIN.read_text(encoding="utf-8")
    lab = LAB.read_text(encoding="utf-8")
    checks = {
        "service_profile": '"SERVICE" -> ServicePanel' in main_source and '"SERVICE"' in lab,
        "real_routing": '"SERVICE" -> ServicePanel' in main_source,
        "entitlement_operation": 'operationType = "ENTITLEMENT_CONSUMPTION"' in panel,
        "idempotency": ':CONSUME:COFFEE:$tokenHash' in panel,
        "duplicate_protection": "ALREADY_CONSUMED" in panel,
        "offline_dataset": "loadActiveDataset()" in panel,
        "queue_sync": "syncOperationQueue" in panel,
        "capability_scope": all(value in panel for value in ("CONSUME_ENTITLEMENT", "SCAN_QR", "SERVICE")),
        "privacy": "credential_ref" in panel and '.put("token"' not in panel,
        "lab_dataset": all(value in lab for value in ("BITORA:A5:VALID", "BITORA:A5:DENY", "service_entitlements")),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    print({"status": status, **checks})
    raise SystemExit(0 if status == "PASS" else 1)


if __name__ == "__main__":
    main()
