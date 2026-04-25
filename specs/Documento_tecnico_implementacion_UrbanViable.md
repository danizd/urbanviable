# UrbanViable — Documento técnico de implementación

> Resumen del estado real de la implementación. Equivalente al
> `Documento_tecnico_implementacion.md` de GeoViable. Donde la arquitectura es
> idéntica se indica con ✅. Donde difiere se explica el motivo.

---

## 1. Frontend

### 1.1 Stack y librerías clave

| Librería | Versión | Propósito | vs GeoViable |
|---|---|---|---|
| React | 18.x | Framework UI | ✅ igual |
| React Router DOM | 6.x | Navegación SPA | ✅ igual |
| MapLibre GL JS | 4.x | Motor de mapas WebGL/GPU | Sustituye Leaflet + React-Leaflet |
| — | — | Sin Leaflet-Geoman (no hay dibujo) | GeoViable usa Geoman |
| — | — | Sin Turf, shpjs, togeojson, dxf-parser | GeoViable los usa para parseo de archivos |

### 1.2 Estructura de carpetas

```
frontend/src
│   App.css               ← Tokens CSS idénticos a GeoViable
│   App.jsx               ← Rutas: /, /scouting, /como-usar
│   index.js
│
├── components/
│   ├── MapViewer.jsx     ← MapLibre GL JS (≈ MapViewer de GeoViable)
│   ├── ToolPanel.jsx     ← Sidebar de sliders (≈ ToolPanel de GeoViable)
│   ├── ScoreSlider.jsx   ← Slider individual (equivale a DrawTools)
│   ├── DataStatus.jsx    ← Badge de fecha ETL (≈ LayerStatus)
│   └── Tooltip.jsx       ← Panel de detalle en sidebar
│
├── pages/
│   ├── HomePage.jsx      ← Hero gradient, estructura idéntica a GeoViable
│   ├── ScoutingPage.jsx  ← Página principal (≈ AnalysisPage)
│   └── HowToUsePage.jsx  ← Guía de uso
│
├── hooks/
│   └── useMapStyle.js    ← Sin equivalente en GeoViable (lógica GPU/MapLibre)
│
├── services/
│   └── api.js            ← Solo GET /api/status (vs GeoViable: analyze + report)
│
└── constants/
    └── variables.js      ← URLs, nombres de capas, definición de variables
```

### 1.3 Sistema de navegación y menús

```jsx
// frontend/src/App.jsx
<Routes>
  <Route path="/"          element={<HomePage />} />
  <Route path="/scouting"  element={<ScoutingPage />} />
  <Route path="/como-usar" element={<HowToUsePage />} />
</Routes>
```

- **HomePage** (`/`): hero gradient con CTA "Explorar el mapa" → `/scouting`.
  Nav: "Scouting" + "¿Cómo usar?".
- **ScoutingPage** (`/scouting`): header oscuro con nav central + badge estado datos
  (derecha). Sidebar izquierdo 320px + mapa MapLibre pantalla completa.
- **HowToUsePage** (`/como-usar`): layout de texto centrado, misma estructura que GeoViable.

### 1.4 Componente MapViewer

**Archivo:** `frontend/src/components/MapViewer.jsx`

Funciones principales:
- Inicializa MapLibre GL JS con estilo base dark (CartoDB Dark Matter).
- Añade source vectorial apuntando al TileServer GL vía proxy Nginx.
- Crea capas `secciones-fill` (fill) y `secciones-outline` (line).
- Gestiona evento `click` sobre polígonos → dispara `onFeatureClick`.
- Cambio de cursor (`pointer`) al pasar sobre polígonos.

```jsx
// Parámetros de inicialización
center: [-7.8, 42.8]   // Galicia, mismo que GeoViable
zoom: 7
minZoom: 6
maxZoom: 16

// Source vectorial
type: 'vector'
tiles: [`${REACT_APP_TILE_URL}/galicia-scouting/{z}/{x}/{y}.pbf`]
source-layer: 'secciones'   // ← Debe coincidir con --layer de Tippecanoe
```

**Diferencia clave vs GeoViable:** No hay capa de dibujo (Geoman), no hay toggle de
satélite (el mapa base es siempre dark), no hay pintado de intersecciones (la GPU colorea
todo el mapa en base a scores, no a geometrías específicas devueltas por la API).

### 1.5 Panel de control (ToolPanel + ScoreSlider)

**Archivo:** `frontend/src/components/ToolPanel.jsx`

Secciones del sidebar (misma estructura visual que GeoViable):

| Sección | Contenido | Equivalente GeoViable |
|---|---|---|
| SCOUTING SCORE | Título + descripción breve | Sección "Dibujo del polígono" |
| VARIABLES | 4× `<ScoreSlider />` | Sección herramientas |
| INFORMACIÓN DE ZONA | `<Tooltip />` (inline) | Popup flotante del mapa |

**ScoreSlider:** `<input type="range" min=0 max=1 step=0.01>` con label, porcentaje
y descripción. `accentColor: var(--color-secondary)`. Sin estado global — cada slider
actualiza la clave correspondiente en el objeto `weights` del estado de `ScoutingPage`.

### 1.6 Hook useMapStyle — el motor de scoring

**Archivo:** `frontend/src/hooks/useMapStyle.js`

**Sin equivalente en GeoViable.** Es el componente más crítico de UrbanViable.

Lógica:
1. Recibe `weights` (objeto con los 4 valores de slider, 0–1 cada uno).
2. Filtra las entradas con peso > 0 (variables activas).
3. Divide cada peso por la suma total → normalización para que score ∈ [0,1].
4. Construye un array de expresión MapLibre con los valores numéricos **literales**:
   `["*", ["get", "renta_norm"], 0.42]`
