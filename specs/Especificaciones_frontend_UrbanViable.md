# UrbanViable — Especificaciones del frontend

## 1. Stack tecnológico

| Paquete | Versión mín. | Propósito | Equivalente GeoViable |
|---|---|---|---|
| `react` | 18.x | Framework UI | ✅ igual |
| `react-dom` | 18.x | Renderizado DOM | ✅ igual |
| `react-router-dom` | 6.x | Navegación SPA | ✅ igual |
| `maplibre-gl` | 4.x | Motor de mapas GPU | Leaflet + React-Leaflet |
| `axios` / `fetch` | — | Llamadas HTTP (solo status) | ✅ igual |

> **Sin dependencias de dibujo ni parseo de archivos:** UrbanViable no necesita
> Leaflet-Geoman, Turf, shpjs, togeojson ni dxf-parser.
> La interacción del usuario son sliders HTML estándar, no geometrías.

---

## 2. Estructura de la interfaz — página de scouting

```
┌────────────────────────────────────────────────────────────────┐
│  HEADER (--header-height: 56px, fondo --color-primary)         │
│  UrbanViable   │  Inicio  ¿Cómo usar?   │  📊 Datos: 01/01/26 │
├────────────────┬───────────────────────────────────────────────┤
│                │                                               │
│  SIDEBAR       │   MAPA A PANTALLA COMPLETA                   │
│  (--sidebar-   │   (MapLibre GL JS, dark mode base)           │
│   width:320px) │                                               │
│                │   Botones flotantes (top-left):               │
│  SCOUTING      │   ┌──────────────┐                           │
│  SCORE         │   │ 🌍 Satélite  │  (no aplica en dark mode) │
│  ─────────     │   └──────────────┘                           │
│                │                                               │
│  VARIABLES     │   Mapa de calor dinámico:                    │
│  ─────────     │   - Gris: zonas sin puntuación               │
│  [Sliders]     │   - Azul→Naranja→Rojo: puntuación creciente  │
│                │                                               │
│  INFORMACIÓN   │                                               │
│  ─────────     │                                               │
│  [Tooltip      │                                               │
│   activo]      │                                               │
│                │                                               │
└────────────────┴───────────────────────────────────────────────┘
```

---

## 3. Páginas

### 3.1 `<HomePage />` — `/`

Estructura **idéntica a GeoViable** (ver `DESIGN_SYSTEM.md`, sección 5).

| Elemento | Contenido UrbanViable |
|---|---|
| Logo/nombre | "UrbanViable" |
| Subtítulo | "Inteligencia de ubicación para Galicia" |
| Descripción | "Descubre las zonas con mayor atractivo comercial. Ajusta qué te importa y el mapa responde en tiempo real." |
| Botón CTA | "Explorar el mapa" → `/scouting` |
| Nav links | "Scouting" + "¿Cómo usar?" |

### 3.2 `<ScoutingPage />` — `/scouting`

Página principal de la herramienta. Layout idéntico a `<AnalysisPage />` de GeoViable:
header + sidebar izquierdo + mapa derecho.

### 3.3 `<HowToUsePage />` — `/como-usar`

Página de texto con instrucciones. Mismo layout de GeoViable (header + contenido centrado).

---

## 4. Componentes

### 4.1 `<MapViewer />` — Motor MapLibre

**Equivalente GeoViable:** `MapViewer.jsx` (Leaflet)
**Diferencia:** MapLibre usa WebGL/GPU; no hay capa de dibujo ni edición de geometrías.

```jsx
// Props
// weights: { renta_norm: 0.5, densidad_norm: 0.3, jovenes_norm: 0, mayores_norm: 0 }
// onFeatureClick: (properties) => void

// Configuración inicial
center: [-7.8, 42.8]   // Centro de Galicia — igual que GeoViable
zoom: 7                 // Vista de toda Galicia
minZoom: 6
maxZoom: 16

// Estilo base oscuro (equivalente al toggle PNOA de GeoViable)
style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
```

**Capas MapLibre añadidas en `map.on('load')`:**

| ID de capa | Tipo | Propósito |
|---|---|---|
| `secciones-fill` | `fill` | Mapa de calor (color dinámico por score) |
| `secciones-outline` | `line` | Bordes sutiles (solo zoom ≥ 9) |

