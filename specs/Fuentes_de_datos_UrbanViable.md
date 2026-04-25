# UrbanViable — Fuentes de datos

Descripción técnica de todas las fuentes de datos del ETL: ubicación en disco,
formato, estructura de columnas, lógica de procesamiento y variables que aportan
al modelo final.

---

## Resumen de fuentes

| # | Fuente | Organismo | Ubicación local | Formato | Variables generadas |
|---|---|---|---|---|---|
| 1 | Secciones censales | CNIG / INE | `etl/data/secciones_censales/` | Shapefile (.zip) | Geometría + CUSEC |
| 2 | Atlas de Renta | INE | `etl/data/renta.csv` | CSV largo | `renta_norm`, `renta_abs` |
| 3 | OpenStreetMap Galicia | Geofabrik / OSM | `etl/data/osm/galicia-260424.osm.pbf` | PBF binario | `actividad_norm`, `actividad_abs` |
| 4 | Catastro vectorial | Sede Catastro | `etl/data/catastro/[provincia]/` | ZIP con Shapefile | `uso_comercial_norm`, `antiguedad_norm` |

Las fuentes 1 y 2 son las del MVP mínimo viable. Las fuentes 3 y 4 enriquecen el
modelo con variables de actividad económica y tejido urbano, y se procesan en una
segunda fase del ETL.

---

## 1. Secciones censales — CNIG / INE

**URL:** https://www.ine.es/dyngs/DAB/index.htm?cid=1389
**Ubicación local:** `etl/data/secciones_censales/`
**Formato:** Shapefile comprimido en ZIP

### Propósito
Base geométrica del proyecto. Define las ~3.800 unidades territoriales (CUSEC) de
Galicia sobre las que se cruzan todos los demás datos. Es la única fuente con
geometría de polígono — el resto son tablas de atributos que se unen a esta base.

### Sistema de referencia
- **CRS original:** ETRS89 — EPSG:25829 (zona 29N, Galicia occidental) o EPSG:25830
- **CRS de salida:** WGS84 — EPSG:4326 (requerido por Tippecanoe y MapLibre)
- La reproyección se hace con GeoPandas: `gdf.to_crs(epsg=4326)`

### Campo clave
| Campo | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `CUSEC` | string (10 dígitos) | Código único de sección censal | `1500101001` |

Estructura del CUSEC: `CCPP`(2) + `MMM`(3, municipio) + `DDD`(3, distrito) + `SS`(2, sección)

Provincias de Galicia: `15` (A Coruña), `27` (Lugo), `32` (Ourense), `36` (Pontevedra).

### Carga en ETL
```python
import geopandas as gpd
import zipfile

# Descomprimir si es necesario
with zipfile.ZipFile("etl/data/secciones_censales/secciones.zip", 'r') as z:
    z.extractall("etl/data/secciones_censales/shp/")

gdf = gpd.read_file("etl/data/secciones_censales/shp/")

# Filtrar Galicia
GALICIA = ['15', '27', '32', '36']
gdf = gdf[gdf['CUSEC'].str[:2].isin(GALICIA)].copy()
gdf['cusec'] = gdf['CUSEC'].str.zfill(10)

# Calcular área en km² ANTES de reproyectar (ETRS89 está en metros)
gdf_proj = gdf.to_crs(epsg=25830)
gdf['area_km2'] = gdf_proj.geometry.area / 1_000_000

# Reproyectar a WGS84 para el output final
gdf = gdf.to_crs(epsg=4326)

print(f"Secciones censales de Galicia: {len(gdf)}")
```

---

## 2. Atlas de Renta de los Hogares — INE

**URL:** https://www.ine.es/dynt3/inebase/index.htm?padre=12385&capsel=12384
**Ubicación local:** `etl/data/renta.csv`
**Formato:** CSV en formato largo (orientado a análisis estadístico)

### Estructura del CSV (formato largo del INE)
El archivo **no es una tabla directa** cusec → renta. Cada fila representa una
combinación de sección censal, indicador y año:

```
Municipios y secciones censales;Indicadores de renta media y mediana;Periodo;Total
15001 - A Coruña  Sección:001 01;Renta neta media por hogar;2021;32150
15001 - A Coruña  Sección:001 01;Renta neta media por persona;2021;13200
15001 - A Coruña  Sección:001 01;Renta neta media por hogar;2020;31800
...
```

### ⚠️ Problemas conocidos del formato

