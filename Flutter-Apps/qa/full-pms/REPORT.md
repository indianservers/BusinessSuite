# Full PMS Android acceptance — incomplete

Date: 24 October 2026. Device: CPH2717 physical Android 16 phone.
Backend: https://businesssuite-rosy.vercel.app/api/v1.

This is an incomplete acceptance run. It does not claim all requested operations
work. The phone left KaryaFlow, the driver disconnected, and ADB subsequently
listed no connected device, including after a server restart. A prepared resume
attempt could not install or start the application.

## Evidence and counts

- The supplied list contains 316 items across 31 categories.
- Initial matrix: 206 checks; 192 passed, 13 failed, one blocked by a missing form fixture.
- Additional native/retry matrix: 53 checks completed before interruption;
  44 passed, eight failed and one blocked after a transient component-creation failure.
- Across both batches: 259 attempts, 236 recorded passes, 21 recorded failures,
  two recorded blockers. These include repeated setup and retries, not 259 distinct features.
- Conservative reconciliation: 115 checklist items fully device verified,
  40 partially verified; the remaining 161 have an explicit pending, missing-UI,
  deployment, permission, configuration or desktop-interaction status.
- 31 unit/widget tests pass. This includes nullable PATCH/PUT clearing,
  stale-record hydration, stable task-type defaults, file validation, array
  editing, nested schema preservation and comma-separated tags.

[All checklist items and their evidence](checklist-results.json),
[combined raw summary](summary.json), [first matrix](batch-1.json),
[second matrix console evidence](batch-2-log.json).
The first driver's overall “All tests passed” means the matrix finished;
its per-operation failures are retained and are not counted as passing here.

## Important unresolved backend permission finding

The test account reports `is_superuser=false`, role `pms_org_admin`.
A host diagnostic, separately labelled and not counted as a device pass, got:

- GET workspace-reset preview: 200 instead of the requested super-admin-only denial.
- POST reset with deliberately invalid confirmation and an invalid preview hash:
  422, showing the request reached confirmation validation rather than being
  rejected as a non-superuser.
- The workspace preview hash was unchanged before/after. No reset was executed.

The current backend guard accepts `pms_admin` permission. Flutter now restricts
the global reset/recovery controls to `is_superuser`. That client restriction
does not repair the server's authorization rule for other clients.

[Probe evidence](reset-permission-probe.json),
[prepared guard-only patch](proposed-super-admin-guard.patch),
[four isolated proposal checks](proposed-guard-validation.json).
The patch passed `git apply --check`. It has not been applied or deployed,
because the earlier instruction forbids backend edits and the scope exception
is awaiting an answer. No backend API, table or migration was changed.

## Client changes

- Added native Kanban/list views with touch drag/drop, selected-task bulk editing,
  clipboard IDs/links, task menus and task duplication.
- Added a native calendar/planner with month/week/day/agenda views, navigation,
  search/project filtering, event/task entry points and scheduling gestures.
- Edit forms fetch current records where a detail endpoint exists; saving is
  blocked when that read fails. Revisioned forms retain selected-record metadata.
- Clearing optional PATCH and PUT fields sends explicit null when supported.
- Custom-field values preserve text, numeric, boolean and nullable alternatives.
- Expanded nested schema resolution so deeply nested question conditions and
  dashboard configurations retain the actual scalar types.
- Existing array items can be edited and moved; untyped object arrays expose a
  native property editor.
- Added missing record-picker mappings, project membership IDs and readable
  project-member labels; camel-case query IDs use record selectors.
- Preserved non-null PUT defaults and explained immutable task-type names.
- Added invoice-permission checks to billing controls, comma-separated task tags,
  copyable error details, and native file-save confirmation/cancellation feedback.

The board/list, board drag, clipboard ID, bulk-selection, duplication and calendar
navigation checks passed on the phone. Later fixes after disconnection have
automated regression coverage and still require current-build device acceptance.

