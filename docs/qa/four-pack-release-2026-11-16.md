# Four-pack release scope

This release selects Hospital, Salon, Accounts Company and Construction. Retail,
Pharma and Restaurant remain Upcoming; their existing source is retained and new
activation is blocked. Existing native permissions, company approval, explicit
pack grants and native module licensing remain mandatory.

Hospital covers appointments and payments only. Doctors and stylists remain
canonical HRMS employees. Scheduled work does not create actual worked time.
Publication requires the verified private-delivery schema121 and an explicitly
reviewed empty branch; existing operational history is never silently adopted.

Validation completed before deployment:

- Original integration: five PostgreSQL cases passed in63.76s, including fresh
  signup/approval/login, doctor/patient/appointment creation, payment replay,
  canonical audit provenance and ordinary Construction workspace/site/WBS.
- Private delivery: five native PostgreSQL cases passed in324.52s; migration
  119→120→121, repeat migration, issuer retention and genuine Team/Task producers.
- Strict schema qualification:27 native PostgreSQL and24 SQLite tests passed;
  canonical schema reports ready and weakened checks/guards remain rejected.
- Original static delivery and probe cohort:84 passed,27 PostgreSQL-only skipped
  under SQLite, before the narrow native-TRIM parser correction qualified above.
- Company-admin POS fields:36 passed. Publication control regressions:2 passed.
- Upcoming activation policy:10 passed. Construction startup helpers:29 passed.
- Construction ordinary-user correction:1 HTTP chain,5 compatibility and2
  exact-self authorization checks passed on the frozen owner packet.
- Accounts current-main verification:42 SQLite,11 PostgreSQL and one actual API
  desktop/mobile browser workflow passed;151 calls drained successfully.
- Full suite frontend production build and Interns Hub production build passed.

This is focused release validation, not a claim that the entire repository test
suite passed. UI changes use existing components and styles; unrelated pending
authentication-page edits are excluded from this release. Production activation
and post-deployment health are recorded separately after execution.

## Production result

Deployed exact commit `e2e534c60f055f50c0a071d79125163352513e3e` to
`https://besterp.app`. Both frontends were rebuilt from that committed snapshot;
concurrent uncommitted homepage/authentication work was preserved separately.
Subsequent Team UI commits on main are not part of this release.

Before migration, API/socket and backup writers were stopped. The matching
database and private uploads/configuration were streamed off-host and validated
with PostgreSQL18 full restore-to-null, complete tar reads and SHA256 receipts.
Migration reached `pg_20261116_121_delivery_sources`; strict delivery qualification,
exact four-pack publication and existing critical business counts passed.

The initial automated public check received HTTP403 for Python's default user
agent. The API had started successfully; public verification using curl returned
HTTP200 and the exact release commit. The new release was resumed and both public
and local API health passed. The existing backup timer was restored.

Live anonymous browser checks passed at1440px and390px: Settings redirected to
login, returned HTTP200 and produced zero page errors. These checks do not claim
authenticated production workflow testing. Existing UI styles and components
were retained. Retail, Pharma and Restaurant remain Upcoming.
