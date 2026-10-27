# BusinessSuite Communication Engine

Implementation and integration report, 27 October 2026.

## Release status

This is a working shared communication foundation and Messages redesign, not certification that every item in the master specification is finished. It has not been deployed and no production database was migrated.

PMS, CRM, HRMS, Sales and Finance now have entry points to the same workspace/conversation backend and reusable frontend. Contextual record adapters have been exercised for PMS projects/tasks, CRM leads/deals, and HRMS employee profiles. The separate InternHub portal, automatic batch membership synchronization, digests, advanced follow-up evidence/comments, and enterprise capacity validation remain incomplete. Do not describe those as shipped integrations.

## Architecture and dependency map

- Frontend: React/TypeScript, Vite, React Router, TanStack Query, Zustand, Radix UI and the existing Tiptap rich-text editor.
- Backend: FastAPI, Pydantic, SQLAlchemy and Alembic. Both migration trees are maintained.
- Identity: existing bearer sessions and effective company/record policies. No additional authentication system.
- Canonical records: existing `pms_chat_conversations`, `pms_chat_members`, `pms_chat_messages`, attachments, PMS tasks, calendar events and suite notifications.
- Shared metadata: `backend/app/shared/communication`. Its API delegates to the existing chat services; there is no per-module backend fork.
- Common endpoint namespace: `/api/v1/collaboration`. Legacy `/api/v1/project-management/workspaces/{id}/chat` endpoints remain available against the same records.
- Realtime: existing authenticated WebSocket invalidations, plus a durable, membership-scoped database invalidation feed when a socket is unavailable. Events contain no message bodies or previews. PostgreSQL append commits are serialized to protect cursor ordering.
- Context: code-owned allowlist -> effective module/record authorization -> canonical native API -> one conversation identity for that workspace/record. Every contextual read rechecks source access.
- Follow-up: source message -> follow-up -> optional actual PMS task created by `create_task_operation`. Task -> authorized source endpoint supplies the reverse link. Task status is read live rather than copied into a competing task system.
- Meetings: shared conversation link -> existing private `PMSCalendarEvent`. A private channel's meeting is not published as a workspace-wide calendar event.
- Reminders: existing authenticated scheduler -> bounded due-follow-up worker -> conditional claim and notification in one transaction. Repeated runs do not duplicate the due notification.

## Implemented behavior

- Shared responsive conversation workspace, module navigation reuse, grouped conversation sidebar, search, unread/draft/pinned/archived filters and collapsible context panel.
- Channels, private channels, one-to-one and group conversations, membership controls, existing history preservation, cursor pagination, server-issued IDs and idempotent submissions.
- Optimistic send reconciliation using the server-returned submission ID; reconnect and tab-visibility recovery.
- Thread replies and a server-paginated thread browser.
- Reactions, manager-controlled pins, personal saved messages and a paginated saved-message view.
- Existing safe rich-text rendering, editing, soft deletion, revision snapshots, and text-only previews that do not expose serialized rich-text markup.
- Shared composer with formatting, mentions of current participants, emoji insertion, file picker, drag/drop, clipboard image uploads and configurable Enter-to-send behavior.
- Local draft recovery plus server-side conversation/thread drafts. Private draft endpoints never accept a caller-supplied author.
- Shared-file view and permission-checked downloads through the existing storage service.
- Follow-up creation, assignment, priority, due time, statuses and linked PMS tasks. Assigning someone else requires conversation management authority as well as existing task authorization when converting.
- Seen-through markers based on the existing authorized read state, expiring real presence and throttled typing heartbeats.
- Conversation notification preferences: all messages, mentions only, none, Do Not Disturb and existing mute behavior.
- Meeting scheduling through the existing calendar service, replay protection and validated HTTPS join links. This does not introduce a voice/video provider.
- Read-only AI actions through the existing authorized AI Operator provider: summarize, extract actions/questions, draft a reply and find decisions. No AI response is automatically sent or executed.
- Source-record launchers on PMS project/task screens, CRM lead/deal/account screens and HRMS employee details.
- Module Messages routes: `/pms/messages`, `/crm/messages`, `/hrms/messages`, `/srm/messages`, `/fam/messages`.

