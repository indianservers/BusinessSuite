# Inventory Module

This folder contains the Business Suite inventory module wrapper and the cloned
canonical Inventory implementation.

Canonical source:

`C:\Indian Servers\AI Inventory Management Software`

Cloned implementation:

`backend/app/apps/inventory/vyapara_erp`

The cloned app is the existing Vyapara ERP Flask application with its routes,
models, migrations, templates, static assets, tests, seed script, and docs
preserved. Business Suite should wrap, mount, proxy, or integrate this app
rather than recreating Inventory screens or business logic from scratch.

