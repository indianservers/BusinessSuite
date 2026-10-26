# Notes UX comparison and remaining work

Reviewed 26 October 2026 against the current Notes implementation and Evernote's public product documentation. This is an inventory of gaps found in this review, not a claim that every Evernote plan/platform has every feature. Evernote's signed-in web UI was not inspected. Items described as polish below are findings in our app, not independently verified Evernote capabilities.

## Added in this implementation

- Three independently scrolling panels; folder explorer and note list can collapse and resize.
- Real project/task/subtask navigation, private nested folders, contextual creation, keyboard tree navigation, saved expansion state.
- Click-and-drag note cards, including checkbox selections, to projects/tasks/folders.
- Folder drops before, inside, or after another folder; visible target feedback and hover expansion. Server validates ownership, scope, cycles, and versions, and updates sibling order atomically.
- Document block drag handle for paragraphs, headings, lists, tables, quotes, code, and images. Alt+Up/Down offers a keyboard alternative. Dragging ordinary text still selects text.
- Image/file drop and image paste into the editor; authenticated uploads and downloads.
- Rich icon toolbar, H1–H6, tables, checklists, colors, links, references, find/replace, selection toolbar, slash commands, focus mode.
- Search title/body/tags within scope; sorting, list/card/compact views, image thumbnails, pinned/favorite notes, context menus, bulk move/archive/Trash/restore.
- Autosave, optimistic concurrency, per-tab draft recovery, revisions, explicit revocable read-only sharing, attachments and PDF preview, templates, Markdown import/export, PDF export, print.
- Task Notes tab reuses the real PMS task; default privacy does not change with project membership.

## Highest-priority remaining interaction polish

1. Persistent Undo snackbar after a move/archive/Trash action. Editor undo currently covers document edits, while note management uses explicit restore/unarchive/move.
2. Ctrl/Cmd-click selection and Shift-click ranges in the note list; checkbox multi-select already works.
3. Touch/pointer drag handles for mobile/tablet and equivalent Move controls for every drag action. Current mouse drag uses native HTML drag-and-drop.
4. A live insertion line while dragging an editor block; current block drag highlights the document, while folder drops show before/inside/after feedback.
5. Multi-block drag, dragging nested list items independently, and Alt-drag to copy blocks. Current handle moves one complete top-level block.
6. Auto-scroll near the edges of the editor/tree during long drags; spring-loaded expansion is present for tree nodes.
7. Drag a folder back to a project/task/personal root. Current folder drops target another folder; notes can already target those root views.
8. Persist manual note ordering in a folder. Current list order is modified/created/title, with pins first; dragging note cards moves their folder association.
9. Keyboard shortcut help and a Notes command palette for creation, navigation, search, and moving items.
10. Arrow-key selection and focus management in the slash menu. Current filtered commands support Enter for the first match and mouse selection.
11. Tooltips with a consistent delay and a complete shortcut reference. Current toolbar uses accessible labels and native title tooltips.
12. Rich revision diffs and formatted history preview; current history preview is plain text and restores content as a new version.
13. Explicit sync/offline status, a reconnect queue, and cross-device local drafts. Current recovery is per tab/session; it is not an offline-first note store.
14. Keyboard announcements for completed moves, selection counts, upload progress, and recovery events; broader screen-reader and high-contrast validation.
15. Per-user persistence of view mode, editor width, sort, selected scope, and last-opened note. Panel sizes and tree expansion already persist; note URLs survive refresh.
16. Load/search pagination and virtualization for large libraries; current note lists are loaded together.
17. Better folder search that reveals matching descendants and their ancestors, including unloaded project tasks.
18. Consistent loading skeletons, cancel/retry uploads, and a clear multi-file progress queue.
19. Share dialog autocomplete, confirmed invitation state, and immediately updated privacy badges after the last reader is revoked.
20. Full export fidelity for complex tables, fonts, colors, checklists, and private images across Markdown/PDF/print. PDF export includes protected images; Markdown uses attachment references rather than packaging image files, and print currently shows image labels.

## Documented Evernote capabilities still missing or substantially narrower

