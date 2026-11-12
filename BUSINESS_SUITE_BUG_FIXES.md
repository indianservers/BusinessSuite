# Business Suite bug fixes

Identified defect groups: 27. Fixed and verified: 27. Verification is based on executed evidence, not code inspection alone.

## B01 — Client item-type flag bypassed stock issuance

- Severity: Critical
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Client item-type flag bypassed stock issuance
- Correction: Determine inventory behavior from the canonical product and lock stock rows.
- Files: `backend/app/apps/srm/api/router.py`
- Retest evidence: `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_pos_integrity.test_tc054_stock_type_cannot_be_spoofed_as_service`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_pos_concurrency.test_tc059_two_checkouts_cannot_sell_the_last_unit_twice`

## B02 — Negative/zero quantities and negative money were accepted

- Severity: Critical
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Negative/zero quantities and negative money were accepted
- Correction: Validate positive, storable quantity precision and nonnegative finite line amounts.
- Files: `backend/app/apps/srm/schemas.py`
- Retest evidence: `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_pos_integrity.test_tc106_invalid_quantity_is_atomic[-1]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_pos_integrity.test_tc106_invalid_quantity_is_atomic[0]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_pos_integrity.test_tc107_negative_money_is_rejected[discount_amount]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_pos_integrity.test_tc107_negative_money_is_rejected[tax_amount]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_pos_integrity.test_tc107_negative_money_is_rejected[unit_price]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_pos_integrity.test_tc111_unsupported_sale_precision_cannot_be_silently_truncated[0.001]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_pos_integrity.test_tc111_unsupported_sale_precision_cannot_be_silently_truncated[1.234]`

## B03 — POS trusted client totals/tax and lost bill discounts

- Severity: Critical
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: POS trusted client totals/tax and lost bill discounts
- Correction: Reuse commercial decimal normalization, allocate bill discounts and snapshot canonical item tax.
- Files: `backend/app/apps/srm/api/router.py`, `backend/app/apps/srm/services/commercial.py`
- Retest evidence: `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_pos_integrity.test_tc027_bill_discount_is_allocated_before_each_item_tax`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_pos_integrity.test_tc076_pos_totals_and_tax_are_server_authoritative`

## B04 — Non-restocked refunds did not consume refundable quantity

- Severity: Critical
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Non-restocked refunds did not consume refundable quantity
- Correction: Count every return and serialize competing refunds.
- Files: `backend/app/apps/srm/api/router.py`
- Retest evidence: `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_pos_integrity.test_tc030_nonrestocked_return_still_consumes_refundable_quantity`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_pos_concurrency.test_tc030_concurrent_nonrestocked_refunds_cannot_exceed_original_sale`

## B05 — Return could substitute a different inventory product

- Severity: Critical
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Return could substitute a different inventory product
- Correction: Bind returns to the original sale line and validate warehouse scope.
- Files: `backend/app/apps/srm/api/router.py`
- Retest evidence: `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_pos_integrity.test_tc073_return_cannot_substitute_another_product`

## B06 — Refund lost original discounts/tax and allowed over-refund

- Severity: High
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Refund lost original discounts/tax and allowed over-refund
- Correction: Use remaining original value/tax, proportional refunds and last-return rounding remainder.
- Files: `backend/app/apps/srm/api/router.py`
- Retest evidence: `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_pos_integrity.test_tc040_refund_uses_original_discount_and_tax_snapshot`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_pos_integrity.test_tc108_refund_cannot_exceed_original_sale_value`

## B07 — PostgreSQL contact retention query compared text IDs to integers

- Severity: High
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: PostgreSQL contact retention query compared text IDs to integers
- Correction: Bind identifiers using their stored SQL type; retain linked history.
- Files: `backend/app/apps/crm/contact_directory.py`
- Retest evidence: `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_contact_retention.test_tc075_text_identity_history_prevents_permanent_deletion`; `backend\outputs\business-suite-full-verified.xml :: tests.test_contact_directory.test_permanent_deletion_is_admin_only_and_protects_referenced_contacts`

## B08 — FAM GST ties rounded differently from commercial/POS arithmetic

- Severity: High
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: FAM GST ties rounded differently from commercial/POS arithmetic
- Correction: Apply explicit ROUND_HALF_UP to each tax component.
- Files: `backend/app/apps/fam/api/router.py`
- Retest evidence: `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-0]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-12]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-18]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-28]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-5]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-0]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-12]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-18]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-28]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-5]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-0]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-12]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-18]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-28]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-5]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-0]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-12]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-18]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-28]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-5]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-0]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-12]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-18]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-28]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-5]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-0]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-12]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-18]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-28]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-5]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-0]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-12]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-18]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-28]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-5]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-0]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-12]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-18]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-28]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-5]`

