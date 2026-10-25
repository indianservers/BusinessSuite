# BusinessSuite mobile — KaryaFlow PMS

Latest build: `build/releases/KaryaFlow-PMS-0.2.1-arm64.apk`.
The [full PMS device audit](qa/full-pms/REPORT.md) is incomplete because the phone
disconnected. It lists all 316 requested items, verified flows, remaining native
UI/deployment/permission gaps, and the prepared super-admin guard patch.


Flutter Android/iOS client using the existing FastAPI backend. All application
source and native platform projects live in this directory. The web application
and backend remain shared with the existing suite.

API contract source: [mobile API guide](../docs/mobile-api-reference/README.md)
and its OpenAPI bundle. Version 0.2 adds a native Flutter feature hub with
forms and data views for 281 deployed general PMS operations. Privileged recovery
screens require a superuser. Nineteen undeployed operations are unavailable.
Catalog coverage is separate from physical-device verification.
The API base includes `/api/v1` once. Task detail uses its dedicated GET endpoint,
and every request sends a unique `X-Request-ID`; error references are retained.

## PMS client features

- PMS login (`module: project_management`), TOTP/recovery-code MFA.
- Secure persisted session, token rotation, authenticated startup, logout.
- Membership-scoped workspace selector and projects/tasks overview.
- Workspace creation for server-granted `pms_manage_projects` / `pms_admin` users.
- Project creation for workspace owners/admins.
- Task creation and status changes for owners/admins/members.
- Read-only guest experience, unknown roles denied editing.
- Search and project filtering, pull-to-refresh, errors and retry.
- Workspace people, private invitation tokens, invitation acceptance/revocation,
  member role changes and removal using existing PMS APIs.

No demo records, production credentials, separate database, or backend changes
are included. HRMS attendance/leave are deferred: PMS is the first module as
requested. Version 0.2 adds epics, components, releases, milestones, sprints,
risks, comments, checklists, subtasks, tags, time logs, saved filters, teams,
documents, reports, approvals and commercial forms through existing endpoints.
Native timer and chat screens support messages, replies and file attachments.
File picking, downloads and sharing use native platform dialogs.
Version 0.2.1 adds native board/list and month/week/day/agenda planner views.
Gantt/roadmap/report endpoints still use structured data views;
full web visualization parity, push, offline writes and SSO remain future work.

## Toolchain

Use a current stable Flutter SDK with Dart >=3.10. Android needs Android Studio,
the Android SDK and an emulator or connected device. iOS builds require macOS,
Xcode, and Apple signing setup. The generated `com.businesssuite` application
identifier is provisional; confirm company-owned identifiers before publishing.

On this machine the local SDK is installed outside the repository at
`C:\Users\Sai Satish\.local\share\flutter`. Invoke its `bin\flutter.bat`
directly, or add that `bin` directory to your own PATH.

Flutter 3.47.8 / Dart 3.13.7 was used for initial validation. On this Windows
machine, native dependency hooks fail when the SDK executable path contains a
space. Use the equivalent short path when invoking Flutter:
`C:\Users\SAISAT~1\LOCAL~1\share\flutter\bin\flutter.bat`.
The provided Windows wrapper resolves that path and gives Java a local socket
directory, avoiding the loopback failure seen with this machine's JDK:

```powershell
./scripts/flutter.ps1 pub get
./scripts/flutter.ps1 analyze
./scripts/flutter.ps1 test
./scripts/flutter.ps1 run --dart-define=API_BASE_URL=https://your-staging-server/api/v1
```

This changes environment variables only for the command; it does not change
global PATH, Java configuration, or firewall settings.

```powershell
cd 'C:\Users\Sai Satish\Documents\GitHub\BusinessSuite\Flutter-Apps'
flutter pub get
flutter analyze
flutter test
flutter run --dart-define=API_BASE_URL=https://your-staging-server/api/v1
```

The URL is required; there is no implicit production backend. Configure a
trusted HTTPS endpoint for release builds. Tokens are saved using platform
secure storage; passwords and MFA challenges are not persisted. Do not enable
HTTP against a public server: it transmits credentials without encryption.

### Local Android emulator

Start the existing backend using its documented PostgreSQL environment, then:

```powershell
# From backend/, after configuring the database and installed PMS module:
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# From Flutter-Apps/:
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1 --dart-define=ALLOW_INSECURE_HTTP=true
```

Android debug builds allow local cleartext networking. Release manifests do not
enable it. For a physical phone use a reachable development machine LAN address
and the appropriate firewall rule, or a trusted HTTPS staging server.
An iOS simulator on the same Mac as the backend can use `http://localhost:8000`;
iOS debug configuration permits local networking. Use HTTPS for device testing
when the local networking exception does not apply.

Use an existing PMS account (`pms_project_manager`, `pms_team_member`, etc.). The
server applies its module-login policy. Workspace membership is required even
for global administrators; global role does not bypass workspace membership.
The client reads permission names from `/auth/me`'s role object. It does not
mistake `/auth/permissions` (the permission catalog) for the user's grants.

## API contracts

All paths are relative to `API_BASE_URL`:

- `POST /auth/login`, `POST /auth/mfa/verify`
- `POST /auth/refresh`, `GET /auth/me`, `POST /auth/logout`
- `GET/POST /project-management/workspaces`
- `GET /project-management/workspaces/{id}/overview`
- `POST /project-management/projects`
- `POST /project-management/projects/{id}/tasks`
- `PATCH /project-management/tasks/{id}`
- `GET /project-management/workspaces/{id}/members`
- `PATCH/DELETE /project-management/workspaces/{id}/members/{member_id}`
- `GET/POST /project-management/workspaces/{id}/invitations`
- `DELETE /project-management/workspaces/{id}/invitations/{invitation_id}`
- `POST /project-management/workspace-invitations/accept`

