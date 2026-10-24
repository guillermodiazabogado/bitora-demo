# BITORA 1.0.0 Production Closure

Date: 2026-10-24

## Automated gates

- Railway production health and readiness: PASS
- PostgreSQL and migrations: PASS
- R2 persistent storage and recent backup: PASS
- Background jobs, pending and failed: PASS (0/0)
- Stable HTTPS Android endpoint: PASS
- Protected Android production release workflow: PASS
- Operation and Display APK signatures: PASS (RSA-4096, v2/v3)
- APK checksums reproduced from the CI artifact: PASS
- Production demo accounts disabled: PASS
- Administrator account active with forced password change completed: PASS
- Isolated production event restore with no external effects: PASS

## Release evidence

- Production commit: `b25dcfaf5bb93d9b5c42c932d2eda71d107541db`
- Railway `/health`: version `1.0.0`, status `ok`
- Railway `/ready`: status `ready`, configuration warnings `0`
- Android production workflow: run `40114849165`, status `PASS`
- Operation APK SHA-256:
  `0a79db5b69b0f4366e4f18c83b078ea212d2e44494a342a140befdbd40a5386d`
- Display APK SHA-256:
  `83cefe384ba579c3e21a8cefbc73af7a261af947d5c37232c3a9b006e8bc0c4c`
- Signer certificate SHA-256:
  `bfc73d29956a04614655866b340c70566274c7d7d90c9206698802405297a3f3`
- Signatures: APK Signature Scheme v2/v3, RSA-4096
- Distribution: GitHub draft release `v1.0.0` (private controlled access)

## Restore certification

- Source event: `BITORA Demo Full 2026`
- Backup: `bitora-event-3-20261024-171241.zip`
- Backup SHA-256:
  `80378C9C3C8AB4D2A3C251F038A444FBE62C3A9E29E05BCF49B985D5590A4F59`
- Participants/accreditations restored: `56/56`
- Storage files restored: `8/8`
- Jobs restored inactive: `2`
- Tokens regenerated: `56`
- External effects: `0`

## Operational policy

- External email and WhatsApp delivery remain disabled in safe mode until real
  provider credentials, verified senders and webhook secrets are supplied.
- This is an intentional production configuration, not a readiness failure.
- Android distribution is private. APK hashes, version code and signer identity
  must be recorded for every rollout.

## Human acceptance gates

- Install the signed Operation APK on the designated operation devices.
- Install the signed Display APK on the designated display devices.
- Pair both app types to the final event and verify current datasets.
- Complete one controlled offline operation and confirm the queue drains after
  connectivity returns.
- Reboot one device of each app type and confirm background heartbeat recovery.
- Record the event owner approval after the final event configuration is loaded.

BITORA 1.0.0 is technically releasable when all automated gates pass. It is
operationally accepted only after the human gates above are recorded.
