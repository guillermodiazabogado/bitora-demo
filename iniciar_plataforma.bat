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
start "Plataforma acreditaciones" "%PY%" "%~dp0backend\app.py"
timeout /t 2 /nobreak >nul
start http://localhost:8787
endlocal
