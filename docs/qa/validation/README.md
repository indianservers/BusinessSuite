# Validation implementation evidence

This change implements validation fixes, starting with Interns Hub. It is not a claim that every form has had an individual browser create/edit test. See `inventory.json` and `coverage.json` for the inventory and verification levels.

## Scope and implementation

The current inventory identifies 166 web source files containing form controls, 34 phone/mobile-related source files, 72 contact consumer files, and 22 mapped models with 28 phone columns. These are source-file counts, not unique-form counts; some matches are read-only displays, hardware icons, or responsive-layout names.

Implemented controls cover the application and profile in Interns Hub; HRMS employee creation/editing, profile change requests, company/settings, directory and CSV exchange; PMS task custom fields/shared responses; and CRM lead/contact/company forms, inline edits, enrichment, calls, messages and custom fields. Mapped FAM and communication contact writes also receive the shared server checks. Other modules retain their existing field-specific policies; the server additionally checks changed email/name values, URLs and finite numeric values.

The canonical rules live in `shared/validation/`. `scripts/sync_validation_contract.py` copies portable sources into both independent frontend deployments and the backend. `--check` verifies that those sources match. Calling codes and national numbers remain separate strings. The central requested national length is 10 ASCII digits for every supported code. The searchable selector defaults to +91 for new entries. Missing legacy codes stay unknown. Paste handlers reject the full candidate and never truncate it into another valid number. No phone verification or ownership is implied.

Applications validate Unicode/mononym names, email syntax without spaces, supported choices, real past birth dates, percentages 0–100, optional blank 12th marks, configured dates/durations, bounded skills, typed IDs, URLs, consent, uploads and passwords. Aadhaar/PAN have distinct format checks. International passport and legacy voter IDs remain bounded text as printed; no unverified jurisdiction pattern is imposed. Resume upload remains optional.

The employee wizard now validates forward navigation, focuses invalid controls, maps backend field errors, retains values, accepts an optional last name, and prevents duplicate submissions. Personal editing supports null/empty legacy last-name submissions without a database conflict. The separate login-account form no longer supplies a shared default password and now uses the configured server password policy and byte limit. The LMS completion callback now requires permission and tenant scope and parses a finite decimal score before persistence.

## Changed file groups

`change-manifest.json` lists the validation-related source, schema, model, frontend, migration, fixture and test files. Shared rules/generated copies, request validation, HRMS/CRM/PMS editors and both migration trees are included. Unrelated existing work remains in place.

## Migration and existing records

Both migration trees contain revision 021 (`20261025_021_contact_codes.py` and its `pg_` equivalent). It adds nullable calling-code columns without rewriting numbers, widens employee names/user email where required, and includes the calling code in the existing communication-consent subject constraint. It does not introduce unique-phone restrictions.

The contact migration was applied transactionally to the configured PostgreSQL database. All 28 country-code columns were verified. Before/after aggregate fingerprints and row counts confirmed that existing contact/name/email values were unchanged. Pre-migration schema evidence is stored privately at the path in `configured-db-migration.json`; it contains schema and fingerprints, not raw contact records or credentials. Other feature migrations and the Alembic revision marker were not changed. The deployment pipeline should still process its normal migration chain; revision 021 is retryable.

Invalid legacy contacts are flagged for correction. Shared identity does not guess a code or copy ambiguous legacy contacts into a new usable contact. Valid changes and explicit phone clearing propagate correctly. Old application approvals require corrected contacts before account creation. CSV imports require an explicit calling code when a phone is supplied; exports include both strings. Provider transport strings are constructed only after validating the pair; historical delivery records are preserved.

## Verification

- `acceptance-tests.log`: 249 passing affected backend tests.
- `frontend-tests.log`: 289 passing frontend validation checks, including every supported calling code.
- `main-build.log` and `interns-build.log`: both production builds succeed.
- `full-final-tests.log`: the earlier full run had 993 passes, 4 failures and 7 skips. All four failing scenarios were corrected and pass in the affected-group reruns; this is not represented as a fresh, entirely green full-suite run after every final edit.
- Migration tests exercise both revision files, retries, unchanged legacy phone text and consent identity across different calling codes. API tests cover frontend bypass, malformed values, leading zeros, create/edit/reopen, Unicode mononyms, email/ID/date/percentage/consent handling, password limits, tenant boundaries and legacy identity synchronization.
- Browser evidence includes mobile full-number paste rejection, application review and account errors, HRMS step blocking, valid employee creation, mononym editing, country change/save/reopen, and a 390px editor without document-level horizontal overflow.

## Remaining verification limits

Individual browser coverage is incomplete across the full inventory, especially company/settings, CRM variants and dynamic custom-field editors. The native Flutter client was not changed or device-tested. Seven tests requiring a disposable PostgreSQL test database remain skipped; no synthetic fixtures were inserted into the configured PostgreSQL database. Its contact schema migration was separately verified without changing existing record values.

## Format references

Calling-code reference: https://www.ituob.org/registers/e164-cc/

Aadhaar reference: https://uidai.gov.in/images/Aadhaar_Handbook_2021_LR.pdf

PAN reference: https://www.incometaxindia.gov.in/documents/d/guest/1-permanent-account-number-pan-pdf