**1. El CUSEC no viene como campo directo.** Hay que construirlo parseando el
campo de texto de municipio+sección:
```python
# El campo suele tener formato: "15001 - A Coruña  Sección:001 01"
# municipio = primeros 5 caracteres = "15001"
# distrito  = en "Sección:001" → "001"
# sección   = últimos 2 dígitos = "01"
# CUSEC final = "15001" + "001" + "01" = "1500100101"
```

Inspeccionar el CSV descargado para confirmar el separador exacto (`;` o `,`),
el nombre literal de las columnas y el formato del campo de localización
antes de ejecutar el ETL. El INE cambia este formato entre versiones anuales.

**2. Múltiples indicadores y años.** Filtrar siempre por:
- Indicador: `"Renta neta media por hogar"` (confirmar texto exacto en el CSV)
- Periodo: el año más reciente disponible

**3. Secciones sin dato.** El INE suprime datos de secciones con menos de 100 hogares.
Aparecen como `"."` o vacías. Se tratan como `NaN` y se rellenan con `0` antes de normalizar.

### Lógica de procesamiento
```python
import pandas as pd
import re

df = pd.read_csv(
    "etl/data/renta.csv",
    sep=';',               # Verificar separador real
    encoding='latin-1',    # Los CSVs del INE suelen usar latin-1
    thousands='.',
    decimal=','
)

# Inspección inicial obligatoria antes de continuar
print(df.columns.tolist())
print(df.iloc[:5])
print(df.iloc[:, 1].unique())  # Ver indicadores disponibles

# Filtrar indicador y año más reciente
df_renta = df[
    df.iloc[:, 1] == 'Renta neta media por hogar'
].copy()
año_max = df_renta.iloc[:, 2].max()
df_renta = df_renta[df_renta.iloc[:, 2] == año_max].copy()

# Construir CUSEC desde el campo de texto
def parse_cusec(texto):
    """
    Extrae el CUSEC de 10 dígitos del campo de texto del INE.
    AJUSTAR según el formato real del CSV descargado.
    """
    municipio = str(texto)[:5].strip()
    match = re.search(r'Sección:(\d{3})\s+(\d{2})', str(texto))
    if match:
        return f"{municipio}{match.group(1)}{match.group(2)}"
    return None

df_renta['cusec'] = df_renta.iloc[:, 0].apply(parse_cusec)
df_renta = df_renta.dropna(subset=['cusec'])

# Limpiar valor numérico
df_renta['renta_abs'] = (
    pd.to_numeric(
        df_renta.iloc[:, 3].astype(str)
        .str.replace('.', '', regex=False)
        .str.replace(',', '.', regex=False),
        errors='coerce'
    ).fillna(0).astype(int)
)

df_renta = df_renta[['cusec', 'renta_abs']].copy()
print(f"Secciones con dato de renta: {len(df_renta)} (año: {año_max})")
```

### Variables generadas
| Columna en tesela | Tipo | Descripción |
|---|---|---|
| `renta_abs` | integer | Renta neta media por hogar en euros |
| `renta_norm` | float [0,1] | Normalizado Min-Max sobre Galicia |

---

## 3. Actividad económica — OpenStreetMap Galicia

**URL:** https://download.geofabrik.de/europe/spain/galicia.html
**Ubicación local:** `etl/data/osm/galicia-260424.osm.pbf`
**Formato:** OSM Protocol Buffer Format (binario comprimido)

### Propósito
Proporciona la distribución geográfica de la actividad económica: tiendas, restaurantes,
servicios, oficinas, industria. Permite calcular dos métricas por sección censal:
- **Densidad de actividad:** número de negocios por km² (proxy de vitalidad comercial)
- **Nº de establecimientos:** valor absoluto para el tooltip

### Librería de procesamiento: `pyrosm`
```bash
pip install pyrosm
```

### Etiquetas OSM de interés (establecimientos comerciales)
```python
TAGS_COMERCIALES = {
    'shop': True,
    'amenity': [
        'restaurant', 'cafe', 'bar', 'fast_food',
        'bank', 'pharmacy', 'clinic', 'school',
        'supermarket', 'marketplace'
    ],
    'office': True,
    'leisure': ['fitness_centre', 'sports_centre'],
}
```

