# Workflow Board live verification — 8 November 2026

All six module dashboards passed against the running application and its real local database. No API responses were mocked or intercepted.

- **36 dashboard checks passed:** real records rendered; team and owner filters matched recorded assignments; date boundaries were inclusive and excluded undated records; column drill-downs respected filters; cards opened their actual records. All six mobile checks found no page overflow.
- **Six branch checks passed:** switched from writable branch 6 to read-only branch 1 through the actual confirmation flow. Branch choice persisted, records changed with scope, and stage controls were hidden.
- **Six workflow checks passed:** CRM Qualification → Discovery; HR Applied → Screening; PMS To Do → In Progress (and subsequent review transitions); SRM Draft → Approved → Confirmed; Finance's five calendar ageing buckets with manual moves disabled; Power Apps approval by a separately assigned reviewer, self-approval denied, and Approved status with verified audit evidence.

The dashboard sample contained 141 CRM deals, 74 candidates, 1,000 loaded PMS tasks, 124 sales orders, five temporary outstanding references, and one approval. PMS's 1,000-record limit is disclosed in the UI; counts and totals cover loaded records.

## Fixes verified

- Added a compact, access-scoped PMS dashboard projection to avoid repeated full navigator requests and the observed timeout/rate-limit pressure.
- Returned canonical task destinations when a project has no enabled custom workflow; retained configured transitions and approvals when one is enabled.
- Added permission-gated SRM submit and confirm actions using the existing document lifecycle endpoints.
- Gated CRM stage controls by central branch edit access as well as record permissions.
- Excluded generated Playwright trace/report HTML from Vite's watcher, preventing unrelated test artifacts from reloading active app sessions.

Production build, TypeScript check, scoped ESLint, Workflow Board unit/browser regressions, and two targeted PMS backend tests passed.

## Environment and limitation

Initial six-dashboard filter/link checks used `http://localhost:5125`. Additional live checks used isolated app instances on ports 5197 and 5198, including the production build, with the same real backend on port 1534 and the same database. This avoided concurrent development-server restarts and source reloads.

The local setup has no continuously running Power Apps automation worker. The tagged approval was processed through the production worker functions restricted to that request's run ID. A continuous worker remains required for normal automatic approval progression.

## Cleanup

Removed the five temporary outstanding references (no vouchers or allocations), removed the test candidate, soft-deleted the tagged operational fixtures, cancelled their draft billing plan/milestone, disabled both test policies, revoked all three temporary users and their sessions, and removed their saved passwords. The completed approval and audit trail were retained as evidence. The running app's Finance board was checked again with zero outstanding test records.

Evidence: [dashboard checks](results.json), [branch checks](branches.json), [workflow checks](stages.json), [cleanup](cleanup.json).
