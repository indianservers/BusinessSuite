# WhatsApp Cloud API

Sender numbers and credentials belong to each deployment. Never put tokens,
app secrets, sender numbers or WABA IDs in frontend code or committed config.
Use backend environment variables, then restart/redeploy after changing them.

## Deployment configuration

```dotenv
CRM_WHATSAPP_PROVIDER=meta
CRM_WHATSAPP_ACCESS_TOKEN=<server-side access token>
CRM_WHATSAPP_PHONE_NUMBER_ID=<Meta phone number ID, not the display number>
CRM_WHATSAPP_BUSINESS_ACCOUNT_ID=<WhatsApp Business Account ID>
CRM_WHATSAPP_ORGANIZATION_ID=<authorized Business Suite company ID>
CRM_WHATSAPP_API_VERSION=v26.0
CRM_WHATSAPP_APP_SECRET=<Facebook app secret for HMAC verification>
CRM_WHATSAPP_VERIFY_TOKEN=<random deployment-specific webhook verify token>
CRM_WHATSAPP_APP_ID=<Meta app ID>
CRM_WHATSAPP_EMBEDDED_CONFIG_ID=<Facebook Login for Business configuration ID>
```

Each company can connect one customer-owned WABA/sender in Account settings,
through Embedded Signup or a verified manual connection. Customer tokens are
encrypted with the application's credential encryption key and never returned
by the API. Keep that encryption key stable across deployments and protect its
backup. A sender cannot be actively assigned to multiple companies. The optional
environment sender is available only to CRM_WHATSAPP_ORGANIZATION_ID. Changing
deployments or customer numbers does not require source edits.

## Meta webhook

For Indian Servers, use:

`https://app.indianservers.com/api/v1/integrations/whatsapp/webhook`

1. Deploy the API and environment configuration first.
2. In the Facebook developer app, WhatsApp Configuration / Webhooks, enter that
   callback and the configured verify token; click Verify and save.
3. Subscribe to `messages` at the same Graph API version.
4. Ensure the app is subscribed to the correct WABA (`/{WABA_ID}/subscribed_apps`).
5. Confirm signed delivery callbacks arrive for a real outbound message.

GET echoes Meta's challenge only with a matching verification token. POST checks
HMAC-SHA256 over the original raw bytes using the app secret. Updates must match
the configured WABA, phone number ID, organization, provider, and message ID.
Duplicate/out-of-order callbacks cannot downgrade delivered/read messages.
Signed inbound messages and delivery receipts are stored against the matching
customer connection. Duplicate messages are ignored. Text STOP/UNSUBSCRIBE and
related opt-out keywords block sending; START/SUBSCRIBE records opt-in. No
automatic replies are sent. Media messages currently show their type; attachments
are not downloaded. Business-scoped user IDs without phone numbers are not yet
supported.

## Sending

Open `/crm/whatsapp` for Send message, Inbox & delivery, Meta templates, and
administrator Account settings. Sales users must use an accessible CRM record;
administrators can also manage unlinked conversations. The existing
`POST /api/v1/crm/messages/send` also supports:

```json
{
  "channel": "whatsapp",
  "requestId": "unique-stable-client-request-id",
  "entityType": "lead",
  "entityId": 123,
  "country_code": "+91",
  "to": "9876543210",
  "body": "Template: hello_world",
  "whatsappTemplateName": "hello_world",
  "whatsappTemplateLanguage": "en_US"
}
```

The number above is illustrative; choose an explicitly authorized recipient for
live tests. Approved template components can be supplied through
`whatsappTemplateComponents` in the API. The simple page supports templates that
need no components or numbered body text variables. Local template IDs do not imply Meta template approval.
Omit `whatsappTemplateName` for free text inside the customer service window.
Business Suite also blocks opted-out recipients, requires recorded opt-in for
templates, checks actual Meta template approval, and requires a webhook-observed
inbound message within 24 hours for free text. Meta enforces its remaining
eligibility and billing requirements. The per-organization API limit is 30
outbound reservations per minute.

`accepted` means Meta accepted the request, not that it reached the phone.
Webhook statuses move the stored CRM message through sent/delivered/read/failed.
Transport uncertainty is marked `reconciliation_required`; do not blindly retry.
No automatic send retries are made. Requests with the same requestId and payload
return the durable original reservation, including uncertain outcomes, rather
than sending again. A different payload with the same ID is rejected. Receipts
arriving before provider acceptance is saved are retained and replayed. Reconcile
a crash between provider acceptance and local persistence before creating a new
request ID. Legacy CRM callers should supply requestId for the same guarantees.

