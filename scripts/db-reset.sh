#!/usr/bin/env bash
# ОСТОРОЖНО: пересоздаёт БД development-стенда с нуля (только docker volume!).
set -euo pipefail
cd "$(dirname "$0")/.."
read -r -p "Удалить том pgdata и пересоздать БД? [y/N] " ans
[[ "${ans,,}" == "y" ]] || { echo "Отменено"; exit 1; }
docker compose down -v
docker compose up -d db redis
sleep 3
docker compose run --rm migrations
echo "✅ БД пересоздана"
