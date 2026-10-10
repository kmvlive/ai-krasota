"""Проверки здоровья для Docker healthcheck и мониторинга (PRD §14.2 Uptime)."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai-krasota-api"}
