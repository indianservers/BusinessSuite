# Inventory Source Of Truth

Inventory must not be recreated inside this Business Suite repository from scratch.

Use the existing Inventory/ERP application as the canonical implementation:

`C:\Indian Servers\AI Inventory Management Software`

That project is a standalone Flask, SQLAlchemy, MySQL, Bootstrap 5 application named Vyapara ERP. It already includes:

- Product, category, brand, unit, warehouse, customer, and supplier masters
- Purchase invoices, sales invoices, receipts, payments, expenses, and journal entries
- Inventory ledger, current stock, stock adjustment, weighted-average costing, low-stock alerts
- POS, reports, dashboards, Chart.js, DataTables, invoice print/PDF flows
- Manufacturing/BOM, recurring invoices, multi-currency, scheduled reports, PWA/offline support
- Its own `app`, `migrations`, `docs`, `tests`, `seed.py`, and deployment documentation

Business Suite Inventory work should therefore:

- Inspect and reuse/clone from that project first.
- Preserve that project's existing business logic, database model, migrations, routes, templates, tests, and UX unless a real blocker requires an integration adjustment.
- Prefer integration, mounting, shared navigation, proxying, or controlled code import over rebuilding equivalent Inventory screens/APIs.
- Avoid creating a separate competing Inventory module with duplicated concepts.
- If Inventory must appear in Business Suite navigation, link or wrap the existing Vyapara ERP implementation rather than replacing it.

Current canonical git branch checked: `main`.
Current canonical commit checked: `a7646c7`.
