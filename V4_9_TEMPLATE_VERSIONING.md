# BITORA V4.9 Template Versioning

Templates are stable containers. Content is stored in immutable versions.

Rules:
- Creating a template creates version 1.
- Updating content creates a new version.
- Campaigns pin an exact `template_version_id`.
- Approving a template approves its current version.
- Editing an approved or active template returns the template to draft state without changing historical campaign content.

Security:
- Only catalog variables are allowed.
- Script-like content and unsafe HTML schemes are rejected.
- Preview escapes rendered values.
