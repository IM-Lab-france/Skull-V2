#!/usr/bin/env bash
set -euo pipefail

# Local/Linux candidate launcher. Production systemd is not changed by this task.
APP_DIR=$(dirname "$(readlink -f "$0")")
cd "$APP_DIR"

VENV_DIR="${SKULL_VENV_DIR:-.venv}"
GUNICORN_BIN="$VENV_DIR/bin/gunicorn"
if [[ ! -x "$GUNICORN_BIN" ]]; then
  echo "Gunicorn introuvable dans $GUNICORN_BIN" >&2
  echo "Installez requirements.lock dans le venv avant de lancer la candidate." >&2
  exit 78
fi

export SKULL_HARDWARE_MODE="${SKULL_HARDWARE_MODE:-production}"
exec "$GUNICORN_BIN" \
  --config "$APP_DIR/gunicorn.conf.py" \
  wsgi_entry:app
