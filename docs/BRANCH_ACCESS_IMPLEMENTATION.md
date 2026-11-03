# Branch access and centralized Settings implementation

This document records the implemented local behavior, verification evidence and remaining release gates. It is not a claim that every business workflow or production rollout is certified.

## Intended access model

A company can have multiple branches. Ordinary users can work only in their assigned branches, and module permissions still apply within each branch. Super Admin and explicitly authorized all-branch users can switch between authorized branches or select All branches. A user can have CRM administration in Chennai and SRM read-only access in Bengaluru without receiving CRM access in Bengaluru.

Company/module authorization is the ceiling. Branch membership and branch module grants narrow that ceiling. Removing company membership or module access wins over a saved branch grant. Branch write access never supplies a module permission that the company has not granted. Browser switching reloads the application and clears query caches and other local state so records from the previous branch cannot remain as the working context.

## Enforcement and ownership

The branch subsystem stores company/user policies, branch grants, accounting branch mappings, record ownership, record shares, append-only audit events and branch lifecycle/recovery metadata. Existing business tables retain their identities and relationships. The ownership register scopes legacy independent roots without adding a nullable branch column to hundreds of tables. Directly owned records, inherited child ownership and independent roots are classified explicitly; unknown historical ownership fails closed for branch-restricted users.

The current generated runtime inventory is [ownership-inventory.json](qa/branch-access/ownership-inventory.json): **782 SQLAlchemy tables**, comprising **23 direct**, **489 inherited**, **182 owned roots** and **88 shared definitions/security tables**. The new recovery metadata table is shared control-plane metadata; its administration endpoints independently check company and branch authority. This is an enforcement/model inventory, not independent business approval for every classification.

The authenticated ORM boundary applies branch ownership in addition to existing company, module and workspace guards. It checks ordinary reads, writes, relationship changes, identity-map retrieval and bulk operations. Unscoped business SQL through the guarded Session is rejected. Independent Core connections and external integration sessions still require their own audited service-path authorization; the ORM boundary does not automatically rewrite arbitrary independent SQL.

Identity discovery does not expose private employee or HR profile data. A person can be discoverable for a second branch application while their employee/home-branch profile remains private. Branch heads cannot inspect another branch's restricted roster or erase hidden grants during a replacement operation. Shared configuration/metadata reads do not automatically authorize business writes.

Company singleton definitions such as AI security settings, tenant subscription settings and CRM lead management configuration are company-shared. Their existing company/admin API permissions remain enforced. Business activity, transactions and results are not made shared merely to avoid a configuration conflict.

## Historical Main Branch migration

The user explicitly approved assigning unassigned local records to one Main Branch. **33,749 records** were assigned locally, existing branch assignments were preserved, and counts, exact financial/quantity totals and business-link fingerprints reconciled across the **697 tables classified private at that checkpoint**. Three singleton configuration tables were subsequently reclassified as company-shared, so the current private-table count is 694.

Evidence: [dry run](qa/branch-access/main-migration-dry-run.json) and [applied reconciliation](qa/branch-access/main-migration-applied.json). A local PostgreSQL backup was created first in the ignored `.tmp` directory. This historical migration must not be rerun casually or used to guess a new ownership mapping. No production database was migrated by the local QA work.

## Central Settings

Home exposes Settings before sign-in and on the authenticated application dashboard. Public visitors must authenticate and return to a validated Settings destination. The public module catalog has a single shared Sign in link; module cards do not repeat individual sign-in links.

Main Settings groups company identity, branches, users, permissions and business defaults. It also hosts the existing native editors for CRM, SRM, PMS, finance, HR setup masters, document templates, security, audit, module availability, connections, delivery, shared service defaults, API keys, webhooks and AI providers. Finance configuration includes financial years, cost centers, accounting branches, voucher types/numbering, payment modes and GST settings. CRM configuration includes pipelines, approvals, scoring, territories and automation.

Legacy configuration URLs redirect to the canonical Settings section while preserving query strings and fragments. Module top bars expose Main Settings. User management starts with a searchable listing, supports named branch filters and retains the permission matrix, custom roles, company permission ceilings and per-branch module roles. Administrator verification and native write permissions are retained.

HR document issuance remains in the module. Template and letterhead editing opens Main Settings; existing template storage and permissions are reused. Company identity and shared defaults use the same audited Company profile API. Each profile/default form submits its own visible fields. Existing project-specific and transactional workflows retain their native scope.

