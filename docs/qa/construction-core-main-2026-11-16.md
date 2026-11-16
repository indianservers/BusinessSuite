# Construction core integration

The backend now supports canonical workspace/site setup, BOQ and independent review, variations and certified measurements, work packages, WBS/tasks/dependencies, resource scheduling and retained baselines, actual hours/costs/budgets, commercial links, native file evidence, payment certificates, handover and client reports. It reuses native PMS/SRM operations, projects, tasks, files and financial records. Planned work does not become actual time or ledger postings automatically.

The reviewed merge preserves all 146 earlier route rules and adds 37 exact Construction rules. Six native PMS operations retain their default public bodies, signatures and documentation. The existing Accounts upload operation and Restaurant branch-history retention remain present. The Construction branch-delete addition blocks deletion of retained evidence before generic cleanup. Frontend changes and the newer multi-user Member/issuer delivery extension are separate work.

## Current-source evidence

- Full Construction functional cohort: **230 passed, 7 skipped**, zero failures/errors, 1,130.88 seconds. Skips are recorded by exact node/reason in `.local/construction-main-final-proof.json`; they are not represented as completed tests.
- Eight targeted actual PostgreSQL cases passed in 76.42 seconds: workspace creation/rollback/native-user identity, actual-write workspace retention, immutable baseline identity and native PMS compatibility. The PostgreSQL writer path is unchanged by the separate SQLite metadata-lock fix.
- Existing native scheduling module: 10 passed with one explicit browser-only skip. A separate repeat of its existing baseline case passed with new exact persisted/response field assertions; this repeat is not counted as another unique test.
- All 45 integrated backend/test files match the reviewed current-main diagnostic freeze. Eleven shared source hashes match the independently reviewed additive candidate.

The initial broader run was 229 passed/1 failed/7 skipped. Its commercial retry failure was caused by the shared SQLite writer lock updating the company timestamp. Commit `9550692ef` preserves that timestamp; the original authority fingerprint is unchanged. Deterministic clock and independent SQLite/PostgreSQL lock tests pass, and the entire Construction cohort was rerun above. Earlier handoff collection failures came from four omitted fixture/test files; those exact frozen files were restored, with no skipped assertion or invented fixture. Failed artifacts are retained.

The donor also has source-qualified PostgreSQL and desktop/mobile browser evidence across multiple revisions; those are not claimed as one unified current-source all-green run. Current UI wiring, multi-user delivery/actor17 integration, real first activation and the final whole-app regression remain gates. Runtime support is still unpublished; this backend integration does not activate or deploy a pack.

Evidence: `.local/construction-main-core-sqlite.xml`, `.local/construction-main-targeted-postgres.xml`, `.local/construction-main-shared-proof.json`, `.local/construction-main-final-proof.json`, and `.local/construction-main-core-before-writer-fix.xml`.
