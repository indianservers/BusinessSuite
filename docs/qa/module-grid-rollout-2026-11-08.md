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

Source coverage: 137 GridTable instances, 11 typed-grid instances and 86 GroupedRecords instances across 139 components. These are renderer instances, not unique pages.

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

## Visual comparison and remaining fixes

Compared native list/grid layouts with PMS Projects using full-reload browser captures at 1440×1000. Captures include grouped rows, card-to-table switches and populated generic Gantt panels. Screenshot sheets are a layout review; the interaction suites exercise the shared controls separately.

- Matched compact summary sizing, status-specific text/tinted icons, white table surfaces, header typography and narrow Favorite headings. Sales commercial create controls now use the Projects primary color and compact sizing.
- Loading placeholders no longer become records or receive misleading counts/group controls. Empty spanning-row worklists retain column controls, grouping, zero counts and their original empty-state actions. Matrices and editable forms retain native semantics.
- Missing accessor values no longer display the literal text `undefined`; numeric zero remains visible. Added known display-name/key aliases for Business OS, SaaS, Analytics and portal quote numbers.
- Corrected Sales record identity selection so a Sales order is identified before Customer. Long names now retain icon spacing and truncate without squeezing the icon or marking the Customer cell with the order's status.
- Confirmed grouped and load-more rows skip record-only priority rendering. The stricter production audit detects caught application error screens as failures, in addition to uncaught browser errors.
- Added a shared grid to Partner Commission Claims with Claim reference, Claimed amount, Currency, Notes, Created and Updated columns. Dates use the existing formatter; original permission-aware claim actions remain in the preview. Portal headings now distinguish Quote, Invoice, Project, Lead and Person.
- Fixed Enterprise Platform's indefinite skeleton when no password policy exists. It shows an explicit empty state and its Login Attempt Log grid; loading and fetch errors have distinct states.

Validation: the final full-reload route corpus passed 439/439 routes, including six added workspace routes; grouping was exercised on 215 routes and rendered on 144. Final Enterprise, Sales and workspace checks use production bundles. See `outputs/module-grid-visual-final-audit/pages.json` and `summary.json`. Captures are saved per route, with additional `-table` and `-gantt-*` images where applicable. Protected portal record layouts were checked separately with read-only synthetic API fixtures: seven customer/partner pages, including project completion/Gantt and original commission preview actions (`outputs/portal-grid-visual/checks.json`). Portal invitation/authentication and business mutations are outside this visual pass.

The production build and TypeScript check passed (`outputs/collection-rollout/visual-approved-build.log` and `visual-final-checked-bundle.log`). Targeted lint, model/icon tests, shared collection interactions, eighteen parity checks, twelve layout/preview regressions and six real module control checks passed. Physical header dragging, keyboard resizing, pinning, saved widths, reset and grouping are recorded in `outputs/collection-grid-refresh/checks.json`.

The disposable SQLite QA database was missing seven fields required by the existing Background Verification models. A consistent backup was created at `.local/grid-visual-before-bgv-20261108-184753.sqlite` before adding those fields. The register then passed with loaded records. No deployment database was changed.

The shared Workspace Directory List view now uses GridTable with its existing favorite controls, direct links and page search. It retains headers and column/group controls for an empty list. The adapter can disable its added personal views to avoid duplicate favorite columns. Workspace fixtures verify original favorites, direct links, grouping, resizing and empty-list controls; see `frontend/scripts/test-workspace-directory.cjs` and `outputs/workspace-directory-list.png`. Source coverage is 137 adapters, 11 typed grids and 86 card collections across 139 components, with zero unmigrated native page tables.

The five operational workspace routes needed the current backend routes, which were absent from the earlier running QA process. They were checked using an isolated API on a copied QA database (`outputs/serve-grid-visual-1598.py`), without restarting the existing API. Protected portal fixtures remain separately identified; production databases and portal invitations were not changed.


## Repeat running-app visual pass

Rechecked all 439 scoped routes in the running frontend. The pass began on port 5174; after intermittent module-loading/network-suspension failures, remaining routes were checked on an isolated current-source Vite instance on port 5311 using the copied QA API on 1598. No existing app or API process was restarted. Final result: 439/439 routes passed; grouping exercised on 221 routes, colored groups rendered on 149. Fresh route, table and applicable Gantt captures and results are in `outputs/module-grid-running-repeat`. ERP bridge destinations and protected portal access notices retain the scope limitations described above.

Found and fixed two missed native CRM card lists: Calls and Meetings now use the shared collection host with explicit columns, table/card/list views, grouping, column icons/counts, resizing and reordering. The original permission-aware editing, record links and follow-up actions remain accessible through previews. Meetings expose a read-only calendar-day Gantt from recorded start/end times; Calls do not invent an end date or completion percentage. Removed the extra nested page padding. Classic CRM Leads and Contacts create buttons now use the compact primary purple style instead of green.

`frontend/scripts/test-engagement-grid-visual.cjs` checks populated read-only conversation fixtures against the running app: column icons, Table view, grouping, keyboard resize, original preview actions, two meeting Gantt bars and no artificial Calls schedule. Evidence: `outputs/engagement-grid-repeat/checks.json`, `meetings.png` and `calls.png`. The six-module live drag/resize/pinning/persistence/reset/group expansion checks passed again (`outputs/collection-grid-refresh/checks.json`). TypeScript and targeted ESLint checks passed; production build logs: `outputs/grid-repeat-approved-final-build.log`. Collection model checks include recorded meeting time ranges.

The browser audit now waits for custom busy regions, skeletons and embedded-frame loading before capturing, reducing false passes on loading placeholders. Source inventory: 137 table adapters, 11 typed grids and 87 shared card collections across 140 components, with no unmigrated native page tables. These are rendering and grid-interaction checks, not business mutation acceptance tests.

The final table review also found AI Agent Configuration rendering generic blank cells for nested `agent` / `setting` records. Explicit Agent, Module, Status, Auto action, Approval required and Data access scope columns now read those records correctly, with Module/Status grouping and the original configuration form in previews. Calls/Meetings columns now use domain-specific phone, calendar, duration, direction, location and notes icons. Evidence: `outputs/module-grid-running-repeat/-ai-agents-config-table.png` and the extended `test-engagement-grid-visual.cjs` browser checks. Final TypeScript log: `outputs/grid-repeat-typecheck-confirmed.log`.
