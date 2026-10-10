#!/usr/bin/env bash
# Применяет Alembic-миграции к Postgres из docker-compose.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose run --rm migrations
echo "✅ Миграции применены"
