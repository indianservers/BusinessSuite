# Physical Android PMS acceptance test

**Result: 20/20 device operations passed.**

Tested on 24 October 2026 using the connected OPPO CPH2717 physical phone running Android 16. Flutter integration tests drove the real native UI against https://businesssuite-rosy.vercel.app/api/v1. No simulated backend was used for these 20 operations.

The normal ARM64 debug APK was installed afterward. Its login was also exercised through native phone input, then the app was force-stopped and reopened: the encrypted session restored and existing deployed workspace/project data loaded without signing in again.

## Operations

1. PASS — Sign in to deployed backend as PMS admin
2. PASS — Create first workspace
3. PASS — Create second workspace
4. PASS — Switch workspace and load owner permissions
5. PASS — Create first project
6. PASS — Create second project
7. PASS — Create task with description
8. PASS — Create high priority task in another project
9. PASS — Filter tasks by project
10. PASS — Search task by title across projects
11. PASS — Change task to In Progress
12. PASS — Complete task
13. PASS — Refresh and confirm persisted task status
14. PASS — Invite existing user to workspace
15. PASS — Create second user invitation
16. PASS — Revoke pending invitation
17. PASS — Accept invitation as member and add workspace user
18. PASS — Create a task with member permissions
19. PASS — Change member to Guest as workspace owner
20. PASS — Guest can read but cannot mutate workspace tasks

The Guest security check includes both read-only Flutter controls and an actual write request sent from the phone receiving HTTP 403. User addition used the existing email-bound workspace invitation and acceptance flow; no global authentication account was created.

## Persisted backend readback

Independent authenticated reads confirmed workspace 8 contains two projects, three tasks, one completed task, accepted/revoked invitation history, and only the Owner membership after temporary member cleanup.

The final test run is `1024145646`. Its retained QA workspace IDs are [8, 9]. Records created during testing are labelled Android QA; earlier diagnostic runs also left labelled QA records. Existing business records were not edited.

## Delivery and implementation

- APK: [KaryaFlow PMS ARM64 debug APK](../../build/releases/KaryaFlow-PMS-0.1.0-arm64.apk).
- Machine-readable results: [report.json](report.json).
- Normal APK after cold-start session restoration: [screenshot](normal-apk-signed-in.png).
- Projects: [screenshot](operation-06.png).
- Completed task: [screenshot](operation-12.png).
- Invitations: [screenshot](operation-16.png).
- Member-created task: [screenshot](operation-18.png).
- Guest read-only view: [screenshot](operation-20.png).

All implementation changes are in Flutter-Apps. No backend endpoint, migration, or table was added. The supplied mobile API reference was checked: all 19 client operations exist in its OpenAPI, and none are marked local-only in its deployment comparison.

Additional validation: 14 local unit/widget tests passed; static analysis and Dart formatting are clean. iOS was not compiled or tested in this Windows/Android task.

The distributed APK contains the deployed API URL and excludes the QA password and integration-test entry point. Test credentials remain only in ignored local test configuration.

APK SHA-256: `606c9ac94871f6c01aacd1ee8e64154b7f9f0d4efd10659af96d79dcec8a0c05`

## Toolchain repair

Installed NDK 28.2.13676358 from the official archive after verifying Google repository SHA-1 086bba43ff2f5eb0e387b15c8278bb4e0d89ba1d. Installed required Android platforms/CMake through the existing build toolchain. Recovered the exact Flutter ARM64 engine through ranged downloads and verified it against Google MD5 cVUs2HzyZ4REGkXd/afiNA== before use. The optional local engine Maven cache is ignored and scoped to the exact engine version; other dependencies continue using their normal repositories.

The Windows helper uses a short SDK path and a scoped Java socket directory. It now forwards Flutter verbosity flags correctly. No global firewall, PATH, or Java settings were changed.
