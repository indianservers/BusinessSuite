# Shared productivity UI

## Integration references in Power Apps

Calendar, Notes, Tasks and Workflow Automation are available as integration references. Each reference explains host requirements and links to PMS when the user has access. References do not load PMS records, create drafts or install subscriptions. Studio environments do not create separate copies of PMS data.

`references.ts` exports the catalog and `ProductivityIntegration<Record, Column, Action>` contract. Generic types preserve the receiving application's full records and columns. This is an integration contract, not an executable adapter. Hosts implement APIs, persistence, tenant scope and server authorization.

To integrate another application:

1. Use the referenced source as the behavioral starting point and reuse shared presentation where appropriate.
2. Supply host records, columns, statuses, assignments, actions and linked entities through an explicit adapter.
3. Connect persistence, attachments, notifications, realtime and workflow triggers/actions. Verify tenant boundaries and business rules before enabling writes or execution.

PMS remains the integrated implementation. Its database columns, task columns, saved views, calendar settings, note persistence and workflow subscriptions are preserved. The PMS Workflow Automation reference is separate from the existing Power Apps Automations builder.

`NoteEditor` is the single rich notes editor used by PMS and CRM. It includes block dragging, slash commands, formatting, tables, outline and focus mode. It has no module API dependency. Pass `value` and `onChange` to use it in another module. Optional attachment/reference callbacks enable host-specific features.

PMS keeps its existing `NoteRichEditor` import as a thin adapter that injects `PrivateNoteImage`. PMS owns attachment loading and all existing note persistence. PMS tasks are unchanged.

`ProductivityWorkspace` provides the CRM notebook/list/editor shell and task arrangement UI. It starts empty and stores drafts under the host-provided `storageKey`, scoped by module and user. Its browser drafts never fetch or mutate CRM/PMS records. Hosts must remount it with `key={storageKey}` when switching user or storage scope.

CRM uses `workspaceView=notes|tasks` for its inner view. The suite reserves `operation` for top-level activity tabs; keep `operation=/crm/tasks` when switching between the two inner views.


`NotesWorkspace` provides the three-pane notes presentation for hosts with browser-local records. The explorer, note cards, search filters, tags, templates, editor, and styles are shared with PMS; the PMS components remain thin adapters around their existing API calls. `NotesExplorer` receives `loadProjectTasks` from its host rather than importing a module API. CRM supplies no projects or task loader data and uses its own storage namespace, including saved searches. Previous CRM browser notes are carried forward once; PMS notes are never read or copied.
