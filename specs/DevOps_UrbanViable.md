# UrbanViable — DevOps y despliegue

## 1. Docker Compose (producción)

```yaml
# docker-compose.yml
version: "3.9"

services:
  # ────────────────────────────────────────────────────
  # Servidor de teselas vectoriales
  # Equivalente a geoviable-db: almacena y sirve los datos
  # ────────────────────────────────────────────────────
  urbanviable-tiles:
    image: maptiler/tileserver-gl:latest
    container_name: urbanviable-tiles
    restart: unless-stopped
    volumes:
      - ./tiles_data:/data        # Contiene galicia_scouting.mbtiles + config.json
    command: --config /data/config.json
    networks:
      - urbanviable-net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    # NO expone puertos al host — solo accesible desde la red interna

  # ────────────────────────────────────────────────────
  # Nginx: proxy inverso + frontend estático
  # Idéntico a geoviable-web en estructura y configuración
  # ────────────────────────────────────────────────────
  urbanviable-web:
    image: nginx:1.25-alpine
    container_name: urbanviable-web
    restart: unless-stopped
    depends_on:
      - urbanviable-tiles
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./frontend/build:/usr/share/nginx/html:ro
      - ./certs:/etc/letsencrypt:ro
      - ./tiles_data/last_update.json:/usr/share/nginx/html/api/status.json:ro
    networks:
      - urbanviable-net

networks:
  urbanviable-net:
    driver: bridge
```

> **Comparación con GeoViable:** La estructura es idéntica salvo que `urbanviable-tiles`
> ocupa el rol de proveedor de datos que en GeoViable ocupan `geoviable-db` + `geoviable-api`.
> `urbanviable-web` (Nginx) es equivalente a `geoviable-web` sin cambios.

---

## 2. Configuración Nginx

### `nginx/conf.d/default.conf`

```nginx
# ──────────────────────────────────────────────────
# Redirect HTTP → HTTPS (idéntico a GeoViable)
# ──────────────────────────────────────────────────
server {
    listen 80;
    server_name tu-dominio.com;
    return 301 https://$host$request_uri;
}

# ──────────────────────────────────────────────────
# HTTPS — servidor principal
# ──────────────────────────────────────────────────
server {
    listen 443 ssl http2;
    server_name tu-dominio.com;   # ← Cambiar en producción

    ssl_certificate     /etc/letsencrypt/live/tu-dominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tu-dominio.com/privkey.pem;

    # Cabeceras de seguridad (idénticas a GeoViable)
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;

    # ── Frontend React (SPA) ─────────────────────
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    # ── Endpoint de estado de datos (JSON estático) ─
    # Equivalente a GET /api/v1/layers/status de GeoViable
    location /api/status {
        alias /usr/share/nginx/html/api/status.json;
        add_header Content-Type application/json;
        add_header Cache-Control "public, max-age=3600";
    }

    # ── Proxy al TileServer GL ───────────────────
    # El frontend hace: GET /tiles/galicia-scouting/{z}/{x}/{y}.pbf
    location /tiles/ {
        proxy_pass http://urbanviable-tiles:8080/data/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # CORS — solo el dominio del propio frontend
        add_header 'Access-Control-Allow-Origin' 'https://tu-dominio.com' always;
        add_header 'Access-Control-Allow-Methods' 'GET, OPTIONS' always;

        # Cache agresivo para teselas (no cambian hasta nueva versión ETL)
        add_header Cache-Control "public, max-age=86400";
    }
}
```

---

## 3. Comandos de despliegue

### Primera vez (setup inicial)

```bash
# 1. Clonar repositorio en el servidor OCI (mismo servidor que GeoViable)
git clone https://github.com/tu-usuario/urbanviable.git
cd urbanviable

# 2. Crear archivo .env desde el ejemplo
cp .env.example .env
nano .env

# 3. Preparar directorio de teselas
mkdir -p tiles_data

# 4. Copiar el .mbtiles generado por el ETL (ejecutado en local)
scp etl/data/processed/galicia_scouting.mbtiles usuario@servidor:~/urbanviable/tiles_data/
scp etl/data/processed/last_update.json usuario@servidor:~/urbanviable/tiles_data/

# 5. Crear config de TileServer
cat > tiles_data/config.json << 'EOF'
{
  "options": { "paths": { "root": "/data", "mbtiles": "/data" } },
  "data": { "galicia-scouting": { "mbtiles": "galicia_scouting.mbtiles" } }
}
EOF

# 6. Compilar el frontend
cd frontend
npm install
npm run build
cd ..

# 7. Levantar los contenedores
docker compose up -d

# 8. Verificar
docker compose ps
docker compose logs -f urbanviable-tiles
```

### Actualización del .mbtiles (nuevo ETL)

