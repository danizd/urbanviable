@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "MODE=start"
if /I "%~1"=="check" set "MODE=check"

echo [1/8] Comprobando prerequisitos...
where docker >nul 2>nul
if errorlevel 1 (
  echo ERROR: Docker no esta disponible en PATH.
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo ERROR: npm no esta disponible en PATH.
  exit /b 1
)

set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
if not defined PYTHON_EXE set "PYTHON_EXE=python"

echo [2/8] Validando artefactos ETL...
if not exist "etl\data\processed\galicia_scouting.geojson" (
  echo GeoJSON no encontrado. Ejecutando ETL...
  call "%PYTHON_EXE%" etl\process_data.py
  if errorlevel 1 (
    echo ERROR: Fallo process_data.py
    exit /b 1
  )
)

if not exist "etl\data\processed\galicia_scouting.mbtiles" (
  echo MBTiles no encontrado. Generando teselas...
  powershell -NoProfile -ExecutionPolicy Bypass -File ".\etl\generate_tiles.ps1"
  if errorlevel 1 (
    echo ERROR: Fallo generate_tiles.ps1
    exit /b 1
  )
)

if not exist "tiles_data" mkdir tiles_data
if not exist "tiles_data\config.json" (
  echo ERROR: Falta tiles_data\config.json
  exit /b 1
)

copy /Y "etl\data\processed\galicia_scouting.mbtiles" "tiles_data\galicia_scouting.mbtiles" >nul
if errorlevel 1 (
  echo ERROR: No se pudo copiar galicia_scouting.mbtiles a tiles_data
  exit /b 1
)

if exist "etl\data\processed\last_update.json" (
  copy /Y "etl\data\processed\last_update.json" "tiles_data\last_update.json" >nul
)

echo [3/8] Iniciando TileServer local (puerto 8080)...
docker rm -f urbanviable-tiles-local >nul 2>nul
powershell -NoProfile -Command "$src=(Resolve-Path '.\tiles_data').Path; docker run -d --name urbanviable-tiles-local -p 8080:8080 --mount \"type=bind,source=$src,target=/data\" maptiler/tileserver-gl --config /data/config.json | Out-Null"
if errorlevel 1 (
  echo ERROR: No se pudo iniciar urbanviable-tiles-local
  exit /b 1
)

echo [4/8] Esperando TileServer...
powershell -NoProfile -Command "$ok=$false; 1..30 | ForEach-Object { try { Invoke-WebRequest -Uri 'http://127.0.0.1:8080/data/galicia-scouting.json' -UseBasicParsing -TimeoutSec 5 | Out-Null; $ok=$true; break } catch { Start-Sleep -Milliseconds 500 } }; if($ok){exit 0}else{exit 1}"
if errorlevel 1 (
  echo ERROR: TileServer no responde en /data/galicia-scouting.json
  exit /b 1
)

if /I "%MODE%"=="check" (
  echo OK: Verificacion completada.
  exit /b 0
)

echo [5/8] Preparando frontend...
if not exist "frontend\node_modules" (
  pushd frontend
  call npm install
  if errorlevel 1 (
    popd
    echo ERROR: Fallo npm install
    exit /b 1
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

echo [8/8] Fin de start.bat
exit /b %EXIT_CODE%
