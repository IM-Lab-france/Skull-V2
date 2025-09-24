#!/usr/bin/env bash
set -euo pipefail

# Simple launcher for Servo Sync Player on Raspberry Pi
# - Creates Python venv if missing
# - Installs dependencies from requirements.txt
# - Runs web_app.py directly (no systemd)
# - Creates logs directory for servo monitoring

APP_DIR=$(dirname "$(readlink -f "$0")")
cd "$APP_DIR"

if [ ! -d .venv ]; then
  echo "==> Creating virtualenv"
  python3 -m venv .venv
fi

source .venv/bin/activate

# Upgrade basics
pip install --upgrade pip setuptools wheel

# Install requirements
if [ -f requirements.txt ]; then
  echo "==> Installing requirements.txt"
  pip install -r requirements.txt
fi

# Ensure Blinka is available for PCA9685
pip install adafruit-blinka

# Create logs directory if missing
if [ ! -d logs ]; then
  echo "==> Creating logs directory"
  mkdir -p logs
  echo "Logs directory created at: $(pwd)/logs"
fi

echo "==> Setup complete!"
echo "    - Main interface: http://localhost:5000"
echo "    - Logs viewer: http://localhost:5000/static/logs.html"
echo "    - Log files: $(pwd)/logs/"

# Launch app
exec python web_app.py