# Arquitectura GUI

Esta carpeta define la capa de interfaz de usuario del sistema completo de entrenamiento.

La GUI no sustituye a la base relacional ni a los agentes. Su funcion es ofrecer una forma humana, rapida y operativa de:
- consultar la planificacion,
- ver la ejecucion real,
- revisar analisis y ajustes,
- lanzar tareas de importacion o sincronizacion,
- y tomar decisiones sobre el plan.

## 1. Papel de la GUI dentro del sistema

La GUI es la interfaz principal para el usuario humano.

Su papel correcto es:
- leer el estado del sistema desde SQLite,
- mostrar informacion sintetica y navegable,
- permitir acciones controladas,
- y delegar logica compleja en agentes o servicios del sistema.

La GUI no deberia contener la logica deportiva principal. Esa logica debe vivir en agentes y en la capa estructurada del sistema.

## 2. Lugar de la GUI en la arquitectura general

Relaciones principales:
- `Sistema/`: fuente primaria de verdad.
- `Agentes/`: capa de automatizacion y analisis.
- `GUI/`: interfaz para navegar, revisar y operar el sistema.
- `Bloques/`, `Macro.md`, `Ficha-usuario.md`: vistas humanas narrativas complementarias.

La GUI deberia poder mostrar tanto datos estructurados como vistas markdown renderizadas cuando aporten contexto.

## 3. Modulos principales de la GUI

### 1. Dashboard general

Debe mostrar:
- bloque actual,
- semana actual,
- estado de cumplimiento,
- carga reciente,
- metricas fisiologicas clave,
- alertas de prudencia,
- y decisiones pendientes.

Es la portada operativa del sistema.

### 2. Planificacion

Debe permitir navegar:
- temporada,
- macro,
- bloques meso,
- semanas micro,
- sesiones planificadas.

Debe mostrar tanto la estructura del plan como los criterios narrativos asociados.

### 3. Registro diario

Debe permitir ver y editar:
- actividades realizadas,
- metricas fisiologicas diarias,
- revisiones diarias,
- y notas operativas derivadas del flujo real.

En la instancia actual, la escritura manual queda deshabilitada para conservar un dataset Garmin-only.

### 4. Analisis

Debe mostrar:
- comparacion plan vs realidad,
- tendencias de carga,
- tendencias de peso y recuperacion,
- cumplimiento por semana y bloque,
- patrones detectados por agentes.

Este modulo es donde el sistema empieza a aportar valor real mas alla de almacenar datos.

### 5. Ajustes del plan

Debe permitir:
- ver recomendaciones generadas por agentes,
- aceptar, rechazar o modificar ajustes,
- y registrar la decision final con trazabilidad.

Esto es importante: la GUI no solo muestra, tambien gobierna el cambio del plan.

### 6. Importaciones y sincronizacion

Debe permitir:
- lanzar importaciones desde Garmin,
- ver estado de sincronizacion,
- revisar errores,
- repetir una importacion,
- y consultar trazabilidad.

### 7. Auditoria y salud del sistema

Debe mostrar:
- inconsistencias detectadas,
- markdown desactualizado respecto a SQLite,
- sesiones sin enlace plan-real,
- metricas faltantes,
- y errores de agentes o importaciones.

## 4. Interfaz con agentes

La GUI no deberia llamar logica interna compleja directamente. Deberia hacerlo a traves de acciones bien definidas.

Ejemplos de acciones:
- `importar_desde_garmin`
- `analizar_semana_actual`
- `proponer_ajuste_bloque`
- `renderizar_markdown`
- `auditar_consistencia`

Cada accion deberia:
- dejar trazabilidad,
- devolver estado,
- mostrar resultado al usuario,
- y permitir revisar errores.

## 5. Tipos de interfaz recomendados

Hay tres alternativas razonables:

### Opcion A. Web app local

Ventajas:
- muy flexible,
- buena para dashboards y tablas,
- mas facil de hacer crecer,
- buena base para futuros agentes y APIs.

Inconvenientes:
- requiere una pequena capa de backend o servicio local.

### Opcion B. App de escritorio

Ventajas:
- acceso directo a SQLite,
- buena experiencia local,
- mas sencilla si todo va a vivir en una sola maquina.

Inconvenientes:
- normalmente menos flexible para evolucionar a integraciones futuras.

### Opcion C. GUI ligera dentro de VS Code

