# V4.3 Certificate Domain Model

Entidades:

- `certificate_types`: categoria funcional y reglas operativas.
- `certificate_templates`: contenedor editable.
- `certificate_template_versions`: contenido publicado e inmutable.
- `certificate_batches`: lote de emisiones.
- `certificate_issuances`: acto de emision.
- `certificate_documents`: archivo PDF y hashes.
- `certificate_verification_tokens`: token publico hasheado.
- `certificate_revocations`: revocacion formal.
- `certificate_reissuances`: enlace entre emision anterior y nueva.
- `certificate_number_sequences`: numeracion por alcance.

Toda entidad tiene `organization_id` y, donde corresponde, `event_id`.
