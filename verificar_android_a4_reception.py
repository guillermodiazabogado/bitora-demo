from pathlib import Path


ROOT = Path(__file__).resolve().parent
PANEL = ROOT / "android/apps/operation/src/main/java/com/bitora/android/operation/ReceptionPanel.kt"
MAIN = ROOT / "android/apps/operation/src/main/java/com/bitora/android/operation/MainActivity.kt"
LAB = ROOT / "tools/android_pairing_lab_server.py"


def main() -> None:
    panel = PANEL.read_text(encoding="utf-8")
    main_source = MAIN.read_text(encoding="utf-8")
    lab = LAB.read_text(encoding="utf-8")
    checks = {
        "reception_profile": '"RECEPTION" -> ReceptionPanel' in main_source and '"RECEPTION"' in lab,
        "real_routing": '"RECEPTION" -> ReceptionPanel' in main_source,
        "check_in": 'operationType: String = "PARTICIPANT_CHECK_IN"' in panel,
        "idempotency": ':CHECK_IN:$tokenHash' in panel,
        "duplicate_protection": 'ALREADY_CHECKED_IN' in panel,
        "offline_dataset": 'loadActiveDataset()' in panel,
        "reconnect_flush": 'if (heartbeat) syncOperationQueue(identity, store)' in main_source,
        "capability_scope": all(value in panel for value in ("CHECK_IN", "SCAN_QR", "VIEW_PARTICIPANT")),
        "privacy": 'credential_ref' in panel and 'token_hash' not in lab,
        "lab_dataset": 'BITORA:A4:VALID' in lab and 'BITORA:A4:DENY' in lab,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    print({"status": status, **checks})
    raise SystemExit(0 if status == "PASS" else 1)


if __name__ == "__main__":
    main()
