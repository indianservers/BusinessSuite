# Finance connector validation — 4 November 2026

Result: **6 passed** on PostgreSQL (3 dependency/configuration deprecation warnings).

The dedicated database `business_suite_connector_validation_test` was created by the guarded PostgreSQL test runner and migrated through Alembic. Application business data was not modified.

Both QuickBooks Online and Zoho Books were exercised for ledgers and outstanding invoices through the real authenticated Finance APIs. Only the provider network boundary was simulated.

Verified:
- OAuth setup checks, state replay rejection, regional host validation and encrypted/private tokens.
- Expired access tokens refresh before fetching.
- Provider fetch creates an uploaded staging batch without creating Finance records.
- Commit before preview is rejected.
- Missing required mappings are rejected; external customer/account IDs do not automatically become local IDs.
- Invalid local reference selections produce blocking preview errors.
- Valid mapping and preview still create no Finance records.
- Duplicate source rows create one record and skip the repeated row.
- Fetching again detects existing records; error policy blocks commit and skip policy skips both rows.
- Import writes the selected local ledger/party references and correct outstanding balance.
- Revoke removes imported records, preserves pre-existing records, and permits a fresh import.
- Repeated revoke is rejected, and a later local edit blocks revoke without deleting the edited record.

Command from backend:
`python scripts/run_postgres_tests.py tests/test_import_connectors.py -q --tb=short`

Live-account testing remains unavailable: neither provider has OAuth client configuration or a connected account in the configured application database. No live QuickBooks or Zoho API calls were made. Configure the six IMPORT_QUICKBOOKS_* / IMPORT_ZOHO_* settings documented in docs/import-workspace.md and connect an account in Finance → Import data for live verification.
