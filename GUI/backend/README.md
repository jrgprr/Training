# Backend GUI V0.2 / V0.3

Backend minimo de lectura para la GUI de `V0.2`.

## Endpoints

- `GET /api/health`
- `GET /api/seasons`
- `GET /api/seasons/{season_id}/blocks`
- `GET /api/blocks/{block_id}/weeks`
- `GET /api/weeks/{week_id}/sessions`
- `GET /api/weeks/{week_id}/plan-vs-real`
- `GET /api/weeks/{week_id}/review`
- `PUT /api/weeks/{week_id}/review`
- `DELETE /api/weeks/{week_id}/review`
- `POST /api/imports/garmin-connect/preview`
- `POST /api/imports/garmin-connect/run`
- `GET /api/import-jobs`
- `GET /api/import-jobs/{import_job_id}`

## Arranque local

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Fuente de datos

La API lee desde `Sistema/training.sqlite`.

## V0.3 - Garmin Connect directo

El backend ya tiene el esqueleto de `V0.3` para un adaptador Garmin Connect desacoplado.

Superficies creadas:
- `app/imports/contracts.py`
- `app/imports/garmin_connect.py`
- `app/imports/pipeline.py`
- `app/imports/storage.py`

Estado actual:
- `preview` existe,
- `run` existe,
- la autenticacion usa la libreria `garminconnect`,
- se recuperan actividades por rango y metricas diarias basicas,
- la carga persiste `import_jobs`, staging y tablas finales en SQLite,
- la GUI ya puede lanzar importaciones y consultar el historial,
- el CLI minimo equivalente ya esta operativo,
- y los artefactos TCX por actividad se guardan por defecto en `/<temporada>/Datos/Importaciones/Garmin/Actividades/<fecha>/<activity_id>.tcx`.

Configuracion minima esperada:

```bash
export GARMIN_CONNECT_SESSION_PATH=~/.garminconnect
```

o bien:

```bash
export GARMIN_CONNECT_USERNAME=tu_usuario
export GARMIN_CONNECT_PASSWORD=tu_password
```

Si la cuenta usa MFA en un flujo no interactivo:

```bash
export GARMIN_CONNECT_MFA_CODE=123456
```

Comportamiento actual:
- si falta configuracion, la API responde con error `400` explicito,
- si existe configuracion, el adaptador autentica y consulta Garmin Connect mediante `garminconnect`,
- `preview` devuelve conteos reales del rango consultado,
- `run` persiste el lote en staging y en las tablas `exec_*`,
- `run` registra el `import_job` desde el inicio y marca el intento como `failed` si falla el fetch o la persistencia,
- el historial expone detalle de `inserted/updated` cuando ese dato existe para el job,
- y `dry-run` y `apply` del CLI reutilizan el mismo pipeline interno.

CLI minimo equivalente:

```bash
python -m app.imports.garmin_connect --season 2026 --from 2026-05-04 --to 2026-05-10 --dry-run
python -m app.imports.garmin_connect --season 2026 --from 2026-05-04 --to 2026-05-10 --apply
```

Sincronizacion manual del perfil actual de Garmin hacia la app:

```bash
python -m app.imports.garmin_connect --season 2026 --sync-profile
```

Opcional:

```bash
python -m app.imports.garmin_connect --season 2026 --from 2026-05-04 --to 2026-05-10 --dry-run --no-daily-metrics
```

Validacion realizada para cierre de V0.3:
- tests automatizados del CLI para `dry-run`, `apply` y fallo de fetch,
- `dry-run` real validado sobre `2026-05-05`,
- `apply` real validado sobre `2026-05-05`,
- y comprobacion de staging, `meta_import_jobs` y `raw_payload_path` final en SQLite.

## Modo Garmin-only

La instancia de trabajo actual queda fijada en modo Garmin-only:
- las actividades y metricas reales nuevas deben entrar por Garmin Connect,
- el backend ya no expone endpoints de escritura manual heredados,
- y el dataset activo se ha saneado para eliminar capturas manuales y residuos sinteticos.