**`source-layer`:** `"secciones"` — debe coincidir **exactamente** con `--layer` de Tippecanoe.

**Eventos:**
- `map.on('click', 'secciones-fill', ...)` → dispara `onFeatureClick` con las propiedades del feature.
- `mouseenter` / `mouseleave` → cambia cursor a `pointer`.

### 4.2 `<ToolPanel />` — Sidebar de control

**Equivalente GeoViable:** `ToolPanel.jsx` (herramientas + formulario + botones)
**Diferencia:** Contiene sliders de pesos en lugar de herramientas de dibujo.

Secciones del sidebar (misma estructura visual que GeoViable):

```
┌─────────────────────────────┐
│  SCOUTING SCORE             │  ← h3 uppercase, color-gray-500
│  Ajusta qué importa         │
│  para tu negocio            │
├─────────────────────────────┤
│  VARIABLES                  │  ← sección
│  [ScoreSlider × 4]          │
├─────────────────────────────┤
│  INFORMACIÓN DE ZONA        │  ← sección (se rellena al hacer clic)
│  [Tooltip.jsx inline]       │
└─────────────────────────────┘
```

### 4.3 `<ScoreSlider />` — Slider individual

**Equivalente GeoViable:** `DrawTools.jsx` (herramienta de interacción principal)
**Diferencia:** Es un `<input type="range">` con metadatos de la variable.

```jsx
// Props
// variable: { key, label, description, absKey, absLabel, absFormat }
// value: number [0, 1]
// onChange: (key, value) => void

// Visual:
// [Label]                    [Porcentaje%]
// [━━━━━━━━━━━━━━━━●───────]  ← input range, accentColor: --color-secondary
// [Descripción breve]
```

**Estados visuales del slider:**
- Valor 0: etiqueta en `--color-gray-500`, trazo gris
- Valor > 0: etiqueta en `--color-gray-900`, trazo `--color-secondary` (verde)
- Hover: tooltip con `variable.description`

### 4.4 `<DataStatus />` — Indicador de datos

**Equivalente GeoViable:** `<LayerStatus />` (estado de 7 capas en BD)
**Diferencia:** Consulta un JSON estático en lugar de un endpoint de API.

```jsx
// Consulta: GET /api/status (→ Nginx sirve last_update.json estático)
// Muestra en header:
// ✅ Datos: 01/01/2026   ← si < 400 días
// ⚠️ Datos: 01/01/2025   ← si > 400 días (amarillo, advertencia)

// Mismo badge visual que GeoViable LayerStatus
```

### 4.5 `<Tooltip />` — Panel de detalle de sección censal

**Equivalente GeoViable:** Tooltip/popup del mapa
**Diferencia:** Aparece en el sidebar (sección "Información de zona") en lugar de
flotante sobre el mapa. Esto preserva el layout limpio del mapa oscuro.

```
┌────────────────────────────────┐
│  SECCIÓN 1503001002     [✕]   │
├────────────────────────────────┤
│  Renta media          24.500€  │
│  Habitantes           3.200    │
│  ─────────────────────────── │
│  Índice renta            0.72  │
│  Índice densidad         0.45  │
│  Índice jóvenes          0.38  │
│  Índice mayores          0.61  │
└────────────────────────────────┘
```

Muestra valores absolutos cuando están disponibles (`renta_abs`, `poblacion_abs`)
e índices normalizados para las demás variables.

---

## 5. Hook de estilos MapLibre — `useMapStyle.js`

**Sin equivalente en GeoViable** (es específico de MapLibre GL JS).

### Concepto crítico
Las expresiones de MapLibre son arrays JSON puros evaluados por la GPU.
**No tienen acceso al scope de JavaScript.** Los valores de los pesos deben ser
literales numéricos embebidos en el array, no referencias a variables.

### Fórmula de scoring
```
score = Σ(variable_norm × peso_i) / Σ(pesos_activos)
```
La división por la suma de pesos activos garantiza que el resultado siempre esté
en `[0, 1]`, independientemente de cuántas variables estén activas o con qué valores.

### Implementación

