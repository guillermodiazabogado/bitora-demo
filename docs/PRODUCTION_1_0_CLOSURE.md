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
