# AI-krasota

Премиальная B2B2C SaaS-платформа для автоматизации бьюти-индустрии.
Полное ТЗ: [docs/PRD.md](docs/PRD.md)

## Tech Stack

| Слой | Технологии |
|---|---|
| Frontend | Next.js 14+ (App Router), React 18, TypeScript, Tailwind CSS, Framer Motion |
| Backend | Python 3.11+, FastAPI, SQLAlchemy, Pydantic |
| Database | PostgreSQL 15+ (multi-tenant через `tenant_id` + Row-Level Security) |
| Cache / Queue | Redis 7+, Celery |
| AI | Timeweb API (dashscope/qwen3.5-flash) |
| Infrastructure | Docker, Docker Compose, Nginx (маршрутизация субдоменов) |

## Структура монорепозитория

```
.
├── apps/
│   ├── web/          # Next.js 14 (App Router): лендинг, кабинет мастера, сайт салона (PWA)
│   ├── api/          # FastAPI: REST API, аутентификация, multi-tenant логика
│   └── worker/       # Celery: фоновые задачи (напоминания, боты, AI, уведомления)
├── packages/
│   └── ui/           # Общая дизайн-система (React + Tailwind, premium design tokens)
├── docs/
│   └── PRD.md        # Product Requirements Document (утверждено)
├── nginx/            # Конфигурация Nginx (маршрутизация субдоменов *.ai-krasota.ru)
├── scripts/          # Dev-скрипты (db-init, db-reset, init-rls.sql)
├── .github/workflows/# CI: lint, tests, build
├── docker-compose.yml
├── .env.example
└── .cursorrules      # Правила проекта для AI-ассистентов
```

## Быстрый старт

### Требования
- Docker 24+ и Docker Compose v2
- Node.js 20+ и pnpm 9+ (локальная разработка фронтенда)
- Python 3.11+ (локальная разработка бэкенда)

### 1. Переменные окружения

```bash
cp .env.example .env        # заполните секреты — НЕ коммитьте .env
```

### 2. Запуск платформы в Docker

```bash
docker compose up -d --build
```

| Сервис | URL |
|---|---|
| Веб (лендинг/кабинет) | http://localhost:3000 |
| API (FastAPI, OpenAPI) | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

Сайты салонов доступны по субдоменам вида `http://<tenant-slug>.localhost`
(Nginx маршрутизирует запросы, см. `nginx/`).

### 3. Инициализация базы данных

```bash
./scripts/db-init.sh          # применяет Alembic-миграции к docker-compose Postgres
```

### 4. Локальная разработка без Docker

```bash
# Backend
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload            # http://localhost:8000

# Worker (Celery)
cd apps/worker
celery -A app.celery_app worker --loglevel=info

# Frontend (в корне репозитория)
pnpm install
pnpm --filter @ai-krasota/web dev        # http://localhost:3000
```

## Полезные команды

```bash
docker compose down                       # остановить
docker compose logs -f api                # логи бэкенда
./scripts/db-reset.sh                     # ОСТОРОЖНО: пересоздать БД с нуля
cd apps/api && pytest                     # тесты бэкенда
pnpm --filter @ai-krasota/web lint        # линт фронтенда
```

## Multi-tenancy

Каждый салон — изолированный тенант (`tenant_id` во всех таблицах уровня салона +
PostgreSQL Row-Level Security). Подробности — раздел 22 PRD и правила в `.cursorrules`.

## Вклад в проект

См. [CONTRIBUTING.md](CONTRIBUTING.md). Сообщения коммитов — Conventional Commits
(`feat:`, `fix:`, `docs:`, `refactor:`).
