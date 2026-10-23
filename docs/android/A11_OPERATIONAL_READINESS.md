# Android A11 Operational Readiness

## Implemented

- One-command LAB lifecycle with `Start`, `Status` and `Stop` actions
- Pairing/Edge and APK download health checks
- Automatic rebuild of Operation and Display against the active Edge endpoint
- Persistent hidden service processes tracked through ignored runtime state
- Retry and cleanup for quick-tunnel DNS failures
- Reuse of externally managed or named tunnel endpoints
- Fail-closed production preflight for endpoint and signing inputs
- Release artifact SHA-256 reporting when production inputs are present
- CI instrumentation matrix on Android API 26 and API 35
- Pilot, telemetry and rollback runbook
- Privacy-minimized heartbeat telemetry for app version, environment, queue depth
  and synchronization duration
- Operational monitor with stale-heartbeat, missing-dataset and queue-depth alerts

## Local acceptance evidence

- LAB lifecycle result: `RUNNING`
- Edge health: PASS
- Download health: PASS
- Operation APK download: HTTP 200
- Display APK download: HTTP 200
- Operation ZIP SHA-256: `60088EE02E7B600191C930D51C2E2E1AB8C21C4B82118EE5DA6F9FE5B73AB102`
- Display ZIP SHA-256: `044C7A5B6695B30065E1DA1C0812D0A1DBD06B07215A677FFF1FE37E813B0789`
- Public-download hashes match the local A11 artifacts
- A11 operational verifier: PASS
- Full Android build and A0-A11 verifier suite: PASS
- Final Operation heartbeat: 2026-10-23 17:01:59 America/Buenos_Aires,
  device `lab-d6bd2d50cc`, profile `SELF_SERVICE`, status `ACTIVE`
- Operation telemetry: version `0.11.1-a11-debug`, environment `LAB`, queue
  pending `0`, synchronization duration `1206 ms`
- Final Display heartbeat: 2026-10-23 16:52:05 America/Buenos_Aires,
  device `lab-30e5ad59e7`, profile `DISPLAY`, status `ACTIVE`
- Display telemetry: version `0.11.1-a11-debug`, environment `LAB`, queue
  pending `0`, synchronization duration `502 ms`
- Both final devices reported dataset revision `LAB-A9-18-010` with no alerts
- Physical A11 Operation and Display acceptance: PASS

Runtime URLs and process IDs are stored only in ignored files under `tmp/`.
They are intentionally excluded from source control because quick-tunnel URLs are
temporary environment data.

## Production boundary

LAB is operational. Production remains fail-closed until an owner supplies the
stable HTTPS endpoint and the four protected release-signing values. The
preflight reports these missing inputs without printing secrets or creating an
unsigned distributable.
