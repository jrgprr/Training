# Roadmap del sistema

Este documento define la hoja de ruta del sistema completo de entrenamiento.

El objetivo del roadmap no es enumerar ideas, sino fijar versiones intermedias que permitan:
- construir el sistema por capas,
- validar cada bloque funcional antes de abrir el siguiente,
- y reducir el riesgo tecnico y de producto.

## 1. Principio de ejecucion

Cada version debe cerrar tres cosas:
- una capacidad funcional clara,
- una validacion tecnica concreta,
- y una validacion de uso real.

Eso significa que no se deberia avanzar de version solo porque el codigo existe. Hay que comprobar que el sistema ya sirve para operar una parte real del flujo.

Ademas, desde fases tempranas conviene disponer de una validacion visual minima. Aunque la GUI completa llegue mas tarde, el roadmap debe incluir una GUI de lectura suficiente para inspeccionar la base y comprobar que el sistema realmente contiene lo que creemos que contiene.

## 2. Estado actual

Lo que ya esta definido o iniciado:
- modelo de planificacion macro, meso y micro,
- bloques y semanas iniciales de 2026,
- base SQLite unica plurianual en raiz como fuente primaria,
- infraestructura general del sistema separada del contenido anual,
- semilla inicial de 2026 cargable desde `Sistema/Seeds/2026.sql`,
- arquitectura de agentes,
- arquitectura GUI,
- y separacion entre planificacion, ejecucion e importaciones.

Lo que ya no forma parte del objetivo:
- una base SQLite separada dentro de cada carpeta anual.

Decisiones arquitectonicas ya consolidadas:
- `Sistema/` en raiz contiene esquema, vistas, semillas y la base unica.
- las carpetas anuales como `2026/` contienen contexto, vistas humanas e importaciones/exportaciones propias del ano.
- SQLite es la fuente de verdad; markdown es una vista humana.

## 3. Roadmap por versiones

### V0.1 - Fundacion del modelo

Objetivo:
- dejar cerrada la arquitectura conceptual y el modelo de datos inicial.

Incluye:
- estructura del workspace,
- definicion de temporadas,
- modelo macro/meso/micro,
- SQLite unica plurianual como fuente primaria,
- separacion entre infraestructura general en raiz y contenido anual,
- markdown como vistas humanas,
- definicion inicial de agentes y GUI.

Validacion tecnica:
- esquema SQLite creado,
- base unica inicial generada en `Sistema/training.sqlite`,
- semilla 2026 separada en `Sistema/Seeds/2026.sql`,
- plan 2026 cargado al menos parcialmente.

Validacion de uso:
- se puede leer el plan y entender la arquitectura completa sin ambiguedades.

Estado:
- completada a nivel arquitectonico base.

### V0.2 - Plan operativo minimo

Objetivo:
- poder mantener una temporada real operativa aunque no exista todavia automatizacion con Garmin.

Incluye:
- carga estructurada de B1 en la base unica,
- posibilidad de registrar actividades y metricas manualmente,
- enlace basico entre plan y realidad,
- primera revision semanal manual asistida,
- y una GUI minima de solo lectura para visualizar la planificacion cargada en SQLite.

Validacion tecnica:
- tablas `plan_`, `exec_`, `link_` y `review_` utilizables,
- consultas basicas de plan vs realidad funcionando,
- separacion clara entre semilla estructural, datos ejecutados y vistas markdown,
- y una vista visual minima conectada a la base unica.

Validacion de uso:
- se puede cerrar una semana real registrando lo hecho y comparandolo con lo previsto,
- y se puede inspeccionar visualmente la planificacion almacenada sin depender de consultas manuales o de leer SQL.

GUI minima esperada en esta fase:
- vista de temporadas disponibles,
- vista de bloques de una temporada,
- vista de semanas de un bloque,
- y vista de sesiones planificadas de una semana.

### V0.3 - Ingestion externa inicial

Objetivo:
- traer datos reales desde fuentes externas de forma repetible.

Incluye:
- pipeline de importacion inicial,
- staging de importaciones,
- primer importador Garmin en modo manual o semiautomatico,
- trazabilidad de import jobs,
- y carga de datos a la base unica filtrando por temporada.

Validacion tecnica:
- importacion reproducible de actividades reales,
- deduplicacion minima,
- carga correcta en `exec_activities` y `exec_daily_metrics`.

Validacion de uso:
- se puede importar una semana real desde Garmin o desde una exportacion equivalente sin rehacer el proceso a mano.

Estado:
- cerrada sobre Garmin Connect directo con API y CLI minimos validados.

### V0.4 - Analisis basico automatizado

Objetivo:
- empezar a convertir datos en informacion util.

Incluye:
- `Activity Analysis Agent`,
- `Daily Physiology Agent`,
- `Plan-Execution Linking Agent`,
- primeras vistas SQL de resumen,
- primeras alertas basicas de prudencia.

Validacion tecnica:
- una actividad puede clasificarse,
- una sesion planificada puede enlazarse con una actividad real,
- una revision diaria puede generarse a partir de datos reales.

Validacion de uso:
- el sistema ya detecta al menos algunas desviaciones o senales utiles sin interpretacion completamente manual.

### V0.5 - Revision semanal util

Objetivo:
- disponer de una revision semanal que ayude de verdad a decidir.

Incluye:
- `Weekly Review Agent`,
- dashboards o vistas semanales,
- resumen de cumplimiento,
- lectura de tolerancia de carga,
- decision sugerida: mantener, progresar o consolidar,
- apoyado ya en una GUI capaz de mostrar esa revision de forma legible.

