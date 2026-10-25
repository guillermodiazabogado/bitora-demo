# BITORA V5.8 Event Dataset Spec

## Dataset Model

V5.8 extends enterprise_event_datasets with schema_version v5.8 and EVENT_EDGE_FULL dataset_type.

Included data is minimized by capability: event identity, credential status, revocations, doors, zones, entitlements, rules, service points, device profiles, capability classes and configuration revisions.

## Integrity

Dataset checksum is deterministic over canonical JSON payload. Checksum is integrity, not cryptographic signature.

## Activation

DOWNLOAD -> VERIFY -> STAGE -> ACTIVATE.

Invalid datasets are not activated over the last valid CURRENT dataset.

## Freshness

Statuses: CURRENT, STALE, EXPIRED, INVALID, UNAVAILABLE.
