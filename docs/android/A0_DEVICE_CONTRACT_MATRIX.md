# Android A0 Device Contract Matrix

| Android Requirement | Existing V5.8 Contract | Status |
|---|---|---|
| Device identity | `enterprise_devices`, Device Contract scoped by organization/event/device | READY |
| Pairing | short-lived pairing code -> admin authorization -> device identity | READY |
| Device profile | V5.8 `enterprise_device_profiles` | READY |
| Capabilities | V5.8 capability execution classes | READY |
| Event dataset | V5.8 EVENT_EDGE_FULL dataset, minimized by capability | READY |
| Dataset revision | dataset revision/checksum/signature path from V5.8/V5.9 | READY |
| Local operation envelope | V5.8 operation envelope fields | READY |
| Persistent queue | V5.8 Edge queue contract; Android local queue foundation added | PARTIAL |
| Device local fallback | only `DEVICE_LOCAL_SAFE` capabilities | READY |
| Display content contracts | signage priority/content contracts not yet backend-backed | MISSING FOR A1+ |
| Offline media cache | client architecture placeholder only | PARTIAL |
| Watchdog/auto-start | future Android Display operational feature | MISSING FOR A1+ |

No backend changes were made for missing items.
