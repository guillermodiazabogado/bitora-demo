# BITORA V4.9 Communications Architecture

The V4.9 domain is implemented in `backend/services/communications_automation.py`.

Core boundaries:
- HTTP routes perform authentication, RBAC and event scope checks.
- `CommunicationsAutomationService` owns domain rules.
- `SinkProvider` normalizes provider behavior without external effects.
- Existing `jobs` infrastructure can enqueue campaign execution with `communications.campaign.execute`.
- Existing audit service records material state changes.

Data model:
- `communication_v4_templates`
- `communication_v4_template_versions`
- `communication_v4_segments`
- `communication_v4_campaigns`
- `communication_v4_campaign_recipients`
- `communication_v4_messages`
- `communication_v4_deliveries`
- `communication_v4_attempts`
- `communication_v4_consents`
- `communication_v4_suppressions`
- `communication_v4_unsubscribes`
- `communication_v4_automations`
- `communication_v4_automation_runs`
- `communication_v4_provider_events`
- `communication_v4_approvals`
