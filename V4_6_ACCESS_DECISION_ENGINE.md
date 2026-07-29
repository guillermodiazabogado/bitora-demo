# BITORA V4.6 - Access Decision Engine

Orden de decision:

1. tenant y evento;
2. zona;
3. credencial;
4. estado de acreditacion;
5. vigencia de zona;
6. override;
7. asignacion;
8. resultado final.

Resultados: `ALLOWED`, `DENIED`, `EXPIRED`, `REVOKED`, `INVALID_CREDENTIAL`, `WRONG_EVENT`, `WRONG_ZONE`, `OUTSIDE_TIME_WINDOW`.
