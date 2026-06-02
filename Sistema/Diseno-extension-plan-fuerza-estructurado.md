# Diseno de extension SQLite para plan de fuerza estructurado

## Estado actual

Esta nota queda como documento de diseno historico y como referencia de esquema, pero no describe ya una superficie activa de GUI o API.

Situacion vigente:
- la GUI no expone detalle estructurado de prescripcion;
- el endpoint dedicado de detalle fue retirado;
- el plan operativo visible vive en `plan_planned_sessions` y en los objetivos de zona derivados;
- las tablas de prescripcion pueden seguir existiendo como soporte interno o compatibilidad, pero no forman parte del flujo actual de lectura minima.

## 1. Problema que hay que resolver

El modelo actual permite guardar bien el plan a nivel semanal y de sesion, pero no la prescripcion interna de una sesion de fuerza.

Hoy la informacion de fuerza solo cabe de forma parcial en:
- `plan_planned_sessions.primary_session`,
- `plan_planned_sessions.complementary_session`,
- `plan_planned_sessions.notes`,
- `plan_planned_sessions.adjustment_rule`,
- y `plan_planned_sessions.markdown_path`.

Eso sirve para un resumen humano breve, pero no para representar de forma estructurada:
- bloques de calentamiento, principal, accesorios y core,
- ejercicios concretos,
- series, repeticiones, tiempo o distancia,
- RPE o RIR objetivo,
- variantes y sustituciones,
- y progresion real semana a semana dentro de un bloque.

## 2. Criterio de diseno

La extension correcta no debe ser una tabla solo para `fuerza`, sino una capa de prescripcion estructurada reutilizable por cualquier sesion planificada.

Principios:
- `plan_planned_sessions` sigue siendo la cabecera minima de cada sesion.
- La prescripcion detallada, si existe, vive en tablas hijas nuevas como soporte interno.
- La GUI sigue leyendo el resumen semanal sin cargar toda la estructura.
- No existe actualmente ficha detallada de sesion ni consulta bajo demanda desde la GUI.
- La solucion debe permitir sesiones diferentes semana a semana sin obligar a reutilizar plantillas.
- Las plantillas reutilizables pueden venir despues, pero no deben bloquear la primera version util.

## 3. Propuesta relacional

## 3.1. Nivel 1 - Cabecera de prescripcion

Nueva tabla: `plan_session_prescriptions`

Funcion:
- guardar la prescripcion estructurada asociada a una sesion planificada concreta.

Relacion:
- `1:1` con `plan_planned_sessions`.

Campos propuestos:
- `prescription_id`.
- `planned_session_id`.
- `prescription_type`: `strength`, `bike`, `run`, `mobility`, `other`.
- `title`: nombre visible de la sesion prescrita.
- `focus_primary`: por ejemplo `tren_superior`, `core`, `torso`, `traccion`, `empuje`.
- `focus_secondary`.
- `estimated_duration_min`.
- `estimated_duration_max`.
- `target_rpe_min`.
- `target_rpe_max`.
- `warmup_notes`.
- `cooldown_notes`.
- `execution_notes`.
- `adaptation_notes`.
- `source_markdown_path`.
- `created_at`.
- `updated_at`.

## 3.2. Nivel 2 - Bloques dentro de la sesion

Nueva tabla: `plan_prescription_blocks`

Funcion:
- dividir una sesion en bloques legibles y ordenados.

Relacion:
- `1:N` desde `plan_session_prescriptions`.

Campos propuestos:
- `prescription_block_id`.
- `prescription_id`.
- `sequence_order`.
- `block_type`: `warmup`, `main`, `accessory`, `core`, `cooldown`.
- `block_name`.
- `objective`.
- `rounds`.
- `rest_seconds`.
- `notes`.

## 3.3. Nivel 3 - Ejercicios de cada bloque

Nueva tabla: `plan_prescription_exercises`

Funcion:
- representar cada ejercicio o tarea prescripta de forma estructurada.

Relacion:
- `1:N` desde `plan_prescription_blocks`.

