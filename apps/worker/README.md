# @ai-krasota/worker — Фоновые задачи (Celery + Redis)

Задачи: напоминания и прогрев клиентов (PRD §6), уведомления (PRD §6.3),
Telegram/MAX-боты (PRD §8), AI-сессии RAG и коуча (PRD §9), биллинг-подписки (PRD §12).

```bash
pip install -e .
celery -A app.celery_app worker --loglevel=info   # worker
celery -A app.celery_app beat --loglevel=info     # планировщик
```
