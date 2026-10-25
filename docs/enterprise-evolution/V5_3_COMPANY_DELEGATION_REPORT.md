# V5.3 Company & Delegation Portal Report

## SUMMARY

V5.3 implements the Company and Delegation Portal foundation behind feature flags. BITORA remains authoritative, V4 access contracts remain untouched, and V5 access enforcement remains disabled.

## DOMAIN_MODEL

The model separates Organization, Event, Company, Delegation, Person, Accreditation, User, Entity, Entitlement, and Permission. Company and Delegation records are event-scoped where operational permissions, quotas, memberships, and invitations are involved.

## COMPANY

`enterprise_companies` stores external participating entities such as exhibitors, sponsors, press, suppliers, contractors, institutions, and partners.

## EVENT_PARTICIPATION

`enterprise_company_event_participation` links a company to one event with role, status, approval mode, validity fields, metadata, and an Enterprise Entity mapping.

## DELEGATIONS

`enterprise_delegations` stores event-scoped company groups and maps each delegation to Enterprise Entity when available.

## MEMBERSHIP

`enterprise_delegation_members` links Person/Accreditation/Enterprise Entity to a company and optional delegation without copying personal data.

## QUOTAS

`enterprise_company_quotas` tracks allocated, reserved, consumed, and available counts by company/delegation/quota type.

## COMPANY_USERS

`enterprise_company_users` stores external scoped users with roles `COMPANY_ADMIN`, `DELEGATION_MANAGER`, and `VIEWER`. These users do not become BITORA admins.

## INVITATIONS

`enterprise_invitations` uses secure random tokens, stores only hashes and hints, supports expiration, revocation, completion, idempotency, and company/delegation scope.

## APPROVAL_WORKFLOW

`enterprise_approval_requests` supports submitted, pending review, approved, and rejected outcomes with reviewer, timestamp, reason, and source.

## BULK_IMPORT

CSV import implements preview/validation before confirm. It detects required columns, invalid emails, duplicates in file, existing people reuse, and idempotent repeated imports.

## DUPLICATE_HANDLING

People are reused by the existing V4 global email identity. V5.3 does not remove or weaken the current global `people.email` uniqueness.

## PORTAL

The functional portal foundation is represented by scoped service/API-ready operations for dashboard, people, invitations, import, delegations, and status. Visual UI is intentionally not finalized in this ExecPlan.

## ORGANIZER_VIEW

Organizer operations are supported through the service layer: companies, delegations, quotas, invitations, approvals, import jobs, membership status, suspension-ready status fields, and audit trail.

## AUTHORIZATION

Company authorization derives from organization, event, company, user email, role, and permissions. Cross-company and cross-event access is denied by scope.

## PRIVACY

Company users can only operate within their own company/event scope. No global participant search, survey data, networking data, private notes, or unrelated company data is exposed.

## AUDIT

Administrative operations record audit entries for company creation, company-event linking, user grants, quota changes, delegation creation, invitation creation/revocation, and approvals.

## DOMAIN_EVENTS

Relevant business facts are recorded in Enterprise Domain Events, including company-event linking and delegation member registration.

## PERFORMANCE

Performance was measured locally using SQLite temp DB. These numbers are reproducible test baselines, not production capacity claims. See `V5_3_PERFORMANCE_BASELINE.json`.

## BACKUP_RESTORE

V5.3 tables are included in event backup and isolated restore with ID remapping for companies, delegations, people, accreditations, entities, invitations, approvals, import jobs, and quotas.

## MULTITENANT

All V5.3 operations are scoped by organization and event. Tests cover cross-company and cross-event isolation.

## GOLDEN_DATASET

The V5.0 Golden Access Dataset remains 10/10 for V4 and 10/10 for V5 after V5.3.

## TEST_RESULTS

Dedicated verifier: `verificar_v5_3_company_delegation_portal.py`.

Result: PASS.

## NO_REGRESSION

Required no-regression gate passed across V4, participant scope, multievent, backup/restore, security, V5.0, V5.1, V5.2, V5.3, and secret scan.

## RISKS

- Visual Company Portal UI is foundation-level, not final design.
- CSV import is intentionally conservative and does not resolve ambiguous identities automatically.
- Company users are service/API scoped; production login UX needs a later hardening pass.
- Performance is local SQLite only.
- Lead Retrieval, vouchers, and commercial entitlements remain future phases.

## ROLLBACK

Set `delegations = OFF` and `company_portal = OFF`. Existing data remains stored, while V4/V5.0/V5.1/V5.2 continue operating.

## NEXT_RECOMMENDED_EXECPLAN

V5.4 — ENTITLEMENTS & VOUCHERS.
