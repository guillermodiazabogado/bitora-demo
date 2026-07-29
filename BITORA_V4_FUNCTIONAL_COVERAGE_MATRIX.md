# BITORA V4 Functional Coverage Matrix

Estado formal: FUNCTIONALLY COMPLETE - PENDING FINAL CERTIFICATION

| Dominio | Version | Estado | Feature flag | Endpoints/UI | RBAC | Auditoria | Backup/Restore | Verificador | Limitaciones |
|---|---|---:|---|---|---|---|---|---|---|
| eventos | core | PASSED | core | events | RBAC | audit_logs | incluido | verificar_integridad_bitora.py | - |
| inscripciones | core | PASSED | core | accreditations | RBAC | audit_logs | incluido | verificar_integridad_bitora.py | - |
| participantes | core | PASSED | core | people/accreditations | RBAC | audit_logs | incluido | verificar_integridad_bitora.py | - |
| actividades | core | PASSED | core | activities | RBAC | audit_logs | incluido | verificar_integridad_bitora.py | - |
| reservas | core | PASSED | core | reservations | RBAC | audit_logs | incluido | verificar_reservas.py | - |
| QR | core | PASSED | core | QR/credential | RBAC | audit_logs | incluido | verificar_integridad_bitora.py | - |
| acreditacion | core | PASSED | core | update/check-in | RBAC | audit_logs | incluido | verificar_seguridad_basica.py | - |
| asistencia | V4.1 | PASSED | attendance_v4_enabled | attendance | attendance.* | audit | incluido | verificar_v4_1_attendance_domain.py | - |
| cierre | V4.2 | PASSED | attendance_closure_eligibility_v4_enabled | attendance-closures | attendance.closure.* | audit | incluido | verificar_v4_2_attendance_closure_eligibility.py | - |
| elegibilidad | V4.2 | PASSED | attendance_closure_eligibility_v4_enabled | eligibility | attendance.eligibility.* | audit | incluido | verificar_v4_2_attendance_closure_eligibility.py | - |
| certificados | V4.3 | PASSED | certificates_v4_enabled | certificates | certificates.* | audit | incluido | verificar_v4_3_certificates_foundation.py | - |
| encuestas | V4.4 | PASSED | surveys_v4_enabled | surveys | surveys.* | audit | incluido | verificar_v4_4_surveys_foundation.py | anonimato por umbral |
| speakers | V4.5 | PASSED | speakers_v4_enabled | speakers | speakers.* | audit | incluido | verificar_v4_5_speakers_foundation.py | - |
| zonas | V4.6 | PASSED | zone_permissions_v4_enabled | zones | zones.* | audit | incluido | verificar_v4_6_zone_permissions_foundation.py | ocupacion exacta no inferida |
| historial | V4.7 | PASSED | history_autocomplete_v4_enabled | history | history.* | audit | incluido | verificar_v4_7_history_autocomplete_foundation.py | - |
| autocompletado | V4.7 | PASSED | history_autocomplete_v4_enabled | autocomplete | autocomplete.* | audit | incluido | verificar_v4_7_history_autocomplete_foundation.py | - |
| operations center | V4.8 | PASSED | operations_center_v4_enabled | operations-center | operations_center.* | audit | incluido | verificar_v4_8_operations_center.py | - |
| comunicaciones | V4.9 | PASSED | communications_v4_enabled | communications-v4 | communications.* | audit | safe restore | verificar_v4_9_communications_automation.py | Live Mode OFF |
| automatizaciones | V4.9 | PASSED | communications_automation_v4_enabled | communications-v4 | communications.automations.* | audit | paused restore | verificar_v4_9_communications_automation.py | no envia proveedores en V4.10 |
| analytics | V4.10 | PASSED | analytics_v4_enabled | analytics-v4 | analytics.* | audit | reconstruible | verificar_v4_10_analytics_functional_closure.py | pendiente certificacion final |
