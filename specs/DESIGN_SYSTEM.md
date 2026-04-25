# Sistema de diseño compartido — GeoViable / UrbanViable

Este documento define el lenguaje visual y de estructura común a ambos proyectos.
**Regla:** Cualquier token, patrón de layout o componente que exista aquí se implementa
de forma idéntica en los dos proyectos. Las diferencias funcionales son bienvenidas;
las diferencias visuales injustificadas no.

---

## 1. Tokens CSS (`App.css` — idéntico en ambos proyectos)

```css
:root {
  /* ── Colores de marca ──────────────────────────── */
  --color-primary:   #1E3A5F;   /* Azul marino oscuro — cabeceras, CTA */
  --color-secondary: #2D8C4E;   /* Verde — botones de acción principal */
  --color-accent:    #E67E22;   /* Naranja — alertas, énfasis, badges */
  --color-blue:      #2563EB;   /* Azul acción — botones secundarios */
  --color-red:       #DC2626;   /* Rojo — errores, riesgo alto */

  /* ── Escala de grises ──────────────────────────── */
  --color-gray-100:  #f3f4f6;
  --color-gray-200:  #e5e7eb;
  --color-gray-500:  #6b7280;
  --color-gray-700:  #374151;
  --color-gray-900:  #111827;

  /* ── Layout ────────────────────────────────────── */
  --sidebar-width:   320px;
  --header-height:   56px;

  /* ── Gradiente hero (home page) ────────────────── */
  --gradient-hero: linear-gradient(135deg, #1E3A5F 0%, #2D8C4E 100%);

  /* ── Sombras ───────────────────────────────────── */
  --shadow-card:   0 2px 8px rgba(0,0,0,0.08);
  --shadow-panel:  0 4px 24px rgba(0,0,0,0.12);

  /* ── Tipografía ────────────────────────────────── */
  --font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
  --font-size-sm:  12px;
  --font-size-md:  14px;
  --font-size-base: 16px;
  --font-size-lg:  20px;
  --font-size-xl:  32px;

  /* ── Bordes ────────────────────────────────────── */
  --radius-sm:   4px;
  --radius-md:   8px;
  --radius-lg:   12px;
  --radius-pill: 999px;

  /* ── Transiciones ──────────────────────────────── */
  --transition-fast:   0.15s ease;
  --transition-normal: 0.25s ease;
}
```

---

## 2. Layout de la página de herramienta principal

Ambos proyectos comparten **exactamente** esta estructura visual:

```
┌────────────────────────────────────────────────────────┐
│  HEADER (56px, fondo --color-primary)                  │
│  [Logo]      [Nav links]          [Indicador estado]   │
├──────────────────┬─────────────────────────────────────┤
│                  │                                      │
│  SIDEBAR         │   MAPA (ocupa todo el espacio        │
│  (320px fijo)    │   restante, 100%)                    │
│                  │                                      │
│  Secciones con   │   Botones flotantes sobre el mapa    │
│  separadores     │   (top-left: controles del mapa)     │
│                  │                                      │
└──────────────────┴─────────────────────────────────────┘
```

