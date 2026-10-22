# PostgreSQL schema migration completed

Completed: 22 October 2026 (Asia/Calcutta).

The Business Suite runtime now uses local PostgreSQL 18.6 through Psycopg 3. No dummy records were imported. The retired application MySQL database `ai_hrms` was dropped after PostgreSQL schema and backup/restore verification; PyMySQL was removed from the backend environment and dependency lists. The machine-wide MySQL service was not modified because it may serve other applications.

## Schema coverage

| Database | Verified tables | Coverage |
|---|---:|---|
| `business_suite` | 617 | 616 application tables plus Alembic version metadata. Includes all current HRMS, CRM, PMS, SRM, FAM and platform models, two historical onboarding tables, and 25 additional historical columns. |
| `business_suite_inventory` | 136 | All 135 standalone Inventory/POS application tables plus independent Alembic version metadata. |

Every expected table and column in both coverage manifests was checked on the running PostgreSQL databases. None were missing. Core employee, lead, project, task, sales-order and voucher tables remain empty; new system permissions, roles, administrator, foundation company and configuration records are initialized separately by startup.

## Implementation

- PostgreSQL-only application configuration, provider URL normalization, safe password encoding and PostgreSQL TLS/CA options. Local credentials are in the ignored `backend/.env`.
- Frozen schema-only suite baseline `pg_20261022_001` in `backend/alembic_postgresql`, with independent Inventory/POS baseline `pg_inventory_20261022`. No MySQL dump or old migration chain is needed to initialize a new installation.
- Full-suite schema provisioning is independent of enabled UI modules. Historical fields are protected from accidental removal during migration autogeneration.
- PostgreSQL-compatible boolean backfills, timestamp DDL and database provisioning; retired MySQL runtime/setup/backup code removed or replaced. Earlier migration files remain archived historical reference, not the active migration path.
- Demo seeding disabled locally. Bootstrap administrator creation is configured explicitly and no longer resets an existing administrator's password on restart.
- PostgreSQL backup/restore scripts, repeatable schema verification, a guarded PostgreSQL integration-test runner, local server start/stop helper and updated local/remote setup instructions.
- Database dependency versions aligned with the tested environment: SQLAlchemy 2.0.49, Alembic 1.18.4, Psycopg 3.2.13.

## Validation performed

- Fresh PostgreSQL suite and Inventory/POS schema creation succeeded; repeated suite provisioning succeeded without schema duplication.
- Offline Alembic SQL generation succeeded.
- Schema verifier passed for both databases, including every expected column.
- Application startup and administrator authentication succeeded on the running API. Health and HRMS/company, CRM, PMS/workspaces, SRM dashboard and FAM dashboard endpoints returned HTTP 200.
- Browser sign-in reached `/pms/workspaces`, displayed the fresh empty workspace state and recorded no runtime errors.
- PostgreSQL custom-format backup restored successfully into a separate empty database; all 617 suite tables were present. The temporary restore database was then removed.
- 63 selected real-PostgreSQL API tests passed across authentication, companies, CRM, PMS collaboration, SRM schema/sales orders/POS, FAM voucher creation/balancing, payroll, automation and analytics. A fixture cleanup error at teardown was corrected; its affected POS test was rerun successfully together with six PostgreSQL configuration/schema-completeness tests (`7 passed`). Those six configuration tests also passed independently. This was representative integration coverage, not an execution of every existing test in the repository.
- Frontend TypeScript validation passed.
- MySQL retirement receipt confirms the retired source database was removed and no source data was transferred.

The PostgreSQL test harness supplies the foundation tenant and shares its isolated transaction with module-gating middleware. CRM tests now use actual created user IDs rather than assuming IDs reset to 1; PostgreSQL sequences intentionally do not roll back with test transactions.

Evidence:

- `docs/migrations/postgresql-verification.json`
- `docs/migrations/postgresql-backup-verification.json`
- `docs/migrations/mysql-retirement.json`
- `backend/alembic_postgresql/schema/coverage.json`
- `backend/app/apps/inventory/vyapara_erp/migrations_postgresql/schema/coverage.json`

## Running and later remote hosting

Use `start-backend.cmd` and `start-frontend.cmd`; the backend launcher starts this workspace's local PostgreSQL cluster when present. The local API is available at `http://127.0.0.1:1534` and the frontend at `http://localhost:5173`.

For setup commands, test execution, backups, migrations and later remote PostgreSQL credentials/TLS, see [POSTGRESQL_SETUP.md](POSTGRESQL_SETUP.md). Remote deployment requires environment configuration and PostgreSQL provisioning/restore, with a separate Inventory/POS database URL if that standalone app is deployed. Remote credentials have not yet been supplied or used.
