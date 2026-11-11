# Create menu real API verification — 11 November 2026

Result: **139/139 checks passed**. 125 save flows returned successful real API responses and passed a separate authenticated GET readback. 14 checks cover view/navigation actions.

The production frontend ran against real FastAPI endpoints and a fresh disposable SQLite database built from current ORM metadata. No Playwright API interception or mocked API responses were used. QA records use CREATEQA identifiers. Outbound delivery workers were disabled; email and campaign checks saved server drafts only.

Desktop: 1440 × 950. Mobile responsive viewport: 390 × 950. Chromium, Asia/Kolkata, QA administrator. This does not certify physical phones, every browser, production infrastructure, or other permission roles.

## Coverage

- PMS: 53 passing checks.
- CRM: 64 passing checks.
- HRMS: 22 passing checks.

The PMS board exposes one extra desktop-only action, Add existing person. All actions present in each discovered menu were checked.

## Behavior boundaries

- List opens the existing task list. PMS Reminder opens Tasks & Follow-ups. CRM Dashboard opens reporting. CRM Tag opens the Relationship Hub for record tags; these actions do not create independent entities.
- Whiteboard arranges existing records in a personal browser layout. Card movement and layout persistence after reload were verified; it has no standalone whiteboard record API.
- Page uses the Notes editor. Space uses the workspace editor. Sheet, Artifact and Clip attach actual CSV, text and recorded WebM files through Files; there is no native spreadsheet editor or clip recorder in this menu.
- Email and Campaign save server drafts. No email/campaign was sent. Invitations were created with reserved QA addresses with delivery workers disabled.
- HR checks include guided employee save, actual CSV import preview/commit, attendance correction and UTC round-trip, leave submission, tickets, expenses, certificate upload, letter PDF preview/issue, forms and assets.

## Issues fixed during verification

- Completed the shared PMS board menu and blocked it while permissions/context load.
- Fixed navigation that changed the URL while retaining the previous screen.
- Opened mobile create forms after the sheet closes and prevented modal forms from dismissing on restored outside focus.
- Waited for CRM custom fields before saving reminders and preserved validation messages.
- Replaced row-count-based CRM ticket numbers with unique identifiers.
- Corrected User / invitation to open the invitation form.
- Fixed overlapping expanded mobile menu descriptions and restored the mobile certificate upload submit button.
- Preserved UTC attendance timestamps when opening correction forms and displaying recorded punches.

## Reproduce

1. Start `backend/venv/Scripts/python.exe backend/scripts/create_menu_real_api_server.py` from the repository root. It binds only to 127.0.0.1:1597 and creates disposable QA data.
2. From frontend, set `VITE_DEV_API_PROXY_TARGET=http://127.0.0.1:1597`; build with `node node_modules/vite/bin/vite.js build --outDir ../.local/create-menu-real/frontend`; preview with `node node_modules/vite/bin/vite.js preview --outDir ../.local/create-menu-real/frontend --host 127.0.0.1 --port 5194 --strictPort`.
3. From the repository root, run `node qa/create-menu-real.cjs --inventory`, then `node qa/create-menu-real.cjs`. Use `CREATE_MODULE`, `CREATE_ACTION` (pipe-separated), and `CREATE_WIDTH` to narrow a rerun. `CREATE_RESUME=1` skips already passing matrix entries.
4. Run `node qa/create-menu-real-report.cjs` to reject missing/failing entries and regenerate this report and its JSON evidence.

Production build and TypeScript checks passed. The adjacent JSON stores per-action HTTP methods/statuses, save endpoints/IDs and GET readback endpoints. Screenshots and complete attempt history are under `.local/create-menu-real/`.

## Per-action API evidence

### PMS

