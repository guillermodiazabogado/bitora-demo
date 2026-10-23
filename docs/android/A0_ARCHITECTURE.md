# Android A0 Architecture

## Scope

A0 starts the Android line separately from BITORA Web certification. It creates a reusable foundation for BITORA Operation and BITORA Display without backend changes.

## Runtime Shape

BITORA Cloud -> BITORA Event Edge -> Event LAN -> Android Device Platform -> Operation / Display.

The Android layer adapts to V5.8 contracts:

- Device Identity
- Pairing
- Device Profile
- Event Dataset
- Persistent Queue
- Sync/Reconciliation
- Device Local Fallback for explicitly safe capabilities

## Modules

- `android/shared/foundation`: models, contracts, local queue interface, theme and UI primitives.
- `android/apps/operation`: phone/tablet operation shell with DEV profile selector.
- `android/apps/display`: fullscreen display shell for Android TV/TV Box.

## Security

No production secrets are stored in source. A0 uses placeholder state only. Release signing keys are intentionally not generated.

## Roll Forward

Android A1 should connect pairing code generation/authorization to V5.8 Device Identity and Device Profiles.
