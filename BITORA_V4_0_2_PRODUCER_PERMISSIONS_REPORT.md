# BITORA V4.0.2 Producer Permissions Polish Report

## Scope

V4.0.2 aligns the Producer Visual Home with effective event access. The Home is a visual representation of permissions, feature flags, and active-event context. It does not grant access and does not replace backend RBAC.

## Changes

- Added sanitized per-event `feature_flags` to `/api/events` and `/api/event`.
- Updated Producer Home card declarations with required actions and V4 feature flags.
- Changed Producer Home visibility so cards must satisfy all declared controls:
  - active event;
  - project/event module availability;
  - required module permission;
  - required action permission;
  - required V4 feature flag.
- Kept frontend and static bundles synchronized.
- Added `verificar_v4_0_2_producer_permissions_polish.py`.
- Added `BITORA_PRODUCER_HOME_ACCESS_MATRIX.md`.

## Special Modules

### Surveys

The Surveys card now requires:

- module: `surveys`;
- action: `surveys.read`;
- flag: `surveys_v4_enabled`.

Survey API endpoints already reject disabled feature flags and unauthorized event access.

### Analytics

The Analytics card now requires:

- action: `analytics.read`;
- flag: `analytics_v4_enabled`.

Analytics API endpoints already resolve event scope and enforce resource-specific permissions.

### Operations Center

The Operations Center card now requires:

- action: `operations_center.read`;
- flag: `operations_center_v4_enabled`.

Operations Center API endpoints already reject disabled feature flags and unauthorized event access.

## Security

- Backend RBAC remains authoritative.
- Hidden cards are not a security mechanism.
- Direct URL and API access remain protected by session, event scope, organization scope, feature flags, and RBAC.
- Safe Mode remains ON.
- Live Mode remains OFF.
- Real communications sent: 0.
- Secrets exposed: 0.

## Validation

- Static contract verifier: `verificar_v4_0_2_producer_permissions_polish.py`.
- Existing online health and Home verifier remain applicable.
- User Management is unchanged except for previously merged feedback behavior.

## Limitations

- The current role model does not expose arbitrary per-user permission subsets for a user that still has effective role `Productor`; limited behavior is represented through effective event role and feature flags rather than a new RBAC system.
- No Endurance was executed.
- No production deployment was executed.
- Persistent Disk was not touched.

## Result

Ready for PR after local verifier, Home regression, User Management regression, and online staging checks pass.