Adding a workspace user uses the existing invitation/membership process. This
does not create a global authentication account or elevate a PMS administrator
to a system superuser. Users accept invitations while signed into the addressed
existing account. Tokens are shown once for private sharing and never logged.

## Physical Android device test

`integration_test/pms_device_test.dart` runs 20 real UI operations against a
configured live backend. It creates clearly labelled `Android QA` workspaces,
projects, tasks, and invitations. Use authorized test accounts. The final
permission check also sends a device-side API request to confirm a Guest write
is rejected by the server, in addition to checking read-only UI controls.

Prepare an ignored `.dart_tool/device-test.json` containing `API_BASE_URL`,
`QA_ADMIN_EMAIL`, `QA_ADMIN_PASSWORD`, `QA_MEMBER_EMAIL`, `QA_MEMBER_PASSWORD`,
and a unique `QA_RUN_ID`. Never commit or distribute this credential file.

```powershell
./scripts/flutter.ps1 drive -d YOUR_DEVICE_ID --driver=test_driver/device_test.dart --target=integration_test/pms_device_test.dart --dart-define-from-file=.dart_tool/device-test.json
```

Results and app screenshots are written under `build/device-qa/`. Build the
normal APK afterward with only `API_BASE_URL`; the distributed app must not
contain QA account credentials or the test entry point:

```powershell
./scripts/flutter.ps1 build apk --debug --target-platform android-arm64 --dart-define=API_BASE_URL=https://businesssuite-rosy.vercel.app/api/v1
```

Workspace role is reloaded from the overview before enabling editing. Workspace
switching clears the prior dataset; stale overview responses are discarded.
The server authorizes every operation. Expired access tokens trigger one shared
refresh, then one retry; a failed refresh due to connectivity preserves the
session for retry. Financial/offline write queues are intentionally absent.
After an uncertain save, refresh before resubmitting to avoid duplicate records.

## Verification

Validation on 24 October 2026:

- `flutter analyze`: no issues.
- `dart format --output=none --set-exit-if-changed lib test`: clean.
- `flutter test`: 14 local unit/widget tests passed.
- Physical OPPO CPH2717 / Android 16: all 20 live PMS operations passed against
  the deployed backend, including invitations, member access, status persistence,
  and a server-rejected Guest write. See [device acceptance report](qa/android-2026-10-24/REPORT.md).
- The normal ARM64 debug APK was built, installed, and tested separately from
  the integration-test APK. Native UI sign-in and cold-start secure-session
  restoration were verified. The APK excludes QA credentials and the test entry point.
- NDK `28.2.13676358`, required Android platforms and CMake are installed.
  The recovered NDK and Flutter engine archives were checksum-verified.
  An optional exact-version local engine Maven cache avoids the stalled engine
  download on this machine; it lives in ignored `.dart_tool/verified-engine-maven`.
  The helper script enables it only when present. Other dependencies and engine
  versions continue using their normal repositories.
- iOS platform files and keychain entitlements are configured; compilation and
  secure-storage behavior require validation on macOS/Xcode and an Apple device.

Automated tests cover token refresh concurrency, rejected refresh cleanup,
offline refresh, forbidden requests, PMS login payload, corrupt stored sessions,
guest read-only controls, member controls, and unknown membership roles.

Before real-device acceptance, verify with staging users:

1. Sign in, including MFA if enabled, restart the app, and restore the session.
2. Switch workspaces; verify another workspace's tasks never remain visible.
3. As an owner/admin create a project; as a member create a task and change status.
4. Confirm the changes appear in the existing web app.
5. As a guest verify editing is unavailable and direct writes are rejected by the server.
6. Revoke membership on web, refresh mobile, and confirm access is removed.
7. Expire/revoke the session; confirm reauthentication and local credential cleanup.

Native signing, store metadata, privacy declarations, push, release signing and
distribution pipelines must be completed before store submission. Generated
Android release signing remains the Flutter development template until replaced
with company-owned release credentials. Never publish a debug-signed artifact.


## PMS 0.2 Android build and acceptance

The debug APK for direct phone testing is
[build/releases/KaryaFlow-PMS-0.2.0-arm64.apk](build/releases/KaryaFlow-PMS-0.2.0-arm64.apk).
It uses the deployed BusinessSuite backend. Build it without QA credentials:

```powershell
./scripts/flutter.ps1 build apk --debug --target-platform android-arm64 --dart-define=API_BASE_URL=https://businesssuite-rosy.vercel.app/api/v1
```

Open **PMS features** in the app bar, a project's overflow button for project
features, or **More task actions** in task details. The hub has search, category
filters, project context, role checks, real record pickers, date pickers, nested
forms, explicit mutation confirmation, pagination and native file controls.
The server remains authoritative for permissions.

Regenerate the contract inventory after the supplied guide changes:

```powershell
python scripts/generate_pms_catalog.py
```

The extended acceptance test uses real Flutter controls and the deployed API:

```powershell
./scripts/flutter.ps1 drive -d YOUR_ADB_SERIAL --driver=test_driver/features_device_test.dart --target=integration_test/pms_features_device_test.dart --dart-define-from-file=.dart_tool/device-test.json
```

The ignored test configuration requires `API_BASE_URL`, `QA_ADMIN_EMAIL`,
`QA_ADMIN_PASSWORD`, and a unique `QA_RUN_ID`. Never use this configuration to
build the distributable APK. Evidence and remaining validation limits are in
[qa/pms-v2/REPORT.md](qa/pms-v2/REPORT.md). Contract inventory is in
[qa/pms-coverage.json](qa/pms-coverage.json).

