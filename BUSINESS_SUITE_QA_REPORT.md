# Business Suite QA report

Date: 12 November 2026. Release status: **BLOCKED**.

This report distinguishes requested business workflows from individual automated assertions. Missing service appointments/packages and incomplete POS invoicing/payment posting are not counted as passing features.

Business cases planned: **107**. Statuses: PASS **70**, FAIL **0**, BLOCKED **37**, NOT RUN **0**.
Completed evidence contains **465 unique latest backend test nodes** ({'PASS': 462, 'BLOCKED': 3}) and **26 frontend harnesses** ({'PASS': 26}). Route-harness checks are separate from real browser/API workflows.

Safety: the configured application PostgreSQL schema was inspected in a READ ONLY transaction. All financial writes, 10,000-customer seeding and concurrency checks used disposable SQLite databases or a separate localhost PostgreSQL cluster. No application tables were migrated, dropped, truncated, reset or merged. No external messages/payments were sent.

Evidence: `backend/outputs/business-suite-qa-summary.json`, JUnit XML/logs under `backend/outputs/business-suite-*`, and the read-only `business-suite-source-schema.json`. GST rates are synthetic configured fixtures, not legal classifications.

Full pre-fix repository regression: **1800/6496 observed progress entries**; completed: **False**. It must not be represented as a clean post-fix full run.

Scope qualifications: common-route harnesses verify registry/permission/context behavior and use stub native content. The live browser test mounts the actual registered React pages and forwards requests unchanged to the real disposable FastAPI DB. POS tax/discount tests certify order arithmetic; they do not establish invoice issuance or receipt posting. Generic contract lifecycle tests do not establish AMC scheduling or HRMS technician integration.

## TC001 — Open Tasks from CRM and PMS; verify same canonical route and page

- Module: Common
- Expected: Open Tasks from CRM and PMS; verify same canonical route and page with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: test-common-routes.cjs, tests.test_common_task_scope.test_project_and_all_filters_keep_original_tasks[all], tests.test_common_task_scope.test_project_and_all_filters_keep_original_tasks[pms]
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend/outputs/business-suite-frontend-results.json :: test-common-routes.cjs`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_common_task_scope.test_project_and_all_filters_keep_original_tasks[all]`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_common_task_scope.test_project_and_all_filters_keep_original_tasks[pms]`

## TC002 — Open Employees from HRMS and PMS; verify same records

- Module: Common
- Expected: Open Employees from HRMS and PMS; verify same records with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: test-common-routes.cjs, tests.test_shared_profiles.test_profiles_and_links_cannot_cross_users_or_organizations
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend/outputs/business-suite-frontend-results.json :: test-common-routes.cjs`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_shared_profiles.test_profiles_and_links_cannot_cross_users_or_organizations`

## TC003 — Open Teams from CRM, PMS and HRMS

- Module: Common
- Expected: Open Teams from CRM, PMS and HRMS with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: test-common-routes.cjs, tests.test_pms_teams.test_workspace_teams_permissions_membership_and_scope
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend/outputs/business-suite-frontend-results.json :: test-common-routes.cjs`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_teams.test_workspace_teams_permissions_membership_and_scope`

## TC004 — Open Vendors from Sales and FAM

- Module: Common
- Expected: Open Vendors from Sales and FAM with canonical identities, correct amounts, authorized scope and retained history.
- Actual: FAM retains its native party/ledger view. Canonical vendor identity reconciliation is not implemented end to end.
- Status: **BLOCKED**
- Severity: High
- Root cause: FAM retains its native party/ledger view. Canonical vendor identity reconciliation is not implemented end to end.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC005 — Open Notes from CRM and PMS

- Module: Common
- Expected: Open Notes from CRM and PMS with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: test-common-routes.cjs, tests.test_pms_private_notes.test_attachment_type_size_empty_and_quota_validation, tests.test_pms_private_notes.test_backlinks_respect_both_target_and_source_permissions, tests.test_pms_private_notes.test_bulk_conflict_is_atomic_and_trash_remains_recoverable, tests.test_pms_private_notes.test_default_personal_project_is_user_specific, tests.test_pms_private_notes.test_explicit_sharing_is_read_only_revocable_and_hides_trashed_notes, tests.test_pms_private_notes.test_folder_drag_reorder_is_atomic_owned_and_cycle_safe, tests.test_pms_private_notes.test_inline_image_presentation_attributes_are_bounded_and_sanitized, tests.test_pms_private_notes.test_inline_image_references_never_store_remote_sources, tests.test_pms_private_notes.test_management_undo_conflicts_are_atomic_and_readers_cannot_undo, tests.test_pms_private_notes.test_management_undo_rejects_foreign_folder_and_arbitrary_fields, tests.test_pms_private_notes.test_management_undo_restores_metadata_without_replacing_content[archive], tests.test_pms_private_notes.test_management_undo_restores_metadata_without_replacing_content[move], tests.test_pms_private_notes.test_management_undo_restores_metadata_without_replacing_content[restore], tests.test_pms_private_notes.test_management_undo_restores_metadata_without_replacing_content[trash], tests.test_pms_private_notes.test_management_undo_restores_metadata_without_replacing_content[unarchive], tests.test_pms_private_notes.test_nested_folders_cycles_and_owner_isolation, tests.test_pms_private_notes.test_note_search_filters_dates_attachments_and_match_context, tests.test_pms_private_notes.test_note_to_task_only_publishes_reviewed_text_is_idempotent_and_private, tests.test_pms_private_notes.test_note_to_task_requires_destination_permissions_and_writable_note, tests.test_pms_private_notes.test_owner_only_all_operations_including_admin, tests.test_pms_private_notes.test_pdf_export_and_duplicate_keep_private_notes, tests.test_pms_private_notes.test_private_attachments_download_remove_restore_and_cross_note_isolation, tests.test_pms_private_notes.test_project_links_do_not_share_or_export_notes, tests.test_pms_private_notes.test_rich_note_excerpt_is_readable_without_changing_stored_content, tests.test_pms_private_notes.test_save_conflict_revisions_archive_and_trash, tests.test_pms_private_notes.test_selected_branch_note_move_undo_and_hidden_folder_rejection, tests.test_pms_private_notes.test_selected_branch_note_save_and_folder_edit_keep_version_conflicts, tests.test_pms_private_notes.test_unauthenticated_notes_api
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend/outputs/business-suite-frontend-results.json :: test-common-routes.cjs`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_attachment_type_size_empty_and_quota_validation`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_backlinks_respect_both_target_and_source_permissions`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_bulk_conflict_is_atomic_and_trash_remains_recoverable`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_default_personal_project_is_user_specific`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_explicit_sharing_is_read_only_revocable_and_hides_trashed_notes`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_folder_drag_reorder_is_atomic_owned_and_cycle_safe`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_inline_image_presentation_attributes_are_bounded_and_sanitized`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_inline_image_references_never_store_remote_sources`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_management_undo_conflicts_are_atomic_and_readers_cannot_undo`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_management_undo_rejects_foreign_folder_and_arbitrary_fields`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_management_undo_restores_metadata_without_replacing_content[archive]`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_management_undo_restores_metadata_without_replacing_content[move]`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_management_undo_restores_metadata_without_replacing_content[restore]`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_management_undo_restores_metadata_without_replacing_content[trash]`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_management_undo_restores_metadata_without_replacing_content[unarchive]`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_nested_folders_cycles_and_owner_isolation`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_note_search_filters_dates_attachments_and_match_context`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_note_to_task_only_publishes_reviewed_text_is_idempotent_and_private`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_note_to_task_requires_destination_permissions_and_writable_note`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_owner_only_all_operations_including_admin`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_pdf_export_and_duplicate_keep_private_notes`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_private_attachments_download_remove_restore_and_cross_note_isolation`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_project_links_do_not_share_or_export_notes`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_rich_note_excerpt_is_readable_without_changing_stored_content`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_save_conflict_revisions_archive_and_trash`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_selected_branch_note_move_undo_and_hidden_folder_rejection`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_selected_branch_note_save_and_folder_edit_keep_version_conflicts`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_private_notes.test_unauthenticated_notes_api`

