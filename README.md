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

En este repositorio se usa `frontend/.env.production` para el build de produccion.

Valores actuales recomendados:

```env
REACT_APP_TILE_URL=https://api.urbanviable.movilab.es/data
REACT_APP_DATA_STATUS_URL=/api/status
REACT_APP_LAYER_NAME=secciones
REACT_APP_SOURCE_NAME=galicia-scouting
```

Si cambian variables `REACT_APP_*`, recompila frontend:

```powershell
cd frontend
npm run build
```

## Despliegue en Producción (Oracle Cloud ARM A1)

### Pre-requisitos en tu máquina local

1. **Build del frontend compilado (obligatorio)**:
   - El servidor Oracle **no permite npm install/build**, así que el frontend DEBE estar pre-compilado.
   - En tu máquina local, ejecuta:

```powershell
cd frontend
npm install
npm run build
```

   - Esto genera la carpeta `frontend/build/` con archivos estáticos listos.

2. **Artefactos ETL ya generados**:
   - `etl/data/processed/galicia_scouting.mbtiles` (ubicar en `tiles_data/`)
   - `etl/data/processed/last_update.json` (ubicar en `tiles_data/`)

### Transferencia al servidor

Conéctate al servidor Oracle y transfiere los artefactos:

```bash
# Desde tu máquina local
scp -r frontend/build/* usuario@tu-servidor:/home/usuario/urbanviable/frontend/build/
scp -r tiles_data/galicia_scouting.mbtiles usuario@tu-servidor:/home/usuario/urbanviable/tiles_data/
scp -r tiles_data/config.json usuario@tu-servidor:/home/usuario/urbanviable/tiles_data/
scp -r docker-compose.yml usuario@tu-servidor:/home/usuario/urbanviable/
scp -r nginx/ usuario@tu-servidor:/home/usuario/urbanviable/
```

### Configuración en el servidor Oracle

El frontend ya queda parametrizado por `frontend/.env.production` durante el build.

En el servidor, edita `.env` solo para variables de infraestructura:

```bash
ssh usuario@tu-servidor

cd /home/usuario/urbanviable

# Crea/edita .env
cat > .env << 'EOF'
DOMAIN=tu-dominio.com
ENVIRONMENT=production
CORS_ORIGIN=https://tu-dominio.com
EOF
```

### Arrancar servicios en producción

```bash
cd /home/usuario/urbanviable

# Inicia Docker Compose en background
docker compose up -d

# Verifica que los contenedores estén corriendo
docker compose ps
docker compose logs -f
```

### Validar endpoints de producción

```bash
# Verifica que TileServer responde
curl -s http://127.0.0.1:8080/data/galicia-scouting.json | jq . | head -20

# Verifica que Nginx/frontend responden
curl -s https://tu-dominio.com/api/status | jq .

# Verifica que se sirven teselas
curl -s https://tu-dominio.com/tiles/galicia-scouting/14/8192/5460.pbf | wc -c
```

### Reiniciar servicios (si necesario)

```bash
# Detener todo
docker compose down

# Reiniciar todo
docker compose up -d
```

### Actualizaciones futuras

Para actualizar datos o configuración en producción:

1. **Solo teselas/datos ETL cambiaron**:
   ```bash
   scp tiles_data/galicia_scouting.mbtiles usuario@tu-servidor:~/urbanviable/tiles_data/
   docker compose restart urbanviable-tiles
   ```

2. **Frontend cambió**:
   ```bash
   npm run build
   scp -r frontend/build/* usuario@tu-servidor:~/urbanviable/frontend/build/
   docker compose restart urbanviable-web
   ```

3. **Configuración de Nginx cambió**:
   ```bash
   scp -r nginx/conf.d/* usuario@tu-servidor:~/urbanviable/nginx/conf.d/
   docker compose restart urbanviable-web
   ```

## Estado funcional actual (MVP)

- El slider de `Renta` es el unico habilitado en la interfaz de scouting.
- El resto de variables aparecen deshabilitadas hasta disponer de datos consistentes en el tileset de produccion.
- El slider de `Renta` controla la visualizacion de forma progresiva (0% sin capa visible, 100% intensidad completa).
