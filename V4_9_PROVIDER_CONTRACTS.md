# BITORA V4.9 Provider Contracts

Provider result shape:
- accepted;
- provider_message_id;
- provider_status;
- error_code;
- error_message_sanitized;
- retryable.

The initial provider is `SinkProvider`.

It gives deterministic, auditable results without real external effects. Existing email and WhatsApp providers remain untouched by this sprint.
