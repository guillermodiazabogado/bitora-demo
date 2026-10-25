# BITORA V5.8 Event Network Architecture

## Recommended Topology

- Router/firewall with WAN1 and optional WAN2.
- Managed switch for wired critical devices.
- Event Edge server on event LAN.
- Access terminals wired where possible.
- APs for mobile/handheld devices.
- Public attendee Wi-Fi separated from operational VLAN.
- UPS for router, switch, Edge server and critical APs.

## Failure Modes

- WAN down: Cloud OFFLINE, Edge LIVE can continue certified local operations.
- LAN degraded: Event operation DEGRADED.
- Edge unavailable: only DEVICE_LOCAL_SAFE fallback may continue.
- Dataset expired/invalid: NOT_READY for affected capabilities.

Vendor-neutral: no hardware brand is required.