Campos propuestos:
- `prescription_exercise_id`.
- `prescription_block_id`.
- `sequence_order`.
- `exercise_name`.
- `movement_pattern`: `push_horizontal`, `push_vertical`, `pull_horizontal`, `pull_vertical`, `anti_rotation`, `anti_extension`, `carry`, etc.
- `equipment`: `mancuernas`, `barra`, `banda`, `banco`, `dominadas`, `peso_corporal`, etc.
- `unilateral_mode`: `none`, `left_right`, `alternating`.
- `sets_count`.
- `reps_min`.
- `reps_max`.
- `hold_seconds_min`.
- `hold_seconds_max`.
- `distance_meters`.
- `target_rpe_min`.
- `target_rpe_max`.
- `target_rir_min`.
- `target_rir_max`.
- `tempo`.
- `load_guidance`.
- `optional_flag`.
- `substitution_group`.
- `notes`.

## 3.4. Nivel 4 - Sustituciones y variantes

Nueva tabla: `plan_prescription_exercise_options`

Funcion:
- permitir sustituciones sin meterlas en texto libre dentro del ejercicio principal.

Relacion:
- `1:N` desde `plan_prescription_exercises`.

Campos propuestos:
- `exercise_option_id`.
- `prescription_exercise_id`.
- `sequence_order`.
- `option_name`.
- `equipment`.
- `condition_notes`.

## 4. DDL propuesto

```sql
CREATE TABLE IF NOT EXISTS plan_session_prescriptions (
    prescription_id INTEGER PRIMARY KEY,
    planned_session_id INTEGER NOT NULL UNIQUE,
    prescription_type TEXT NOT NULL DEFAULT 'other',
    title TEXT,
    focus_primary TEXT,
    focus_secondary TEXT,
    estimated_duration_min INTEGER,
    estimated_duration_max INTEGER,
    target_rpe_min REAL,
    target_rpe_max REAL,
    warmup_notes TEXT,
    cooldown_notes TEXT,
    execution_notes TEXT,
    adaptation_notes TEXT,
    source_markdown_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (planned_session_id) REFERENCES plan_planned_sessions (planned_session_id)
);

CREATE TABLE IF NOT EXISTS plan_prescription_blocks (
    prescription_block_id INTEGER PRIMARY KEY,
    prescription_id INTEGER NOT NULL,
    sequence_order INTEGER NOT NULL,
    block_type TEXT NOT NULL,
    block_name TEXT,
    objective TEXT,
    rounds INTEGER,
    rest_seconds INTEGER,
    notes TEXT,
    FOREIGN KEY (prescription_id) REFERENCES plan_session_prescriptions (prescription_id),
    UNIQUE (prescription_id, sequence_order)
);

CREATE TABLE IF NOT EXISTS plan_prescription_exercises (
    prescription_exercise_id INTEGER PRIMARY KEY,
    prescription_block_id INTEGER NOT NULL,
    sequence_order INTEGER NOT NULL,
    exercise_name TEXT NOT NULL,
    movement_pattern TEXT,
    equipment TEXT,
    unilateral_mode TEXT NOT NULL DEFAULT 'none',
    sets_count INTEGER,
    reps_min INTEGER,
    reps_max INTEGER,
    hold_seconds_min INTEGER,
    hold_seconds_max INTEGER,
    distance_meters REAL,
    target_rpe_min REAL,
    target_rpe_max REAL,
    target_rir_min REAL,
    target_rir_max REAL,
    tempo TEXT,
    load_guidance TEXT,
    optional_flag INTEGER NOT NULL DEFAULT 0,
    substitution_group TEXT,
    notes TEXT,
    FOREIGN KEY (prescription_block_id) REFERENCES plan_prescription_blocks (prescription_block_id),
    UNIQUE (prescription_block_id, sequence_order)
);

CREATE TABLE IF NOT EXISTS plan_prescription_exercise_options (
    exercise_option_id INTEGER PRIMARY KEY,
    prescription_exercise_id INTEGER NOT NULL,
    sequence_order INTEGER NOT NULL,
    option_name TEXT NOT NULL,
    equipment TEXT,
    condition_notes TEXT,
    FOREIGN KEY (prescription_exercise_id) REFERENCES plan_prescription_exercises (prescription_exercise_id),
    UNIQUE (prescription_exercise_id, sequence_order)
);

CREATE INDEX IF NOT EXISTS idx_plan_prescriptions_session
ON plan_session_prescriptions (planned_session_id);

CREATE INDEX IF NOT EXISTS idx_plan_prescription_blocks_prescription
ON plan_prescription_blocks (prescription_id, sequence_order);

CREATE INDEX IF NOT EXISTS idx_plan_prescription_exercises_block
ON plan_prescription_exercises (prescription_block_id, sequence_order);
```