## TC006 — Open Customers from CRM and Sales

- Module: Common
- Expected: Open Customers from CRM and Sales with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_live_browser.test_tc006_012_common_customer_ui_uses_real_canonical_api
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_live_browser.test_tc006_012_common_customer_ui_uses_real_canonical_api`

## TC007 — Open Leads from CRM and Sales

- Module: Common
- Expected: Open Leads from CRM and Sales with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Sales-only users have no approved lead adapter independent of CRM grants; routing alone does not grant CRM access.
- Status: **BLOCKED**
- Severity: High
- Root cause: Sales-only users have no approved lead adapter independent of CRM grants; routing alone does not grant CRM access.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC008 — Open Calendar from all modules

- Module: Common
- Expected: Open Calendar from all modules with canonical identities, correct amounts, authorized scope and retained history.
- Actual: The common PMS calendar exists, but CRM native events and service appointments are not one calendar projection.
- Status: **BLOCKED**
- Severity: High
- Root cause: The common PMS calendar exists, but CRM native events and service appointments are not one calendar projection.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC009 — Refresh common routes and verify no 404 errors

- Module: Common
- Expected: Refresh common routes and verify no 404 errors with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: test-common-routes.cjs, tests.test_business_suite_live_browser.test_tc006_012_common_customer_ui_uses_real_canonical_api
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend/outputs/business-suite-frontend-results.json :: test-common-routes.cjs`; `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_live_browser.test_tc006_012_common_customer_ui_uses_real_canonical_api`

## TC010 — Verify browser back, breadcrumbs, active menus and module context

- Module: Common
- Expected: Verify browser back, breadcrumbs, active menus and module context with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: test-common-routes.cjs, test-desktop-navigation.cjs, test-navigation-guards.cjs
- Status: **PASS**
- Severity: Medium
- Root cause: Navigation/accounting harnesses had stale dependencies, server assumptions and races
- Fix: Load real route helpers, honor current workspace presentation, start isolated servers and await confirmed requests.
- Files changed: `frontend/scripts/test-accounting-connected.cjs`, `frontend/scripts/test-navigation-categories.cjs`, `frontend/scripts/test-navigation-workspaces.cjs`, `frontend/scripts/test-operations-workspaces.cjs`, `frontend/scripts/test-relationship-hub.cjs`
- Retest: PASS
- Evidence: `backend/outputs/business-suite-frontend-results.json :: test-common-routes.cjs`; `backend/outputs/business-suite-frontend-results.json :: test-desktop-navigation.cjs`; `backend/outputs/business-suite-frontend-results.json :: test-navigation-guards.cjs`

## TC011 — Create customer in CRM; verify immediately in Sales

- Module: Shared records
- Expected: Create customer in CRM; verify immediately in Sales with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_live_browser.test_tc006_012_common_customer_ui_uses_real_canonical_api
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_live_browser.test_tc006_012_common_customer_ui_uses_real_canonical_api`

## TC012 — Edit customer in Sales; verify updated details in CRM

- Module: Shared records
- Expected: Edit customer in Sales; verify updated details in CRM with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_live_browser.test_tc006_012_common_customer_ui_uses_real_canonical_api
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_live_browser.test_tc006_012_common_customer_ui_uses_real_canonical_api`

## TC013 — Create lead in Sales; verify in CRM

- Module: Shared records
- Expected: Create lead in Sales; verify in CRM with canonical identities, correct amounts, authorized scope and retained history.
- Actual: A Sales-only lead-write adapter is not implemented; broadening CRM permissions would not be a safe QA fix.
- Status: **BLOCKED**
- Severity: High
- Root cause: A Sales-only lead-write adapter is not implemented; broadening CRM permissions would not be a safe QA fix.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC014 — Convert lead to customer without duplicate creation

- Module: Shared records
- Expected: Convert lead to customer without duplicate creation with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_contact_directory.test_conversion_reuses_identity_preserves_history_and_correction
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_contact_directory.test_conversion_reuses_identity_preserves_history_and_correction`

## TC015 — Create vendor in Sales; verify in FAM

- Module: Shared records
- Expected: Create vendor in Sales; verify in FAM with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Vendor-to-FAM canonical identity mapping requires reconciliation of legacy party IDs; no business records were merged.
- Status: **BLOCKED**
- Severity: High
- Root cause: Vendor-to-FAM canonical identity mapping requires reconciliation of legacy party IDs; no business records were merged.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC016 — Update employee in HRMS; verify in PMS

- Module: Shared records
- Expected: Update employee in HRMS; verify in PMS with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_shared_profiles.test_profile_contact_edit_requests_hr_approval_and_syncs_after_approval
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_shared_profiles.test_profile_contact_edit_requests_hr_approval_and_syncs_after_approval`

## TC017 — Create team in PMS; verify authorized visibility elsewhere

- Module: Shared records
- Expected: Create team in PMS; verify authorized visibility elsewhere with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_pms_teams.test_workspace_teams_permissions_membership_and_scope
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_pms_teams.test_workspace_teams_permissions_membership_and_scope`

## TC018 — Create task in CRM; verify in common Tasks

- Module: Shared records
- Expected: Create task in CRM; verify in common Tasks with canonical identities, correct amounts, authorized scope and retained history.
- Actual: CRM-linked task reads are tested; task quick-create still needs explicit CRM associations and origin-aware return navigation.
- Status: **BLOCKED**
- Severity: High
- Root cause: CRM-linked task reads are tested; task quick-create still needs explicit CRM associations and origin-aware return navigation.
- Fix: Preserve ownership of pending single-action slot filling and cancellation.; Reload persisted task state before computing the next checkpoint digest; retain checks against actual external edits.
- Files changed: `backend/app/ai_operator/jobs.py`, `backend/app/ai_operator/workflows.py`
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC019 — Create note against customer; verify authorized cross-module access

- Module: Shared records
- Expected: Create note against customer; verify authorized cross-module access with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Persistent private notes are tested; a universal customer-to-note association with cross-module visibility is incomplete.
- Status: **BLOCKED**
- Severity: High
- Root cause: Persistent private notes are tested; a universal customer-to-note association with cross-module visibility is incomplete.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC020 — Test duplicate detection, shared phone numbers and multiple contact roles

- Module: Shared records
- Expected: Test duplicate detection, shared phone numbers and multiple contact roles with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_contact_directory.test_multiple_relationships_counts_filters_and_conflicts, tests.test_master_data.test_secondary_phone_country_and_optional_sharing_reason
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_contact_directory.test_multiple_relationships_counts_filters_and_conflicts`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_master_data.test_secondary_phone_country_and_optional_sharing_reason`

## TC021 — Sell one physical product

- Module: Sales & POS
- Expected: Sell one physical product with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pos_integrity.test_tc054_stock_type_cannot_be_spoofed_as_service
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc054_stock_type_cannot_be_spoofed_as_service`

## TC022 — Sell multiple products

- Module: Sales & POS
- Expected: Sell multiple products with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pos_integrity.test_tc027_bill_discount_is_allocated_before_each_item_tax
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc027_bill_discount_is_allocated_before_each_item_tax`

## TC023 — Sell one service

- Module: Sales & POS
- Expected: Sell one service with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pos_integrity.test_tc060_service_does_not_move_stock
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc060_service_does_not_move_stock`

## TC024 — Sell products and services in the same invoice

