# Desktop-like navigation: architecture and verification

## Audit

The suite already uses React 18, React Router, lazy route modules, Zustand, React Query, and the existing RecordCacheManager. Ordinary navigation links largely use the SPA router; a wholesale router/framework migration would add risk without addressing the actual problems.

The audit identified these concrete bottlenecks:

- A route-sensitive ProtectedRoute surrounded AppLayout. Membership checks or denied destinations could replace the entire shell instead of just the content pane.
- The form-defaults gate surrounded the shell, so loading or failing to load defaults could remove common navigation.
- The outer Suspense boundary was the final fallback for some specialized/private routes. Content needed its own boundary inside the shell.
- Company branding was fetched and root theme variables restored/reapplied on every pathname change.
- Dashboard and application startup used separate permission reads, without sharing an in-flight query.
- Lazy route imports had no intent preload interface.
- Some list preferences existed already, but scroll positions and several CRM/employee-list view settings were lost on navigation.
- A chunk-loading error automatically reloaded the document, including on a transient connection failure.

## Implementation

### Shell and authorization

AppLayout remains mounted across compatible private routes. Authentication still protects the parent layout; destination permissions and membership checks protect the content route. Denied records are never rendered while membership is pending. The defaults gate and Suspense fallback now live inside the content area. Unknown private destinations have an in-pane not-found state.

Content errors reset when navigating to another destination. A retryable lazy-route wrapper shares one import promise between hover and rendering; loaded code renders directly on subsequent visits. Failed imports remain rejected until the user explicitly retries, preventing an import retry loop. The boundary also offers an explicit application reload for a deployment whose old chunk files no longer exist.

### Prefetching

Route code preloads on keyboard focus or sustained pointer intent. It does not mount destination pages or prefetch business records. React Router ranks matching route patterns before selecting the importer, so hovering a static page does not also preload an overlapping record-detail route.

The scheduler allows at most two concurrent route preloads and four starts per minute across navigation, caps its completed-route bookkeeping at 200 entries, cancels queued work after intent ends/navigation, and skips Save-Data, 2G, hidden tabs, and low-memory devices. An import already in flight cannot be aborted by JavaScript; no claim of cancelling those downloads is made. External links, downloads, new tabs, and modifier-key/native navigation remain unchanged.

### Existing cache, not another data store

RecordCacheManager still owns approved collection data, request deduplication, server-approved disk persistence, deltas/ETags, bounded eviction, mutation invalidation, and authorization revocation. Its original user/session/company/branch/grant scope remains in force. Sensitive/no-store responses are not newly made persistent.

Revalidation thresholds now distinguish rapidly changing records (15 seconds for supported transaction/leave/attendance collections), work/sales records (30 seconds), and the existing 45-second default. These thresholds apply on reads and existing background synchronization; no extra polling loop or endpoint was introduced. Unconfirmed cached reads are never used as write confirmation. Background synchronization preserves visible rows and provides unobtrusive freshness/unavailability feedback.

Branding uses a user/company-scoped React Query entry with explicit branding-change invalidation and no pathname dependency. Access reads share a query only while in flight: permission staleTime remains zero. Hidden tabs no longer make the periodic application access request.

### View state

The content viewport retains URL presentation parameters and scroll positions for up to 40 route views in memory. It excludes action, invitation, credential, and creation-intent parameters from replay. Forms retain their existing draft and navigation guards; this layer does not save or replay form contents.

The same bounded registry retains CRM Deals filters/search/view/page and employee list page/sort settings. Existing project preferences, grid column settings, HR session preferences, and draft handling remain in use. No inactive page trees are kept mounted just to retain their state. Identity/company/permission changes clear or rescope view metadata; stale callbacks cannot write into a different scope.

## Measured results

These are reproducible isolated browser fixtures, not production or real-user latency claims:

- The actual branding hook navigated six pages: the previous implementation made six branding requests; the updated implementation made one. A company change made a separate correctly scoped request.
- The existing real cache integration fixture measured eight simultaneous collection reads as one transport request. A repeated view made zero transport requests. The run logged an approximately 34 ms initial read and 0.5 ms memory repeat; the exact timings vary by run.
- The route fixture observed one shell mount and no document recreation through cross-module navigation and Back/Forward. Both controlled before/after variants kept their header visible in this particular fixture; no remount reduction is claimed from it.
- Intent-prefetched route content was visible roughly 50–80 ms after the automated click in local runs. This includes browser automation overhead and is not a service-level target or a cold-data measurement.

Fresh output files are written to `outputs/navigation-branding-results.json` and `outputs/navigation-shell-results.json`. Cache tests print their timings and network counts.

## Verification

Run `npm run test:navigation-performance` in frontend. The browser tests exercise the real shared implementations with isolated records/import/permission fixtures:

- Delayed route loading with persistent header/sidebar and retained collapse state.
- Code-only hover/focus prefetch, Save-Data opt-out, and cached import reuse.
- Local view, URL filter, vertical scroll, Back/Forward, direct refresh, and scoped/bounded memory retention.
- Chunk failure and explicit retry while retaining the document and header.
- The actual route guard during delayed membership checks, denial, allowed navigation, and logout.
- Actual branding hook before/after and concurrent access read deduplication without a permission freshness TTL.
- Existing cache tests for company/user/permission changes, cross-tab locking, logout races, no-store/secrets, offline/reconnect, optimistic rollback, stale deltas, eviction, storage errors, and unchanged-row reference preservation.
- Existing background-refresh tests for retained DOM/drafts and failed refresh recovery.

## Deliberate boundaries and remaining measurement work

The launcher, central Settings page, dedicated PMS board/task workspaces, POS, Power Apps, public portals, and legacy inventory integrations have specialized shells. Their business layouts were not replaced. Crossings into those shells may replace their own chrome; persistence is guaranteed only within the compatible private AppLayout shell.

Company/branch switching retains its existing document reload because it currently destroys local record state, in-flight requests, sockets, and non-query caches as a security boundary. This change does not claim seamless company/branch switching. Replacing that boundary requires a separately verified reset of every module's state.

Large lists retain their existing pagination/grid infrastructure and cache page bounds; this change does not claim a new virtualized renderer for every page. Financial and permission-sensitive endpoints were not blindly cached. Production click-to-usable time, transferred bytes, cumulative layout shift, long tasks, and heap usage across every business workflow still require representative authenticated traffic and production profiling; local fixture values are not a substitute for those measurements.