## Customer API and onboarding

Use the existing Business Suite bearer authentication, organization context, and
CRM permissions; do not share Meta credentials with software customers. See the
deployment's OpenAPI documentation for these `/api/v1/integrations/whatsapp` APIs:

- `GET /status`, `POST /connection`, `/connection/environment`, `/connection/check`, `/connection/register`.
- `POST /connection/inbound-branch`: select a writable branch in the top bar,
  then route new inbound conversations there. Existing conversations retain
  their branch. Without a route, signed inbound data is retained privately,
  unresolved, for a global administrator to link to a permitted CRM record.
- `POST /onboarding/start` and `/onboarding/complete`: actor/company-bound,
  ten-minute, single-use server session; codes and registration PINs are not stored.
- `GET|POST /templates`: actual Meta templates and text-template review submission.
- `POST /consent`, `POST /messages`, `GET /conversations`,
  `GET /conversations/{id}/messages`, and administrator `POST /conversations/{id}/link`.
- `DELETE /connection`: clears local credentials, disables sending and inbound
  routing, retains history. Revoke the app in Meta to finish provider revocation.
  It deliberately does not unsubscribe the entire WABA, which may have other senders.

Configure the deployed domain and JavaScript SDK allowance in Meta's Facebook
Login for Business settings. External customer onboarding requires applicable
Advanced Access approval; a configured signup button does not imply approval.
Customers pay Meta directly; this integration does not supply a credit line.

Before production deployment, rehearse the additive PostgreSQL migration
`pg_20261103_065_whatsapp` on an isolated production branch. No history tables are
dropped on downgrade. Consent evidence, retention periods, data-subject requests,
customer service terms, and operational monitoring remain the business owner's
responsibility; do not certify policies merely because fields exist in the app.

## Account checked on 3 November 2026

Facebook app `320348640687450`, portfolio `254758805217071`.
Selected sender: Indian Servers Private Limited, `+91 92464 78419`.
Phone number ID `267339059794803`; WABA `283980451458391`.
These are setup notes only; runtime code does not use these values as defaults.
Meta returned `code_verification_status=EXPIRED`, `quality_rating=UNKNOWN` and
showed a missing/ineligible payment-method warning for two accounts.
An additional read confirmed `status=CONNECTED` and `platform_type=CLOUD_API`;
the expired verification-code status alone does not establish a sending failure.
Actual message acceptance and delivery still need a real recipient test.
The WABA already lists this app in `subscribed_apps`, and `hello_world` is an
approved `en_US` template. No additional WABA app subscription or template
creation is needed for that initial test.

Deployment credentials are kept in ignored `.local/whatsapp.env` and backend
environment configuration. The initial temporary token has been replaced with
a system-user token with no scheduled expiry. It can still be revoked by Meta
or the business; never commit it or expose it to the browser.
The live domain currently belongs to Vercel project `indianservers-app`
(`prj_b3XOky29D6HclRNTh6nu5kJtiI2q`), not the checkout's `businesssuite` link.

## Live setup completed on 3 November 2026

Deployment `dpl_BkzMunGHQaAd7GW5k9P6SehWPya4` is ready on
`https://app.indianservers.com`. Production and local backend environments have
the deployment's WhatsApp settings; the sender is assigned to company `1`.
The local backend was subsequently restarted for the non-expiring token rollout.

Meta verified and saved the callback above. The `messages` webhook field is
subscribed at `v26.0`. Live checks returned the expected challenge (200), rejected
an unsigned POST (403), and accepted a correctly signed POST (200). Vercel request
records also confirm Facebook's verification request and subsequent webhook POSTs
returned 200, including Meta's sample webhook test.

One explicitly authorized `hello_world` test send was accepted by Meta. Its
private provider message ID is in ignored `.local/whatsapp-live-test.json`.
This transport-only test does not create a CRM customer record and does not
establish handset delivery. Normal sends from the CRM page are stored against
their selected CRM record.
The recipient subsequently supplied a screenshot confirming handset delivery.

## Non-expiring token

On 3 November 2026, created a token for existing system user `userindianservers`
and app `320348640687450`, choosing expiry **Never**. WhatsApp scopes are
`whatsapp_business_messaging` and `whatsapp_business_management`; Meta also
includes its default `public_profile` scope. Unrelated Ads and other business
permissions were not requested.

