# BITORA V4.9 Campaign Lifecycle

Supported states:
- DRAFT
- VALIDATING
- APPROVED
- SCHEDULED
- RUNNING
- PAUSED
- COMPLETED
- PARTIALLY_FAILED
- FAILED
- CANCELLED
- RESTORED_REVIEW

Flow:
1. Create campaign.
2. Validate recipients.
3. Approve campaign.
4. Execute directly or enqueue a job.
5. Store message, delivery and attempt evidence.

Restore policy:
- Restored campaigns are moved to `RESTORED_REVIEW`.
- Live Mode remains disabled.