### Lógica de procesamiento
```python
import pyrosm
import geopandas as gpd

osm = pyrosm.OSM("etl/data/osm/galicia-260424.osm.pbf")

# Extraer puntos de interés comerciales
pois = osm.get_pois(custom_filter=TAGS_COMERCIALES)
pois = pois[pois.geometry.type == 'Point'].copy()
print(f"POIs comerciales extraídos: {len(pois)}")

# Spatial join: asignar cada POI a su sección censal
pois_proj      = pois.to_crs(epsg=25830)
secciones_proj = gdf.to_crs(epsg=25830)

join = gpd.sjoin(
    pois_proj,
    secciones_proj[['cusec', 'area_km2', 'geometry']],
    how='left', predicate='within'
)

# Agregar por sección
actividad = (
    join.groupby('cusec')
    .agg(actividad_abs=('index_right', 'count'))
    .reset_index()
)

# Merge con todas las secciones (incluir las que no tienen actividad)
actividad = secciones_proj[['cusec', 'area_km2']].merge(
    actividad, on='cusec', how='left'
).fillna(0)

actividad['densidad_actividad'] = (
    actividad['actividad_abs'] / actividad['area_km2'].clip(lower=0.01)
)

print(f"Secciones con actividad > 0: {(actividad['actividad_abs'] > 0).sum()}")
```

### Variables generadas
| Columna en tesela | Tipo | Descripción |
|---|---|---|
| `actividad_abs` | integer | Número de establecimientos en la sección |
| `actividad_norm` | float [0,1] | Densidad de negocios/km² normalizada |

---

## 4. Catastro vectorial — Sede Electrónica del Catastro

**URL:** https://www.sedecatastro.gob.es/DescargaDatos/SECFormularioDescargas.aspx
**Ubicación local:** `etl/data/catastro/[provincia]/`
**Formato:** ZIP por municipio, con múltiples capas Shapefile dentro

### Propósito
Caracteriza el **tejido urbano** de cada sección censal: qué proporción del parque
edificatorio tiene uso comercial y cuál es la antigüedad media de los edificios.

### Estructura de los ZIPs del catastro
Cada ZIP de municipio contiene varias capas. Las relevantes son:

| Capa | Contenido | Campos de interés |
|---|---|---|
| `building` | Edificios (geometría) | `currentUse`, `geometry` |
| `buildingpart` | Partes de edificio | `numberOfFloorsAboveGround`, `beginning` |

El campo `currentUse` del catastro sigue esta codificación:
`1_residential`, `2_agriculture`, `3_industrial`, `4_office`, `5_retail`, `6_publicServices`

### ⚠️ Volumen de datos
Galicia tiene ~300 municipios. Procesar todos los ZIPs puede llevar varias horas.
Estrategia recomendada:
- **Validación:** procesar primero los 20 municipios más poblados.
- **Producción:** bucle sobre todos los ZIPs del directorio.

### Lógica de procesamiento
```python
import os
import geopandas as gpd
import pandas as pd

CATASTRO_DIR = "etl/data/catastro/"
resultados = []

for provincia in os.listdir(CATASTRO_DIR):
    prov_dir = os.path.join(CATASTRO_DIR, provincia)
    if not os.path.isdir(prov_dir):
        continue

    for zip_file in os.listdir(prov_dir):
        if not zip_file.endswith('.zip'):
            continue
        zip_path = os.path.join(prov_dir, zip_file)
        try:
            # Inspeccionar el ZIP para confirmar el nombre exacto de la capa
            gdf_edif = gpd.read_file(f"zip://{zip_path}", layer='building')
            gdf_edif = gdf_edif.to_crs(epsg=25830)
            resultados.append(gdf_edif[['geometry', 'currentUse', 'beginning']])
        except Exception as e:
            print(f"⚠️  Error en {zip_file}: {e}")
            continue

edificios = pd.concat(resultados, ignore_index=True)
edificios = gpd.GeoDataFrame(edificios, geometry='geometry', crs='EPSG:25830')

# Spatial join con secciones censales
secciones_proj = gdf.to_crs(epsg=25830)
join = gpd.sjoin(edificios, secciones_proj[['cusec', 'geometry']],
                 how='left', predicate='within')

# Agregar por sección
USOS_COMERCIALES = ['5_retail', '4_office', '3_industrial']

catastro_agg = (
    join.groupby('cusec')
    .apply(lambda x: pd.Series({
        'n_edificios':    len(x),
        'n_comerciales':  x['currentUse'].isin(USOS_COMERCIALES).sum(),
        'año_medio':      pd.to_numeric(
                              x['beginning'].str[:4], errors='coerce'
                          ).mean()
    }))
    .reset_index()
)

catastro_agg['ratio_comercial'] = (
    catastro_agg['n_comerciales'] / catastro_agg['n_edificios'].clip(lower=1)
)
# Antigüedad invertida: más reciente → valor más alto (más atractivo)
catastro_agg['modernidad'] = 2025 - catastro_agg['año_medio'].fillna(1970)
```

