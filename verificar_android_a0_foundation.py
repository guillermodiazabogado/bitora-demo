from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent


REQUIRED_FILES = [
    "android/settings.gradle.kts",
    "android/build.gradle.kts",
    "android/shared/foundation/build.gradle.kts",
    "android/shared/foundation/src/main/java/com/bitora/android/foundation/model/DeviceContracts.kt",
    "android/shared/foundation/src/main/java/com/bitora/android/foundation/network/BitoraContracts.kt",
    "android/shared/foundation/src/main/java/com/bitora/android/foundation/persistence/LocalQueue.kt",
    "android/shared/foundation/src/main/java/com/bitora/android/foundation/theme/BitoraTheme.kt",
    "android/shared/foundation/src/main/java/com/bitora/android/foundation/ui/BitoraComponents.kt",
    "android/apps/operation/build.gradle.kts",
    "android/apps/operation/src/main/java/com/bitora/android/operation/MainActivity.kt",
    "android/apps/display/build.gradle.kts",
    "android/apps/display/src/main/java/com/bitora/android/display/MainActivity.kt",
    "docs/android/A0_ARCHITECTURE.md",
    "docs/android/A0_DEVICE_CONTRACT_MATRIX.md",
    "docs/android/A0_BUILD.md",
    "docs/android/A0_FINAL_REPORT.md",
]


FORBIDDEN_SECRET_PATTERNS = [
    "DATABASE_URL=",
    "R2_SECRET_ACCESS_KEY=",
    "R2_ACCESS_KEY_ID=",
    "RAILWAY_TOKEN=",
    "sk-",
]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def main() -> int:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    if missing:
        print({"status": "FAIL", "missing": missing})
        return 1

    settings = read("android/settings.gradle.kts")
    required_modules = [":shared:foundation", ":apps:operation", ":apps:display"]
    module_failures = [module for module in required_modules if module not in settings]

    operation = read("android/apps/operation/src/main/java/com/bitora/android/operation/MainActivity.kt")
    display = read("android/apps/display/src/main/java/com/bitora/android/display/MainActivity.kt")
    foundation = read("android/shared/foundation/src/main/java/com/bitora/android/foundation/model/DeviceContracts.kt")

    assertions = {
        "operation_shell": "BITORA OPERATION" in operation and "DEV profile selector" in operation,
        "display_shell": '"BITORA"' in display and '"DISPLAY"' in display and "Pairing required" in display,
        "device_identity": "DeviceIdentityState" in foundation,
        "edge_status": "BitoraEdgeStatus" in foundation,
        "dataset_status": "BitoraDatasetStatus" in foundation,
        "profiles": "ACCESS_FAST" in foundation and "SELF_SERVICE" in foundation,
    }

    secret_hits = []
    for rel in REQUIRED_FILES:
        text = read(rel)
        for pattern in FORBIDDEN_SECRET_PATTERNS:
            if pattern in text:
                secret_hits.append({"file": rel, "pattern": pattern})

    failures = [name for name, ok in assertions.items() if not ok]
    if module_failures or failures or secret_hits:
        print(
            {
                "status": "FAIL",
                "module_failures": module_failures,
                "assertion_failures": failures,
                "secret_hits": secret_hits,
            }
        )
        return 1

    print(
        {
            "status": "PASS",
            "modules": required_modules,
            "operation_shell": True,
            "display_shell": True,
            "shared_foundation": True,
            "no_secrets": True,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