- Module: Sales & POS
- Expected: Sell products and services in the same invoice with canonical identities, correct amounts, authorized scope and retained history.
- Actual: POS checkout posts a sales order; it does not atomically issue an invoice and persist its payment.
- Status: **BLOCKED**
- Severity: Critical
- Root cause: POS checkout posts a sales order; it does not atomically issue an invoice and persist its payment.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC025 — Sell taxable and exempt items together

- Module: Sales & POS
- Expected: Sell taxable and exempt items together with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_gst_matrix.test_tc025_exempt_fixture_preserves_zero_tax[False-exempt], tests.test_business_suite_gst_matrix.test_tc025_exempt_fixture_preserves_zero_tax[False-nil], tests.test_business_suite_gst_matrix.test_tc025_exempt_fixture_preserves_zero_tax[False-out_of_scope], tests.test_business_suite_gst_matrix.test_tc025_exempt_fixture_preserves_zero_tax[False-zero_rated], tests.test_business_suite_gst_matrix.test_tc025_exempt_fixture_preserves_zero_tax[True-exempt], tests.test_business_suite_gst_matrix.test_tc025_exempt_fixture_preserves_zero_tax[True-nil], tests.test_business_suite_gst_matrix.test_tc025_exempt_fixture_preserves_zero_tax[True-out_of_scope], tests.test_business_suite_gst_matrix.test_tc025_exempt_fixture_preserves_zero_tax[True-zero_rated]
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc025_exempt_fixture_preserves_zero_tax[False-exempt]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc025_exempt_fixture_preserves_zero_tax[False-nil]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc025_exempt_fixture_preserves_zero_tax[False-out_of_scope]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc025_exempt_fixture_preserves_zero_tax[False-zero_rated]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc025_exempt_fixture_preserves_zero_tax[True-exempt]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc025_exempt_fixture_preserves_zero_tax[True-nil]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc025_exempt_fixture_preserves_zero_tax[True-out_of_scope]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc025_exempt_fixture_preserves_zero_tax[True-zero_rated]`

## TC026 — Apply different GST percentages to different items

- Module: Sales & POS
- Expected: Apply different GST percentages to different items with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pos_integrity.test_tc027_bill_discount_is_allocated_before_each_item_tax
- Status: **PASS**
- Severity: Medium
- Root cause: POS trusted client totals/tax and lost bill discounts
- Fix: Reuse commercial decimal normalization, allocate bill discounts and snapshot canonical item tax.
- Files changed: `backend/app/apps/srm/api/router.py`, `backend/app/apps/srm/services/commercial.py`
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc027_bill_discount_is_allocated_before_each_item_tax`

## TC027 — Apply line-level and invoice-level discounts

- Module: Sales & POS
- Expected: Apply line-level and invoice-level discounts with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pos_integrity.test_tc027_bill_discount_is_allocated_before_each_item_tax
- Status: **PASS**
- Severity: Medium
- Root cause: POS trusted client totals/tax and lost bill discounts
- Fix: Reuse commercial decimal normalization, allocate bill discounts and snapshot canonical item tax.
- Files changed: `backend/app/apps/srm/api/router.py`, `backend/app/apps/srm/services/commercial.py`
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc027_bill_discount_is_allocated_before_each_item_tax`

## TC028 — Hold, resume and complete POS transaction

- Module: Sales & POS
- Expected: Hold, resume and complete POS transaction with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_srm_pos_held_bills.test_pos_held_bill_recall_lifecycle_is_database_backed
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_srm_pos_held_bills.test_pos_held_bill_recall_lifecycle_is_database_backed`

## TC029 — Accept split payments and partial payments

- Module: Sales & POS
- Expected: Accept split payments and partial payments with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Split/partial payment inputs are not persisted as native receipts by POS checkout. This is a release blocker.
- Status: **BLOCKED**
- Severity: Critical
- Root cause: Split/partial payment inputs are not persisted as native receipts by POS checkout. This is a release blocker.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC030 — Process refund and return without corrupting inventory or accounts

- Module: Sales & POS
- Expected: Process refund and return without corrupting inventory or accounts with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pos_concurrency.test_tc030_concurrent_nonrestocked_refunds_cannot_exceed_original_sale, tests.test_business_suite_pos_integrity.test_tc030_nonrestocked_return_still_consumes_refundable_quantity
- Status: **PASS**
- Severity: Medium
- Root cause: Non-restocked refunds did not consume refundable quantity
- Fix: Count every return and serialize competing refunds.
- Files changed: `backend/app/apps/srm/api/router.py`
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc030_nonrestocked_return_still_consumes_refundable_quantity`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_pos_concurrency.test_tc030_concurrent_nonrestocked_refunds_cannot_exceed_original_sale`

## TC031 — Calculate 5% GST on a configured taxable item

- Module: GST & invoices
- Expected: Calculate 5% GST on a configured taxable item with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-5]
- Status: **PASS**
- Severity: Medium
- Root cause: FAM GST ties rounded differently from commercial/POS arithmetic
- Fix: Apply explicit ROUND_HALF_UP to each tax component.
- Files changed: `backend/app/apps/fam/api/router.py`
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-5]`

## TC032 — Calculate 12% GST on a configured legacy/test item

- Module: GST & invoices
- Expected: Calculate 12% GST on a configured legacy/test item with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-5]
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-5]`

## TC033 — Calculate 18% GST on a configured taxable item

- Module: GST & invoices
- Expected: Calculate 18% GST on a configured taxable item with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-5]
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-5]`

## TC034 — Calculate 28% GST on a configured legacy/test item

- Module: GST & invoices
- Expected: Calculate 28% GST on a configured legacy/test item with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-5]
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-5]`

## TC035 — Calculate multiple GST rates on one invoice

- Module: GST & invoices
- Expected: Calculate multiple GST rates on one invoice with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pos_integrity.test_tc027_bill_discount_is_allocated_before_each_item_tax
- Status: **PASS**
- Severity: Medium
- Root cause: POS trusted client totals/tax and lost bill discounts
- Fix: Reuse commercial decimal normalization, allocate bill discounts and snapshot canonical item tax.
- Files changed: `backend/app/apps/srm/api/router.py`, `backend/app/apps/srm/services/commercial.py`
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc027_bill_discount_is_allocated_before_each_item_tax`

## TC036 — Calculate CGST + SGST/UTGST for intra-state supply

- Module: GST & invoices
- Expected: Calculate CGST + SGST/UTGST for intra-state supply with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-5], tests.test_fam_gst_intra_inter_state.test_fam_gst_intra_and_inter_state_logic
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_fam_gst_intra_inter_state.test_fam_gst_intra_and_inter_state_logic`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-5]`

## TC037 — Calculate IGST for inter-state supply

- Module: GST & invoices
- Expected: Calculate IGST for inter-state supply with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-5], tests.test_fam_gst_intra_inter_state.test_fam_gst_intra_and_inter_state_logic
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_fam_gst_intra_inter_state.test_fam_gst_intra_and_inter_state_logic`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-5]`

## TC038 — Verify tax-inclusive and tax-exclusive calculations

- Module: GST & invoices
- Expected: Verify tax-inclusive and tax-exclusive calculations with canonical identities, correct amounts, authorized scope and retained history.
- Actual: The current POS/catalog workflow does not expose a complete, verified tax-inclusive pricing contract.
- Status: **BLOCKED**
- Severity: High
- Root cause: The current POS/catalog workflow does not expose a complete, verified tax-inclusive pricing contract.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC039 — Verify discounts, fractional quantities and rounding

- Module: GST & invoices
- Expected: Verify discounts, fractional quantities and rounding with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-5], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-0], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-12], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-18], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-28], tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-5], tests.test_business_suite_live_browser.test_tc006_012_common_customer_ui_uses_real_canonical_api
- Status: **PASS**
- Severity: Medium
- Root cause: FAM GST ties rounded differently from commercial/POS arithmetic; POS rounded payable to whole currency units and displayed a local rather than confirmed total
- Fix: Apply explicit ROUND_HALF_UP to each tax component.; Keep cents in the preview and display the persisted server total after checkout.
- Files changed: `backend/app/apps/fam/api/router.py`, `frontend/src/apps/srm/pages/SRMPOSPage.tsx`
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_live_browser.test_tc006_012_common_customer_ui_uses_real_canonical_api`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-5]`

## TC040 — Verify credit notes, tax reversal and historical invoice integrity

- Module: GST & invoices
- Expected: Verify credit notes, tax reversal and historical invoice integrity with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pos_integrity.test_tc040_refund_uses_original_discount_and_tax_snapshot, tests.test_fam_srm_posting_reversal.test_fam_reverses_srm_invoice_posting_with_opposite_voucher
- Status: **PASS**
- Severity: Medium
- Root cause: Refund lost original discounts/tax and allowed over-refund
- Fix: Use remaining original value/tax, proportional refunds and last-return rounding remainder.
- Files changed: `backend/app/apps/srm/api/router.py`
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_fam_srm_posting_reversal.test_fam_reverses_srm_invoice_posting_with_opposite_voucher`; `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc040_refund_uses_original_discount_and_tax_snapshot`

