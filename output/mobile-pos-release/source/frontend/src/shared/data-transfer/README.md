# Shared import and export

Use `ImportWizard` and `DataExportButton` from `@/shared/data-transfer` for tabular transfers. These components adapt files; existing module APIs continue to authorize, validate, audit and save records.

`ImportWizard` takes destination `fields` (or an async field loader) and `onImport`. Fields support labels, required values, aliases, types, hints and defaults. The flow supports Excel/CSV/TSV/JSON, drag and drop, worksheet/header-row selection, automatic/manual mapping, unmapped-column exclusion, templates, review and downloadable errors. It never calls `onImport` before confirmation.

`onImport` receives mapped `rows`, a normalized CSV `file`, original `filename`, source-to-target `mapping`, and original `rowNumbers`. Return `{created, errors, message}`. Error `row` values are one-based positions in the mapped input, not worksheet row numbers; adapt existing endpoints that count their header row. The wizard restores original row numbers for display. A partial success produces a completion receipt; users upload corrected rejected rows separately instead of replaying saved rows. Preview-only workflows should explain the next confirmation step in `message`.

`DataExportButton` takes an async `load` callback returning the existing authorized export Blob or records. It offers Excel, CSV, JSON and clipboard output with column selection. Use a truthful scope description. Keep existing module export permissions, filters and row limits in `load`; this component does not fetch module records itself. Specialized multi-sheet/full-detail exports and existing Deals PDF exports retain their own workflows.

The authenticated `/data-transfer` APIs are stateless: they only inspect or convert the caller's submitted files. They do not read module records or write imports. File content and mappings are not saved to browser storage. The pure parser in `backend/app/shared/tabular_files.py` is also reused by the separately hosted legacy inventory app.

Default limits are 3 MB / 5,000 imported rows / 150 columns. Adapters retain smaller limits (catalog 500 rows, invitations 100, bank results 1,000). Conversion allows up to 20 MB / 20,000 rows; oversized files fail explicitly. Old `.xls` files must be saved as `.xlsx`. Spreadsheet formula protection applies to exports.

Validation: `backend/tests/test_data_transfer.py` and `qa/data_transfer_browser.cjs`. Browser checks use mocked responses; backend tests exercise actual parsing, export files and an employee import through the existing persistence API. Legacy inventory adapter tests avoid its separately configured Flask/PostgreSQL runtime.
