from __future__ import annotations

from backend.services.whatsapp import create_whatsapp_provider, forced_whatsapp_recipient, valid_phone


provider = create_whatsapp_provider()
config = provider.validate_configuration()
status = provider.get_status() if config.get("ok") else {"status": "configuration_error"}
print({
    "provider": provider.name,
    "ready": provider.ready,
    "config_ok": bool(config.get("ok")),
    "errors": config.get("errors") or [],
    "meta_status": status.get("status"),
    "safe_recipient_valid": valid_phone(forced_whatsapp_recipient()),
})
