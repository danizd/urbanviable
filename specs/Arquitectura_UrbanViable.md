# UrbanViable — Arquitectura del sistema y flujos de datos

## 1. Visión general de la arquitectura

```
┌──────────────────────────────────────────────────────────────┐
│                   SERVIDOR ORACLE CLOUD ARM                  │
│                                                              │
│  ┌──────────────────────┐    ┌──────────────────────────┐    │
│  │  urbanviable-tiles   │    │   urbanviable-web        │    │
│  │  (TileServer GL)     │    │   (Nginx Alpine)         │    │
│  │  Puerto interno:8080 │    │   Puertos: 80, 443       │    │
│  │                      │    │                          │    │
│  │  Sirve .pbf via HTTP │    │  - Archivos estáticos    │    │
│  │  desde .mbtiles      │    │    de React (build/)     │    │
│  │  CORS configurado    │    │  - Proxy /tiles/ →       │    │
│  └──────────────────────┘    │    urbanviable-tiles     │    │
│                              └──────────────────────────┘    │
│         galicia_scouting.mbtiles                             │
│         (volumen compartido Docker)                          │
└──────────────────────────────────────────────────────────────┘
              │                         │
    GET .pbf  │       HTTPS             │ GET /
              │                         │
         ─────┴─────────────────────────┴─────
                        INTERNET
         ─────┬─────────────────────────┬─────
              │                         │
              ▼                         ▼
        Teselas vectoriales       Aplicación React
        (datos norm. crudos)      MapLibre GL JS
              │                         │
              └───────────┬─────────────┘
                          │
                  ┌───────▼────────┐
                  │  GPU CLIENTE   │
                  │                │
                  │  score =       │
                  │  Σ(var×peso)   │
                  │  ÷ Σ(pesos)    │
                  │                │
                  │  → Mapa calor  │
                  └────────────────┘
```

> **Comparación con GeoViable:** GeoViable tiene 3 contenedores (db + api + web).
> UrbanViable tiene 2 (tiles + web) porque no hay cálculo en servidor. El patrón
> de red interna Docker, Nginx como punto de entrada único y la estructura de
> volúmenes es idéntica.

---

## 2. Infraestructura y despliegue

### Servidor (mismo que GeoViable)

| Aspecto | Detalle |
|---|---|
| Proveedor | Oracle Cloud Infrastructure (OCI) — Always Free |
| Arquitectura | ARM (Ampere A1) |
| RAM | 24 GB |
| Almacenamiento | 200 GB (block storage) |
| SO | Ubuntu 22.04 LTS (ARM64) |

### Contenedores Docker

| Contenedor | Imagen base | Puerto interno | Propósito |
|---|---|---|---|
| `urbanviable-tiles` | `maptiler/tileserver-gl:latest` | 8080 | Servidor de teselas vectoriales |
| `urbanviable-web` | `nginx:1.25-alpine` | 80, 443 | Proxy inverso + React estático |

### Red interna Docker (misma convención que GeoViable)

```yaml
networks:
  urbanviable-net:
    driver: bridge
```

- Solo `urbanviable-web` (Nginx) expone puertos al exterior.
- `urbanviable-tiles` **no** expone puertos al host.
- La comunicación interna usa nombres de servicio: `http://urbanviable-tiles:8080`.

### Volúmenes

| Volumen | Montaje | Propósito |
|---|---|---|
| `./tiles_data` | `/data` en tileserver | `.mbtiles` + `config.json` |
| `./nginx/conf.d` | `/etc/nginx/conf.d` | Config Nginx |
| `./frontend/build` | `/usr/share/nginx/html` | Build de producción React |
| `./certs` | `/etc/letsencrypt` | Certificados SSL |

---

## 3. Pipeline ETL (el "back-office")

Este flujo es invisible para el usuario. Se ejecuta manualmente o via cron anual.

```
[1. EXTRACCIÓN]
Python descarga:
  ├── Shapefile secciones censales Galicia  ← CNIG (ZIP, EPSG:25829)
  ├── Atlas de Renta de los Hogares         ← INE (Excel)
  └── Padrón Municipal por sección          ← INE (CSV)

[2. TRANSFORMACIÓN]
GeoPandas/Pandas:
  ├── Filtra Galicia (provincias 15,27,32,36)
  ├── Reproyecta geometrías a WGS84 (EPSG:4326)
  ├── Join por campo CUSEC (10 dígitos)
  ├── Calcula densidad = poblacion / area_km2
  ├── Normalización Min-Max → columnas _norm
  └── Exporta 7 columnas exactas → galicia_scouting.geojson

[3. GENERACIÓN DE TESELAS]
Tippecanoe:
  └── galicia_scouting.geojson → galicia_scouting.mbtiles
      Zoom 6-14, layer "secciones"
      ~15-40 MB resultado final

[4. DESPLIEGUE]
  └── Copiar .mbtiles a ./tiles_data/
      TileServer GL recarga en caliente
```

