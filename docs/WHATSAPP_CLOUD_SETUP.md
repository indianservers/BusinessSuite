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
```

One configured sender is assigned to one company per deployment. Other companies
cannot send through it. Separate deployments can use different accounts/numbers
without changing source code. Multi-sender onboarding within one deployment is
outside this adapter's scope.

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
Unknown callbacks are acknowledged; inbound customer messages are not stored or
auto-replied to by this outbound adapter.

## Sending

The CRM WhatsApp page sends against an accessible lead/contact/deal. The existing
`POST /api/v1/crm/messages/send` also supports:

```json
{
  "channel": "whatsapp",
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
need no components. Local template IDs do not imply Meta template approval.
Omit `whatsappTemplateName` for free text inside the customer service window.
Meta enforces approval, messaging-window, opt-in, and billing requirements.

`accepted` means Meta accepted the request, not that it reached the phone.
Webhook statuses move the stored CRM message through sent/delivered/read/failed.
Transport uncertainty is marked `reconciliation_required`; do not blindly retry.
No automatic send retries are made. Reconcile a crash between provider acceptance
and local persistence before repeating a send. Status callbacks arriving before
the local message is stored cannot currently be recovered automatically.

## Account checked on 3 November 2026

Facebook app `320348640687450`, portfolio `254758805217071`.
Selected sender: Indian Servers Private Limited, `+91 92464 78419`.
Phone number ID `267339059794803`; WABA `283980451458391`.
These are setup notes only; runtime code does not use these values as defaults.
Meta returned `code_verification_status=EXPIRED`, `quality_rating=UNKNOWN` and
showed a missing/ineligible payment-method warning for two accounts.
The account's operational readiness must be checked before a real send.
The WABA already lists this app in `subscribed_apps`, and `hello_world` is an
approved `en_US` template. No additional WABA app subscription or template
creation is needed for that initial test.

Temporary credentials are kept in ignored `.local/whatsapp.env`. They expire;
replace with an appropriate production system-user token before ongoing use.
The live domain currently belongs to Vercel project `indianservers-app`
(`prj_b3XOky29D6HclRNTh6nu5kJtiI2q`), not the checkout's `businesssuite` link.

## Validation

`backend/venv/Scripts/python.exe -m pytest tests/test_whatsapp_cloud.py -q`
from `backend`, and `npx tsc --noEmit` from `frontend`.
