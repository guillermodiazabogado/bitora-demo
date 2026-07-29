# BITORA V4.7 Multitenant Report

V4.7 queries resolve organization from the event and do not trust tenant identifiers supplied by the client.

Validated:

- Event history from another organization is rejected.
- Participant autocomplete does not leak other organizations.
- Duplicate candidates are limited to the current organization.
- Duplicate decisions for another organization's person are rejected.

Result:

`Cross-tenant leaks: 0`
