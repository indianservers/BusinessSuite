# Indian Servers platform owner

The local portal now mounts a separate React application under `/platform/*`.
Its overview, signup, customer, billing, team, tasks, communications, reports,
operations, audit, settings and profile pages do not render the client app shell.
See [the 60-feature implementation map](platform-owner-feature-map.md) for the
practical product scope requested by the user. VPN restrictions, mandatory MFA,
passkeys and client impersonation are excluded.

The platform owner signs in at `/platform/login`; customers use `/login`.
These are different account stores, JWT signing keys, audiences and API clients.
`users.is_superuser` in the business database does not authorize public signup
review. Only an active `platform_admins` identity can read or review requests.

`PLATFORM_DATABASE_URL` must name a separate PostgreSQL database.
`PLATFORM_SECRET_KEY` must contain at least 32 characters. Missing configuration
fails closed with HTTP 503; there is no fallback to customer storage.

Platform database tables: `platform_admins`, `platform_signup_requests`,
`platform_approval_history` and independent rate-limit counters. Customer IDs
in the signup queue are external references rather than cross-database keys.
The existing `suite_signup_requests` table is retired and remains empty.

Run `venv/Scripts/python scripts/setup_local_platform_owner.py` from `backend`
for first-time local provisioning. The script uses the existing privileged local
connection to create `indian_servers_platform`, copies and verifies the old
queue, then removes its old rows. It creates two separate runtime login roles
without superuser, database-creation or role-creation privileges. Neither runtime
role can connect to the other database. It writes local connection settings into
the ignored `.env`, and disables automatic customer schema migrations because
the runtime account cannot own or alter schema objects. Keep the existing
privileged database account for operator-run migrations. New business tables
inherit grants to the business runtime account through default privileges.

Platform migrations: `venv/Scripts/python -m alembic -c alembic_platform.ini upgrade head`.
Customer migrations remain under the existing `alembic.ini` and must be run using
a privileged migration connection (set `DATABASE_URL` for that process only).
Platform migrations are explicit; HTTP requests never create schema objects.

Local owner bootstrap: `owner@indianservers.com` uses the existing local bootstrap
password hash. It is an independent identity; changing either account later does
not change the other. Owner tokens expire in eight hours with a configurable
idle timeout; disabling the owner or
incrementing `platform_admins.token_version` revokes its existing tokens.

Approval locks the platform request and creates the customer workspace,
company-scoped administrator, invitation and a provisioning receipt in a single
customer transaction. The platform status and approval history commit second.
If that second commit fails, retry approval: the receipt recovers the already
created workspace without creating another. Rejecting a request with an existing
provisioning receipt is blocked. A recovered approval relies on the queued
invitation email rather than persisting an activation token in its receipt.

Public signup submissions grant no login access. Company admins cannot list,
approve or reject the platform signup queue, even if their role label contains
“Super Admin”. The platform portal has its own session storage and sign-out.

Validation: `venv/Scripts/python -m pytest tests/test_public_signup.py -q` uses
two independent SQLite test stores. Local verification also checks actual
PostgreSQL connections and denies cross-database access in both directions.
