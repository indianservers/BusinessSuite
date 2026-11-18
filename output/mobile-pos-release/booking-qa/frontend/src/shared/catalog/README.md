# Shared catalog views

`CatalogPage` serves Products & Services in PMS, CRM, Sales, and Inventory.

- Cards retains the existing loaded-page grouping controls.
- List uses `LocalRecordGrid` for columns, filters, saved layouts and grouping. The catalog API owns the outer search and pagination.
- Categories and Tags group the records on the current page. A tagged item can appear in several tag groups; selection uses its stable kind/id identity.
- Favorites and Frequent are personal browser preferences, scoped to account and company and shared across module entry points. Frequent ranks actual preview opens, rather than sales or purchase volume. Up to 500 personal records are retained.

Favorites and Frequent send `item_keys` to the catalog endpoint. Filtering and optional key ordering happen before pagination and after tenant, branch, workspace and record visibility restrictions. An empty key list returns no records. Facets cover the accessible matching set, not only the current page.

Tags are shared catalog data stored in `SRMProduct.metadata_json.catalog_tags`. The API accepts up to 20 normalized tags of 40 characters each. Omitting `tags` preserves existing tags for older clients; `tags: []` clears them. This does not require a database migration. Tag edits use the existing version-checked item save endpoint.

Write actions use the API's per-kind permissions and existing save, duplication, branch-reuse and archive handlers. Archive retains its review dialog. Favorites, previews and code copying are available to readers. Failed tag saves keep the draft visible.

Relevant validation:

- `playwright/catalog-views.spec.ts`
- `backend/tests/test_shared_catalog.py`
- `backend/tests/test_pos_shared_catalog.py`
- `backend/tests/test_catalog_branch_reuse.py`
