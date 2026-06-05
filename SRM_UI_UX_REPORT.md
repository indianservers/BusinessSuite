# SRM UI UX Report

Date: 2026-06-04

## Routes
| Route | Status | Evidence |
|---|---|---|
| `/srm` | Passed | Dashboard route registered. |
| `/srm/dashboard` | Passed | Dashboard route registered. |
| `/srm/sales-orders` | Passed | Real API list and lifecycle action buttons. |
| `/srm/contracts` | Passed | Real API list view. |
| `/srm/engagements` | Passed | Real API list and create PMS project action. |
| `/srm/billing-plans` | Passed | Real API list view. |
| `/srm/invoice-drafts` | Passed | Real API list view. |
| `/srm/invoices` | Passed | Real API list and approve/send actions. |
| `/srm/collections` | Passed | Real aging API view. |
| `/srm/revenue-recognition` | Partially Passed | Uses lead-to-cash report; detailed recognition schedules are not built. |
| `/srm/profitability` | Passed | Real profitability API view. |
| `/srm/customer-360` | Partially Passed | Route exists; backend endpoint requires customer id; UI lacks customer selector/drill-in. |
| `/srm/reports` | Passed | Real lead-to-cash report API view. |
| `/srm/settings` | Partially Passed | Route and API call exist; no settings edit form yet. |

## Frontend Evidence
- `npm run build`: Passed.
- SRM included in app registry, suite card, breadcrumbs, global search, product context, login page, protected route logic, and sidebar nav.

## Responsive/Mobile
Status: Partially Passed.
Evidence: SRM tables use horizontal overflow and responsive header layout. Dedicated mobile workflow testing was not performed in Browser/Playwright.

## Pending
- Dedicated creation/edit forms for all SRM entities.
- Customer 360 selector and detail panels.
- Frontend automated tests.