## B09 — GST API accepted negative and invalid component rates

- Severity: High
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: GST API accepted negative and invalid component rates
- Correction: Validate GST component bounds and nonnegative taxable/cess values; preserve configurable positive cess.
- Files: `backend/app/apps/fam/schemas.py`
- Retest evidence: `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[-1-cess_rate]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[-1-cgst_rate]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[-1-igst_rate]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[-1-sgst_rate]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[101-cess_rate]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[101-cgst_rate]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[101-igst_rate]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[101-sgst_rate]`

## B10 — 100-customer page performed 405 SELECTs

- Severity: Medium
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: 100-customer page performed 405 SELECTs
- Correction: Batch details, relationships and branch availability for the authorized page only.
- Files: `backend/app/shared/master_data.py`
- Retest evidence: `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_pagination.test_tc077_ten_thousand_customers_have_bounded_page_and_queries`

## B11 — FAM table adapter swallowed the financial empty state

- Severity: Medium
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: FAM table adapter swallowed the financial empty state
- Correction: Render explicit empty status and suppress stale statements on failed requests.
- Files: `frontend/src/apps/fam/FinancialStatementsPage.tsx`
- Retest evidence: `backend/outputs/business-suite-frontend-results.json :: test-mobile-fam-workflows.cjs`

## B12 — Successful bank-rule creation left its dialog open

- Severity: Medium
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Successful bank-rule creation left its dialog open
- Correction: Close on an explicit successful creation revision; retain forms on errors.
- Files: `frontend/src/apps/fam/BankRulesPage.tsx`
- Retest evidence: `backend/outputs/business-suite-frontend-results.json :: test-mobile-fam-workflows.cjs`

## B13 — Navigation/accounting harnesses had stale dependencies, server assumptions and races

- Severity: Medium
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Navigation/accounting harnesses had stale dependencies, server assumptions and races
- Correction: Load real route helpers, honor current workspace presentation, start isolated servers and await confirmed requests.
- Files: `frontend/scripts/test-navigation-workspaces.cjs`, `frontend/scripts/test-navigation-categories.cjs`, `frontend/scripts/test-operations-workspaces.cjs`, `frontend/scripts/test-relationship-hub.cjs`, `frontend/scripts/test-accounting-connected.cjs`
- Retest evidence: `backend/outputs/business-suite-frontend-results.json :: test-accounting-connected.cjs`; `backend/outputs/business-suite-frontend-results.json :: test-navigation-categories.cjs`; `backend/outputs/business-suite-frontend-results.json :: test-navigation-workspaces.cjs`; `backend/outputs/business-suite-frontend-results.json :: test-operations-workspaces.cjs`; `backend/outputs/business-suite-frontend-results.json :: test-relationship-hub.cjs`

## B14 — POS order/return accepted foreign or replacement customer IDs

- Severity: Critical
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: POS order/return accepted foreign or replacement customer IDs
- Correction: Reuse tenant-scoped commercial customer/contact resolvers and bind return customer to its source sale.
- Files: `backend/app/apps/srm/api/router.py`
- Retest evidence: `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_pos_integrity.test_tc071_foreign_customer_cannot_be_attached_to_pos_order`; `backend\outputs\business-suite-full-verified.xml :: tests.test_business_suite_pos_integrity.test_tc073_return_customer_cannot_be_replaced`

## B15 — Workflow interpretation intercepted pending single-action help/cancellation

- Severity: High
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Workflow interpretation intercepted pending single-action help/cancellation
- Correction: Preserve ownership of pending single-action slot filling and cancellation.
- Files: `backend/app/ai_operator/workflows.py`
- Retest evidence: `backend\outputs\business-suite-full-verified.xml :: tests.test_action_model_v2.test_invalid_followup_keeps_question_and_cancel_only_affects_that_chat`; `backend\outputs\business-suite-full-verified.xml :: tests.test_action_repairs.test_ambiguous_or_help_reply_never_becomes_a_task_title[I do not know]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_action_repairs.test_ambiguous_or_help_reply_never_becomes_a_task_title[I don\u2019t know]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_action_repairs.test_ambiguous_or_help_reply_never_becomes_a_task_title[explain this field]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_action_repairs.test_ambiguous_or_help_reply_never_becomes_a_task_title[no]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_action_repairs.test_ambiguous_or_help_reply_never_becomes_a_task_title[okay]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_action_repairs.test_ambiguous_or_help_reply_never_becomes_a_task_title[please explain this field]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_action_repairs.test_ambiguous_or_help_reply_never_becomes_a_task_title[what are my choices?]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_action_repairs.test_ambiguous_or_help_reply_never_becomes_a_task_title[yes]`

