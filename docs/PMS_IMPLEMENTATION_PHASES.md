# PMS implementation phases

Date: 2026-10-23. Scope: the non-LLM gaps identified in the ClickUp comparison.
Existing uncommitted work is preserved. Completion means persistent behavior,
backend permissions, usable UI and relevant verification, not a route or mockup.

## Phase 1 — trustworthy configuration and core work

- Navigation: replace misleading destinations with the actual supported feature;
  retain workspace, project, view and return context.
- Settings: remove unsaved controls; expose only settings with implemented behavior.
- Custom fields: typed project definitions and task values, then field lifecycle,
  required validation, create-task integration, table columns/filtering and scope.
- Workflows: configurable ordered statuses and categories used consistently by
  boards, task forms, automation and reports, with transition validation.
- Recurrence: editable schedules, occurrence generation, timezone/end conditions,
  duplicate prevention and recovery tests.
- Task experience: shared field components and consistent drawer/detail actions;
  improve inline editing, column controls and saved view behavior.
- Practice workflow: client/service/period/preparer/reviewer/billing information.

### Implemented in the first slice

- Added persisted project custom-field definitions and task values for text,
  number, date, checkbox and dropdown.
- Added server permission checks, project isolation and value validation.
- Added the same field editor to full task details and the workspace drawer.
- Replaced generic unsaved settings checkboxes with links to existing management
  screens and explicit descriptions.
- Added SQLite and PostgreSQL migration revisions for the new tables.

### Remaining in Phase 1

Required fields, field edit/archive and audit events, field-aware task creation,
list filtering/columns, configurable workflows, recurrence execution, navigation
cleanup and the remaining task-view consolidation are not complete.

## Phase 2 — team execution and operational visibility

- Teams with aliases, icons, membership, assignment and sharing semantics.
- Automation: expanded triggers/actions, conditions, editable rules and execution
  failure/retry history.
- Dashboard builder: saved widgets/layouts/filters, drilldown, sharing and export.
- Structured templates: subtasks/checklists/fields/relative dates and target project.
- Intake designer: typed/conditional questions, files, routing and submissions.
- Planner: day/week/agenda, duration, time blocking and rescheduling.
- Time/resource planning: timer verification, dated capacity, schedules, holidays,
  effort allocation, approval and billing export.
- Unified personal work, watcher/reminder and notification workflows.

## Phase 3 — collaboration, integrations and administration

- Private DMs, channels, threads, unread state, reactions, attachments and pins.
- Collaborative documents and whiteboards; media recording/calls evaluated as a
  separate infrastructure capability.
- Calendar/mail connectors, connection lifecycle and delivery health, generic
  outgoing webhooks, imports with mapping/dry run and workspace exports.
- Shared-platform security audit and implementation of SSO/2FA/session policies,
  custom permissions, access requests and private sharing enforcement.
- Trash coverage, deleted-by metadata, bulk restore and retention/purge semantics.
- Accessibility, mobile, role/tenant isolation, concurrent updates, network failure,
  data-volume and recovery verification across all completed capabilities.

## Verification and rollout

The first slice has targeted backend field-validation/access tests and a browser
test using mocked API persistence. These do not replace deployed database and
live browser acceptance checks. Apply the migration for the database deployment
before enabling the new custom-field API in that environment. No production
migration or deployment has been performed by this slice.


### Phase 2 first slice

Implemented workspace Teams with unique aliases, collaborator membership, create,
edit, search and backend role/workspace isolation. Teams do not grant access or
expand task assignments yet; icons, team assignment and sharing remain pending.
Automation rules can now be edited and duplicated; duplicates start paused and
editing preserves the rule's existing enabled/paused state. Execution actions
remain priority and assignee updates. Dashboard builder and other Phase 2 work
are still pending. Team migrations are included for both database tracks but no
production migration or deployment has been performed.


### Phase 3 first slice

Implemented one-to-one direct conversations scoped to a workspace. Conversation
and message records persist; only current participants can read messages, and
admins have no participant bypass. Sending requires both people to remain active
non-guest collaborators. Client request IDs make retries idempotent. The UI
supports collaborator selection, conversation search, per-conversation drafts,
recent-message polling and loading earlier history. It is accessible from shared
chat and Settings and preserves the originating workspace.

Channels, threads, reactions, attachments, unread counts/notifications, document
collaboration, external integrations, security policy administration and broader
recovery/scale work remain pending. No production migration or deployment has
been performed. Database migration revisions are included for both tracks.


### Task type manager increment

Added organization task type definitions with categories, descriptions, icon/color,
default priority, accessible active-task usage, archive/restore and recommended
presets, including practice-specific work. Task creation loads active definitions
and applies the chosen type's priority in the form; the backend rejects unknown
or archived types on creation and explicit type changes. Existing task types are
preserved when archived. Names remain immutable identifiers. This does not yet
provide type-specific custom fields, required-field rules, transitions or
conversion of a classified task into another module's business record. Migration
revisions are included; no deployed database migration has been performed.


### Persisted time tracker increment

Time Tracking now includes a server-backed timer with project/task selection,
notes, billable flag, refresh, stop/save and confirmed discard. A user has one
active timer; session keys protect stale requests and repeated stop requests
return the saved log instead of duplicating it. Stop creates a standard time log
and activity in the same transaction. Duration rounds up to whole minutes and
is attributed to the start date in the stored browser time zone. Manual entry
also accepts durations such as 3h 20m. Timer migrations are included for both
tracks; deployment has not been performed. Global toolbar timer controls,
time-entry tags and additional weekly timesheet UX remain separate work.


### Project Docs increment

Added saved project documents, Markdown editing and safe preview (headings, lists,
checklists, quotes, links, code and tables), task linking, Markdown export,
Ctrl+S, word count, unsaved-change warnings, version history and revision loading.
Saves use an atomic version condition to reject stale writers without overwriting
the newer content. Revision content is immutable and restoring creates a new
version on save. Project permissions are checked on document/history operations.
Both migration tracks are included; no deployed migration has been applied.

This is not full Google Docs or Sheets parity. WYSIWYG editing, simultaneous
coediting, comments/suggestions, granular sharing, nested wiki pages, print/PDF
and Office import/export, spreadsheet formulas, calculation, charts, pivots,
data validation and automation remain pending.


### Subtask management increment

Existing subtasks already support nested children, independent task detail,
completion/reopening, priority, due date, story points, deletion and progress.
Added multiple collaborator assignments during creation and inline editing,
explicit parent-assignee inheritance, descriptions, search and completion
filters, persisted up/down ordering and promotion to a standalone project task.
Reordering checks project permissions and requires every current child exactly
once. Promotion preserves nested children. Clearing a due date now sends null.

Not full ClickUp parity: inline expandable multi-level trees, bulk operations,
recursive duplication, date shifting, descendant effort rollups, automatic parent
completion rules and drag/drop reparenting remain pending.
