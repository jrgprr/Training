# Flujo manual V0.2

Este documento fija el flujo minimo para registrar una semana real sin Garmin y sin ambiguedad operativa.

## 1. Objetivo

Cerrar una semana de B1 de extremo a extremo con cuatro capas:
- metricas diarias,
- actividad ejecutada,
- enlace plan vs realidad,
- y revision diaria con decision operativa.

## 2. Unidad operativa minima

La unidad minima de registro es una sesion planificada concreta identificada por `planned_session_id`.

Desde esa sesion se derivan automaticamente:
- `season_id`,
- `block_id`,
- `week_id`,
- y la fecha planificada por defecto.

Esto evita escribir manualmente claves estructurales y reduce errores.

## 3. Campos minimos por tabla

### `exec_daily_metrics`

Minimos recomendados por dia:
- `metric_date`
- `source_system = manual`
- `weight_kg`
- `sleep_hours`
- `resting_hr`
- `subjective_energy`
- `subjective_fatigue`
- `notes`

### `exec_activities`

Minimos recomendados cuando hubo actividad:
- `season_id`
- `source_system = manual`
- `activity_date`
- `discipline`
- `activity_type`
- `duration_seconds`
- `perceived_exertion`
- `subjective_feeling`
- `notes`

### `link_plan_execution`

Minimos:
- `planned_session_id`
- `activity_id`
- `compliance_status`
- `rationale`

Estados recomendados de `compliance_status` para `V0.2`:
- `completed`
- `partial`
- `skipped`
- `replaced`

### `review_daily_reviews`

Minimos:
- `review_date`
- `planned_session_id`
- `planned_summary`
- `actual_summary`
- `compliance_status`
- `general_feeling`
- `perceived_recovery`
- `observations`
- `next_day_decision`

## 4. Regla de escritura minima

Para cada sesion planificada:
1. Registrar metricas diarias si existen.
2. Registrar actividad solo si realmente hubo una actividad identificable.
3. Enlazar plan y ejecucion solo cuando exista actividad.
4. Registrar siempre una revision diaria, incluso si la sesion se omite.

## 5. Resultado esperado

Con este flujo debe poder responderse, para cualquier dia de una semana:
- que estaba previsto,
- que se hizo realmente,
- como se tolero,
- y que decision deja para el dia siguiente.

## 6. Referencia de ejemplo

La semana de ejemplo cargable para `B1 / Semana-01` esta en:
- `Seeds/2026-v0.2-example-week.sql`