**Detalles del header:**
- Fondo: `var(--color-primary)` (#1E3A5F)
- Logo: texto blanco, `font-weight: 700`, izquierda
- Links de navegación: centro (desktop), color blanco semi-opaco
- Indicador de estado: derecha, badge con icono ✅/⚠️

**Detalles del sidebar:**
- Ancho: `var(--sidebar-width)` = 320px
- Fondo: blanco
- Borde derecho: `1px solid var(--color-gray-200)`
- Scroll interno si el contenido desborda
- Secciones separadas por: `<h3>` con `font-size: 11px`, `text-transform: uppercase`,
  `color: var(--color-gray-500)`, `letter-spacing: 0.08em`

---

## 3. Estructura de rutas — patrón compartido

| Ruta | GeoViable | UrbanViable |
|---|---|---|
| `/` | `<HomePage />` | `<HomePage />` |
| `/analisis` | `<AnalysisPage />` (mapa + sidebar herramientas) | — |
| `/scouting` | — | `<ScoutingPage />` (mapa + sidebar sliders) |
| `/report` | `<ReportPage />` | — |
| `/como-usar` | `<HowToUsePage />` | `<HowToUsePage />` |

La página de herramienta principal se llama `/analisis` en GeoViable y `/scouting` en
UrbanViable. El layout es idéntico; el contenido del sidebar y el motor del mapa difieren.

---

## 4. Componentes compartidos por nombre y estructura

| Componente | GeoViable | UrbanViable | Diferencia |
|---|---|---|---|
| `<MapViewer />` | Leaflet + Geoman | MapLibre GL JS | Motor diferente; mismo slot en layout |
| `<ToolPanel />` | Herramientas de análisis | Panel de sliders | Contenido diferente; mismo CSS de sidebar |
| `<LayerStatus />` | Estado de capas ambientales (7 capas) | Estado de datos del INE (fecha ETL) | Mismo patrón badge |
| `<HowToUsePage />` | Guía de uso GeoViable | Guía de uso UrbanViable | Solo texto diferente |
| `<HomePage />` | Hero gradient + CTA | Hero gradient + CTA | Solo copy diferente |

---

## 5. HomePage — patrón exacto

```jsx
// Estructura idéntica en ambos proyectos
<div className="home-container">           {/* gradient-hero, 100vh, flex center */}
  <header className="home-header">
    <span className="home-logo">[Nombre]</span>
    <nav>
      <Link to="/[herramienta]">Herramienta</Link>
      <Link to="/como-usar">¿Cómo usar?</Link>
    </nav>
  </header>
  <main className="home-hero">
    <h1>[Nombre del producto]</h1>
    <p>[Subtítulo — una línea]</p>
    <p>[Descripción — 2-3 líneas]</p>
    <Link to="/[herramienta]" className="btn-cta">
      [Acción principal]
    </Link>
  </main>
</div>
```

**CSS del botón CTA:**
```css
.btn-cta {
  background: white;
  color: var(--color-primary);
  border: none;
  border-radius: var(--radius-pill);
  padding: 14px 32px;
  font-size: var(--font-size-base);
  font-weight: 600;
  cursor: pointer;
  transition: transform var(--transition-fast), box-shadow var(--transition-fast);
}
.btn-cta:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.2);
}
```

---

## 6. Sistema de notificaciones (Toasts)

Mismo patrón visual en ambos proyectos:

```css
.toast { border-radius: var(--radius-md); padding: 12px 16px; font-size: var(--font-size-md); }
.toast-error   { background: #FEF2F2; border-left: 4px solid var(--color-red);    color: #991B1B; }
.toast-success { background: #F0FDF4; border-left: 4px solid var(--color-secondary); color: #166534; }
.toast-warning { background: #FFFBEB; border-left: 4px solid var(--color-accent);  color: #92400E; }
```

---

## 7. Botones flotantes sobre el mapa

```css
.map-floating-controls {
  position: absolute;
  top: 12px;
  left: 12px;           /* GeoViable: top-left. UrbanViable: mismo */
  z-index: 1000;
  display: flex;
  gap: 8px;
}
.map-floating-btn {
  background: white;
  border: 1px solid var(--color-gray-200);
  border-radius: var(--radius-md);
  padding: 8px 14px;
  font-size: var(--font-size-md);
  font-weight: 500;
  cursor: pointer;
  box-shadow: var(--shadow-card);
  transition: background var(--transition-fast);
}
.map-floating-btn:hover { background: var(--color-gray-100); }
.map-floating-btn.active { background: var(--color-primary); color: white; }
```

---

## 8. Responsive — breakpoints idénticos

| Breakpoint | Comportamiento |
|---|---|
| ≥ 1024px | Sidebar lateral fijo (320px) + mapa |
| 768–1023px | Sidebar colapsable superpuesto al mapa |
| < 768px | Sidebar como bottom sheet; mapa 100% pantalla |

---

## 9. Estructura de directorios — patrón compartido

```
[proyecto]/
├── CLAUDE.md
├── .env.example
├── .gitignore
├── docker-compose.yml
├── specs/                        ← Toda la documentación
├── backend/ (solo GeoViable)
├── etl/     (solo UrbanViable)
├── frontend/
│   └── src/
│       ├── components/           ← Componentes UI reutilizables
│       ├── pages/                ← Páginas (rutas)
│       ├── services/             ← Llamadas a API / lógica externa
│       ├── hooks/                ← Custom hooks React
│       ├── utils/                ← Funciones puras
│       ├── constants/            ← Constantes y configuración
│       ├── App.jsx
│       ├── App.css               ← Tokens CSS (este archivo)
│       └── index.js
├── nginx/
│   └── conf.d/
└── certs/
```
