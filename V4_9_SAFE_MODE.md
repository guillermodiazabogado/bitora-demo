# BITORA V4.9 Safe Mode

V4.9 is safe by default.

Configuration:
- `BITORA_COMMUNICATIONS_V4_ENABLED=false` by default.
- `BITORA_COMMUNICATIONS_AUTOMATION_V4_ENABLED=false` by default.
- `BITORA_COMMUNICATIONS_LIVE_MODE_ENABLED=false` by default.

When executing locally or in staging:
- email recipients can be forced with `COMMUNICATIONS_FORCE_EMAIL_RECIPIENT`;
- WhatsApp recipients can be forced with `COMMUNICATIONS_FORCE_WHATSAPP_RECIPIENT`;
- provider execution uses a sink provider unless Live Mode is explicitly enabled by configuration.

The V4.9 verifier confirms real external communications sent: 0.
