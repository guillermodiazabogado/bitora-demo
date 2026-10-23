from pathlib import Path

ROOT = Path(__file__).resolve().parent
PANEL = (ROOT / "android/apps/operation/src/main/java/com/bitora/android/operation/LeadRetrievalPanel.kt").read_text(encoding="utf-8")
MAIN = (ROOT / "android/apps/operation/src/main/java/com/bitora/android/operation/MainActivity.kt").read_text(encoding="utf-8")
LAB = (ROOT / "tools/android_pairing_lab_server.py").read_text(encoding="utf-8")

checks = {
    "profile": '"LEAD_RETRIEVAL" -> LeadRetrievalPanel' in MAIN and '"LEAD_RETRIEVAL"' in LAB,
    "routing": '"LEAD_RETRIEVAL" -> LeadRetrievalPanel' in MAIN,
    "durable_event": 'operationType = "LEAD_CAPTURE"' in PANEL,
    "idempotency": ':LEAD:${identity.deviceId}:$tokenHash' in PANEL,
    "duplicate": "ALREADY_CAPTURED" in PANEL,
    "consent": "CONSENT_REQUIRED" in PANEL and "lead_consent" in PANEL,
    "offline": "loadActiveDataset()" in PANEL and "syncOperationQueue" in PANEL,
    "privacy": "participant_ref" in PANEL and '.put("token"' not in PANEL,
    "lab": all(v in LAB for v in ("BITORA:A6:VALID", "BITORA:A6:DENY", "BITORA:A6:OFFLINE")),
}
status = "PASS" if all(checks.values()) else "FAIL"
print({"status": status, **checks})
raise SystemExit(0 if status == "PASS" else 1)
