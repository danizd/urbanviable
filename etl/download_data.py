"""Descarga asistida de fuentes para UrbanViable.

Este script no resuelve autenticaciones complejas de Catastro,
pero deja automatizada la descarga de OSM y permite verificar
que el resto de fuentes esten en su ruta esperada.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

DATA_DIR = Path("etl/data")
SECTIONS_DIR = DATA_DIR / "secciones_censales"
OSM_PATH = DATA_DIR / "galicia-260424.osm.pbf"
RENTA_PATH = DATA_DIR / "renta.csv"
CATASTRO_DIR = DATA_DIR / "catastro"

OSM_URL = "https://download.geofabrik.de/europe/spain/galicia-latest.osm.pbf"


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        with open(destination, "wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    file.write(chunk)


def print_status() -> int:
    ok = True

    section_shp = sorted(SECTIONS_DIR.glob("*.shp"))
    if section_shp:
        print(f"[OK] Secciones censales: {section_shp[0]}")
    else:
        print("[WARN] No se encontro shapefile en etl/data/secciones_censales")
        ok = False

    if RENTA_PATH.exists():
        print(f"[OK] Renta: {RENTA_PATH}")
    else:
        print("[WARN] Falta etl/data/renta.csv")
        ok = False

    if OSM_PATH.exists():
        print(f"[OK] OSM: {OSM_PATH}")
    else:
        print("[WARN] Falta OSM. Usa --download-osm para descargarlo.")
        ok = False

    if CATASTRO_DIR.exists() and any(CATASTRO_DIR.rglob("*.ZIP")):
        print(f"[OK] Catastro: {CATASTRO_DIR}")
    else:
        print("[WARN] Catastro no detectado. El ETL seguira con fallbacks a cero.")

    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Descarga y verificacion de fuentes ETL UrbanViable")
    parser.add_argument("--download-osm", action="store_true", help="Descargar OSM Galicia de Geofabrik")
    args = parser.parse_args()

    if args.download_osm:
        print("Descargando OSM Galicia...")
        download_file(OSM_URL, OSM_PATH)
        print(f"OSM guardado en: {OSM_PATH}")

    return print_status()


if __name__ == "__main__":
    sys.exit(main())
