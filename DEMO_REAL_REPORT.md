# Demo Real V4.0.5

## Objetivo

Crear una demo realista para validar la plataforma completa antes de V4.1, sin integrar WhatsApp, email ni pagos reales.

## Datos generados

- Evento: Congreso de Innovacion Neuquen 2027.
- Participantes simulados: 500.
- Espacios: 5.
- Actividades: 20.
- Tipos: General, VIP, Prensa, Staff, Sponsor y Disertante.
- Reservas confirmadas y listas de espera.
- Bolsas de cupos por actividad.
- Pantalla publica configurada.
- Portal participante operativo.
- Comunicaciones demo registradas.
- Backups antes y despues de crear la demo.

## Acceso desde el panel

En el panel operativo:

1. Abrir `Crear Demo Real`.
2. Escribir `DEMO`.
3. Confirmar la accion.

La accion crea backup previo, limpia datos operativos actuales, genera la demo y crea backup posterior.

## Participantes demo

El dashboard muestra una seccion `Participantes demo para probar` con 5 accesos rapidos:

- Abrir portal.
- Ver QR.
- Agenda.
- Reservas.

## Guia manual incluida

El dashboard muestra una guia con pasos para probar landing publica, portal, reservas, lista de espera, impresion, acceso QR, QR repetido, actividad reservada/no reservada, pantalla publica y dashboard operativo.

## Prueba automatica

Script:

```powershell
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' verificar_demo_real.py
```

Valida evento, participantes, espacios, actividades, tipos, bolsas, reservas, lista de espera, portal, pantalla publica, QR, accesos, backups y auditoria.
