# BITORA V4.5 - Self-Service Access

Los tokens de autogestion:

- se generan con alta entropia;
- se almacenan como SHA-256;
- exponen solo `token_hint` en auditoria;
- pueden vencer;
- pueden revocarse;
- quedan limitados a un perfil.

No crean un sistema de login paralelo.
