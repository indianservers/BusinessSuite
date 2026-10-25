# Dashboard builder implementation — 24 October 2026

The dashboard page at `/pms/dashboards` now uses the supplied KaryaFlow mockup as its visual direction. The implementation runs against the existing API and database; screenshots contain records created in an isolated local QA workspace.

## Delivered

- Library with All, Mine, Organization, Private, Shared with me, Favorites, Recent, Archive, and Trash; search, grid/list presentation, duplication and ownership controls.
- Four-step creation: identity and sharing, one of 15 templates or blank canvas, data scope, review and create.
- Six real KPI cards, task creation/completion trend, status donut, project progress, sprint commitments, open tasks, activity and deadlines in the default template. Estimated hours replace utilization because utilization cannot be inferred from assignment counts.
- A 12-column canvas with drag, resize, locking, hiding, showing, duplication, removal and position reset. Saved desktop coordinates are preserved. Tablet and phone layouts derive non-overlapping rows without rewriting desktop coordinates. Touch users can configure size or use Move earlier in widget menus.
- Undo/redo, keyboard shortcuts, preview, explicit server saves, local draft recovery and unload protection. Server revision checks reject concurrent stale saves with HTTP 409 and preserve the draft. Local drafts are recovery aids, not cross-device backups.
- Widget configuration for title, description, approved icon, data source, supported metric, aggregation, grouping, limits, sorting, color, legend, grid, labels, tooltips, dimensions, locking, numeric formatting and filter overrides, where relevant.
- Filters for projects, task and project status, priority, assignees, teams, sprints, tags, exact custom field value, timezone and date range. Named presets persist with configuration.
- Authenticated private, selected member, workspace and organization sharing. Selected users have viewer/editor access; only the owner changes sharing, transfers ownership, archives or deletes. A shared definition never grants access to its underlying project records.
- Configuration history with up to 30 previous versions, editor and save time. Restoring history changes the dashboard definition only. Trash is recoverable; permanent deletion requires exact name and current revision.
- Guided natural-language template suggestions and optional integration with the existing configured assistant providers. Provider mode reuses encrypted configuration, AI permissions, module policy, redaction, rate limiting, validation and usage logging. No project rows are sent to the provider. Generated record IDs, notes and URLs are removed. Preview and explicit Save are required. Provider integration is tested with a controlled adapter; no paid external provider call was made during QA.
- Dashboard/widget CSV with formula-injection protection, PNG capture, browser print/save-PDF layout and presentation mode. CSV and PNG downloads were exercised in the browser.
- Real calendar month navigation, project date timeline preview, numeric histograms, one-dimensional pivot summaries and Markdown notes. Notes support headings, bold, italic, code and lists; HTML remains text.

## Widget and source coverage

There are 100 catalog entries, of which 82 have connected rendering/query paths and 18 show explicit unavailable states. See `widget-catalog.json` for each entry's source, visualization and requirement.

Connected sources are authorized PMS projects, tasks, time logs, activity, sprint commitment/completion snapshots, milestones and risks. Time logs remain personal for non-administrators. Budget data requires workspace Owner/Admin access and is reported in stored source units without currency conversion. Generic datasets use approved ORM fields and aggregations; there is no arbitrary SQL or executable formula evaluation.

The 18 unavailable entries cover capacity/utilization, numeric health scoring, baseline comparison/forecasts, historical burndown/burnup/flow/lead/cycle data, WIP limits, dashboard checklists, OKRs, heterogeneous custom-field charts and generated AI insights. Their prerequisites are shown in the library and canvas. They are not reported as finished metrics. A generic histogram also requires a selected numeric metric.

## Storage and files

No dashboard database migration is required. Existing `PMSWorkspaceEntry` records remain compatible with `dashboard_v1`. Configuration, sharing and revisions are stored as validated JSON; history and preferences use separate entry kinds excluded from ordinary workspace chat/note feeds. Compare-and-swap checks protect concurrent edits. Production frontend and backend must be released together.

Primary backend files:

