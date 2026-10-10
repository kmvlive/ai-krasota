"""Задачи маркетинга и удержания (PRD §6). Реализация — Фаза 2."""

from app.celery_app import celery_app


@celery_app.task(name="app.tasks.marketing.find_lost_clients")
def find_lost_clients() -> None:
    """Найти клиентов без визита дольше порога (по умолчанию 180 дней, PRD §6.1).

    TODO (Фаза 2): запрос по clients/bookings, формирование раздела «Требуют внимания»,
    уведомление мастера через бота.
    """
    raise NotImplementedError("Фаза 2: маркетинг и удержание (PRD §6)")


@celery_app.task(name="app.tasks.marketing.send_booking_reminders")
def send_booking_reminders() -> None:
    """Напоминания о записях и прогрев по триггерам услуг (PRD §6.2–6.3).

    TODO (Фаза 2): группировка событий в дайджест при большом количестве.
    """
    raise NotImplementedError("Фаза 2: напоминания (PRD §6.3)")
