from pathlib import Path


ROOT = Path(__file__).resolve().parent
DISPLAY = (ROOT / "android/apps/display/src/main/java/com/bitora/android/display/MainActivity.kt").read_text(encoding="utf-8")
BUILD = (ROOT / "android/apps/display/build.gradle.kts").read_text(encoding="utf-8")
LAB = (ROOT / "tools/android_pairing_lab_server.py").read_text(encoding="utf-8")

checks = {
    "profile": 'requestedProfile = "DISPLAY"' in DISPLAY,
    "version": 'softwareVersion = "android-a11-${BuildConfig.VERSION_NAME}"' in DISPLAY and 'versionName = "1.0.0"' in BUILD,
    "content": 'optJSONObject("display_content")' in DISPLAY and all(value in LAB for value in ("BITORA LIVE", "Bienvenidos al Evento 18", "MAIN_HALL")),
    "verified_dataset": "DatasetVerifier(identity.credentialToken).verify" in DISPLAY and "saveActiveDataset(envelope)" in DISPLAY,
    "offline": "displayOfflineSnapshot" in DISPLAY and "loadActiveDataset()" in DISPLAY,
    "sync": '"SYNC CONTENT"' in DISPLAY and "edge.heartbeat" in DISPLAY,
    "lab_revision": 'LAB-A9-{event_id}-010' in LAB,
}

status = "PASS" if all(checks.values()) else "FAIL"
print({"status": status, **checks})
raise SystemExit(0 if status == "PASS" else 1)
