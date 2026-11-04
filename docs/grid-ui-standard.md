# Suite grid standard

Record directories use the CRM Deals `SharedDataGrid` engine across PMS, CRM,
HRMS, SRM, finance, inventory, Power Apps, and shared administration.

## Components

- `SharedDataGrid`: server-backed records, saved layouts/views, filtering,
  grouping, column ordering/resizing/pinning, keyboard navigation, selection,
  exports, row actions, record preview, and bulk actions.
- `GridRecordPane`: common desktop details pane and accessible mobile dialog.
  Company Directory uses the same pane while retaining its full company profile.
- `LocalRecordGrid`: typed records already loaded by a page. PMS Advanced Tasks
  and workspace task lists use it directly, including their existing editors,
  custom fields, action menus, and permission checks.
- `GridTable`: compatibility adapter for existing declarative record tables.
  React cells and handlers remain owned by the page. Existing checkbox selection
  and header controls remain connected to the page's business actions.

## Scope and permissions

Server-backed grids operate on the server query. Local adapters explicitly label
search, grouping, and export as applying to loaded records. Existing server page
filters and pagination remain available. Do not label a local result as an
organization-wide total.

Adapters do not infer authorization to export; export is disabled by default.
Page-owned exports retain their existing authorization. Enable `allowExport`
only where the page has established the user's export permission.

Pass permission-aware actions through `bulkActions`, or page-owned controls through
`bulkToolbar`. Bulk actions may provide a confirmation message. Errors stay in the
shared alert, failed operations retain the selection, and successful operations
refresh the grid. Do not introduce generic delete, payroll, or accounting writes.

## Specialized layouts

Entry forms, roster matrices, comparison tables, totals, merged cells, loading
and error rows, and opaque render-prop row wrappers retain native table semantics
with the shared visual treatment. The compatibility adapter deliberately avoids
flattening these structures and breaking their editors or business behavior.
Use `variant="matrix"` explicitly for non-record layouts, or migrate a complex
record page to `LocalRecordGrid` to gain the complete interaction model.

## Verification

From `frontend`:

```sh
npx tsc --noEmit
npx vite build
node scripts/test-grid-standard.cjs --unit
# Start Vite, then use its URL for the browser fixture:
GRID_TEST_URL=http://127.0.0.1:5174 node scripts/test-grid-standard.cjs
```

The regression fixture checks local query behavior, grouping and expansion,
selected-row export scope, spreadsheet formula escaping, previews and Escape,
bulk mutations, preservation of page-owned selection/actions and editable entry
matrices, and mobile details dialogs. It uses local fixture records; it does not
certify every authenticated route or business workflow.

The idempotent `scripts/migrate-suite-grids.cjs` script changes native table shells
without rewriting their cells. Use it only after reviewing new table layouts.
