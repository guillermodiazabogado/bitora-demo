# BITORA V4.7 Normalization Policy

Normalization is conservative:

- Email: lowercase and trim.
- Document: remove non-alphanumeric characters and lowercase.
- Text: Unicode decomposition, accent removal, lowercase and whitespace compaction.

Normalization is used for search and duplicate candidate discovery. It does not mutate stored source data.
