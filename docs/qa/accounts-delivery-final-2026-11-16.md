# Accounts Company delivery — final coherent verification

Status: all six core Accounts workflows delivered and verified. The complete run plus its bounded fixture repair rerun cover **179 distinct native cases passed**, including **all 11 concurrency cases**. The single remaining skip is an explicitly SQLite-only compatibility simulation. No unresolved failed case remains.

## Source and isolation

The original work used in-progress snapshot `cc30e193620769611aa11d8cac699fc61aa852ad`, with the prior Accounts handoff at `e68713f1`. The final candidate is assembled in the separate managed `codex/accounts-final-coherent` checkout, seeded from integrator-approved current base `49e0375bdfa70c95453c1dc39f16b6dc17d921cd` plus the reviewed in-progress Accounts backend, global storage extension and latest retry proofs. Main alone did not contain these changes.

Frozen application implementation: `152d90d59`; final test-fixture revision: `3e56b7ab9`. Between them, only two test strings changed. The current-base 119 schema, Warehouse behavior, checkout probes and additive request rules are preserved. No original checkout write, deployment, unfinished-pack activation or main push was performed from this workstream. Snapshot ancestry must not be merged into main.

## Delivered workflows

- Canonical CRM client and SRM engagement selection/creation, with no shadow company or engagement master. Existing native client/project visibility and explicit company/branch/pack ownership are required. A preparer assignment cannot grant source access. Project selection checks both existing commercial/customer links and effective native currency before an immutable link can be created.
- Explicit recurring periods and due dates with month-end anchoring, deterministic child commands and atomic collision rollback.
- Document requests, immutable checklist/link revisions, canonical PMS task/file uploads and authenticated downloads. Routed cloud, native S3 and private Blob return verified immediate bytes without generic reusable blob capabilities. Size, checksum, ownership, native export rights, source/configuration and post-fetch authorization are checked; response plans and streams are cleaned up on failure. Existing local/public PMS behavior is preserved.
- Assigned preparer work/submission and independent reviewer approve/return. Self-review, stale revisions and duplicate conflicting submissions are denied; legitimate exact retries remain idempotent.
- Explicit actual time through the native PMS operation, creating a canonical pending time log without a timesheet. Planned service time is not treated as actual work.
- Independently approved work uses canonical service invoice issue, outstanding balances, partial/final collections and existing receipts/ledgers. Immutable birth/source certificates prevent adopting an unrelated invoice. Native bounded writer-busy behavior is tested through actual PostgreSQL locks and identical-key retries.

The frontend patch uses existing cards, grid, dialog, buttons, inputs and selectors. No menu, CSS, color or shared layout file changed. Company creation and Company-master authorization remain in the separately owned integration workstream.

## Separate review commits

- `a32e36297`: Accounts pack-local implementation on current integrator source.
- `d21c9a285`: functional, storage, browser and PostgreSQL concurrency tests.
- `a35ffd2c6`: reviewed exact shared capability/source hooks.
- `ec0098c9e`: native task-upload operation extraction; default public behavior unchanged.
- `152d90d59`: **frontend wiring only**, two Accounts page files.
- `3e56b7ab9`: test-fixture-only role prefixes kept below the existing native 50-character limit; full UUID uniqueness, permissions and assertions retained.

Shared source changes are limited to the native PMS task-upload wrapper, `business_packs/boundary.py`, `financial_projections.py`, `industry_billing_guard.py` and exact Accounts `request_operations.py` entries. Each was coordinated with the integrator. No Company-master adapter, Payroll/Home, generic authorization implementation, generic blob endpoint or shared accounting helper was modified.

## Verified results and provenance

