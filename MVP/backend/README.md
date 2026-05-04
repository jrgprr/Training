# Backend

Backend FastAPI del MVP de entrenamiento.

## Arranque local

1. Crear entorno virtual.
2. Instalar dependencias con `pip install -e .[dev]`.
3. Configurar variables de entorno con `.env` si hace falta.
4. Arrancar con `uvicorn app.main:app --reload`.

## Variables principales

- `APP_NAME`
- `APP_ENV`
- `API_V1_PREFIX`
- `DATABASE_URL`
