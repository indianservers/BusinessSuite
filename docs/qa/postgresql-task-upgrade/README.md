# Production Projects database error repair — 1 November 2026

## Cause

The production build runs `backend/scripts/migrate_deployment.py` through `backend/alembic.ini`. That configuration uses `alembic_postgresql`, while the recent task-group, general-task, task-workspace and file-arrangement migrations existed only in the legacy `alembic/versions` directory. Deployments therefore verified the old PostgreSQL head successfully while application models required newer columns such as `pms_projects.is_task_collection`.

## Repair

Added PostgreSQL revisions 046–049 after `pg_20261031_045_people_workspace`. They add the missing tables, columns, indexes and foreign keys without rewriting existing records. Updated the schema coverage manifest. Legacy migrations remain available for their existing consumers.

Applied the tested chain over direct Neon connections with the existing deployment advisory lock, bounded DDL timeouts and transactional migrations. Both the repository-linked Business Suite database and the separately configured Indian Servers database reached `pg_20261101_049_arrangement`; existing project/task/comment row counts were unchanged. The initial target was the repository's default Business Suite deployment; the Indian Servers domain was then explicitly resolved to its separate Vercel project and database before applying the same repair there.

Read-only verification against Indian Servers confirmed that the management home query succeeds for the screenshot account and that every registered ORM table/column exists. No frontend changes or account permission changes were required.

## Regression checks

`backend/venv/Scripts/python.exe qa/run_pms_postgresql_upgrade.py`: **8 passed** on PostgreSQL 17. The runner creates a uniquely named loopback-only disposable test database and removes it afterwards. Checks include the actual production migration head, full PostgreSQL bootstrap through the test fixture, an isolated pre-change schema with existing project/task records, all required new tables/columns, unchanged existing rows, and repeated upgrade as a no-op. PostgreSQL schema-coverage checks catch newly introduced ORM fields omitted from the deployment manifest.

SQLite-only execution intentionally skips the real PostgreSQL test; it must not be used as evidence that the production upgrade has run.
