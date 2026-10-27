# Power Apps Integration Studio

## Implemented surface

Integration Studio is available at `/power-apps/connectors` (also `/power-apps/integrations`). The automation node library exposes named connector nodes backed by the existing worker and encrypted credential vault. The catalog currently registers 44 connectors and 103 actions; incoming webhooks reuse the existing trigger rather than introducing a second ingress engine. Forty-three connector action node types are added to the existing node catalog.

The gallery supports provider/category search, account creation, read probes, explicitly confirmed write actions, connection enable/disable and write authorization, and request monitoring. The canvas provides account selection and guided action inputs, including safe references to webhook payloads and earlier outputs. Credentials never enter workflow JSON or responses. A webhook-only receiver and three configurable connected starter workflows begin with signed webhooks: Sheets/email, Groq/Slack and Google Forms/Gmail. Starters remain drafts and require saved connections, provider IDs, model selection and intentional write authorization.

## Connections and live tests

Every account must be authorized by its owner. Live tests are not inferred from fixtures, catalog availability or connection creation. The first requested live targets are Google Sheets, email and Groq; the user subsequently selected dummy tests for this pass and deferred all real-account tests. Do not paste credentials in chat or commit them. Use the account dialog.

Google and Microsoft OAuth use the existing server-side PKCE flow. Configure `POWER_GOOGLE_CLIENT_ID`, `POWER_GOOGLE_CLIENT_SECRET`, `POWER_MICROSOFT_CLIENT_ID`, `POWER_MICROSOFT_CLIENT_SECRET`, and the exact `POWER_OAUTH_REDIRECT_URI` when using that flow. The callback is `/api/v1/power-apps/integrations/oauth/callback`. Google service accounts and explicitly supplied access tokens are also supported where listed in the provider manifest. Static bearer tokens do not gain refresh capability; rotate or reconnect them when they expire. Other providers currently accept the listed API credential/authentication types rather than claiming one-click OAuth setup for every service.

An email provider accepting a request is not confirmation that the recipient received it. OpenRouter public model-list responses do not verify credential validity. Other successful authenticated actions update connection health; failed authentication invalidates it. No live provider success is claimed in this report.

## Webhook-first setup

1. Open Connectors and create the intended accounts with the required scopes. Enable external writes only for the connections intended to send/create data.
2. Choose a webhook starter or add Webhook Trigger to an automation. Select saved accounts on every action and configure the spreadsheet, channel, verified sender or model ID.
3. Map fields using `{{trigger.input.message}}`, `{{trigger.input.email}}` or declared step outputs. Groq/AI text is available as `{{steps.action_1.output.text}}` in the Groq/Slack starter.
4. Authorize intended write nodes explicitly, validate, publish with the existing owner delegation policy, and activate the workflow.
5. Open Publish & runs and configure its webhook trigger. Save the one-time signing secret securely. Use the returned endpoint. The sender signs timestamp + dot + nonce + dot + exact JSON bytes with HMAC-SHA256.
6. Send the event and inspect the existing run history and Integration Studio request monitor. Reused nonces are rejected. External writes with an uncertain outcome require provider reconciliation rather than blind resend.

Google Forms can be called through its read/create API actions. For form-submit push events, use an authorized installable Forms Apps Script trigger ([sender sample](examples/google-forms-webhook.gs)) or your own signed sender; this release does not claim a native Google Forms push subscription or polling cursor.

## Execution and security

The existing Phase 3 queue remains the only workflow runtime. External nodes commit dispatch intent before network I/O and release database transactions during provider calls. A durable operation key is tied to the workflow run/step and connection. Successful results are reused, uncertain mutations are not automatically resent, and lease/cancellation checks fence completion after network I/O. Losing a worker lease cannot erase an external result from the operation journal.

Connection and credential access is company/environment/owner scoped. Cross-owner, cross-tenant, disabled-module and read-only callers are covered by tests. Sharing is intentionally rejected by the new public connection API until a separate sharing authorization review is completed. Disabled connections and missing/incorrect account references stop dispatch. External writes require both connection opt-in and the published node confirmation, rechecked at execution.

