#!/bin/sh
set -eu

INPUT="etl/data/processed/galicia_scouting.geojson"
OUTPUT="etl/data/processed/galicia_scouting.mbtiles"
LAYER_NAME="secciones"

if [ ! -f "$INPUT" ]; then
  echo "ERROR: $INPUT no existe. Ejecuta process_data.py primero."
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
  --include=cusec \
  --include=renta_norm \
  --include=renta_abs \
  --include=densidad_norm \
  --include=jovenes_norm \
  --include=mayores_norm \
  --include=poblacion_abs \
  --include=actividad_norm \
  --include=actividad_abs \
  --include=uso_comercial_norm \
  --include=antiguedad_norm \
  "$INPUT"

echo "Teselas generadas: $OUTPUT"