Ventajas:
- muy alineada con el entorno actual,
- podria apoyarse en markdown, notebooks y scripts.

Inconvenientes:
- menos natural para convertirse en una interfaz general de producto.

## 6. Recomendacion arquitectonica

La opcion mas solida para este sistema es una web app local.

Motivos:
- separa bien interfaz y logica,
- convive bien con SQLite,
- permite dashboards, filtros y graficas,
- facilita una evolucion futura hacia API o MCP,
- y encaja bien con agentes como servicios del sistema.

## 7. Arquitectura minima recomendada

### Frontend
- interfaz web local para navegacion, tablas, formularios y dashboards.

### Backend de aplicacion
- capa fina que consulta SQLite,
- ejecuta acciones de agentes,
- y expone endpoints internos para la GUI.

### SQLite
- fuente primaria.

### Agentes
- servicios especializados invocados por el backend segun la accion del usuario.

## 8. MVP recomendado para la GUI

Para no abrir demasiado frente a la vez, el MVP de GUI deberia cubrir solo cuatro vistas:

1. Dashboard semanal
2. Navegacion de planificacion
3. Registro diario
4. Importaciones Garmin

Con eso ya se puede operar el sistema de forma real.

## 9. Segunda fase recomendada

Despues del MVP, anadir:
- analisis plan vs realidad,
- recomendaciones de ajuste,
- auditoria del sistema,
- y renderizado/sincronizacion Markdown.

## Arranque local con Garmin

Para levantar la GUI local con backend y frontend a la vez, y dejar disponible la importacion Garmin, usa:

```bash
cp GUI/.env.garmin.local.example GUI/.env.garmin.local
# editar GUI/.env.garmin.local con tus credenciales o session path
bash GUI/dev-with-garmin.sh
```

Detalles operativos:
- el script arranca FastAPI en `http://127.0.0.1:8000`,
- arranca Vite en `http://127.0.0.1:5173`,
- carga variables desde `GUI/.env.garmin.local` si existe,
- usa `GUI/.garminconnect` como tokenstore persistente por defecto,
- y falla rapido si no encuentra configuracion Garmin suficiente.

La GUI ya muestra un error explicito cuando `preview` o `run` fallan por falta de `GARMIN_CONNECT_*`.
Tambien muestra en la tarjeta Garmin si el backend esta configurado o no antes de lanzar la importacion.
El flujo de `V0.3` ya queda respaldado por el mismo pipeline disponible tambien por CLI en `GUI/backend`.

## 10. Regla de gobierno

La GUI puede disparar cambios, pero no deberia escribir en el sistema de forma opaca.

Todo cambio relevante deberia quedar registrado con:
- actor,
- fecha,
- accion,
- entidad afectada,
- y motivo.

Sin eso, la interfaz seria util, pero el sistema dejaria de ser auditable.

## 11. Estado actual V0.2

Implementacion ya creada en esta carpeta:
- `backend/`: API minima FastAPI de solo lectura sobre `Sistema/training.sqlite`.
- `frontend/`: interfaz React + TypeScript + Vite para navegar temporadas, bloques, semanas y sesiones.

Endpoints disponibles en el backend actual:
- `GET /api/health`
- `GET /api/seasons`
- `GET /api/seasons/{season_id}/blocks`
- `GET /api/blocks/{block_id}/weeks`
- `GET /api/weeks/{week_id}/sessions`
- `GET /api/weeks/{week_id}/plan-vs-real`

Flujo minimo ya cubierto:
- seleccionar temporada,
- ver bloques de la temporada,
- ver semanas del bloque,
- ver sesiones planificadas de la semana,
- revisar la comparativa `plan vs realidad`,
- revisar actividades reales importadas desde Garmin,
- y lanzar importaciones o reimportaciones Garmin desde la propia GUI.

Pendiente para completar la vision original de `V0.2`:
- dashboard semanal consolidado,
- endurecer mas el modo Garmin-only a nivel de experiencia y permisos,
- y validacion visual completa del flujo con Node disponible.

## Estado actual del entorno

La instancia de trabajo actual queda en modo Garmin-only:
- las actividades y metricas reales nuevas deben entrar por Garmin Connect,
- el alta manual desde GUI queda deshabilitada,
- y el historico activo se ha saneado para eliminar capturas manuales y residuos sinteticos.