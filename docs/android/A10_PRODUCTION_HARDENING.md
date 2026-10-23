# Android A10 Production Hardening

## Completed in block 1

- Separate debug and release application identities
- Version `0.11.1-a11` with production package names
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

## Deliberately not distributable yet

Release APKs are unsigned and have no production endpoint. They must not be
installed or distributed as production artifacts.

## External inputs still required

- Stable production pairing/Edge base URL
- Production signing keystore and secure CI secret references
- Confirmed Android application IDs and ownership
- Production Admin pairing endpoints and rollout environment

## Remaining A10 blocks

- First successful remote CI emulator-matrix run
- Production inputs and execution of the approved pilot runbook
