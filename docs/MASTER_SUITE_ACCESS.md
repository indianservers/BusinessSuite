# Master Suite: Users & Access

The subsequent [Phase 1 control-center report](MASTER_SUITE_PHASE1.md) documents the dashboard, organization hierarchy, company entitlements, security center, audit consolidation and latest rollout requirements.

The existing Business Suite shell now includes `/admin/access` for global Super Admins and explicitly delegated organization administrators. The compact user × module matrix uses the live backend catalog; screenshot examples are not seeded production users or counts. Account activation uses `/invite-access` and the existing password-reset mechanism.

## Discovery

The registry and router inventory discovers 18 access groups: HRMS, CRM, Project Management, SRM, Finance (FAM), Interns Hub, Forms, Scheduling, Approvals, Audit, Automation, Customization, Communication, Analytics, AI, Security, SaaS, and Business OS. Five are registered product modules; the others are shared functional groups. Sales, quotes, tasks, inventory and invoicing remain within their existing applications rather than becoming duplicate applications.

The generated [discovery inventory](qa/suite-access/discovery.json), refreshed after Phase 1, records 2,210 HTTP route definitions, 204 seeded permission names and 35 seeded role definitions. Discovery is an integration inventory, not proof that every route has an independently exercised security test.

## Architecture and behavior

`backend/app/access/` extends existing User, Role, Permission, UserSession and organization identity records. It does not create another login system. Per-company policies hold independent module grants, native permission names, allowed actions, role references and record scopes. Accounts without a central policy preserve existing authorization. Once managed, server-side effective permissions replace legacy role permissions for business authorization; the original role record is never mutated.

The console provides searchable, paginated users; a virtualized sticky matrix; individual access drawers; module-specific preset/custom roles; granular native permissions and actions; own, assigned, team, department, branch and organization scopes; invitation setup; membership management; reusable templates; audit history; insights; and authorized CSV reporting. Existing recognized module roles remain usable in module navigation.

Edits are staged with a required reason, reviewed against server-generated diffs, and applied after password reauthentication. Bulk requests support atomic or per-user results. Optimistic policy and custom-role versions reject stale updates. The console can refresh current versions while retaining proposed edits for another review. Custom-role updates require acknowledgment of the currently affected users. Superuser accounts are protected from mutation through these APIs, preserving the last global administrator.

Policies invalidate active sessions on changes. Requests reread policy state; background AI/operator tasks recheck current grants and restore their organization context when finished. Managed signed file links carry policy/session context and stop working after revocation. Organization selection is validated against server-side membership rather than trusted from the browser header. Delegated administrators cannot grant powers beyond their own ceiling.

Request-scoped ORM filtering narrows supported tenant and record ownership relationships, including CRM ownership/teams and PMS membership/assignments. Identity-map lookups and refreshes are checked as well. Existing business membership checks continue to apply. Audit changes record actor, target, tenant, session, before/after values and reason; database triggers and ORM guards prevent audit update/delete.

## Database rollout

New tables: `suite_access_memberships`, `suite_access_policies`, `suite_access_roles`, `suite_access_templates`, and `suite_access_audit`.

Migrations:

- PostgreSQL: `backend/alembic_postgresql/versions/pg_20261026_023_suite_access.py`.
- SQLite migration tree: `backend/alembic/versions/20261026_023_suite_access.py`.

No development or production database was migrated by this implementation. Back up and migrate the intended environment before using administration. With the existing PostgreSQL configuration, run from `backend`:

```powershell
venv/Scripts/python.exe -m alembic upgrade head
```

The existing `backend/alembic.ini` selects the PostgreSQL migration tree. Confirm environment database settings before executing. Until the access schema exists, legacy authentication continues and access administration returns a migration-required 503.

## Extension contract

Register a product's models/router through `APP_MODULES`, retain its real Permission definitions and permission dependencies, and supply navigation metadata for nonstandard paths. New registered modules appear in the catalog. Models with unconventional ownership, polymorphic parents, raw SQL, or global configuration need an explicit tenant/scope adapter and behavioral authorization tests. Registration alone cannot safely infer those semantics.

## Validation and limits

Evidence is saved under [qa/suite-access](qa/suite-access/). PostgreSQL tests cover persistence, direct API denial, six CRM record scopes, tenant membership, delegated-admin ceilings, custom roles/templates, bulk rollback/partial results, session and signed-link revocation, invitation activation, protected superusers, database audit immutability, assigned PMS records, background authorization and real concurrent administrators. Playwright exercises eight matrix/drawer/bulk/role/invitation/mobile/report scenarios with mocked API data; backend integration tests exercise real authorization separately. The production frontend build checks TypeScript and bundles the application.

Final verification: 133 PostgreSQL integration/regression tests passed (`release-regressions.log`), including the access suite; the focused access/employee-scope run passed 27 tests (`release-postgres.log`). All eight browser tests passed (`release-browser.log`), and `npm run build:lowmem` passed (`release-build.log`). Backend runs report existing deprecation warnings. `git diff --check` found no whitespace errors. Desktop, mobile and drawer screenshots are included in the evidence folder.

Remaining integration limits:

- Invitation delivery currently produces a secure setup link for manual delivery; it does not claim to have emailed recipients.
- Legacy raw SQL and configuration without tenant ownership fail closed for centrally scoped users until explicit adapters exist. Some shared HRMS employee records still require an HRMS grant in addition to Interns Hub permissions; independent intern administration needs a dedicated employee-partition adapter.
- Preexisting unsigned-context file links retain their existing expiry behavior; newly generated managed links support policy/session revocation.
- External customer-portal identities retain their separate authentication flow. This console manages corporate User accounts.
- Administrative step-up currently uses the existing password verifier. SSO-only accounts need an appropriate identity-provider reauthentication adapter.
- Coverage targets critical paths; it is not an exhaustive independent security audit of every legacy endpoint.