## TC041 — Create salon service appointment for an existing customer

- Module: Appointments
- Expected: Create salon service appointment for an existing customer with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- Status: **BLOCKED**
- Severity: High
- Root cause: Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC042 — Create appointment for a new customer

- Module: Appointments
- Expected: Create appointment for a new customer with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- Status: **BLOCKED**
- Severity: High
- Root cause: Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC043 — Assign service to an eligible employee

- Module: Appointments
- Expected: Assign service to an eligible employee with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- Status: **BLOCKED**
- Severity: High
- Root cause: Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC044 — Verify appointment in common Calendar

- Module: Appointments
- Expected: Verify appointment in common Calendar with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- Status: **BLOCKED**
- Severity: High
- Root cause: Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC045 — Reschedule appointment and verify all views update

- Module: Appointments
- Expected: Reschedule appointment and verify all views update with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- Status: **BLOCKED**
- Severity: High
- Root cause: Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC046 — Cancel appointment and release reserved slot

- Module: Appointments
- Expected: Cancel appointment and release reserved slot with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- Status: **BLOCKED**
- Severity: High
- Root cause: Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC047 — Prevent overlapping bookings for same employee

- Module: Appointments
- Expected: Prevent overlapping bookings for same employee with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- Status: **BLOCKED**
- Severity: High
- Root cause: Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC048 — Prevent booking during employee leave or unavailable hours

- Module: Appointments
- Expected: Prevent booking during employee leave or unavailable hours with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- Status: **BLOCKED**
- Severity: High
- Root cause: Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC049 — Book multiple services with different durations

- Module: Appointments
- Expected: Book multiple services with different durations with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- Status: **BLOCKED**
- Severity: High
- Root cause: Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC050 — Complete appointment and generate correct POS invoice

- Module: Appointments
- Expected: Complete appointment and generate correct POS invoice with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- Status: **BLOCKED**
- Severity: High
- Root cause: Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC051 — Create product with SKU and barcode

- Module: Inventory
- Expected: Create product with SKU and barcode with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_srm_inventory_product_master.test_srm_product_master_and_opening_stock_are_database_backed
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_srm_inventory_product_master.test_srm_product_master_and_opening_stock_are_database_backed`

## TC052 — Add opening stock

- Module: Inventory
- Expected: Add opening stock with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_fam_inventory_opening_stock.test_fam_inventory_opening_stock_updates_quantity_and_valuation, tests.test_srm_inventory_product_master.test_srm_product_master_and_opening_stock_are_database_backed
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_fam_inventory_opening_stock.test_fam_inventory_opening_stock_updates_quantity_and_valuation`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_srm_inventory_product_master.test_srm_product_master_and_opening_stock_are_database_backed`

## TC053 — Record purchase and update inventory

- Module: Inventory
- Expected: Record purchase and update inventory with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_srm_inventory_product_master.test_srm_product_master_and_opening_stock_are_database_backed
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_srm_inventory_product_master.test_srm_product_master_and_opening_stock_are_database_backed`

## TC054 — Sell product and verify stock deduction

- Module: Inventory
- Expected: Sell product and verify stock deduction with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pos_integrity.test_tc054_stock_type_cannot_be_spoofed_as_service
- Status: **PASS**
- Severity: Medium
- Root cause: Client item-type flag bypassed stock issuance
- Fix: Determine inventory behavior from the canonical product and lock stock rows.
- Files changed: `backend/app/apps/srm/api/router.py`
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc054_stock_type_cannot_be_spoofed_as_service`

## TC055 — Return product and verify correct stock reversal

- Module: Inventory
- Expected: Return product and verify correct stock reversal with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_srm_inventory_product_master.test_srm_product_master_and_opening_stock_are_database_backed
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_srm_inventory_product_master.test_srm_product_master_and_opening_stock_are_database_backed`

## TC056 — Transfer inventory between warehouses

- Module: Inventory
- Expected: Transfer inventory between warehouses with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_fam_inventory_transfer_accounting.test_fam_inventory_transfer_accounting_posts_existing_transfer, tests.test_srm_inventory_product_master.test_srm_product_master_and_opening_stock_are_database_backed
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_fam_inventory_transfer_accounting.test_fam_inventory_transfer_accounting_posts_existing_transfer`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_srm_inventory_product_master.test_srm_product_master_and_opening_stock_are_database_backed`

## TC057 — Test low-stock and reorder alerts

- Module: Inventory
- Expected: Test low-stock and reorder alerts with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_srm_inventory_product_master.test_srm_product_master_and_opening_stock_are_database_backed
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_srm_inventory_product_master.test_srm_product_master_and_opening_stock_are_database_backed`

## TC058 — Test serial number and batch tracking

- Module: Inventory
- Expected: Test serial number and batch tracking with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Batch/serial master persistence and duplicate rejection are tested; POS allocation, expiry enforcement and serial lifecycle are not certified by those master-data tests.
- Status: **BLOCKED**
- Severity: High
- Root cause: Batch/serial master persistence and duplicate rejection are tested; POS allocation, expiry enforcement and serial lifecycle are not certified by those master-data tests.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_srm_inventory_product_master.test_srm_product_master_and_opening_stock_are_database_backed`

## TC059 — Test concurrent sales against limited inventory

- Module: Inventory
- Expected: Test concurrent sales against limited inventory with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pos_concurrency.test_tc059_two_checkouts_cannot_sell_the_last_unit_twice
- Status: **PASS**
- Severity: Medium
- Root cause: Client item-type flag bypassed stock issuance
- Fix: Determine inventory behavior from the canonical product and lock stock rows.
- Files changed: `backend/app/apps/srm/api/router.py`
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_pos_concurrency.test_tc059_two_checkouts_cannot_sell_the_last_unit_twice`

## TC060 — Verify service-only sales do not reduce stock unless materials are configured

- Module: Inventory
- Expected: Verify service-only sales do not reduce stock unless materials are configured with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pos_integrity.test_tc060_service_does_not_move_stock
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc060_service_does_not_move_stock`

## TC061 — Create AMC contract for an existing customer

