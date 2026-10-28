# Riesgos residuales

- Readiness 503 rápido aprobado en prueba automatizada; corte real Docker/red con balanceador pendiente.
- Docker local no disponible; las pruebas integradas requieren runner autorizado.
- Endurance de 6/12 horas no ejecutada.
- Hardware, red y operadores físicos no verificados.
- Staging externo y monitoreo operativo no autorizados.
- El workflow de 60 minutos reserva 30 minutos adicionales para instalación, restore, build y CVE; la suficiencia de esa ventana debe confirmarse en la ejecución real.
- Vouchers, leads y vehículos no forman parte de la mezcla del runner integrado actual y permanecen fuera de esta endurance.
