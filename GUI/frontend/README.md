# Frontend GUI V0.2

Frontend minimo para navegar la planificacion estructurada y comparar semana planificada vs realidad en modo Garmin-only.

## Arranque local

```powershell
npm install
npm run dev
```

## Dependencia de backend

Espera un backend FastAPI local en `http://127.0.0.1:8000`.

## Alcance actual

- navegacion temporada -> bloque -> semana -> sesiones,
- tabla semanal de `plan vs realidad`,
- resumen semanal minimo derivado de la comparativa,
- feed de actividades reales de temporada,
- y acceso al detalle de actividades Garmin enlazadas.

Estado actual del entorno:
- el formulario manual se muestra deshabilitado para no reintroducir datos fuera de Garmin Connect,
- y la GUI trabaja sobre un dataset saneado a Garmin-only.
