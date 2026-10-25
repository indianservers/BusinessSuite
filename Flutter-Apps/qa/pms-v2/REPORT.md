# PMS Flutter 0.2 — physical Android acceptance

Date: 24 October 2026. Device: CPH2717, Android 16, connected by USB.
Backend: https://businesssuite-rosy.vercel.app/api/v1.

All implementation and evidence are under Flutter-Apps. No backend API,
database table, migration or web source was changed for this work.

## Results

- 43 of 43 new device workflows passed against the real deployed API.
- Tests used native Flutter controls, real authentication, record selection,
  confirmation dialogs, network responses and persisted server data.
- Validation completed in three batches: operations 1–20, 21–42 and 43.
  The first tag attempt exposed duplicate optional query/body fields; the
  Flutter form now presents the body field once. The first thread attempt
  stalled opening the long-press menu; a visible message-actions button was
  added and the thread reply was retried successfully on the phone.
- 20 unit/widget tests passed, including permission controls, session handling,
  contract validation, mutation confirmation and duplicate tag-field regression.
- Flutter analysis reports no issues. Android ARM64 debug APK build succeeds.
- The ordinary main.dart APK was checked to exclude the QA password, QA define
  name and integration-test entry point. Only the API URL is supplied to its build.

Machine-readable consolidated results: [report.json](report.json).
Original batch evidence: [part-1.json](part-1.json), [part-2.json](part-2.json),
[part-3.json](part-3.json). Original failed attempts remain in those batch files;
the consolidated report records the successfully retried result per operation.
APK integrity: [apk-verification.json](apk-verification.json).

## Verified phone flows

Epic create/list/edit; component create/list; release create/list/readiness;
milestone create/list; sprint create with date pickers/list; risk create/list;
task comment create/list; checklist create/list; subtask create/list; task tag
create/list; time log create/list; saved project filter create/list; team
create/list; document create/list; board data; project dashboard; task distribution;
resource workload; workspace activity; notifications; trash; native timer start
and stop with a saved log; private channel creation; chat send/edit/thread reply.

The QA workspace is `PMS Features QA 1024214529` (ID 19), project ID 16, task
ID 31. Earlier setup attempts also left clearly labelled `PMS Features QA`
workspaces. Test records are retained so they can be inspected in web/mobile.
No existing business record was intentionally edited by this acceptance run.

## Coverage and limits

The supplied contract contains 312 PMS operations: 293 deployed and 19 marked
undeployed by its deployment comparison. The Flutter hub exposes 281 deployed
general operations through native contract forms and structured data views.
Internal webhook/realtime infrastructure routes are not user menu actions;
global recovery screens require a superuser. Inventory coverage is not a claim
that 281 operations were exercised on the phone.

The 43 listed flows are the device-verified subset. Financial writes, approval
chains, privileged recovery, native file-picker/upload/download/share dialogs
and every advanced configuration combination still require device acceptance.
Board/calendar/Gantt/report views currently show structured native data rather
than full web visualization parity. Chat uses foreground polling. Push,
offline writes and SSO are not implemented. iOS requires a separate macOS/Xcode
build, signing and physical Apple-device test.

The APK is a debug-signed direct-testing build, not a store submission artifact.

## Installed result

The normal APK was installed successfully with ADB and launched on the phone.
Android reports `versionName=0.2.0`, `versionCode=2`, min SDK 24 and target SDK 36.
The phone's original USB stay-awake value (`0`) was restored after testing.
