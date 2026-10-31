# Optional WhatsApp style task experience

Open `/pms/tasks` and choose **WhatsApp style** in the top-right appearance switch. **Classic** remains the default. Preference and starred tasks are stored per signed-in user in this browser; `?theme=classic` and `?theme=whatsapp` explicitly select a view. `&task=123` opens a conversation directly.

The new view has a project/task navigator, message bubbles with replies and reactions, progress updates, follow-ups and blocker resolution, an existing rich-text mention composer, file uploads/previews, assignment management, checklist/subtask access, status changes, watcher controls, and activity. On wide screens the details panel opens alongside the conversation; narrower screens use an explicit details toggle. Full task links retain the existing workspace and its review controls. New Task retains the existing full-page creation flow.

Both appearances use the same scoped task, comment, task-workspace, attachment, checklist and assignment APIs. The existing task-list endpoint additionally accepts optional comma-separated `taskIds` (maximum 100 unique values), combined with its existing access restrictions, filters and pagination. No chat-specific records, parallel task models, new schema, or migration were added. Stars are a browser preference, not a shared task permission or workflow state. Existing production data was not modified.

## Verification

- `npm run build`: passed (existing dependency annotation and bundle-size warnings).
- Scoped ESLint for the new React components and final TypeScript check: passed.
- Task studio, task workspace and My Work backend suites together: 17 passed.
- `backend/venv/Scripts/python -m pytest tests/test_pms_my_work.py -q`: 7 passed, including task ID filtering, pagination, invalid IDs and an inaccessible task.
- `node qa/whatsapp_theme_browser.cjs`: passed against a disposable loopback SQLite QA server. Covers Classic default, switching/persistence, discussion/replies/reactions, progress, follow-up resolution, status changes, checklist, file upload, reload, and responsive navigation.
- `node qa/task_workspace_browser.cjs`: passed for the existing full task workspace: explicit preview, full page navigation, progress/time, discussion, follow-ups, blockers, reviews/rework, persistence, filters, and mobile.
- Screenshots: `desktop.png` and `mobile.png`.

The test task-studio fixture now explicitly depends on tenant bootstrap and middleware database setup so it also runs in isolation, independently of test collection order.

This is a local implementation; it has not been deployed to app.indianservers.com. Voice calling and video calling are not supplied by existing task APIs and no placeholder call buttons were added.