### Variables generadas
| Columna en tesela | Tipo | Descripción |
|---|---|---|
| `uso_comercial_norm` | float [0,1] | % edificios con uso comercial/oficina normalizado |
| `antiguedad_norm` | float [0,1] | Modernidad del parque edificatorio normalizada |

> **Nota sobre `antiguedad_norm`:** Se normaliza la modernidad (año más reciente → 1.0),
> no la antigüedad. Una zona con edificios nuevos obtiene puntuación alta.
> Ajustar la interpretación en `HowToUsePage` si es necesario.

---

## 5. Variables del modelo final

Columnas exactas que deben existir en `galicia_scouting.mbtiles`.
**Este es el contrato entre el ETL y el frontend.**

| Columna | Tipo | Fuente | Para GPU | Para tooltip |
|---|---|---|---|---|
| `cusec` | string | Secciones censales | — | ✅ ID de sección |
| `renta_norm` | float [0,1] | Atlas de Renta | ✅ | — |
| `renta_abs` | integer | Atlas de Renta | — | ✅ euros |
| `densidad_norm` | float [0,1] | Padrón / Secciones | ✅ | — |
| `jovenes_norm` | float [0,1] | Padrón / Secciones | ✅ | — |
| `mayores_norm` | float [0,1] | Padrón / Secciones | ✅ | — |
| `poblacion_abs` | integer | Padrón / Secciones | — | ✅ habitantes |
| `actividad_norm` | float [0,1] | OSM | ✅ | — |
| `actividad_abs` | integer | OSM | — | ✅ establecimientos |
| `uso_comercial_norm` | float [0,1] | Catastro | ✅ | — |
| `antiguedad_norm` | float [0,1] | Catastro | ✅ | — |

**MVP mínimo (solo fuentes 1+2):** Las columnas de OSM y Catastro se rellenan
con `0.0`. Sus sliders en el frontend aparecerán con valor cero pero funcionales
para cuando se añadan los datos.

---

## 6. Padrón Municipal

Los datos de población (densidad, % jóvenes, % mayores) se obtienen de una de
estas dos formas, en orden de preferencia:

**Opción A (verificar primero):** El shapefile de secciones censales del CNIG ya
incluye atributos demográficos básicos en sus campos. Ejecutar `print(gdf.columns.tolist())`
al cargarlo para ver qué campos demográficos están disponibles.

**Opción B:** Descarga separada.
- **URL:** https://www.ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736177012
- **Formato:** CSV con estructura similar al Atlas de Renta (formato largo, mismas
  precauciones sobre nombres de columnas y construcción del CUSEC)

---

## 7. Licencias y atribuciones

| Fuente | Licencia | Texto de atribución |
|---|---|---|
| CNIG / INE — Secciones censales | CC BY 4.0 | "Fuente: IGN / INE" |
| INE — Atlas de Renta | Reutilización libre (Ley 37/2007) | "Fuente: INE" |
| OpenStreetMap | ODbL 1.0 | "© OpenStreetMap contributors" |
| Catastro | Reutilización libre (RD 663/2007) | "Fuente: Sede Electrónica del Catastro" |

Incluir todas las atribuciones en el footer de la aplicación y en `HowToUsePage`.

---

## 8. Verificación de calidad post-ETL

```python
# Ejecutar al final de process_data.py antes de generar las teselas
assert len(gdf_output) > 3500, f"Pocas secciones: {len(gdf_output)}"
assert gdf_output['cusec'].nunique() == len(gdf_output), "CUSECs duplicados"

COLS_NORM = [
    'renta_norm', 'densidad_norm', 'jovenes_norm', 'mayores_norm',
    'actividad_norm', 'uso_comercial_norm', 'antiguedad_norm'
]
for col in COLS_NORM:
    assert gdf_output[col].between(0, 1).all(), f"{col} fuera de [0,1]"
    pct_cero = (gdf_output[col] == 0).mean() * 100
    print(f"{col:25s}: {pct_cero:5.1f}% secciones en 0")
    if pct_cero > 20:
        print(f"  ⚠️  Revisar fuente de {col}")
```
