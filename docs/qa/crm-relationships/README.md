# CRM customers, companies and vendors

Implemented dedicated CRM Customers, Companies and Vendors pages on the existing shared master-data API. Sales Customers and POS quick creation use that same master and IDs. Individual classification uses the existing company-master details field; no tables, database or migration were added. Business companies can independently hold Customer and Vendor roles.

Lead conversion creates a shared Sales customer, reuses the verified contact identity, and preserves the customer ID through correction and reconversion. Existing company/customer data is not automatically merged or reclassified by name.

Navigation: Dashboard is the first CRM group and `/crm` opens the KPI dashboard. Birthdays and marketing entries are under Communication. Shared companies is available in main Settings, with the old CRM directory link redirected there.

Validation:
- Shared relationships plus master-data tests: 11 passed, 1 skipped (existing PostgreSQL-specific coverage).
- Contact-directory regression suite and initial shared relationship tests: 23 passed.
- Final conversion/identity checks: 4 passed.
- Browser harness `node qa/crm_relationships_browser.cjs`: creation payloads, individual/business selection, dedicated pages, menu ordering and Communication placement passed.
- ESLint and TypeScript checks passed. Production build checked separately.

Screenshots: `companies-desktop.png`, `customers-mobile.png` (isolated browser fixtures).

Final verification: main Settings catalog/detail checks passed (1 test); final production build and refreshed API health returned successfully.