- `backend/app/apps/project_management/dashboards.py`
- `backend/app/apps/project_management/dashboard_config.py`
- `backend/app/apps/project_management/dashboard_engine.py`
- `backend/app/apps/project_management/dashboard_suggestions.py`
- `backend/tests/test_pms_dashboard_builder.py`

Primary frontend files:

- `frontend/src/apps/project-management/pages/DashboardsPage.tsx`
- `frontend/src/apps/project-management/dashboard/model.ts`
- `frontend/src/apps/project-management/dashboard/DashboardWizard.tsx`
- `frontend/src/apps/project-management/dashboard/Panels.tsx`
- `frontend/src/apps/project-management/dashboard/WidgetContent.tsx`
- `frontend/src/apps/project-management/dashboard/builder.css`
- `frontend/package.json` and lockfile: react-grid-layout 1.5.4, corresponding types and html-to-image.
- `playwright/pms-dashboard-builder-live.spec.ts` and the dashboard/commercial Playwright configurations.

The earlier suite design-system, shell, navigation, search, profile, status and mobile work is summarized separately in `README.md`.

## Verification

- TypeScript, ESLint and production build pass.
- Seven dashboard backend tests pass: compatibility, permissions, organization boundaries, selected editors, source restrictions, save conflicts, history, validation, 50 widgets, all connected source paths with seeded records and provider preview isolation.
- Ten browser regression tests pass against real local API handlers: commercial invoice workflow, assistant approval, dashboard creation/edit/save/reopen/CSV, drag/resize/conflict/drilldown/history/guided preview, task interaction/guest restrictions, premium workspace interactions, missing-record handling, recovery and admin soft-reset.
- A focused rerun additionally exercises actual PNG download and mobile card bounds.
- Six dashboard scans at widths 1672, 820 and 390 in light/dark have zero detected WCAG A/AA violations, page overflow, overlapping widget rectangles or page exceptions. See `dashboard-accessibility.json`. This is automated coverage, not a claim of exhaustive accessibility certification.
- Fifty KPI widgets over eight real QA tasks returned correct values in three loopback requests: 13.3 ms, 12.6 ms and 10.9 ms. This is a small local SQLite check, not production load certification. Data loading is batched and cached by approved source/project scope within each request. Sources cap at 10,000 records and request narrower scope beyond that limit. Dashboards cap at 50 widgets.
- Existing build reports large main/local-model chunks and an outdated Browserslist dataset. Python tests report existing dependency/deprecation warnings. No failing test remains in the dashboard verification runs.

Reproduce with the isolated QA API (`SUITE_UI_QA=1`, `COMMERCIAL_QA_DATABASE_NAME=businesssuite-commercial-ui-v2.db`), Vite on loopback port 5191, generated suite/commercial harnesses and `npx playwright test --config playwright.commercial-audit.config.ts`. `check-dashboard-ui.cjs` expects `@axe-core/playwright`, supplied through `AXE_PLAYWRIGHT_MODULE` when installed outside the repository.

## Actual UI captures

- `dashboard-light-1672.png`, `dashboard-dark-1672.png`
- `dashboard-light-820.png`, `dashboard-dark-820.png`
- `dashboard-light-390.png`, `dashboard-dark-390.png`
- `dashboard-builder-desktop.png`, `dashboard-builder-mobile.png`

## Remaining limits

- The 18 unavailable catalog entries need additional integrations or persisted historical/capacity data.
- Pivot is a grouped summary, not a multi-axis spreadsheet engine. Notes use a safe Markdown subset rather than a full document editor. Generic tables expose approved common fields rather than arbitrary relational joins.
- Exports are CSV, PNG and browser print/PDF; native XLSX and scheduled/email reports are not implemented here. Remote images must permit browser CORS for PNG capture. Widget CSV respects the configured record/group limit; drilldown is limited to 100 rows.
- Comparisons need explicit dates and nonzero baseline data. Missing completion/due timestamps are excluded from eligible on-time measurements. Current status is never substituted for historical transition data.
- Desktop supports free placement; narrower screens prioritize readable derived layouts and use settings/menu controls rather than pointer drag.
- Paid-provider connectivity and production-scale load remain unverified. Changes are local; this work has not been committed, pushed or deployed.
