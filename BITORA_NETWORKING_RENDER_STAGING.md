# BITORA Networking Render Staging Pilot

Date: 2026-08-15

This note records the existing Render route for the BITORA Networking V2.4 pilot. It does not introduce a new hosting architecture.

## Existing Render Route

- Git repository: `https://github.com/guillermodiazabogado/bitora-demo.git`
- Deploy branch: `deployment/v4-online`
- Render web service: `bitora-staging`
- Render service id: `srv-d9p5pn6gekts73f8u24g`
- Render database: `bitora-staging-postgres`
- Public HTTPS host: `https://bitora-staging.onrender.com`
- Runtime: Docker via `Dockerfile`
- Start command: `python backend/app.py`
- Health check: `/health`
- Auto deploy: disabled in `render.yaml`; deploy is manual from Render dashboard/API.

## Deployable Checkpoint

- Verified V2.4 checkpoint: `3dbea536b528ee0088edf6039ac4a3bd1b16d07b`
- Deployment branch prepared at: `9a51bcdda735dea12689817917055256b0faae4d`
- Extra deployment fix: `ci: ignore checksum evidence in secret scan`

The extra commit changes only the CI secret scanner so generated checksum evidence is not mistaken for provider tokens. It does not change Networking runtime behavior.

## Persistence

The Render blueprint uses PostgreSQL for application data:

- `QR_DB_ENGINE=postgres`
- `QR_POSTGRES_DSN` from `bitora-staging-postgres`
- `DATABASE_URL` from `bitora-staging-postgres`

This means event, Networking, contact, Discovery, launch and operations data are not stored only on the ephemeral web-service filesystem.

Storage/backups use the existing BITORA storage configuration. Older Render staging notes mention Free-plan local persistent disk limitations; the current deployed health endpoint reports `storage.backend=r2` and `backup=recent`, but an operator should still take/confirm a backup before a manual Render deploy that may run migrations.

## Public URL Configuration

The authoritative public host in `render.yaml` is:

- `BASE_URL=https://bitora-staging.onrender.com`
- `BITORA_PUBLIC_URL=https://bitora-staging.onrender.com`
- `HTTPS_REQUIRED=true`
- `BITORA_ALLOWED_HOSTS=bitora-staging.onrender.com`
- `BITORA_CORS_ORIGINS=https://bitora-staging.onrender.com`

Networking QR/deep links must use the deployed HTTPS host and must not contain `localhost`, LAN hosts, auth tokens, or owner session values.

## Manual Render Deploy Gate

Codex prepared and validated the deployment branch, but no Render deploy credential was available locally:

- no `RENDER_API_KEY`
- no `RENDER_TOKEN`
- no `RENDER_DEPLOY_HOOK`
- no Render CLI
- unauthenticated Render API deploy attempt returned HTTP 401

Required operator action:

1. Open Render dashboard.
2. Select service `bitora-staging`.
3. Confirm source branch `deployment/v4-online`.
4. Confirm latest commit `9a51bcdda735dea12689817917055256b0faae4d`.
5. Confirm backup/recovery posture for the staging database.
6. Trigger manual deploy.
7. Wait for deploy completion and inspect logs for build, migration, startup, port and static-serving errors.

## Post-Deploy Smoke

After Render reports the deploy complete, verify from `https://bitora-staging.onrender.com`:

1. `/health` returns `status=ok`.
2. `/ready` returns `status=ready`.
3. `networking.html`, `networking-admin.html` and `networking-register.html` load.
4. A configured participant opens the Digital Credential.
5. The credential QR payload uses the Render HTTPS host.
6. Anonymous QR open shows only the permitted public profile.
7. Public QR does not authenticate the profile owner.
8. A second authenticated participant saves the scanned profile.
9. Repeated save remains one canonical Networking contact.
10. Golden Ticket opens Discovery onboarding or the live Discovery stream according to the participant state.
11. My Contacts and Networking Admin reflect the activity.

## Pilot Event Procedure

Use normal BITORA configuration and data, not source-code edits:

1. Create or select a small pilot event.
2. Configure event branding with safe BITORA or test-event identity.
3. Configure Networking launch state and presentation mode.
4. Configure public URL as `https://bitora-staging.onrender.com`.
5. Enable Discovery only if the pilot should exercise Discovery.
6. Add 5-10 test participants across at least two organizations.
7. Include permitted and restricted channels.
8. Add offers, seeks, sectors, functions and objectives for Discovery.
9. Activate at least User A and User B through normal authentication.

## Two-Phone Test

Phone A:

1. Log in as User A.
2. Open the Digital Credential.
3. Keep the QR visible.

Phone B:

1. Use the normal phone Camera app, not the BITORA scanner.
2. Scan User A's QR.
3. Confirm the HTTPS Render public profile opens.
4. Confirm User A is not authenticated by the QR.
5. Log in or register as User B when offered.
6. Confirm return to User A's public profile.
7. Save User A.
8. Confirm User A appears in User B's My Contacts.
9. Open Golden Ticket and test Discovery.

Reverse the test with User B showing the credential and User A scanning.

## Rollback

Fastest code rollback:

1. In Render, redeploy the previous successful deployment if available.
2. Or reset `deployment/v4-online` to the previous known commit and trigger a manual Render deploy.

Known previous online commit before Networking V2.4 branch update:

- `9b1f3e65cf65208cce568f6023fedc6b144c5ffa`

V2.4 is schema-neutral. Do not restore the database unless a migration or data incident is evidenced. If database rollback is required, use the latest verified Render/PostgreSQL backup and validate restore in isolation first.

## Current Status

- Deployment branch pushed: yes.
- GitHub CI for deployment branch: passed.
- Render service currently reachable: yes.
- Render currently serving V2.4: no, still reports `version=RC1-live-demo-10` until manual deploy occurs.
- Pilot event configured on deployed V2.4: blocked until Render deploy and admin access.
- Real phone QR test: manual required.
