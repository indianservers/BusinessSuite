# BusinessSuite endpoint audit — 2026-10-23

Scope: every operation in the deployed BusinessSuite OpenAPI schema, across HRMS, CRM, PMS, SRM, FAM and shared services. The CSV and JSON inventory contain one row per HTTP method and route, with status, coverage and limitations. No response records, credentials or tokens are retained.

## Production failures repaired

- `GET /api/v1/reports/global-search`: queried nonexistent `Job.department`. Now joins the department table using `Job.department_id` and searches its name.
- `GET /api/v1/performance/summary/{employee_id}`: read nonexistent `Employee.performance_rating`. Now derives the latest manager score from persisted reviews, returns null without one, and serializes goals/reviews through explicit schemas.
- `GET /api/v1/fam/integrity/checks`: referenced nonexistent `FAMStockItem.current_value`. Now calculates stock value from quantity multiplied by average cost, matching the inventory reports.
- `GET /api/v1/fam/period-close/checklist`: same stock calculation failure.
- `GET /api/v1/fam/final-certification`: same stock calculation failure.

All five returned HTTP 200 on the production alias after deployment `dpl_55jpPLGVbGA2WMvetqTpup7V11Pn`. Evidence: `repaired-production-retests.json`. Original failures remain in `server-failures.json`; they are historical findings, not unresolved current failures.

The finance helper is also used by POST integrity/run, POST period-close/run-checks and POST period-close/lock-period. Its correction fixes that shared exception path; these financial mutations were not invoked against live company data.

## Coverage

Inventoried 1838 operations: 66 DELETE, 814 GET, 41 PATCH, 740 POST, 177 PUT.

Reviewed 814 GET operations: 813 HTTP probes and one provider authentication callback excluded. Initial statuses: 1 × excluded, 659 × 200, 1 × 307, 22 × 400, 1 × 401, 7 × 403, 113 × 404, 5 × 422, 5 × 500.

659 reads initially returned 200; the five repaired reads add five successful targeted retests. 129 probes used a missing resource identifier because no matching live record was available. A 400, 404, 422, access rejection or redirect is not certification of a valid workflow. The CSV preserves each limitation.

The 1,024 non-GET operations are all listed, but were not swept blindly against production. Such a sweep could send messages, change permissions, post accounting records, run payroll or delete company records. Their inventory rows explicitly say `not_executed`. A full valid-input certification of every write operation remains outstanding; this audit does not claim every BusinessSuite feature is certified.

## Isolated automated verification

The broad backend suite ran against an isolated SQLite database and release source snapshot: 572 passed, seven skipped, one schema-inventory assertion failed, three setup errors from the unavailable S3 mock package. Fixed test middleware session routing for SQLite, updated the schema extension inventory for the migrated PMS tables, and installed the test requirements' S3 mock dependency. The failed/setup groups plus new regressions were rechecked: 16 passed, three skipped. The performance appraisal workflow separately passed, including summary serialization with multiple reviews.

New regression coverage checks global search by department and the exact stock valuation amount. Existing appraisal tests exercise the repaired summary. PostgreSQL-specific tests and environment-dependent external-service flows remain excluded; SQLite test success does not substitute for those.

The earlier PMS repair and its create-task/custom-field/timer/docs evidence are documented in `docs/PMS_PRODUCTION_AUDIT_2026-10-23.md` and its QA directory.

## Reproduction

`backend/scripts/audit_endpoints.py` fetches the deployed schema, inventories all operations and performs bounded read probes. Supply test account credentials using the `SUITE_AUDIT_ACCOUNTS_JSON` environment variable; no credentials are embedded in the script. Use `--base-url`, `--output`, and optional `--workers`.

Production data was not bulk deleted or changed as part of the endpoint sweep. The isolated repair deployment excludes concurrent unrelated workspace changes. Source changes are present locally and have not been committed or pushed by this audit.
