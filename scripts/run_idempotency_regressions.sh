#!/usr/bin/env sh
set -eu

python -m compileall -q backend scripts server.py verificar_*.py

for test_file in \
  verificar_p0_access_registration_projection.py \
  verificar_p0_registration_idempotency.py \
  verificar_p0_access_event_scope.py \
  verificar_p0_access_authority.py \
  verificar_p0_access_activation.py \
  verificar_p0_edge_admin_api.py \
  verificar_p0_device_api_security.py \
  verificar_p0_device_http_api.py \
  verificar_p0_lead_company_scope.py \
  verificar_v5_4_voucher_application_contract.py \
  verificar_v5_5_v5_6_contracts.py \
  verificar_v5_5_v5_6_db_integration.py \
  verificar_seguridad_p1.py \
  verificar_p1_auth_http_security.py \
  verificar_p1_access_distributed_lock.py \
  verificar_p1_access_concurrency_direct.py \
  verificar_persistent_sessions.py \
  verificar_session_revocation_security.py \
  verificar_multievent_isolation_20_events.py \
  verificar_e2e_10_participants_closure.py \
  verificar_v5_1_access_state_engine_shadow.py \
  verificar_v5_8_event_edge.py \
  verificar_v4.py
do
  printf 'RUN:%s\n' "$test_file"
  python "$test_file"
done
