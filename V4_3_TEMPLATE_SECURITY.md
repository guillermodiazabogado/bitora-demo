# V4.3 Template Security

La version inicial no acepta HTML libre. Se bloquean:

- `script`
- `iframe`
- `object`
- `embed`
- eventos `onload` / `onerror`
- `javascript:`
- `file://`
- URLs externas
- `data:`
- `@import`

No hay ejecucion de codigo en plantillas.
