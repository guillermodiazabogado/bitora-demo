# BITORA V5.9 Certification Matrix

| Gate | Result | Evidence |
| --- | --- | --- |
| Regression / Golden | PASS | V4 10/10, V5 10/10, divergences 0 |
| Signed Event Dataset | PASS | valid accepted, modified/invalid/wrong/expired/revoked rejected |
| Production-like PostgreSQL/R2 | NOT VERIFIED | No live credentials used in this local certification run |
| Edge Certification | PASS | normal, cloud down, reconnect, restart, invalid dataset, revoked device, duplicate, out-of-order, skew |
| Cloud Outage Offline | PASS | 5,000 operations, 0 lost ACK |
| 30/50/100 Devices | PASS | V5.9 simulator run |
| Device Local Fallback | PASS | DEVICE_LOCAL_SAFE only |
| Disaster Recovery | PASS | backup/restore plus queue recovery |
| Full Event Simulation | PASS | PRE -> LIVE -> outage -> reconnect -> POST |