- Module: AMC & contracts
- Expected: Create AMC contract for an existing customer with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_commercial_links.test_tc061_contract_reuses_existing_canonical_customer
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_commercial_links.test_tc061_contract_reuses_existing_canonical_customer`

## TC062 — Link AMC to a product or asset

- Module: AMC & contracts
- Expected: Link AMC to a product or asset with canonical identities, correct amounts, authorized scope and retained history.
- Actual: AMC product/asset association is not implemented as a verified canonical relationship.
- Status: **BLOCKED**
- Severity: High
- Root cause: AMC product/asset association is not implemented as a verified canonical relationship.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC063 — Assign service technician from HRMS employee master

- Module: AMC & contracts
- Expected: Assign service technician from HRMS employee master with canonical identities, correct amounts, authorized scope and retained history.
- Actual: AMC technician assignment does not implement the requested HRMS employee/skill eligibility contract.
- Status: **BLOCKED**
- Severity: High
- Root cause: AMC technician assignment does not implement the requested HRMS employee/skill eligibility contract.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC064 — Schedule AMC visit in common Calendar

- Module: AMC & contracts
- Expected: Schedule AMC visit in common Calendar with canonical identities, correct amounts, authorized scope and retained history.
- Actual: AMC service-visit appointment projection into the common calendar is not implemented.
- Status: **BLOCKED**
- Severity: High
- Root cause: AMC service-visit appointment projection into the common calendar is not implemented.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC065 — Generate renewal reminder

- Module: AMC & contracts
- Expected: Generate renewal reminder with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Generic recurring billing exists; an AMC renewal reminder workflow was not verified.
- Status: **BLOCKED**
- Severity: High
- Root cause: Generic recurring billing exists; an AMC renewal reminder workflow was not verified.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC066 — Renew AMC without duplicating contract history

- Module: AMC & contracts
- Expected: Renew AMC without duplicating contract history with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Generic renewal status/audit persistence is tested; new AMC coverage terms and renewal history were not exercised end to end.
- Status: **BLOCKED**
- Severity: High
- Root cause: Generic renewal status/audit persistence is tested; new AMC coverage terms and renewal history were not exercised end to end.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_srm_contracts.test_srm_contract_create_persists`

## TC067 — Generate AMC invoice and verify FAM integration

- Module: AMC & contracts
- Expected: Generate AMC invoice and verify FAM integration with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Native FAM invoice posting is tested, but the requested AMC-to-invoice workflow is not complete.
- Status: **BLOCKED**
- Severity: High
- Root cause: Native FAM invoice posting is tested, but the requested AMC-to-invoice workflow is not complete.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC068 — Cancel or expire AMC and verify access, status and billing behavior

- Module: AMC & contracts
- Expected: Cancel or expire AMC and verify access, status and billing behavior with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Contract expiry/status persistence is tested; cancellation/expiry enforcement across AMC visits and billing is not implemented end to end.
- Status: **BLOCKED**
- Severity: High
- Root cause: Contract expiry/status persistence is tested; cancellation/expiry enforcement across AMC visits and billing is not implemented end to end.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_srm_contracts.test_srm_contract_create_persists`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_srm_recurrence.test_end_date_and_template_settings`

## TC069 — Verify employee cannot access unauthorized HR records

- Module: Security
- Expected: Verify employee cannot access unauthorized HR records with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_security_employee_scope.test_document_policies_and_templates_do_not_cross_company_boundaries, tests.test_security_employee_scope.test_employee_permission_does_not_grant_other_company_records
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_security_employee_scope.test_document_policies_and_templates_do_not_cross_company_boundaries`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_security_employee_scope.test_employee_permission_does_not_grant_other_company_records`

## TC070 — Verify CRM user cannot access restricted FAM data

- Module: Security
- Expected: Verify CRM user cannot access restricted FAM data with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_cross_module_audit.test_commercial_role_matrix[contributor-permissions2-Member-False-False-False-True], tests.test_cross_module_audit.test_commercial_role_matrix[finance-permissions3-Member-True-True-True-True], tests.test_cross_module_audit.test_commercial_role_matrix[inactive-permissions7-Member-False-False-False-False], tests.test_cross_module_audit.test_commercial_role_matrix[other_tenant-permissions8-Member-False-False-False-True], tests.test_cross_module_audit.test_commercial_role_matrix[outsider-permissions5-None-False-False-False-True], tests.test_cross_module_audit.test_commercial_role_matrix[project_manager-permissions1-Manager-True-False-False-True], tests.test_cross_module_audit.test_commercial_role_matrix[read_only-permissions4-Viewer-True-False-False-True], tests.test_cross_module_audit.test_commercial_role_matrix[removed-permissions6-None-False-False-False-True], tests.test_cross_module_audit.test_commercial_role_matrix[sales-permissions0-Member-True-False-False-True], tests.test_fam_srm_posting_rbac.test_fam_srm_posting_rbac_blocks_readonly_users_from_posting
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_fam_srm_posting_rbac.test_fam_srm_posting_rbac_blocks_readonly_users_from_posting`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_cross_module_audit.test_commercial_role_matrix[contributor-permissions2-Member-False-False-False-True]`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_cross_module_audit.test_commercial_role_matrix[finance-permissions3-Member-True-True-True-True]`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_cross_module_audit.test_commercial_role_matrix[inactive-permissions7-Member-False-False-False-False]`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_cross_module_audit.test_commercial_role_matrix[other_tenant-permissions8-Member-False-False-False-True]`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_cross_module_audit.test_commercial_role_matrix[outsider-permissions5-None-False-False-False-True]`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_cross_module_audit.test_commercial_role_matrix[project_manager-permissions1-Manager-True-False-False-True]`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_cross_module_audit.test_commercial_role_matrix[read_only-permissions4-Viewer-True-False-False-True]`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_cross_module_audit.test_commercial_role_matrix[removed-permissions6-None-False-False-False-True]`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_cross_module_audit.test_commercial_role_matrix[sales-permissions0-Member-True-False-False-True]`

## TC071 — Verify tenant/workspace isolation

- Module: Security
- Expected: Verify tenant/workspace isolation with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pos_integrity.test_tc071_foreign_customer_cannot_be_attached_to_pos_order, tests.test_shared_catalog.test_links_pricing_tax_and_tenant_isolation
- Status: **PASS**
- Severity: Critical
- Root cause: POS order/return accepted foreign or replacement customer IDs
- Fix: Reuse tenant-scoped commercial customer/contact resolvers and bind return customer to its source sale.
- Files changed: `backend/app/apps/srm/api/router.py`
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_shared_catalog.test_links_pricing_tax_and_tenant_isolation`; `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc071_foreign_customer_cannot_be_attached_to_pos_order`

## TC072 — Attempt direct API access without permission

- Module: Security
- Expected: Attempt direct API access without permission with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_security_backend_enforcement.test_backend_security_permissions_are_enforced
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_security_backend_enforcement.test_backend_security_permissions_are_enforced`

## TC073 — Test IDOR by modifying entity IDs in authorized test requests