Meta token debugging confirmed `type=SYSTEM_USER`, `is_valid=true`,
`expires_at=0`, and `data_access_expires_at=0`. A read with that token confirmed
access to the configured sender and `status=CONNECTED`. Production environment
read-back matched the verified token. Private validation metadata is stored in
ignored `.local/whatsapp-permanent-token-validation.json`.
Production deployment `dpl_7heyvW4wwPKzKJtaUzjsKc665sn3` is ready and assigned
to `app.indianservers.com` with the new token. Candidate and live health checks
returned 200, and live webhook verification returned the expected challenge.
No additional test message was
sent during token rotation; token validity and sender access were checked with
read-only Meta API requests.

## Customer service / Tech Provider application

Business model confirmed on 3 November 2026: customers pay Meta's messaging
charges directly; Indian Servers charges for CRM/API software. Prepare the
Tech Provider route with each customer authorizing its own WABA and sender.
Do not distribute Indian Servers' system-user token as a customer API key.

Meta's Quickstart shows business verification complete and App Review incomplete.
Current Permissions and Features shows **Standard access** for both WhatsApp
permissions, despite an earlier review feedback page saying messaging was
approved. The historical feedback is not evidence of current Advanced Access.

Existing App Review draft `970372292351745` has not been submitted. Saved factual
usage descriptions for `whatsapp_business_messaging` and
`whatsapp_business_management`, describing the intended customer CRM/software
use and explicitly distinguishing it from the own-sender implementation.
Controller details are Indian Servers Private Limited, India. The owner
confirmed no national-security disclosures; service-provider details still
need completion, including Vercel and the detected Neon database provider and
their applicable processing countries. Do not certify unimplemented policies.

Created Embedded Signup login configuration **Business Suite WhatsApp**,
ID `1399606888609363`, with Never expiry and the two WhatsApp permissions.
The builder uses Embedded Signup `v4` and session information version `3`.
Configuration creation does not grant Advanced Access or onboard a customer.

Before submission:

- Demonstrate the implemented customer authorization, server-side code exchange,
  tenant-specific encrypted credential/asset storage, account subscription,
  disconnect/revocation, and webhook routing to the correct customer account.
- Demonstrate the implemented account/template management operations in review.
- Record a genuine end-to-end screencast for each requested permission and
  supply a working reviewer login/instructions for the demo environment.
- Complete provider names and processing-country declarations from the actual
  hosting/database arrangements; review the remaining data-handling answers.
- Allow required API-call counters to update. Meta currently shows 0/1 for
  each permission and says successful calls can take up to 24 hours to appear.
- Review and accept Meta's allowed-usage declarations before final submission.

The customer workspace now implements one account/sender per company, Embedded
Signup code exchange, encrypted customer credentials, inbound inbox, persisted
consent, template management, and durable delivery receipts. It uses Business
Suite's existing bearer authentication and CRM permissions. Separate customer
API keys, billing/metering, attachment download, and number-less BSUID recipients
are not implemented. Do not describe those as shipped in the review submission.

Saved `https://app.indianservers.com/` in Meta's JavaScript SDK domain allowlist
with the owner's explicit approval; Login with the JavaScript SDK is enabled.
Meta's Login settings additionally require Advanced Access for `public_profile`.
This requirement and WhatsApp Advanced Access are still outstanding.

Migration rehearsal on production child branch `br-calm-tree-b7ezsnzk` upgraded
`pg_20261103_064_follow_ups` to `pg_20261103_065_whatsapp`, verified all 792 model
tables, created five new WhatsApp tables, and preserved existing record counts.
The branch auto-expires after one day.
The follow-up rehearsal upgraded the same branch to
`pg_20261103_066_wa_branch`, adding explicit inbound branch routing. Account
connections/signup sessions are company configuration; contacts and messages
retain branch ownership in addition to CRM record visibility. Switching to
all-branches mode is for inspection; choose a writable branch before sending.

## Validation

From `backend`, `venv/Scripts/python.exe scripts/run_postgres_tests.py
tests/test_whatsapp_cloud.py tests/test_whatsapp_workspace.py -q` passed 20 tests
against an isolated PostgreSQL database. The same tests passed on SQLite.
`npm run build` from `frontend` passed. Tests mock external sends; live checks
only read token validity and sender metadata and do not message recipients.

## Customer workspace release, 3 November 2026

