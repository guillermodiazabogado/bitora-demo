# Android A10 Production Hardening

## Completed in block 1

- Separate debug and release application identities
- Version `1.0.0` with production package names
- DEV tools disabled in release through immutable BuildConfig fields
- LAB test actions and diagnostics gated out of release
- Stable HTTPS endpoint policy for production
- Pairing and returned Edge endpoints validated before identity persistence
- Fail-closed UI when the production endpoint is not configured
- Backup disabled and cleartext traffic rejected
- R8 code shrinking and resource shrinking enabled
- Operation and Display debug builds, release builds, unit tests and lint PASS
- Release signing reads only external environment variables
- Android CI builds, tests, shrinks and runs every phase verifier
- Gradle Wrapper and generated-file exclusions make builds reproducible
- Immediate and 15-minute background synchronization with network constraints
- Exponential retry for unavailable Edge services
- Persistent unique WorkManager jobs recovered after process/device restart
- Shared idempotent queue flushing for foreground and background sync
- Instrumented persistence and WorkManager recovery tests for API 26 and API 35
- CI emulator matrix for minimum and current supported Android versions
- Remote CI recovery matrix passed on API 26 and API 35
- Production RSA-4096 signing identity provisioned in the protected
  `android-production` GitHub environment
- Manual production release workflow validates configuration, builds both APKs,
  verifies signatures, records SHA-256 checksums and uploads private artifacts
- Private rollout, telemetry, pilot and rollback runbook

## Physical evidence

- Display device `lab-043c44801c` recovered from `RETRY: UnknownHostException`
  to `Background: SUCCESS` after the LAB Edge endpoint migration.
- The Edge LAB received the matching heartbeat on 2026-10-23 at 11:45:11
  America/Buenos_Aires with dataset revision `LAB-A9-18-010`.
- This certifies real WorkManager execution, network retry recovery, dataset sync,
  and heartbeat delivery on the physical Display device.
- After a full device reboot, the Edge LAB received another automatic heartbeat
  at 13:14:48 America/Buenos_Aires without manual synchronization. This certifies
  WorkManager restart recovery on the physical Display device.

## Production release boundary

The stable production endpoint is configured in the protected
`android-production` GitHub environment. The protected production workflow has
completed successfully and produced signed Operation and Display APKs.

Distribution remains private and controlled. Promotion beyond the internal
pilot still requires the physical-device gates in `A10_ROLLOUT_RUNBOOK.md`.

## Fulfilled production inputs

- Stable production pairing/Edge/Admin base URL
- Confirmed production application IDs
- RSA-4096 production signing identity in protected CI secrets
- Successful protected production release workflow
