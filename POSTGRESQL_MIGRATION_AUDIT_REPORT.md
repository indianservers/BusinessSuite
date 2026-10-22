# PostgreSQL migration audit and execution plan

> Historical assessment. The schema-only migration has since been completed; see `POSTGRESQL_MIGRATION_COMPLETE.md` and `POSTGRESQL_SETUP.md` for current status and setup. Dummy source data was not transferred.

Date: 22 October 2026 (Asia/Calcutta)

Status: **Assessment started and completed for the main database; application cutover has not started.** PostgreSQL is a viable target, but the application is not ready for a connection-string-only switch. Keep MySQL as the active source until a local PostgreSQL rehearsal passes the checks below.

## Scope and evidence

Reviewed the shared database configuration, all five registered product modules (HRMS, CRM, PMS, SRM, FAM), common platform modules, current ORM schema, Alembic history, startup schema helpers, seed/backup scripts, test configuration, frontend database coupling, and the bundled legacy Inventory/POS source.

Executed a read-only snapshot inventory of the configured MySQL database, PostgreSQL DDL compilation without a PostgreSQL connection, foreign-key orphan checks on populated model tables, and zero-date checks. The API was not started by the audit; startup seeds and migrations were not executed. No source rows or application configuration were changed. The audit saves aggregate counts and schema information, not credentials or business row values.

Reproducible audit: `backend/scripts/audit_postgresql_readiness.py`.
Detailed evidence: `docs/migrations/postgresql-audit.json`.

| Measurement | Observed result |
|---|---:|
| Source engine/version | MySQL 9.4.0 |
| Source tables | 617, all InnoDB |
| Source rows | 53,725 across 154 populated tables |
| Estimated source table/index allocation | 22.2 MiB / 37.5 MiB; not transfer-size or timing estimates |
| Full-suite current model tables / columns | 614 / 7,491 |
| Current model foreign-key constraints / indexes | 1,328 / 3,275 |
| PostgreSQL table/index compilation failures | 0 / 0 |
| Duplicate explicit index names / indexed JSON columns | 0 / 0 |
| Native enums requiring PostgreSQL type creation | 0 in current main-app models |
| Model foreign keys checked on nonempty source tables | 381; no orphaned references found |
| Zero-date columns found in populated source tables | 0 |
| Alembic migration files / code heads | 113 / one head: `20261022_001` |
| Source Alembic revision | `20260607_019`; behind the code head |

These are audit-time counts. The running application can add records afterward. Offline DDL compilation does not establish successful PostgreSQL execution, data transfer, API compatibility, or performance.

## Findings that must be addressed

| Priority | Finding and evidence | Required migration work |
|---|---|---|
| Blocker | No `psycopg` or `psycopg2` installed in the backend environment. `backend/requirements.txt` declares PyMySQL only. PostgreSQL CLI tools, a PostgreSQL Windows service, and Docker were not found in the checked locations/PATH. | Provision local PostgreSQL and client tools; add and pin a tested PostgreSQL driver. Recheck for any custom installation path when credentials are supplied. |
| Blocker | `backend/app/core/config.py` accepts `DATABASE_URL`, but defaults to MySQL and applies `MYSQL_SSL_CA` connection arguments without checking the selected dialect. | Support an explicit `postgresql+psycopg://` URL; select connection/TLS options by dialect; retain MySQL connectivity for transfer and rollback. |
| Blocker | `backend/create_db.py` always creates a MySQL database using PyMySQL, even when `DATABASE_URL` points elsewhere. Column repair also uses MySQL backticks. | Separate database provisioning from schema migrations; implement PostgreSQL-compatible initialization and identifier quoting. Do not run the existing helper against the PostgreSQL target. |
| Blocker | `backend/app/apps/crm/schema.py` performs unconditional boolean backfills such as `COALESCE(is_visible, 1)` and mixes boolean columns with integer-valued CASE expressions. It also uses raw `DATETIME` for missing columns. `backend/app/apps/project_management/schema.py` has `BOOLEAN DEFAULT 0`. | Use typed SQLAlchemy statements/portable true/false and dialect-appropriate timestamp DDL. CRM backfills run during normal startup, so even a freshly created target schema will not bypass all failures. |
| High | Startup in `backend/app/main.py` calls `create_all`, seed routines, and schema repairs. The migration baseline also creates tables from the current model snapshot. `backend/alembic/env.py` patches operations to skip existing objects and manually updates the version row. | Establish a tested PostgreSQL baseline and explicit upgrade path. Reconcile the actual schema before changing revision state; never simply stamp the current source as migrated. Keep production runtime startup separate from provisioning and data migration. |
| High | Historical CRM migrations contain the same integer/boolean expressions: `20260511_008`, `20260511_010`, `20260605_002`, and `20260605_003`. Thirteen revision identifiers exceed Alembic's normal 32-character version field. Existing widening logic only alters an existing narrow table on MySQL. | Test clean installation and upgrade separately; fix incompatible data migrations and support the wide version column on PostgreSQL. |
| High | Source has 25 extra columns across 12 modeled tables, plus two historical onboarding tables not represented by current models. Both historical tables are currently empty. | Include these in a migration mapping/preservation decision. Copying only current ORM columns would lose schema information. The Alembic version table is also source-only by design and must be reconciled, not blindly copied over a different baseline. |
| High | Local `INSTALLED_APPS` enables HRMS, CRM, PMS, SRM, but omits FAM. The 73 FAM tables still contain 49 rows. Enabled-only metadata includes just 541 tables. | Build migration metadata from the whole suite, not only enabled modules. Preserve all FAM data while retaining the existing feature-enable setting unless intentionally changed. |
| High | `backend/scripts/mysql_backup.py` and `mysql_restore.py` emit/read MySQL-specific SQL (`SHOW TABLES`, MySQL DDL, `FOREIGN_KEY_CHECKS`). | Keep these for source backup/rollback. Use a typed cross-database transfer for MySQL to PostgreSQL, and PostgreSQL-native backup/restore after migration. A MySQL SQL dump is not a PostgreSQL restore file. |
| High | Bundled `backend/app/apps/inventory/vyapara_erp` is a separate Flask application with its own DB configuration, migrations, backup helper, and 135 statically identified model table declarations. It hardcodes a MySQL URI and uses `DATETIME` in schema repair. | Track this as a separate migration workstream. Confirm whether that standalone application/database is used. Its live database was not connected to or counted in the 617-table inventory. Preserve its separate namespace/database because generic table names overlap the suite. |
| High | `backend/tests/conftest.py` runs the shared test suite against SQLite in memory. | Add a real PostgreSQL test database and run integration tests there; SQLite passing is insufficient for PostgreSQL sign-off. |
| Medium | Runtime SQLAlchemy is 2.0.49; requirements pin 2.0.30. | Reproduce a locked dependency environment and test the chosen driver/version pair. Current compile results apply to the installed 2.0.49 environment. |

