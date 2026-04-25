# UrbanViable

Plataforma de scouting comercial para Galicia con calculo de score en GPU (cliente).

## Flujo completo

## Arranque rapido local

Ejecuta desde la raiz del proyecto:

```bat
start.bat
```

El script:
- valida/genera artefactos ETL si faltan,
- levanta `urbanviable-tiles-local` en `127.0.0.1:8080`,
- levanta un servidor de estado en `127.0.0.1:8081`,
- arranca frontend (`npm run start`) con proxies de Vite.

Modo validacion (sin lanzar frontend):

```bat
start.bat check
```

1. Preparar datos de entrada del ETL

```powershell
cd c:\Proyextos\UrbanViable
python etl\download_data.py --download-osm
```

Coloca manualmente estas fuentes si faltan:
- `etl/data/secciones_censales/*.shp`
- `etl/data/renta.csv`
- `etl/data/catastro/**/*.ZIP` (opcional en MVP tecnico; el ETL aplica fallback si no existe)

2. Ejecutar ETL y generar GeoJSON

```powershell
python etl\process_data.py
```

Salida:
- `etl/data/processed/galicia_scouting.geojson`
- `etl/data/processed/last_update.json`

3. Generar teselas MBTiles

```bash
bash etl/generate_tiles.sh
```

En Windows PowerShell:

```powershell
./etl/generate_tiles.ps1
```

El script de PowerShell usa `tippecanoe` local si existe y, si no,
cae automaticamente a WSL Ubuntu ejecutando `etl/generate_tiles.sh`.

Si necesitas instalar Tippecanoe en WSL:

```powershell
wsl -d Ubuntu -u root -- bash -lc "apt-get update && apt-get install -y tippecanoe"
```

Salida:
- `etl/data/processed/galicia_scouting.mbtiles`

4. Publicar artefactos de teselas

Copia estos archivos a `tiles_data/`:
- `galicia_scouting.mbtiles`
- `last_update.json`

```powershell
Copy-Item etl/data/processed/galicia_scouting.mbtiles tiles_data/galicia_scouting.mbtiles -Force
Copy-Item etl/data/processed/last_update.json tiles_data/last_update.json -Force
```

5. Frontend

```powershell
cd frontend
npm install
npm run build
```

6. Levantar despliegue con Docker

```powershell
cd c:\Proyextos\UrbanViable
docker compose up -d
```

## Endpoints esperados

- Estado datos: `/api/status`
- Metadata tileset: `/tiles/galicia-scouting.json`
- Teselas: `/tiles/galicia-scouting/{z}/{x}/{y}.pbf`

## Variables de entorno (build del frontend)

Ver `.env.example`.

Si cambian variables `REACT_APP_*`, recompila frontend:

```powershell
cd frontend
npm run build
```
