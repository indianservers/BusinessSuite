# Product / service customer dashboard

Route: `/crm/product-customers?entity=all&scope=all`

## Implemented

- Compact gradient header, existing growth navigation, eight clickable KPIs, collapsible distribution/top-offering/trend panels, light/dark themes, and responsive cards.
- Searchable shared-catalog multi-select, product/service groups, checkboxes, select/clear actions, removable chips, ANY/ALL matching, and keyboard navigation.
- Server-side search (including offering names), record/customer classification, status, stage, owner, branch, catalog workspace, follow-up status, activity and creation-date filters. Existing tenant/branch/record/catalog permissions remain authoritative.
- URL-restored filters, pagination, sorting and trend configuration. User/browser-scoped saved and default views. Saved-view restoration applies its query and external filters together.
- Existing enterprise grid: resizing/reordering, column visibility, density, sticky headers, selection, sorting, filtering, pagination, and mobile cards. CSV and Excel exports reuse authorized records and the existing conversion service.
- Five-tab relationship detail: Overview, Products & Services, Deals, Follow-ups, Activity History. Reuses catalog association editing, notes, existing lead conversion and deal creation workflows, communication composer, phone/WhatsApp/SMS links, and bounded bulk follow-up scheduling.
- Individual offering follow-ups use existing activity metadata. Removing association links requires confirmation. Mutations invalidate the affected views.
- No customer, product or service copies, new schema tables, migrations, or repository package dependencies were added.

## API changes

`GET /api/v1/crm/growth/records` is extended additively with `audience`, JSON `offerings` (`[{"kind":"product","id":1}]`), `match=any|all`, `include_analytics`, trend period/interval, advanced filters and export intent. Legacy single-offering consumers remain supported.

The audience projection uses permission-scoped queries, existing catalog links and visible deal catalog lines. Matching can span directly associated offerings and products inherited through visible deals. Page results contain offering chips and existing owner/stage/activity fields. Analytics aggregate the same filtered selection used by the grid, without joining duplicate offerings into record totals.

Conversion is converted leads divided by the filtered lead cohort, not an invented historical comparison. Pipeline amounts are grouped by currency. Per-offering deal values overlap when one deal covers multiple offerings and are explicitly described as non-additive. Trend event dates use UTC.

## Files

New dashboard components:

- `frontend/src/apps/crm/product-customers/ProductCustomersPage.tsx`
- `frontend/src/apps/crm/product-customers/AudienceAnalytics.tsx`
- `frontend/src/apps/crm/product-customers/RelationshipDetail.tsx`
- `frontend/src/apps/crm/product-customers/BulkFollowUp.tsx`
- `frontend/src/apps/crm/product-customers/types.ts`
- `frontend/src/apps/crm/product-customers/product-customers.css`
- `frontend/src/shared/catalog/CatalogMultiSelect.tsx`
- `backend/app/apps/crm/growth_audience.py`

Extended integrations:

- `backend/app/apps/crm/growth.py`
- `frontend/src/apps/crm/routes.tsx`
- `frontend/src/apps/crm/GrowthWorkspace.tsx` (optional offering context in existing follow-up dialog)
- `frontend/src/shared/catalog/CatalogLinesEditor.tsx` (optional removal confirmation)
- `frontend/src/shared/data-grid/SharedDataGrid.tsx`
- `frontend/src/shared/data-grid/GridControls.tsx`
- `frontend/src/shared/data-grid/types.ts`
- `frontend/src/shared/data-grid/state.ts`
- `frontend/src/components/PersonPreviewDialog.tsx` (five-tab layout)

Validation:

- `backend/tests/test_crm_product_audience.py`
- `qa/product_customers_browser.cjs`
- This report and `*-final.png` browser snapshots in this directory. Snapshot relationships are test fixtures, not live customer counts.

## Verification

- Four audience API contract tests passed: ANY/ALL, clearing, all entity types and inherited links, pagination/sorting, unique totals, real converted-lead trends, association refresh, notes/activity, permission isolation, catalog changes shared across CRM/Sales/PMS, and PostgreSQL SQL compilation.
- The additional offering-context follow-up scenario passed: two offering conversations retain one contact record.
- Browser checks passed for ANY/ALL, URL reload, saved/default views with sorting and trend period, association edits, offering-context dialog, CSV export, pagination/sorting, advanced filters, mobile drawer bounds, and desktop/tablet/mobile/dark layouts.
- Existing person-preview browser regressions passed.
- Targeted ESLint and TypeScript checks passed. Production builds passed; the existing bundle-size and mixed static/dynamic import warnings remain.
- Broader backend run: 39 passed, 1 failed. `test_mapped_employee_file_uses_existing_validation` fails because its existing fixture creates an employee without the required destination branch. An earlier attempt also encountered the same existing branch-fixture omission in `test_shared_catalog.py::test_shared_crud_preserves_legacy_ids_and_projects` and `test_links_pricing_tax_and_tenant_isolation`. Those business rules were not relaxed.
- The live Vite page and API schema returned HTTP 200 after reloading local services.

## Limits and validation boundaries

- At most 50 offerings per filter, 50 explicitly selected recipients per bulk follow-up, and 20,000 relationships per export.
- Saved/default views are stored per user, company and branch in the current browser. Customer result rows are not persisted by this page.
- Existing association pricing links and offering-context activities are reused. Separate association lifecycle, owner and expected-value columns were not introduced into the schema; record-level ownership and deal values remain authoritative.
- Browser scenarios use fixtures and backend integration scenarios use isolated test data. PostgreSQL query syntax was compiled, but no authenticated end-to-end browser run against the user's live data or large-dataset load benchmark was performed.
