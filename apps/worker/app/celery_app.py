"""Celery-приложение AI-krasota.

Фоновые задачи (PRD): напоминания клиентам и прогрев (§6), уведомления (§6.3),
боты Telegram/MAX (§8), AI-сессии (§9), подписки/биллинг (§12).
"""

import os

from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "ai_krasota_worker",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2"),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    beat_schedule={
        # Ежедневная проверка потерянных клиентов (порог 180 дней — PRD §6.1)
        "find-lost-clients": {
            "task": "app.tasks.marketing.find_lost_clients",
            "schedule": crontab(hour=9, minute=0),
        },
    },
)
celery_app.autodiscover_tasks(["app.tasks"])
