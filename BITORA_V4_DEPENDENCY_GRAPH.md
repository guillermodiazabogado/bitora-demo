# BITORA V4 Dependency Graph

```mermaid
flowchart TD
  RC["RC certified baseline"] --> Contracts["V4 contracts"]
  Contracts --> Attendance["V4.1 Attendance"]
  Attendance --> Closing["V4.2 Attendance closing"]
  Closing --> Certificates["V4.3 Certificates"]
  Attendance --> Surveys["V4.4 Surveys"]
  Contracts --> Speakers["V4.5 Speakers"]
  Attendance --> Zones["V4.6 Zone permissions"]
  Certificates --> History["V4.7 Participant history"]
  Surveys --> History
  History --> Autocomplete["V4.7 Autocomplete"]
  Attendance --> Incidents["Incident management"]
  Incidents --> Operations["V4.8 Operations center"]
  Certificates --> Communications["V4.9 Communications"]
  Surveys --> Communications
  Communications --> Automation["V4.9 Supervised automation"]
  Attendance --> Analytics["V4.10 Analytics"]
  Certificates --> Analytics
  Surveys --> Analytics
```

## Bloqueantes

Contratos de ownership, permisos y auditoria deben cerrarse antes de implementar entidades. Asistencia bloquea certificados, parte de analytics y parte del centro operativo.

## Paralelizables

Disertantes puede avanzar luego de contratos base. Encuestas puede avanzar en paralelo con certificados si comparte elegibilidad via contrato estable. Incidencias puede avanzar en paralelo con zonas si mantiene ownership evento.

## Dependencias Futuras

Migraciones: asistencia, certificados, encuestas, disertantes, zonas e incidencias.
Backend: servicios por dominio y repositorios.
UI: admin por modulo, portal participante, portal disertante y centro operativo.
Worker: certificados, comunicaciones, automatizaciones y report snapshots.
