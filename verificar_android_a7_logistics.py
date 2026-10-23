from pathlib import Path
R=Path(__file__).resolve().parent
p=(R/'android/apps/operation/src/main/java/com/bitora/android/operation/LogisticsPanel.kt').read_text()
m=(R/'android/apps/operation/src/main/java/com/bitora/android/operation/MainActivity.kt').read_text()
l=(R/'tools/android_pairing_lab_server.py').read_text()
c={'profile':'"LOGISTICS" -> LogisticsPanel' in m and '"LOGISTICS"' in l,'routing':'"LOGISTICS" -> LogisticsPanel' in m,'event':'operationType = "VEHICLE_ACCESS"' in p,'duplicate':'ALREADY_ENTERED' in p,'offline':'loadActiveDataset()' in p and 'syncOperationQueue' in p,'privacy':'vehicle_ref' in p and '.put("token"' not in p,'lab':all(x in l for x in ('BITORA:A7:VALID','BITORA:A7:DENY','BITORA:A7:OFFLINE'))}
s='PASS' if all(c.values()) else 'FAIL'; print({'status':s,**c}); raise SystemExit(0 if s=='PASS' else 1)
