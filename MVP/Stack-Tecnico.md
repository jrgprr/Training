# Stack tecnico propuesto

## 1. Objetivo

Elegir un stack tecnico razonable para construir el MVP con rapidez, mantenerlo sencillo y permitir crecer sin rehacer todo en pocos meses.

---

## 2. Criterios de eleccion

El stack debe favorecer:
- desarrollo rapido,
- buen soporte para datos relacionales,
- facilidad para importar archivos y programar tareas,
- front-end web simple y claro,
- y despliegue local o personal sin demasiada friccion.

---

## 3. Propuesta principal

### Base de datos
- PostgreSQL.

Motivo:
- modelo relacional claro,
- buen soporte JSON cuando haga falta,
- consultas semanales y agregaciones fiables,
- y mejor recorrido que SQLite si el sistema crece.

### Backend
- Python 3.12
- FastAPI
- SQLAlchemy 2.x
- Alembic
- Pydantic

Motivo:
- Python encaja bien con procesos de importacion y analisis,
- FastAPI permite montar una API limpia y documentada rapido,
- SQLAlchemy y Alembic facilitan evolucionar el esquema,
- y Pydantic encaja bien con validacion de payloads y modelos.

### Tareas en segundo plano
- APScheduler al principio.
- Celery o RQ solo si aparece necesidad real de colas mas serias.

Motivo:
- para un MVP personal, una capa ligera de tareas programadas suele bastar.

### Front-end
- React
- TypeScript
- Vite
- TanStack Query
- React Router
- un sistema de UI ligero como shadcn/ui o componentes propios simples.

Motivo:
- buena velocidad de desarrollo,
- tipado claro,
- consumo de API comodo,
- y facilidad para montar dashboards y formularios cortos.

### Graficos
- Recharts o ECharts.

Motivo:
- suficiente para tendencias de peso, carga, adherencia y revision semanal.

### Autenticacion
- si el sistema es estrictamente personal al inicio, autenticacion simple local.
- si luego quieres acceso remoto serio, tokens JWT con FastAPI.

---

## 4. Alternativa mas compacta

Si quieres reducir complejidad inicial al maximo:
- PostgreSQL
- Python
- FastAPI
- Jinja o HTMX en vez de React

Ventaja:
- menos piezas.

Inconveniente:
- menos flexible para dashboards ricos y evolucion futura.

Para este caso, la opcion con React sigue pareciendo la mejor si ya asumes front-end dedicado.

---

## 5. Estructura de proyecto recomendada

```text
MVP/
  backend/
    app/
      api/
      core/
      db/
      models/
      schemas/
      services/
      repositories/
      jobs/
      analytics/
      imports/
      tests/
    alembic/
    pyproject.toml
  frontend/
    src/
      app/
      pages/
      components/
      features/
      hooks/
      services/
      types/
      utils/
    package.json
  docs/
    MVP-Arquitectura.md
    API-Minima.md
    Stack-Tecnico.md
    schema-postgresql.sql
```

---

## 6. Responsabilidad de carpetas

### Backend `app/api`
- routers y endpoints.

### Backend `app/models`
- modelos ORM.

### Backend `app/schemas`
- contratos de entrada y salida.

### Backend `app/services`
- logica de negocio.

### Backend `app/repositories`
- acceso a datos.

### Backend `app/imports`
- lectura, parseo y normalizacion de archivos de Garmin y otras fuentes.

### Backend `app/analytics`
- calculo de indice aerobico, tendencia de peso y resumentes semanales.

### Backend `app/jobs`
- tareas programadas de importacion, consolidacion y recalculo.

### Frontend `src/features`
- modulos por dominio: dashboard, plan, daily-log, weekly-review, imports, metrics.

---

## 7. Servicios backend iniciales

Backend minimo recomendado:
- `profile_service`
- `planning_service`
- `daily_log_service`
- `training_session_service`
- `import_service`
- `metrics_service`
- `weekly_review_service`

Esto permite que la API no meta toda la logica en los endpoints.

---

## 8. Pantallas front-end iniciales

1. Dashboard de hoy.
2. Registro del dia.
3. Semana actual.
4. Revision semanal.
5. Tendencias.
6. Importaciones.
7. Configuracion de perfil y dispositivos.

---

## 9. Despliegue recomendado

### Fase inicial local
- backend y frontend en local,
- PostgreSQL local,
- importacion manual de archivos,
- y tareas programadas locales.

### Fase siguiente
- despliegue en un VPS o servicio cloud sencillo,
- PostgreSQL persistente,
- almacenamiento de archivos importados,
- y backups periodicos.

---

## 10. Decision recomendada

Para este proyecto, la recomendacion mas equilibrada es:
- PostgreSQL
- FastAPI
- SQLAlchemy
- Alembic
- APScheduler
- React
- TypeScript
- Vite
- TanStack Query
- Recharts

Es suficientemente ligera para un MVP serio y suficientemente solida para crecer a medio plazo.
