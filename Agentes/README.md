# Arquitectura de agentes

Esta carpeta define la arquitectura de agentes del sistema completo de entrenamiento.

El objetivo no es tener un unico agente generalista, sino varios agentes especializados sobre una base comun:
- SQLite como fuente primaria estructurada,
- Markdown como vista humana,
- `Datos/Importaciones/` como entrada de fuentes externas como Garmin,
- y una GUI como interfaz principal para el usuario.

## 1. Principio de diseno

Los agentes se separan por responsabilidad, no por herramienta.

Eso significa:
- un agente no deberia importar, analizar, ajustar y renderizar al mismo tiempo,
- cada agente deberia leer y escribir en tablas concretas,
- y las decisiones de ajuste deberian quedar trazadas en la base.

## 2. Capas de agentes

Los agentes no viven aislados: forman parte de una arquitectura mayor en la que la GUI lanza acciones y consulta resultados.

### Capa de ingestion
- Mete datos externos dentro del sistema.

### Capa de interpretacion
- Convierte datos crudos en informacion util sobre entrenamiento, recuperacion y cumplimiento.

### Capa de planificacion y ajuste
- Propone cambios sobre el plan a partir del contexto y la ejecucion real.

### Capa de publicacion
- Convierte el estado estructurado del sistema en vistas humanas legibles.

### Capa de interfaz
- No es una capa de agentes en sentido estricto, pero es la capa que consume a los agentes y expone sus resultados al usuario.

## 3. Agentes principales

### 1. Garmin Import Agent

Funcion:
- importar actividades, metricas diarias y otros datos desde Garmin.

Entradas:
- ficheros en `Datos/Importaciones/Garmin/`,
- credenciales o exportaciones manuales,
- y tablas `meta_import_jobs`, `exec_activities`, `exec_daily_metrics`.

Salidas:
- registros cargados en tablas de ejecucion,
- trazabilidad de importacion,
- y errores de mapeo si los hay.

Valor:
- convierte Garmin en una fuente operativa real del sistema.

### 2. Data Normalization Agent

Funcion:
- limpiar, normalizar y mapear datos importados antes de que entren en las tablas definitivas.

Entradas:
- ficheros crudos o staging,
- reglas de mapeo por deporte, dispositivo o fuente.

Salidas:
- datos consistentes en unidades, nombres de disciplina, tipos de actividad y campos derivados.

Valor:
- evita que el sistema se llene de variantes incompatibles del mismo dato.

### 3. Activity Analysis Agent

Funcion:
- analizar actividades realizadas desde el punto de vista del entrenamiento.

Entradas:
- `exec_activities`,
- vistas del plan,
- metricas fisiologicas cercanas.

Salidas:
- clasificacion de actividad,
- lectura de carga real,
- deteccion de sesiones clave,
- observaciones sobre duracion, intensidad y tolerancia.

Valor:
- traduce hechos brutos a significado deportivo.

### 4. Daily Physiology Agent

Funcion:
- analizar el estado diario del usuario a partir de peso, sueno, FC reposo, HRV y senales subjetivas.

Entradas:
- `exec_daily_metrics`,
- contexto del perfil y del bloque actual.

Salidas:
- lectura de frescura,
- senales de prudencia,
- estado de recuperacion,
- observaciones para el dia siguiente.

Valor:
- aporta contexto fisiologico a la interpretacion del entrenamiento.

### 5. Plan-Execution Linking Agent

Funcion:
- enlazar sesiones planificadas con actividades realmente realizadas.

Entradas:
- `plan_planned_sessions`,
- `exec_activities`,
- fechas, disciplinas, duraciones y contexto de bloque.

Salidas:
- registros en `link_plan_execution`,
- estado de cumplimiento,
- explicacion del enlace o de la desviacion.

Valor:
- crea el puente clave entre plan y realidad.

### 6. Daily Review Agent

Funcion:
- generar una revision diaria operativa.

Entradas:
- actividad real,
- metricas diarias,
- sesion planificada,
- estado del bloque.

Salidas:
- registros en `review_daily_reviews`,
- lectura del dia,
- propuesta para el dia siguiente.

Valor:
- convierte datos dispersos en una decision util y trazable.

### 7. Weekly Review Agent

Funcion:
- revisar la semana completa frente a lo planificado.

Entradas:
- tablas `plan_`, `exec_`, `link_` y `review_`.

Salidas:
- cumplimiento semanal,
- desviaciones,
- tolerancia real de carga,
- decision de mantener, progresar o consolidar.

