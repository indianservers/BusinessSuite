# Shared import workspace

Open **Import data** in CRM, Sales, HRMS, PMS or Finance. The routes are
`/crm/import-data`, `/srm/import-data`, `/hrms/import-data`, `/pms/import-data`
and `/fam/import-data`. The catalogue exposes only import types the current
user can manage in the selected company and writable branch.

Each module has three priority import types. Upload Excel/CSV/TSV, choose a
worksheet and header row, review suggested column mappings, and map required
fields or supply fixed values. Local record IDs must refer to existing records
in the selected company/branch; provider identifiers are never assumed to be
local IDs. Expand source corrections to fix individual cells without changing
the original spreadsheet. Preview validates every row (maximum 5,000 rows,
3 MB), shows cleaning suggestions and duplicate decisions, and blocks commit
until errors are fixed. Nothing is written to business records during preview.

By default existing records are skipped. Updating is limited to supported
master records. Operational transactions are not overwritten. Imported sales
orders remain drafts; time entries remain pending; Finance opening references
do not automatically post journals. HRMS salary imports create salary
assignments (annual CTC and monthly basic/HRA), not processed payslips.

History retains mapping, original source rows, corrections, preview, counts,
timestamps and the owning importer. History access is limited to that importer
with current module permissions and the same company/branch. Revoke checks the
complete saved change receipt, including generated canonical contacts and
channels. Later edits or dependencies block undo atomically. Revoke-and-retry
creates a fresh draft from the same original source for remapping.

## Database deployment

Apply the normal migration chain before enabling the new workspace:

- SQLite chain: `20261104_064_imports`
- PostgreSQL chain: `pg_20261104_080_imports`

These additive migrations create `suite_import_batches` and
`suite_import_connections`. Existing business data is not rewritten.

## Finance connections

QuickBooks Online and Zoho Books use OAuth. Connector fetches only stage data;
they always pass through local mapping, validation and preview. Tokens are
encrypted with the existing application cipher and never returned to the UI.
Credentials cannot be supplied in a spreadsheet or arbitrary URL.

Configure the appropriate values in the backend environment (or `.env`), then
restart the backend:

```
IMPORT_QUICKBOOKS_CLIENT_ID=
IMPORT_QUICKBOOKS_CLIENT_SECRET=
IMPORT_QUICKBOOKS_REDIRECT_URI=https://YOUR-SUITE-HOST/fam/import-data
IMPORT_ZOHO_CLIENT_ID=
IMPORT_ZOHO_CLIENT_SECRET=
IMPORT_ZOHO_REDIRECT_URI=https://YOUR-SUITE-HOST/fam/import-data
```

Register the exact redirect URI in each provider console. Users select their
Zoho data centre and enter their Zoho organization ID before connecting.
QuickBooks supplies its company realm ID during authorization. Authorization
state is user/company/branch scoped, expires after ten minutes and is single
use. Token refresh remains on the server. Disconnect removes locally stored
credentials; an administrator may additionally remove the provider-side grant
in the provider console.

Supported connector data: chart-of-account ledgers and outstanding customer
invoices. Bank statement lines use the provider's CSV/XLSX export. Provider
pulls are bounded; exceeding the limit fails instead of silently importing a
partial account. Foreign-currency outstanding references must be converted
through the Finance workflow first; this importer does not invent FX rates.
QuickBooks uses the production Online API. Live account authorization requires
the provider credentials above and has not been exercised by automated tests.

Provider references:

- [QuickBooks OAuth](https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization/oauth-2.0)
- [QuickBooks Accounting API](https://developer.intuit.com/docs/api/accounting/invoice)
- [Zoho Books OAuth](https://www.zoho.com/books/api/v3/oauth/)
- [Zoho chart of accounts](https://www.zoho.com/books/api/v3/chart-of-accounts/)
- [Zoho invoices](https://www.zoho.com/books/api/v3/invoices/)

## Verification

```
backend/venv/Scripts/python.exe -m pytest backend/tests/test_import_workspace.py backend/tests/test_import_adapters.py backend/tests/test_import_connectors.py -q
node frontend/node_modules/typescript/bin/tsc --noEmit -p frontend/tsconfig.json
```

Browser fixtures use no real accounts or data. Start frontend Vite on port 5191
and run `node frontend/scripts/check-import-workspace.cjs`. This checks five
modules at desktop/mobile widths through mapping, preview acknowledgement,
commit, history and revoke/remap. The sample workbook is generated from the
same field catalogue; application template downloads include per-type samples
and field instructions.
