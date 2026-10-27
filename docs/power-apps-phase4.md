# Power Apps Phase 4 — connector foundation (in progress)

Phase 4 is **not complete or production-ready**. This checkpoint adds server-side connector foundations. It does not expose Integration Studio routes, attach external executors to the Phase 3 worker, activate a connection, or change a native Business Suite module. No production migration or live provider call was performed.

## Existing systems reused

- Power Apps organization/environment/owner records, environment validation, permissions and central account membership checks.
- Existing SQLAlchemy models/session infrastructure; no new database or queue.
- Existing Fernet encryption primitive from the governed AI provider gateway. This derives its key from `SECRET_KEY`; deployment key rotation must include re-encryption of stored connector values before this framework is enabled.
- Existing OAuth PKCE helper, existing strict TLS SMTP delivery helper and existing governed AI gateway.
- Existing bounded workflow value validation, secret redaction and JSON-schema validation.
- Phase 3 execution/run/step identifiers for the external-operation journal. Worker integration is still outstanding.

## Implemented source

`backend/app/apps/power_apps/integrations/` contains:

- Typed versioned manifests and typed action inputs, including 15 bounded AI tasks. Ten connector manifests remain explicitly “Requires Configuration”; candidates remain “In Development” with no executable actions. Native module contracts remain inactive.
- Encrypted credential records, explicit organization/environment/owner checks, credential binding to connector and exact hosts, metadata-only audit records, write opt-in and least-privilege scope checks.
- Fixed-provider OAuth authorization-code/PKCE state, exact callback configuration, encrypted verifier, single-use expiry, fenced refresh-token rotation, and provider revocation helper. The public callback route is **not mounted**.
- Exact-host HTTPS egress policy with every DNS answer checked, private/metadata/loopback denial, explicit private-address grant records, application-host and application-address denial, pinned sockets with original-host TLS verification/SNI, bounded reads and restricted redirects. Private grants have no API yet.
- HTTP JSON/form/multipart requests, bounded read pagination, safe custom headers, signed outbound webhooks, response selection, and retry/uncertainty classification. Mutating automatic pagination is rejected.
- Structured parameterized PostgreSQL operations with schema/table allowlists, non-administrative-role checks, read-only default transactions, TLS verification, statement timeout, row bounds and rollback on excessive mutation matches. Actual PostgreSQL connector TLS/CRUD fixtures remain outstanding; the application regression database is not evidence of external-connector correctness.
- Fixed-endpoint adapters for GitHub, Google Sheets, Google Drive and Microsoft Outlook; existing authorized SMTP and AI gateway adapters. These are source implementations, **not live-verified integrations**.
- Durable external-operation intent and outcome records, scoped idempotency keys, uncertain-write reconciliation blocking, per-connection rate/bulkhead/circuit gates, and actual request-attempt records. These are tested directly, but are **not connected to workflow execution**. There is no second queue or runtime.

## Verification

The isolated foundation tests use injected transports and fixture values exclusively. They do not send fabricated credentials to real providers.

- 27 foundation checks passed with SQLite.
- Checks include manifest truthfulness, SSRF URL/IP/DNS rejection, application-host alias protection, exact private grants, actual pinned socket target and TLS SNI, redirect and header restrictions, read/write network-error classification, Retry-After, secret removal, encryption, tenant isolation, mutation opt-in, successful-operation reuse, uncertain-write redelivery prevention, OAuth state replay protection and refresh rotation/revocation fencing.
- 27 foundation checks passed against an isolated migrated PostgreSQL test database.
- Both frozen migration variants passed idempotent upgrade/downgrade and legacy-data preservation checks.
- The corrected broader PostgreSQL regression run passed **219 checks**, covering the connector foundation, both migration variants, existing Power Apps authoring/intelligence/runtime behavior, and company security boundaries.
- The final targeted run passed all **29 connector and migration checks** in SQLite and PostgreSQL after additional pre-dispatch credential/scope revalidation and refresh-race fencing.
- Python compilation and Black formatting passed for the new integration package.
- No Phase 4 browser or live-provider verification has been completed.

## Remaining work before release

1. Complete deployment review of the additive migration 036 in both migration trees; the frozen definitions and isolated upgrade/downgrade checks are now present. No developer or production database was migrated.
2. Implement explicit sharing in the central ORM scope guard using exact JSON membership. Keep owner-only credential management, sharing validation and credential-sharing metadata synchronized.
3. Add authenticated API routes for catalog, connections, credentials, testing, rotation, revocation, safe usage-aware deletion, constrained custom actions and real monitoring. Add only the exact OAuth callback public-capability exception.
4. Register canonical connector/AI nodes, validate references/scopes and effective identities at publication, and require explicit published external-write authority. Integrate the journal into the Phase 3 worker with transaction release before I/O, lease/result fencing, Retry-After scheduling, cancellation recovery and manual-retry reconciliation controls.
5. Build all requested Integration Studio screens and reusable components, including editor connection/action selection, API Explorer, Webhook Studio and Integration Monitor. Reuse existing Phase 3 webhook configuration and signing infrastructure.
6. Finish tenant-wide quotas, individual wire-request accounting for paginated calls, safe credential rotation/deletion with active-usage checks, pool invalidation, and administrative private-egress workflows.
7. Complete real isolated HTTPS/PostgreSQL/SMTP fixtures, provider/OAuth/AI fixtures, crash and concurrency tests, migration verification, permission/sharing cases, responsive browser QA and the full requested acceptance scenarios.
8. Finish deployment guidance, supported-action inventory, monitoring/export permission checks and operational reconciliation UX. No connector may be marked “Available” based only on a manifest or mock response.

## Server configuration reserved for the unfinished OAuth/database setup

- `POWER_GOOGLE_CLIENT_ID`, `POWER_GOOGLE_CLIENT_SECRET`
- `POWER_MICROSOFT_CLIENT_ID`, `POWER_MICROSOFT_CLIENT_SECRET`
- `POWER_OAUTH_REDIRECT_URI`: exactly `${BACKEND_PUBLIC_URL}/api/v1/power-apps/integrations/oauth/callback`; this route is not mounted yet.
- `POWER_CONNECTOR_PG_CA`: optional CA bundle path; the connector uses verify-full TLS.

Do not enter provider secrets in workflow JSON, public connection configuration, URLs, screenshots, logs or frontend storage. Provider application registration, consent and authorized credentials are still required. Existing automations remain on the Phase 3 runtime.

## Provider references used during implementation

- [GitHub authentication](https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api), [rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api), and [issues API](https://docs.github.com/en/rest/issues/issues).
- [Google OAuth web-server flow](https://developers.google.com/identity/protocols/oauth2/web-server), [Sheets append](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/append), and [Drive least-privilege authorization](https://developers.google.com/workspace/drive/api/guides/api-specific-auth).
- [Microsoft authorization-code flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow) and [Graph sendMail](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0). Outlook adapter acceptance does not claim delivery confirmation.