The employee model's MySQL `row_format` option is dialect-specific, and its corresponding migration guards MySQL-only row-format SQL. It was reviewed but did not cause PostgreSQL DDL compilation failures.

## Data and behavior compatibility

- **Identifiers and relationships:** Preserve primary keys, tenant/company IDs, relationships, status values, audit history, and password hashes. Detect cyclic/self-referencing dependencies and use staged load/constraint validation. Reset PostgreSQL sequences after explicit ID insertion, including correct handling of empty tables.
- **Booleans:** Convert source MySQL boolean storage to actual Python/PostgreSQL booleans. Validate out-of-domain source values before transfer; do not rely on implicit numeric casts. The audit did not yet run an exhaustive boolean-value domain scan.
- **Dates and time zones:** There are 1,051 ORM `DateTime(timezone=True)` columns and two naive datetime columns. Source MySQL reports session time zone `SYSTEM`. Confirm the source timestamp convention before conversion; the database host time zone is not established by this setting alone. PostgreSQL-aware return values and naive Python datetime comparisons need regression coverage. Keep naive PMS invitation timestamps consistent with their current explicit model semantics, or migrate them deliberately.
- **JSON:** There are 243 current JSON columns. Preserve SQL NULL versus JSON null, object/array values, and Unicode. Retain JSON initially; introduce JSONB/index changes only where query behavior is tested. No current explicit index on a JSON column was found.
- **Money and quantities:** Preserve all 612 Numeric columns as Decimal values with their declared precision/scale. Check financial totals, stock valuation, tax rounding, and payroll calculations. Do not transfer these through floating-point conversion.
- **Search and uniqueness:** Source collation is `utf8mb4_unicode_ci`. Default PostgreSQL text comparison will not automatically reproduce its case/accent behavior. Define explicit email/login normalization, unique business-key rules, search behavior, and sorting. Test mixed-case logins and duplicate prevention.
- **Query behavior:** Most application data access uses the ORM; targeted searches found little use of MySQL-only SQL functions outside setup/backup code. This reduces rewrite scope but is not a proof of runtime query portability. Test ordering of NULLs, grouping/aggregates, date filters, pagination, locking, and transaction failure handling against PostgreSQL.
- **Files:** Attachments are files in upload directories, not just database records. Back up and transfer the actual files with path mapping and download verification, including the new PMS demo attachments.
- **External services:** Redis/Celery, integrations, mail, and provider tokens remain separate configuration concerns. Migration rehearsals must not dispatch demo notifications, integration calls, payroll actions, or duplicate background jobs.
- **Frontend:** React uses HTTP APIs rather than a database connection. Preserve API contracts and user flows. No general frontend rewrite is required; update setup text that explicitly advertises the old MySQL stack when the corresponding service has migrated.

## Local-first migration sequence

