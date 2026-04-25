# UrbanViable — Especificaciones del ETL y generación de teselas

El ETL es el único proceso que escribe datos en este proyecto. Se ejecuta en local
(no en el servidor), produce un único archivo `galicia_scouting.mbtiles` y se sube
manualmente al servidor. No existe backend API; el servidor solo sirve ese archivo.

---

## 1. Estructura de carpetas del ETL

```
etl/
├── download_data.py        ← Descarga fuentes (ejecutar manualmente)
├── process_data.py         ← Pipeline completo → GeoJSON
├── generate_tiles.sh       ← Tippecanoe → .mbtiles
└── data/
    ├── secciones_censales/ ← Shapefile CNIG (ZIP + SHP descomprimido)
    ├── renta.csv           ← Atlas de Renta INE (CSV largo)
    ├── osm/
    │   └── galicia-260424.osm.pbf
    ├── catastro/
    │   ├── a_coruña/       ← ZIPs por municipio
    │   ├── lugo/
    │   ├── ourense/
    │   └── pontevedra/
    └── processed/
        ├── galicia_scouting.geojson
        ├── galicia_scouting.mbtiles
        └── last_update.json
```

---

## 2. Dependencias Python

```txt
# requirements-etl.txt
geopandas>=0.14
pandas>=2.0
pyrosm>=0.6
pyproj>=3.6
shapely>=2.0
openpyxl>=3.1      # por si el Atlas de Renta viene en .xlsx
requests>=2.31
```

```bash
pip install -r requirements-etl.txt
```

Tippecanoe (CLI, no Python):
```bash
# Ubuntu/Debian
sudo apt-get install tippecanoe

# macOS
brew install tippecanoe
```

---

## 3. Script `process_data.py` — Pipeline completo

