# BITORA V5 Discovery - Domain Model

## Entity

Representa un sujeto operativo generico.

Tipos futuros:

- PERSON;
- CREDENTIAL;
- VEHICLE;
- COMPANY;
- DEVICE;
- STAND;
- DELEGATION.

Mapeo inicial recomendado:

- PERSON -> people + accreditations.
- CREDENTIAL -> accreditations.token.
- COMPANY -> people.company inicialmente, luego tabla formal.
- DEVICE -> nuevo registro por terminal.

## Identity

Conjunto de atributos verificables de una entity:

- nombre;
- documento;
- email;
- telefono;
- foto/documento futuro;
- estado de verificacion.

No implementar KYC/biometria en V5 inicial.

## Credential

Objeto que permite presentarse ante el sistema:

- QR actual;
- QR dinamico futuro;
- NFC/RFID futuro;
- credencial impresa;
- token portal.

Debe poder revocarse sin borrar historial.

## Permission

Autorizacion administrativa/RBAC para usuarios del sistema.

No mezclar con Entitlement operativo del participante.

## Entitlement

Derecho operativo consumible o verificable:

- ingresar a zona;
- ingresar por puerta;
- asistir a charla;
- retirar kit;
- consumir voucher;
- estacionar;
- usar backstage;
- generar credenciales como empresa.

Campos conceptuales:

- organization_id;
- event_id;
- entity_id;
- type;
- scope;
- allocated;
- consumed;
- status;
- valid_from;
- valid_until;
- metadata.

## Rule

Condicion que determina si un Entitlement puede ejercerse:

- ventana horaria;
- puerta/zona;
- cupo;
- cooldown;
- anti-passback;
- estado de acreditacion;
- revocacion;
- consentimiento.

## Zone / Door

Zone representa area logica/fisica. Door representa punto de control. El modulo V4.6 de zonas debe extenderse, no reemplazarse.

## Device

Terminal autenticada para operar:

- id;
- tipo;
- evento asignado;
- ultima conexion;
- version;
- permisos;
- dataset revision;
- sync state.

## Vehicle

Futuro VAPP:

- patente;
- conductor/person;
- empresa;
- ventana horaria;
- puerta;
- destino;
- check-in/check-out.

## Company / Delegation

Agrupa personas, cupos y permisos operativos:

- sponsor;
- expositor;
- prensa;
- proveedor;
- staff externo.

Debe permitir aprobacion, carga masiva, invitaciones y auditoria.
