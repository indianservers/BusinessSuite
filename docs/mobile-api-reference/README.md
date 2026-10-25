# Business Suite backend API reference for iOS and Android

Use this bundle to build mobile screens against the existing Business Suite backend. It covers authentication, HRMS, CRM, Project Management, Sales and Inventory, Finance and Accounting, AI, and shared platform services. The existing Flutter application starts with Project Management; the complete suite catalog is included for later modules.

The 24 October 2026 export contains **2,022 HTTP operations**, **1,064 schemas**, one additional hidden file route, and one WebSocket route. The deployed OpenAPI contains **1,986 HTTP operations**; **36 local operations are not yet present there**, mainly assistant workbench, dashboard builder and workspace notes routes. These entries are marked in the catalog. Documentation reachability was checked; individual business operations were not exercised.

## Reference files

- [Full endpoint catalog](ENDPOINTS.md): every registered HTTP method and path, summary, declared description, endpoint URL template, Swagger link, handler source, authentication dependencies, parameters, request fields, and declared responses.
- [OpenAPI contract](openapi.json): import into an API client or use as input for mobile model generation. Includes nested schemas, required fields, defaults, enums, formats, constraints, and declared security schemes.
- [Endpoint details as JSON](endpoints.json): the same operation inventory with source locations and request and response metadata, suitable for giving to another coding agent.
- [Postman collection](postman.collection.json): requests organized by module. Set `origin` to the host only and `access_token` to a valid token. Fill resource IDs, query values, and request bodies before sending. Empty JSON bodies are placeholders, not valid payload examples.
- [Generation manifest](manifest.json): module counts, schema counts, validation results, and endpoints without typed success responses.
- [Deployed API comparison](deployment-check.json): documentation reachability and differences between local and deployed method/path inventories. A matching path does not establish matching payloads or business behavior.
- [Unmounted route declarations](unmounted-route-declarations.json): source routes outside the main registered application, including the separate legacy inventory application. These are not callable suite endpoints unless separately deployed.

Share this entire directory so relative links and schema references remain available. For an AI coding tool, provide this guide and `openapi.json` first, then the catalog for the feature being built.

## Backend links and environments

