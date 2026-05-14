# Sistema

Esta carpeta contiene la infraestructura general y la fuente primaria estructurada del sistema completo de entrenamiento.

## 1. Funcion

La base SQLite de esta carpeta es la verdad estructurada del sistema.

Contiene:
- planificacion macro, meso y micro de todas las temporadas,
- sesiones planificadas,
- ejecucion real,
- metricas fisiologicas,
- enlaces entre plan y realidad,
- revisiones operativas,
- y metadatos de importacion y sincronizacion.

## 2. Archivos

### `schema.sql`
- Define tablas, restricciones e indices de la plataforma.

### `Diseno-extension-plan-fuerza-estructurado.md`
- Propone una extension relacional para guardar y mostrar prescripciones estructuradas de fuerza dentro del plan global.

### `views.sql`
- Define vistas SQL para consulta humana y analitica.

### `Seeds/`
- Contiene scripts de carga o bootstrap por temporada.

### `Flujo-manual-V0.2.md`
- Define el registro manual minimo de ejecucion para cerrar `V0.2`.

### `training.sqlite`
- Base SQLite unica plurianual del sistema.

## 3. Modelo de verdad

- La base SQLite de esta carpeta es la fuente primaria.
- Los markdown son vistas humanas del sistema.
- Los CSV, si existen, son formatos auxiliares de intercambio o exportacion y no forman parte del runtime normal.
- Las carpetas anuales contienen contenido de temporada, no infraestructura general.

## 4. Separacion logica dentro de la base

La separacion entre planificacion y ejecucion se mantiene dentro del modelo relacional mediante prefijos de tablas:
- `plan_`: estructura del plan.
- `exec_`: datos ejecutados y fisiologia.
- `link_`: correspondencia entre plan y realidad.
- `review_`: revisiones y decisiones.
- `meta_`: control de importaciones, fuentes y sincronizacion.

## 5. Relacion con las temporadas

Cada carpeta anual como `2026/` o `2027/` contiene:
- contexto especifico del ano,
- vistas humanas de planificacion,
- importaciones y exportaciones ligadas a esa temporada.

Pero la estructura comun del sistema y la base relacional viven aqui, en raiz.

## 6. Flujo manual minimo V0.2

Para `V0.2` ya existe una ruta de trabajo minima para registrar una semana real sin Garmin:
- especificacion funcional en `Flujo-manual-V0.2.md`,
- datos de ejemplo en `Seeds/2026-v0.2-example-week.sql`,
- y una ruta de escritura controlada en la API local.