| Stage | Concrete work | Completion condition |
|---|---|---|
| 0 — audit (completed) | Read-only source inventory, schema compilation, compatibility findings, migration plan. | This report and machine-readable evidence saved. |
| 1 — PostgreSQL foundation | Provision a separate local PostgreSQL instance/database; add a tested synchronous Psycopg driver; dialect-aware configuration; portable bootstrap/startup SQL; PostgreSQL test configuration and migration baseline. | Fresh PostgreSQL schema and application startup succeed without changing the active MySQL source. |
| 2 — migration tooling | Implement source snapshot export/typed target import, complete schema mapping including historical columns/tables, sequence reset, constraints/indexes, verification manifests, dry-run mode, resume/retry rules, and source/upload backup. | Repeatable load into a disposable local target; no skipped tables/columns without an explicit mapping decision. |
| 3 — rehearsal | Copy all 617 source tables according to the mapping, preserve demo data and files, verify counts/checksums and business invariants. Test clean schema plus populated upgrade paths. | All validations pass; discrepancies are explained and resolved. |
| 4 — local cutover | Pause source writes/workers, take final snapshot, rerun transfer/verification, switch local `DATABASE_URL`, then restart API/workers. Keep the MySQL source and backup available. | Full local application works on PostgreSQL, including new inserts after sequence reset. |
| 5 — remote PostgreSQL | Provision remote target with the same chosen PostgreSQL major version; restore a PostgreSQL dump, transfer uploads, apply least-privilege roles/TLS/network settings, repeat verification, then switch environment configuration. | Remote rehearsal, restore test, and application regression pass before remote cutover. |

Use a locally supported PostgreSQL release that is also available on the intended remote provider. PostgreSQL 17 or 18 are candidates; select one major version for both environments before provisioning. Use UTF-8 and a documented timestamp convention. This report does not infer the remote provider or install a server before connection details are available.

Planned local connection shape, with placeholders only:

```dotenv
DATABASE_URL=postgresql+psycopg://business_suite_app:<URL-encoded-password>@127.0.0.1:5432/business_suite_local
```

Remote hosting should use verified TLS where supported by the provider, for example `sslmode=verify-full` and the provider CA as needed. Do not pass the existing MySQL SSL dictionary to Psycopg. Use PostgreSQL-native `pg_dump`/`pg_restore` for the later PostgreSQL-to-PostgreSQL move; provision roles/grants separately because a single-database dump does not include cluster-global roles.

## Acceptance tests and rollback

Before local cutover, require:

1. Every mapped table/column present; source/target row counts and canonicalized data checksums reconcile. No new orphaned references, duplicate business keys, invalid dates, or invalid JSON; sequences produce unused IDs.
2. Login, refresh, RBAC, tenant isolation, role/member management, and mixed-case email behavior pass.
3. HRMS: employee lifecycle, attendance/leave balances, payroll calculation and approvals, documents, reports, and workflow/audit trails pass.
4. CRM → SRM → PMS → invoice/accounting handoffs preserve links and idempotency. FAM debit/credit, tax, stock and financial invariants remain unchanged.
5. PMS: workspaces, invitation acceptance/expiry, members/roles, project/task creation, drag/drop persistence, Gantt dependencies, comments/mentions, files/downloads, sprints, time logs, timesheets, reports, and client approvals pass.
6. SRM: customer/product/pricing, sales orders, invoices, payments, procurement, inventory movements, POS sessions, and accounting handoff pass. Independently used legacy Inventory/POS has its own test gate.
7. Shared automation, communication, analytics, AI-agent persistence, audit/security, SaaS/platform services, worker retries and concurrent updates pass on PostgreSQL.
8. A PostgreSQL backup restores into a clean test database. Uploads are present and downloadable. Representative queries meet recorded baseline timings.

For rehearsal, MySQL remains authoritative and PostgreSQL is disposable. At cutover, freeze writes until verification completes. A switch back to MySQL is straightforward only before accepting PostgreSQL-only writes; afterward it requires explicit reconciliation/replay of those writes to avoid data loss. Do not run both databases as independent write targets.

## Details needed for the next stage

- Local PostgreSQL host, port, database name, username, password, and server major version; alternatively confirm an existing local instance and its path.
- Whether the supplied role may create a database/schema, or whether an empty target database will be precreated.
- Later remote host/provider, PostgreSQL major version, TLS/CA requirements, and network access details.
- Whether the standalone Vyapara Inventory/POS database is actively used; if so, include its separate source connection in the migration inventory.

Credentials belong in local environment/secret configuration, not in this report or source-controlled files. No remote credentials are needed to complete local migration development.

## References

- [SQLAlchemy PostgreSQL dialect and Psycopg support](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)
- [PostgreSQL pg_dump/pg_restore transfer capabilities](https://www.postgresql.org/docs/current/app-pgdump.html)
- [PostgreSQL sequence reset semantics](https://www.postgresql.org/docs/current/functions-sequence.html)
- [PostgreSQL verified TLS connection modes](https://www.postgresql.org/docs/current/libpq-ssl.html)

Remaining limits: no PostgreSQL server connection, server-side DDL execution, data import, application regression run on PostgreSQL, or independent legacy database audit has occurred. The findings above are readiness evidence, not migration certification.