- **Task** — 1440px: 201 `/api/v1/project-management/task-studio/projects/1/tasks` (#3); GET `/project-management/tasks/3` · 390px: 201 `/api/v1/project-management/task-studio/projects/1/tasks` (#8); GET `/project-management/tasks/8`.
- **Quick task** — 1440px: 200 `/api/v1/project-management/projects/1/tasks` (#4); GET `/project-management/tasks/4` · 390px: 200 `/api/v1/project-management/projects/1/tasks` (#11); GET `/project-management/tasks/11`.
- **Subtask** — 1440px: 200 `/api/v1/project-management/projects/1/tasks` (#7); GET `/project-management/tasks/7` · 390px: 200 `/api/v1/project-management/projects/1/tasks` (#12); GET `/project-management/tasks/12`.
- **Project** — 1440px: 200 `/api/v1/project-management/projects` (#4); GET `/project-management/projects/4` · 390px: 200 `/api/v1/project-management/projects` (#3); GET `/project-management/projects/3`.
- **Story** — 1440px: 201 `/api/v1/project-management/task-studio/projects/1/tasks` (#5); GET `/project-management/tasks/5` · 390px: 201 `/api/v1/project-management/task-studio/projects/1/tasks` (#9); GET `/project-management/tasks/9`.
- **Bug** — 1440px: 201 `/api/v1/project-management/task-studio/projects/1/tasks` (#6); GET `/project-management/tasks/6` · 390px: 201 `/api/v1/project-management/task-studio/projects/1/tasks` (#10); GET `/project-management/tasks/10`.
- **Add existing person** — 1440px: 200 `/api/v1/project-management/people-management/memberships/bulk`; GET `/project-management/workspaces/1/members`.
- **List** — 1440px: view verified; GET `/project-management/tasks` · 390px: view verified; GET `/project-management/tasks`.
- **Reminder** — 1440px: view verified; GET `/record-360/work/queue/items` · 390px: view verified; GET `/record-360/work/queue/items`.
- **Time Tracked** — 1440px: 200 `/api/v1/project-management/time-logs` (#3); GET `/project-management/time-logs?project_id=1` · 390px: 200 `/api/v1/project-management/time-logs` (#4); GET `/project-management/time-logs?project_id=1`.
- **Document** — 1440px: 201 `/api/v1/project-management/projects/1/docs` (#1); GET `/project-management/docs/1` · 390px: 201 `/api/v1/project-management/projects/1/docs` (#2); GET `/project-management/docs/2`.
- **Private note** — 1440px: 201 `/api/v1/project-management/notes` (#1); GET `/project-management/notes/1` · 390px: 201 `/api/v1/project-management/notes` (#2); GET `/project-management/notes/2`.
- **Folder** — 1440px: 201 `/api/v1/project-management/file-folders` (#1); GET `/project-management/file-folders?project_id=1` · 390px: 201 `/api/v1/project-management/file-folders` (#2); GET `/project-management/file-folders?project_id=1`.
- **Page** — 1440px: 201 `/api/v1/project-management/notes` (#3); GET `/project-management/notes/3` · 390px: 201 `/api/v1/project-management/notes` (#4); GET `/project-management/notes/4`.
- **Sheet** — 1440px: 201 `/api/v1/project-management/projects/1/files/upload` (#1); GET `/project-management/files?project_id=1` · 390px: 201 `/api/v1/project-management/projects/1/files/upload` (#4); GET `/project-management/files?project_id=1`.
- **Artifact** — 1440px: 201 `/api/v1/project-management/projects/1/files/upload` (#2); GET `/project-management/files?project_id=1` · 390px: 201 `/api/v1/project-management/projects/1/files/upload` (#5); GET `/project-management/files?project_id=1`.
- **Clip** — 1440px: 201 `/api/v1/project-management/projects/1/files/upload` (#3); GET `/project-management/files?project_id=1` · 390px: 201 `/api/v1/project-management/projects/1/files/upload` (#6); GET `/project-management/files?project_id=1`.
- **Workspace** — 1440px: 201 `/api/v1/project-management/workspace-directory` (#2); GET `/project-management/workspace-directory/2` · 390px: 201 `/api/v1/project-management/workspace-directory` (#4); GET `/project-management/workspace-directory/4`.
- **User / invitation** — 1440px: 201 `/api/v1/project-management/workspaces/1/invitations` (#1); GET `/project-management/workspaces/1/invitations` · 390px: 201 `/api/v1/project-management/workspaces/1/invitations` (#2); GET `/project-management/workspaces/1/invitations`.
- **Space** — 1440px: 201 `/api/v1/project-management/workspace-directory` (#3); GET `/project-management/workspace-directory/3` · 390px: 201 `/api/v1/project-management/workspace-directory` (#5); GET `/project-management/workspace-directory/5`.
- **Conversation** — 1440px: 201 `/api/v1/collaboration/workspaces/1/chat/conversations` (#2); GET `/collaboration/workspaces/1/chat/conversations` · 390px: 201 `/api/v1/collaboration/workspaces/1/chat/conversations` (#3); GET `/collaboration/workspaces/1/chat/conversations`.
- **Form** — 1440px: 201 `/api/v1/forms` (#3); GET `/forms/3` · 390px: 201 `/api/v1/forms` (#4); GET `/forms/4`.
- **Custom Field** — 1440px: 201 `/api/v1/project-management/custom-fields` (#1); GET `/project-management/custom-fields?include_archived=true` · 390px: 201 `/api/v1/project-management/custom-fields` (#2); GET `/project-management/custom-fields?include_archived=true`.
- **Dashboard** — 1440px: 201 `/api/v1/project-management/dashboards` (#1); GET `/project-management/dashboards/1` · 390px: 201 `/api/v1/project-management/dashboards` (#2); GET `/project-management/dashboards/2`.
- **Tag** — 1440px: 201 `/api/v1/project-management/tags` (#1); GET `/project-management/tag-manager` · 390px: 201 `/api/v1/project-management/tags` (#2); GET `/project-management/tag-manager`.
- **View List** — 1440px: 201 `/api/v1/project-management/saved-views` (#1); GET `/project-management/saved-views` · 390px: 201 `/api/v1/project-management/saved-views` (#2); GET `/project-management/saved-views`.
- **Whiteboard** — 1440px: view verified; GET `/project-management/tasks` · 390px: view verified; GET `/project-management/tasks`.

### CRM

- **Add Lead** — 1440px: 201 `/api/v1/crm/lead-management/leads` (#1); GET `/crm/lead-management/leads/1` · 390px: 201 `/api/v1/crm/lead-management/leads` (#2); GET `/crm/lead-management/leads/2`.
- **Contact** — 1440px: 201 `/api/v1/crm/contacts` (#4); GET `/crm/contacts/4` · 390px: 201 `/api/v1/crm/contacts` (#7); GET `/crm/contacts/7`.
- **Company** — 1440px: 201 `/api/v1/master-data/companies` (#1); GET `/master-data/companies/1?source=crm` · 390px: 201 `/api/v1/master-data/companies` (#3); GET `/master-data/companies/3?source=crm`.
- **Add Customer** — 1440px: 201 `/api/v1/master-data/companies` (#2); GET `/master-data/companies/2?source=crm` · 390px: 201 `/api/v1/master-data/companies` (#4); GET `/master-data/companies/4?source=crm`.
- **Deal** — 1440px: 201 `/api/v1/crm/deals` (#1); GET `/crm/deals/1` · 390px: 201 `/api/v1/crm/deals` (#2); GET `/crm/deals/2`.
- **Reminder** — 1440px: 201 `/api/v1/crm/tasks` (#1); GET `/crm/tasks/1` · 390px: 201 `/api/v1/crm/tasks` (#2); GET `/crm/tasks/2`.
- **Task** — 1440px: 201 `/api/v1/project-management/task-studio/projects/1/tasks` (#16); GET `/project-management/tasks/16` · 390px: 201 `/api/v1/project-management/task-studio/projects/1/tasks` (#14); GET `/project-management/tasks/14`.
- **Activity** — 1440px: 201 `/api/v1/crm/activities` (#2); GET `/crm/activities?per_page=100` · 390px: 201 `/api/v1/crm/activities` (#3); GET `/crm/activities?per_page=100`.
- **Product** — 1440px: 201 `/api/v1/catalog/items` (#1); GET `/catalog/items/product/1` · 390px: 201 `/api/v1/catalog/items` (#3); GET `/catalog/items/product/3`.
- **Service** — 1440px: 201 `/api/v1/catalog/items` (#2); GET `/catalog/items/service/2` · 390px: 201 `/api/v1/catalog/items` (#4); GET `/catalog/items/service/4`.
- **Quote** — 1440px: 201 `/api/v1/crm/quotes` (#1); GET `/crm/quotes/1` · 390px: 201 `/api/v1/crm/quotes` (#2); GET `/crm/quotes/2`.
- **Support ticket** — 1440px: 201 `/api/v1/crm/tickets` (#3); GET `/crm/tickets?per_page=100` · 390px: 201 `/api/v1/crm/tickets` (#4); GET `/crm/tickets?per_page=100`.
- **Campaign** — 1440px: 201 `/api/v1/communication/campaigns` (#2); GET `/communication/campaigns` · 390px: 201 `/api/v1/communication/campaigns` (#1); GET `/communication/campaigns`.
- **Email** — 1440px: 201 `/api/v1/communication/emails/draft` (#1); GET `/communication/timeline/lead/2` · 390px: 201 `/api/v1/communication/emails/draft` (#2); GET `/communication/timeline/lead/2`.
- **Subtask** — 1440px: 200 `/api/v1/project-management/projects/1/tasks` (#15); GET `/project-management/tasks/15` · 390px: 200 `/api/v1/project-management/projects/1/tasks` (#13); GET `/project-management/tasks/13`.
- **List** — 1440px: view verified; GET `/project-management/tasks` · 390px: view verified; GET `/project-management/tasks`.
- **Time Tracked** — 1440px: 200 `/api/v1/project-management/time-logs` (#5); GET `/project-management/time-logs?project_id=1` · 390px: 200 `/api/v1/project-management/time-logs` (#6); GET `/project-management/time-logs?project_id=1`.
- **Note** — 1440px: 201 `/api/v1/project-management/notes` (#7); GET `/project-management/notes/7` · 390px: 201 `/api/v1/project-management/notes` (#8); GET `/project-management/notes/8`.
- **Folder** — 1440px: 201 `/api/v1/crm/file-workspace/folders` (#1); GET `/crm/file-workspace` · 390px: 201 `/api/v1/crm/file-workspace/folders` (#2); GET `/crm/file-workspace`.
- **Document** — 1440px: 201 `/api/v1/project-management/projects/1/docs` (#3); GET `/project-management/docs/3` · 390px: 201 `/api/v1/project-management/projects/1/docs` (#4); GET `/project-management/docs/4`.
- **Page** — 1440px: 201 `/api/v1/project-management/notes` (#5); GET `/project-management/notes/5` · 390px: 201 `/api/v1/project-management/notes` (#6); GET `/project-management/notes/6`.
- **Sheet** — 1440px: 201 `/api/v1/crm/file-workspace/upload` (#1); GET `/crm/file-workspace` · 390px: 201 `/api/v1/crm/file-workspace/upload` (#4); GET `/crm/file-workspace`.
- **Artifact** — 1440px: 201 `/api/v1/crm/file-workspace/upload` (#2); GET `/crm/file-workspace` · 390px: 201 `/api/v1/crm/file-workspace/upload` (#5); GET `/crm/file-workspace`.
- **Clip** — 1440px: 201 `/api/v1/crm/file-workspace/upload` (#3); GET `/crm/file-workspace` · 390px: 201 `/api/v1/crm/file-workspace/upload` (#6); GET `/crm/file-workspace`.
- **Form** — 1440px: 201 `/api/v1/forms` (#1); GET `/forms/1` · 390px: 201 `/api/v1/forms` (#5); GET `/forms/5`.
- **Custom Field** — 1440px: 201 `/api/v1/crm/custom-fields` (#1); GET `/crm/custom-fields?entityType=leads&per_page=100` · 390px: 201 `/api/v1/crm/custom-fields` (#2); GET `/crm/custom-fields?entityType=leads&per_page=100`.
- **Dashboard** — 1440px: view verified; GET `/crm/dashboard` · 390px: view verified; GET `/crm/dashboard`.
- **Tag** — 1440px: view verified; GET `/crm/lead-management/leads` · 390px: view verified; GET `/crm/lead-management/leads`.
- **View List** — 1440px: 200 `/api/v1/crm/productivity/shared-views`; GET `/crm/productivity/shared-views` · 390px: 200 `/api/v1/crm/productivity/shared-views`; GET `/crm/productivity/shared-views`.
- **Whiteboard** — 1440px: view verified; GET `/crm/lead-management/leads` · 390px: view verified; GET `/crm/lead-management/leads`.
- **Space** — 1440px: 201 `/api/v1/crm/workspace-directory` (#4b4de9731f7f43a4b84e394cbbbd4df1); GET `/crm/workspace-directory/4b4de9731f7f43a4b84e394cbbbd4df1` · 390px: 201 `/api/v1/crm/workspace-directory` (#5220e31f2da743dfb76d2e50b5d99281); GET `/crm/workspace-directory/5220e31f2da743dfb76d2e50b5d99281`.
- **Conversation** — 1440px: 201 `/api/v1/collaboration/workspaces/1/chat/conversations` (#6); GET `/collaboration/workspaces/1/chat/conversations` · 390px: 201 `/api/v1/collaboration/workspaces/1/chat/conversations` (#5); GET `/collaboration/workspaces/1/chat/conversations`.

### HRMS

- **Add employee** — 1440px: 201 `/api/v1/employees/` (#4); GET `/employees/4` · 390px: 201 `/api/v1/employees/` (#5); GET `/employees/5`.
- **Bulk add employees** — 1440px: 200 `/api/v1/imports/hrms/batches/38c85fe5-e957-4a04-b973-1a8b3f6d1b27/commit` (#38c85fe5-e957-4a04-b973-1a8b3f6d1b27); GET `/employees/?search=CreateImport1794389980400` · 390px: 200 `/api/v1/imports/hrms/batches/b0b16035-7d46-412f-93c0-8edbc73ee69a/commit` (#b0b16035-7d46-412f-93c0-8edbc73ee69a); GET `/employees/?search=CreateImport1794389988695`.
- **Correct attendance** — 1440px: 200 `/api/v1/employees/workbench/attendance/2/correct`; GET `/attendance/employee/2?from_date=2026-11-01&to_date=2026-11-30` · 390px: 200 `/api/v1/employees/workbench/attendance/2/correct`; GET `/attendance/employee/2?from_date=2026-11-01&to_date=2026-11-30`.
- **Apply for leave** — 1440px: 201 `/api/v1/leave/apply` (#1); GET `/leave/my-requests` · 390px: 201 `/api/v1/leave/apply` (#2); GET `/leave/my-requests`.
- **Support ticket** — 1440px: 201 `/api/v1/helpdesk/tickets` (#4); GET `/helpdesk/tickets` · 390px: 201 `/api/v1/helpdesk/tickets` (#5); GET `/helpdesk/tickets`.
- **Submit expense** — 1440px: 201 `/api/v1/expenses/claims` (#1); GET `/expenses/claims` · 390px: 201 `/api/v1/expenses/claims` (#2); GET `/expenses/claims`.
- **Generate letter** — 1440px: 201 `/api/v1/documents/studio/issue` (#1); GET `/documents/studio/issued` · 390px: 201 `/api/v1/documents/studio/issue` (#2); GET `/documents/studio/issued`.
- **Note** — 1440px: 201 `/api/v1/project-management/notes` (#9); GET `/project-management/notes/9` · 390px: 201 `/api/v1/project-management/notes` (#10); GET `/project-management/notes/10`.
- **Upload document** — 1440px: 201 `/api/v1/documents/certificates` (#4); GET `/documents/certificates?employee_id=2` · 390px: 201 `/api/v1/documents/certificates` (#5); GET `/documents/certificates?employee_id=2`.
- **Form** — 1440px: 201 `/api/v1/forms` (#2); GET `/forms/2` · 390px: 201 `/api/v1/forms` (#6); GET `/forms/6`.
- **Asset** — 1440px: 201 `/api/v1/assets/` (#1); GET `/assets/?search=CREATEQA-1794389932762%20asset` · 390px: 201 `/api/v1/assets/` (#2); GET `/assets/?search=CREATEQA-1794389932762%20asset`.