```bash
# En local: ejecutar el ETL completo
cd etl/
python download_data.py
python process_data.py
bash generate_tiles.sh

# Subir nuevo .mbtiles al servidor
scp data/processed/galicia_scouting.mbtiles usuario@servidor:~/urbanviable/tiles_data/
scp data/processed/last_update.json usuario@servidor:~/urbanviable/tiles_data/

# TileServer GL recarga el archivo en caliente — no requiere reinicio
# Verificar que el nuevo tileset está disponible:
curl https://tu-dominio.com/tiles/galicia-scouting.json | jq .minzoom
```

### Actualización de código frontend

```bash
# Mismo patrón que GeoViable
git pull origin main
cd frontend && npm run build && cd ..
docker compose restart urbanviable-web
docker compose logs -f urbanviable-web --tail=20
```

### Comandos útiles

```bash
# Ver logs en tiempo real
docker compose logs -f

# Verificar que el TileServer sirve correctamente
curl http://localhost:8080/data/galicia-scouting.json

# Reiniciar solo el tileserver (ej. tras cambiar config.json)
docker compose restart urbanviable-tiles

# Ver tamaño del .mbtiles
du -sh tiles_data/galicia_scouting.mbtiles
```

---

## 4. Variables de entorno (`.env.example`)

```env
# No hay secretos de BD en UrbanViable.
# Solo configuración de dominio y entorno.

# ── Dominio ─────────────────────────────────────
DOMAIN=tu-dominio.com

# ── Entorno ─────────────────────────────────────
ENVIRONMENT=production

# ── Frontend (build time) ────────────────────────
# Estas variables se inyectan en el build de React.
# Cambiarlas requiere npm run build + reiniciar Nginx.
REACT_APP_TILE_URL=https://tu-dominio.com/tiles
REACT_APP_DATA_STATUS_URL=https://tu-dominio.com/api/status
```

> **Nota de seguridad:** A diferencia de GeoViable, no hay contraseñas de BD ni
> secretos de API en este archivo. La seguridad se centra en las cabeceras CORS
> de Nginx y en los certificados SSL.

---

## 5. Monitorización y backups

### Health checks

| Servicio | Endpoint | Frecuencia |
|---|---|---|
| TileServer | `GET http://urbanviable-tiles:8080/health` | 30s (Docker) |
| Nginx | Puerto 443 abierto | — |
| Datos frescos | `GET /api/status` → campo `updated_at` | Manual |

### Backups

No hay base de datos que respaldar. El repositorio Git es la fuente de verdad del código.
Los archivos de datos se regeneran con el ETL.

Opcionalmente, guardar copia del `.mbtiles` en Oracle Object Storage:

```bash
# Backup manual del .mbtiles (opcional, ~15-40 MB)
oci os object put \
  --bucket-name urbanviable-backups \
  --file tiles_data/galicia_scouting.mbtiles \
  --name "galicia_scouting_$(date +%Y%m%d).mbtiles"
```

---

## 6. Estructura de directorios del proyecto completo

```
urbanviable/
├── CLAUDE.md
├── DESIGN_SYSTEM.md              ← Compartido con GeoViable
├── .env.example
├── .gitignore
├── docker-compose.yml
├── specs/
│   ├── Arquitectura_y_flujos.md
│   ├── Especificaciones_etl.md
│   ├── Especificaciones_frontend.md
│   ├── Seguridad_y_configuracion.md
│   └── DevOps_y_despliegue.md
├── etl/                          ← Ejecutar en local, no en Docker
│   ├── download_data.py
│   ├── process_data.py
│   ├── generate_tiles.sh
│   └── data/
│       ├── raw/                  ← .gitignore
│       └── processed/            ← .gitignore
│           ├── galicia_scouting.geojson
│           ├── galicia_scouting.mbtiles
│           └── last_update.json
├── tiles_data/                   ← Montado en contenedor tileserver
│   ├── config.json
│   ├── galicia_scouting.mbtiles  ← .gitignore (archivo grande)
│   └── last_update.json
├── frontend/
│   ├── package.json
│   ├── public/
│   └── src/
│       ├── components/
│       │   ├── MapViewer.jsx
│       │   ├── ToolPanel.jsx
│       │   ├── ScoreSlider.jsx
│       │   ├── DataStatus.jsx
│       │   └── Tooltip.jsx
│       ├── pages/
│       │   ├── HomePage.jsx
│       │   ├── ScoutingPage.jsx
│       │   └── HowToUsePage.jsx
│       ├── hooks/
│       │   └── useMapStyle.js
│       ├── services/
│       │   └── api.js
│       ├── constants/
│       │   └── variables.js
│       ├── App.jsx
│       ├── App.css
│       └── index.js
├── nginx/
│   └── conf.d/
│       └── default.conf
└── certs/                        ← .gitignore
```

### `.gitignore` relevante

```gitignore
# Datos ETL (pueden ser grandes)
etl/data/raw/
etl/data/processed/
tiles_data/galicia_scouting.mbtiles

# Secretos
.env
*.pem
*.key

# Build
frontend/build/
node_modules/

# Python
__pycache__/
*.pyc
.venv/

# IDE
.vscode/
.idea/
```