## B16 — Nested provider/worker retries made nine requests for a three-attempt job

- Severity: High
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Nested provider/worker retries made nine requests for a three-attempt job
- Correction: Worker owns retries through a context-local one-attempt provider budget; synchronous retries retain their bounded contract.
- Files: `backend/app/ai_operator/providers.py`, `backend/app/ai_operator/jobs.py`
- Retest evidence: `backend\outputs\business-suite-full-verified.xml :: tests.test_ai_operator_jobs.test_provider_retry_budget_and_failed_attempt_telemetry`

## B17 — POS rounded payable to whole currency units and displayed a local rather than confirmed total

- Severity: High
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: POS rounded payable to whole currency units and displayed a local rather than confirmed total
- Correction: Keep cents in the preview and display the persisted server total after checkout.
- Files: `frontend/src/apps/srm/pages/SRMPOSPage.tsx`
- Retest evidence: `backend\outputs\business-suite-live-browser-final.xml :: tests.test_business_suite_live_browser.test_tc006_012_common_customer_ui_uses_real_canonical_api`

## B18 — Checkpoint snapshots mistook a successful own update for a stale plan

- Severity: High
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Checkpoint snapshots mistook a successful own update for a stale plan
- Correction: Reload persisted task state before computing the next checkpoint digest; retain checks against actual external edits.
- Files: `backend/app/ai_operator/jobs.py`
- Retest evidence: `backend\outputs\business-suite-full-verified.xml :: tests.test_ai_operator_jobs.test_background_work_uses_durable_queue_and_after_commit_events[atomic]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_ai_operator_jobs.test_background_work_uses_durable_queue_and_after_commit_events[checkpointed]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_ai_operator_jobs.test_expired_lease_resumes_without_duplicate_completed_step`; `backend\outputs\business-suite-full-verified.xml :: tests.test_ai_operator_jobs.test_failed_checkpoint_preserves_completed_effects_and_resumes`

## B19 — Single-asset assignment passed null into the handover condition contract

- Severity: High
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Single-asset assignment passed null into the handover condition contract
- Correction: Use the existing Good default when the optional legacy condition is omitted.
- Files: `backend/app/api/v1/assets.py`
- Retest evidence: `backend\outputs\business-suite-full-verified.xml :: tests.test_hrms_workspaces.test_bike_assignment_duplicate_return_and_exit_clearance`

## B20 — Contact imports normalized calling codes only when a phone was present

- Severity: High
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Contact imports normalized calling codes only when a phone was present
- Correction: Normalize an explicitly supplied calling code independently of the optional phone value.
- Files: `backend/app/shared/import_service.py`
- Retest evidence: `backend\outputs\business-suite-full-verified.xml :: tests.test_import_adapters.test_each_priority_import_writes_native_records[crm-contacts]`

## B21 — LWP feed repeated period/group/policy queries for every employee

