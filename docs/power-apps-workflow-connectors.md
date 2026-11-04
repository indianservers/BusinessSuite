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

## Native subscriptions and event sources

New connector triggers require no signed relay. Enabling **Connector events**
queues native setup on the existing automation worker. Runtime shows pending,
active, retrying, cleanup and disabled status. **Retry native setup** requests
reconciliation. Disabling a trigger queues removal of its owned remote resources.
Changing a published setup retires the previous registration before creating its
replacement. Provider permissions are checked through the saved connection.

Apply the additive migration before enabling these triggers: from the backend
environment run `alembic upgrade head`. The configured PostgreSQL track includes
`pg_20261104_077_native_events`; the legacy track includes
`20261104_061_native_events`. Tests create isolated schemas and exercise the
migration separately. No production migration is run by the implementation.

Webhook delivery requires `BACKEND_PUBLIC_URL` to be an externally reachable HTTPS
backend. Callbacks use `/api/v1/power-apps/native-hooks/{endpoint}`; Slack and Meta
use an app callback under `/api/v1/power-apps/native-apps/{module}/{app_id}`.
The worker registers these URLs automatically. No user bearer token is required
on provider callbacks: their own signature, channel token or client-state protocol
is validated. Graph validation tokens and Slack/Meta challenges are answered in
their native formats. Raw signed bytes bypass rich-text request rewriting.

Provider setup:

- **Outlook, OneDrive, SharePoint, Microsoft Calendar and Teams:** Graph subscriptions
  are created automatically, renewed with PATCH and deleted on disable. Configure
  mailbox/folder, drive/site/list, calendar, or team/channel/chat as appropriate.
  The account/app needs the matching Graph read permissions and tenant consent.
  Graph lifecycle requests reauthorize or recreate subscriptions; missed mailbox
  notifications can be recovered through the message delta API.
- **Google Drive and Calendar:** native notification channels are created and
  renewed with overlapping channels. Channel IDs/tokens/resource IDs are checked.
  The worker follows Drive changes and Calendar sync cursors; calendar reminders
  use the worker clock. Drive access is limited by the connection's OAuth scopes.
- **Gmail and Google Forms:** enter a Google Cloud project ID and a service-account
  JSON document in the write-only Runtime credential field. The service account
  needs Pub/Sub administration/IAM permissions in that project; enable Pub/Sub and
  the relevant Workspace API. Power Apps creates topics and pull subscriptions,
  merges the publisher role into topic IAM without replacing unrelated bindings,
  creates/renews mailbox/form watches, consumes history/responses, and acknowledges
  Pub/Sub messages after durable run/cursor commits. Gmail OAuth and the topic must
  use the same Google developer project. Form watches expire weekly and are renewed.
- **GitHub:** repository Webhooks write permission is required. Power Apps creates
  repository hooks and verifies `X-Hub-Signature-256` over raw bytes. A changed
  unsigned delivery header cannot bypass duplicate protection.
- **ClickUp:** select a Workspace and optional Space/List. The returned per-hook
  secret is encrypted and validates the provider's `X-Signature` header.
- **Box:** select a non-root folder and enter the app's primary webhook signing key
  in Runtime. Power Apps creates/removes the v2 hook and validates Box signatures
  and delivery timestamps. Folder `0` is not supported by Box v2 webhooks.
- **Airtable:** select base/table and optionally a view or watched field IDs. Hook
  creation, refresh, MAC-secret storage, payload-cursor reads and deletion are
  automatic. Condition fields refer to Airtable field IDs. Creator-level access
  and the provider's webhook scopes are required.
- **Zoho CRM:** select a module. The token needs notification-management scopes.
  Native notification watches are created, renewed and removed; callback channel
  IDs and tokens are verified and changed records are fetched from Zoho.
- **Jira:** an account able to administer webhooks is required. Native admin hooks
  wake an authorized Jira REST read. Jira admin webhooks are unsigned, so callback
  issue data is never trusted as workflow input; comments are fetched and verified
  against the selected project and trigger start time.
- **Slack:** enter an app ID, signing secret and app configuration access token in
  Runtime. Power Apps exports the app manifest, preserves unrelated settings,
  merges event subscriptions and manages the shared callback for its workflows.
  Use a dedicated Events API app with the event read scopes already approved.
  An existing foreign callback is rejected rather than overwritten. Notifications
  must match the bot token's workspace and configured app ID.
- **WhatsApp Business:** select app ID, API version, WABA and optional phone number;
  enter the Meta app secret in Runtime. The worker configures the app subscription,
  subscribes the WABA and sets its callback override. Native SHA-256 signatures,
  verify-token challenges, WABA and phone bindings are checked.
- **HubSpot:** the default journal mode creates v4 subscriptions and consumes native
  journal files using encrypted developer-app client credentials. The connected
  CRM account determines the portal binding. The app must have access to HubSpot's
  journal beta and developer journal read/subscription read/write scopes. Signed
  S3 journal downloads never receive the app bearer token. Select `polling` mode
  for accounts without journal access; it uses direct CRM reads and snapshots.
- **Salesforce:** record events use authorized REST snapshots. Platform events use
  native CometD subscription, wrapped Bayeux messages and persisted replay IDs.
  Select the API version and `/event/...` or `/data/...` channel; Salesforce must
  grant Streaming API/channel access.
- **Dropbox and Notion:** automatic native change reads are used because their
  developer settings do not offer a general webhook-URL creation API. Dropbox
  cursors cover file changes; Notion reads the selected page/data source or shared
  page collection. No external event router is needed. First snapshots establish
  a baseline; changes that occur and revert between polls cannot be observed.
- **HTTP:** incoming JSON uses a generated callback bearer credential shown once.
  Send it in `Authorization: Bearer ...`; use `Idempotency-Key` for explicit
  delivery identities. Response-condition triggers use a read-only allowlisted
  request and fire when the configured condition becomes true.

Provider setup credentials stay encrypted and are never written into workflow
definitions or public trigger responses. Authenticated notifications enter an
encrypted, branch-owned durable inbox. Successful processing clears its payload
but retains duplicate-protection metadata. Source cursors commit with workflow
runs; stale workers are fenced after publication changes or disable operations.
Native snapshot watches are bounded to 1,000 records/512 KB and provider pages
are bounded; narrow the selected resource if these limits are exceeded. Calendar
reminder lookahead uses 90 days. Provider retention windows still apply.

Previously published relay configurations remain compatible. New setup selects
native delivery and does not expose or require the relay signing protocol.

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