> **Equivalente GeoViable:** El script `update_layers.py` de GeoViable descarga
> Shapefiles y los carga en PostGIS. El ETL de UrbanViable hace lo mismo pero en
> lugar de volcar a una BD, genera un archivo `.mbtiles` estático.
> Ambos son procesos programados y transparentes al usuario.

---

## 4. Flujo de interacción del usuario

```
Usuario abre /scouting
        │
        ▼
[1] MapLibre solicita solo las teselas visibles en pantalla
    GET /tiles/galicia-scouting/{z}/{x}/{y}.pbf
    → Carga instantánea (lazy, solo el viewport actual)
        │
        ▼
[2] Teselas contienen polígonos con propiedades pre-calculadas:
    { cusec: "1500101001", renta_norm: 0.72, densidad_norm: 0.45,
      jovenes_norm: 0.38, mayores_norm: 0.61,
      renta_abs: 24500, poblacion_abs: 3200 }
        │
        ▼
[3] Mapa inicial: todos los polígonos en gris (pesos = 0)
        │
        ▼
[4] Usuario mueve un slider → React actualiza estado `weights`
        │
        ▼
[5] useMapStyle hook detecta cambio →
    Construye array de expresión MapLibre con literales numéricos →
    map.setPaintProperty('secciones-fill', 'fill-color', expr)
        │
        ▼
[6] GPU recalcula color de ~3.800 polígonos:
    score = Σ(var_norm × peso) / Σ(pesos_activos)  ← siempre [0,1]
    Rojo intenso = score alto, gris = score bajo
    ⚡ < 16ms (60fps), CERO peticiones al servidor
        │
        ▼
[7] Usuario hace clic en polígono →
    MapLibre emite evento 'click' con propiedades del feature →
    React muestra Tooltip:
    "Sección 1503001002 | Renta: 24.500€ | Habitantes: 3.200"
```

---

## 5. Flujo de red en producción (idéntico a GeoViable)

```
Internet → Cloudflare (DNS + proxy) → Oracle Cloud VM :443
  → Nginx (SSL termination + reverse proxy)
    → /tiles/*  → urbanviable-tiles:8080
    → /*        → archivos estáticos React (/usr/share/nginx/html)
```

---

## 6. Configuración TileServer GL

### `tiles_data/config.json`

```json
{
  "options": {
    "paths": {
      "root": "/data",
      "mbtiles": "/data"
    }
  },
  "data": {
    "galicia-scouting": {
      "mbtiles": "galicia_scouting.mbtiles"
    }
  }
}
```

La URL resultante de las teselas sigue el patrón:
`http://urbanviable-tiles:8080/data/galicia-scouting/{z}/{x}/{y}.pbf`

Verificar disponibilidad del tileset (metadata):
`http://urbanviable-tiles:8080/data/galicia-scouting.json`

---

## 7. Actualización de datos

| Aspecto | GeoViable | UrbanViable |
|---|---|---|
| Frecuencia | Mensual (cron job en contenedor) | Anual (datos INE tienen ~1 año de desfase) |
| Ejecución | Dentro del contenedor `geoviable-api` | Fuera de Docker (estación de trabajo dev) |
| Resultado | Registros nuevos en PostGIS | Archivo `galicia_scouting.mbtiles` nuevo |
| Impacto en servicio | Sin cortes (transacción SQL) | Sin cortes (sustituir .mbtiles en caliente) |
| Trazabilidad | Tabla `layer_update_log` en BD | Archivo `etl/data/processed/last_update.json` |

### `last_update.json` (generado por `process_data.py`)

```json
{
  "updated_at": "2026-01-01T03:00:00Z",
  "year_data": 2023,
  "sections_count": 3847,
  "sources": {
    "geometries": "CNIG secciones censales 2023",
    "renta": "INE Atlas de Renta 2021",
    "padron": "INE Padrón Municipal 2023"
  }
}
```

Este archivo se sirve a través de Nginx y el frontend lo consulta para mostrar
el indicador de estado de datos (equivalente a `GET /api/v1/layers/status` en GeoViable).

---

## 8. Rendimiento esperado

| Métrica | Valor esperado |
|---|---|
| Tamaño `.mbtiles` | 15–40 MB |
| Carga inicial del mapa | < 2s (solo teselas del viewport) |
| Tiempo de actualización de color (slider) | < 16ms (60fps, GPU) |
| Peticiones al servidor al mover sliders | **0** (todo en cliente) |
| Teselas en caché del navegador | Automático (HTTP cache-control) |