- Severity: Medium
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: LWP feed repeated period/group/policy queries for every employee
- Correction: Batch group selection and cache the period and effective policy per group, retaining policy calculations.
- Files: `backend/app/api/v1/leave_payroll.py`
- Retest evidence: `backend\outputs\business-suite-full-verified.xml :: tests.test_loading_batches.test_lwp_batch_keeps_overlap_half_day_attendance_and_latest_salary`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_assigned_component_flags_and_payslip_reconcile`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_component_mapping_override_and_snapshot`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_conflicting_paid_unpaid_half_day[block-0-True]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_conflicting_paid_unpaid_half_day[paid_wins-0-False]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_conflicting_paid_unpaid_half_day[unpaid_wins-.5-False]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_core_component_treatment[False-False]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_core_component_treatment[False-True]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_core_component_treatment[True-False]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_core_component_treatment[True-True]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_divisor_calculation_with_independent_oracle[calendar_days-2024-2]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_divisor_calculation_with_independent_oracle[calendar_days-2025-2]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_divisor_calculation_with_independent_oracle[calendar_days-2026-4]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_divisor_calculation_with_independent_oracle[calendar_days-2026-5]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_divisor_calculation_with_independent_oracle[fixed_26-2024-2]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_divisor_calculation_with_independent_oracle[fixed_26-2025-2]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_divisor_calculation_with_independent_oracle[fixed_26-2026-4]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_divisor_calculation_with_independent_oracle[fixed_26-2026-5]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_divisor_calculation_with_independent_oracle[fixed_30-2024-2]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_divisor_calculation_with_independent_oracle[fixed_30-2025-2]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_divisor_calculation_with_independent_oracle[fixed_30-2026-4]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_divisor_calculation_with_independent_oracle[fixed_30-2026-5]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_divisor_calculation_with_independent_oracle[working_days-2024-2]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_divisor_calculation_with_independent_oracle[working_days-2025-2]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_divisor_calculation_with_independent_oracle[working_days-2026-4]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_divisor_calculation_with_independent_oracle[working_days-2026-5]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_half_leave_and_half_attendance_make_one_covered_day[False-.5]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_half_leave_and_half_attendance_make_one_covered_day[True-0]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_incentive_and_reimbursement_treatment[False-False]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_incentive_and_reimbursement_treatment[False-True]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_incentive_and_reimbursement_treatment[True-False]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_incentive_and_reimbursement_treatment[True-True]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_invalid_policy_options_rejected[components-value4]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_invalid_policy_options_rejected[leave_conflict-latest]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_invalid_policy_options_rejected[lop_divisor-fixed_31]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_invalid_policy_options_rejected[missing_attendance-guess]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_invalid_policy_options_rejected[proration_divisor-zero]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_joining_proration_divisor_and_basis[calendar_days-calendar_days]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_joining_proration_divisor_and_basis[calendar_days-fixed_26]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_joining_proration_divisor_and_basis[calendar_days-fixed_30]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_joining_proration_divisor_and_basis[calendar_days-working_days]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_joining_proration_divisor_and_basis[working_days-calendar_days]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_joining_proration_divisor_and_basis[working_days-fixed_26]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_joining_proration_divisor_and_basis[working_days-fixed_30]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_joining_proration_divisor_and_basis[working_days-working_days]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_missing_attendance_policy[False-block]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_missing_attendance_policy[False-lop]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_missing_attendance_policy[False-payable]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_missing_attendance_policy[True-block]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_missing_attendance_policy[True-lop]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_missing_attendance_policy[True-payable]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_missing_component_configuration_blocks_even_force_approve`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_monthly_nonworking_policy_does_not_invent_wage_units[daily-None-21000]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_monthly_nonworking_policy_does_not_invent_wage_units[daily-unpaid_day1-20000]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_monthly_nonworking_policy_does_not_invent_wage_units[daily-unpaid_day2-21000]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_monthly_nonworking_policy_does_not_invent_wage_units[hourly-None-2000]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_nonworking_and_sandwich_combinations[False-False-False]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_nonworking_and_sandwich_combinations[False-False-True]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_nonworking_and_sandwich_combinations[False-True-False]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_nonworking_and_sandwich_combinations[False-True-True]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_nonworking_and_sandwich_combinations[True-False-False]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_nonworking_and_sandwich_combinations[True-False-True]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_nonworking_and_sandwich_combinations[True-True-False]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_nonworking_and_sandwich_combinations[True-True-True]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_policy_api_permissions_versioning_and_history`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_policy_read_and_publish_cannot_cross_company`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_policy_snapshot_and_regeneration_requirement`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_policy_uses_configured_working_calendar[5_day-5-2]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_policy_uses_configured_working_calendar[6_day-6-3]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_policy_uses_configured_working_calendar[company-7-4]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_reconciled_missing_attendance_cannot_be_force_approved`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_sandwich_crosses_month_boundary`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_sandwich_crosses_year_and_holiday`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_sandwich_inferred_only_between_full_unpaid_workdays[False-False-2]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_sandwich_inferred_only_between_full_unpaid_workdays[True-False-4]`; `backend\outputs\business-suite-full-verified.xml :: tests.test_payroll_configurable_policies.test_sandwich_inferred_only_between_full_unpaid_workdays[True-True-1]`

## B22 — PostgreSQL schema verification manifest lagged existing migrations

- Severity: High
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: PostgreSQL schema verification manifest lagged existing migrations
- Correction: Update the verification manifest for migration-backed tables and columns; preserve the historical baseline and do not change application schema.
- Files: `backend/alembic_postgresql/schema/extensions.json`
- Retest evidence: `backend\outputs\business-suite-full-verified.xml :: tests.test_postgresql_configuration.test_baseline_covers_every_module_and_historical_schema`

## B23 — Legacy fixtures bypassed current identity, inspection and serialization contracts

