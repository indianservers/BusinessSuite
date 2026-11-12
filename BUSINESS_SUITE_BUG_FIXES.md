# Business Suite bug fixes

Identified defect groups: 18. Fixed and verified: 18. Verification is based on executed evidence, not code inspection alone.

## B01 — Client item-type flag bypassed stock issuance

- Severity: Critical
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Client item-type flag bypassed stock issuance
- Correction: Determine inventory behavior from the canonical product and lock stock rows.
- Files: `backend/app/apps/srm/api/router.py`
- Retest evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc054_stock_type_cannot_be_spoofed_as_service`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_pos_concurrency.test_tc059_two_checkouts_cannot_sell_the_last_unit_twice`

## B02 — Negative/zero quantities and negative money were accepted

- Severity: Critical
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Negative/zero quantities and negative money were accepted
- Correction: Validate positive, storable quantity precision and nonnegative finite line amounts.
- Files: `backend/app/apps/srm/schemas.py`
- Retest evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc106_invalid_quantity_is_atomic[-1]`; `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc106_invalid_quantity_is_atomic[0]`; `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc107_negative_money_is_rejected[discount_amount]`; `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc107_negative_money_is_rejected[tax_amount]`; `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc107_negative_money_is_rejected[unit_price]`; `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc111_unsupported_sale_precision_cannot_be_silently_truncated[0.001]`; `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc111_unsupported_sale_precision_cannot_be_silently_truncated[1.234]`

## B03 — POS trusted client totals/tax and lost bill discounts

- Severity: Critical
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: POS trusted client totals/tax and lost bill discounts
- Correction: Reuse commercial decimal normalization, allocate bill discounts and snapshot canonical item tax.
- Files: `backend/app/apps/srm/api/router.py`, `backend/app/apps/srm/services/commercial.py`
- Retest evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc027_bill_discount_is_allocated_before_each_item_tax`; `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc076_pos_totals_and_tax_are_server_authoritative`

## B04 — Non-restocked refunds did not consume refundable quantity

- Severity: Critical
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Non-restocked refunds did not consume refundable quantity
- Correction: Count every return and serialize competing refunds.
- Files: `backend/app/apps/srm/api/router.py`
- Retest evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc030_nonrestocked_return_still_consumes_refundable_quantity`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_pos_concurrency.test_tc030_concurrent_nonrestocked_refunds_cannot_exceed_original_sale`

## B05 — Return could substitute a different inventory product

- Severity: Critical
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Return could substitute a different inventory product
- Correction: Bind returns to the original sale line and validate warehouse scope.
- Files: `backend/app/apps/srm/api/router.py`
- Retest evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc073_return_cannot_substitute_another_product`

## B06 — Refund lost original discounts/tax and allowed over-refund

- Severity: High
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Refund lost original discounts/tax and allowed over-refund
- Correction: Use remaining original value/tax, proportional refunds and last-return rounding remainder.
- Files: `backend/app/apps/srm/api/router.py`
- Retest evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc040_refund_uses_original_discount_and_tax_snapshot`; `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc108_refund_cannot_exceed_original_sale_value`

## B07 — PostgreSQL contact retention query compared text IDs to integers

- Severity: High
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: PostgreSQL contact retention query compared text IDs to integers
- Correction: Bind identifiers using their stored SQL type; retain linked history.
- Files: `backend/app/apps/crm/contact_directory.py`
- Retest evidence: `backend\outputs\business-suite-postgres-acceptance.xml :: tests.test_contact_directory.test_permanent_deletion_is_admin_only_and_protects_referenced_contacts`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_contact_retention.test_tc075_text_identity_history_prevents_permanent_deletion`

## B08 — FAM GST ties rounded differently from commercial/POS arithmetic

- Severity: High
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: FAM GST ties rounded differently from commercial/POS arithmetic
- Correction: Apply explicit ROUND_HALF_UP to each tax component.
- Files: `backend/app/apps/fam/api/router.py`
- Retest evidence: `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-0.10-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-1000.25-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[False-99.99-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-0.10-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-1000.25-5]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-0]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-12]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-18]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-28]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc031_039_configured_rate_components_and_decimal_rounding[True-99.99-5]`

## B09 — GST API accepted negative and invalid component rates

- Severity: High
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: GST API accepted negative and invalid component rates
- Correction: Validate GST component bounds and nonnegative taxable/cess values; preserve configurable positive cess.
- Files: `backend/app/apps/fam/schemas.py`
- Retest evidence: `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[-1-cess_rate]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[-1-cgst_rate]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[-1-igst_rate]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[-1-sgst_rate]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[101-cess_rate]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[101-cgst_rate]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[101-igst_rate]`; `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_gst_matrix.test_tc076_tax_rate_bounds_cannot_be_bypassed[101-sgst_rate]`

## B10 — 100-customer page performed 405 SELECTs

- Severity: Medium
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: 100-customer page performed 405 SELECTs
- Correction: Batch details, relationships and branch availability for the authorized page only.
- Files: `backend/app/shared/master_data.py`
- Retest evidence: `backend\outputs\business-suite-postgres-final.xml :: tests.test_business_suite_pagination.test_tc077_ten_thousand_customers_have_bounded_page_and_queries`

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
- Retest evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc071_foreign_customer_cannot_be_attached_to_pos_order`; `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_pos_integrity.test_tc073_return_customer_cannot_be_replaced`