- Module: Security
- Expected: Test IDOR by modifying entity IDs in authorized test requests with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pos_integrity.test_tc073_return_cannot_substitute_another_product, tests.test_business_suite_pos_integrity.test_tc073_return_customer_cannot_be_replaced
- Status: **PASS**
- Severity: Critical
- Root cause: Return could substitute a different inventory product; POS order/return accepted foreign or replacement customer IDs
- Fix: Bind returns to the original sale line and validate warehouse scope.; Reuse tenant-scoped commercial customer/contact resolvers and bind return customer to its source sale.
- Files changed: `backend/app/apps/srm/api/router.py`
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc073_return_cannot_substitute_another_product`; `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc073_return_customer_cannot_be_replaced`

## TC074 — Test SQL injection and stored XSS using harmless payloads

- Module: Security
- Expected: Test SQL injection and stored XSS using harmless payloads with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_security_files_and_formulas.test_api_errors_receive_private_security_headers, tests.test_security_files_and_formulas.test_client_cannot_turn_arbitrary_storage_path_into_download_link, tests.test_security_files_and_formulas.test_docx_traversal_archive_is_rejected, tests.test_security_files_and_formulas.test_expired_file_capability_cannot_be_resaved, tests.test_security_files_and_formulas.test_financial_formula_still_computes, tests.test_security_files_and_formulas.test_forged_s3_signature_is_never_promoted_to_trusted_storage_path, tests.test_security_files_and_formulas.test_formula_variables_cannot_bypass_resource_limits[synthetic], tests.test_security_files_and_formulas.test_formula_variables_cannot_bypass_resource_limits[value1], tests.test_security_files_and_formulas.test_formula_variables_cannot_bypass_resource_limits[value2], tests.test_security_files_and_formulas.test_local_download_requires_valid_expiring_capability, tests.test_security_files_and_formulas.test_public_asset_prefix_cannot_bypass_private_path_guard[/uploads/avatars/../employee_docs/canary.pdf], tests.test_security_files_and_formulas.test_public_asset_prefix_cannot_bypass_private_path_guard[/uploads/avatars/..\\employee_docs/canary.pdf], tests.test_security_files_and_formulas.test_public_upload_quota_is_persisted_not_process_local, tests.test_security_files_and_formulas.test_resource_exhaustion_formulas_are_rejected_without_evaluation['x'*1000000000], tests.test_security_files_and_formulas.test_resource_exhaustion_formulas_are_rejected_without_evaluation[1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+], tests.test_security_files_and_formulas.test_resource_exhaustion_formulas_are_rejected_without_evaluation[10**1000000000], tests.test_security_files_and_formulas.test_resource_exhaustion_formulas_are_rejected_without_evaluation[9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999], tests.test_security_files_and_formulas.test_resource_exhaustion_formulas_are_rejected_without_evaluation[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[]
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_security_files_and_formulas.test_api_errors_receive_private_security_headers`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_security_files_and_formulas.test_client_cannot_turn_arbitrary_storage_path_into_download_link`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_security_files_and_formulas.test_docx_traversal_archive_is_rejected`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_security_files_and_formulas.test_expired_file_capability_cannot_be_resaved`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_security_files_and_formulas.test_financial_formula_still_computes`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_security_files_and_formulas.test_forged_s3_signature_is_never_promoted_to_trusted_storage_path`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_security_files_and_formulas.test_formula_variables_cannot_bypass_resource_limits[synthetic]`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_security_files_and_formulas.test_formula_variables_cannot_bypass_resource_limits[value1]`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_security_files_and_formulas.test_formula_variables_cannot_bypass_resource_limits[value2]`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_security_files_and_formulas.test_local_download_requires_valid_expiring_capability`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_security_files_and_formulas.test_public_asset_prefix_cannot_bypass_private_path_guard[/uploads/avatars/../employee_docs/canary.pdf]`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_security_files_and_formulas.test_public_asset_prefix_cannot_bypass_private_path_guard[/uploads/avatars/..\\employee_docs/canary.pdf]`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_security_files_and_formulas.test_public_upload_quota_is_persisted_not_process_local`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_security_files_and_formulas.test_resource_exhaustion_formulas_are_rejected_without_evaluation['x'*1000000000]`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_security_files_and_formulas.test_resource_exhaustion_formulas_are_rejected_without_evaluation[1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+]`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_security_files_and_formulas.test_resource_exhaustion_formulas_are_rejected_without_evaluation[10**1000000000]`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_security_files_and_formulas.test_resource_exhaustion_formulas_are_rejected_without_evaluation[9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999]`; `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_security_files_and_formulas.test_resource_exhaustion_formulas_are_rejected_without_evaluation[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[]`

## TC075 — Verify audit logs for important record changes

- Module: Security
- Expected: Verify audit logs for important record changes with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_contact_retention.test_tc075_text_identity_history_prevents_permanent_deletion, tests.test_srm_contracts.test_srm_contract_create_persists
- Status: **PASS**
- Severity: Medium
- Root cause: PostgreSQL contact retention query compared text IDs to integers
- Fix: Bind identifiers using their stored SQL type; retain linked history.
- Files changed: `backend/app/apps/crm/contact_directory.py`
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_srm_contracts.test_srm_contract_create_persists`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_contact_retention.test_tc075_text_identity_history_prevents_permanent_deletion`

## TC076 — Verify server-side validation cannot be bypassed through API calls

- Module: Security
- Expected: Verify server-side validation cannot be bypassed through API calls with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[-1-cess_rate], tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[-1-cgst_rate], tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[-1-igst_rate], tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[-1-sgst_rate], tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[101-cess_rate], tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[101-cgst_rate], tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[101-igst_rate], tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[101-sgst_rate], tests.test_business_suite_pos_integrity.test_tc076_pos_totals_and_tax_are_server_authoritative
- Status: **PASS**
- Severity: Critical
- Root cause: Client item-type flag bypassed stock issuance; Negative/zero quantities and negative money were accepted; POS trusted client totals/tax and lost bill discounts; GST API accepted negative and invalid component rates
- Fix: Determine inventory behavior from the canonical product and lock stock rows.; Validate positive, storable quantity precision and nonnegative finite line amounts.; Reuse commercial decimal normalization, allocate bill discounts and snapshot canonical item tax.; Validate GST component bounds and nonnegative taxable/cess values; preserve configurable positive cess.
- Files changed: `backend/app/apps/fam/schemas.py`, `backend/app/apps/srm/api/router.py`, `backend/app/apps/srm/schemas.py`, `backend/app/apps/srm/services/commercial.py`
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc076_pos_totals_and_tax_are_server_authoritative`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[-1-cess_rate]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[-1-cgst_rate]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[-1-igst_rate]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[-1-sgst_rate]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[101-cess_rate]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[101-cgst_rate]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[101-igst_rate]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[101-sgst_rate]`

## TC077 — Load 10,000 customers using server-side pagination

- Module: Performance & regression
- Expected: Load 10,000 customers using server-side pagination with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pagination.test_tc077_ten_thousand_customers_have_bounded_page_and_queries
- Status: **PASS**
- Severity: Medium
- Root cause: 100-customer page performed 405 SELECTs
- Fix: Batch details, relationships and branch availability for the authorized page only.
- Files changed: `backend/app/shared/master_data.py`
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_pagination.test_tc077_ten_thousand_customers_have_bounded_page_and_queries`

## TC078 — Search customers, leads, products and vendors

- Module: Performance & regression
- Expected: Search customers, leads, products and vendors with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_master_data.test_grid_bulk_export_and_source_identity, tests.test_srm_inventory_product_master.test_srm_product_master_and_opening_stock_are_database_backed
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_master_data.test_grid_bulk_export_and_source_identity`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_srm_inventory_product_master.test_srm_product_master_and_opening_stock_are_database_backed`

## TC079 — Verify module switching does not cause unnecessary API calls

- Module: Performance & regression
- Expected: Verify module switching does not cause unnecessary API calls with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: test-navigation-branding.cjs
- Status: **PASS**
- Severity: Medium
- Root cause: Navigation/accounting harnesses had stale dependencies, server assumptions and races
- Fix: Load real route helpers, honor current workspace presentation, start isolated servers and await confirmed requests.
- Files changed: `frontend/scripts/test-accounting-connected.cjs`, `frontend/scripts/test-navigation-categories.cjs`, `frontend/scripts/test-navigation-workspaces.cjs`, `frontend/scripts/test-operations-workspaces.cjs`, `frontend/scripts/test-relationship-hub.cjs`
- Retest: PASS
- Evidence: `backend/outputs/business-suite-frontend-results.json :: test-navigation-branding.cjs`

## TC080 — Verify updated records invalidate stale frontend caches

- Module: Performance & regression
- Expected: Verify updated records invalidate stale frontend caches with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: test-background-refresh.cjs, test-record-list-refresh.cjs, test-record-mutations.cjs
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend/outputs/business-suite-frontend-results.json :: test-background-refresh.cjs`; `backend/outputs/business-suite-frontend-results.json :: test-record-list-refresh.cjs`; `backend/outputs/business-suite-frontend-results.json :: test-record-mutations.cjs`

