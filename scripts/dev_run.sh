#!/usr/bin/env bash
set -euo pipefail
export PYTHONUNBUFFERED=1
poetry run python -m src.server