## 5. Por que esta extension es mejor que usar solo `notes`

- permite conservar estructura rica si mas adelante vuelve a necesitarse;
- permite derivar reglas o lectura adicional sin depender de texto libre;
- permite contar ejercicios, bloques, duraciones y objetivos;
- permite sustituciones explicitadas;
- y mantiene `plan_planned_sessions` limpio como resumen semanal cuando se quiera separar resumen operativo de detalle interno.

`notes` y `adjustment_rule` siguen siendo utiles, pero como capa corta de lectura rapida, no como modelo principal de la fuerza.

## 6. Como encaja con B1

La version actual de B1 ya no usa una sesion principal de fuerza con detalle estructurado expuesto.

Para B1, el patron operativo vigente es:
- lunes y jueves: pecho, triceps y hombro;
- martes y viernes: espalda y biceps;
- miercoles y sabado: core;
- domingo: sin fuerza.

Ejemplo conceptual para una semana:
- cabecera operativa en `plan_planned_sessions`;
- complementario breve por grupo muscular;
- y, si alguna vez hiciera falta, una capa estructurada interna separada del flujo GUI.

## 7. Superficie API recomendada

Superficie vigente:
- `GET /api/weeks/{week_id}/sessions`

Estado actual:
- no existe endpoint publico de detalle estructurado para una sesion planificada;
- el endpoint semanal ya no expone `has_structured_prescription`;
- y la lectura operativa se concentra en resumen de sesion, comparativa plan vs realidad y objetivos de zona.

## 8. Superficie GUI recomendada

Superficie vigente:
- la tabla `Sesiones planificadas` muestra solo lectura operativa de dia, tipo, objetivo, sesion principal, zona, complementario y duracion;
- no hay indicador de detalle estructurado;
- y no hay ficha lateral o modal de prescripcion.

## 9. Migracion recomendada

La migracion ejecutada finalmente tomo otra direccion:
- se consolidaron los cambios operativos en `plan_planned_sessions` y en seeds de planificacion;
- se retiraron la GUI y la API de detalle estructurado;
- y se eliminaron seeds de B1 que solo alimentaban ese drill-down.

Si alguna vez se reabre esta linea:
- primero habria que justificar un consumidor real de GUI o API;
- despues decidir si conviene reintroducir prescripciones persistidas o derivacion al vuelo;
- y solo entonces volver a poblar detalle estructurado.

## 10. Lo que no haria en esta fase

- no moveria todo el plan a JSON dentro de un solo campo;
- no intentaria modelar una libreria global de ejercicios demasiado pronto;
- no intentaria mezclar ejecucion real de fuerza con prescripcion estructurada en la misma tabla;
- y no sustituiria `plan_planned_sessions`, porque sigue siendo la unidad correcta de plan semanal.

## 11. Decision propuesta

Decision vigente:
- mantener `plan_planned_sessions` como resumen operativo canonico visible;
- mantener objetivos de zona y comparativa semanal como lectura estructurada activa;
- no exponer detalle estructurado de prescripcion en GUI o API mientras no exista un caso de uso claro;
- y tratar esta extension como esquema potencial o soporte interno, no como contrato activo de lectura.