This consolidates editors and navigation; it does not silently merge unrelated accounting tables or migrate accounting balances/defaults. Company access branches and finance accounting branch registrations are distinct, labeled concepts. Finance statutory/book settings retain their existing financial records. No accounting defaults were rewritten by the Settings consolidation.

Central Settings discovery is server-owned and evaluates the selected branch's effective module grants. Company access administrators can manage company roles, and deployment integration credentials remain Super Admin-only. Every native API independently checks its existing authorization; moving an editor never grants extra access.

Evidence: [Main Settings access checks](qa/branch-access/main-settings-access-checks.json), [central Settings access checks](qa/branch-access/central-settings-api-checks.json), [central Settings summary](qa/branch-access/central-settings-summary.json), [Settings regression output](qa/branch-access/central-settings-tests.txt). The central consolidation checkpoint passed **45 tests**, **64 live API checks** and TypeScript checking. Chrome verified finance/CRM/security redirects, embedded editors, document letterhead deep links and catalog search.

## Branch rename, Trash and protected recovery

Under **Settings > Branches**, active branches provide Rename and Move to Trash. Trash and Protected recovery are separate tabs. Previously archived branches can also be reactivated with Restore.

Renaming changes the display name without changing branch ID, code, record ownership or user grants. Moving a branch to Trash disables it as an active workspace but leaves its customers, employees, sales, ownership rows, accounting mappings, memberships and module roles in place. Restore reactivates the same branch. Current user status, company membership and module revocations still apply; restoring a branch does not override a revoked company permission.

**Recovery is retained for at least 45 days. Delete from trash starts another complete 45-day protected recovery period.** That action moves the branch into Protected recovery instead of physically deleting it. Restore remains available in both recovery views, including after the minimum retention date. There is no automatic purge after day 45 and no permanent-delete action.

Migration `pg_20261103_062_branch_trash` adds company-scoped `suite_branch_lifecycle` metadata: deletion/protection timestamps and actors, minimum retention deadline and optimistic version. It also adds PostgreSQL triggers that block physical deletion of branch and recovery rows and reject retention shorter than 45 days. The local migration was applied after verifying the local database and saving a branch/membership snapshot in ignored `.tmp` storage. The migration deliberately refuses a destructive downgrade that could discard recovery history.

Lifecycle actions validate branch-management authority and company scope. A company row lock and transactional check prevent deletion of the last active branch. Optimistic versions reject stale administrator actions. Delegated managers retain recovery authority over their authorized inactive branches without gaining authority over other branches. Branch metadata and recovery lists do not reveal unauthorized companies or branches.

Branch discovery excludes deleted branches. The browser clears a deleted current-branch selection before reloading. Unchanged memberships in deleted branches can be preserved during unrelated access reviews, so restoration retains those original grants. Legacy company branch deletion and activation/rename endpoints use the same lifecycle service. A branch cannot be moved between companies through an ordinary update.

The branch-level retention policy does not create a new suite-wide retention policy for independently deleting individual customers, employees, invoices or other module records.

### Recovery verification

- Initial lifecycle/access/Settings regression: **70 passed**.
- Final lifecycle/module-ownership regression, including inactive membership preservation: **44 passed**.
- Live API lifecycle/access checks: **22 passed**. A synthetic customer's identity and access survived Trash, Delete from trash and Restore.
- Local PostgreSQL guards: **4 passed**, covering branch hard deletion, recovery hard deletion, short retention and the additional protected-recovery retention floor. Every probe was rolled back.
- TypeScript checking passed.
- Chrome completed Rename, Move to Trash, Delete from trash and Restore. The synthetic QA branch was left **active**. Existing real branches were not deleted.

Evidence: [recovery summary](qa/branch-access/branch-recovery-summary.json), [live API checks](qa/branch-access/branch-recovery-api-checks.json), [PostgreSQL guards](qa/branch-access/branch-recovery-postgres-guards.json), [initial tests](qa/branch-access/branch-recovery-regression-tests.txt), [final tests](qa/branch-access/branch-recovery-final-tests.txt), and [protected recovery screenshot](qa/branch-access/branch-protected-recovery.png).

## Full HTTP API access sweep checkpoint