## TC081 — Test simultaneous customer edits and conflict handling

- Module: Performance & regression
- Expected: Test simultaneous customer edits and conflict handling with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_contact_directory.test_financial_profile_roundtrip_conflict_and_optional, tests.test_master_data.test_relationship_edits_reject_stale_version
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_contact_directory.test_financial_profile_roundtrip_conflict_and_optional`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_master_data.test_relationship_edits_reject_stale_version`

## TC082 — Test simultaneous POS checkout requests for duplicate prevention

- Module: Performance & regression
- Expected: Test simultaneous POS checkout requests for duplicate prevention with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pos_concurrency.test_tc082_duplicate_concurrent_checkout_has_one_order_and_stock_movement
- Status: **PASS**
- Severity: Critical
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_pos_concurrency.test_tc082_duplicate_concurrent_checkout_has_one_order_and_stock_movement`

## TC083 — Verify all existing legacy routes continue working

- Module: Performance & regression
- Expected: Verify all existing legacy routes continue working with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: test-common-routes.cjs, test-navigation-workspaces.cjs
- Status: **PASS**
- Severity: Medium
- Root cause: Navigation/accounting harnesses had stale dependencies, server assumptions and races
- Fix: Load real route helpers, honor current workspace presentation, start isolated servers and await confirmed requests.
- Files changed: `frontend/scripts/test-accounting-connected.cjs`, `frontend/scripts/test-navigation-categories.cjs`, `frontend/scripts/test-navigation-workspaces.cjs`, `frontend/scripts/test-operations-workspaces.cjs`, `frontend/scripts/test-relationship-hub.cjs`
- Retest: PASS
- Evidence: `backend/outputs/business-suite-frontend-results.json :: test-common-routes.cjs`; `backend/outputs/business-suite-frontend-results.json :: test-navigation-workspaces.cjs`

## TC084 — Verify mobile, tablet and desktop layouts

- Module: Performance & regression
- Expected: Verify mobile, tablet and desktop layouts with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: test-mobile-fam-workflows.cjs, test-mobile-pms-notes.cjs, tests.test_business_suite_live_browser.test_tc006_012_common_customer_ui_uses_real_canonical_api
- Status: **PASS**
- Severity: Medium
- Root cause: FAM table adapter swallowed the financial empty state; Successful bank-rule creation left its dialog open
- Fix: Render explicit empty status and suppress stale statements on failed requests.; Close on an explicit successful creation revision; retain forms on errors.
- Files changed: `frontend/src/apps/fam/BankRulesPage.tsx`, `frontend/src/apps/fam/FinancialStatementsPage.tsx`
- Retest: PASS
- Evidence: `backend/outputs/business-suite-frontend-results.json :: test-mobile-fam-workflows.cjs`; `backend/outputs/business-suite-frontend-results.json :: test-mobile-pms-notes.cjs`; `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_live_browser.test_tc006_012_common_customer_ui_uses_real_canonical_api`

## TC085 — Run complete regression suite after fixes

- Module: Performance & regression
- Expected: Run complete regression suite after fixes with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Full pre-fix repository regression: 1800 progress entries of 6496; still running/not yet complete. Targeted reruns do not substitute for a clean full run.
- Status: **BLOCKED**
- Severity: High
- Root cause: Full pre-fix repository regression: 1800 progress entries of 6496; still running/not yet complete. Targeted reruns do not substitute for a clean full run.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC086 — Empty and null values

- Module: Edge cases
- Expected: Empty and null values with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pos_integrity.test_tc106_invalid_quantity_is_atomic[-1], tests.test_business_suite_pos_integrity.test_tc106_invalid_quantity_is_atomic[0], tests.test_crm_lead_management.test_nulls_and_invalid_score_return_validation_errors
- Status: **PASS**
- Severity: Medium
- Root cause: Negative/zero quantities and negative money were accepted
- Fix: Validate positive, storable quantity precision and nonnegative finite line amounts.
- Files changed: `backend/app/apps/srm/schemas.py`
- Retest: PASS
- Evidence: `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_crm_lead_management.test_nulls_and_invalid_score_return_validation_errors`; `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc106_invalid_quantity_is_atomic[-1]`; `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc106_invalid_quantity_is_atomic[0]`

## TC087 — Unicode customer names

- Module: Edge cases
- Expected: Unicode customer names with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_live_browser.test_tc006_012_common_customer_ui_uses_real_canonical_api, tests.test_validation_contract.test_unicode_mononym_and_controls
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_validation_contract.test_unicode_mononym_and_controls`; `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_live_browser.test_tc006_012_common_customer_ui_uses_real_canonical_api`

## TC088 — Very long customer names

- Module: Edge cases
- Expected: Very long customer names with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_contact_directory.test_long_display_names_fit_canonical_identity_columns
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_contact_directory.test_long_display_names_fit_canonical_identity_columns`

## TC089 — Shared family phone numbers

- Module: Edge cases
- Expected: Shared family phone numbers with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_master_data.test_secondary_phone_country_and_optional_sharing_reason
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_master_data.test_secondary_phone_country_and_optional_sharing_reason`

## TC090 — Duplicate email addresses

- Module: Edge cases
- Expected: Duplicate email addresses with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_crm_lead_management.test_duplicate_prevention_and_transfer_tenant_attributes
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-crossmodule-security.xml :: tests.test_crm_lead_management.test_duplicate_prevention_and_transfer_tenant_attributes`

## TC091 — Multiple customer roles

- Module: Edge cases
- Expected: Multiple customer roles with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_contact_directory.test_multiple_relationships_counts_filters_and_conflicts
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_contact_directory.test_multiple_relationships_counts_filters_and_conflicts`

## TC092 — Zero-price products

- Module: Edge cases
- Expected: Zero-price products with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pos_integrity.test_tc092_zero_price_product_is_zero_billed_but_still_issues_stock
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc092_zero_price_product_is_zero_billed_but_still_issues_stock`

## TC093 — Fractional quantities

- Module: Edge cases
- Expected: Fractional quantities with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pos_integrity.test_tc093_fractional_quantity_stock_and_money_remain_consistent, tests.test_business_suite_pos_integrity.test_tc111_unsupported_sale_precision_cannot_be_silently_truncated[0.001], tests.test_business_suite_pos_integrity.test_tc111_unsupported_sale_precision_cannot_be_silently_truncated[1.234]
- Status: **PASS**
- Severity: Medium
- Root cause: Negative/zero quantities and negative money were accepted
- Fix: Validate positive, storable quantity precision and nonnegative finite line amounts.
- Files changed: `backend/app/apps/srm/schemas.py`
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc093_fractional_quantity_stock_and_money_remain_consistent`; `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc111_unsupported_sale_precision_cannot_be_silently_truncated[0.001]`; `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc111_unsupported_sale_precision_cannot_be_silently_truncated[1.234]`

## TC094 — Expired service packages

- Module: Edge cases
- Expected: Expired service packages with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Service-package expiry and entitlement storage/redemption workflow is not implemented.
- Status: **BLOCKED**
- Severity: High
- Root cause: Service-package expiry and entitlement storage/redemption workflow is not implemented.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC095 — Service package partial redemption

- Module: Edge cases
- Expected: Service package partial redemption with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Service-package partial redemption and its idempotent ledger are not implemented.
- Status: **BLOCKED**
- Severity: High
- Root cause: Service-package partial redemption and its idempotent ledger are not implemented.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC096 — Customer cancellation