5. Llama a `map.setPaintProperty('secciones-fill', 'fill-color', expr)`.
6. La GPU recalcula el color de ~3.800 polígonos en < 16ms.

```javascript
// Ejemplo de expresión generada cuando weights = { renta_norm: 0.6, jovenes_norm: 0.4 }
[
  "interpolate", ["linear"],
  ["+",
    ["*", ["get", "renta_norm"],  0.6],   // literales numéricos
    ["*", ["get", "jovenes_norm"], 0.4]
  ],
  0,    "rgba(60,  60,  80,  0.15)",
  0.3,  "rgba(30, 120, 180,  0.55)",
  0.6,  "rgba(255,165,   0,  0.75)",
  1,    "rgba(220,  20,  20,  0.90)"
]
```

**Error común a evitar:** Pasar `weights.renta` como referencia JavaScript dentro del
array JSON de MapLibre. La GPU no tiene acceso al scope JS. Los valores **deben ser
literales** en el array. Por eso el hook reconstruye el array completo en cada render.

### 1.7 Sistema de diseño

**Archivo:** `frontend/src/App.css`

Tokens CSS **idénticos** a GeoViable. Ver `DESIGN_SYSTEM.md`.
La única adición específica de UrbanViable es la documentación de la rampa de color
del mapa de calor dentro del CSS como comentario de referencia.

---

## 2. ETL (proceso de datos)

> Equivalente al backend de actualización de capas de GeoViable (`update_layers.py`).
> Se ejecuta en local, no en el servidor.

### 2.1 Estructura de carpetas

```
etl/
├── download_data.py       ← Descarga fuentes INE/CNIG
├── process_data.py        ← Limpieza, join, normalización → GeoJSON
├── generate_tiles.sh      ← Wrapper de Tippecanoe → .mbtiles
└── data/
    ├── raw/               ← Archivos originales (.zip, .xlsx, .csv)
    └── processed/
        ├── galicia_scouting.geojson
        ├── galicia_scouting.mbtiles
        └── last_update.json
```

### 2.2 Flujo del ETL

| Paso | Script | Input | Output |
|---|---|---|---|
| 1 | `download_data.py` | URLs manuales | `data/raw/` |
| 2 | `process_data.py` | `data/raw/` | `galicia_scouting.geojson` + `last_update.json` |
| 3 | `generate_tiles.sh` | `.geojson` | `galicia_scouting.mbtiles` |
| 4 | Manual (scp) | `.mbtiles` | Servidor → `tiles_data/` |

### 2.3 Parámetros críticos de Tippecanoe

```bash
tippecanoe \
  --layer="secciones" \          # ⚠️ Nombre de capa — debe coincidir con source-layer
  --minimum-zoom=6 \
  --maximum-zoom=14 \
  --coalesce-densest-as-needed \ # Correcto para polígonos (NO --drop-densest-as-needed)
  --include="cusec" \            # Solo las 7 columnas necesarias
  --include="renta_norm" \
  --include="densidad_norm" \
  --include="jovenes_norm" \
  --include="mayores_norm" \
  --include="renta_abs" \
  --include="poblacion_abs" \
  --output="galicia_scouting.mbtiles" \
  galicia_scouting.geojson
```

---

## 3. Docker Compose y contenedores

**Archivo:** `docker-compose.yml`

Servicios:
- `urbanviable-tiles`: TileServer GL, volumen `./tiles_data`, healthcheck HTTP.
  Sin puertos expuestos al host.
- `urbanviable-web`: Nginx Alpine, puertos `80:80` y `443:443`, sirve `frontend/build`
  y proxya `/tiles/` al tileserver.

> GeoViable tiene 3 contenedores (db + api + web). UrbanViable tiene 2 (tiles + web)
> porque no hay cálculo en servidor. La convención de nombres, la red interna y la
> estructura de volúmenes es idéntica.

### Puertos
- Frontend (Nginx): `443` (producción) / `80` (redirección)
- TileServer: sin puerto público — solo accesible desde red interna Docker

---

## 4. Flujo funcional end-to-end

```
[ETL — anual, en local]
  download_data.py → process_data.py → generate_tiles.sh
  → galicia_scouting.mbtiles + last_update.json
  → scp al servidor → tiles_data/

[Usuario — tiempo real, sin servidor]
  Abre /scouting
  → MapLibre carga teselas del viewport (lazy)
  → Mueve slider → useMapStyle reconstruye expresión
  → setPaintProperty → GPU colorea polígonos en <16ms
  → Clic en polígono → Tooltip con datos absolutos
```

---

## 5. Notas operativas

- El frontend se sirve desde `frontend/build`. Cambios en `src/` requieren
  `npm run build` + reiniciar `urbanviable-web`.
- Actualizar el `.mbtiles` no requiere reiniciar el TileServer — recarga en caliente.
- Si el mapa aparece en blanco (sin polígonos), verificar que `source-layer: "secciones"`
  en `MapViewer.jsx` coincide exactamente con `--layer="secciones"` en `generate_tiles.sh`.
- Si los sliders no colorean el mapa, verificar que `map.isStyleLoaded()` es `true`
  en el momento en que `useMapStyle` llama a `setPaintProperty`. Usar el evento
  `map.on('load', ...)` como guardia.
- Las URLs del INE cambian con cada publicación anual. Actualizar `download_data.py`
  antes de cada ejecución del ETL revisando manualmente los portales del INE y CNIG.
