@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "MODE=start"
if /I "%~1"=="check" set "MODE=check"
set "PAUSE_ON_EXIT=1"
if /I "%~2"=="--no-pause" set "PAUSE_ON_EXIT=0"
if /I "%~1"=="--no-pause" set "PAUSE_ON_EXIT=0"

echo [1/8] Comprobando prerequisitos...
where docker >nul 2>nul
if errorlevel 1 (
  echo ERROR: Docker no esta disponible en PATH.
  exit /b 1
)

call :ensure_docker_daemon
if errorlevel 1 (
  echo ERROR: Docker daemon no disponible. Abre Docker Desktop y vuelve a intentar.
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo ERROR: npm no esta disponible en PATH.
  goto :fail
)

set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
if not defined PYTHON_EXE set "PYTHON_EXE=python"

echo [2/8] Validando artefactos pre-generados...
if not exist "tiles_data" mkdir tiles_data
if not exist "tiles_data\galicia_scouting.mbtiles" (
  echo ERROR: Falta tiles_data\galicia_scouting.mbtiles. Genera los tiles primero con etl/generate_tiles.ps1
  goto :fail
)
if not exist "tiles_data\config.json" (
  echo ERROR: Falta tiles_data\config.json
  goto :fail
)

echo [3/8] Iniciando TileServer local (puerto 8080)...
docker rm -f urbanviable-tiles-local >nul 2>nul
powershell -NoProfile -Command "$src=(Resolve-Path '.\tiles_data').Path; docker run -d --name urbanviable-tiles-local -p 8080:8080 --mount \"type=bind,source=$src,target=/data\" maptiler/tileserver-gl --config /data/config.json | Out-Null"
if errorlevel 1 (
  echo ERROR: No se pudo iniciar urbanviable-tiles-local
  goto :fail
)

echo [4/8] Esperando TileServer...
powershell -NoProfile -Command "$ok=$false; 1..30 | ForEach-Object { try { Invoke-WebRequest -Uri 'http://127.0.0.1:8080/data/galicia-scouting.json' -UseBasicParsing -TimeoutSec 5 | Out-Null; $ok=$true; break } catch { Start-Sleep -Milliseconds 500 } }; if($ok){exit 0}else{exit 1}"
if errorlevel 1 (
  echo ERROR: TileServer no responde en /data/galicia-scouting.json
  goto :fail
)

if /I "%MODE%"=="check" (
  echo OK: Verificacion completada.
  goto :success
)

echo [5/8] Preparando frontend...
if not exist "frontend\node_modules" (
  pushd frontend
  call npm install
  if errorlevel 1 (
    popd
    echo ERROR: Fallo npm install
    goto :fail
  )
  popd
)

echo [6/8] Iniciando servidor local de estado (puerto 8081)...
set "STATUS_PID="
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "$c=Get-NetTCPConnection -LocalPort 8081 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess; if($c){$c}"`) do set "STATUS_PID=%%P"
if defined STATUS_PID taskkill /PID !STATUS_PID! /F >nul 2>nul

powershell -NoProfile -Command "$py='%PYTHON_EXE%'; $dir=(Resolve-Path '.\tiles_data').Path; Start-Process -WindowStyle Hidden -FilePath $py -ArgumentList '-m','http.server','8081','--directory',$dir"

echo [7/8] Arrancando frontend en modo desarrollo...
pushd frontend
set "REACT_APP_TILE_URL=/tiles"
set "REACT_APP_DATA_STATUS_URL=/api/status"
start "" http://localhost:5173
call npm run start
set "EXIT_CODE=%ERRORLEVEL%"
popd

if not "%EXIT_CODE%"=="0" (
  echo ERROR: El frontend termino con codigo %EXIT_CODE%.
  goto :fail
)
goto :success

:success
if "%PAUSE_ON_EXIT%"=="1" (
  echo.
  echo Script completado correctamente. Pulsa una tecla para cerrar esta ventana.
  pause >nul
)
exit /b 0

:fail
if "%PAUSE_ON_EXIT%"=="1" (
  echo.
  echo Pulsa una tecla para cerrar esta ventana.
  pause >nul
)
exit /b 1

:ensure_docker_daemon
docker info >nul 2>nul
if not errorlevel 1 exit /b 0

set "DOCKER_DESKTOP=%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
if exist "%DOCKER_DESKTOP%" (
  echo Docker daemon no disponible. Intentando abrir Docker Desktop...
  start "" "%DOCKER_DESKTOP%"
  powershell -NoProfile -Command "$ready=$false; 1..60 | ForEach-Object { try { docker info | Out-Null; $ready=$true; break } catch { Start-Sleep -Seconds 2 } }; if($ready){exit 0}else{exit 1}"
  if not errorlevel 1 exit /b 0
)
exit /b 1
