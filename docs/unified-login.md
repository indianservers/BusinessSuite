# Shared Business Suite login

All employee-facing modules use `/login`. Old HRMS, CRM, PMS, Sales and Finance login URLs redirect to that same page without a module-specific destination. Password login no longer submits a module restriction; roles, company membership, module permissions and record scopes remain enforced by existing API authorization. Customer/partner portals and Interns Hub retain their separate identity boundaries.

Every successful sign-in opens the dedicated `/dashboard` application dashboard, filtered to authorized modules. MFA and SSO use the same dashboard destination. Supplied return URLs never redirect to an external host or directly select a module.

The public `/auth/branding` endpoint returns only `company_name` from the active master Company record selected by server `LOGIN_COMPANY_ID` (default 1). It accepts no company selector and never returns addresses, contacts, registrations or memberships. Company name edits appear on the login page after its short branding cache refresh. If the master company is missing or inactive, the page displays generic Business Suite branding. No database migration is required.

The application dashboard reuses the public home module catalog. It provides authorized module cards, module search, responsive layouts, an empty-access state, retriable access loading and the existing company-context switch for multi-company members. All applications navigation in the module switcher and Power Apps links back to `/dashboard`. The root `/` redirects signed-out visitors to `/login` and signed-in users to `/dashboard`; the public module chooser is no longer the entry page.

All suite entry links now use exactly `/login` without module-specific `next` parameters. Legacy login links strip `next`, and every successful sign-in opens `/dashboard` so users choose their authorized module there. Password-reset tokens and SSO handoff parameters remain intact. This supersedes the earlier destination-preservation behavior.
