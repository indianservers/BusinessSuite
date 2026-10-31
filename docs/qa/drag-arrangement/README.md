# Suite drag and arrangement upgrade

Local implementation, 31 October 2026. No production deployment or production database migration was performed.

## Implemented and improved

### Project Management

- Project Board uses a movement threshold, supports cancel, shows server error reasons, and reloads canonical statuses and card positions after a move.
- Backlog and the new Sprint planning board use one transactional move-and-rank endpoint. Hidden siblings retain their ordering. Completed sprint history is locked. Within-list backlog reordering requires Rank sorting; moving between sprints remains available under other sorts.
- Tasks and My Work include arrangement boards for the current page. Tasks move between status groups; ordering is maintained within each project. Search and page limits remain explicit.
- Work Hub / Impact and Live Work now use accessible, persisted project tasks rather than the previous in-memory sample work cards. Existing task, timeline and workload routes remain available.
- Workload has an assignment board. Moving an assignment removes that individual assignment and adds the destination person, retaining other assignees, group responsibility and protected batch-controlled assignments. The server validates eligibility and notifications.
- Gantt move and resize handles now use pointer events, including cancellation. Existing date editors and dependency validation remain intact.
- Roadmap bars show movement feedback, support edge resizing and keyboard rescheduling, and serialize local dates without shifting a day in Indian time. Existing task dependencies remain managed by Gantt's dependency tools; arbitrary visual epic dependency rewiring was not added.
- PMS Files supports actual multi-file uploads, folder creation, folder moves and authenticated downloads. The previous metadata-only page was replaced. Folders are flat and scoped to a project. The page explicitly shows the latest 100 files.
- PMS Org Chart has a separate arrangement handle, pointer and keyboard positioning, saved workspace positions, bounded coordinates and revision checks. Moving the visual layout does not change access or reporting relationships.
- Existing calendar/planner rescheduling, dashboard move/resize/save, Notes folder moves and form field drag behavior were exercised. The shared form canvas now accepts palette drops when there is no question under the pointer.

### CRM

- Pipeline settings save stage order atomically, update both ordering fields, check the previous order and display failures instead of silently ignoring failed updates.
- Task priorities can be changed through a priority board using the existing task update API.
- Quote Builder has ordered line items with pointer, keyboard and button controls. Ordering survives reload and is used by quote/PDF line reads. Finalized quotes remain immutable.
- CRM Files now supports actual uploads, flat organization folders, conflict-checked moves and authenticated downloads. Existing record visibility and organization checks apply. The cabinet lists up to 200 accessible files.

### HRMS

- Recruitment has a persisted hiring-stage board and resolves candidate names from first/last names returned by the API.
- Onboarding template steps can be added and reordered. The persisted template order is used for future onboardings; existing employee checklists are not silently rewritten.
- LMS supports sections and lessons, section ordering and lesson transfers. Contents are stored in existing course metadata with revision checks; unrelated metadata is retained. Editors are loaded when a course is opened.
- Custom Fields now shows actual definitions with per-module persisted ordering rather than the previous placeholder page.
- HR Org Chart exposes explicit position reporting changes. Same-company validation, stale relationship checks and cycle rejection run on the server. This changes the position hierarchy, not employee access roles.
- The existing HR Workflow Designer retains its step execution model and gains reusable ordering controls, pointer support and cancellation. Adjacent workflow steps remain connected by their existing execution order; a new arbitrary graph execution model was not introduced.
- Shift Roster has pointer capture, a visible drag preview and slot highlighting. Click-to-select remains available. Drops continue through the existing review and draft-apply flow; nothing is automatically published.

### Shared tools

- Reusable handle-only movement controls include pointer and keyboard sensors, accessible Move menus, up/down buttons, busy states, error messages and saved-move announcements. Card targets take priority over containing columns during collision detection.
- Customization Studio has revision-checked section ordering and movement of fields between sections. Existing field properties and row identities are retained.
- The Notes block grip is now shared with formatted editors. Document Studio can rearrange body blocks and its field order before saving a template. This is flow-based document composition, not a new free-position print canvas.
- Existing Power Apps automation, approval and Shared Services node designers were retained. Their execution and publication models were not replaced.

## Database and access

Migration `20261031_048_drag_arrangement` follows migration 047. It adds quotation line order, PMS/CRM folder tables and nullable file-folder references. Existing files and quote lines remain intact; default line positions retain ID ordering until rearranged. Upgrade and downgrade were tested on isolated SQLite. Production PostgreSQL migration execution remains pending.

Domain mutations use the existing project, company, task, CRM and HR permission checks. Reorders require the complete scoped set and its previous order. Task arrangement checks task versions and uses a project lock. File moves validate their destination scope. Review, evidence and blocker guards are still enforced when dragging task statuses. Batch-controlled assignments cannot be removed through workload dragging.

The scheduling viewer regression fixture now establishes company membership and installs its catalogue before demoting the administrator to a viewer. Production authorization was not weakened to make that test pass.

## Verification

- Backend: 62 task/movement/security/realtime tests and 75 quote/calendar/Notes/forms/dashboard/roster/scheduling regressions passed. `test_drag_arrangement.py` includes migration preservation, atomic ordering, stale writes, scopes, uploads, curriculum validation, layout placement and reporting-cycle checks.
- TypeScript, scoped ESLint, production Vite build and `git diff --check` passed. Existing bundle-size/dependency annotation warnings remain.
- `node qa/drag_arrangement_browser.cjs`: real pointer and keyboard task movements, Sprint transfers, Backlog/Board, Gantt, recruitment, quote ordering, PMS/CRM uploads and folder moves, reload persistence and mobile layout.
- `node qa/arrangement_editors_browser.cjs`: course sections/lessons, onboarding/custom-field ordering, layout fields, chart positions, Roadmap keyboard changes, form palette drops and draft saving.
- `node qa/resource_assignment_browser.cjs`: workload reassignment and reload persistence.
- `node qa/existing_drag_browser.cjs`: Planner date drop, dashboard movement/resizing/saving, Notes folder drop, pipeline stage keyboard order, and roster drop/review/apply.

All browser scripts use only loopback port 1558 with disposable SQLite and synthetic QA users; the frontend preview uses port 5190. Screenshots `live.png` and `mobile.png` are illustrative QA captures.

## Remaining verification boundaries

The browser checks above do not certify every interaction in every role/browser. Full designer connection/save/publish flows in automation, approvals and Shared Services, CRM Leads/Calendar-specific native drag flows, and the CRM Gantt page were not re-certified end to end in this pass. Existing scheduling/quote/access regressions cover their shared backend contracts. Free-position print layout and arbitrary epic dependency rewiring remain separate additions, as noted above.
