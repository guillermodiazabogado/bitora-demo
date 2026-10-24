from pathlib import Path


ROOT = Path(__file__).resolve().parent
OP_BUILD = (ROOT / "android/apps/operation/build.gradle.kts").read_text(encoding="utf-8")
DISPLAY_BUILD = (ROOT / "android/apps/display/build.gradle.kts").read_text(encoding="utf-8")
OP_MAIN = (ROOT / "android/apps/operation/src/main/java/com/bitora/android/operation/MainActivity.kt").read_text(encoding="utf-8")
DISPLAY_MAIN = (ROOT / "android/apps/display/src/main/java/com/bitora/android/display/MainActivity.kt").read_text(encoding="utf-8")
HTTP = (ROOT / "android/shared/foundation/src/main/java/com/bitora/android/foundation/network/HttpPairingClient.kt").read_text(encoding="utf-8")
POLICY = (ROOT / "android/shared/foundation/src/main/java/com/bitora/android/foundation/network/EndpointPolicy.kt").read_text(encoding="utf-8")
BACKGROUND = (ROOT / "android/shared/foundation/src/main/java/com/bitora/android/foundation/sync/BitoraBackgroundSync.kt").read_text(encoding="utf-8")
SYNC_ENGINE = (ROOT / "android/shared/foundation/src/main/java/com/bitora/android/foundation/sync/EdgeSyncEngine.kt").read_text(encoding="utf-8")
MANIFESTS = "\n".join(
    (ROOT / path).read_text(encoding="utf-8")
    for path in (
        "android/apps/operation/src/main/AndroidManifest.xml",
        "android/apps/display/src/main/AndroidManifest.xml",
    )
)
PANELS = "\n".join(
    (ROOT / f"android/apps/operation/src/main/java/com/bitora/android/operation/{name}").read_text(encoding="utf-8")
    for name in ("AccessFastPanel.kt", "ReceptionPanel.kt", "ServicePanel.kt", "LeadRetrievalPanel.kt", "LogisticsPanel.kt")
)
CI = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
PRODUCTION_RELEASE = (ROOT / ".github/workflows/android-production-release.yml").read_text(encoding="utf-8")
INSTRUMENTED = "\n".join(
    path.read_text(encoding="utf-8")
    for path in (ROOT / "android/shared/foundation/src/androidTest").rglob("*.kt")
)
RUNBOOK = (ROOT / "docs/android/A10_ROLLOUT_RUNBOOK.md").read_text(encoding="utf-8")

checks = {
    "release_identity": 'applicationId = "com.bitora.operation"' in OP_BUILD and 'applicationId = "com.bitora.display"' in DISPLAY_BUILD,
    "debug_isolation": all('applicationIdSuffix = ".alpha"' in source for source in (OP_BUILD, DISPLAY_BUILD)),
    "release_dev_off": all('buildConfigField("boolean", "DEV_TOOLS_ENABLED", "false")' in source for source in (OP_BUILD, DISPLAY_BUILD)),
    "r8": all("isMinifyEnabled = true" in source and "isShrinkResources = true" in source for source in (OP_BUILD, DISPLAY_BUILD)),
    "endpoint_policy": all(value in POLICY for value in ('uri.scheme == "https"', '.trycloudflare.com', "isLoopback", "uri.userInfo")),
    "endpoint_enforced": "edge_endpoint_not_allowed" in HTTP and "pairing_endpoint_not_allowed" in HTTP,
    "fail_closed_ui": "CONFIGURATION REQUIRED" in OP_MAIN and "CONFIGURATION REQUIRED" in DISPLAY_MAIN,
    "dev_ui_gated": PANELS.count("BuildConfig.DEV_TOOLS_ENABLED") >= 5 and "if (BuildConfig.DEV_TOOLS_ENABLED)" in OP_MAIN,
    "manifest_hardening": MANIFESTS.count('android:allowBackup="false"') == 2 and MANIFESTS.count('android:usesCleartextTraffic="false"') == 2,
    "release_outputs": all(
        any((ROOT / path).exists() for path in candidates)
        for candidates in (
            (
                "android/apps/operation/build/outputs/apk/release/operation-release.apk",
                "android/apps/operation/build/outputs/apk/release/operation-release-unsigned.apk",
            ),
            (
                "android/apps/display/build/outputs/apk/release/display-release.apk",
                "android/apps/display/build/outputs/apk/release/display-release-unsigned.apk",
            ),
        )
    ),
    "external_signing": all(
        value in OP_BUILD and value in DISPLAY_BUILD
        for value in ("BITORA_ANDROID_KEYSTORE_PATH", "BITORA_ANDROID_KEYSTORE_PASSWORD", "BITORA_ANDROID_KEY_ALIAS", "BITORA_ANDROID_KEY_PASSWORD")
    ),
    "wrapper": all((ROOT / path).exists() for path in ("android/gradlew", "android/gradlew.bat", "android/gradle/wrapper/gradle-wrapper.jar", "android/gradle/wrapper/gradle-wrapper.properties")),
    "ci": "assembleRelease" in CI and "testDebugUnitTest" in CI and "verificar_android_a*.py" in CI,
    "production_release": all(
        value in PRODUCTION_RELEASE
        for value in (
            "environment: android-production",
            "BITORA_ANDROID_PRODUCTION_BASE_URL",
            "android_production_preflight.ps1",
            "apksigner",
            "sha256sum",
            "upload-artifact@v4",
        )
    ),
    "background_sync": all(value in BACKGROUND for value in ("PeriodicWorkRequestBuilder", "OneTimeWorkRequestBuilder", "NetworkType.CONNECTED", "BackoffPolicy.EXPONENTIAL")),
    "restart_recovery": "enqueueUniquePeriodicWork" in BACKGROUND and "ExistingPeriodicWorkPolicy.UPDATE" in BACKGROUND,
    "shared_queue_flush": "flushOperations" in SYNC_ENGINE and "ACKNOWLEDGED" in SYNC_ENGINE and "DUPLICATE" in SYNC_ENGINE,
    "scheduled_by_apps": "BitoraBackgroundSync.schedule" in OP_MAIN and "BitoraBackgroundSync.schedule" in DISPLAY_MAIN,
    "instrumented_recovery": all(value in INSTRUMENTED for value in ("encryptedIdentitySurvivesStoreRecreation", "datasetQueueAndWorkerStateSurviveStoreRecreation", "schedulesImmediateAndPeriodicRecoveryWork")),
    "device_matrix": "api-level: [26, 35]" in CI and "connectedDebugAndroidTest" in CI,
    "rollout_runbook": all(value in RUNBOOK for value in ("Pilot rings", "Telemetry contract", "Rollback triggers", "Rollback procedure")),
}

status = "PASS" if all(checks.values()) else "FAIL"
print({"status": status, **checks})
raise SystemExit(0 if status == "PASS" else 1)
