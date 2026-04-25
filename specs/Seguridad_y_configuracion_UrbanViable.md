# UrbanViable — Seguridad y configuración

> **Referencia cruzada:** Este documento es el equivalente a `Seguridad_y_configuracion.md`
> de GeoViable. La estructura es idéntica; las diferencias reflejan la ausencia de
> backend API y base de datos en UrbanViable.

---

## 1. Variables de entorno

Todas las variables configurables se gestionan mediante un archivo `.env` en la raíz
del proyecto (no versionado en Git). A diferencia de GeoViable, no hay secretos de
base de datos ni credenciales de API — la superficie de ataque es significativamente menor.

### Variables de Nginx / infraestructura

| Variable | Descripción | Ejemplo | Requerida |
|---|---|---|---|
| `DOMAIN` | Dominio público del frontend | `urbanviable.movilab.es` | ✅ |
| `ENVIRONMENT` | Entorno de ejecución | `production` \| `development` | ✅ |
| `CORS_ORIGIN` | Origen permitido para las teselas | `https://urbanviable.movilab.es` | ✅ |

### Variables de build del frontend (prefijo `REACT_APP_`)

Estas variables se inyectan en el bundle de React en tiempo de compilación
(`npm run build`). Cambiarlas requiere recompilar el frontend.

| Variable | Descripción | Ejemplo |
|---|---|---|
| `REACT_APP_TILE_URL` | URL base del proxy de teselas (Nginx) | `https://urbanviable.movilab.es/tiles` |
| `REACT_APP_DATA_STATUS_URL` | URL del JSON de estado de datos | `https://urbanviable.movilab.es/api/status` |
| `REACT_APP_LAYER_NAME` | Nombre interno de la capa MapLibre | `secciones` |
| `REACT_APP_SOURCE_NAME` | Nombre del source MapLibre | `galicia-scouting` |

> **Nota:** `REACT_APP_LAYER_NAME` y `REACT_APP_SOURCE_NAME` deben coincidir
> exactamente con los valores usados en Tippecanoe (`--layer`) y en `config.json`
> del TileServer. Si alguno cambia, hay que actualizar los tres puntos.

### Archivo `.env.example` (sin secretos — sí versionar en Git)

```env
# ── Infraestructura ──────────────────────────────────
DOMAIN=tu-dominio.com
ENVIRONMENT=production
CORS_ORIGIN=https://tu-dominio.com

# ── Frontend (build time) ────────────────────────────
REACT_APP_TILE_URL=https://tu-dominio.com/tiles
REACT_APP_DATA_STATUS_URL=https://tu-dominio.com/api/status
REACT_APP_LAYER_NAME=secciones
REACT_APP_SOURCE_NAME=galicia-scouting
```

> **Regla (igual que GeoViable):** `.env` nunca se versiona en Git.
> `.env.example` sí se versiona. Siempre mantener `.env.example` actualizado.

---

## 2. CORS

En UrbanViable, CORS se configura en **Nginx** (no en FastAPI, que no existe).
El TileServer GL no es accesible directamente desde el exterior — todo pasa por Nginx.

```nginx
location /tiles/ {
    proxy_pass http://urbanviable-tiles:8080/data/;

    # Solo el dominio del propio frontend puede consumir las teselas
    add_header 'Access-Control-Allow-Origin' 'https://tu-dominio.com' always;
    add_header 'Access-Control-Allow-Methods' 'GET, OPTIONS' always;
}
```

| Origen permitido | Entorno |
|---|---|
| `https://urbanviable.movilab.es` | Producción |
| `http://localhost:5173` | Desarrollo local (Vite dev server) |
| `http://localhost:3000` | Desarrollo local (Create React App) |

> **Nunca usar `*` en producción.** Si en el futuro se añade autenticación de usuarios,
> un origen amplio permitiría que cualquier web consuma las teselas sin credenciales.

---

## 3. HTTPS / TLS (idéntico a GeoViable)

| Aspecto | Decisión |
|---|---|
| Certificado SSL | Let's Encrypt (gratuito, renovación automática) o Cloudflare proxy |
| Terminación SSL | En Nginx (`urbanviable-web`) |
| HTTP → HTTPS redirect | Sí, automático en Nginx |
| HSTS | Activado (`Strict-Transport-Security: max-age=31536000`) |

