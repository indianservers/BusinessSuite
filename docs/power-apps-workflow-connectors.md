# Workflow automation connectors

The workflow builder exposes actions and event-trigger nodes for these 25 modules:
Gmail, Outlook, Telegram, WhatsApp Business, Slack, Microsoft Teams, Google
Sheets, Excel Online, Google Drive, OneDrive, SharePoint, Dropbox, Box, Google
Calendar, Microsoft Calendar, Google Forms, Notion, Airtable, HubSpot, Salesforce,
Zoho CRM, Jira, ClickUp, GitHub, and HTTP API.

## Configure and run

1. Add an integration action or an event trigger from the node library.
2. Create/select an authorized connection in Module settings or Connection settings.
   Credentials stay in the encrypted server vault. Microsoft Graph modules support
   the configured Microsoft OAuth application or a supplied bearer token. Other
   modules expose their supported connection types in the catalog. Jira requires
   the tenant hostname; Salesforce requires its instance hostname; Zoho requires
   the regional API hostname. Hostnames exclude the scheme and path.
3. Select the action/event and populate its generated fields. Object/array fields
   use JSON; workflow expressions may map action inputs from earlier steps.
4. Enable connection writes and authorize each mutating action when required.
5. Publish the workflow with owner delegation or an authorized service identity.
6. For an event-trigger workflow, open Runtime, select **Connector events**, keep
   the policy `{}`, and save with the trigger enabled. Setup comes from the
   published trigger node, preventing unpublished configuration from executing.
7. Run `python -m app.apps.power_apps.worker` from the backend environment.

Previously published action contracts retain their original fields and handlers.
Where an expanded operation overlaps an existing action, its expanded version is
exposed with an `_advanced` action ID.

## Telegram incoming events

Telegram uses `getUpdates` polling, with a durable offset and one active listener
per bot. It receives text, captions, photos, documents, voice payloads, channel
posts, edited messages, callbacks and membership updates that Telegram delivers
to the bot. Select the event and optionally a chat ID. It does not require send
permission to receive messages. Remove an existing webhook before enabling
polling. External polling consumers must also be stopped. Group privacy and bot
administrator permissions still apply. The bot API does not provide arbitrary
chat history.

The trigger output is available as `trigger.input`, including `event`, `event_id`,
`chat_id`, `text`, `message` and the original `update`. Fetch attachment metadata
using Get file, then use Download file with its relative `file_path`.

## Spreadsheet row updates

Google Sheets polls an A1 range containing a header row. Excel Online polls a
structured table and its column definitions. Configure a stable unique key column,
optional watched columns, interval and optionally equality conditions. Supported
events are row added, row updated, row deleted, cell changed and condition matched.

The first sample establishes a baseline unless **Emit initial** is enabled. Rows
are matched by key, so reordering is not an update. Changing a key is a deletion
and an insertion. A condition event fires when a row enters the matching state.
Blank rows are ignored; duplicate/missing keys fail the sample. Previous snapshots
are encrypted and omitted from public trigger responses.

Limits per watch: 1,000 rows, 64 KB of snapshot JSON, 100 emitted changes per sample.
Google Sheets/Excel intervals are 15–3,600 seconds (default 30); these are polling
updates, not a promise of instantaneous cell events. Incomplete paginated Excel
responses fail closed. Narrow the table/range rather than silently dropping pages.
Trigger outputs include `row_key`, `current`, `previous`, `changed_columns`, `event`
and `timestamp`. Watch relevant input columns to avoid loops caused by writing
back to a watched output column. Provider changes that occur and revert between
polls cannot be observed.

Find rows and Upsert row are available for both spreadsheet providers. Google
Sheets upserts require a bounded A1 range, such as `Sheet1!A1:Z1000`. Upserts
preserve unspecified columns and reject duplicate matching keys. They use a
read-then-write sequence; concurrent edits outside this workflow are not an
atomic database transaction.

## Other provider events: signed relay setup

The remaining event nodes implement authenticated relay ingress. They do **not**
automatically create provider-native subscriptions, renew provider watches, or
verify provider-specific webhook signatures. Configure a trusted relay to receive
the provider's webhook/subscription, verify that provider's authentication, map
the provider event to the selected catalog event, and forward this envelope:

```json
{
  "event": "mention_received",
  "event_id": "stable-provider-event-id",
  "data": {"text": "Hello", "channel": "C123"}
}
```

Enabling the trigger returns its `/api/v1/power-apps/hooks/...` endpoint and a
one-time signing secret. Send `X-Power-Timestamp` (Unix seconds), `X-Power-Nonce`
(unique, 8–180 characters), and `X-Power-Signature` (hex HMAC-SHA256 of
`timestamp + "." + nonce + "." + raw_body`). Timestamp tolerance is five minutes;
request bodies are limited to 32 KB. Replay nonces are rejected and stable provider
event IDs deduplicate separate deliveries. Optional equality filters apply to
`data`. A saved connection remains required and is reauthorized at ingress.
Provider-specific setup fields include mailbox/folder/label, drive/site/list,
channel/chat, calendar, form, CRM object/pipeline/stage, project, repository/branch,
and watched fields. The relay must normalize these selectors into the matching
`data` keys. Text/subject contains fields filter the corresponding text; watched
fields match `data.changed_fields`; a Gmail label matches `data.label_ids`.
Rotate a relay secret from Runtime when required. A newly published workflow
version must have its connector trigger configured again.

## Files and verification

Uploads accept base64 file content. Downloads return base64 and MIME type within
the existing 64 KB step-output budget. Larger files require a separate streaming
file pipeline; upload-session creation is available for supported Graph drives.
Download redirects are limited to known provider content domains, revalidate
public DNS/TLS, and never forward API authorization headers to those domains.
Slack uploads use the current external-upload URL and completion flow.

Automated checks use isolated provider fixtures. A connection is live-verified
only after an authorized request succeeds. No customer-provider credentials are
included or live accounts modified by the test suite.
