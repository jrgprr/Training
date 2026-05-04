# Current Development Status

## 1. Purpose of this file

This file is a handoff summary for continuing the MVP work in a fresh chat session or on a different machine.

It describes:
- what has already been defined,
- what has already been created in the workspace,
- what is still incomplete,
- known environment issues,
- and the most logical next steps.

---

## 2. Workspace status

Current relevant folders under the workspace root:
- `2026/`
- `Principios/`
- `MVP/`

The MVP has been moved into its own folder:
- `MVP/`

Current MVP files present:
- `MVP/MVP-Arquitectura.md`
- `MVP/schema-postgresql.sql`
- `MVP/API-Minima.md`
- `MVP/Stack-Tecnico.md`
- `MVP/backend/` with initial FastAPI skeleton
- `MVP/frontend/` with directory structure only
- `MVP/docs/` exists but is currently empty

---

## 3. Functional definition already completed

The training system itself has already been documented outside the MVP codebase:
- general principles in `Principios/Principios.md`
- 2026 planning in `2026/`
- weekly operational planning and logging structure inside `2026/Bloques/`

Important system concepts already defined:
- annual, block and weekly planning
- daily execution and logging
- aerobic index as a derived metric
- weight trend as a separate derived metric
- indoor substitution logic for bad weather
- use of Garmin devices plus spinning bike and treadmill

---

## 4. MVP documentation already completed

### 4.1 Architecture document

File:
- `MVP/MVP-Arquitectura.md`

Status:
- detailed and usable

What it already contains:
- daily, weekly and historical workflow
- functional layers of the MVP
- detailed relational database design
- service breakdown
- automated vs manual data capture logic
- weekly analysis requirements
- frontend requirements
- recommended implementation order

### 4.2 Database design

File:
- `MVP/schema-postgresql.sql`

Status:
- created
- syntactically accepted by editor validation
- intended for PostgreSQL

What it includes:
- profile and goals tables
- devices and import tracking tables
- planning tables
- daily check-in and body measurement tables
- training session tables
- weekly review and metrics tables
- indexes

This is currently the main concrete technical artifact.

### 4.3 API design

File:
- `MVP/API-Minima.md`

Status:
- created
- documents MVP REST API surface

What it includes:
- profile endpoints
- planning endpoints
- daily log endpoints
- training session endpoints
- import endpoints
- analytics and dashboard endpoints
- example payloads and example responses

### 4.4 Technical stack proposal

File:
- `MVP/Stack-Tecnico.md`

Status:
- created

Current recommended stack:
- PostgreSQL
- FastAPI
- SQLAlchemy 2.x
- Alembic
- APScheduler
- React
- TypeScript
- Vite
- TanStack Query
- Recharts

---

## 5. Backend implementation status

Backend root:
- `MVP/backend/`

### 5.1 Created backend files

