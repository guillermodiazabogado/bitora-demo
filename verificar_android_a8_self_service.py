from pathlib import Path


ROOT = Path(__file__).resolve().parent
PANEL = (ROOT / "android/apps/operation/src/main/java/com/bitora/android/operation/ReceptionPanel.kt").read_text(encoding="utf-8")
MAIN = (ROOT / "android/apps/operation/src/main/java/com/bitora/android/operation/MainActivity.kt").read_text(encoding="utf-8")
LAB = (ROOT / "tools/android_pairing_lab_server.py").read_text(encoding="utf-8")

checks = {
    "profile": 'requestedProfile = "SELF_SERVICE"' in MAIN,
    "routing": '"SELF_SERVICE" -> ReceptionPanel' in MAIN,
    "check_in": '"SELF_SERVICE_CHECK_IN"' in MAIN and 'operationType = operationType' in PANEL,
    "badge_request": 'print_requested' in PANEL and 'expectedProfile == "SELF_SERVICE"' in PANEL,
    "duplicate": "ALREADY_CHECKED_IN" in PANEL,
    "offline": "loadActiveDataset()" in PANEL and "syncOperationQueue" in PANEL,
    "privacy": "credential_ref" in PANEL and '.put("token"' not in PANEL,
    "lab": all(value in LAB for value in ("BITORA:A8:VALID", "BITORA:A8:DENY", "BITORA:A8:OFFLINE")),
}

status = "PASS" if all(checks.values()) else "FAIL"
print({"status": status, **checks})
raise SystemExit(0 if status == "PASS" else 1)
