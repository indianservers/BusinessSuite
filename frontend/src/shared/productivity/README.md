# Shared productivity UI

`NoteEditor` is the single rich notes editor used by PMS and CRM. It includes block dragging, slash commands, formatting, tables, outline and focus mode. It has no module API dependency. Pass `value` and `onChange` to use it in another module. Optional attachment/reference callbacks enable host-specific features.

PMS keeps its existing `NoteRichEditor` import as a thin adapter that injects `PrivateNoteImage`. PMS owns attachment loading and all existing note persistence. PMS tasks are unchanged.

`ProductivityWorkspace` provides the CRM notebook/list/editor shell and task arrangement UI. It starts empty and stores drafts under the host-provided `storageKey`, scoped by module and user. Its browser drafts never fetch or mutate CRM/PMS records. Hosts must remount it with `key={storageKey}` when switching user or storage scope.

CRM uses `workspaceView=notes|tasks` for its inner view. The suite reserves `operation` for top-level activity tabs; keep `operation=/crm/tasks` when switching between the two inner views.


`NotesWorkspace` provides the three-pane notes presentation for hosts with browser-local records. The explorer, note cards, search filters, tags, templates, editor, and styles are shared with PMS; the PMS components remain thin adapters around their existing API calls. `NotesExplorer` receives `loadProjectTasks` from its host rather than importing a module API. CRM supplies no projects or task loader data and uses its own storage namespace, including saved searches. Previous CRM browser notes are carried forward once; PMS notes are never read or copied.