Already created:
- `backend/pyproject.toml`
- `backend/README.md`
- `backend/.env.example`
- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/db/session.py`
- `backend/app/db/base.py`
- `backend/app/models/base.py`
- `backend/app/models/base_models.py`
- `backend/app/api/router.py`
- `backend/app/api/v1/router.py`
- `backend/app/api/v1/health.py`
- `backend/app/api/v1/profile.py`
- `backend/app/api/v1/weeks.py`
- `backend/app/api/v1/dashboard.py`
- `backend/app/schemas/health.py`
- `backend/app/schemas/profile.py`
- `backend/app/schemas/week.py`
- `backend/app/schemas/dashboard.py`
- `backend/app/services/health_service.py`
- `backend/app/services/profile_service.py`
- `backend/app/services/week_service.py`
- `backend/app/services/dashboard_service.py`
- `backend/app/tests/test_health.py`

### 5.2 Backend status summary

Current state:
- FastAPI skeleton exists
- routing exists
- minimal response schemas exist
- placeholder services exist
- SQLAlchemy base exists
- only a minimal sample model file exists
- Alembic bootstrap file exists
- no actual migration file exists yet
- the full SQL schema has not yet been translated into ORM models
- repositories are not implemented
- business services are mostly placeholders
- import pipeline is not implemented
- metrics logic is not implemented

### 5.3 Known backend issue

The editor currently reports unresolved import for `fastapi` in:
- `MVP/backend/app/api/v1/router.py`

This is not a code design issue.
It is an environment issue: backend dependencies are not installed in the current Python environment.

Reason:
- a Python environment configuration step was attempted,
- but the environment configuration tool call was cancelled by the user before completion.

Implication:
- the backend skeleton is present,
- but the machine does not yet have the backend environment set up and dependencies installed.

---

## 6. Frontend implementation status

Frontend root:
- `MVP/frontend/`

### 6.1 Created frontend structure

Folders already created:
- `frontend/public/`
- `frontend/src/app/`
- `frontend/src/pages/`
- `frontend/src/components/`
- `frontend/src/features/dashboard/`
- `frontend/src/features/plan/`
- `frontend/src/features/daily-log/`
- `frontend/src/features/weekly-review/`
- `frontend/src/features/imports/`
- `frontend/src/features/metrics/`
- `frontend/src/hooks/`
- `frontend/src/services/`
- `frontend/src/types/`
- `frontend/src/utils/`

### 6.2 Frontend status summary

Current state:
- folder structure exists
- no frontend files have been created yet
- no `package.json`
- no Vite config
- no React app entrypoints
- no pages or components yet

So the frontend is only scaffolded at directory level, not yet bootstrapped.

---

## 7. Documentation consistency status

The MVP docs are internally linked and usable.

Files currently linked together:
- `MVP/MVP-Arquitectura.md`
- `MVP/schema-postgresql.sql`
- `MVP/API-Minima.md`
- `MVP/Stack-Tecnico.md`

Also, references from higher-level docs were updated after the MVP was moved into its own folder.

---

## 8. What is complete vs incomplete

### Complete enough to continue

- functional MVP concept
- architecture document
- relational database design
- PostgreSQL SQL schema draft
- API design draft
- stack decision draft
- backend folder structure
- backend FastAPI base skeleton
- frontend folder structure

### Not complete yet

- Python environment setup
- dependency installation
- ORM models for full schema
- Alembic initial migration
- repository layer
- actual services using database access
- import pipeline from Garmin files
- metrics calculations
- dashboard aggregation endpoints
- frontend app bootstrap
- frontend pages and forms
- data flow between frontend and backend

---

## 9. Recommended next steps in the fresh session

Recommended order:

1. Configure Python environment for `MVP/backend`.
2. Install backend dependencies from `backend/pyproject.toml`.
3. Translate `MVP/schema-postgresql.sql` into SQLAlchemy ORM models.
4. Create the first Alembic migration.
5. Add a minimal repository layer and connect the existing placeholder services to the database.
6. Bootstrap the frontend with Vite + React + TypeScript.
7. Create the first frontend screens:
   - today dashboard
   - daily log
   - weekly review
8. Implement import flow for files as the first ingestion path.

---

## 10. Best first technical task to resume with

If resuming in a fresh chat, the best first prompt is effectively:

> Set up the backend environment for `MVP/backend`, install dependencies, convert the SQL schema into SQLAlchemy models, and create the initial Alembic migration.

Reason:
- the backend skeleton already exists,
- the database design is the most concrete technical asset already produced,
- and the rest of the implementation depends on stabilizing the data model first.

---

## 11. Notes for the next assistant session

Important context to preserve:
- this is a personal training MVP, not a generic fitness app
- the core workflow is plan -> execute -> auto/manual register -> weekly review -> adjust next week
- weight trend must remain separate from aerobic index
- indoor substitutions due to weather are an explicit first-class concept
- Garmin devices are central to automated ingestion
- the current backend code is a skeleton only, not a connected application yet
- the frontend has not been bootstrapped yet
- environment setup was interrupted, so unresolved imports are currently expected