## B15 — Workflow interpretation intercepted pending single-action help/cancellation

- Severity: High
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Workflow interpretation intercepted pending single-action help/cancellation
- Correction: Preserve ownership of pending single-action slot filling and cancellation.
- Files: `backend/app/ai_operator/workflows.py`
- Retest evidence: `backend\outputs\business-suite-regression-repairs.xml :: tests.test_action_model_v2.test_invalid_followup_keeps_question_and_cancel_only_affects_that_chat`; `backend\outputs\business-suite-regression-repairs.xml :: tests.test_action_repairs.test_ambiguous_or_help_reply_never_becomes_a_task_title[I do not know]`; `backend\outputs\business-suite-regression-repairs.xml :: tests.test_action_repairs.test_ambiguous_or_help_reply_never_becomes_a_task_title[I don\u2019t know]`; `backend\outputs\business-suite-regression-repairs.xml :: tests.test_action_repairs.test_ambiguous_or_help_reply_never_becomes_a_task_title[explain this field]`; `backend\outputs\business-suite-regression-repairs.xml :: tests.test_action_repairs.test_ambiguous_or_help_reply_never_becomes_a_task_title[no]`; `backend\outputs\business-suite-regression-repairs.xml :: tests.test_action_repairs.test_ambiguous_or_help_reply_never_becomes_a_task_title[okay]`; `backend\outputs\business-suite-regression-repairs.xml :: tests.test_action_repairs.test_ambiguous_or_help_reply_never_becomes_a_task_title[please explain this field]`; `backend\outputs\business-suite-regression-repairs.xml :: tests.test_action_repairs.test_ambiguous_or_help_reply_never_becomes_a_task_title[what are my choices?]`; `backend\outputs\business-suite-regression-repairs.xml :: tests.test_action_repairs.test_ambiguous_or_help_reply_never_becomes_a_task_title[yes]`

## B16 — Nested provider/worker retries made nine requests for a three-attempt job

- Severity: High
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Nested provider/worker retries made nine requests for a three-attempt job
- Correction: Worker owns retries through a context-local one-attempt provider budget; synchronous retries retain their bounded contract.
- Files: `backend/app/ai_operator/providers.py`, `backend/app/ai_operator/jobs.py`
- Retest evidence: `backend\outputs\business-suite-regression-repairs.xml :: tests.test_ai_operator_jobs.test_provider_retry_budget_and_failed_attempt_telemetry`

## B17 — POS rounded payable to whole currency units and displayed a local rather than confirmed total

- Severity: High
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: POS rounded payable to whole currency units and displayed a local rather than confirmed total
- Correction: Keep cents in the preview and display the persisted server total after checkout.
- Files: `frontend/src/apps/srm/pages/SRMPOSPage.tsx`
- Retest evidence: `backend\outputs\business-suite-postgres-closure.xml :: tests.test_business_suite_live_browser.test_tc006_012_common_customer_ui_uses_real_canonical_api`

## B18 — Checkpoint snapshots mistook a successful own update for a stale plan

- Severity: High
- Status: **FIXED AND VERIFIED**
- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.
- Root cause: Checkpoint snapshots mistook a successful own update for a stale plan
- Correction: Reload persisted task state before computing the next checkpoint digest; retain checks against actual external edits.
- Files: `backend/app/ai_operator/jobs.py`
- Retest evidence: `backend\outputs\business-suite-regression-repairs.xml :: tests.test_ai_operator_jobs.test_background_work_uses_durable_queue_and_after_commit_events[atomic]`; `backend\outputs\business-suite-regression-repairs.xml :: tests.test_ai_operator_jobs.test_background_work_uses_durable_queue_and_after_commit_events[checkpointed]`; `backend\outputs\business-suite-regression-repairs.xml :: tests.test_ai_operator_jobs.test_expired_lease_resumes_without_duplicate_completed_step`; `backend\outputs\business-suite-regression-repairs.xml :: tests.test_ai_operator_jobs.test_failed_checkpoint_preserves_completed_effects_and_resumes`