Valor:
- es el agente que realmente dice si el plan esta funcionando.

### 8. Meso Adjustment Agent

Funcion:
- proponer ajustes del bloque actual o del siguiente bloque.

Entradas:
- revisiones semanales,
- tendencias de recuperacion,
- cumplimiento del bloque,
- prioridades del macro.

Salidas:
- recomendaciones de ajuste sobre volumen, densidad, fuerza o prudencia,
- propuestas de extender, acortar o modificar bloques.

Valor:
- convierte analisis en plan adaptativo.

### 9. Plan Authoring Agent

Funcion:
- escribir o reescribir planificacion estructurada en la base de datos.

Entradas:
- objetivos macro,
- decisiones de ajuste,
- estado actual del usuario.

Salidas:
- nuevas filas o cambios en `plan_macro_cycles`, `plan_meso_blocks`, `plan_micro_weeks` y `plan_planned_sessions`.

Valor:
- permite que el plan viva de verdad en la base, no solo en markdown.

### 10. Markdown Rendering Agent

Funcion:
- generar vistas humanas en markdown a partir de la base relacional.

Entradas:
- tablas `plan_`, `review_` y `meta_markdown_views`.

Salidas:
- `Macro.md`,
- `Bloques/README.md`,
- `README.md` de bloque,
- semanas,
- y otros documentos narrativos.

Valor:
- mantiene legibilidad humana sin romper la fuente primaria.

### 11. Consistency and Audit Agent

Funcion:
- comprobar integridad entre base, markdown, importaciones y enlaces plan-real.

Entradas:
- base SQLite,
- vistas markdown,
- metadatos de importacion.

Salidas:
- deteccion de huecos,
- inconsistencias,
- sesiones sin enlace,
- bloques sin semanas,
- markdown desactualizado respecto a la base.

Valor:
- protege la calidad del sistema a medio plazo.

## 4. Agente orquestador

Ademas de los agentes especializados, conviene un agente coordinador.

### 12. Training System Orchestrator

Funcion:
- decidir que agente debe intervenir y en que orden segun la tarea.

Ejemplos:
- si entran exportaciones Garmin: llama a importacion, normalizacion y enlace plan-real,
- si termina una semana: llama a revision diaria acumulada, revision semanal y ajuste meso,
- si cambia el plan: llama a autoria de plan y renderizado markdown.

Valor:
- evita que el usuario tenga que pensar siempre en el pipeline interno.
- y facilita que la GUI trabaje contra una capa de acciones coherente.

## 5. Flujo recomendado del sistema

### Flujo A. Ingestion y carga
1. `Garmin Import Agent`
2. `Data Normalization Agent`
3. `Plan-Execution Linking Agent`
4. `Daily Review Agent`

### Flujo B. Revision operativa
1. `Activity Analysis Agent`
2. `Daily Physiology Agent`
3. `Daily Review Agent`
4. `Weekly Review Agent`

### Flujo C. Ajuste de plan
1. `Weekly Review Agent`
2. `Meso Adjustment Agent`
3. `Plan Authoring Agent`
4. `Markdown Rendering Agent`

### Flujo D. Salud del sistema
1. `Consistency and Audit Agent`
2. `Training System Orchestrator`

## 6. MVP recomendado

Para no sobredisenar, el MVP deberia empezar con estos cinco agentes:
- `Garmin Import Agent`
- `Activity Analysis Agent`
- `Plan-Execution Linking Agent`
- `Weekly Review Agent`
- `Markdown Rendering Agent`

Con eso ya tendrias:
- entrada de datos reales,
- interpretacion basica,
- enlace plan-real,
- revision util,
- y sincronizacion entre SQLite y Markdown.

## 7. Orden de implementacion recomendado

1. `Garmin Import Agent`
2. `Plan-Execution Linking Agent`
3. `Activity Analysis Agent`
4. `Daily Physiology Agent`
5. `Weekly Review Agent`
6. `Meso Adjustment Agent`
7. `Plan Authoring Agent`
8. `Markdown Rendering Agent`
9. `Consistency and Audit Agent`
10. `Training System Orchestrator`

## 8. Regla importante de gobierno

Ningun agente deberia modificar el plan sin dejar trazado:
- que datos ha usado,
- que criterio aplico,
- que cambio propone o ejecuta,
- y sobre que bloque, semana o sesion actua.

Esa trazabilidad es la diferencia entre un sistema fiable y una caja negra.