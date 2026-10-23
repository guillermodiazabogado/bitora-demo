# BITORA Networking V2.3 - Event Launch, Branding & Deployment Readiness

## Starting State

- Expected checkpoint verified: `fdcfb5f feat: add networking organizer operations dashboard`.
- Branch during implementation: `chore/final-endurance-certification`.
- Pre-existing unrelated work preserved: `R2_RESTORE_ISOLATED_VALIDATION.json`.
- No `AGENTS.md` was present.

## Scope

V2.3 makes Networking launchable as an event-specific product through configuration.

Preserved:

- Digital Credential;
- public QR/deep links;
- canonical contacts;
- Golden Ticket and Discovery;
- V2.1 rotation/recycle;
- V2.2 organizer operations;
- event isolation;
- privacy and anti-directory boundaries;
- no AI/ML, no new Discovery ranking, no CRM, no CMS and no event-specific source branches.

## Event Branding

V2.3 reuses existing event landing branding where possible:

- `events.landing_logo_data`
- `events.landing_primary_color`
- `events.landing_secondary_color`

V2.3 adds Networking launch/brand fields:

- `networking_brand_title`
- `networking_brand_welcome`
- `networking_brand_mode`
- `networking_public_base_url`
- `networking_launch_state`
- `networking_launched_at`
- `networking_launch_updated_at`

Safe defaults:

- title falls back to event name;
- primary color falls back to BITORA navy;
- accent falls back to BITORA gold;
- missing logo falls back to BITORA logo and is a warning, not a blocker.

Brand config accepts controlled text, hex colors and safe logo references only. It does not accept arbitrary HTML/CSS/JS.

## Participant Surfaces

The event brand now appears on:

- Digital Credential;
- public QR/deep-link profile;
- Discovery onboarding through shared CSS tokens;
- Discovery stream through the same profile card/brand tokens.

QR modules remain standard high-contrast SVG. Branding accents do not recolor QR modules.

## Public URL Architecture

Authoritative public link behavior:

1. Event-specific `networking_public_base_url`, when configured.
2. Runtime configured base URL fallback in server context.
3. Local development fallback for non-production test use.

Networking public profile URLs remain event-participation scoped:

`<base>/n/<NET-public-profile-id>`

Public profile IDs are not owner credentials and cannot authenticate a participant session.

## Launch States

`networking_launch_state` supports:

- `DRAFT`: configured/prelaunch, public profile scans are safely unavailable.
- `LIVE`: public QR/deep links resolve permitted public profiles.
- `DISABLED`: reversible emergency/off state; data is preserved.

Launching or disabling never:

- rewrites profiles;
- regenerates tokens;
- deletes contacts;
- resets Discovery;
- changes participant semantics.

Discovery can be disabled while Networking is live.

## Launch Readiness

Authoritative service:

- `NetworkingService.launch_readiness(db, event_id, fallback_base_url, app_env)`

Admin endpoints:

- `GET /api/networking/brand`
- `POST /api/networking/brand`
- `GET /api/networking/launch`
- `POST /api/networking/launch`

Launch readiness returns:

- `NOT_READY`
- `READY_WITH_WARNINGS`
- `READY`

Checks are explainable and include stable keys, severity, message and action.

Blocking examples:

- no participants;
- invalid public URL;
- production-like launch using local/non-HTTPS URL.

Warning examples:

- missing event logo;
- incomplete profiles;
- weak Discovery vocabulary;
- small Discovery pool.

Info examples:

- Discovery disabled intentionally;
- event configured;
- QR deep-link structure available.

## Admin Launch Panel

`networking-admin.html` includes a compact launch section for:

- title/welcome/mode;
- primary/accent color;
- logo reference;
- public base URL;
- launch check;
- launch;
- disable;
- return to prelaunch.

The V2.2 operations panel also includes launch state/checks.

## Public Behavior

Before launch:

- owner preview with owner token works;
- normal public QR scans do not expose the profile;
- the public response is safe and generic.

After launch:

- QR/deep links resolve the correct event participation;
- visible public profile data respects privacy;
- logged-in/owner flows remain separate from public token resolution.

Disabled:

- public routes stop resolving profiles;
- state and reports remain intact;
- re-enable is safe.

Invalid token:

- returns a safe not-found response.

## Backup/Restore

New launch/brand fields live on `events`, so event backup/restore includes them through the existing event-row export/restore path.

Verified:

- brand title;
- public base URL;
- primary color;
- launch state coherence after restore.

## Client Input Checklist

Ask the event/client for:

1. Event public display name.
2. Optional short welcome text.
3. Event logo.
4. Primary brand color.
5. Accent color if distinct.
6. Public host/domain for Networking QR links.
7. Participant source/import file.
8. Desired profile mode: organization-first, person-first or auto.
9. Whether Discovery should be enabled for launch.

No client should need to provide source-code changes.

## New Event Deployment Runbook

1. Create event.
2. Configure presentation mode and readiness.
3. Configure brand title, colors and logo.
4. Configure public Networking base URL.
5. Import participants.
6. Activate/test at least one participant profile.
7. Configure Discovery if the event will use it.
8. Inspect live vocabulary.
9. Open Launch Check.
10. Fix blocking checks.
11. Preview credential/public profile as owner/admin.
12. Test QR with a standard camera.
13. Launch Networking.
14. Monitor V2.2 operations.
15. Disable/re-enable only if needed; do not delete event data.

## Manual Certification

Automated tests structurally verify QR/deep-link behavior, but real launch certification still requires:

1. Phone A opens an active participant credential.
2. Phone B scans the Networking QR with the normal camera app.
3. Confirm the public profile opens on the configured public host.
4. Confirm Phone B is not authenticated as the owner.
5. Login/register scanner if applicable.
6. Confirm return to scanned profile.
7. Save contact.
8. Confirm contact appears in My Contacts.
9. Repeat on the actual staging/production hostname from outside the local network.
10. Visually inspect credential, public profile and Discovery with real event branding.

Do not mark external internet reachability as passed from local structural tests alone.

## Known Limitations

- V2.3 does not provision DNS, TLS certificates or hosting.
- V2.3 does not implement custom domains beyond configured base URL support.
- No WYSIWYG/page builder exists.
- Missing logo is only a launch warning.
- Local development can still use local URLs; production-like readiness blocks unsafe local/non-HTTPS launch configuration.

## Verification

Dedicated:

```powershell
python verificar_networking_v2_3.py
```

Regression:

```powershell
python verificar_networking_v2_2.py
python verificar_networking_v2_1.py
python verificar_networking_v2.py
python verificar_networking_v1_3.py
python verificar_networking_v1_2.py
python verificar_networking_v1_1.py
python verificar_networking_v1.py
python verificar_event_restore.py
python verificar_backup_restore.py
python verificar_auth_red.py
python verificar_landing_config.py
```
