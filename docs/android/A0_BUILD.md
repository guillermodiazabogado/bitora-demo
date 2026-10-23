# Android A0 Build

## Requirements

- JDK 17 or newer
- Android SDK with API 35
- Gradle or Android Studio

For A0.1 a portable local toolchain was used under `C:\Users\Noxie-PC\.codex\android-toolchain`:

- JDK: Temurin 17.0.20.1
- Android SDK: command line tools 19.0, API 35, build-tools 35.0.0
- Gradle: 8.10.2

## Commands

```powershell
cd android
gradle :shared:foundation:assemble :apps:operation:assembleDebug :apps:display:assembleDebug
```

## APK Names

Generated Alpha APKs:

- `android/artifacts/a0/bitora-operation-alpha-a0.apk`
- `android/artifacts/a0/bitora-display-alpha-a0.apk`

Release signing is intentionally deferred.
