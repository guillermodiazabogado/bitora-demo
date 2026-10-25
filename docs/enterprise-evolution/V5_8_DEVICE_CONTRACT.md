# BITORA V5.8 Device Contract

## Android-ready, not Android-dependent

V5.8 defines contracts a future Android client can use. It does not implement Android, APK, Kotlin, Play Store integration or mobile UI.

## Device Identity

Each device has scoped identity: organization_id, event_id, device_id, credentials, status, capabilities, dataset revision and last_seen.

## Pairing

Flow: pairing code -> admin authorization -> device identity -> profile -> event -> zone/door/config -> ready.

Pairing codes are short-lived, single-use, and stored hashed.

## Operation Envelope

Fields: operation_id, idempotency_key, organization_id, event_id, edge_id, device_id, capability, device_timestamp, edge_timestamp, sequence, dataset_revision, payload_version, result, sync_status, correlation_id.

## Device Local Fallback

Only DEVICE_LOCAL_SAFE capabilities may run on device-local fallback. All operations must persist locally and sync to Edge later.
