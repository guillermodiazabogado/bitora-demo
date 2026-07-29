# BITORA V4.7 Privacy Policy

Default API responses avoid full personal data.

Rules:

- History summaries do not include raw audit payloads by default.
- Participant autocomplete masks email by default.
- Full participant details require `autocomplete.private.use`.
- Raw audit payload requires `history.sensitive.read`.
- Duplicate results expose masked email hints only.
- Logs and reports must not include secrets or full personal data.
