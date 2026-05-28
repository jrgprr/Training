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
- acceso al detalle de actividades Garmin enlazadas,
- panel de revision AI con ultimas evaluaciones por cadencia,
- detalle de evidencia, hallazgos y dialogo acotado de cada evaluacion,
- y cola de propuestas pendientes con acciones de aprobacion o rechazo apoyadas solo en payloads backend.

## Workflow local-first

- La GUI no construye prompts, no llama directamente a proveedores LLM y no infiere decisiones de coaching.
- El backend entrega el roster de agentes mediante `agent_profile_key`, las evaluaciones persistidas, las propuestas y el historial de decisiones.
- Las aclaraciones del usuario se muestran como dialogo acotado ligado a una evaluacion o propuesta persistida.
- El plan canonico no cambia en frontend: solo una propuesta aceptada desde backend puede materializar una mutacion trazable en SQLite.

Roster visible en V1:
- `daily_execution_v1`
- `daily_recovery_readiness_v1`
- `weekly_adherence_adequacy_v1`
- `block_performance_direction_v1`

Estado actual del entorno:
- el formulario manual se muestra deshabilitado para no reintroducir datos fuera de Garmin Connect,
- y la GUI trabaja sobre un dataset saneado a Garmin-only.
