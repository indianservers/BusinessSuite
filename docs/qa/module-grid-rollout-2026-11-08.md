# Module grid rollout — 8 November 2026

Business Suite's native collection pages now share PMS Projects' compact table controls, field icons, grouping, configurable columns, saved layouts and record view presentation. This rollout adds domain column definitions, loaded-record status summaries, explicit percentage progress cells and date-backed Gantt schedules.

## Implementation

- Migrated 45 additional collections in 27 files across HRMS, Communication, CRM Tasks, AI Copilot, Business OS, Power Apps, SaaS, connectors, birthdays and payment requests. Existing cards and their permission-aware actions remain available; table and schedule previews render the original record content/actions.
- Added explicit domain default columns for onboarding, exits, benefit plans/claims, recruitment, assets/custody, learning, expenses, API logs, messages/events, tasks, approvals, reports, connectors, workflows, automations, templates, certificates, marketplace, notifications, modules, campaigns, forms and AI agents. Known optional display fields become columns when present. Arbitrary API properties and nested payloads do not become automatic columns.
- Added Table views to card collections, including icon headings, search/filter/group controls, column counts, sorting, ordering, resizing, pinning, saved layouts and previews through the existing grid implementation.
- Added PMS-style status summary strips. Local summaries use the filtered loaded dataset before grouping/pagination, so collapsing groups does not change totals. Server-backed grids retain backend matching totals and label local status counts as loaded records. No mixed-currency monetary totals are invented.
- Added accessible progress bars for actual Progress/Completion percentage fields. Unknown, out-of-range, custom/editor and unrelated percentage cells retain their original semantics.
- Added Gantt schedules for valid start/end field pairs. ISO and the suite's day/month/year dates are validated; missing or reversed ranges are excluded. Charts support horizontal scrolling, zoom, date labels, actual completion overlays and opening the original record/actions. Single-day ranges receive one date tick.
- Sales commercial lists now name the entity (Sales order, Contract, Engagement or Billing plan), and include their actual planned/expected dates and explicit progress when supplied. The Finance ledger action header now matches its body cells, allowing the shared grid adapter to operate correctly.
- Preserved the PMS Projects reference summary. Static matrices, calendars, editors, conversations and other specialized views retain their existing models.

## Scope and classification

Source coverage: 136 GridTable instances, 11 typed-grid instances and 85 GroupedRecords instances across 137 components. These are renderer instances, not unique pages.

The [full checklist](module-grid-rollout-checklist.csv) classifies every one of the 393 non-PMS destinations in the original source-derived inventory. It distinguishes shared collections, specialized/matrix/empty-state/redirected destinations, the three concrete CRM statistics worklists, and 29 standalone ERP source-catalogue entry points. Those catalogue links are not native Business Suite business-record grids; the separate Flask ERP application was not restyled by this React rollout.

Generic Gantt schedules are read-only: date changes remain in the owning record forms and existing module scheduling views. Dependency editing, date mutation, and progress measures are not inferred from unrelated fields or statuses. Existing specialized Gantt workflows remain intact.

## Validation

- Production build passed: TypeScript and Vite. Existing vendor annotation, mixed import and bundle-size warnings remain.
- Targeted ESLint passed across all 27 migrated files and the shared collection/grid files.
- `test-collection-model.cjs`: calendar validation, invalid/reversed ranges, progress bounds, status counts, default domain columns, filtered summary scope, and summaries before grouping/pagination.
- `test-column-presentation.cjs`: domain icon matching and preservation of custom/editable/unrelated percentage cells.
- `test-collection-rollout.cjs`: summary counts, invalid date exclusion, Gantt bars/zoom, original record actions from Gantt/table, table columns/progress, filtering, collapsed-group totals and desktop/mobile screenshots. Passed without browser runtime errors.
- `verify-module-grid-rollout.cjs`: 433/433 concrete routes passed browser smoke checks against the production bundle and disposable QA API. Exercised grouping on 181 routes; rendered group headers on 51; retained 18 matrix layouts. The fresh audit also checks visible column icons and opens populated generic Gantt views to validate bar bounds. An initial overloaded multi-page run was resumed with lower concurrency; all routes passed. This is route/render/grouping smoke coverage, not a claim that every page's business mutations were submitted.
- `qa/collection_grid_refresh_browser.cjs` retains the focused cross-module checks for icons/counts, column drag, keyboard resize, pinning, saved widths, reset and grouping.
- The source coverage audit reports zero unmigrated native tables. The three remaining tables in PMS AdvancedSchedulingPanel and ExternalDeliveryPanel now use the shared adapter.

