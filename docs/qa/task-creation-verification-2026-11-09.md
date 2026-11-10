# PMS task creation verification

Verified the current checkout in Chrome at `http://localhost:5125/pms/tasks`.

- Opened Add Task and confirmed three form sections.
- Basic Info contains Assignees and Assign to me. Toggling self-assignment off removes Platform Admin; toggling it on restores the selection.
- Assignment Summary > Add more returns to Basic Info, expands the member picker, and focuses its search field. The selected person remains visible. The tested project had no additional eligible people in its search results; no memberships were changed.
- Copy from existing fetched four real tasks for the selected project. Selecting the Low-priority source populated `Copy of QA Live Priority Low 20261108`, changed the draft priority to Low, and preserved self-assignment. No task was submitted or existing task modified.

Automated browser regression: `node scripts/test-task-compact.cjs` passed against the actual React components with mocked API responses. Coverage includes self-assignment, member/group controls, Add more focus, project-scoped fresh task loading, empty-list reload, failed-request retry, copied fields with preserved assignments/dates, three sections, and desktop/768px/390px layouts. These failure/empty cases are simulated, not live backend failures.

The reported controls already had fixes in the current checkout. This verification found no additional production-code change necessary.

Rechecked on 2026-11-09: the Chromium regression passed again on the current checkout at 1440px, 768px, and 390px. Reviewed the refreshed desktop screenshot. This repeat used mocked API responses; no real task was created. No additional production fix was needed.

Latest requested recheck: Chromium regression passed again, including added assertions that copying fills work type, priority, and description, and that self-assignment is unavailable when the current user is absent from eligible project members. TypeScript `tsc --noEmit` passed. The current localhost:5125 application was not listening during this recheck; the browser used the actual TaskStudioPage in the Vite fixture at localhost:5174 with simulated API responses. No new production defect was reproduced or production code changed.

Rechecked on 2026-11-10 for the reported assignment and existing-task controls: the isolated Chromium regression passed in both modal and standalone creation, including a 390px initial standalone viewport and responsive checks at 390px/768px. Self-assignment, Basic Info members, Add more focus, task loading/copying, single-flight loading, empty reload, failed-request retry, and assignment/date preservation passed. localhost:5125 was not listening; API responses were simulated. No additional production defect was reproduced or production fix made during this recheck.