Provider origins are fixed or explicitly approved HTTPS hosts. The shared transport verifies every resolved address, rejects application/private/metadata/loopback targets, pins sockets to a validated address and verifies TLS for the original hostname. Redirects and responses are bounded. Existing per-connection gates provide rate/concurrency/circuit control. Provider responses and errors are scrubbed; monitor metadata omits credentials and request bodies.

The existing migration 036 creates connector tables in both migration trees. This change adds no tables. Apply the repository migration chain before enabling the API in a database that has not received 036. Run `python -m app.apps.power_apps.worker` from the backend directory. No production database migration or external-account authorization was performed during automated QA.

## Current limits

Provider coverage is a bounded selection of actions for each listed service, not parity with its entire API. Schema errors, remote API changes, actual account scopes and delivery outcomes still require live verification. Most new REST actions read one bounded provider page. There is no claim of automatic OAuth registration for every provider, arbitrary provider actions, automatic reconciliation of unknown writes, complete company-wide integration quotas or native subscriptions for every app. PostgreSQL setup currently uses the typed API for database/table allowlists; its account form points this out. Provider secrets use the existing SECRET_KEY-derived encryption primitive; preserve its documented key-rotation procedure.

## Registered integrations and supported actions

### AI Services

- [Business Suite AI Gateway](https://platform.openai.com/docs/api-reference/responses): Generate Text; Summarize Text; Classify Content; Extract Structured Data; Analyze Sentiment; Identify Action Items; Normalize Data; Translate Text; Compare Documents; Generate JSON Output; Route by Classification; Explain an Error; Create Draft Message; Process Form Data; Analyze Feedback.
- [Groq](https://console.groq.com/docs/api-reference): List models; Generate text.
- [Anthropic](https://docs.anthropic.com/en/api/messages): List models; Generate text.
- [Mistral AI](https://docs.mistral.ai/api/): List models; Generate text.
- [Cohere](https://docs.cohere.com/reference/chat): Generate text.
- [OpenRouter](https://openrouter.ai/docs/api-reference/chat-completion): List models; Generate text.
- [DeepSeek](https://api-docs.deepseek.com/api/create-chat-completion): List models; Generate text.

### CRM

- [HubSpot](https://developers.hubspot.com/docs/api-reference/crm-contacts-v3/basic/post-crm-v3-objects-contacts): List contacts; Create contact.
- [Pipedrive](https://developers.pipedrive.com/docs/api/v1/Persons): List people; Create person.

### Collaboration

- [Notion](https://developers.notion.com/reference/post-page): Verify integration; Create child page.

### Communication

- [Google Chat](https://developers.google.com/workspace/chat/api/reference/rest/v1/spaces.messages/create): List spaces; Send message.
- [Slack](https://docs.slack.dev/reference/methods/chat.postMessage): Verify Slack identity; Send channel message.
- [Telegram Bot](https://core.telegram.org/bots/api#sendmessage): Verify bot; Send message.
- [Discord](https://discord.com/developers/docs/resources/channel#create-message): Verify bot; Send channel message.

### Databases

- [PostgreSQL](https://www.postgresql.org/docs/current/libpq-ssl.html): Test database; Inspect approved schema; Read records; Insert record; Update records; Delete records.
- [Airtable](https://airtable.com/developers/web/api/create-records): List records; Create record.

### Developer Tools

- [GitHub](https://docs.github.com/en/rest/issues/issues): Verify GitHub account; List repository issues; Create issue.
- [GitLab](https://docs.gitlab.com/api/issues/): Verify account; Create project issue.
- [Bitbucket](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-repositories/): Verify account; List workspace repositories.

### Email

- [Authorized SMTP](https://docs.python.org/3/library/smtplib.html): Test authorized SMTP transport; Send email.
- [Microsoft Outlook](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0): Verify account; List message summaries; Submit email.
- [Gmail](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send): Verify Gmail account; Send email.
- [SendGrid](https://www.twilio.com/docs/sendgrid/api-reference/mail-send/mail-send): Send email.
- [Resend](https://resend.com/docs/api-reference/emails/send-email): Send email.
- [Brevo](https://developers.brevo.com/reference/sendtransacemail): Verify account; Send transactional email.
- [Postmark](https://postmarkapp.com/developer/api/email-api): Send transactional email.

### File Storage

- [Google Drive](https://developers.google.com/workspace/drive/api/guides/api-specific-auth): List app-visible files; List app-visible files; Read file metadata; Create text file.

### Payments

- [Stripe](https://docs.stripe.com/api/customers/create): Verify Stripe account; Create customer.
- [Razorpay](https://razorpay.com/docs/api/customers/create/): List customers; Create customer.

### Productivity

- [Google Sheets](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/append): Verify spreadsheet access; Read values; Append rows.
- [Google Forms](https://developers.google.com/workspace/forms/api/reference/rest): Read form; Read form responses; Create form.
- [Google Calendar](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert): List calendar events; Create event.
- [Google Docs](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents): Read document; Create document.
- [Google Slides](https://developers.google.com/workspace/slides/api/reference/rest/v1/presentations): Read presentation; Create presentation.
- [Google Tasks](https://developers.google.com/workspace/tasks/reference/rest/v1/tasks/insert): List tasks; Create task.
- [Google Contacts](https://developers.google.com/people/api/rest/v1/people/createContact): List contacts; Create contact.

### Project Management

- [Asana](https://developers.asana.com/reference/createtask): Verify account; Create task.
- [ClickUp](https://developer.clickup.com/reference/createtask): Verify account; Create task.
- [monday.com](https://developer.monday.com/api-reference/reference/items): Verify account; Create board item.
- [Todoist](https://developer.todoist.com/api/v1/): List tasks; Create task.
- [Linear](https://linear.app/developers/graphql): Verify account; Create issue.

### Webhooks and APIs

- [HTTP API](https://developer.mozilla.org/en-US/docs/Web/HTTP): Send HTTP request.
- [Incoming Webhooks](https://datatracker.ietf.org/doc/html/rfc2104): existing signed incoming webhook trigger.
- [Outgoing Webhooks](https://datatracker.ietf.org/doc/html/rfc2104): Deliver signed webhook.

## Automated verification

Tests cover each new provider action request shape and fixed origin, authentication/remote/rate-limit/server failures, application-level failures, a real local TLS fixture, encrypted credentials and tenant/owner boundaries, write opt-in, duplicate suppression, unknown write outcomes, worker integration and signed webhook replay. Google Sheets append and SMTP use the existing mapping/queue/mail components with controlled provider transports. Browser QA covers the forty-plus gallery, secure account creation, mobile layout and a webhook starter with guided provider controls. These fixtures never send fabricated credentials to real providers.

Use `tests/test_power_provider_actions.py`, `tests/test_power_connector_runtime.py` and the existing connector foundation/runtime/approval tests. Browser command: `npx playwright test --config=playwright.integrations.config.ts`. Final verification: 457 PostgreSQL Power Apps regression checks passed during implementation; 292 focused PostgreSQL connector/provider/SMTP checks passed after hardening; a final PostgreSQL cancellation/operation-journal check passed. The final browser run passed all three scenarios, including actual draft persistence of the selected account and model fields. Frontend TypeScript, targeted ESLint and production build passed. The transport checks include a real local TLS server with fixture-only routing, not calls to provider production accounts. All real-account testing was explicitly deferred by the user.

The Forms sender sample follows the official [Forms event contract](https://developers.google.com/apps-script/guides/triggers/events) and [Utilities HMAC API](https://developers.google.com/apps-script/reference/utilities/utilities). Store the endpoint/secret in Script Properties, install a Forms submit trigger and match the question names to your form. It is provided for authorized setup; no real Google Form submission was performed during fixture tests.