```python
"""
UrbanViable — Pipeline ETL completo.

Entradas:
  etl/data/secciones_censales/  → geometrías CNIG
  etl/data/renta.csv            → Atlas de Renta INE (formato largo)
  etl/data/osm/galicia-260424.osm.pbf
  etl/data/catastro/[provincia]/

Salidas:
  etl/data/processed/galicia_scouting.geojson
  etl/data/processed/last_update.json
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import zipfile, os, re, json
from datetime import datetime, timezone

DATA_DIR      = "etl/data"
PROCESSED_DIR = "etl/data/processed"
os.makedirs(PROCESSED_DIR, exist_ok=True)

GALICIA_PROVINCIAS = ['15', '27', '32', '36']

# ── Normalización Min-Max ──────────────────────────────────────────────────────
def minmax_norm(series: pd.Series) -> pd.Series:
    """
    Normalización Min-Max sobre Galicia completa.
    Mínimo de Galicia → 0.0, máximo de Galicia → 1.0.
    Los NaN se tratan como 0 antes de llamar a esta función.
    """
    vmin, vmax = series.min(), series.max()
    if vmax == vmin:
        return pd.Series(0.0, index=series.index)
    return ((series - vmin) / (vmax - vmin)).round(4)


# ══════════════════════════════════════════════════════════════════════════════
# PASO 1 — Cargar y preparar geometrías base
# ══════════════════════════════════════════════════════════════════════════════
print("\n[1/5] Cargando secciones censales...")

SEC_DIR = f"{DATA_DIR}/secciones_censales"

# Descomprimir ZIP si aún no se ha hecho
zip_files = [f for f in os.listdir(SEC_DIR) if f.endswith('.zip')]
if zip_files and not os.path.exists(f"{SEC_DIR}/shp"):
    with zipfile.ZipFile(f"{SEC_DIR}/{zip_files[0]}", 'r') as z:
        z.extractall(f"{SEC_DIR}/shp/")

gdf = gpd.read_file(f"{SEC_DIR}/shp/")

# Inspección — confirmar campos disponibles
print(f"  Campos del Shapefile: {gdf.columns.tolist()}")
print(f"  CRS original: {gdf.crs}")

# Filtrar Galicia
gdf = gdf[gdf['CUSEC'].str[:2].isin(GALICIA_PROVINCIAS)].copy()
gdf['cusec'] = gdf['CUSEC'].str.zfill(10)

# Calcular área en km² en proyección métrica (antes de reproyectar a WGS84)
gdf_metr    = gdf.to_crs(epsg=25830)
gdf['area_km2'] = gdf_metr.geometry.area / 1_000_000

# Reproyectar a WGS84 para Tippecanoe
gdf = gdf.to_crs(epsg=4326)
print(f"  Secciones de Galicia: {len(gdf)}")

# Padrón demográfico — intentar extraer del propio Shapefile
# Si el Shapefile incluye campos de población, usarlos directamente.
# Inspeccionar gdf.columns para confirmar nombres exactos.
CAMPO_POBLACION = 'NPOB'   # ← AJUSTAR según el Shapefile real
CAMPO_JOVENES   = None     # ← Rellenar si el Shapefile los incluye
CAMPO_MAYORES   = None

if CAMPO_POBLACION in gdf.columns:
    gdf['poblacion_abs'] = pd.to_numeric(gdf[CAMPO_POBLACION], errors='coerce').fillna(0).astype(int)
    gdf['densidad']      = gdf['poblacion_abs'] / gdf['area_km2'].clip(lower=0.01)
    print(f"  Población total extraída del Shapefile.")
else:
    print(f"  ⚠️  Campo de población no encontrado. Rellenar con 0.")
    gdf['poblacion_abs'] = 0
    gdf['densidad']      = 0.0

# % jóvenes y mayores — pueden venir del Shapefile o necesitar Padrón separado
gdf['pct_jovenes'] = 0.0
gdf['pct_mayores'] = 0.0


# ══════════════════════════════════════════════════════════════════════════════
# PASO 2 — Atlas de Renta (CSV formato largo del INE)
# ══════════════════════════════════════════════════════════════════════════════
print("\n[2/5] Procesando Atlas de Renta...")

df_renta_raw = pd.read_csv(
    f"{DATA_DIR}/renta.csv",
    sep=';',
    encoding='latin-1',
    thousands='.',
    decimal=','
)

# Inspección obligatoria en la primera ejecución
print(f"  Columnas CSV renta: {df_renta_raw.columns.tolist()}")
print(f"  Primeras filas:\n{df_renta_raw.head(3)}")
print(f"  Indicadores disponibles: {df_renta_raw.iloc[:, 1].unique()[:5]}")

# Filtrar indicador de renta por hogar y año más reciente
# AJUSTAR el texto exacto del indicador según el CSV descargado
INDICADOR_RENTA = 'Renta neta media por hogar'
col_lugar     = df_renta_raw.columns[0]
col_indicador = df_renta_raw.columns[1]
col_periodo   = df_renta_raw.columns[2]
col_valor     = df_renta_raw.columns[3]

df_renta = df_renta_raw[
    df_renta_raw[col_indicador] == INDICADOR_RENTA
].copy()

año_renta = df_renta[col_periodo].max()
df_renta  = df_renta[df_renta[col_periodo] == año_renta].copy()
print(f"  Año de referencia de renta: {año_renta}")

def parse_cusec_ine(texto):
    """
    Construye CUSEC de 10 dígitos desde el campo de texto del INE.
    Formato esperado: "15001 - A Coruña  Sección:001 01"
    AJUSTAR si el formato del CSV descargado es diferente.
    """
    texto = str(texto)
    municipio = texto[:5].strip()
    match = re.search(r'Sección:(\d{3})\s+(\d{2})', texto)
    if match:
        return f"{municipio}{match.group(1)}{match.group(2)}"
    return None

df_renta['cusec'] = df_renta[col_lugar].apply(parse_cusec_ine)
df_renta = df_renta.dropna(subset=['cusec'])

df_renta['renta_abs'] = (
    pd.to_numeric(
        df_renta[col_valor].astype(str)
        .str.replace('.', '', regex=False)
        .str.replace(',', '.', regex=False)
        .str.replace('..', '0', regex=False),
        errors='coerce'
    ).fillna(0).astype(int)
)

df_renta = df_renta[['cusec', 'renta_abs']].drop_duplicates('cusec')
print(f"  Secciones con dato de renta: {len(df_renta)}")

# Join con geometrías
gdf = gdf.merge(df_renta, on='cusec', how='left')
gdf['renta_abs'] = gdf['renta_abs'].fillna(0).astype(int)
print(f"  Secciones sin dato de renta: {(gdf['renta_abs'] == 0).sum()}")


# ══════════════════════════════════════════════════════════════════════════════
# PASO 3 — Actividad económica (OSM)
# ══════════════════════════════════════════════════════════════════════════════
print("\n[3/5] Procesando datos OSM...")

OSM_FILE = f"{DATA_DIR}/osm/galicia-260424.osm.pbf"

if os.path.exists(OSM_FILE):
    import pyrosm

    osm = pyrosm.OSM(OSM_FILE)

    TAGS_COMERCIALES = {
        'shop': True,
        'amenity': [
            'restaurant', 'cafe', 'bar', 'fast_food',
            'bank', 'pharmacy', 'clinic', 'school',
            'supermarket', 'marketplace'
        ],
        'office': True,
    }

    pois = osm.get_pois(custom_filter=TAGS_COMERCIALES)
    pois = pois[pois.geometry.geom_type == 'Point'].copy()
    print(f"  POIs comerciales: {len(pois)}")

    pois_proj      = pois.to_crs(epsg=25830)
    secciones_proj = gdf.to_crs(epsg=25830)

    join_osm = gpd.sjoin(
        pois_proj[['geometry']],
        secciones_proj[['cusec', 'area_km2', 'geometry']],
        how='left', predicate='within'
    )

    actividad = (
        join_osm.groupby('cusec')
        .size()
        .reset_index(name='actividad_abs')
    )

    gdf = gdf.merge(actividad, on='cusec', how='left')
    gdf['actividad_abs'] = gdf['actividad_abs'].fillna(0).astype(int)
    gdf['densidad_actividad'] = gdf['actividad_abs'] / gdf['area_km2'].clip(lower=0.01)
    print(f"  Secciones con actividad > 0: {(gdf['actividad_abs'] > 0).sum()}")
else:
    print(f"  ⚠️  Archivo OSM no encontrado. actividad_abs = 0.")
    gdf['actividad_abs']     = 0
    gdf['densidad_actividad'] = 0.0


# ══════════════════════════════════════════════════════════════════════════════
# PASO 4 — Catastro
# ══════════════════════════════════════════════════════════════════════════════
print("\n[4/5] Procesando datos del Catastro...")

CATASTRO_DIR = f"{DATA_DIR}/catastro"
resultados_cat = []

USOS_COMERCIALES = ['5_retail', '4_office', '3_industrial', '6_publicServices']

if os.path.exists(CATASTRO_DIR):
    for provincia in os.listdir(CATASTRO_DIR):
        prov_path = os.path.join(CATASTRO_DIR, provincia)
        if not os.path.isdir(prov_path):
            continue
        for zip_file in os.listdir(prov_path):
            if not zip_file.endswith('.zip'):
                continue
            try:
                gdf_edif = gpd.read_file(
                    f"zip://{os.path.join(prov_path, zip_file)}",
                    layer='building'    # AJUSTAR nombre de capa si es diferente
                ).to_crs(epsg=25830)
                resultados_cat.append(gdf_edif[['geometry', 'currentUse', 'beginning']])
            except Exception as e:
                pass  # Archivo sin capa building, ignorar

    if resultados_cat:
        edificios = gpd.GeoDataFrame(
            pd.concat(resultados_cat, ignore_index=True),
            geometry='geometry', crs='EPSG:25830'
        )
        print(f"  Edificios cargados: {len(edificios)}")

        secciones_proj = gdf.to_crs(epsg=25830)
        join_cat = gpd.sjoin(
            edificios,
            secciones_proj[['cusec', 'geometry']],
            how='left', predicate='within'
        )

        catastro_agg = (
            join_cat.groupby('cusec')
            .apply(lambda x: pd.Series({
                'n_edificios':   len(x),
                'n_comerciales': x['currentUse'].isin(USOS_COMERCIALES).sum(),
                'año_medio':     pd.to_numeric(
                    x['beginning'].str[:4], errors='coerce'
                ).mean()
            }))
            .reset_index()
        )
        catastro_agg['ratio_comercial'] = (
            catastro_agg['n_comerciales'] / catastro_agg['n_edificios'].clip(lower=1)
        )
        # Modernidad: año más reciente → valor más alto
        catastro_agg['modernidad'] = 2025 - catastro_agg['año_medio'].fillna(1970)

        gdf = gdf.merge(
            catastro_agg[['cusec', 'ratio_comercial', 'modernidad']],
            on='cusec', how='left'
        )
        gdf['ratio_comercial'] = gdf['ratio_comercial'].fillna(0.0)
        gdf['modernidad']      = gdf['modernidad'].fillna(gdf['modernidad'].median())
    else:
        print("  ⚠️  No se procesaron ZIPs del catastro. Variables = 0.")
        gdf['ratio_comercial'] = 0.0
        gdf['modernidad']      = 0.0
else:
    print(f"  ⚠️  Directorio catastro no encontrado. Variables = 0.")
    gdf['ratio_comercial'] = 0.0
    gdf['modernidad']      = 0.0


# ══════════════════════════════════════════════════════════════════════════════
# PASO 5 — Normalización y exportación
# ══════════════════════════════════════════════════════════════════════════════
print("\n[5/5] Normalizando y exportando...")

# Normalizar todas las variables a [0,1] Min-Max sobre Galicia
gdf['renta_norm']        = minmax_norm(gdf['renta_abs'].fillna(0))
gdf['densidad_norm']     = minmax_norm(gdf['densidad'].fillna(0))
gdf['jovenes_norm']      = minmax_norm(gdf['pct_jovenes'].fillna(0))
gdf['mayores_norm']      = minmax_norm(gdf['pct_mayores'].fillna(0))
gdf['actividad_norm']    = minmax_norm(gdf['densidad_actividad'].fillna(0))
gdf['uso_comercial_norm']= minmax_norm(gdf['ratio_comercial'].fillna(0))
gdf['antiguedad_norm']   = minmax_norm(gdf['modernidad'].fillna(0))

# Seleccionar exactamente las 11 columnas del contrato ETL↔Frontend
# Ver Fuentes_de_datos.md para la definición completa de cada columna
COLS_OUTPUT = [
    'cusec',
    'renta_norm', 'renta_abs',
    'densidad_norm',
    'jovenes_norm',
    'mayores_norm',
    'poblacion_abs',
    'actividad_norm', 'actividad_abs',
    'uso_comercial_norm',
    'antiguedad_norm',
    'geometry'
]

gdf_output = gdf[COLS_OUTPUT].copy()

# Verificación de calidad
print("\n  Verificación de calidad:")
assert len(gdf_output) > 3500, f"Pocas secciones: {len(gdf_output)}"
assert gdf_output['cusec'].nunique() == len(gdf_output), "CUSECs duplicados"

COLS_NORM = [c for c in COLS_OUTPUT if c.endswith('_norm')]
for col in COLS_NORM:
    assert gdf_output[col].between(0, 1).all(), f"{col} fuera de [0,1]"
    pct_cero = (gdf_output[col] == 0).mean() * 100
    flag = "⚠️ " if pct_cero > 20 else "  "
    print(f"  {flag}{col:25s}: {pct_cero:5.1f}% secciones en 0")

# Exportar GeoJSON
geojson_path = f"{PROCESSED_DIR}/galicia_scouting.geojson"
gdf_output.to_file(geojson_path, driver='GeoJSON')
print(f"\n  ✓ GeoJSON: {geojson_path}")
print(f"    Polígonos: {len(gdf_output)}")
print(f"    Tamaño: {os.path.getsize(geojson_path)/1024/1024:.1f} MB")

# Exportar metadatos para el badge de estado del frontend
last_update = {
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "sections_count": len(gdf_output),
    "sources": {
        "geometries": "CNIG secciones censales",
        "renta": f"INE Atlas de Renta (año {año_renta if 'año_renta' in dir() else 'desconocido'})",
        "osm": "OpenStreetMap Galicia (Geofabrik)",
        "catastro": "Sede Electrónica del Catastro"
    },
    "variables": COLS_NORM
}
with open(f"{PROCESSED_DIR}/last_update.json", 'w') as f:
    json.dump(last_update, f, indent=2, ensure_ascii=False)

print(f"  ✓ Metadatos: {PROCESSED_DIR}/last_update.json")
```