## Public usage

```tsx
import {
  CommunicationWorkspace,
  ContextualChat,
  ConversationLauncher,
  FollowUpWidget,
} from "@/shared/communication";

<CommunicationWorkspace
  module="PMS"
  workspaceId={workspaceId}
  features={{ channels: true, threads: true, followUps: true, files: true }}
/>

<ContextualChat module="CRM" workspaceId={workspaceId}
  context={{ type: "deal", id: dealId }} />

<ConversationLauncher module="HRMS"
  context={{ type: "employee", id: employeeId }} />

<FollowUpWidget workspaceId={workspaceId} conversationId={conversationId} />
```

`ContextualChat` resolves or creates the authorized canonical discussion and opens the module's full shared workspace. It is not a copied per-record chat implementation. Feature flags control presentation; they never confer backend permissions. Callers cannot supply a tenant or author ID.

## Files created

- `backend/app/shared/communication/__init__.py`
- `backend/app/shared/communication/models.py`
- `backend/app/shared/communication/api.py`
- `backend/app/shared/communication/gateway.py`
- `backend/app/shared/communication/contexts.py`
- `backend/app/shared/communication/reminders.py`
- `backend/alembic/versions/20261027_031_communication.py`
- `backend/alembic_postgresql/versions/pg_20261027_031_communication.py`
- `backend/tests/test_communication_engine.py`
- `backend/scripts/communication_qa_server.py`
- `frontend/src/shared/communication/CommunicationWorkspace.tsx`
- `frontend/src/shared/communication/collaboration.tsx`
- `frontend/src/shared/communication/MeetingPanel.tsx`
- `frontend/src/shared/communication/adapters.tsx`
- `frontend/src/shared/communication/widgets.tsx`
- `frontend/src/shared/communication/useCommunicationDraft.ts`
- `frontend/src/shared/communication/useCommunicationEvents.ts`
- `frontend/src/shared/communication/usePresence.ts`
- `frontend/src/shared/communication/scope.ts`
- `frontend/src/shared/communication/types.ts`
- `frontend/src/shared/communication/index.ts`
- `frontend/src/shared/communication/communication.css`
- `playwright/communication-live.spec.ts`
- Desktop, tablet and mobile screenshots in `docs/qa/communication-*.png`.

## Existing files extended

- Backend: `module_registry.py`, `access/catalog.py`, `api/v1/scheduled_jobs.py`, PMS `chat.py`, `chat_models.py`, `calendar_settings.py`, `api/router.py`.
- Frontend: PMS `DirectMessagesPage.tsx` is a compatibility re-export; PMS `ProjectDashboard.tsx`, `TaskDetail.tsx`, `realtime.ts`; CRM `CRMRecordDetailPage.tsx`; HRMS `EmployeeDetailPage.tsx`; CRM/HRMS/SRM/FAM route files; shared `AppLayout.tsx`, `Sidebar.tsx`, `MessagingNavLink.tsx`.
- Unrelated pre-existing working-tree changes were retained. A build-only correction split the workflow builder reducer’s combined undo/redo/checkpoint union into distinct variants in `frontend/src/apps/power-apps/applications/automations/builder/useDocument.ts`; runtime behavior is unchanged.

## Schema and rollout

Revision `031_communication` adds reactions, pins, saved items, drafts, revisions, context links, follow-ups, notification preferences, presence, invalidation events and meeting links. It does not replace existing conversation/message/file/task/calendar IDs or rewrite old history.

The migration in each tree follows that tree's `030_security_boundary` revision. Both migration bodies were exercised against isolated SQLite schemas containing pre-existing chat history. This proves additive structure and history preservation in those tests; it is not a claim of PostgreSQL deployment validation.

Before deployment:

1. Review the combined working tree and migration heads, including pre-existing uncommitted migrations 029/030.
2. Test the PostgreSQL migration on an isolated database branch with production-like data, using a direct connection.
3. Apply the additive schema before serving code that reads the new tables; deploy frontend and backend together.
4. Keep existing private storage and authentication configuration. Configure an authorized AI Operator provider for AI assistance.
5. Enable the existing scheduler with its established secret to process due reminders and expire ephemeral event/presence data.
6. Validate the production WebSocket/database transport and concurrency on the intended deployment.

No production migrations, deployments, external messages, or provider calls were performed by this implementation.

## Verification

Latest completed checks: 11 backend integration/security/migration tests passed; the real two-browser HTTP workflow passed; the production build passed. Build warnings concern upstream Zod annotations and large existing application chunks.

Automated HTTP integration coverage uses the real FastAPI routes, SQLAlchemy persistence, authentication and authorization on disposable databases. Cases cover:

- reactions, pins, saves, private drafts, revisions;
- follow-up assignment, replay conflicts, one notification per assignment, real task creation and live status synchronization;
- cross-company access, unauthorized participants, removed workspace members, attachment enumeration, mass assignment and source-message tampering;
- canonical context identity and native CRM/HRMS/PMS source authorization;
- event-feed membership, presence, mentions-only preferences and reminder idempotency;
- additive migrations retaining existing history;
- private calendar meetings, HTTPS link validation and replay protection;
- retained channel/group/DM, join, thread, file, search, edit/delete and member-revocation workflows;
- AI access refusal, rejected privilege fields and no privilege elevation.

The live Playwright journey proxies requests to an actual disposable local HTTP server, not mocked APIs. Two independent browser sessions exchange a message, react, reply in a thread, create a follow-up, upload/share a real file and schedule a meeting. It captures desktop/tablet/mobile layouts, checks mobile overflow, and verifies that switching to an unauthorized company clears the previous company’s message cache. Its SQLite QA server serializes requests; this test does not certify concurrent PostgreSQL capacity.

Run locally:

```powershell
backend/venv/Scripts/python.exe -m pytest backend/tests/test_communication_engine.py -q
# In a separate terminal, start the disposable API:
backend/venv/Scripts/python.exe backend/scripts/communication_qa_server.py
# From frontend/:
node node_modules/playwright/cli.js test --config=playwright.config.ts communication-live.spec.ts --workers=1
npm run build
```

The initial attempt to run the old `test_pms_chat.py` suite stopped in its legacy workspace bootstrap because those fixtures lack the verified company identities required by the working tree's existing security-boundary changes. The new integration suite supplies persisted company membership and independently covers the retained messaging workflows. No existing authorization requirement was weakened to make old fixtures pass.

## Remaining work and limits

- Separate InternHub portal integration and automatic batch/mentor membership synchronization are not implemented. Existing portal-token restrictions remain intact. Passing `module="InternHub"` is not proof that this journey works.
- Department channels, sensitive HR-case adapters, support-ticket adapters and finance-specific context resolvers require additional explicit policies. Unsupported context types fail closed.
- Native voice/video provisioning is absent; meetings use authorized HTTPS links and existing calendar records.
- Notification digests, channel-wide mentions, structured mention records, custom reminder policies and a global assigned-follow-up inbox remain incomplete.
- Follow-up comments, additional follow-up attachments and required completion evidence are not implemented as separate workflows; linked PMS tasks retain their existing work/submission controls.
- The timeline is bounded to five cursor pages and uses browser render containment. Full row virtualization and paginated large-channel participant pickers remain future work.
- Presence is bounded and expires automatically; it describes recent activity rather than guaranteeing device connectivity.
- Real AI provider execution, provider-specific injection evaluation, PostgreSQL migration execution, WebSocket reconnection under load, and thousands-user capacity tests were not performed. Do not label this release enterprise-capacity certified.
- Message retention policy enforcement and cross-device draft conflict resolution still need dedicated product policies. This change does not delete message history.
