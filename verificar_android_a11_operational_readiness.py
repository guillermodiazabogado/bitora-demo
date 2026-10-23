from pathlib import Path


ROOT = Path(__file__).resolve().parent
LAB = (ROOT / "tools/android_lab.ps1").read_text(encoding="utf-8")
PREFLIGHT = (ROOT / "tools/android_production_preflight.ps1").read_text(encoding="utf-8")
README = (ROOT / "android/README.md").read_text(encoding="utf-8")
REPORT = (ROOT / "docs/android/A11_OPERATIONAL_READINESS.md").read_text(encoding="utf-8")
EDGE_CLIENT = (ROOT / "android/shared/foundation/src/main/java/com/bitora/android/foundation/edge/EdgeClient.kt").read_text(encoding="utf-8")
LAB_SERVER = (ROOT / "tools/android_pairing_lab_server.py").read_text(encoding="utf-8")
MONITOR = (ROOT / "tools/android_operational_monitor.ps1").read_text(encoding="utf-8")
OPERATION = (ROOT / "android/apps/operation/src/main/java/com/bitora/android/operation/MainActivity.kt").read_text(encoding="utf-8")
DISPLAY = (ROOT / "android/apps/display/src/main/java/com/bitora/android/display/MainActivity.kt").read_text(encoding="utf-8")

checks = {
    "lab_lifecycle": all(value in LAB for value in ('"Start"', '"Status"', '"Stop"', "android_lab_runtime.json")),
    "persistent_processes": LAB.count("Start-Process") >= 3 and LAB.count('WindowStyle = "Hidden"') >= 3 and LAB.count("Start-HealthyTunnel") >= 3,
    "endpoint_rebuild": "-PbitoraPairingBaseUrl=$edgeUrl" in LAB,
    "health_checks": "edgeHealthy" in LAB and "downloadHealthy" in LAB,
    "existing_endpoints": "EdgePublicUrl" in LAB and "DownloadPublicUrl" in LAB and "externallyManagedEdge" in LAB,
    "artifact_urls": "operationUrl" in LAB and "displayUrl" in LAB,
    "production_fail_closed": 'status = if ($ready) { "READY" } else { "BLOCKED" }' in PREFLIGHT and "exit 1" in PREFLIGHT,
    "production_endpoint": all(value in PREFLIGHT for value in ("https", ".trycloudflare.com", ".example", ".invalid")),
    "external_signing": all(value in PREFLIGHT for value in ("BITORA_ANDROID_KEYSTORE_PATH", "BITORA_ANDROID_KEYSTORE_PASSWORD", "BITORA_ANDROID_KEY_ALIAS", "BITORA_ANDROID_KEY_PASSWORD")),
    "release_hashes": "Get-FileHash" in PREFLIGHT and "SHA256" in PREFLIGHT,
    "documented": "android_lab.ps1" in README and "android_production_preflight.ps1" in README,
    "acceptance_report": "LAB lifecycle result: `RUNNING`" in REPORT and "Production remains fail-closed" in REPORT,
    "telemetry_contract": all(value in EDGE_CLIENT for value in ("HeartbeatTelemetry", "softwareVersion", "queuePending", "syncDurationMs")),
    "manual_sync_telemetry": all("HeartbeatTelemetry(" in source and "BuildConfig.VERSION_NAME" in source for source in (OPERATION, DISPLAY)),
    "telemetry_endpoint": "/api/admin/telemetry" in LAB_SERVER and "HEARTBEAT_STALE" in LAB_SERVER and "QUEUE_DEPTH_HIGH" in LAB_SERVER,
    "operational_monitor": "android_lab_runtime.json" in MONITOR and 'status -ne "HEALTHY"' in MONITOR,
}

status = "PASS" if all(checks.values()) else "FAIL"
print({"status": status, **checks})
raise SystemExit(0 if status == "PASS" else 1)
