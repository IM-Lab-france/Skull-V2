#!/usr/bin/env bash
set -euo pipefail

# Simple launcher for "public_interface"
# - Creates Python venv if missing
# - Upgrades pip tooling
# - Installs 'requests'
# - Creates a logs directory
# - Runs public_interface (file or module)

APP_DIR=$(dirname "$(readlink -f "$0")")
cd "$APP_DIR"

if [ ! -d .venv_public ]; then
  echo "==> Creating virtualenv"
  python3 -m venv .venv_public
fi

# shellcheck disable=SC1091
source .venv_public/bin/activate

# Upgrade basics
python -m pip install --upgrade pip setuptools wheel

# Install required dependency
echo "==> Installing requests"
python -m pip install requests flask websocket

# Create logs directory if missing
if [ ! -d logs ]; then
  echo "==> Creating logs directory"
  mkdir -p logs
  echo "Logs directory created at: $(pwd)/logs"
fi

echo "==> Setup complete!"
echo "    - Log files: $(pwd)/logs/"

# Launch app:
# Priority 1: a local script file public_interface.py
# Fallback: run as a module `python -m public_interface`
if [ -f "public_interface.py" ]; then
  echo "==> Launching: python public_interface.py"
  exec python public_interface.py
else
  echo "==> public_interface.py not found, trying: python -m public_interface"
  exec python -m public_interface
fi
