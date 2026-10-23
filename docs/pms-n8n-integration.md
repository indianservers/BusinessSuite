# PMS → n8n preparation

Status: prepared, not connected. No n8n URL, credentials, outbound webhooks or scheduled delivery have been configured.

## Read-only event contract

`GET /api/v1/project-management/workspaces/{workspace_id}/workflow-events?after_id=0&limit=100`

Use `Authorization: Bearer <access_token>` from an account that is an Owner or Admin of that specific workspace. Global company privileges do not bypass workspace membership. Members and Guests receive 403; unrelated workspaces return 404.

Responses contain `schema_version`, `items`, `next_cursor`, `has_more` and `replayed`. Each item has a stable `event_id`, activity `type`, UTC `occurred_at`, project/task/actor IDs, safe scheduling/status changes and a **current** task snapshot. Snapshots are not historical task versions. Descriptions, files, emails, tokens and arbitrary activity metadata are excluded.

Supported activity types: `task.created`, `task.updated`, `status.changed`, `priority.changed`, `assignee.changed`, `schedule.changed`, `automation.executed`, `automation.skipped`. One user action can produce multiple activity types; select the event type your workflow needs rather than processing all of them as the same business action.

## Connect later

1. Import `integrations/n8n/pms-read-events.json`. It is an **inactive, manual, read-only starter**. Set the workspace ID in the URL and select an n8n Header Auth credential. Never put credentials in the workflow JSON or a URL.
2. For unattended use, arrange a dedicated integration account with the required workspace membership and a credential lifecycle. PMS access tokens expire; existing `/api/v1/auth/refresh` accepts `{ "refresh_token": "..." }` and rotates credentials. The starter deliberately does not store a refresh token or implement unattended login.
3. Add a Schedule Trigger only when ready. Use the workflow timezone intentionally. Keep one polling execution active per workspace/consumer.
4. Store the cursor separately for every workspace and workflow consumer. Pass it as `after_id`; follow `has_more` to drain pages.
5. Persist processed `event_id` values in durable storage and deduplicate before side effects. By default, the feed replays recent events to tolerate retries and delayed commits. `replay=false` is available for inspection and deterministic pagination. The bounded replay window is not an exactly-once delivery guarantee; a high-volume integration requiring lossless delivery should add a transactional outbox and acknowledgements before enabling business-critical automation.
6. Advance `next_cursor` **only after downstream processing succeeds**. On failure, retry the same cursor. Make downstream writes idempotent using `event_id`; manual retries must not send duplicate messages or create duplicate records.
7. Configure alerts for authentication failures and repeated downstream errors. Recheck permissions after role changes. Do not publish or activate the workflow until credentials, cursor persistence, deduplication and failure handling are configured.

PMS task creation, schedule changes and template/intake actions use the same stored activity history. This preparation adds no unauthenticated write endpoint and sends no user data to n8n.

Official references: [HTTP Request node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.httprequest/), [Schedule Trigger](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.scheduletrigger/).