- Severity: Medium
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Legacy fixtures bypassed current identity, inspection and serialization contracts
- Correction: Exercise a real canonical customer, required inspection approvals, normalized dependency fields, explicit-rule precedence and structural weight privacy; retain all authorization controls.
- Files: `backend/tests/test_hrms_workspaces.py`, `backend/tests/test_hrms_operational_foundations.py`, `backend/tests/test_srm_inventory_product_master.py`, `backend/tests/test_suite_module_agents.py`, `backend/tests/test_local_tensorflow.py`, `backend/tests/test_platform_nlp_training.py`
- Retest evidence: `backend\outputs\business-suite-full-verified.xml :: tests.test_hrms_operational_foundations.test_exit_asset_helpdesk_and_announcements`; `backend\outputs\business-suite-full-verified.xml :: tests.test_local_tensorflow.test_neural_model_actually_selects_unseen_intents_and_rules_correct_filter_errors`; `backend\outputs\business-suite-full-verified.xml :: tests.test_platform_nlp_training.test_platform_server_training_activation_and_scope`; `backend\outputs\business-suite-full-verified.xml :: tests.test_srm_inventory_product_master.test_srm_product_master_and_opening_stock_are_database_backed`; `backend\outputs\business-suite-full-verified.xml :: tests.test_suite_module_agents.test_followup_preserves_module_and_refetches_selected_record`

## B24 — Rate-limit integration tests depended on remaining in one wall-clock minute

- Severity: Medium
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Rate-limit integration tests depended on remaining in one wall-clock minute
- Correction: QA counters recorded six attempts in one minute and three in the next (business-suite-rate-window-evidence.json). Pin only the limiter clock in the fixture; retain production fixed-window behavior and explicit rollover/deadline tests.
- Files: `backend/tests/test_shared_request_limits.py`
- Retest evidence: `backend\outputs\business-suite-request-limits-final.xml :: tests.test_shared_request_limits.test_counters_are_shared_between_sessions_and_reset_after_window`; `backend\outputs\business-suite-request-limits-final.xml :: tests.test_shared_request_limits.test_login_throttle_cannot_be_bypassed_with_forwarded_header`; `backend\outputs\business-suite-request-limits-final.xml :: tests.test_shared_request_limits.test_reset_has_shared_account_and_ip_throttle`

## B25 — Assistant presentation tool omitted its structured-slide input contract

- Severity: Medium
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Assistant presentation tool omitted its structured-slide input contract
- Correction: Describe the existing bounded slide schema and required empty text/table fields; preserve review-before-save behavior.
- Files: `backend/app/ai_operator/suite_tools.py`
- Retest evidence: `backend\outputs\business-suite-presentations-final.xml :: tests.test_artifact_presentations.test_cloud_can_prepare_structured_slides_without_saving_them`

## B26 — Finance analytics fixture used the host date for an explicitly UTC organization

- Severity: Medium
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Finance analytics fixture used the host date for an explicitly UTC organization
- Correction: Date synthetic vouchers using UTC, matching the fixture company; retain organization-timezone filtering.
- Files: `backend/tests/test_business_analytics_overview.py`
- Retest evidence: `backend\outputs\business-suite-analytics-final.xml :: tests.test_business_analytics_overview.test_daily_activity_uses_organization_timezone`; `backend\outputs\business-suite-analytics-final.xml :: tests.test_business_analytics_overview.test_finance_counts_only_posted_vouchers`

## B27 — PMS analytics mixed organization business days with UTC date/hour buckets

- Severity: High
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: PMS analytics mixed organization business days with UTC date/hour buckets
- Correction: Use organization-zone range boundaries, local daily/hourly buckets, server-default dates and matching UI labels/exports. Verify midnight and a 25-hour DST day.
- Files: `backend/app/apps/project_management/analytics.py`, `frontend/src/apps/project-management/pages/AnalyticsPage.tsx`, `backend/tests/test_pms_analytics.py`
- Retest evidence: `backend/outputs/business-suite-frontend-results.json :: test-mobile-pms-analytics.cjs`; `backend\outputs\business-suite-postgres-pms-timezone.xml :: tests.test_pms_analytics.test_analytics_counts_shared_assignments_and_time_without_duplication`; `backend\outputs\business-suite-postgres-pms-timezone.xml :: tests.test_pms_analytics.test_analytics_timezone_midnight_and_dst_boundaries[America/New_York-2026-11-01-2026-11-02T04:30:00+00:00-23]`; `backend\outputs\business-suite-postgres-pms-timezone.xml :: tests.test_pms_analytics.test_analytics_timezone_midnight_and_dst_boundaries[Asia/Kolkata-2026-11-13-2026-11-12T19:00:00+00:00-0]`
