# Shared loading and operation progress

The existing `lib/async-progress.ts` external store remains the single operation registry. `AsyncProgress` is mounted once in the application root. Existing `beginProgress(label)` callers retain their nonblocking behavior. No backend schema, endpoint, or job store was added.

## Audit and integration

- Removed the timer-based route activity simulation. Suspense uses the existing shared `LoadingState` skeleton and real API activity drives the top bar.
- Reused permission-aware navigation labels for context across CRM, PMS, HRMS, Sales, Inventory, Finance, and Settings. Explicit operation titles take precedence. API URLs are never converted into user-facing titles.
- Extended the existing Button with `loading` and `loadingLabel`; skeletons accept cards, table, form, and chart variants.
- Deal Create/Edit loads configuration, custom fields, permissions, and the form layout through actual promise stages. Cancellation aborts the underlying lookup requests. The progress dialog is removed after the form commits. Details use a contextual skeleton.
- Shared import workspace tracks server validation, import confirmation, and results refresh. Shared export controls retain their existing dialog and use nonblocking feedback, avoiding a second modal.
- Attachment transfers expose byte-based progress where available; the server-confirmation interval is indeterminate. Invoice generation, report generation/export, and message sending use explicit operation titles.
- Shared Finance/Sales loading wrappers and primary employee/project views reuse the skeleton. Existing purpose-specific table skeletons remain in place.

## Usage

```tsx
const operation = progress.start({
  id: operationId("report"),
  title: "Generating Sales Report",
  mode: "modal",
  operationType: "generate",
  steps: [{id: "generate", label: "Generating report", status: "active"}],
  successTitle: "Sales Report Ready",
});
try {
  const result = await generateReport();
  operation.update({steps: [{id: "generate", label: "Generating report", status: "completed"}]});
  // Complete only after the result is ready for the user.
  operation.complete();
} catch (error) {
  operation.fail(error);
}
// In a component's cleanup: operation.dispose(). Late handle updates are ignored.
```

Use `progress: false` for silent API requests. Explicit Axios metadata is supported:

```tsx
api.post(endpoint, file, {
  progress: {
    title: "Uploading Attachment",
    operationType: "upload",
    mode: "modal",
    successTitle: "Attachment Uploaded",
  },
});
```

`progress.update(id, patch)`, `complete`, `fail`, `cancel`, `minimize`, `restore`, and `dismiss` are available. Prefer the handle returned by `start` for asynchronous work: its token prevents an old completion from affecting a replacement operation with the same ID. Concurrent modal operations share one foreground window; background operations have a compact dock and completion/error states.

## Capability and lifecycle rules

- Omit `progress` when no percentage is available. No timer advances steps or percentages.
- Transfer percentage describes measured bytes. At transfer completion, show indeterminate server confirmation rather than implying the complete operation has finished.
- `cancellable: true` requires a real `onCancel` callback. Connect it to AbortController or the server job cancellation API. Aborting an HTTP request does not roll back server writes.
- Enable `backgroundable` only when the caller owns work that continues safely after minimizing. Existing synchronous form/import endpoints deliberately do not offer this control. The registry is in-memory; surviving a browser reload requires an existing persistent server job and an integration that reconnects using its ID.
- Starting directly in background mode requires `backgroundable: true`.
- Ordinary requests and mutations use micro feedback. Cached React Query refetches and cache synchronization do not open foreground windows.
- Route changes remove route-owned foreground operations. Minimized, explicitly background-capable operations survive navigation. Identity/company changes clear old operation presentation.
- Errors retain context and can expose Retry/View Details callbacks. Never automatically retry writes whose result is uncertain.

## Validation

`npm run test:progress` runs isolated browser tests for the store/host lifecycle, module titles, concurrent operations, stale handles, cancellation, real byte events, background transitions, failure recovery, route cleanup, responsive layouts, dark mode, and reduced motion.

With Vite on port 5174, `npm run test:progress:deals` verifies the real QuickDealDialog using isolated API fixtures, including delayed fields, successful form mounting, Create/Edit titles, cancellation, and failure/retry. Override `PROGRESS_QA_ORIGIN` for another local port. These tests do not modify production records.
