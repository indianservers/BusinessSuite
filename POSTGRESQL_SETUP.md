# PostgreSQL setup

The suite now uses PostgreSQL through Psycopg 3. Existing dummy MySQL records are not imported. Runtime schema creation is handled by the new PostgreSQL Alembic baseline, independently of which modules are enabled in the UI.

## Local databases

- `business_suite`: 616 application tables plus `alembic_version` (617 total), including all HRMS, CRM, PMS, SRM, FAM and shared platform tables, the two historical onboarding tables, and 25 historical columns.
- `business_suite_inventory`: 135 standalone Inventory/POS tables plus its own `alembic_version` (136 total). Keeping this database separate prevents generic table names from colliding with suite tables.

Local PostgreSQL server binaries and data are under `.local/postgresql/` and excluded from Git. The server binds to `127.0.0.1:5432` and uses password authentication. Connection credentials are in the ignored `backend/.env`; no database passwords are committed. This local installation uses `max_locks_per_transaction=256` to support operations across the large schema.

Start the local server using `start-postgres.cmd`. `start-backend.cmd` starts it automatically when this workspace's local cluster is present. To stop it:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File backend/scripts/local_postgres.ps1 stop
```

For another machine, install a supported PostgreSQL version and client tools, create a login/database, and configure the connection. The downloaded runtime is deliberately not committed to source control.

## Fresh installation

Run these commands from `backend` after installing `requirements.txt` and configuring `.env`:

```powershell
venv/Scripts/python.exe create_db.py
venv/Scripts/python.exe main.py
```

The provisioning role needs `CREATEDB` only if the database does not exist. Otherwise a precreated database owned by the migration role is sufficient. Startup creates permissions, roles, one foundation company, a first administrator and application configuration/catalog records. `SEED_DEMO_DATA=false` prevents demo employees, leads and role-based demo accounts from being generated. No old dummy business data is copied.

Set `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` before first startup. An existing administrator password is not reset on subsequent starts.

For standalone Inventory/POS, run `create_db.py` from `backend/app/apps/inventory/vyapara_erp` using its environment with Psycopg and Flask dependencies installed. It reads `INVENTORY_DATABASE_URL` or the `POSTGRES_*` fields and `INVENTORY_POSTGRES_DB`; it never uses the suite database's table namespace.

## Schema migrations

The suite's active migration folder is `backend/alembic_postgresql`; its frozen schema-only baseline is `pg_20261022_001`. The previous `backend/alembic` tree remains historical reference and is no longer selected by `backend/alembic.ini`. Do not run the old revision chain against a fresh PostgreSQL database. Historical tables/columns are protected from accidental removal during new autogeneration.

```powershell
venv/Scripts/python.exe -m alembic upgrade head
venv/Scripts/python.exe -m alembic revision --autogenerate -m "describe schema change"
venv/Scripts/python.exe scripts/verify_postgresql_schema.py
```

For the FastAPI suite deployment without the separate legacy Inventory/POS database, run `venv/Scripts/python.exe scripts/verify_postgresql_schema.py --suite-only`. This verifies the suite migration head, tables and columns and explicitly reports the Inventory check as skipped. The default command still checks both databases.

Review generated migrations before applying them. For production, set `DATABASE_AUTO_MIGRATE=false` and apply migrations as a deployment step. The standalone Inventory/POS app uses its own frozen baseline and `migrations_postgresql` folder.

## Tests and backups

From `backend`:

```powershell
venv/Scripts/python.exe scripts/run_postgres_tests.py tests/test_auth.py tests/test_pms_workspaces.py -q
venv/Scripts/python.exe scripts/postgres_backup.py --output backups/business_suite.dump
venv/Scripts/python.exe scripts/postgres_restore.py backups/business_suite.dump
```

The test runner recreates only its fixed disposable `business_suite_integration_test` database. It never uses the configured application database as the test target. Restore expects an empty configured target database and stops on any error; it does not automatically delete existing tables. Back up uploads separately.

Client tools are discovered through `POSTGRES_BIN`, this workspace's local runtime, or PATH. Passwords are passed to tools through the child process environment rather than command-line arguments.

## Later remote PostgreSQL

Set `DATABASE_URL=postgresql+psycopg://user:URL-encoded-password@host:5432/database?sslmode=verify-full`, with `POSTGRES_SSLROOTCERT` if a provider CA is needed. A raw-password alternative is the discrete `POSTGRES_*` fields, which are encoded safely. `postgresql://` and provider-style `postgres://` URLs are normalized to the Psycopg driver.

Restore PostgreSQL dumps into precreated empty remote databases, provision roles/grants, copy uploads if the application host changes, verify schemas and health/login, then switch the deployment environment. Configure `INVENTORY_DATABASE_URL` separately if deploying standalone Inventory/POS. No MySQL conversion is needed for this later PostgreSQL-to-PostgreSQL move.
