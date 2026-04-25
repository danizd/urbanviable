# CLAUDE.md — UrbanViable

## Descripción del proyecto
Plataforma web de Location Intelligence para emprendedores, franquicias e inmobiliarias.
Visualiza el atractivo comercial de cada sección censal de Galicia mediante un mapa de
calor dinámico. El usuario ajusta qué variables le importan mediante sliders y el mapa
responde en tiempo real, sin consultar al servidor.

## Principio arquitectónico fundamental
> **"El servidor sirve datos estáticos. La GPU del cliente los interpreta."**

El servidor nunca recibe los pesos del usuario ni calcula ningún score.
Su única función es entregar teselas vectoriales pre-generadas con los datos ya
normalizados. Todo el cálculo de `score = Σ(variable_norm × peso) / Σ(pesos_activos)`
ocurre en la GPU mediante expresiones nativas de MapLibre GL JS.

## Alcance del MVP
- **Zona:** Comunidad Autónoma de Galicia (~3.800 secciones censales).
- **Variables:** 7 variables sociodemográficas y urbanas (ver tabla abajo).
- **Monetización:** Ninguna en fase de validación.
- **Usuarios:** Emprendedores, consultores de localización, equipos de expansión de franquicias.

---

## Stack tecnológico

| Capa | Tecnología | Notas |
|---|---|---|
| ETL | Python 3.11 + Pandas + GeoPandas + pyrosm | Ejecutar en local, no en servidor |
| Generación de teselas | Tippecanoe (CLI Mapbox/Felt) | Produce el archivo `.mbtiles` |
| Servidor de teselas | Docker: `maptiler/tileserver-gl` | Sirve las teselas vía HTTP |
| Frontend | React 18 + MapLibre GL JS 4.x | Renderizado en GPU del cliente |
| Servidor web | Docker: Nginx Alpine | Proxy inverso + archivos estáticos React |
| Infraestructura | Oracle Cloud Free Tier (ARM A1) | Ubuntu 22.04 LTS ARM64 |
| Backend API | **No existe** | Sin base de datos, sin API de cálculo |

---

## Variables del modelo — contrato ETL ↔ Frontend

Nombres exactos de columnas en las teselas vectoriales.
**No cambiar sin actualizar simultáneamente el ETL y el frontend.**

| Columna | Tipo | Fuente | Uso en mapa | Uso en tooltip |
|---|---|---|---|---|
| `cusec` | string (10 dig.) | CNIG secciones censales | — | ID de sección |
| `renta_norm` | float [0,1] | INE Atlas de Renta | ✅ GPU | — |
| `renta_abs` | integer (€) | INE Atlas de Renta | — | ✅ "24.500 €" |
| `densidad_norm` | float [0,1] | Padrón / Secciones CNIG | ✅ GPU | — |
| `jovenes_norm` | float [0,1] | Padrón / Secciones CNIG | ✅ GPU | — |
| `mayores_norm` | float [0,1] | Padrón / Secciones CNIG | ✅ GPU | — |
| `poblacion_abs` | integer (hab.) | Padrón / Secciones CNIG | — | ✅ "3.200 hab." |
| `actividad_norm` | float [0,1] | OpenStreetMap (Geofabrik) | ✅ GPU | — |
| `actividad_abs` | integer | OpenStreetMap (Geofabrik) | — | ✅ "47 establec." |
| `uso_comercial_norm` | float [0,1] | Catastro (Sede Electrónica) | ✅ GPU | — |
| `antiguedad_norm` | float [0,1] | Catastro (Sede Electrónica) | ✅ GPU | — |

> Las columnas `_norm` son el input de la GPU (valores 0–1 para la expresión MapLibre).
> Las columnas `_abs` son para el tooltip informativo al hacer clic en una sección.

---

## Estructura de directorios

```
urbanviable/
├── CLAUDE.md                     ← Este archivo
├── DESIGN_SYSTEM.md              ← Tokens CSS y patrones visuales
├── .env.example
├── .gitignore
├── docker-compose.yml
├── specs/
│   ├── Fuentes_de_datos.md       ← Descripción de las 4 fuentes de datos
│   ├── Especificaciones_etl.md   ← Pipeline completo (process_data.py, Tippecanoe)
│   ├── Especificaciones_frontend.md
│   ├── Arquitectura_y_flujos.md
│   ├── Seguridad_y_configuracion.md
│   └── DevOps_y_despliegue.md
├── etl/
│   ├── process_data.py
│   ├── generate_tiles.sh
│   └── data/
│       ├── secciones_censales/   ← Shapefile CNIG (no versionado)
│       ├── renta.csv             ← INE Atlas de Renta (no versionado)
│       ├── osm/                  ← galicia-260424.osm.pbf (no versionado)
│       ├── catastro/             ← ZIPs por municipio (no versionado)
│       └── processed/            ← GeoJSON + .mbtiles + last_update.json
├── tiles_data/
│   ├── config.json
│   ├── galicia_scouting.mbtiles  ← No versionado (archivo grande)
│   └── last_update.json
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── MapViewer.jsx     ← MapLibre GL JS
│       │   ├── ToolPanel.jsx     ← Sidebar con sliders
│       │   ├── ScoreSlider.jsx   ← Slider individual por variable
│       │   ├── DataStatus.jsx    ← Badge de fecha ETL en header
│       │   └── Tooltip.jsx       ← Panel de detalle de sección
│       ├── pages/
│       │   ├── HomePage.jsx
│       │   ├── ScoutingPage.jsx  ← Página principal de la herramienta
│       │   └── HowToUsePage.jsx
│       ├── hooks/
│       │   └── useMapStyle.js    ← Lógica de expresiones MapLibre (GPU)
│       ├── services/
│       │   └── api.js            ← Solo GET /api/status
│       ├── constants/
│       │   └── variables.js      ← Definición de variables y URLs
│       ├── App.jsx               ← Rutas: / /scouting /como-usar
│       └── App.css               ← Tokens CSS (ver DESIGN_SYSTEM.md)
├── nginx/
│   └── conf.d/
│       └── default.conf
└── certs/
```

---

## Rutas de la aplicación

```jsx
// frontend/src/App.jsx
<Routes>
  <Route path="/"          element={<HomePage />} />
  <Route path="/scouting"  element={<ScoutingPage />} />
  <Route path="/como-usar" element={<HowToUsePage />} />
</Routes>
```

---

## Variables de entorno (`.env`)

```env
# Infraestructura
DOMAIN=tu-dominio.com
ENVIRONMENT=production
CORS_ORIGIN=https://tu-dominio.com

# Frontend (build time — requieren npm run build si cambian)
REACT_APP_TILE_URL=https://tu-dominio.com/tiles
REACT_APP_DATA_STATUS_URL=https://tu-dominio.com/api/status
REACT_APP_LAYER_NAME=secciones
REACT_APP_SOURCE_NAME=galicia-scouting
```

---

## Flujo operativo resumido

```
[ETL — anual, en local]
  python etl/process_data.py       → galicia_scouting.geojson + last_update.json
  bash etl/generate_tiles.sh       → galicia_scouting.mbtiles
  scp *.mbtiles usuario@servidor:~/urbanviable/tiles_data/

[Despliegue — una vez]
  docker compose up -d             → TileServer GL + Nginx

[Usuario — en tiempo real, sin servidor]
  Abre /scouting → MapLibre carga teselas del viewport
  Mueve slider → useMapStyle reconstruye expresión MapLibre
  setPaintProperty → GPU colorea ~3.800 polígonos en <16ms
  Clic en sección → Tooltip con datos absolutos del INE/OSM/Catastro
```