- Deployed origin: [Business Suite](https://businesssuite-rosy.vercel.app).
- Mobile API base: `https://businesssuite-rosy.vercel.app/api/v1`.
- [Swagger API explorer](https://businesssuite-rosy.vercel.app/api/v1/docs).
- [ReDoc API reference](https://businesssuite-rosy.vercel.app/api/v1/redoc).
- [Live OpenAPI JSON](https://businesssuite-rosy.vercel.app/api/v1/openapi.json).
- [Health endpoint](https://businesssuite-rosy.vercel.app/health).

The repository launcher `start-backend.cmd` uses port **1534**. Its local API base is `http://localhost:1534/api/v1`. The Flutter README also documents a manual server on port **8000**; use that port only if you start the server with `--port 8000`.

An Android emulator uses `http://10.0.2.2:1534/api/v1` to reach the host launcher. An iOS simulator can use `http://localhost:1534/api/v1` when the backend runs on the same Mac. A physical phone needs a reachable host LAN address or a trusted HTTPS server. The existing Flutter client requires `API_BASE_URL`; local HTTP also requires its explicit development flag. See the [Flutter setup guide](../../Flutter-Apps/README.md).

Choose one URL convention in the mobile API client:

- With an API base ending in `/api/v1`, call relative paths such as `/auth/me`.
- The full catalog and OpenAPI already contain `/api/v1`; prefix those paths with the origin only.

Do not append `/api/v1` twice. The OpenAPI `servers` entries are origins for this reason. Link templates containing `{workspace_id}` or other placeholders must be filled before making a request.

## Module availability and screen areas

The main app can register five product modules through `INSTALLED_APPS`: `hrms`, `crm`, `project_management`, `srm`, and `fam`. Shared routers load independently. Business OS settings can additionally disable access to module prefixes with a `403` response. Use the target deployment's live schema and enabled module configuration when choosing screens.

- **Authentication and users**: `/auth`, `/users`. Login, MFA, session management, current user, roles, permissions, password recovery, and account administration.
- **Project Management**: `/project-management`. Workspaces, projects, tasks, Kanban, people and invitations, comments, attachments, planning and calendar, chat and direct messages, time tracking, dashboards, recovery, and workspace lifecycle.
- **CRM**: `/crm`. Customer relationships, leads, contacts, accounts, sales opportunities and pipelines, activities, campaigns, quotes, communication and CRM administration.
- **Sales and Inventory Management**: `/srm`. Sales documents, commercial workflows, recurring revenue, collections, inventory-related workflows, reports and settings.
- **Finance and Accounting Management**: `/fam`, including `/fam/inventory`. Accounting setup, vouchers, ledgers, banking, reconciliation, taxation, payables and inventory/accounting integration.
- **HRMS**: domain prefixes such as `/employees`, `/attendance`, `/leave`, `/payroll`, `/benefits`, `/recruitment`, `/performance`, `/documents`, `/helpdesk`, and `/notifications`. HR administration and employee or manager self-service have different access requirements.
- **AI Operator and Assistant**: `/ai-operator`. Provider setup, plans, approvals, runs, private assistant conversations and related tools. Provider credentials belong on the backend.
- **Shared platform**: Business OS, SaaS administration, automation, customization, communications, analytics, approvals, workflow, AI agents, security, scheduling and logs. The catalog includes administrative and internal integration routes; implement screens only for the intended user permissions.

The catalog group `hrms-and-shared-services` also includes service prefixes not assigned to a dedicated catalog group. Group names help navigation; the actual method/path and registered handler determine the contract.

## Authentication and session flow

All paths in the remainder of this guide are relative to the API base ending in `/api/v1`, unless stated otherwise. Authentication uses JSON login and bearer tokens, not a form-based OAuth password grant.

### Sign in

Call `POST /auth/login` with:

```json
{
  "email": "person@example.com",
  "password": "USER_SUPPLIED_PASSWORD",
  "module": "project_management"
}
```

Use `project_management` for PMS; the other product module keys are `hrms`, `crm`, `srm`, and `fam`. The server enforces a module-specific role policy. An optional `trusted_device_token` can be supplied for a previously trusted device.

Successful login has two possible response shapes. Without an MFA challenge, it returns `access_token`, `refresh_token`, `token_type` (normally `bearer`), `user_id`, `email`, `role`, `is_superuser`, and nullable `employee_id`. With MFA, it returns a challenge instead:

```json
{
  "mfa_required": true,
  "mfa_token": "TEMPORARY_MFA_TOKEN",
  "mfa_methods": ["totp", "recovery"]
}
```

Check `mfa_required` before parsing tokens. Login does not declare this response union in OpenAPI; use the two branches described here. Keep passwords and the temporary MFA challenge out of persistent storage.

### Complete MFA

Call `POST /auth/mfa/verify` with:

```json
{
  "mfa_token": "TEMPORARY_MFA_TOKEN",
  "code": "USER_SUPPLIED_CODE",
  "method": "totp",
  "trust_device": false,
  "device_name": "User iPhone"
}
```

Use `method: "recovery"` for a recovery code. Success returns the token response and may also include `trusted_device_token` when requested. Recovery codes are single use.

### Restore the session and permissions

Save tokens in platform secure storage. Send `Authorization: Bearer ACCESS_TOKEN` on authenticated HTTP requests. Call `GET /auth/me` at authenticated startup; its `role` is an object containing a `permissions` array. The token response's `role` is a name string, so it needs a different DTO.

Read granted permission names from `GET /auth/me` → `role.permissions[].name`. `GET /auth/permissions` is an administrative permission catalog, not the current user's grants. Refresh identity and workspace membership when returning to sensitive screens or after an access rejection.

### Refresh and logout

On an expired access token, call `POST /auth/refresh` with `{"refresh_token":"REFRESH_TOKEN"}`. Save both returned tokens. The configured defaults are 60 minutes for access tokens and 7 days for refresh tokens; deployments can override them. The refresh endpoint issues new tokens; do not assume the server implements one-time use of the previous refresh token.

Use one shared refresh operation for concurrent requests and retry each failed request at most once. Avoid refreshing recursively on login or refresh failures. Preserve a stored session on a transient connectivity failure; require sign-in again when the server rejects the refresh credentials.

Call authenticated `POST /auth/logout` to revoke the current session, then clear local tokens and user-scoped data. Session inspection and revocation are available under `/auth/sessions/me`.

Sources: [auth handlers](../../backend/app/api/v1/auth.py), [auth schemas](../../backend/app/schemas/auth.py), [auth dependencies](../../backend/app/core/deps.py), [default configuration](../../backend/app/core/config.py).

## Project Management mobile screen flow

The existing [Flutter client](../../Flutter-Apps/README.md) already uses the first flow below. Workspace roles are case-sensitive values: `Owner`, `Admin`, `Member`, and `Guest`.

1. Sign in with `module: "project_management"`, complete MFA if requested, and load `/auth/me`.
2. Call `GET /project-management/workspaces`. This returns an array of `{id, name, role}` for the current user's memberships.
3. On selection, call `GET /project-management/workspaces/{workspace_id}/overview`. This returns `{id, name, role, projects, tasks}`. Use its fresh role to enable editing. The overview includes task fields for the board and list, including status, priority, assignees, dates, estimates, position, and comment counts.
4. For task details, call `GET /project-management/tasks/{task_id}`. For project task lists, use `GET /project-management/projects/{project_id}/tasks`. Their typed models differ from the compact workspace overview.
5. Create tasks with `POST /project-management/projects/{project_id}/tasks`; update them with `PATCH /project-management/tasks/{task_id}`. The create request requires both `task_key` and `title`; use the exact additional fields and defaults in OpenAPI.
6. For workspace people, call `GET /project-management/workspaces/{workspace_id}/members`. Invitation and member-management APIs are listed below.

Clear the selected workspace dataset immediately when switching, and discard stale asynchronous responses belonging to the previous selection.

### Create a workspace and project

`POST /project-management/workspaces` accepts `{"name":"Mobile delivery"}` and returns the new workspace with the creator as `Owner` (`201`). Creation requires global `pms_manage_projects` or `pms_admin`, or the server's superuser grant.

`POST /project-management/projects` accepts a project create model. A minimal workspace project payload is:

```json
{
  "workspace_id": 123,
  "name": "Mobile application",
  "project_key": "MOBILE"
}
```

Replace `123` with a workspace where the current user is Owner or Admin. The project key is normalized to uppercase. Keep project status, task status, and workspace roles as separate concepts.

For task creation, a minimal payload is:

```json
{
  "task_key": "MOBILE-1",
  "title": "Build sign in screen"
}
```

The task key must be unique within the project. For a status change, use `PATCH /project-management/tasks/{task_id}` with a valid task update such as `{"status":"In Progress"}`. Render configured workflow choices when available rather than treating these examples as a complete enum.

### Workspace access

- Owner and Admin can administer their workspace and its projects.
- Member can browse, manage tasks, comment, upload, and log time in workspace projects.
- Guest can browse. Hide editing controls and handle server rejection if access changes.
- Unknown roles should disable editing until the client understands them.

A global administrator without workspace membership cannot use that global role to bypass access to a workspace project. Projects without a workspace use separate legacy project, organization and global permission rules. See [project access checks](../../backend/app/apps/project_management/access.py).

### Invitations and membership

- `GET/POST /project-management/workspaces/{workspace_id}/invitations`: list or create invitations. Create accepts `email` and `role` (`Admin`, `Member`, or `Guest`). Only the Owner can invite or appoint Admins.
- `DELETE /project-management/workspaces/{workspace_id}/invitations/{invitation_id}`: revoke an invitation.
- `POST /project-management/workspace-invitations/accept`: an authenticated existing user accepts with `{"token":"PRIVATE_INVITATION_TOKEN"}`. The account must match the addressed email.
- `GET /project-management/workspace-invitations/preview?token=...`: preview a valid invitation before sign-in.
- `POST /project-management/workspace-invitations/activate`: conditional account creation for the addressed invitation, accepting `token` and `password`. Existing accounts must sign in and accept; activation also has server-side workspace provisioning restrictions.
- `PATCH /project-management/workspaces/{workspace_id}/members/{member_id}`: change membership with `{"role":"Member"}` or another allowed role.
- `DELETE /project-management/workspaces/{workspace_id}/members/{member_id}`: remove a member. The Owner cannot be removed through this route.

An invitation token is private, email-bound, single use, and expires. Do not place it in analytics or logs. Invitation creation is distinct from global account administration. See [workspace handlers](../../backend/app/apps/project_management/workspaces.py).

### Other mobile feature areas

Use the catalog to select exact endpoint contracts for comments, files, checklists, dependencies, milestones, sprints, time logs, timesheets, boards, calendar and planner, analytics, dashboards, workspace documents, archive/recovery, automation and messaging. The same word can name different resources: workspace members, project members, and chat members are different records and use different IDs.

Workspace chat is under `/project-management/workspaces/{wid}/chat`; unread totals also have a `/project-management/messaging/unread` route. Keep message pagination and attachments separate from task comments. Use the declared request fields for any endpoint-specific request keys or cursors.

## Employee and manager screen starting points

These backend areas can support later mobile modules; HRMS is outside the current Flutter milestone. Resolve each user's `employee_id` from authenticated identity and use the server's scope rules.

- Profile and directory: employee and organizational endpoints under `/employees` and related organization prefixes.
- Attendance: `GET /attendance/today`, `GET /attendance/my`, `POST /attendance/check-in`, `POST /attendance/check-out`; geolocation proof has separate `/attendance/geo/*` routes and contracts.
- Leave: `GET /leave/types`, `GET /leave/balance`, `GET /leave/my-requests`, `POST /leave/apply`.
- Manager approvals: pending leave, regularization, team attendance and approval routes require the applicable manager or administrative scope.
- Payslips and payroll: use the employee-facing routes from the catalog; payroll runs, statutory setup, tax administration and exports have separate authorization requirements.
- Notifications, expenses, helpdesk, employee documents, benefits and performance each have their own route families and schemas.

Do not reuse an administrative list endpoint as an employee self-service endpoint without confirming server filtering and permissions.

## Request and response conventions

### Payloads and lists

JSON field names and casing come from each endpoint's schema; they are not uniform across all modules. Some endpoints return arrays, others return objects with `items`, `data`, counts or cursors. Pagination also varies: use declared names such as `skip`, `limit`, `page`, `page_size`, `before` or `cursor` only where that endpoint defines them.

Treat omitted, nullable and defaulted fields separately. For PATCH requests, send changed fields only unless the handler specifies otherwise. Dates use the endpoint's declared `date` or `date-time` format. Preserve timezone offsets where supplied and interpret dates without times as calendar dates. Decimal monetary fields can have string or numeric representations in the declared schema; avoid binary floating-point arithmetic for financial totals.

The current backend leaves many success payloads untyped, including important workspace and login responses. `manifest.json` identifies those operations. An empty schema is not an empty response: inspect the linked handler and record a staging contract before generating a strict mobile DTO. OpenAPI also does not capture every status code raised by authorization, business validation or middleware.

### Errors and retries

Handle `detail` as a string, object or validation-error array. FastAPI validation errors commonly contain `detail[].loc`, `msg` and `type`. Global server errors may also include `request_id`. Send a unique `X-Request-ID` and retain the response header value for support.

- `400`: business validation or invalid workflow input; show the server's actionable message.
- `401`: invalid or expired access/session credentials; apply the bounded refresh flow.
- `403`: missing authentication, inactive user, role restriction, missing permission or disabled module. The shared auth dependency returns `403` when no bearer credential is supplied. Do not treat every `403` as token expiry.
- `404`: missing or inaccessible resource; some membership checks intentionally return this result.
- `409`: conflict, for example an existing account or membership.
- `413`: upload/request too large.
- `422`: invalid request fields or other validation failures.
- `423`: account lockout, including the login/MFA flow.
- `429`: rate limit; use a bounded delay and `Retry-After` when present.
- `5xx` or network failure: show retry and diagnostic context. A timeout after a write does not prove the write failed.

Use bounded retries for reads. After an uncertain mutation, reload state before resubmitting. Do not assume a universal idempotency header or offline write queue exists. Honor endpoint-specific request keys and confirmation hashes where provided.

### Files and downloads

For `multipart/form-data`, use the schema's exact field names and let the HTTP client set the multipart boundary. File limits differ by deployment and feature. General defaults are 10 MB locally or 3 MB on serverless; PMS attachment defaults are 25 MB locally or 3 MB on serverless. The serverless middleware rejects total requests over 4 MB, so multipart overhead also matters. Extensions and MIME types have endpoint-specific allowlists.

Some file and export endpoints return bytes, CSV, PDF, HTML or other non-JSON content even when the OpenAPI response schema is weak. Inspect content type and the handler before choosing a decoder. Save or share downloads using the platform's native file flow.

Upload references can be relative `/uploads/...` paths or signed private URLs. Resolve relative paths against the origin, use returned signed URLs without rewriting them, and reacquire expired URLs through the owning resource. The hidden `GET /api/v1/files/blob?token=...` route supports the Vercel Blob storage backend only. Its token is a file-access credential, not a login token; do not expose it in logs. See [storage middleware](../../backend/app/core/middleware/storage.py).

## Realtime and assistant streaming

### Project events

Call `GET /project-management/realtime/config` before selecting the transport. It returns `transport` and `pollIntervalMs` (currently 3000). Serverless defaults to the database transport, while other deployments default to WebSocket.

For database polling, call `GET /project-management/realtime/events` without a cursor to establish the current cursor. That initial result contains no historical events. Poll again with `?cursor=LAST_CURSOR`, apply returned events, and keep the new cursor. Re-fetch the owning resource when needed to reconcile current permissions and state. Events are scoped to accessible projects.

For a deployment supporting WebSocket, connect to the origin-relative path `/api/v1/project-management/realtime?token=ACCESS_TOKEN`, replacing HTTPS with WSS. This route is listed separately because OpenAPI does not represent WebSockets. Keep the token out of URL logging. On connection the server sends a `connected` event. Subscribe with:

```json
{"action":"subscribe","projectIds":[123],"taskIds":[]}
```

The server acknowledges `subscribed` with allowed IDs. Other inbound actions include `presence` and `typing`. Event payloads include a `type` and scoped resource information. Authentication/scope failures can close the connection with code `1008`; reconnect after refreshing identity or credentials as appropriate. Do not assume the deployed host supports a persistent socket when it advertises database transport.

Sources: [realtime routes](../../backend/app/apps/project_management/api/router.py), [durable polling feed](../../backend/app/apps/project_management/event_feed.py).

### Assistant conversations

The assistant family is `/ai-operator/assistant`. Create a conversation, send a message with its required UUID `request_key`, and render the returned result/proposal. Business mutations that require confirmation use the corresponding `messages/{message_id}/confirm` route with the exact `approval_hash`. Present the proposed action to the user before confirming it.

`POST /ai-operator/assistant/conversations/{ident}/messages/stream` returns a server-sent event stream using `text/event-stream`, with `status`, `result` and `failure` events. Use a streaming POST-capable client with bearer headers. Read HTTP status before parsing the stream, then handle a `failure` event even if the HTTP request initially succeeded. A normal JSON decoder or a GET-only EventSource wrapper does not implement this contract.

See [assistant handlers and request models](../../backend/app/ai_operator/assistant_api.py). AI availability, provider configuration and access rights remain backend decisions.

## Notes to give the mobile implementation agent

Build against the selected environment's live OpenAPI and this guide. Reuse the shared Business Suite backend and authentication. Keep DTOs specific to response shapes. Start with login, MFA, session restoration, workspace selection, overview and task CRUD. Implement loading, empty, error, retry and forbidden states for every screen. Apply current server grants and workspace roles when enabling actions, and let the server authorize every request. Keep secrets in secure storage, avoid logging credentials or private URLs, and reconcile state after uncertain writes. Use the catalog for exact method, path, parameters, required fields and source links; do not invent endpoints or assume every route is a mobile user action.

## Regenerating the catalog

From the repository root on this Windows checkout:

```powershell
./backend/venv/Scripts/python.exe backend/scripts/export_mobile_api_reference.py --check-deployed
```

Without `--check-deployed`, generation is offline. The exporter enables all five product modules in its own process, imports the app without running its startup lifespan, and writes documentation only. It does not run migrations, seed data, log in, or invoke business APIs. It uses fixed placeholder database configuration and exports no environment secrets. The manually written guide is preserved.

Source: [export script](../../backend/scripts/export_mobile_api_reference.py). The export reflects the working tree, including local changes; deployed availability may differ. Check `deployment-check.json` before using newly added endpoints on the deployed host.
