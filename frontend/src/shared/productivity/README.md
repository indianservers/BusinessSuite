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

All Suite module menus open `/pms/notes`, and their Create menus use `/pms/notes?new=1`. PMS owns the single Notes UI and API persistence. CRM's legacy `workspaceView=notes` entry and Power Apps' `/power-apps/notes` entry redirect to that workspace. Existing browser-local drafts are left in storage; they are not copied into or merged with server notes.

New notes stay inside that persistent workspace. Autosave assigning a temporary
or server ID must not replace an editor window or remount its text fields.

`NotesWorkspace` remains a reusable presentation for existing browser-local hosts and fixtures. Suite module navigation must use the shared Notes route rather than mounting a separate notebook.

`NoteCloudSave` adds **Save to cloud** to Notes and the reusable CRM editor. It
copies a note to the caller's connected Google Drive or OneDrive account in HTML
or plain text, with an explicit folder choice. Accounts are limited to the current
company and the user who connected them; source-module export permission is
required. **Connect Google Drive** and **Connect OneDrive** open OAuth consent
directly from Notes in a popup. The editor and unsaved drafts stay open; only a
matching popup origin, window and request identifier can refresh/select the new
account. Personal Notes accounts remain hidden from company storage Settings and
cannot be used through company administration APIs. Callback handling rechecks
company membership and export permission and never sends provider tokens to the
browser. For PMS, the
backend reads the owned saved note and verifies its version rather than trusting
browser-supplied note content. Copies are downloaded again and checksum-verified
before reporting success. The original note stays in its existing storage;
attachments are not bundled, and future edits are not synchronized automatically.

Shared Notes save their original content to the ERP database before creating a
Drive copy. Note attachments can use the owner's Google Drive connection from
Notes without configuring a company storage route. They upload to My Drive;
after verification and database commit, temporary server bytes are removed.
The database keeps the attachment metadata and cloud locator, with an empty
attachment body. Other project uploads continue to use company storage policy.