---

## 4. Script `generate_tiles.sh` — Tippecanoe

```bash
#!/bin/bash
# Genera galicia_scouting.mbtiles desde el GeoJSON procesado.
# Requiere Tippecanoe instalado: https://github.com/felt/tippecanoe

INPUT="etl/data/processed/galicia_scouting.geojson"
OUTPUT="etl/data/processed/galicia_scouting.mbtiles"

# Nombre de la capa vectorial — DEBE coincidir con:
#   - source-layer en MapViewer.jsx
#   - REACT_APP_LAYER_NAME en .env
LAYER_NAME="secciones"

if [ ! -f "$INPUT" ]; then
  echo "ERROR: $INPUT no encontrado. Ejecuta process_data.py primero."
  exit 1
fi

rm -f "$OUTPUT"

tippecanoe \
  --output="$OUTPUT" \
  --layer="$LAYER_NAME" \
  --minimum-zoom=6 \
  --maximum-zoom=14 \
  --coalesce-densest-as-needed \
  --extend-zooms-if-still-dropping \
  --simplification=2 \
  --include="cusec" \
  --include="renta_norm" \
  --include="renta_abs" \
  --include="densidad_norm" \
  --include="jovenes_norm" \
  --include="mayores_norm" \
  --include="poblacion_abs" \
  --include="actividad_norm" \
  --include="actividad_abs" \
  --include="uso_comercial_norm" \
  --include="antiguedad_norm" \
  "$INPUT"

if [ $? -eq 0 ]; then
  SIZE=$(du -sh "$OUTPUT" | cut -f1)
  echo "✓ Teselas generadas: $OUTPUT ($SIZE)"
else
  echo "✗ Error en Tippecanoe."
  exit 1
fi
```

