# Import validation — 4 November 2026

Configured application database: local PostgreSQL `business_suite`.
Ran `alembic upgrade head` successfully. The database was already at
`pg_20261104_081_task_links`, which includes `pg_20261104_080_imports`.
Verified all 18 batch columns and all 9 connection columns exist.

## PostgreSQL integration tests

33 passed, 3 dependency/configuration deprecation warnings.
Used the guarded runner with the dedicated database
`business_suite_import_validation_test`, recreated from the full Alembic chain.
Application business data was not used for synthetic import testing.

All 15 supported import types across CRM, SRM, HRMS, PMS and Finance verify:
- Commit without preview is rejected.
- Required column mappings are enforced.
- Preview identifies duplicate rows within the uploaded file.
- Import creates native module records.
- Existing duplicates can be skipped or made blocking errors.
- Revoke succeeds, repeated revoke is rejected, and a new preview sees the record as new again.

Additional shared tests verify cleaning, corrections, stale previews, update restoration,
revoke protection for later edits, permissions, private history, templates and connector staging.

Testing exposed and fixed a CRM ownership bug: organization_id identifies the tenant;
CRM company_id is a customer reference and must not be filled with the tenant ID.
Added a regression assertion for imported deals with no selected customer.

Command (from backend):
`python scripts/run_postgres_tests.py tests/test_import_workspace.py tests/test_import_adapters.py tests/test_import_connectors.py tests/test_data_transfer.py -q --tb=short`

## Browser checks

10 passed: CRM, SRM, HRMS, PMS and Finance at 1440px and 390px.
These are UI tests with mocked API responses, independent of the PostgreSQL integration tests.
Cover upload, mapping, preview acknowledgement, import, history and revoke/remap.
Screenshots and results.json are in this directory.

QuickBooks/Zoho OAuth tests use mocked provider responses; live external accounts were not tested.
