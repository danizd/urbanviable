# UrbanViable

Plataforma de scouting comercial para Galicia con cálculo de score en GPU (cliente).

## Quick Start

```powershell
start.bat
```

Esto ejecuta el ETL si es necesario y levanta el entorno de desarrollo.

## Desarrollo local

### Requisitos

- Python 3.11+ con geopandas, pandas, shapely, osmium
- Node.js 18+
- Docker (opcional, solo para tileserver)

### ETL - Generar datos

```powershell
python etl/process_data.py
```

Salida: `etl/data/processed/galicia_scouting.geojson`

### Frontend

```powershell
cd frontend
npm install
npm run start
```

El frontend sirve en `http://localhost:5173` y carga el GeoJSON directamente desde `public/`.

## Sliders disponibles

| Variable | Fuente | Descripción |
|----------|--------|-------------|
| **renta_norm** | INE/renta.csv | Renta neta media por hogar |
| **jovenes_norm** | IGE/poblacion_ige.csv | % población menor de 20 años |
| **mayores_norm** | IGE/poblacion_ige.csv | % población mayor de 64 años |
| **actividad_norm** | OSM (osmium) | Densidad de POIs (escala logarítmica) |
| **uso_comercial_norm** | Catastro/CONSTRU | Ratio edificios comerciales/industriales |
| **antiguedad_norm** | Catastro/CONSTRU | Antigüedad media de edificios |

## Arquitectura

- **Sin backend API** - el cálculo de score se ejecuta en GPU mediante expresiones MapLibre GL JS
- Los nombres de columnas en las teselas son el contrato entre ETL y frontend
- Variables con prefijo `_norm` están normalizadas 0-1 para la GPU, `_abs` son valores para mostrar
- El frontend carga GeoJSON directamente (no requiere MBTiles)

## Interfaz

- **Panel lateral**: Sliders para ajustar pesos de cada variable
- **Mapa**: Colores cambian dinámicamente según el score calculado
- **Click en zona**: Muestra popup con municipio, código de sección, renta y actividad
- **Tooltip**: Información completa de la zona seleccionada

## Despliegue con Docker

```powershell
docker compose up -d
```

Servicios:
- tileserver-gl en puerto 8080
- nginx (frontend) en puerto 3002

## Producción

El frontend se construye con `npm run build` y los archivos estáticos se sirven via nginx/Docker.