Validacion tecnica:
- la revision semanal se puede ejecutar de forma repetible sobre una semana concreta.

Validacion de uso:
- el usuario puede revisar la semana y sacar una decision operativa real sin releer datos dispersos.

### V0.6 - GUI MVP

Objetivo:
- operar el sistema desde una interfaz util para el usuario.

Nota:
- esta version no introduce la primera GUI, sino la primera GUI realmente operativa de uso diario.
- la validacion visual minima ya debe existir desde `V0.2`.

Incluye:
- dashboard semanal,
- navegacion de planificacion,
- registro diario,
- vista de importaciones Garmin.

Validacion tecnica:
- la GUI lee la base unica SQLite,
- puede lanzar acciones controladas,
- y muestra errores y estados de forma clara.

Validacion de uso:
- se puede usar el sistema sin depender de editar archivos manualmente en casi todo el flujo diario.

### V0.7 - Ajuste semiautomatico del plan

Objetivo:
- permitir que el sistema proponga cambios reales sobre el plan.

Incluye:
- `Meso Adjustment Agent`,
- `Plan Authoring Agent`,
- propuesta de ajustes sobre semanas o bloques,
- trazabilidad de decisiones.

Validacion tecnica:
- el sistema puede generar una propuesta de cambio estructurado sobre el plan.

Validacion de uso:
- el usuario puede aceptar, rechazar o modificar una propuesta concreta con criterio claro.

### V0.8 - Sincronizacion base <-> markdown

Objetivo:
- consolidar el markdown como vista humana sincronizada y no como fuente primaria.

Incluye:
- `Markdown Rendering Agent`,
- registro de sincronizacion,
- deteccion de divergencias,
- renderizado de macro, bloques y semanas desde SQLite filtrando por temporada.

Validacion tecnica:
- regeneracion controlada de markdown a partir de la base,
- deteccion de vistas desactualizadas.

Validacion de uso:
- el usuario sigue teniendo documentos legibles sin perder coherencia con la base.

### V0.9 - Garmin directo y orquestacion

Objetivo:
- conectar el sistema con Garmin de forma mas automatizada y consolidar el pipeline completo.

Incluye:
- `Garmin Import Agent` maduro,
- posible MCP Garmin o adaptadores equivalentes,
- `Training System Orchestrator`,
- ejecucion coordinada de flujos.

Validacion tecnica:
- importaciones recurrentes y trazables,
- pipeline completo desde ingreso de datos hasta revision.

Validacion de uso:
- el sistema funciona de punta a punta con minima intervencion manual.

### V1.0 - Sistema operativo completo

Objetivo:
- disponer de un sistema estable, auditable y util para planificar, ejecutar, analizar y ajustar una temporada real.

Incluye:
- planificacion estructurada en una base unica,
- ejecucion importada o registrada,
- analisis y revision,
- ajuste gobernado,
- GUI util,
- sincronizacion markdown,
- auditoria de consistencia.

Validacion tecnica:
- componentes principales integrados,
- trazabilidad completa,
- salud del sistema visible.

Validacion de uso:
- una temporada real puede gestionarse con este sistema sin depender de herramientas paralelas.

## 4. Orden de implementacion recomendado

1. Cerrar `V0.2` con flujo real de semana operativa.
2. Incluir ya en `V0.2` una GUI minima de lectura para validar visualmente el contenido de SQLite.
3. Construir `V0.3` para no depender siempre de carga manual.

Nota operativa actual:
- el entorno activo de validacion se ha consolidado en modo Garmin-only,
- la carga manual desde GUI queda deshabilitada,
- y el dataset operativo conserva solo actividad real Garmin, metricas Garmin y cierres semanales recalculados tras esa limpieza.
4. Construir `V0.4` y `V0.5` antes de la GUI completa.
5. Abrir `V0.6` cuando ya exista suficiente valor operativo para una GUI de uso diario.
6. Pasar despues a ajuste semiautomatico, sincronizacion y Garmin directo.

Precondicion transversal:
- ninguna version futura deberia reintroducir infraestructura general dentro de carpetas anuales.

## 5. Criterio de calidad para pasar de version

No se deberia pasar a la siguiente version si la actual no cumple estas tres condiciones:
- funciona tecnicamente,
- tiene un caso real de uso validado,
- y deja trazabilidad suficiente para auditar lo ocurrido.

## 6. Propuesta inmediata

El siguiente hito mas sensato es abrir `V0.4`.

Base ya cerrada en `V0.3`:
- importacion Garmin Connect desacoplada,
- staging persistente,
- trazabilidad de `meta_import_jobs` tambien en fallo,
- CLI y API minimos equivalentes,
- deduplicacion minima reproducible,
- y validacion real sobre una semana corta hacia `Sistema/training.sqlite`.

Eso deja `V0.4` centrada en convertir datos importados en informacion util:
- clasificacion y lectura basica de actividades,
- primeras vistas resumen,
- enlazado plan-real mas gobernado,
- y primeras alertas o senales operativas.

Artefactos de apoyo inmediatos:
- backlog de cierre en `Roadmap/V0.3-Backlog.md`,
- nota de cierre en `Roadmap/V0.3-Cierre.md`,
- arquitectura Garmin en `Roadmap/V0.3-Garmin-Directo.md`,
- carpeta operativa de artefactos en `2026/Datos/Importaciones/Garmin/`,
- y backend/API en `GUI/backend/README.md`.