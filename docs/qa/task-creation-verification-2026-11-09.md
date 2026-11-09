# PMS task creation verification

Verified the current checkout in Chrome at `http://localhost:5125/pms/tasks`.

- Opened Add Task and confirmed three form sections.
- Basic Info contains Assignees and Assign to me. Toggling self-assignment off removes Platform Admin; toggling it on restores the selection.
- Assignment Summary > Add more returns to Basic Info, expands the member picker, and focuses its search field. The selected person remains visible. The tested project had no additional eligible people in its search results; no memberships were changed.
- Copy from existing fetched four real tasks for the selected project. Selecting the Low-priority source populated `Copy of QA Live Priority Low 20261108`, changed the draft priority to Low, and preserved self-assignment. No task was submitted or existing task modified.

Automated browser regression: `node scripts/test-task-compact.cjs` passed against the actual React components with mocked API responses. Coverage includes self-assignment, member/group controls, Add more focus, project-scoped fresh task loading, empty-list reload, failed-request retry, copied fields with preserved assignments/dates, three sections, and desktop/768px/390px layouts. These failure/empty cases are simulated, not live backend failures.

The reported controls already had fixes in the current checkout. This verification found no additional production-code change necessary.
