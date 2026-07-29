# BITORA V4.9 Approval Policy

Approvals are explicit records in `communication_v4_approvals`.

Template approval:
- Requires `communications.templates.approve`.
- Applies only to the current version.

Campaign approval:
- Requires validated recipients.
- Requires `communications.campaigns.approve`.
- A material change requires revalidation and reapproval.

Execution:
- Requires `communications.campaigns.execute`.
- Live Mode remains off unless explicitly enabled and separately permitted.
