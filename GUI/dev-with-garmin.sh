#!/usr/bin/env bash

set -euo pipefail

GUI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$GUI_DIR/.." && pwd)"
ENV_FILE="${1:-$GUI_DIR/.env.garmin.local}"
DEFAULT_TOKENSTORE_PATH="$GUI_DIR/.garminconnect"
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  echo "Usando variables Garmin desde $ENV_FILE"
else
  echo "No se encontro $ENV_FILE; se usaran las variables ya exportadas en el shell."
fi

export GARMIN_CONNECT_SESSION_PATH="${GARMIN_CONNECT_SESSION_PATH:-$DEFAULT_TOKENSTORE_PATH}"
mkdir -p "$GARMIN_CONNECT_SESSION_PATH"

TOKENSTORE_READY=false
if [[ -d "$GARMIN_CONNECT_SESSION_PATH" ]] && find "$GARMIN_CONNECT_SESSION_PATH" -mindepth 1 -print -quit | grep -q .; then
  TOKENSTORE_READY=true
fi

if [[ "$TOKENSTORE_READY" != "true" ]] && ([[ -z "${GARMIN_CONNECT_USERNAME:-}" ]] || [[ -z "${GARMIN_CONNECT_PASSWORD:-}" ]]); then
  echo "Falta configuracion Garmin. Define GARMIN_CONNECT_SESSION_PATH o GARMIN_CONNECT_USERNAME y GARMIN_CONNECT_PASSWORD." >&2
  echo "Puedes copiar GUI/.env.garmin.local.example a GUI/.env.garmin.local y rellenarlo." >&2
  exit 1
fi

if [[ ! -x "$ROOT_DIR/.venv/bin/python" ]]; then
  echo "No existe el entorno Python esperado en $ROOT_DIR/.venv" >&2
  exit 1
fi

echo "Tokenstore Garmin: $GARMIN_CONNECT_SESSION_PATH"

(
  cd "$GUI_DIR/backend"
  source "$ROOT_DIR/.venv/bin/activate"
  exec uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
) &
BACKEND_PID=$!

(
  cd "$GUI_DIR/frontend"
  exec npm run dev -- --host 127.0.0.1 --port 5173
) &
FRONTEND_PID=$!

echo "Backend:  http://127.0.0.1:8000"
echo "Frontend: http://127.0.0.1:5173"
echo "Pulsa Ctrl+C para detener ambos procesos."

while true; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    wait "$BACKEND_PID" 2>/dev/null || true
    break
  fi

  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    wait "$FRONTEND_PID" 2>/dev/null || true
    break
  fi

  sleep 1
done
