# BITORA V4 Render Staging Deployment Report

Fecha: 2026-08-04

Initial branch: `deployment/v4-online`

Initial release: `v4.0.0`

Initial develop/v4 reference: `5173691c24cc8d522bb51990f8a3ed96d09faa4a`

Current HEAD: `4c70d4224acba79f3fc140ae1413248d165f4f59`

GitHub authentication: BROWSER SESSION PASSED / CLI TOKEN INVALID

Render authentication: PASSED

Hosting provider: Render

## Render resources

| Resource | Value |
| --- | --- |
| Blueprint | `bitora-v4-staging` |
| Blueprint ID | `exs-d9p5l3bm8hqs73acbmo0` |
| PostgreSQL service | `bitora-staging-postgres` |
| Web service | `bitora-staging` |
| Web service ID | `srv-d9p5pn6gekts73f8u24g` |
| Web service plan | `Free` |
| Runtime | Docker |
| Branch | `deployment/v4-online` |
| Public URL | `https://bitora-staging.onrender.com` |
| Deploy commit | `4c70d42` |
| Deployment PR | `#12` |

## Deployment result

| Check | Result |
| --- | --- |
| Render Blueprint sync | PASSED |
| Render PostgreSQL live | PASSED |
| Render web service live | PASSED |
| HTTPS | PASSED |
| `/health` | PARTIAL, `backup=missing` |
| `/ready` | PARTIAL, persistent storage warning |
| Login online | PASSED |
| UI load | PASSED |
| Safe Mode | ON |
| Live Mode | OFF |
| Unauthorized communications | 0 observed |
| Real personal data | 0 introduced |
| Endurance 24h | DEFERRED |
| Production | NOT DEPLOYED |

## Validation details

Remote `/health`:

- `status`: `ok`
- `env`: `staging`
- `db`: `online`
- `jobs.status`: `ok`
- `storage.backend`: `local`
- `backup`: `missing`

Remote `/ready`:

- `configuration`: true
- `database`: true
- `migrations`: true
- `storage`: true
- `safe_mode`: true
- `live_mode_off`: true
- warning: `Storage local requiere disco persistente y backup externo`

Security headers observed:

- HSTS: present
- Referrer-Policy: present
- X-Content-Type-Options: present
- Content-Security-Policy: not observed

## Blocking issue

Render Free does not support Persistent Disks. The Render dashboard shows an `Enable Disk Access` modal explaining that disks require upgrading the instance.

This blocks:

- storage persistent online;
- backup online;
- restore online;
- restart persistence certification;
- final PR merge under the online staging acceptance criteria.

## PR status

| Check | Result |
| --- | --- |
| PR #12 checks | PASSED, `2 / 2 checks OK` |
| PR #12 conflicts | PASSED, `No conflicts with base branch` |
| PR #12 merge readiness in GitHub | READY |
| PR #12 merge decision | NOT MERGED |

PR `#12` remains open because infrastructure acceptance is incomplete.

## Final state

`READY FOR HOSTING APPROVAL`

No stable release is declared.

No production deployment was performed.

No Endurance 24h was executed.
