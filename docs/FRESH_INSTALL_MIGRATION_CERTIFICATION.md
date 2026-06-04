# Fresh Install Migration Certification

Certification date: 2026-06-03  
Scope: Production release hardening - Alembic fresh install only  
Database engine: MySQL  
Certification database: `ai_hrms_fresh_cert`

## Executive Result

| Check | Result | Evidence |
|---|---|---|
| Empty MySQL database created | PASS | `ai_hrms_fresh_cert` was dropped and recreated as an isolated certification database. |
| `alembic upgrade head` from empty DB | PASS | Completed successfully through `20260603_006`. |
| Alembic head validation | PASS | `alembic current` returned `20260603_006 (head)`. |
| Seed data load | PASS | `init_db` completed and loaded users, company, branch, department, designation and employees. |
| Backend startup | PASS | `uvicorn app.main:app --host 127.0.0.1 --port 8002` reached application startup complete. |
| Health endpoint | PASS | `/health` returned `{"status":"healthy","db":"ok","environment":"development"}`. |

Final migration status: **PASS**.

## Root Cause Fixed

The empty database migration chain failed because the first migration creates the current SQLAlchemy metadata, then later historical migrations attempted to add objects that already existed. The specific observed blocker was `employees.interests`, but the migration chain also contained duplicate table, column, index and constraint operations across HRMS, CRM and PMS historical migrations.

## Fix Applied

| Area | Fix |
|---|---|
| Alembic operation safety | Added idempotent Alembic operation guards in `backend/alembic/env.py` for duplicate columns, tables, indexes and constraints during fresh install replay. |
| Alembic version length | Added a wider `alembic_version.version_num` table setup to support long revision identifiers. |
| Head stamping | Ensured the version table is stamped to the actual current head after successful migration execution. |
| MySQL compatibility | Fixed migrations that used PostgreSQL-only SQL patterns or duplicate batch additions. |

## Migration Files Adjusted

| File | Purpose |
|---|---|
| `backend/alembic/env.py` | Idempotent guards, wider Alembic version table and final head stamp. |
| `backend/alembic/versions/20260511_004_crm_multiple_pipelines.py` | Replaced PostgreSQL `RETURNING id` usage with MySQL-safe insert/lookup. |
| `backend/alembic/versions/20260511_017_pms_saved_task_views.py` | Skipped duplicate saved-filter column additions. |
| `backend/alembic/versions/20260511_018_pms_roadmap_epics.py` | Skipped duplicate epic column additions. |
| `backend/alembic/versions/20260512_036_org_structure_master_fields.py` | Replaced PostgreSQL-style joined update with MySQL-safe update path. |

## Commands Certified

```powershell
$env:MYSQL_DB='ai_hrms_fresh_cert'
alembic upgrade head
alembic current
python -c "import app.db.base; from app.db.session import SessionLocal; from app.db.init_db import init_db; db=SessionLocal(); init_db(db); db.close(); print('seed ok')"
uvicorn app.main:app --host 127.0.0.1 --port 8002
```

## Seed Verification

| Table | Count |
|---|---:|
| `alembic_version` | 1 |
| `users` | 13 |
| `companies` | 1 |
| `employees` | 2 |

## Certification Decision

Fresh install migration is **certified PASS**.

