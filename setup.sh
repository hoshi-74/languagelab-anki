#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON=${PYTHON:-}

if [ -z "$PYTHON" ]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON=$(command -v python3)
  elif command -v python >/dev/null 2>&1; then
    PYTHON=$(command -v python)
  else
    echo "Python 3.10+ was not found." >&2
    exit 1
  fi
fi

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  "$PYTHON" -m venv "$ROOT/.venv"
fi

"$ROOT/.venv/bin/python" -m pip install --disable-pip-version-check -r "$ROOT/requirements.txt"
"$ROOT/.venv/bin/python" -m languagelab.cli self-check
