-- ============================================================
-- Multi-tenancy через PostgreSQL Row-Level Security (PRD §22.1, .cursorrules)
-- Выполняется при первом старте контейнера db (docker-entrypoint-initdb.d).
-- Приложение устанавливает GUC app.tenant_id перед запросами
-- (см. apps/api/app/core/database.py :: set_tenant_context).
-- ============================================================

-- Шаблон политики для таблиц уровня салона: применяется миграциями Alembic
-- к каждой таблице с tenant_id. Пример для services:
--
--   ALTER TABLE services ENABLE ROW LEVEL SECURITY;
--   CREATE POLICY tenant_isolation ON services
--     USING (tenant_id = current_setting('app.tenant_id')::uuid);
--
-- Таблицы уровня платформы (tenants, admin_users, platform_settings и т.д.)
-- RLS не оборачиваются либо имеют отдельные политики (только super-admin роль).
SELECT 1;
