#!/usr/bin/env sh
# Mezon: starts the server on port 8000 (installs nothing). First run: pip install -r requirements.txt
cd "$(dirname "$0")" || exit 1
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"
