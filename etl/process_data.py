"""UrbanViable - Pipeline ETL.

Entradas esperadas:
- etl/data/secciones_censales/*.shp
- etl/data/renta.csv
- etl/data/galicia-260424.osm.pbf (opcional)
- etl/data/catastro/**/*.zip (opcional)

Salidas:
- etl/data/processed/galicia_scouting.geojson
- etl/data/processed/last_update.json
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import geopandas as gpd
import numpy as np
import pandas as pd

try:
    import osmium
except ImportError:
    osmium = None

DATA_DIR = Path("etl/data")
PROCESSED_DIR = DATA_DIR / "processed"
SECTIONS_DIR = DATA_DIR / "secciones_censales"
RENTA_FILE = DATA_DIR / "renta.csv"
POBLACION_IGE_FILE = DATA_DIR / "poblacion_ige.csv"
OSM_FILE = DATA_DIR / "galicia-260424.osm.pbf"
CATASTRO_DIR = DATA_DIR / "catastro"

GALICIA_PROVINCIAS = {"15", "27", "32", "36"}


def minmax_norm(series: pd.Series) -> pd.Series:
    values = series.fillna(0)
    vmin = values.min()
    vmax = values.max()
    if vmax == vmin:
        return pd.Series(0.0, index=values.index)
    return ((values - vmin) / (vmax - vmin)).round(4)

def log_norm(series: pd.Series) -> pd.Series:
    values = series.fillna(0).clip(lower=0)
    log_vals = np.log1p(values)
    return minmax_norm(log_vals)


def load_sections() -> gpd.GeoDataFrame:
    shapefiles = sorted(SECTIONS_DIR.glob("*.shp"))
    if not shapefiles:
        raise FileNotFoundError("No se encontro shapefile en etl/data/secciones_censales")

    gdf = gpd.read_file(shapefiles[0])
    if "CUSEC" not in gdf.columns:
        raise KeyError("El shapefile no contiene el campo CUSEC")

    # Normalizar CUSEC a 10 dígitos
    gdf["CUSEC"] = gdf["CUSEC"].astype(str).str.zfill(10)
    # Filtrar solo Galicia (provincias 15, 27, 32, 36)
    gdf = gdf[gdf["CUSEC"].str[:2].isin(GALICIA_PROVINCIAS)].copy()
    gdf["cusec"] = gdf["CUSEC"]

    # Calcular área en km²
    projected = gdf.to_crs(epsg=25830)
    gdf["area_km2"] = projected.geometry.area / 1_000_000
    gdf = gdf.to_crs(epsg=4326)

    # Buscar campo de población — puede venir como string con separadores
    pop_candidates = ["NPOB", "POB_TOT", "POBLACION", "TOTAL", "POB", "POPULATION", "pop"]
    pop_col = None
    for c in pop_candidates:
        if c in gdf.columns:
            pop_col = c
            break
    
    if pop_col:
        # Limpiar valores: quitar puntos de miles y convertir a int
        raw = gdf[pop_col].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        gdf["poblacion_abs"] = pd.to_numeric(raw, errors="coerce").fillna(0).astype(int)
    else:
        print("  [!] No se encontro columna de poblacion en shapefile. Usando 0.")
        gdf["poblacion_abs"] = 0

    gdf["densidad"] = gdf["poblacion_abs"] / gdf["area_km2"].clip(lower=0.01)

    # Juventud/vejez — no disponible en shapefile base, se deja 0
    gdf["pct_jovenes"] = 0.0
    gdf["pct_mayores"] = 0.0

    return gdf


def parse_cusec_ine(text: str) -> Optional[str]:
    """
    Extrae el CUSEC de 10 dígitos de los campos del INE.
    Formatos soportados:
      - "0100101001 Abegondo sección 01001" -> "0100101001"
      - "0100101001" (solo número)
    """
    if pd.isna(text):
        return None
    s = str(text).strip()
    # Extraer los primeros 10 dígitos consecutivos
    import re
    match = re.match(r'(\d{10})', s)
    if match:
        return match.group(1)
    return None


def process_renta(gdf: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, str]:
    if not RENTA_FILE.exists():
        gdf["renta_abs"] = 0
        return gdf, "desconocido"

    # Usar utf-8-sig para manejar BOM automáticamente
    try:
        df = pd.read_csv(RENTA_FILE, sep=";", encoding="utf-8-sig", dtype=str, low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(RENTA_FILE, sep=";", encoding="latin-1", dtype=str, low_memory=False)

    if df.shape[1] < 4:
        gdf["renta_abs"] = 0
        return gdf, "desconocido"

    # Limpiar nombres de columnas
    df.columns = df.columns.str.strip()
    # Quitar BOM si existe en la primera columna
    df.columns = df.columns.str.replace(r'ï»¿', '', regex=True)

    # El CSV del INE tiene esta estructura:
    # Col 0: Municipios (código + nombre, solo a nivel municipio)
    # Col 1: Distritos (código + nombre, a nivel distrito)
    # Col 2: Secciones (código + nombre, a nivel sección censal) ← Aquí está el CUSEC
    # Col 3: Indicadores de renta media ← Aquí está el nombre del indicador
    # Col 4: Periodo (año)
    # Col 5: Total (valor)
    
    col_seccion = df.columns[2]   # "Secciones"
    col_indicador = df.columns[3] # "Indicadores de renta media"
    col_periodo = df.columns[4]   # "Periodo"
    col_valor = df.columns[5]     # "Total"

    # Extraer CUSEC de la columna "Secciones" (formato: "0100101001 Alegría-Dulantzi sección 01001")
    def extract_cusec(val):
        if pd.isna(val):
            return None
        s = str(val).strip()
        # El CUSEC son los primeros 10 dígitos
        import re
        match = re.match(r'(\d{10})', s)
        return match.group(1) if match else None

    df["cusec"] = df[col_seccion].apply(extract_cusec)
    df = df.dropna(subset=["cusec"])

    if df.empty:
        print("  [!] No se encontraron CUSECs válidos en renta.csv")
        gdf["renta_abs"] = 0
        return gdf, "desconocido"

    # Buscar indicador de renta neta por hogar (o por persona como fallback)
    # Prioridad: 1) "Renta neta media por hogar", 2) "Renta neta media por persona"
    indicators_priority = [
        "Renta neta media por hogar",
        "Renta neta media por persona"
    ]
    df_renta = None
    for priority_indicator in indicators_priority:
        mask = df[col_indicador].str.contains(priority_indicator, case=False, na=False)
        if mask.any():
            df_renta = df[mask].copy()
            print(f"  [OK] Usando indicador: '{priority_indicator}'")
            break

    if df_renta is None or df_renta.empty:
        print(f"  [!] No se encontró indicador de renta. Valores disponibles en '{col_indicador}':")
        print(df[col_indicador].dropna().unique()[:10])
        gdf["renta_abs"] = 0
        return gdf, "desconocido"

    # Seleccionar el año más reciente
    year_series = pd.to_numeric(df_renta[col_periodo], errors="coerce")
    if year_series.dropna().empty:
        gdf["renta_abs"] = 0
        return gdf, "desconocido"

    max_year = int(year_series.max())
    df_renta = df_renta[year_series == max_year].copy()

    # Limpiar valores de renta (formato español: "12.345,67" → 12345.67)
    def clean_renta(val):
        s = str(val).strip()
        if s in ['', 'nan', 'NaN']:
            return 0.0
        # Quitar puntos de miles y cambiar coma decimal por punto
        s = s.replace(".", "").replace(",", ".")
        try:
            return float(s)
        except:
            return 0.0

    df_renta["renta_abs"] = df_renta[col_valor].apply(clean_renta)

    # Agrupar por CUSEC (por si hay múltiples filas, tomar la primera)
    renta = df_renta[["cusec", "renta_abs"]].drop_duplicates("cusec", keep="first")

    merged = gdf.merge(renta, on="cusec", how="left")
    merged["renta_abs"] = merged["renta_abs"].fillna(0).astype(int)

    return merged, str(max_year) if max_year is not None else "desconocido"


def process_poblacion_ige(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf["pct_jovenes"] = 0.0
    gdf["pct_mayores"] = 0.0

    if not POBLACION_IGE_FILE.exists():
        print("  [!] Archivo de poblacion IGE no encontrado.")
        return gdf

    try:
        df = pd.read_csv(POBLACION_IGE_FILE, encoding="latin-1", low_memory=False)
    except Exception as e:
        print(f"  [!] Error al leer poblacion IGE: {e}")
        return gdf

    col_ambito = df.columns[2]
    col_indicador = df.columns[3]
    col_valor = df.columns[4]

    def is_cusec_10(val):
        s = str(val).strip()
        return s.isdigit() and len(s) == 10

    df_cusec = df[df[col_ambito].apply(is_cusec_10)].copy()

    if df_cusec.empty:
        print("  [!] No se encontraron CUSEC de 10 digitos en poblacion IGE")
        return gdf

    indicadores = {
        "jovenes": "menor de 20 anos",
        "mayores": "maior de 64 anos",
    }

    for key, search in indicadores.items():
        mask = df_cusec[col_indicador].str.contains(search, case=False, na=False)
        if not mask.any():
            print(f"  [!] Indicador de {key} no encontrado en IGE")
            continue

        temp = df_cusec[mask][[col_ambito, col_valor]].copy()
        temp = temp.rename(columns={col_ambito: "cusec"})
        temp["valor"] = pd.to_numeric(temp[col_valor].astype(str).str.replace(",", ".", regex=False), errors="coerce")
        temp = temp[["cusec", "valor"]].drop_duplicates("cusec")

        gdf = gdf.merge(temp, on="cusec", how="left")
        gdf[f"pct_{key}"] = gdf["valor"].fillna(0.0)
        gdf = gdf.drop(columns=["valor"])

    n_jovenes = len(gdf[gdf["pct_jovenes"] > 0])
    n_mayores = len(gdf[gdf["pct_mayores"] > 0])
    print(f"  [OK] Poblacion IGE: {n_jovenes} secciones con datos de jovenes")
    print(f"  [OK] Poblacion IGE: {n_mayores} secciones con datos de mayores")

    return gdf

    try:
        df = pd.read_csv(POBLACION_IGE_FILE, encoding="latin-1", low_memory=False)
    except Exception as e:
        print(f"  [!] Error al leer población IGE: {e}. jovenes/mayores = 0")
        gdf["pct_jovenes"] = 0.0
        gdf["pct_mayores"] = 0.0
        return gdf

    col_ambito = df.columns[2]
    col_indicador = df.columns[3]
    col_valor = df.columns[4]

    def is_cusec_10(val):
        s = str(val).strip()
        return s.isdigit() and len(s) == 10

    df_cusec = df[df[col_ambito].apply(is_cusec_10)].copy()

    if df_cusec.empty:
        print("  [!] No se encontraron CUSEC de 10 dígitos en población IGE")
        gdf["pct_jovenes"] = 0.0
        gdf["pct_mayores"] = 0.0
        return gdf

    indicadores = {
        "jovenes": "menor de 20 anos",
        "mayores": "maior de 64 anos",
    }

    result = {}
    for key, search in indicadores.items():
        mask = df_cusec[col_indicador].str.contains(search, case=False, na=False)
        if not mask.any():
            print(f"  [!] Indicador de {key} no encontrado en IGE")
            result[key] = None
            continue
        temp = df_cusec[mask][[col_ambito, col_valor]].copy()
        temp[col_ambito] = temp[col_ambito].astype(str)
        temp[col_valor] = pd.to_numeric(temp[col_valor].astype(str).str.replace(",", ".", regex=False), errors="coerce")
        temp = temp.rename(columns={col_ambito: "cusec", col_valor: f"pct_{key}"})
        result[key] = temp[["cusec", f"pct_{key}"]].drop_duplicates("cusec")

    if result.get("jovenes") is not None:
        gdf = gdf.merge(result["jovenes"], on="cusec", how="left")
        gdf["pct_jovenes"] = gdf["pct_jovenes"].fillna(0.0)
    else:
        gdf["pct_jovenes"] = 0.0

    if result.get("mayores") is not None:
        gdf = gdf.merge(result["mayores"], on="cusec", how="left")
        gdf["pct_mayores"] = gdf["pct_mayores"].fillna(0.0)
    else:
        gdf["pct_mayores"] = 0.0

    print(f"  [OK] Población IGE: {len(gdf[gdf['pct_jovenes'] > 0])} secciones con datos de jóvenes")
    print(f"  [OK] Población IGE: {len(gdf[gdf['pct_mayores'] > 0])} secciones con datos de mayores")

    return gdf


def process_osm(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    try:
        import osmium
    except ImportError:
        gdf["actividad_abs"] = 0
        gdf["densidad_actividad"] = 0.0
        return gdf
    
    if not OSM_FILE.exists():
        print("  [!] No OSM file found")
        gdf["actividad_abs"] = 0
        gdf["densidad_actividad"] = 0.0
        return gdf
    
    shop_tags = {"shop"}
    amenity_tags = {
        "restaurant", "cafe", "bar", "fast_food", "bank",
        "pharmacy", "clinic", "school", "supermarket", "marketplace"
    }
    
    class POIHandler(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.points = []
        
        def node(self, n):
            tags = dict(n.tags)
            is_poi = False
            for key in tags:
                if key in shop_tags or key in amenity_tags or key == "office":
                    is_poi = True
                    break
            if is_poi:
                lon, lat = n.location.lon, n.location.lat
                self.points.append((lon, lat))
    
    print("  [OSM] Processing POIs (this may take a while)...")
    handler = POIHandler()
    handler.apply_file(str(OSM_FILE), locations=True)
    
    print(f"  [OSM] Found {len(handler.points)} POIs")
    
    if not handler.points:
        gdf["actividad_abs"] = 0
        gdf["densidad_actividad"] = 0.0
        return gdf
    
    from shapely.geometry import Point
    pois_gdf = gpd.GeoDataFrame(
        [{"geometry": Point(lon, lat)} for lon, lat in handler.points],
        crs="EPSG:4326"
    )
    
    pois_proj = pois_gdf.to_crs(epsg=25830)
    sections_proj = gdf.to_crs(epsg=25830)
    
    join_osm = gpd.sjoin(
        pois_proj[["geometry"]],
        sections_proj[["cusec", "area_km2", "geometry"]],
        how="left",
        predicate="within",
    )
    
    activity = join_osm.groupby("cusec").size().reset_index(name="actividad_abs")
    merged = gdf.merge(activity, on="cusec", how="left")
    merged["actividad_abs"] = merged["actividad_abs"].fillna(0).astype(int)
    merged["densidad_actividad"] = merged["actividad_abs"] / merged["area_km2"].clip(lower=0.01)
    return merged


def process_catastro(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if not CATASTRO_DIR.exists():
        gdf["ratio_comercial"] = 0.0
        gdf["modernidad"] = 0.0
        return gdf

    constru_zips = [
        path for path in CATASTRO_DIR.rglob("*.ZIP") if "CONSTRU" in path.name.upper()
    ]

    if not constru_zips:
        gdf["ratio_comercial"] = 0.0
        gdf["modernidad"] = 0.0
        return gdf

    pieces = []
    for i, zip_path in enumerate(constru_zips):
        try:
            piece = gpd.read_file(f"zip://{zip_path}")
            if piece.empty:
                continue
            pieces.append(piece)
            if i % 50 == 0:
                print(f"  Processed {i+1}/{len(constru_zips)} files...")
        except Exception as e:
            print(f"  Error reading {zip_path.name}: {e}")
            continue

    if not pieces:
        print("  [!] No se leyo nenhum edificio")
        gdf["ratio_comercial"] = 0.0
        gdf["modernidad"] = 0.0
        return gdf

    print(f"  Total edificios: {len(pieces)} archivos, {sum(len(p) for p in pieces)} features")

    buildings = gpd.GeoDataFrame(pd.concat(pieces, ignore_index=True), geometry="geometry")
    print(f"  Edificios combinados: {len(buildings)}")
    
    if buildings.crs is None:
        buildings = buildings.set_crs(epsg=25830, allow_override=True)
    elif str(buildings.crs).lower() not in {"epsg:25830", "25830"}:
        buildings = buildings.to_crs(epsg=25830)

    use_candidates = ["CONSTRU", "TIPO", "currentUse", "USO", "USO_PRINC", "USO_DEST"]
    year_candidates = ["FECHAALTA", "ANO_CONS", "ANIO_CONS", "YEAR", "FEC_CONS", "beginning"]

    constru_col = next((c for c in use_candidates if c in buildings.columns), None)
    year_col = next((c for c in year_candidates if c in buildings.columns), None)
    
    print(f"  constru_col: {constru_col}")
    print(f"  year_col: {year_col}")
    if constru_col:
        print(f"  Sample constru values: {buildings[constru_col].head(3).tolist()}")

    sections_proj = gdf.to_crs(epsg=25830)
    print(f"  Secciones projection: {len(sections_proj)}")
    
    joined = gpd.sjoin(
        buildings[[c for c in [constru_col, year_col, "geometry"] if c]],
        sections_proj[["cusec", "geometry"]],
        how="left",
        predicate="within",
    )
    
    print(f"  Joined result: {len(joined)} rows")

    if joined.empty:
        print("  [!] Join returned empty")
        gdf["ratio_comercial"] = 0.0
        gdf["modernidad"] = 0.0
        return gdf

    residential_codes = {'I', 'II', 'III', 'P', 'PI'}
    
    def is_commercial(value: object) -> int:
        if pd.isna(value):
            return 0
        text = str(value).upper()
        if '+' in text:
            return 1
        if text in residential_codes:
            return 0
        return 1
    
    def get_year(value):
        if pd.isna(value):
            return 1970
        s = str(value)
        if len(s) >= 4:
            try:
                return int(s[:4])
            except:
                pass
        return 1970

    if constru_col is None:
        joined["_commercial"] = 0
    else:
        joined["_commercial"] = joined[constru_col].apply(is_commercial)
        print(f"  Commercial count: {joined['_commercial'].sum()}")

    if year_col is None:
        joined["_year"] = 1970.0
    else:
        joined["_year"] = pd.to_numeric(
            joined[year_col].astype(str).str.extract(r"(\d{4})", expand=False),
            errors="coerce",
        ).fillna(1970.0)

    agg = (
        joined.groupby("cusec")
        .apply(
            lambda x: pd.Series(
                {
                    "n_edificios": len(x),
                    "n_comerciales": int(x["_commercial"].sum()),
                    "anio_medio": float(x["_year"].mean()),
                }
            )
        )
        .reset_index()
    )

    agg["ratio_comercial"] = agg["n_comerciales"] / agg["n_edificios"].clip(lower=1)
    agg["modernidad"] = agg["anio_medio"]
    
    print(f"  Aggregation result: {len(agg)} sections with data")
    print(f"  Sample ratio_comercial: {agg['ratio_comercial'].head(3).tolist()}")
    print(f"  Sample modernidad: {agg['modernidad'].head(3).tolist()}")

    merged = gdf.merge(agg[["cusec", "ratio_comercial", "modernidad"]], on="cusec", how="left")
    print(f"  After merge: {merged['ratio_comercial'].sum()} total ratio, {merged['modernidad'].mean()} mean year")
    merged["ratio_comercial"] = merged["ratio_comercial"].fillna(0.0)
    merged["modernidad"] = merged["modernidad"].fillna(1970.0)
    return merged


def validate_output(output: gpd.GeoDataFrame) -> None:
    # Dependiendo de la version del shapefile puede haber menos secciones que el
    # objetivo historico del MVP (~3800). Se valida un minimo razonable para
    # detectar cortes incompletos sin bloquear ejecuciones validas.
    if len(output) < 1500:
        raise ValueError(f"Numero de secciones inesperado: {len(output)}")
    if output["cusec"].nunique() != len(output):
        raise ValueError("Existen CUSEC duplicados en la salida")

    norm_cols = [c for c in output.columns if c.endswith("_norm")]
    for column in norm_cols:
        if not output[column].between(0, 1).all():
            raise ValueError(f"{column} fuera del rango [0,1]")


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("[1/5] Cargando secciones censales...")
    gdf = load_sections()
    print(f"  Secciones: {len(gdf)}")

    print("[2/5] Procesando renta...")
    gdf, renta_year = process_renta(gdf)

    print("[3/5] Procesando población IGE...")
    gdf = process_poblacion_ige(gdf)

    print("[4/5] Procesando actividad OSM...")
    gdf = process_osm(gdf)

    print("[5/5] Procesando catastro...")
    gdf = process_catastro(gdf)

    print("[6/6] Normalizando y exportando...")
    print(f"  Columns before norm: {gdf.columns.tolist()}")
    print(f"  ratio_comercial: min={gdf['ratio_comercial'].min():.4f}, max={gdf['ratio_comercial'].max():.4f}")
    print(f"  modernidad: min={gdf['modernidad'].min():.4f}, max={gdf['modernidad'].max():.4f}")
    
    gdf["renta_norm"] = minmax_norm(gdf["renta_abs"])
    gdf["densidad_norm"] = minmax_norm(gdf["densidad"])
    gdf["jovenes_norm"] = minmax_norm(gdf["pct_jovenes"])
    gdf["mayores_norm"] = minmax_norm(gdf["pct_mayores"])
    gdf["actividad_norm"] = log_norm(gdf["densidad_actividad"])
    gdf["uso_comercial_norm"] = minmax_norm(gdf["ratio_comercial"])
    gdf["antiguedad_norm"] = minmax_norm(gdf["modernidad"])
    
    print(f"  uso_comercial_norm sample: {gdf['uso_comercial_norm'].head(3).tolist()}")
    print(f"  antiguedad_norm sample: {gdf['antiguedad_norm'].head(3).tolist()}")

    cols_output = [
        "cusec",
        "NMUN",
        "renta_norm",
        "renta_abs",
        "densidad_norm",
        "jovenes_norm",
        "mayores_norm",
        "poblacion_abs",
        "actividad_norm",
        "actividad_abs",
        "uso_comercial_norm",
        "antiguedad_norm",
        "geometry",
    ]

    output = gdf[cols_output].copy()
    validate_output(output)

    geojson_path = PROCESSED_DIR / "galicia_scouting.geojson"
    output.to_file(geojson_path, driver="GeoJSON")

    last_update = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "sections_count": int(len(output)),
        "year_data": renta_year,
        "sources": {
            "geometries": "CNIG secciones censales",
            "renta": f"INE Atlas de Renta (año {renta_year})",
            "osm": "OpenStreetMap Galicia (Geofabrik)",
            "catastro": "Sede Electronica del Catastro",
        },
        "variables": [c for c in cols_output if c.endswith("_norm")],
    }

    with open(PROCESSED_DIR / "last_update.json", "w", encoding="utf-8") as file:
        json.dump(last_update, file, indent=2, ensure_ascii=False)

    print(f"  GeoJSON: {geojson_path}")
    print(f"  Metadatos: {PROCESSED_DIR / 'last_update.json'}")


if __name__ == "__main__":
    main()