## Evidence

- `outputs/module-grid-parity/pages.json` and `summary.json`: full route results.
- `outputs/collection-migrations.json`: each newly migrated collection and its owning file.
- `outputs/collection-rollout/checks.json`, `gantt-desktop.png`, `table-desktop.png`, `table-mobile.png`: focused interactions and visuals.
- `outputs/collection-grid-refresh/checks.json`: cross-module column controls.
- `outputs/suite-list-rollout/source-coverage.json`: renderer coverage with zero remaining native-table exceptions.

## Follow-up regression fixes

- Collection tables now include the route in their grid preference ID, preventing layouts/filters/saved views from bleeding between pages that reuse the same collection component.
- Record previews resolve the current record from refreshed items. Deleting a record closes its preview; changing route, user or company clears it. Table and Gantt preview interactions now count toward Frequent when personal views are enabled.
- Native header drops onto the originating column are no-ops; rightward drops now move to the target position instead of inserting before the adjacent target and leaving the order unchanged. Column resize defaults and ARIA values respect explicit numeric widths and the narrower selection-column minimum; pinned offsets use those same effective widths. Native tables are sized from their visible columns so browser stretching cannot enlarge cells beyond their configured widths and make pinned columns overlap.
- Gantt selects the first valid date pair per record instead of selecting one pair for the entire dataset. Blank generic dates no longer mask valid planned/expected ranges on the same record.
- Generated Quick tools headings receive the shared column icon.

Regression evidence: `outputs/collection-rollout/regressions.json` and `frontend/scripts/test-collection-regressions.cjs`. The focused browser checks exercise route layout isolation/restoration, current/deleted previews, Frequent tracking, self-drop ordering, explicit header widths, and selection resize bounds. The model suite includes alternate date-pair coverage. Existing collection interactions and cross-module checks are rerun separately; the fresh 433-route sweep covers the production rollout and follow-up fixes. The final directory search cleanup is covered by its focused route test and final build.

The follow-up patch passed the model/column suites, the focused collection interaction suite, all twelve browser regression checks, and the six-page real-data collection checks (PMS, CRM, HRMS, Sales, Finance, Inventory). The real-data drag test now selects columns by name rather than by an index that omitted the hidden selection-column handle, and clears stale QA search filters before checking populated groups. Targeted ESLint and whitespace checks passed. Production compilation evidence is retained in `outputs/collection-rollout/regression-build.log`.

## Final parity audit

- Fixed record-view host ownership: waiting collections become active when the current collection unmounts, and capability updates preserve ownership.
- Applied default hidden columns through the typed adapter and shared numeric/formatted progress-bar styling without overriding custom renderers.
- Added field icons to static matrix headers while preserving editable cells and totals. Migrated the remaining advanced scheduling and external delivery tables.
- Updated the live HRMS People Directory with Person, Email, Role, Status, Workspaces and Teams columns, status/role grouping and its original person preview. The table uses the existing page search. No unsupported progress or dates are invented.
- Enabled canonical From/To leave ranges and calculated plan ranges for Gantt views; visible date formatting remains intact.
- Final production build, targeted lint, model tests, collection interactions, twelve layout/preview regressions and parity checks passed. Evidence: `outputs/collection-rollout/parity-final-build.log`, `outputs/collection-parity/checks.json`, `outputs/collection-parity/directory.json` and `outputs/collection-rollout/regressions.json`.
