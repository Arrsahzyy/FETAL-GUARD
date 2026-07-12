#!/usr/bin/env bash
set -euo pipefail

python -m alembic upgrade head
exec python -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
