<!--
Sync Impact Report
Version change: template -> 1.0.0
Modified principles:
- Template Principle 1 -> I. SQLite Es La Fuente Primaria
- Template Principle 2 -> II. Markdown Son Vistas Humanas, No El Runtime Canonico
- Template Principle 3 -> III. GUI Delgada, Logica De Dominio Fuera De La Vista
- Template Principle 4 -> IV. Importaciones Y Cambios Deben Ser Trazables
- Template Principle 5 -> V. Validacion Cercana Al Cambio
Added sections:
- Technical Constraints
- Workflow And Quality Gates
Removed sections:
- None
Templates requiring updates:
- ✅ .specify/templates/plan-template.md
- ✅ .specify/templates/spec-template.md
- ✅ .specify/templates/tasks-template.md
- ✅ .specify/templates/commands/*.md (no command templates present in this project)
- ✅ README.md reviewed; no update required
- ✅ GUI/README.md reviewed; no update required
- ✅ Sistema/README.md reviewed; no update required
Follow-up TODOs:
- None
-->

# Training Constitution

## Core Principles

### I. SQLite Es La Fuente Primaria
Toda decision de implementacion DEBE preservar que `Sistema/` y su base SQLite son la verdad estructurada del sistema. Los markdown, la GUI y los agentes PUEDEN derivar, renderizar, resumir o auditar datos, pero NO DEBEN redefinir la fuente canonica sin persistencia y trazabilidad en la capa estructurada. Rationale: el sistema necesita una fuente primaria unica para soportar analisis, auditoria y evolucion multi-temporada.

### II. Markdown Son Vistas Humanas, No El Runtime Canonico
Los archivos de temporada, bloques y semanas DEBEN tratarse como vistas humanas para lectura, revision y comunicacion. Cuando una funcionalidad cambie planificacion, ejecucion, importaciones o analisis, DEBE mantener coherencia entre SQLite y markdown, dejando claro si el markdown se genera, se sincroniza o se revisa manualmente. Rationale: el repositorio combina narrativa operativa y datos estructurados; sin esta distincion aparecen derivas dificiles de detectar.

### III. GUI Delgada, Logica De Dominio Fuera De La Vista
La GUI DEBE consultar estado, mostrar contexto y ejecutar acciones controladas. La logica deportiva, las reglas de importacion, la auditoria y los calculos relevantes DEBEN vivir en servicios, agentes o capas estructuradas, no embebidos de forma opaca en componentes de interfaz. Rationale: la interfaz tiene que seguir siendo operable, verificable y reemplazable sin romper el dominio.

### IV. Importaciones Y Cambios Deben Ser Trazables
Toda entrada externa, especialmente Garmin y futuras sincronizaciones, DEBE dejar evidencia suficiente para auditar origen, fecha, errores y efectos sobre el sistema. Las funcionalidades nuevas NO DEBEN introducir escrituras silenciosas ni transformaciones irreversibles sin metadatos o posibilidad de inspeccion. Rationale: la utilidad del sistema depende de poder reconstruir que entro, como se transformo y que decision genero.

### V. Validacion Cercana Al Cambio
Cada cambio DEBE validarse en el slice tocado con la comprobacion mas cercana disponible: tests backend, verificacion de importaciones, build frontend, consultas SQLite o scripts de salud. No se aceptan cambios que alteren datos, contratos o flujos operativos sin una forma concreta de falsar la implementacion. Rationale: este repositorio mezcla codigo, datos y vistas; las regresiones locales deben detectarse antes de expandir el alcance.

## Technical Constraints

- El stack actual se asume local-first: SQLite como almacenamiento principal, backend Python/FastAPI para operaciones y frontend React/Vite para la GUI.
- Las carpetas anuales contienen contexto operativo y datos de temporada; la infraestructura comun y el modelo relacional viven en raiz.
- La aplicacion debe seguir siendo operable en entorno local de una sola maquina antes de considerar despliegues mas amplios.
- Los cambios sobre datos historicos, seeds, importaciones o backups deben ser conservadores y evitar perdida accidental de trazabilidad.
- Las integraciones con agentes deben exponerse como acciones o flujos definidos, no como acoplamientos implicitos entre UI y automatizacion.

## Workflow And Quality Gates

- Toda iniciativa no trivial debe pasar por `spec`, `plan` y `tasks` antes de implementacion amplia.
- Las features deben describir explicitamente impacto en alguna de estas capas cuando aplique: `Sistema/`, temporada (`2026/`, `2027/`), `GUI/`, `Agentes/`, importaciones externas.
- Si una tarea toca contratos de importacion, esquema SQLite, o decisiones de planificacion, debe documentar supuestos y riesgos en los artefactos de Spec Kit.
- Antes de cerrar una implementacion, debe comprobarse al menos una validacion ejecutable relevante y anotarse cualquier limite restante.
- La simplicidad prevalece: evitar capas, tablas, endpoints o abstracciones nuevas sin necesidad operativa clara en este sistema.

## Governance

Esta constitucion prevalece sobre instrucciones locales de feature cuando haya conflicto de criterios arquitectonicos o de calidad. Toda enmienda DEBE actualizar este documento junto con la motivacion del cambio y su impacto esperado en el flujo de trabajo.

La politica de versionado de esta constitucion DEBE seguir semver:
- MAJOR cuando se eliminen principios, se relajen garantias o se redefinan reglas de forma incompatible.
- MINOR cuando se anadan principios, secciones o puertas de calidad nuevas.
- PATCH cuando solo haya aclaraciones, redaccion o mejoras no semanticas.

La revision de cumplimiento DEBE ocurrir en spec, plan, tasks e implementacion. Cada revision DEBE verificar: fuente primaria afectada, estrategia de sincronizacion markdown si aplica, separacion GUI/dominio si aplica, trazabilidad de importaciones si aplica y validacion ejecutable asociada. El contexto operativo base para estas revisiones es `README.md`, `Sistema/README.md` y `GUI/README.md`.

**Version**: 1.0.0 | **Ratified**: 2026-05-14 | **Last Amended**: 2026-05-14
