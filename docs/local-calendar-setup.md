# Local two-way calendar sync

Set these backend/.env values and restart the backend. Register each exact callback URL with the provider:

```
CRM_GOOGLE_CALENDAR_CLIENT_ID=
CRM_GOOGLE_CALENDAR_CLIENT_SECRET=
CRM_GOOGLE_CALENDAR_REDIRECT_URI=http://localhost:5174/crm/calendar-integrations
CRM_OUTLOOK_CALENDAR_CLIENT_ID=
CRM_OUTLOOK_CALENDAR_CLIENT_SECRET=
CRM_OUTLOOK_CALENDAR_REDIRECT_URI=http://localhost:5174/crm/calendar-integrations
```

Enable Google Calendar API with calendar.events plus openid/email consent. For Microsoft Entra register a Web callback and delegated Calendars.ReadWrite, User.Read and offline_access. Keep credentials on the backend and keep SECRET_KEY stable for encrypted token storage.

Set CALENDAR_SYNC_WORKER_ENABLED=true and CALENDAR_SYNC_INTERVAL_SECONDS=60. Restart the backend after changing configuration. The local backend uses port 1534; callbacks go to the frontend on port 5174. No public tunnel or webhook is required.

Open CRM / Calendar Integrations and grant consent separately for both accounts. Reconnect older connections to grant the additional identity scopes. Verified connections cannot silently switch calendar accounts: disconnect before selecting a different account.

Sales shares CRM meeting records. PMS / Calendar / Settings / Accounts uses the same connected accounts. Events, edits and deletions sync in both directions. Imported events can also reach the other connected provider through their local record. Only your own records in the connection's authorized branch are exported; shared workspace visibility does not grant export rights.

## Sync controls

- Automatic sync runs every 60 seconds while the backend is running. Pause each account independently or use Sync now, including while paused.
- Choose Sales/CRM meetings or the PMS calendar as the destination for new external events. Existing mappings retain their destination.
- New events are discovered from 90 days ago through one year ahead. The discovery window renews monthly. Existing mappings remain tracked outside that window.
- Provider checkpoints, event IDs and agreed snapshots persist in PostgreSQL. Restarts and repeated pages do not duplicate imports. Rotated refresh tokens are saved before further requests. Failures use exponential backoff and provider Retry-After.
- Simultaneous edits, including deletion versus modification, create conflicts. Compare both versions and choose Keep local or Keep calendar. Other events continue syncing.
- External deletions cancel and soft-delete CRM meetings and remove PMS events. Local deletions remove the external copy. Retained mappings prevent resurrection.
- All-day events appear as day-spanning local records. Recurrence rules stay with the provider; expanded occurrences sync individually. Attendees, invitations and series-rule authoring remain managed in Google/Outlook.
- The worker starts and stops with FastAPI and respects company database routing and branch authorization. It is disabled in tests and serverless mode.

## Database and startup

Apply Alembic head with the schema-owner migration connection before starting the API. The migration adds calendar_sync_states and calendar_event_links. The restricted runtime role intentionally cannot create tables. Existing local default privileges grant runtime access to new tables. Managed company databases need the normal company migration procedure before sync is enabled there.

The local schema was upgraded to pg_20261107_088_calendar_sync during implementation. Start the backend with start-backend.cmd and the frontend with its normal local command.

Tests use simulated provider HTTP responses and isolated databases. Live connections require your provider app credentials and sign-in consent; these credentials were not configured during implementation.

References: [Google incremental sync](https://developers.google.com/workspace/calendar/api/guides/sync), [Microsoft calendar delta](https://learn.microsoft.com/en-us/graph/api/event-delta?view=graph-rest-1.0).
