@echo off
setlocal
cd /d "%~dp0"
set "PY=C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" (
  echo No se encontro Python empaquetado en:
  echo %PY%
  pause
  exit /b 1
)
set "QR_HOST=0.0.0.0"
set "QR_REQUIRE_LOGIN=1"
start "Plataforma acreditaciones red local" "%PY%" "%~dp0backend\app.py"
timeout /t 2 /nobreak >nul
start http://localhost:8787
echo Consola protegida con PIN.
echo PIN inicial Admin: 1234
echo PIN inicial Recepcion: 2222
echo PIN inicial Acceso: 3333
pause
endlocal
