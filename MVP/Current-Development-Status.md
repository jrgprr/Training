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
- FastAPI skeleton exists and is running
- routing exists and is functional
- minimal response schemas exist
- services connected to database via repository layer
- SQLAlchemy ORM models fully implemented for all tables
- Alembic migration created and applied
- SQLite database configured for development
- repository layer implemented with base repository class
- business services connected to database (profile, week, dashboard)
- import pipeline not implemented yet
- metrics logic not implemented yet

### 5.3 Known backend issue

No known backend issues. All dependencies are installed and the backend runs successfully on http://localhost:8000.

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
- Vite + React + TypeScript setup complete
- package.json and dependencies installed
- development server running on http://localhost:5173/
- basic React app with hot reload working
- no custom pages or components yet

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
- Python environment setup (pyenv + Python 3.12.13)
- backend dependencies installed
- full SQLAlchemy ORM models
- initial Alembic migration
- repository layer implementation
- services connected to database
- frontend folder structure
- frontend Vite + React + TypeScript bootstrap

### Not complete yet

- import pipeline from Garmin files
- metrics calculations
- dashboard aggregation endpoints
- custom frontend pages and components
- data flow between frontend and backend
- user interface screens (dashboard, daily log, weekly review)

---

## 9. Recommended next steps in the fresh session

Recommended order:

1. ✅ Configure Python environment for `MVP/backend`. - COMPLETED
2. ✅ Install backend dependencies from `backend/pyproject.toml`. - COMPLETED
3. ✅ Translate `MVP/schema-postgresql.sql` into SQLAlchemy ORM models. - COMPLETED
4. ✅ Create the first Alembic migration. - COMPLETED
5. ✅ Add a minimal repository layer and connect the existing placeholder services to the database. - COMPLETED
6. ✅ Bootstrap the frontend with Vite + React + TypeScript. - COMPLETED
7. ✅ Create the first frontend screens:
   - today dashboard - COMPLETED
   - daily log - COMPLETED (placeholder)
   - weekly review - COMPLETED
8. Implement import flow for files as the first ingestion path.

---

## 10. Best first technical task to resume with

If resuming in a fresh chat, the best first prompt is effectively:

> Implement the import flow for Garmin files as the first data ingestion path. The MVP now has a functional UI connected to the backend.

Reason:
- the core UI screens are complete and functional,
- the backend API is ready for data ingestion,
- implementing file import will make the MVP capable of actual data processing.

---

## 11. Notes for the next assistant session

Important context to preserve:
- this is a personal training MVP, not a generic fitness app
- the core workflow is plan -> execute -> auto/manual register -> weekly review -> adjust next week
- weight trend must remain separate from aerobic index
- indoor substitutions due to weather are an explicit first-class concept
- Garmin devices are central to automated ingestion
- the backend is fully functional with SQLite database and connected services
- the frontend has core screens implemented with React Router and API integration
- both servers are currently running (backend on :8000, frontend on :5173)
- next priority is implementing file import for Garmin data ingestion

---

## 12. Current running state

As of the last update, both development servers are running:
- **Backend**: http://localhost:8000 (FastAPI with SQLite database)
- **Frontend**: http://localhost:5173 (Vite + React + TypeScript)

The MVP foundation is complete and ready for UI development.
