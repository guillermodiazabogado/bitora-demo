# Runbook de incidentes

Aplican los runbooks previos para caída de instancia/PostgreSQL, corte de internet/LAN, cola offline, error de sincronización, dispositivo desconectado, revocación, recuperación, backup/restore y escalamiento.

La endurance estable no mezclará fallos inducidos. Los ensayos de resiliencia se ejecutarán en una fase separada y registrada.

Antes de la fase estable se verificaron en el mismo harness: caída/reinicio de una instancia, persistencia de sesión, logout y cambio de rol entre instancias, reinicio de PostgreSQL, desconexión/reconexión de base, anti-passback concurrente e idempotencia. Todos resultaron PASS. Los cortes de red física, Edge físico y notificaciones a personal permanecen pendientes de campo.