```javascript
export function useMapStyle(mapRef, weights) {
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const activeEntries = Object.entries(weights).filter(([, v]) => v > 0);
    const totalWeight = activeEntries.reduce((sum, [, v]) => sum + v, 0);

    let fillColorExpression;

    if (totalWeight === 0) {
      // Sin pesos activos: mapa neutro gris
      fillColorExpression = 'rgba(80, 80, 100, 0.2)';
    } else {
      // Construir suma ponderada con literales numéricos
      // Los pesos se normalizan (÷ totalWeight) para que score ∈ [0,1]
      const terms = activeEntries.map(([key, value]) => [
        "*",
        ["get", key],          // Propiedad de la tesela
        value / totalWeight    // ← Literal numérico, no referencia JS
      ]);

      const scoreExpr = terms.length === 1 ? terms[0] : ["+", ...terms];

      fillColorExpression = [
        "interpolate", ["linear"], scoreExpr,
        0,    "rgba(60,  60,  80,  0.15)",   // Sin puntuación: casi invisible
        0.3,  "rgba(30, 120, 180,  0.55)",   // Bajo: azul
        0.6,  "rgba(255,165,  0,   0.75)",   // Medio: naranja (--color-accent)
        1,    "rgba(220, 20,  20,  0.90)"    // Alto: rojo
      ];
    }

    // setPaintProperty reconstruye la capa en la GPU — llamada en cada cambio
    map.setPaintProperty('secciones-fill', 'fill-color', fillColorExpression);

  }, [mapRef, weights]);
}
```

---

## 6. Sistema de diseño — tokens CSS

Archivo `App.css` **idéntico al de GeoViable** (ver `DESIGN_SYSTEM.md`).

Tokens relevantes para UrbanViable específicamente:

```css
/* Rampa de color del mapa de calor — documentada aquí para referencia */
/* score 0.0 → rgba(60,  60,  80,  0.15)  gris oscuro transparente    */
/* score 0.3 → rgba(30, 120, 180,  0.55)  azul (--color-blue)         */
/* score 0.6 → rgba(255,165,   0,  0.75)  naranja (--color-accent)    */
/* score 1.0 → rgba(220,  20,  20,  0.90) rojo (--color-red)          */
```

---

## 7. Gestión de errores

| Escenario | Mensaje | Acción |
|---|---|---|
| TileServer no disponible | "No se pudieron cargar los datos del mapa. Inténtalo de nuevo." | Toast error + reintentar |
| Error CORS en teselas | "Error de configuración del servidor de mapas." | Toast error (contactar admin) |
| `source-layer` no encontrado | Mapa en blanco (silencioso) | Ver checklist de integración |
| `DataStatus` falla | Ocultar badge (no bloquea la app) | Sin notificación |

---

## 8. Checklist de integración frontend ↔ TileServer

Verificar en este orden antes de dar por funcional el frontend:

1. `http://localhost:8080/data/galicia-scouting.json` → devuelve metadata JSON ✅
2. `http://localhost:8080/data/galicia-scouting/7/31/50.pbf` → devuelve bytes ✅
3. DevTools → Network: petición `.pbf` sin error CORS ✅
4. Consola MapLibre: sin warning `source-layer "secciones" not found` ✅
   - Si aparece: el nombre en `--layer` de Tippecanoe no coincide con `source-layer` en `MapViewer.jsx`
5. Al mover un slider: consola sin errores de `setPaintProperty` ✅
   - Si aparece: el mapa aún no ha completado `map.on('load')` cuando se intenta actualizar

---

## 9. Responsive design (igual que GeoViable)

| Breakpoint | Comportamiento |
|---|---|
| ≥ 1024px | Sidebar lateral fijo (320px) + mapa |
| 768–1023px | Sidebar colapsable superpuesto al mapa |
| < 768px | Sidebar como bottom sheet deslizable; mapa 100% pantalla |

---

## 10. Notas de despliegue (igual que GeoViable)

- La UI se sirve desde `frontend/build` en producción.
- Cambios en `frontend/src` requieren `npm run build` para verse en Nginx.
- Si tras recompilar no se actualiza el navegador, reiniciar `urbanviable-web`.
