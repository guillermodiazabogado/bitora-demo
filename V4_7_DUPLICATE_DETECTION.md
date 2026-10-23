# BITORA V4.7 Duplicate Detection

Duplicate candidates are suggestions, not automatic merges.

Signals:

- Exact normalized email: probable match.
- Exact normalized `dni`: probable match.
- Normalized full-name similarity using SQL `LIKE`: possible match.

Decisions are stored in `duplicate_resolution_decisions` with:

- organization
- event
- candidate person
- decision
- reason
- actor
- timestamp

Supported decisions:

- `CONFIRMED_MATCH`
- `DISMISSED`
