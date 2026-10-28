# BITORA Edge reference client

This directory contains a transport-neutral reference client for the BITORA
V5.8 device contract. It is a simulator and integration aid, **not certified
hardware, an Android application, or an approved production Edge appliance**.

It demonstrates:

- a durable SQLite/WAL operation queue;
- monotonic per-device sequence numbers across restarts;
- local idempotency keys;
- HMAC-SHA256 dataset checksum/signature verification compatible with
  `EventEdgeService`;
- injectable heartbeat and batch-sync transport;
- bounded exponential retry state; and
- log redaction for the device secret and dataset signing keys.

The database stores the operational queue, but the device credential is only
held in memory by this reference implementation. A production client must use
the operating system's hardware-backed keystore, certificate pinning, secure
provisioning, disk encryption, supervised upgrades and device-management
controls.

Run the isolated verifier from the repository root:

```powershell
C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m tools.edge_client.verify_reference_client
```

The verifier uses no sockets or external services. It queues 100 offline
operations, recreates the client over the same database, reconnects through an
in-memory transport, checks idempotency and rejects a corrupted dataset.