---

## 4. Superficie de ataque y mitigaciones

A diferencia de GeoViable, UrbanViable **no acepta ningún input del usuario en el servidor**.
Los pesos de los sliders nunca llegan al servidor — se procesan íntegramente en el cliente.
Esto elimina los vectores de ataque más comunes (SQL injection, GeoJSON malicioso, DoS
por geometrías complejas).

### Vectores de ataque residuales

| Vector | Riesgo | Mitigación |
|---|---|---|
| Scraping masivo de teselas | Bajo-medio | Cache-Control en Nginx; Cloudflare rate limiting opcional |
| Acceso directo al TileServer | Bajo | No expone puertos al host; solo accesible vía Nginx |
| Manipulación del `last_update.json` | Muy bajo | Archivo de solo lectura, montado como `:ro` en Docker |
| Inyección en parámetros de URL de teselas | Muy bajo | Nginx valida el patrón `{z}/{x}/{y}.pbf`; TileServer rechaza rutas inválidas |
| Exposición de datos sensibles | Ninguno | Las teselas solo contienen datos estadísticos públicos del INE |

### Cache de teselas en Nginx

```nginx
# Las teselas no cambian hasta el próximo ETL anual.
# Cache agresivo para reducir carga y mejorar rendimiento.
add_header Cache-Control "public, max-age=86400";  # 24 horas en cliente
```

Para invalidar la caché del cliente tras un nuevo ETL, cambiar la URL de source en
`variables.js` añadiendo un parámetro de versión:
```javascript
// constants/variables.js
export const TILE_URL = `${process.env.REACT_APP_TILE_URL}?v=2026`;
```

---

## 5. Seguridad del proceso ETL

El ETL se ejecuta en la estación de trabajo del desarrollador, no en el servidor.
Los riesgos son diferentes a los de un proceso en servidor:

| Riesgo | Mitigación |
|---|---|
| Descarga de archivos corruptos del INE | Verificar tamaño y estructura antes de procesar |
| `.mbtiles` generado con datos erróneos | Revisar el informe de `process_data.py` (nº polígonos, nulos) antes de subir |
| Subida de un `.mbtiles` a un servidor incorrecto | Usar siempre el mismo alias SSH documentado en el equipo |
| Datos en `raw/` con información personal | Los datos del INE son estadísticos y no contienen datos personales. `raw/` está en `.gitignore` por tamaño, no por privacidad |

---

## 6. Cabeceras de seguridad HTTP (Nginx)

```nginx
# Idénticas a GeoViable
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header X-XSS-Protection "1; mode=block" always;

# Política de recursos — restricción de carga de scripts externos
add_header Content-Security-Policy "
    default-src 'self';
    script-src 'self' 'unsafe-inline';
    style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
    img-src 'self' data: https://*.basemaps.cartocdn.com https://*.openstreetmap.org;
    connect-src 'self' https://tu-dominio.com;
    font-src 'self' https://fonts.gstatic.com;
" always;
```

> **Nota sobre `img-src`:** MapLibre GL JS carga tiles de imagen del mapa base
> (CartoDB Dark Matter). Los dominios de los proveedores de tiles deben estar
> incluidos en la política CSP.

---

## 7. Archivos en `.gitignore`

```gitignore
# Secretos y configuración local
.env
*.pem
*.key
certs/

# Datos ETL (archivos grandes, regenerables)
etl/data/raw/
etl/data/processed/
tiles_data/galicia_scouting.mbtiles

# Build de producción
frontend/build/
frontend/node_modules/

# Python
__pycache__/
*.pyc
.venv/
venv/

# IDE
.vscode/
.idea/

# Docker override local
docker-compose.override.yml
```

---

## 8. Consideraciones de privacidad

Los datos que maneja UrbanViable son **íntegramente estadísticos y públicos**:
- Renta media por sección censal (INE — datos anonimizados por agregación)
- Datos demográficos del Padrón Municipal (INE — datos agregados, no individuales)
- Geometrías de secciones censales (CNIG — datos cartográficos oficiales)

No se recopila ningún dato del usuario: no hay login, no hay cookies de tracking,
no hay logs de qué zonas ha consultado, no hay envío de los pesos de los sliders
al servidor. El `GDPR` y la `LOPDGDD` no aplican en el MVP al no tratarse
datos personales.