The generated operation inventory at the earlier sweep checkpoint contained **2,730 HTTP operations**, before the additional branch lifecycle routes. All **2,678 bearer-protected operations** received live invalid-token probes across all verbs; all returned 401. The other **52 public/custom-credential operations** received safe boundary probes. Intended public reads remained public, while missing custom credentials or invalid bodies/references were rejected. These probes did not execute successful authenticated business mutations.

A restricted Chennai branch head made **1,212 GET requests** with a forged Bengaluru header: **1,211 returned 403**. The branch-context recovery endpoint intentionally returned 200, with a separate assertion confirming that only the authorized Chennai branch was returned and selected. This expected recovery behavior accounts for the one false failure in the preserved initial raw sweep.

Authenticated static/default GET sweeps covered **747 operations in each of Chennai and Bengaluru**. The initial Chennai sweep found five 409 conflicts caused by singleton configuration rows being incorrectly branch-filtered. Those rows were made explicitly company-shared and all five paths returned 200 on retest. Bengaluru returned 715 successful responses, 11 intern-only denials, 15 missing-profile/disabled-feature responses, four missing-profile responses and two requests requiring an order/engagement reference, with no 409 or server errors. Employee-linked and order-linked fixtures were used in targeted retests; absent onboarding remained an expected 404. **26 targeted retests passed**.

That checkpoint passed **124 regression tests with one PostgreSQL-only skip**, **60 tests on disposable PostgreSQL** and TypeScript checking. The skipped concurrent administrator row-lock test explicitly requires PostgreSQL and was not part of that PostgreSQL subset. Earlier focused checks also covered **89 live exposure/privilege assertions** and **21 cross-module branch-role assertions**. These are historical checkpoints, not an additive count of distinct tests.

Evidence: [operation inventory](qa/branch-access/api-operation-inventory.json), [sweep summary](qa/branch-access/api-sweep-summary.json), [raw initial sweep](qa/branch-access/api-live-sweep.json), [public boundaries](qa/branch-access/public-api-boundaries.json), [second branch reads](qa/branch-access/api-other-branch-reads.json), [targeted retests](qa/branch-access/api-findings-retests.json), and `api-sweep-*-tests.xml` in the QA directory. Raw initial failures remain preserved as evidence of issues subsequently fixed. A GET status below 500 is a server-health observation, not proof that a complete business workflow succeeded.

## Local QA environment

QA uses synthetic users, branches, customers and zero-value draft orders in the local database. The fixture accounts cover Super Admin, branch heads, branch viewers, no-branch users, all-branch viewers, mixed CRM/SRM roles and a cross-branch identity whose home HR profile remains private. Credentials are kept in ignored local `.tmp` storage and are not part of this document.

Email delivery workers/notifications were disabled for local QA. Schema changes use committed Alembic migration code; production schema must be migrated deliberately before deploying code that depends on the new recovery table. Missing branch/recovery schema fails closed.

Representative regression commands from the backend directory:

```powershell
venv/Scripts/python.exe -m pytest tests/test_branch_lifecycle.py tests/test_branch_access.py tests/test_settings_hub.py -q
venv/Scripts/python.exe -m pytest tests/test_branch_lifecycle.py tests/test_branch_module_ownership.py -q
```

Frontend verification from the frontend directory:

```powershell
npx --no-install tsc --noEmit
```

PostgreSQL test runners must target only explicitly disposable `business_suite_*_test` databases. They must never recreate or drop the local application database.

## Release gates still open

This local implementation and its tests do not certify every original suite-wide rollout item.

1. **Service-path audit:** finish end-to-end certification for public ingestion, portals, independent sessions/Core SQL, recurring workers and integration credentials. The shared ORM boundary does not automatically scope arbitrary independent connections.
2. **Business workflow certification:** exercise full lead-to-cash, purchase-to-payment, payroll, reports, imports/exports, AI actions, attachments and inter-branch workflows with production-like fixtures. Focused tests prove their stated invariants, not every table's business semantics.
3. **Accounting reconciliation:** verify historical openings, shared-ledger semantics and cross-branch accounting workflows. Profile sharing does not implement general branch record transfers or inter-branch stock/payment processing. Ordinary ownership/relationship changes remain constrained.
4. **Lifecycle and rollout coverage:** branch rename/Trash/restore are now implemented and locally verified. Mobile selection, profile-sharing UI, sustained performance checks, staged pilots and production rollout remain separate work.

Keep this in local development/staging until the outstanding release gates are resolved. Do not label the entire suite or its production migration complete solely from these checks.
