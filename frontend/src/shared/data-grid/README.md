# Shared data grid

Import `SharedDataGrid` and its types from `@/shared/data-grid`. CRM Deals is the first integration; other module pages remain unchanged.

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