### Justificación de parámetros de Tippecanoe

| Parámetro | Valor | Justificación |
|---|---|---|
| `--layer` | `"secciones"` | **Crítico.** Nombre interno de la capa que referencia el frontend. |
| `--minimum-zoom` | `6` | Vista de Galicia completa. |
| `--maximum-zoom` | `14` | Detalle de calle. Más zoom no aporta info nueva. |
| `--coalesce-densest-as-needed` | — | Correcto para **polígonos**. (`--drop-densest-as-needed` es para puntos, no usar.) |
| `--extend-zooms-if-still-dropping` | — | Extiende zoom máximo si los polígonos siguen siendo grandes. |
| `--simplification` | `2` | Simplificación geométrica leve para reducir tamaño. |
| `--include` | lista explícita | Solo las 11 columnas del contrato. Excluye columnas intermedias del ETL, reduciendo el tamaño de las teselas hasta un 60%. |

---

## 5. Flujo de despliegue tras el ETL

```bash
# 1. Ejecutar el ETL completo
python etl/process_data.py
bash etl/generate_tiles.sh

# 2. Verificar el resultado antes de subir
du -sh etl/data/processed/galicia_scouting.mbtiles
# Esperado: 15–40 MB

# 3. Subir al servidor
scp etl/data/processed/galicia_scouting.mbtiles  usuario@servidor:~/urbanviable/tiles_data/
scp etl/data/processed/last_update.json          usuario@servidor:~/urbanviable/tiles_data/

# TileServer GL recarga el archivo en caliente — no requiere reinicio del contenedor.
# Verificar disponibilidad:
curl https://tu-dominio.com/tiles/galicia-scouting.json | python3 -m json.tool
```