### Search and organization

- Saved searches and reusable search shortcuts.
- Advanced filters by date, attachment type, and other note attributes; search operators and combined filters.
- Search suggestions and typo tolerance.
- OCR/handwriting search and indexing inside PDFs and Office attachments.
- Natural-language/AI note search with citations and strict per-user authorization.

Evernote documents these search capabilities on its [Advanced search page](https://evernote.com/features/search). Our current search matches title, body, and tags only.

### Capture and media

- Browser Web Clipper for full articles, selected content, PDFs, and screenshots.
- Source URL/author/capture metadata and annotated web captures.
- Document scanning and OCR workflows.
- Audio recording, transcription, and interrupted-transcription recovery.
- Image cropping and annotation directly in the editor.
- Formatted preview of an attached Markdown file; ours currently previews it as text.

Sources: [Web Clipper](https://evernote.com/features/webclipper), [Desktop and Web release notes](https://evernote.com/release-notes), and [feature overview](https://evernote.com/features). Capture extensions and scanning are adjacent workflows, not necessarily native actions inside every web client.

### Tasks and meetings

- Due dates, recurring tasks, reminders, and assignment directly within an inline note task.
- A task view grouped by note, assignee, or due date.
- Calendar event-linked meeting notes and event-driven note reminders.

The app currently has checklists, task references, and reviewed note-to-PMS-task creation. Extend those existing PMS records rather than building another task engine. Sources: [Evernote Tasks](https://evernote.com/en-us/features/tasks), [Calendar integration](https://evernote.com/en-us/features/calendar).

### Collaboration and connected knowledge

- Real-time co-editing, presence, and contributor feedback. Current invitations are read-only.
- Shared notebook/folder/space membership and inherited sharing policies.
- External guest/public sharing links with expiry and revocation. These should be explicit opt-in product choices.
- Connected calendar, Google Drive, Slack, Teams, and email capture workflows.
- Rich mentions of notes, folders, people, and spaces; current links are ordinary hyperlinks/references.

Sources: [Collaboration](https://evernote.com/en-us/features/collaboration), [feature overview](https://evernote.com/features), and [Desktop and Web release notes](https://evernote.com/release-notes). Availability depends on plan and platform.

## Additional product decisions and improvements

These are useful gaps in our implementation, not claims of verified Evernote Web parity:

- Dedicated tag browser, tag rename/merge, and nested tag organization.
- Note backlinks, linked-note previews, and a structured note-link picker.
- Outline/table of contents, collapsible heading sections, and heading navigation.
- Image resize/caption/alt-text editing and richer code-block controls.
- Reusable personal templates, template management, and an Evernote ENEX/HTML import path.
- Side-by-side notes, note tabs, and opening a note in a separate window with consistent editing state.
- Shared-note comments, review mentions, and activity history visible in the UI.
- Note locking/read-only toggle for the owner and encrypted sensitive blocks, if the product needs them.
- A configurable Notes home with shortcuts, pinned collections, scratchpad, and recent activity.
- Note reminders and notification settings that reuse Business Suite's existing notification system.
- Retention controls, bulk export packages, and visible storage usage.
- Internationalization, right-to-left editing, spellcheck controls, and print accessibility checks.

## Suggested sequence

First complete Undo, selection shortcuts, drag insertion feedback, touch accessibility, slash keyboard navigation, and persisted preferences. Then add saved searches, tag management, backlinks, outline, image controls, and export fidelity. Plan OCR, capture extensions, calendar integration, and live collaboration as separate features with their own permissions, storage, and operating-cost decisions.

## Validation

- 14 real-browser workflows passed against disposable SQLite with actual auth, Notes, project/task, attachment, and sharing APIs.
- 39 backend/rich-text/migration-chain checks passed; the Notes authorization suite was rerun after the final locking changes (16 passed).
- TypeScript check and production build passed.
- PostgreSQL migration 028 rehearsed upgrade/downgrade/re-upgrade on expiring copies of both production databases; existing note data was unchanged.
- Screenshots: [desktop](qa/notes-desktop.png), [mobile](qa/notes-mobile.png).
