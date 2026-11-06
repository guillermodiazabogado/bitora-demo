# BITORA Android A0

Android A0 creates a separated foundation for two future products:

- BITORA Operation: event operator phones/tablets.
- BITORA Display: Android TV Box / digital signage.

This workspace is intentionally client-side only. It does not change BITORA Web, V5.9.1 certification, Railway, PostgreSQL, R2, migrations or backend contracts.

## Modules

- `shared:foundation`: common Device Identity, Edge, Dataset, queue, contracts and Design System foundation.
- `apps:operation`: Operation Alpha shell.
- `apps:display`: Display Alpha fullscreen shell.

## Build

Requires JDK, Android SDK and Gradle/Android Studio.

```powershell
cd android
gradle :apps:operation:assembleDebug :apps:display:assembleDebug
```

Expected APKs after a successful build:

- `apps/operation/build/outputs/apk/debug/operation-debug.apk`
- `apps/display/build/outputs/apk/debug/display-debug.apk`

## Operational LAB

From the repository root, start a complete persistent LAB runtime:

```powershell
.\tools\android_lab.ps1 Start
```

The command starts the pairing/Edge service and download service, creates HTTPS
tunnels, rebuilds both debug APKs against the current Edge URL, and prints the
Admin, Operation and Display URLs. Inspect or stop only the tracked processes:

```powershell
.\tools\android_lab.ps1 Status
.\tools\android_lab.ps1 Stop
```

Existing healthy endpoints can be reused when the quick-tunnel provider is
rate-limited or when a named tunnel is managed separately:

```powershell
.\tools\android_lab.ps1 Start `
  -EdgePublicUrl https://edge-lab.example.org `
  -DownloadPublicUrl https://downloads-lab.example.org
```

## Production preflight

The production preflight is fail-closed and never prints secret values:

```powershell
.\tools\android_production_preflight.ps1
.\tools\android_production_preflight.ps1 -Build
```

It requires a stable HTTPS production URL and the four external signing
variables documented in `docs/android/A10_PRODUCTION_HARDENING.md`.
