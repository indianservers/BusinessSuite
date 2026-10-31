# Full-page task collaboration workspace

## Navigation

Task titles and task rows open `/pms/tasks/:taskId`. Double-clicking also opens that page. Automatic hover previews are disabled on the Tasks list. Only the labelled **Quick preview** button opens the short read-only right pane; it contains summary metadata and an **Open Full Task** link.

The existing task creation form remains at `/pms/tasks/new`. Detailed editing remains available at `/pms/tasks/:taskId/edit`. The classic tools remain at `/pms/tasks/:taskId/classic`. Task-list query parameters and scroll position are retained when returning using the workspace's Back to tasks link.

## Collaboration features

- Rich-text progress notes, QA/daily templates, text drafts saved in the current browser, mentions, attachments, actual time logs, author identity and timestamps.
- Dated follow-ups with responsible people and completion/reopen actions.
- Paginated discussions with replies, author editing/deletion, reactions, thread resolution and unread counts.
- Watch/unwatch preferences and in-app notifications for updates, mentions, blockers and review decisions.
- Status workflow, manager review/rework feedback and immutable review decisions. Existing InternHub submission/review tools remain available for source-managed work.
- Explicit blocker reporting with category, severity, responsible person, assistance and attachments. Ordinary task updates do not show the blocker form. Open blockers prevent submission/completion and can be resolved or reopened.
- Editable/reorderable checklists and independently assigned subtasks, manual or checklist-derived progress, secure file uploads and image/PDF/video/log previews.
- Paginated activity history reusing the existing append-only PMS audit events. Removing a work note retains its audit trail and logged time.

## Database and access

Migration `20261031_047_task_workspace` adds task workspace state, updates/blockers/follow-ups, comment reactions, watcher preferences, read positions and a resolved flag on existing comments. It does not rewrite existing tasks, comments, attachments or time logs. Apply preceding migrations 045 and 046 if not already deployed.

Writes validate task/project/workspace permissions, assigned work access, mentioned identities and attachment ownership. Update revisions and task versions reject stale changes and retain client drafts. Rich text is sanitized server-side. Review and audit entries cannot be edited through work-note endpoints. Responsible people can finish their follow-ups/blockers without gaining edit rights over another author's note.

Restricted PMS users receive project context only for directly or collectively assigned tasks. Other task roots remain restricted. Collective batch eligibility checks expose only membership eligibility, not private HR records. Discussion parents must belong to the same task.

## Real-time behavior

The workspace reuses the existing authenticated task subscriptions. Persistent deployments use WebSockets; deployments configured for the existing durable database feed use its bounded event cursor. Restricted interns use the access-filtered database feed. This avoids reloading every task on a timer. Database-feed requests include the active task ID; event delivery checks record visibility and cursor advancement preserves skipped-event ordering. Subscriptions clean up on navigation. WebSocket delivery rechecks permissions and rejects unauthorized task presence/typing events. Vite's API proxy now supports local WebSockets.

The connection indicator reports transport state. Full per-person online presence with expiry is not added. Scheduled follow-up reminders are not added; follow-ups are persisted and their assigned people receive the existing in-app notifications.

## Verification and limits

- Backend workflow, stale-update, time-log, blocker, review, follow-up, reaction, unread/watcher, intern-scope and migration tests: `backend/tests/test_pms_task_workspace.py`.
- Existing task, general-task, My Work, employee-scope, company-boundary and real-time security regressions.
- `node qa/task_workspace_browser.cjs` checks the real disposable API and browser: explicit preview, full-page single/double click, progress/time, replies/reactions, follow-up completion, blocker resolution, review/rework, persistence, filter preservation and mobile layout. Screenshots are saved alongside this file.
- Scoped ESLint, TypeScript and production Vite build.

Local checks use isolated SQLite and QA users. Production PostgreSQL migration execution and deployment remain pending. Existing upload size limits remain in effect; no malware-scanning service was available, so scanning is not claimed. Pending local file selections are not saved into browser drafts. Discussion files are shared through the task's secure Attachments tab rather than a separate per-comment attachment relation.