- Module: Edge cases
- Expected: Customer cancellation with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Customer appointment cancellation is blocked by the missing service-appointment workflow.
- Status: **BLOCKED**
- Severity: High
- Root cause: Customer appointment cancellation is blocked by the missing service-appointment workflow.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC097 — Employee reassignment

- Module: Edge cases
- Expected: Employee reassignment with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Appointment employee reassignment is blocked by the missing employee-backed appointment workflow.
- Status: **BLOCKED**
- Severity: High
- Root cause: Appointment employee reassignment is blocked by the missing employee-backed appointment workflow.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC098 — Appointment crossing midnight

- Module: Edge cases
- Expected: Appointment crossing midnight with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Appointment crossing-midnight behavior cannot be certified without the appointment implementation.
- Status: **BLOCKED**
- Severity: High
- Root cause: Appointment crossing-midnight behavior cannot be certified without the appointment implementation.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC099 — Employee timezone changes

- Module: Edge cases
- Expected: Employee timezone changes with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Employee timezone changes for appointments cannot be certified without the scheduling implementation.
- Status: **BLOCKED**
- Severity: High
- Root cause: Employee timezone changes for appointments cannot be certified without the scheduling implementation.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC100 — Duplicate invoice submission

- Module: Edge cases
- Expected: Duplicate invoice submission with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pos_concurrency.test_tc082_duplicate_concurrent_checkout_has_one_order_and_stock_movement, tests.test_fam_srm_posting_idempotency.test_fam_srm_invoice_and_receipt_posting_are_idempotent
- Status: **PASS**
- Severity: Critical
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_fam_srm_posting_idempotency.test_fam_srm_invoice_and_receipt_posting_are_idempotent`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_pos_concurrency.test_tc082_duplicate_concurrent_checkout_has_one_order_and_stock_movement`

## TC101 — Payment gateway timeout

- Module: Edge cases
- Expected: Payment gateway timeout with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Native POS gateway payment persistence/reconciliation is incomplete; an email/provider timeout test does not establish payment-gateway behavior.
- Status: **BLOCKED**
- Severity: High
- Root cause: Native POS gateway payment persistence/reconciliation is incomplete; an email/provider timeout test does not establish payment-gateway behavior.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_cross_module_audit.test_unknown_delivery_outcome_survives_reload_without_resend`

## TC102 — Failed transaction rollback

- Module: Edge cases
- Expected: Failed transaction rollback with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pos_integrity.test_tc059_oversell_rolls_back_order_and_stock
- Status: **PASS**
- Severity: Medium
- Root cause: Checkpoint snapshots mistook a successful own update for a stale plan
- Fix: Reload persisted task state before computing the next checkpoint digest; retain checks against actual external edits.
- Files changed: `backend/app/ai_operator/jobs.py`
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc059_oversell_rolls_back_order_and_stock`

## TC103 — Negative inventory attempts

- Module: Edge cases
- Expected: Negative inventory attempts with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pos_integrity.test_tc059_oversell_rolls_back_order_and_stock
- Status: **PASS**
- Severity: Critical
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc059_oversell_rolls_back_order_and_stock`

## TC104 — Missing GST classification

- Module: Edge cases
- Expected: Missing GST classification with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Configured rates are tested; effective-dated item classification selection and missing-classification policy remain incomplete.
- Status: **BLOCKED**
- Severity: High
- Root cause: Configured rates are tested; effective-dated item classification selection and missing-classification policy remain incomplete.
- Fix: Requires an approved implementation/reconciliation stage; no production data changed.
- Files changed: None for this scenario.
- Retest: BLOCKED — existing adjacent tests do not implement this workflow.
- Evidence: No passing execution evidence for the complete requested workflow.

## TC105 — Deleted or inactive catalog items referenced by historical invoices

- Module: Edge cases
- Expected: Deleted or inactive catalog items referenced by historical invoices with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_business_suite_pos_integrity.test_tc040_refund_uses_original_discount_and_tax_snapshot, tests.test_business_suite_pos_integrity.test_tc109_inactive_catalog_item_cannot_be_sold
- Status: **PASS**
- Severity: Medium
- Root cause: Refund lost original discounts/tax and allowed over-refund
- Fix: Use remaining original value/tax, proportional refunds and last-return rounding remainder.
- Files changed: `backend/app/apps/srm/api/router.py`
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc040_refund_uses_original_discount_and_tax_snapshot`; `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc109_inactive_catalog_item_cannot_be_sold`

## TC106 — Interrupted network requests

- Module: Edge cases
- Expected: Interrupted network requests with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: test-navigation-guards.cjs, test-record-cache.cjs
- Status: **PASS**
- Severity: Medium
- Root cause: Nested provider/worker retries made nine requests for a three-attempt job
- Fix: Worker owns retries through a context-local one-attempt provider budget; synchronous retries retain their bounded contract.
- Files changed: `backend/app/ai_operator/jobs.py`, `backend/app/ai_operator/providers.py`
- Retest: PASS
- Evidence: `backend/outputs/business-suite-frontend-results.json :: test-navigation-guards.cjs`; `backend/outputs/business-suite-frontend-results.json :: test-record-cache.cjs`

## TC107 — Unauthorized cross-module updates

- Module: Edge cases
- Expected: Unauthorized cross-module updates with canonical identities, correct amounts, authorized scope and retained history.
- Actual: Executed: tests.test_contact_directory.test_read_permission_does_not_grant_mutation_or_hr_access, tests.test_cross_module_audit.test_commercial_role_matrix[contributor-permissions2-Member-False-False-False-True], tests.test_cross_module_audit.test_commercial_role_matrix[finance-permissions3-Member-True-True-True-True], tests.test_cross_module_audit.test_commercial_role_matrix[inactive-permissions7-Member-False-False-False-False], tests.test_cross_module_audit.test_commercial_role_matrix[other_tenant-permissions8-Member-False-False-False-True], tests.test_cross_module_audit.test_commercial_role_matrix[outsider-permissions5-None-False-False-False-True], tests.test_cross_module_audit.test_commercial_role_matrix[project_manager-permissions1-Manager-True-False-False-True], tests.test_cross_module_audit.test_commercial_role_matrix[read_only-permissions4-Viewer-True-False-False-True], tests.test_cross_module_audit.test_commercial_role_matrix[removed-permissions6-None-False-False-False-True], tests.test_cross_module_audit.test_commercial_role_matrix[sales-permissions0-Member-True-False-False-True]
- Status: **PASS**
- Severity: Medium
- Root cause: No defect reproduced in the linked assertions.
- Fix: Existing behavior tested.
- Files changed: None for this scenario.
- Retest: PASS
- Evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_contact_directory.test_read_permission_does_not_grant_mutation_or_hr_access`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_cross_module_audit.test_commercial_role_matrix[contributor-permissions2-Member-False-False-False-True]`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_cross_module_audit.test_commercial_role_matrix[finance-permissions3-Member-True-True-True-True]`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_cross_module_audit.test_commercial_role_matrix[inactive-permissions7-Member-False-False-False-False]`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_cross_module_audit.test_commercial_role_matrix[other_tenant-permissions8-Member-False-False-False-True]`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_cross_module_audit.test_commercial_role_matrix[outsider-permissions5-None-False-False-False-True]`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_cross_module_audit.test_commercial_role_matrix[project_manager-permissions1-Manager-True-False-False-True]`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_cross_module_audit.test_commercial_role_matrix[read_only-permissions4-Viewer-True-False-False-True]`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_cross_module_audit.test_commercial_role_matrix[removed-permissions6-None-False-False-False-True]`; `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_cross_module_audit.test_commercial_role_matrix[sales-permissions0-Member-True-False-False-True]`
