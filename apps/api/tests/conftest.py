"""Тестовая инфраструктура: SQLite-файл во временном каталоге + TestClient.

Файловая БД (а не :memory:) выбрана намеренно: фикстуры выполняют DDL через
asyncio.run() (отдельный event loop), а запросы эндпоинтов идут в петле
portal'а anyio TestClient. In-memory SQLite с StaticPool при этом теряет
соединение между лупами («no such table»); файл живёт между лупами надёжно.

- JSONB (postgresql-диалект) компилируется в JSON для SQLite через @compiles.
- RLS — фича PostgreSQL, здесь не проверяется (покрывается интеграционными
  тестами CI с docker-compose).
"""

import asyncio
import uuid as uuid_module

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.core.database import Base


@compiles(postgresql.JSONB, "sqlite")
def compile_jsonb_sqlite(element, compiler, **kwargs):  # noqa: ANN001
    return "JSON"


def run(coro):
    """Синхронно выполнить корутину (для фикстур и ассертов в тестах)."""
    return asyncio.run(coro)


@pytest.fixture
def session_factory(tmp_path):
    db_file = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")

    async def _create():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    run(_create())
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield maker
    run(engine.dispose())


@pytest.fixture
def client(session_factory):
    """TestClient с переопределённой зависимостью get_db."""
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.main import app

    async def _get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def superadmin_token(session_factory) -> str:
    """JWT access-токен Super Admin (владелец платформы, PRD §7)."""
    from app.core.security import create_token, hash_password
    from app.models.user import User

    async def _make():
        async with session_factory() as s:
            su = User(
                email="owner@ai-krasota.ru",
                name="Владелец",
                password_hash=hash_password("Owner12345"),
                is_superadmin=True,
            )
            s.add(su)
            await s.commit()
            return create_token(su.id, "access")

    return run(_make())
