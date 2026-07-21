# Seguridad De Integraciones

## Cifrado

BITORA usa `BITORA_INTEGRATION_ENCRYPTION_KEY` para cifrar secretos mediante Fernet.

En produccion o staging la clave debe estar configurada. En desarrollo local se permite una clave derivada solo para no bloquear pruebas.

## No exposicion

Las APIs eliminan `configuration_encrypted` y enmascaran valores sensibles como:

- token;
- api_key;
- password;
- secret;
- access_token;
- refresh_token;
- app_secret.

## Safe mode

El safe mode puede definirse por organizacion y complementa las variables globales.

Si una organizacion define destinatario forzado, se usa ese valor para pruebas.
