#!/usr/bin/env bash
set -euo pipefail

# Launcher for playlist_web.py
# - Creates a dedicated virtual environment
# - Installs dependencies from requirements_playlist.txt
# - Runs the standalone playlist web interface

APP_DIR=$(dirname "$(readlink -f "$0")")
cd "$APP_DIR"

VENV_DIR=".venv_playlist"
REQ_FILE="requirements_playlist.txt"

if [ ! -d "$VENV_DIR" ]; then
  echo "==> Creating virtualenv at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

pip install --upgrade pip setuptools wheel

if [ -f "$REQ_FILE" ]; then
  echo "==> Installing dependencies from $REQ_FILE"
  pip install -r "$REQ_FILE"
else
  echo "WARNING: $REQ_FILE not found; installing Flask explicitly"
  pip install Flask
fi

echo "==> Environment ready"
echo "    - Playlist interface: http://localhost:5050"
echo "    - Backend cible: http://192.168.1.116:5000"

# Fixe l’URL du backend
export PLAYLIST_BACKEND_BASE="http://192.168.1.116:5000"

echo "==> Starting playlist_web.py"
exec python playlist_web.py
