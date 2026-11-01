# Local menu redesign verification

Verified locally on 2026-11-01. No deployment, Git push, or production database changes.

## Changes

- Shared category navigation in PMS, CRM, HRMS, Finance, Sales & Inventory, and the Power Apps toolkit.
- Expandable categories and related-page submenus; expand/collapse all; saved category state per user, company, and module.
- Search uses original names, clearer display names, categories, and routes, including collapsed pages.
- Existing daily shortcuts, pins, and history remain under Your shortcuts. PMS My work remains a primary task link.
- PMS task list/creation and workspace board now reuse the common menu. Workspace/project context remains in navigation URLs.
- Role-based links retain existing access checks. Power Apps uses its permission-filtered server catalog and preserves the selected environment.
- Mobile task navigation matches the shared 1024px breakpoint; fixed the drawer stacking above its backdrop.
- Replaced an unsupported Lucide icon import discovered during local page navigation with the installed BarChart3 export.

## Automated checks

- Navigation categories script: 102 checks passed (roles, managed grants, canonical paths, categories).
- Navigation workspace script passed, including new category boundary, alias deduplication, original/friendly search, ordering, intern hub, and single-page label checks.
- Scoped ESLint passed for changed menu components and the integrated task/Power Apps pages.
- Frontend production build passed (existing dependency annotation and chunk-size warnings remain).

## Browser checks

- PMS task list and workspace board use the shared categorized menu; task links preserve workspace=1.
- Expand/collapse all, nested backlog/sprint pages, original/friendly page search, no-results recovery, saved state after reload, and compact rail expansion.
- CRM and HRMS category expansion, plus Finance and Sales & Inventory module switching/category visibility.
- Power Apps categories, expandable tools, and environment-preserving links. Local QA organization has no enabled Power Apps environment; execution was not tested as part of this menu change.
- HRMS drawer at 390x844: open, Escape close, focus returns to opener.
- PMS task drawer at 950px and 390px: visible open control, dialog above backdrop, category controls usable, close works.
- Temporary viewport overrides reset. Local preview left open.

Screenshots: .local/menu-redesign/{pms,pms-mobile,crm,hrms,hrms-mobile,power-apps}.png.
