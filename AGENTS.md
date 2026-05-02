# AGENTS.md - UrbanViable

## Quick start

```powershell
start.bat
```

This runs the full local dev environment (tiletest, API mock, frontend).

## Dev commands

| Command | Location | Notes |
|---------|----------|-------|
| `npm run start` | frontend/ | Vite dev server with proxies to 127.0.0.1:8080 (tiles) and 8081 (status) |
| `npm run build` | frontend/ | Build static frontend (output: `frontend/build/`) |
| `npm run lint` | frontend/ | ESLint check |
| `python etl/process_data.py` | root | Generate GeoJSON from input data |
| `docker compose up -d` | root | Start tileserver (8080) + nginx (3002) |

## Architecture

- **No backend API** - all score calculation happens in GPU via MapLibre GL JS expressions
- Column names in tiles are contract between ETL and frontend - see `specs/Especificaciones_etl_UrbanViable.md`
- Variables prefixed `_norm` are 0-1 normalized for GPU, `_abs` are display values

## Key quirks

- Frontend REACT_APP_* env vars are baked at build time - change requires `npm run build`
- Vite proxies: `/tiles` → 127.0.0.1:8080, `/api/status` → 127.0.0.1:8081
- Docker ports: tileserver on 8080, nginx mapped to 3002 (not 80 - adjusts in docker-compose.yml for shared host)
- ETL runs locally only, not in Docker

## Relevant docs

- `README.md` - full deployment and ETL flow
- `frontend/src/hooks/useMapStyle.js` - GPU expression logic
- `frontend/src/constants/variables.js` - variable definitions