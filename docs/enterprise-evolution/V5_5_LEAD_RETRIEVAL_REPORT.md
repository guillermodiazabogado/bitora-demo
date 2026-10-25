# V5.5 Lead Retrieval Report

## SUMMARY

V5.5 implements Lead Retrieval foundation for exhibitors/sponsors using the existing BITORA participant QR. It does not create a new QR and does not expose participant data without license, authorization, and consent checks.

## DOMAIN_MODEL

Lead Retrieval builds on Company, Company Event Participation, Company Users, Device Identity, Enterprise Entity, Credential, and consent evidence.

## STANDS

`enterprise_stands` models event/company-scoped stands such as A12, sponsor lounges, and booths.

## LICENSING

`enterprise_lead_licenses` enables Lead Retrieval per event/company/stand with active, suspended, expired, revoked, and pending states.

## PARTICIPANT_RESOLUTION

Participant QR resolves through existing Enterprise Credential to Entity and legacy Person. QR/token legacy remains unchanged.

## CONSENT

`enterprise_lead_consents` records specific Lead Retrieval consent with participant entity, event, company, purpose, policy version, status, source, and allowed fields.

## DATA_SHARING_POLICY

Field filtering only permits safe configured fields. Restricted fields like document number are not returned/exported.

## LEAD_MODEL

`enterprise_leads` stores one primary lead per Company + Event + Participant, with limited data snapshot of shared fields.

## INTERACTIONS

`enterprise_lead_interactions` stores append-only scans, notes, tags, qualification changes, follow-up changes, and future exports/interactions.

## QUALIFICATION

Supported values: UNQUALIFIED, COLD, WARM, HOT.

## TAGS

Tags/interests are stored as structured JSON on interactions, scoped to the company.

## NOTES

Notes are scoped to Company/Event/Lead and are not written to the global Person record.

## FOLLOW_UP

Supported follow-up states: NEW, CONTACT, FOLLOW_UP, QUALIFIED, CLOSED.

## COMPANY_PORTAL

Foundation supports list, detail, qualification, tags, notes, follow-up, assignment, export, and scoped company access.

## PARTICIPANT_EXPERIENCE

Consent evidence is required before data sharing. Revocation is stored without erasing historical valid capture evidence.

## EXPORT

CSV export is implemented with field filtering and audit in `enterprise_lead_exports`.

## CRM_BOUNDARY

No real CRM connector is implemented. The service boundary supports future CRM export/connectors.

## OFFLINE

Offline capture foundation integrates with Device Identity and persistent operation semantics. Consent evidence must be present.

## RECONCILIATION

Offline capture reconciliation validates device capability, license, consent, participant resolution, and idempotency.

## ANALYTICS

Foundation metrics include licensed companies, stands, scans, unique leads, and exports.

## MONETIZATION_METRICS

The model captures licensed companies, licensed limits, stands, scans, unique leads, and exports without implementing billing.

## PRIVACY

Cross-company notes, qualification, leads, and exports are isolated. Export honors data sharing policy.

## SECURITY

Controls include company/event scope, active license, user authorization, device capability, consent verification, field filtering, audit, and no QR token logging.

## PERFORMANCE

Measured locally with SQLite temp DB. See `V5_5_PERFORMANCE_BASELINE.json`.

## BACKUP_RESTORE

Backup/restore includes stands, licenses, consent, leads, interactions, and export audit.

## MULTITENANT

Lead data remains scoped by organization, event, and company.

## GOLDEN_DATASET

Golden Access Dataset remains V4 10/10 and V5 10/10 with zero divergences.

## TEST_RESULTS

Dedicated verifier: `verificar_v5_5_lead_retrieval.py`.

Result: PASS.

## NO_REGRESSION

Required V4 through V5.5 gates and secret scan passed.

## RISKS

- No HubSpot/Salesforce connector yet.
- No billing/payment implementation.
- UI is foundation-level, not final visual design.
- Offline mode requires consent evidence; otherwise sharing is denied.
- Legal text/policy wording remains event-specific.

## ROLLBACK

Set `lead_retrieval = OFF`. Existing leads, consent evidence, interactions, and export audit remain stored; V4 through V5.4 continue operating.

## NEXT_RECOMMENDED_EXECPLAN

V5.6 — VAPP / Vehicle & Logistics.