## Failed checks: interpretation

- Unarchive and parent-clearing failures were fixed by loading current records;
  targeted retries passed.
- Text/numeric/checkbox custom values and nullable clearing passed after fixing
  union-schema handling.
- Task-type renaming returns an intentional backend 409: names are stable
  identifiers. Mutable metadata editing passed; Flutter explains the restriction.
- Reorder tests initially chose duplicate/wrong-scope IDs. The selector harness
  was corrected and request ID assertions added. The backlog retry passed;
  the sprint/bulk-planning retry needs a valid component/sprint fixture after a
  transient component request failed.
- Recurrence configuration/clearing passed. All three next-occurrence assertions
  failed. Fresh per-frequency tasks and captured response rows are still needed;
  generation is not counted as working.
- Backlog and velocity returned 200, but the test incorrectly waited for filters
  that the page had already hidden after automatic loading. The helper is fixed;
  the corrected device retries remain queued.
- Calendar event creation returned 201; its native test incorrectly expected
  200. The assertion is fixed, with the retry queued.
- Billing/source reads returned 403 because this account lacks SRM invoice
  permissions. No real invoices, payments or outbound invoice messages were sent.
- Deleting a time log in an approved timesheet was correctly rejected. Deletion
  of a separate unsubmitted QA log passed.
- File-picker upload/download/save, complete form intake, document revision,
  dashboard lifecycle and savepoint-restore checks remain in the interrupted queue.

## Deployment and product limits

The live OpenAPI was re-read: 293 deployed PMS operations, matching the deployed
subset of the supplied guide; 19 guide operations remain undeployed. Newer local
notes/dashboard lifecycle routes are not assumed deployed. Missing native AI
operator, audit, advanced dashboard, theme/navigation and calendar-preference
interactions are listed explicitly in the checklist, not counted as generic API
page successes. Desktop hover/double-click/browser tabs need touch equivalents.
No Google/Outlook/Zoom integration or unavailable advanced widget was claimed
to work. Financial and global reset execution require appropriate isolated
accounts/fixtures; a global reset was never attempted with valid confirmation.

## Resume and cleanup

Tests and fixtures are retained under `integration_test/full_pms_*` and
`scripts/build_full_*`. The resume plan has 34 cases using a fresh QA workspace,
with the corrected 201 and auto-loaded-filter handling. Private test configuration
stays under ignored `.dart_tool`; it is not part of the normal APK.

```powershell
./scripts/android_qa_picker.ps1 -Minutes 25
# In a separate terminal, with the unlocked phone left on KaryaFlow:
./scripts/flutter.ps1 drive -d Q8G6ZLF6NR69Q85D --keep-app-running --driver=test_driver/full_pms_device_test.dart --target=integration_test/full_pms_resume_test.dart --dart-define-from-file=.dart_tool/full-resume-device.json
```

The native helper touches only Android DocumentsUI and the generated QA fixture.
It also saves valid device checkpoints to the host. `--keep-app-running` prevents
the driver's default uninstall cleanup from destroying those checkpoints.

QA workspaces 20 and 21 and their clearly labelled records remain available.
No existing business record was intentionally edited. The original USB
stay-awake setting was 0; it was temporarily set to USB stay-awake for testing.
Restoration is pending because the phone is disconnected. Restore with
`scripts/restore_android_qa_settings.ps1` after reconnection and testing.

The normal ARM64 debug build is `build/releases/KaryaFlow-PMS-0.2.1-arm64.apk`.
It still needs installation/current-build acceptance after reconnection.

## Latest build validation

The ordinary `lib/main.dart` ARM64 debug APK for 0.2.1+3 built successfully.
Flutter analysis reports no issues. The kernel was checked to exclude the QA
password, QA define name and integration-test entry points. Integrity and size
are recorded in [apk-verification.json](apk-verification.json). This latest APK
has not been installed because ADB still reports no connected device.
