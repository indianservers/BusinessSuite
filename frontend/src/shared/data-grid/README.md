# Shared data grid

Import `SharedDataGrid` and its types from `@/shared/data-grid`. CRM Deals uses a server-backed source. Module record tables use `GridTable`, which preserves page-owned React cells and falls back to `NativeTableTools` for editable or matrix tables.

## Connect a module

Supply `gridId`, `columns`, `source`, and `getRowId`. The `GridSource` contract has `load`, `facets`, and `export` methods. Keep authorization and tenant scoping in the module's backend adapter. The Deals reference adapter is `apps/crm/deals/DealsDataGrid.tsx`; the backend reference is `backend/app/apps/crm/deal_grid.py`.

`load` receives a `GridQuery` with pagination, search, recursive AND/OR filters, sorting, grouping, and a drill path. Return full filtered totals and aggregates separately from the bounded page of records. Group pages return group keys and counts; expanding a group requests its path. Never compute global summaries from the current page.

Use `GridColumn` for typed filters, renderers, edit validation, and visibility defaults. Enable editing, row actions, bulk actions, exports, and manual row ordering only when the source supports them and the current user has permission. Save handlers should use the record version to reject concurrent edits.

`queryState` supports controlled queries. `viewContext` can include existing module filters in saved views. Alternate cards/list/kanban views can use the same source. Keep module-specific workflow actions in the adapter.

## Preferences and limits

Layouts and saved views are stored in browser local storage, scoped by organization, user, workspace, and grid. They do not synchronize across devices. Row and wide-column virtualization bound rendered DOM; the server owns filtering, sorting, grouping, and pagination.

The Deals adapter caps pages at 200 records, grouping at four levels, selected export IDs at 200, spreadsheet/clipboard exports at 20,000 records, and PDFs at 2,000. Oversized exports return an explicit error. Currency aggregates remain separate; no implicit currency conversion occurs.

## Validation

- Backend: `backend/venv/Scripts/python.exe -m pytest tests/test_shared_data_grid.py -q` from `backend`.
- Frontend: `npm run build` from `frontend`.
- Browser: start Vite on port 5194, then run `node qa/shared_data_grid_browser.cjs` from the repository root. This uses mocked remote responses and covers interactions, preserved Deals views, mobile/themes, and a 100,000-record remote-source simulation. The backend suite separately exercises 10,000 real database records.

## Compact module lists

`GridTable` uses compact rows and shared semantic group badges. `defaultGroupBy` and `defaultHiddenColumns` provide editable-table defaults; personal layouts override them. Grouping, density, visibility, and column order are saved per user, company, route, and table. Tables with totals or nonrectangular cells retain their original semantics.

For a module with its own search and pagination, use `hideSearch` and `externalPagination` to avoid duplicate controls. Internal pagination remains available if a saved grid view requires more than one local page. Group counts still refer to loaded records, not backend totals.

Editable tables can receive `groupCreate={{field:"Status",label:"Add project",onCreate}}`. The module owns permissions and must show the selected status in its creation form. Group badges and record icons share `GroupLabel.tsx` and never substitute for textual status labels.

Browser verification: `node frontend/scripts/verify-grouped-lists.cjs` from the repository root, against the disposable local QA API and Vite frontend. Override `GROUPING_APP_URL` and `GROUPING_API_URL` if needed. The script uses read-only browser checks and opens creation dialogs without submitting them.

## Suite-wide lists and collections

All native record tables route through `GridTable`, including shared platform tables, project overviews, connected-accounting lists, and import history. Use `staticLayout` for index-sensitive import editors or aggregate matrices: they receive compact styling while retaining original row order, totals, and input semantics.

`GroupedRecords` supplies the same colored headers, counts, keyboard-accessible collapse controls, and scoped preferences for card collections. Keep `renderItem` page-owned so permissions, actions, and forms remain unchanged. Supply explicit fields for business-specific labels; `standardRecordGroups(items)` exposes only scalar grouping dimensions actually present in a generic collection. Calendars, boards, conversations, and rich-text editors keep their specialized interaction models.

`cell-content.ts` reads scalar React content and TanStack accessor contexts without mounting or executing cell components. Decorative icons are excluded with `aria-hidden`; `data-grid-value` can supply a canonical value. `suite-list-surface.css` applies shared compact page and grid styling, including server-backed grids, without adding layout wrappers.

Validation:
- `node frontend/scripts/audit-suite-list-coverage.cjs` checks that native tables only live in the shared renderer and writes source coverage.
- `node frontend/scripts/verify-suite-list-rollout.cjs` reviews the disposable QA route catalog. `SUITE_LIST_RESUME=1` retries unfinished/failed pages; `SUITE_LIST_WORKERS=1` runs serially. It changes personal grouping only and does not submit business mutations.
- `playwright/suite-grouped-lists.spec.ts` checks cards and real rendered cell values in HRMS, assets, AI, customization, and view-only portals.

## Personal record views

Record lists expose Table, Cards, List, relevant field grouping, Favorites, and Frequent through shared renderers. Tags appears only when a real tags/labels field exists. The Products & Services catalog retains its specialized catalog views. Static matrices and totals retain their original editing semantics.

Personal favorites and action counts store identifiers only, scoped to company, account, route, and collection in this browser. Frequent counts previews and original record actions; choosing a view does not count as activity. PMS uses its existing project stars when present. Quick tools keep original permission-aware actions, with preview and copy-name helpers.

Local adapters filter the loaded collection before their own pagination. Remote sources declare `personalIdentity` only when their backend supports `GridQuery.recordIds`; these filters apply inside the existing tenant/visibility query before pagination. `recordOrder` ranks frequent identifiers. Other server-paged adapters explicitly label personal results as loaded records only. No record payload is persisted in personal preferences.

Cross-module browser checks: `playwright/suite-record-views.spec.ts`, plus catalog, grouped-list, PMS portfolio, and sidebar suites. Screenshots use disposable fixtures, not production customer data.

## Compact view controls

Wrap pages that already own a `WorkspaceViewBar` with `withRecordViewHost`. The first record collection moves its shared tabs into that strip; redundant legacy record tabs are hidden from the strip while workspace-specific views stay available. Legacy specialized layouts remain reachable through the view catalogue. Nested preview tables retain their own controls and do not register over the page's primary collection.

Table and card adapters recognize page-owned open/preview controls and omit redundant generic preview buttons. Native tables with their own favorite and preview actions keep their original action column. Record counts remain in the footer; generic statistics render only when actual value aggregates are supplied.
