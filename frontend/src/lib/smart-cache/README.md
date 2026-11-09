# Shared browser record cache

PMS, CRM, Sales and HRMS use the shared Axios adapter installed in `main.tsx` by `installRecordCache`. Eligible collections render from memory or IndexedDB and reconcile in the background. Pages, filters, selections and navigation are retained. No database migration or parallel CRUD API is introduced.

## Repository audit

All four applications use `services/api.ts`. Most HRMS and Sales grids and the shared enterprise data grid use TanStack Query. CRM also has state-based workbenches and `useCrmRecords`; the PMS project overview uses a Zustand store. The integration tracks query dependencies and supplies `useRecordView` for those state-based collections. The shared catalog previously checked every two seconds; it now checks every 45 seconds and responds to catalog synchronization events. Existing PMS WebSocket/database-feed events and Sales cross-tab events trigger reconciliation.

Existing model timestamps do not describe hard deletions or records leaving permission scopes. An authorized page snapshot is therefore used as the change-tracking equivalent. This preserves current view state without assuming every model has a reliable version or deletion log.

## Protocol and authorization

`X-Suite-Sync: 1` negotiates the protocol on existing, explicitly allowed GET collection endpoints. The original endpoint executes on every network check, including authentication, session revocation, module access, tenant, branch, row-scope and field masking. Its current authorized result is compared with a bounded previous snapshot. There is no cached authorization decision.

The first response retains the original body and supplies an opaque cursor, ETag, cache policy and effective authorization fingerprint. Later responses return HTTP 304 when the representation matches, or a delta containing changed records, removals, deterministic current order and view metadata. The adapter reconstructs the original response shape before application code sees it. Records leaving a filter, page or permission scope disappear from that view; an entry moving out of a filtered page is not treated as a global deletion.

Snapshots store record hashes and identifiers in bounded server memory: 256 views per worker, 500 rows per view, a 2 MiB response limit, and 15 minute cursor retention. Missing, expired, evicted or wrong-scope cursors produce a full current page when its data changed. Unchanged representations still receive 304 after a worker restart. No transient event history is promised: the synchronization contract is the latest authorized view state.

This approach reduces downloaded JSON and repeated foreground requests. The existing authorized database query and serialization still run for each check. It does not claim a database query-count reduction or a durable global change feed. A future transactional outbox can replace snapshot comparison behind the same browser integration.

## Browser storage and isolation

The browser namespace includes schema version, authenticated user, session ID, organization, branch, role and access grants. The server fingerprint additionally includes freshly resolved permissions, policy version and allowed/writable branches. Logout, identity changes, tenant/branch changes, a changed authorization fingerprint, and HTTP 401/403 clear affected local storage and visible data. Responses completing after a context change are rejected. Access-denied responses do not trigger automatic refetch loops.

IndexedDB stores normalized rows and ordered view references. Projection keys separate endpoint representations, field sets, authorization fingerprints and catalog source contexts so a broader endpoint cannot populate a more restricted representation. Identical views share their stored data, while related entity families share invalidation across modules. Product/service IDs and task/user assignment IDs use composite identities where required. Reconstructed views whose normalized rows changed underneath their cursor request a new baseline.

Persistence is bounded to 100 recently used views, 20 MiB of logical payloads and a 24 hour maximum snapshot age. Eviction removes orphan rows. Only requested pages are stored; the service never walks every page to prefetch an entire table. Oversized or unidentified collections use their existing API path. Storage denial, quota errors or unavailable Web Locks/BroadcastChannel degrade to memory/network behavior. IndexedDB schema version 1 is isolated under `suite-record-cache-v1`; incompatible storage formats must increment the version/namespace and discard incompatible snapshots.

Business collections such as projects, tasks, CRM relationships, safe employee directory projections, departments, teams, intern batches/assignments and shared catalog pages can persist when the server explicitly permits it. Sales orders, quotations, customer financial summaries, attendance and leave views are memory-only. Payroll, identity/document detail APIs, credentials, signed private file links, exports and unknown endpoints remain excluded. Sensitive-field detection is a second safeguard; it can conservatively exclude an otherwise eligible view. Backend `no-store` always wins.

Offline reads use previously authorized, unexpired snapshots. Permission changes cannot be learned while disconnected; they are enforced on the next successful authorization check. Existing access discovery also runs every 45 seconds. No financial, payroll, approval or other mutation is queued offline.

