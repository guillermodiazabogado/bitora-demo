# BITORA V5.8 Event Edge Architecture

## Summary

V5.8 formalizes BITORA Event Edge as the local operational layer for LIVE events. It reuses V5.2 Device Identity, Event Dataset, Persistent Queue, Sync and Reconciliation foundations. No second Edge system was created.

Architecture:

BITORA Cloud -> WAN Sync -> BITORA Event Edge -> Event LAN -> Devices -> Device Local fallback.

## Reuse From V5.2

- enterprise_devices
- enterprise_event_datasets
- enterprise_edge_queue
- enterprise_edge_reconciliations
- enterprise_device_heartbeats
- DeviceEdgeSyncService
- AccessStateEngine shadow/domain logic

## V5.8 Additions

- enterprise_event_edges
- enterprise_device_profiles
- enterprise_device_pairing_codes
- enterprise_capability_execution_classes
- enterprise_edge_checkpoints
- EventEdgeService

## Live Principle

Cloud offline does not automatically mean event offline. If Edge is LIVE/READY and dataset is CURRENT, certified EDGE_LOCAL_SAFE operations continue locally and sync later.

## Rollback

Flags OFF keep V4 through V5.7.3 behavior intact. V5.8 data is retained but inactive.
