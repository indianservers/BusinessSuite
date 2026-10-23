# PMS production audit — 23 October 2026

Site: https://businesssuite-rosy.vercel.app/pms

## Incident and repair

Reproduced HTTP 500 responses on task custom fields, the custom-field manager,
task types, timers and documents. Production logs reported missing tables,
including pms_task_types and pms_custom_fields. The database remained at
pg_20261022_004. Seven newer migrations referenced nonexistent predecessor
revisions, preventing Alembic from constructing its graph.

Repaired both migration chains. Added a production build migration runner that
uses a PostgreSQL transaction and advisory lock, requires a provisioned baseline,
upgrades to the graph head and verifies the resulting revision. A failure fails
the build. Preview builds skip migration; request handlers and serverless cold
starts do not perform schema changes.

Vercel logs confirmed production upgraded through pg_20261023_007. A second
deployment verified that rerunning at the current revision succeeds without
changes. Corrected the attachment panel's misleading 25 MB claim to state the
hosted 3 MB limit.

Final deployment: dpl_EuohW1WjqW9NvpdizGM41xPXuBVQ, READY and aliased to the
production domain. An isolated snapshot of the released source plus this repair
was deployed. Concurrent, unrelated local edits were excluded.

## Completed verification

- 83 authenticated read endpoints returned HTTP 200. The sweep excluded 16 routes
  requiring additional resource IDs, tokens, downloads or event-stream handling.
- 50 secondary UI destinations rendered in live Chrome. Also exercised the main
  workspace Board, List, People, Calendar, Workload and Activity views. These are
  render checks, not certification of every control on every page.
- Created a task through the live New > Task form. Its status update persisted
  and moved it into the workspace board's In Progress column.
- Created a custom field through the task drawer, saved its value, then verified
  it in full task details after reopening.
- Live write checks passed for subtasks, dropdown fields, field renaming,
  invalid-value rejection (422), used-option protection (409), document revisions
  and history, stale-write rejection (409), timers and idempotent stop retries.
- Generated audit text uploaded (201), downloaded (200) and matched its bytes.
- Created a checklist item through task details and verified the activity entry.
  Exercised task Activity, Time Logs, Files, Linked Tasks, Development and History.
- Guest access returned 404 for an inaccessible workspace and 403 for task edits
  and custom-field creation.
- The isolated PMS backend group passed 58 tests. Two migration regression checks
  also passed: graph integrity and repeated upgrades preserving an existing task.
  Local fixtures use SQLite; production migration ran on PostgreSQL.

Evidence is in qa/pms-production-audit-2026-10-23. UI-only actions and the first
subtask POST are not all represented in the write-workflow JSON.

## Remaining scope and findings

- Product Launch, Impact Work Hub / AI Planner and parts of Timeline Plus contain
  sample or browser-local planning data. Rendering does not certify shared,
  server-persisted planning workflows. Those require separate implementation.
- Several navigation entries intentionally open shared Workspace Tools, Software
  Delivery or Task List pages; aliases are not separate feature implementations.
- No outbound chat, comments, invitations, emails or webhooks were sent to other
  users. Permissions, external accounts, billing and destructive administrative
  actions were not exercised.
- Paid integrations, identity-provider flows, simultaneous multi-user editing,
  load testing, exhaustive invalid inputs, every permission combination and live
  mobile-device behavior remain unverified.
- Board, Milestones and Time Tracking initially exceeded short selector waits.
  Each rendered on individual retest. No latency SLA was established.

Audit records were retained in the pre-existing audit workspace for inspection.
The main verification task is /pms/tasks/16 (PA2-1722). Records include one
nonbillable minute, a document, a subtask, a checklist item, two custom fields and
an audit text attachment. Existing user work was not deleted.