The service worker uses Cache Storage only for the application shell and bounded immutable assets. Authenticated API requests bypass it. Cache eviction is limited to this application's shell cache names.

Employee portrait downloads (JPG/PNG in the `photos` storage directory) use the browser HTTP cache with `private, no-cache, must-revalidate`. Every reuse still validates the signed token, session and current permissions before ETag comparison; unchanged files return 304 without retransferring photo bytes. This only helps repeat requests for the same signed URL. Renewed URLs require a new download. Other private files retain `no-store`; portraits are not added to the service worker or IndexedDB. Shared avatars decode asynchronously and reserve their display dimensions.

## Synchronization and mutations

Visible active views check approximately every 45 seconds with jitter. Hidden tabs suspend these checks. Focus and reconnect resume them; failures back off up to five minutes. Per-view promises deduplicate concurrent callers, Web Locks serialize tabs, and a second IndexedDB read inside the lock avoids repeating another tab's successful synchronization. BroadcastChannel carries scoped invalidation notices, not record payloads. Memory-only views cannot reuse another tab's persisted response.

TanStack Query dependencies are discovered from cached result provenance. Nested combined results are supported. ID-based structural sharing retains unchanged row references when sorting or insertion moves their array positions. The existing shared data grid retains its row/column virtualization and server pagination. A 10,000-row structural-sharing fixture verifies that 9,999 unchanged row references survive a single-row update; these fixture rows are not automatically persisted.

State-based grids subscribe to the exact URL/filter combination through `useRecordView` and receive the current view directly.

Confirmed mutations mark related cached entities stale across modules and reconcile from the server. Safe lead contact edits can apply optimistically only with the lead's existing server-enforced version and unchanged workflow details. Failure rolls back the optimistic view; version conflicts propagate to the existing error UI. Stage changes, approvals, bulk operations and financial mutations wait for server confirmation.

## Developer diagnostics and integration

The development-only Cache and Sync panel shows memory/IndexedDB payload usage, hits/misses, hit rate, served cached requests, network checks, changed rows, pending checks, last synchronization and generic errors. It includes refresh and module-clear actions and never displays cached record contents. Usage is logical payload size, not a measurement of the browser's storage-engine overhead.

New collections require matching allowlist entries in `model.ts` and `record_sync.py`, bounded pagination and stable IDs. Existing Query-based views need no separate store. State-based views should call `useRecordView` with the same URL and parameters as their read API. Explicit refreshes can use `recordCache: false`. `getCachedRecord`, `applyChangedRecords`, `invalidateCache`, `syncModuleChanges`, `clearUserCache` and `getSyncStatus` provide the shared integration surface; IndexedDB collection reads/writes live in `storage.ts`.

## Validation and fixture measurements

Run `npm run test:record-cache:assets` for the service-worker cache policy and storage-failure tests. Run `npm run test:record-cache` from `frontend` for the real Chromium/IndexedDB/Web Locks tests. Run `python -m pytest tests/test_record_sync.py tests/test_record_sync_integration.py -q` from `backend` for the protocol and actual authentication stack. TypeScript validation uses `node node_modules/typescript/bin/tsc --noEmit` from `frontend`.

The 100-row server fixture transfers 16,603 bytes for a full JSON body, 0 response-body bytes for an unchanged 304, and 752 bytes for one changed row: a 95.5% reduction in uncompressed JSON body bytes for that update. This excludes headers and gzip and is not a production bandwidth measurement. Chromium verifies that eight concurrent reads make one request, an immediate repeat view makes zero requests, and a second tab reuses IndexedDB. Local fixture timings are printed by the test rather than treated as production page-load improvements.

Production latency, compressed bandwidth and total API request reductions require measurement with real user workflows and deployment traffic. The 70–90% target is an aspiration rather than an asserted result.

Reference behavior follows [TanStack Query structural sharing](https://tanstack.com/query/latest/docs/framework/react/guides/important-defaults), [IndexedDB](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API), and [Web Locks](https://developer.mozilla.org/en-US/docs/Web/API/Web_Locks_API).

The 20 new backend tests pass, including the actual employee authorization stack, role fingerprint changes, signed-file exclusion and a real stale-version lead edit returning HTTP 409. The browser and service-worker suites also pass. Broader existing CRM lead-management and shared-catalog regressions encounter missing organization or destination-branch setup in their fixtures; representative failures are reproducible with record synchronization disabled. Those suites are not reported as green.