Deployment `dpl_6uFcoF2FQZu8mYtWpSGRKEN8v8fa` is ready and promoted to
`app.indianservers.com`. Production reached `pg_20261103_066_wa_branch` and
verified 792 tables / 9235 columns. Candidate and live health returned 200 with
database `ok`; webhook verification returned the exact challenge, unsigned
callbacks returned 403, and signed empty callbacks returned 200.

In the signed-in live UI, verified the Indian Servers sender with Meta, loaded
the actual approved `hello_world` template, and routed new inbound conversations
to company 1's Main branch (branch 1). Embedded Signup preparation returned a
one-use session and loaded the Meta SDK successfully; canceled before any new
business authorization. This is not an end-to-end customer onboarding approval.

Submitted `indianservers_service_update` (`en_US`, Utility) through the live
template screen. Meta returned `PENDING`. Body: “Hello {{1}}, your Indian Servers
service request {{2}} is now {{3}}. Reply to this message if you need assistance.”
Samples were fictitious values. No extra outbound messages were sent.

The owner approved requesting `public_profile` Advanced Access and explicitly
agreed to Meta's allowed-usage declaration. Usage confirmation is complete, but
the request remains on the data-handling step and has NOT been submitted/granted.
No national-security disclosures and no implemented public-authority request
policies were selected, based on the owner's answers. The old prefilled legality
review checkbox was cleared. Processor details still need confirmation: the
form lists “Indian Servers” and “ISPL”, and needs actual Vercel/Neon processing
countries including remote access. Do not claim US-only merely from the hosting
region. WhatsApp App Review still needs genuine screencasts/reviewer access and
the remaining declarations; do not claim customer production approval.

The local database's separate schema-health check found pre-existing missing
follow-up columns at its old revision. The WhatsApp migration applied, but local
runtime was not restarted over that unrelated schema drift. Production and the
isolated PostgreSQL test database passed schema checks.

## Messaging visibility and profile hotfix

The owner reported a delivered message paired with the old form's generic failure
banner, and a 403 from its separate local-template button. Production contained
no CRM or durable WhatsApp message record for that old request; its exact provider
outcome cannot be reconstructed from the application database. Do not resend it
or manufacture a delivered/failed record. The durable composer now looks up its
original request after response errors and distinguishes unknown outcomes from
provider-reported failures. The obsolete local-template creation button was
removed from the WhatsApp workspace; use the actual Meta template page.

Dedicated routes are `/crm/whatsapp/inbox`, `/crm/whatsapp/sent`,
`/crm/whatsapp/templates`, and `/crm/whatsapp/profile`. Received messages and
delivery records retain company, branch and CRM record visibility checks.
`GET /integrations/whatsapp/messages/by-request/{request_id}` reconciles a recorded
send without sending again; `GET /integrations/whatsapp/messages` lists outbound
records. `GET /integrations/whatsapp/profile` reads the actual Meta profile and
administrator `POST /integrations/whatsapp/profile/picture` accepts a square JPEG
up to 2 MB, 192–4096 pixels, with a provider-pinned resumable upload.

Meta initially returned no `profile_picture_url`. Uploaded the existing square
Indian Servers JPEG logo from the company's public website and updated the
connected WhatsApp business profile. Meta returned success and a profile photo
URL afterward. This is separate from the Facebook app logo and Suite avatar.

The owner sent a real inbound “Hi”; production saved inbound message 1 as received
and stamped Main branch 1. No additional outbound WhatsApp message was sent.
The isolated WhatsApp release passed 24 tests on PostgreSQL and a frontend build.
It excludes the unrelated in-progress customer-communication migration 067.
Deployment `dpl_24HnB3tpP7LYUFDekYksjixCEoG5` was promoted to the live domain.

Live UI confirmation: the received “Hi” is visible in its conversation. Submitted
`indianservers_request_received` through the Meta template form while in All
branches; Meta returned PENDING without a 403. The previous
`indianservers_service_update` template is now APPROVED. The optional outgoing
retest requires a separate owner approval; do not reuse the initial one-message
hello_world authorization.

The owner subsequently approved exactly one new text reply to the existing
inbound conversation. Sent through the live app: “Indian Servers WhatsApp test:
your message was received and the integration is working.” Durable message 17
was accepted, then updated to delivered by Meta callbacks and shown as delivered
in the conversation. Do not send further test messages under that approval.
Private validation metadata is in ignored `.local/whatsapp-hotfix-live-validation.json`.