- Complete coherent PostgreSQL run on `152d90d59`: **177 passed, 2 failed, 1 skipped, 62 warnings, 1567.68s**. All **11 genuine independent-session concurrency cases passed**, including actual native busy/same-key retry, invoice creation, submissions, recurrence, competing collections and writer-wait revocation. Both failures occurred at fixture insertion because two generated role names exceeded native `VARCHAR(50)`; business endpoints had not been reached. The one skip is the explicitly SQLite-only older-schema compatibility simulation; native schema 119/history retention passed. The immutable first complete result is preserved in `.local/accounts-coherent-postgres-first-complete.log` and `.xml`.
- Bounded native selector rerun on `3e56b7ab9`: **10 passed, 3 warnings, 88.25s, exit 0**. The two fixture failures are resolved; all permissions/ownership assertions stayed intact. Evidence: `.local/accounts-coherent-selectors-postgres-final.log` and `.xml`. A union of actual JUnit case identities confirms **179 unique native passes**, not 187; no failed case identity remains unresolved. Machine-readable proof: `.local/accounts-native-result.json`.
- Current coherent `152d90d59`: frontend `tsc --noEmit --pretty false` **exit 0**; compatibility preflight **22 passed, 2 warnings, 179.63s, exit 0**. Evidence: `.local/accounts-coherent-typecheck.log`, `.local/accounts-coherent-preflight.log` and `.xml`.
- Global storage donor `b0484ddf`: **75 passed, 2 warnings, 603.29s**, covering global/routed cloud/local documents, binary uploads and native public upload compatibility. All Accounts package text matches the final candidate. This is donor-specific evidence, not a substitute for the coherent native gate.
- Earlier combined `35f6ed5d`: **57 passed, 2 warnings, 493.40s**. Currency guard `e9971793`: **10 passed, 2 warnings, 83.63s**. Earlier `8c7aad92`: two disjoint functional cohorts **80 passed, 6 warnings, 546.55s** and **34 passed, 2 warnings, 151.29s**. Overlapping runs are not added into an inflated total.
- Real API browser on the unchanged two-file frontend: **1 passed, 3 warnings, 145.68s**. Four roles, 151 real API calls, 1440px/390px, real uploaded/downloaded byte equality, lost committed time response followed by one-log retry, independent return/correction/approval at revision 2, invoice issue, two receipts and outstanding `0.00`. Canonical master counts stayed unchanged. Seven viewport checks passed; desktop/mobile screenshots were visually inspected. Evidence: `.local/accounts-history/accounts-delivery-browser/` and matching browser log/XML.
- Actual native busy proof `b4748264` with application source `35f6ed5d`: **1 passed, 8 warnings, 48.33s**. Engine-observed `55P03` on `pg_advisory_xact_lock` after the unchanged five-second native deadline; `503`/`Retry-After: 5`; zero visible payment rows before owner commit; known owner `201`; identical URI/body/UUID/auth retry `201`; exactly one receipt, allocation, receipt context, cash revenue event and payment audit afterward, with paid `500.00` and balance `1000.00`.

Historical logs/XML are preserved under `.local/accounts-history/`. Warnings are existing Starlette, ReportLab, Pydantic and native datetime deprecations. Assertions and native timeouts were not weakened or increased.

## Failure evidence retained

The first source-bound native attempt on `35f6ed5d` stopped at **50 passed, 1 failed, 37 warnings, 731.26s**: the exact parallel collection returned `503`/`201`. Its original SQLSTATE was not captured, so the specific cause is **not retrospectively claimed proven**. An unchanged strict diagnostic then passed **1 test, 8 warnings, 57.98s**; a further strict run also returned two `201`s with a 4.172-second measured writer wait and all canonical counts equal to one.

The first deliberately held-writer test exposed a test-harness response/audit wait cycle: **1 passed, 1 failed, 13 warnings, 90.65s**. It captured the actual native `55P03` deadline but kept the owner paused until HTTP error completion. The harness now snapshots committed state and releases the owner at the actual database error; all assertions and deadlines remain unchanged. The corrected positive proof above passed.

Only after that proof did the integrator approve the exact-race end-to-end contract: immediate two-`201` behavior is retained; an alternate path requires the engine-observed native lock timeout, native retry header and known committed winner, then the exact same command is retried after the advised time inside the existing 20-second total budget. Unknown failures still fail, and canonical counts cannot increase.

## Release limits

The role-name fixture repair changes only two test strings in `3e56b7ab9`. The application is unchanged from `152d90d59`. The bounded native rerun of all ten selector cases passed in the integrator's assigned slot. No schema, native permissions, assertion or timeout was changed. Both native runs used private guarded provisioning, random owned loopback test databases, independent request sessions and successful cleanup. The native slot has been released.

Provider tests execute native clients/storage operations with controlled SDK/network boundaries; live credentials, provider outages/recovery and production accounting were not validated. Deployment and release remain integrator-owned. No production-ready claim is inferred from controlled provider tests.

The final handoff manifest lists every changed file and hash, source base, exact evidence and separate backend/shared/native/frontend patches.
