# CRM Use Case Execution Report

Date: 2026-06-04

## Summary

- Passed: 7
- Partially Passed: 18
- Failed: 0
- Not Implemented: 5
- Bugs fixed during verification: 1 high-impact frontend RBAC bug.
- Final CRM go-live status: **Not ready for full CRM go-live**. Core CRM APIs are strong, but production sales operations still have blockers around web-to-lead, CSV import depth, CRM-to-PMS handoff, global record search, quota/cadence, and cross-module Customer 360.

---

Use Case Number: 1

Use Case Name: Admin creates a new lead manually from CRM UI.

User Role: CRM Admin

Business Scenario: Sales ops manually enters a trade-show or phone lead with source, owner, and initial status.

Steps to Test:
1. Open `/crm/leads`.
2. Use the create action to create a lead with full name, email, source, owner/status fields.
3. Verify `POST /api/v1/crm/leads`.
4. Verify duplicate and required-field behavior.
5. Verify `crm_leads`, audit, and UI confirmation/error behavior.

Expected Result: Lead is saved with required fields, source, owner, status, duplicate warning, success confirmation, audit log, and RBAC protection.

Actual Result: UI route renders and calls CRM list APIs. Backend validates unknown entities/required fields, creates org-scoped lead rows, assigns owner defaults, creates timeline/audit events, and returns duplicate conflict for unique custom-field cases. UI duplicate warning during manual entry was not proven; duplicate UX is mostly via the duplicate management screen.

Status: Partially Passed

Bugs Found: Manual create duplicate-warning UX not proven from UI.

Fix Applied: None.

Evidence: `frontend/src/apps/crm/CRMWorkspacePage.tsx` quick create/list flow; `POST /api/v1/crm/leads`; `crm_leads`, `crm_audit_logs`; `tests/test_crm_rest_api.py::test_crm_leads_crud_is_scoped_to_current_organization`, `test_crm_validates_unknown_entity_and_required_fields`, `test_crm_custom_field_values_are_persisted_and_org_scoped`; Playwright `/crm/leads` desktop/mobile render.

---

Use Case Number: 2

Use Case Name: Sales user views only assigned leads.

User Role: Sales Executive

Business Scenario: A salesperson opens CRM and must not see another salesperson's leads.

Steps to Test:
1. Create two CRM sales executive users.
2. Create one lead owned by each user.
3. Fetch `/api/v1/crm/leads` as each user.
4. Verify hidden peer records.
5. Verify UI route remains available for the sales role.

Expected Result: Sales user sees assigned/permitted leads only; other salesperson records are hidden.

Actual Result: Backend test verifies executive visibility is limited to permitted records. Browser RBAC smoke verifies `crm_sales_executive` can open `/crm/leads`.

Status: Passed

Bugs Found: None.

Fix Applied: None.

Evidence: `tests/test_crm_rest_api.py::test_crm_sales_executive_visibility_is_limited_to_permitted_records`; `_apply_record_visibility` in CRM router; `crm_leads.owner_user_id`; Playwright RBAC smoke `/crm/leads` allowed.

---

Use Case Number: 3

Use Case Name: Sales manager views all team leads.

User Role: Sales Manager

Business Scenario: A sales manager reviews team leads for coaching and pipeline hygiene.

Steps to Test:
1. Login as CRM sales manager.
2. Open `/crm/leads`.
3. Fetch team-owned leads through `GET /api/v1/crm/leads`.
4. Verify hierarchy/team visibility.
5. Verify peer and cross-organization boundaries.

Expected Result: Manager sees team leads according to hierarchy and no cross-organization records.

Actual Result: CRM roles and record visibility helpers exist, org scoping is verified, and manager role can access CRM routes. A specific hierarchy/team-rollup test for manager-owned subordinate leads was not found.

Status: Partially Passed

Bugs Found: Team hierarchy visibility not fully verified by an automated CRM test.

Fix Applied: None.

Evidence: `frontend/src/lib/roles.ts`; `_crm_user_scope`, `_apply_record_visibility`; org-scoped tests in `tests/test_crm_rest_api.py`.

---

Use Case Number: 4

Use Case Name: Admin imports leads from CSV.

User Role: CRM Admin

Business Scenario: Admin imports a marketing list and needs invalid-row handling and duplicate control.

Steps to Test:
1. Open `/crm/import-export` and `/crm/leads`.
2. Submit lead rows through `POST /api/v1/crm/leads/import`.
3. Verify created and failed rows.
4. Verify duplicate handling and error export/rollback behavior.
5. Verify `crm_leads` and audit impact.

Expected Result: CSV import validates rows, detects duplicates, exports invalid rows, and supports safe rollback/error export.

Actual Result: Backend has generic row import and frontend list page has import/export helpers. The dedicated `/crm/import-export` page is more dashboard-style, and true CSV parsing, rollback, and invalid-row export were not proven.

Status: Partially Passed

Bugs Found: Full CSV workflow with rollback/error export is incomplete.

Fix Applied: None.

Evidence: `POST /api/v1/crm/{entity}/import`, `GET /api/v1/crm/{entity}/export`; `CRMListPage` import/export code; `crm_leads`.

---

Use Case Number: 5

Use Case Name: Website lead is captured through web-to-lead form.

User Role: Website Visitor / Sales Ops

Business Scenario: A website visitor submits a form and CRM should create a lead.

Steps to Test:
1. Search for public web-to-lead UI/API.
2. Verify lead creation, source tagging, assignment rule, and notification.
3. Verify database and audit impact.

Expected Result: Public form/API creates CRM lead with website source, assignment rule, and notification.

Actual Result: No dedicated public web-to-lead form or unauthenticated lead-capture endpoint was found. CRM webhooks exist for outbound events, not inbound web-to-lead capture.

Status: Not Implemented

Bugs Found: Feature missing.

Fix Applied: None.

Evidence: Code search for `web-to-lead`, `webtolead`, lead capture; outbound webhook tests only.

---

Use Case Number: 6

Use Case Name: Lead assignment rule auto-assigns lead by territory/source.

User Role: CRM Admin / Sales Ops

Business Scenario: Incoming leads should be routed to the right salesperson by territory/source.

Steps to Test:
1. Open `/crm/territories`.
2. Create territory and assign user.
3. Create matching lead/account/deal.
4. Run `POST /api/v1/crm/territories/auto-assign`.
5. Verify owner assignment and notification.

Expected Result: Matching records receive territory and owner, and owner is notified.

Actual Result: Territory CRUD, territory-user mapping, auto-assignment, org scoping, and territory report are tested. Notification on assignment was not verified.

Status: Partially Passed

Bugs Found: Assignment notification not proven.

Fix Applied: None.

Evidence: `test_crm_territory_rules_assign_records_and_remain_org_scoped`; `crm_territories`, `crm_territory_users`, `crm_leads.owner_user_id`.

---

Use Case Number: 7

Use Case Name: Sales user updates lead status from New to Contacted to Qualified.

User Role: Sales Executive

Business Scenario: Sales rep updates lead progress after outreach and qualification.

Steps to Test:
1. Open `/crm/leads/:id`.
2. PATCH status changes through `PATCH /api/v1/crm/leads/{id}`.
3. Verify timeline, audit log, validation, and next follow-up prompt.

Expected Result: Status changes persist, timeline/audit records are created, and follow-up prompt appears.

Actual Result: Generic update route supports lead status updates; status/timeline events are verified in backend tests. Next follow-up prompt was not proven as a required UI workflow.

Status: Partially Passed

Bugs Found: Next follow-up prompt not proven.

Fix Applied: None.

Evidence: `PATCH /api/v1/crm/leads/{id}`; `_create_update_timeline_events`; `crm_activities`, `crm_audit_logs`; `test_crm_activity_timeline_endpoint_and_system_events`.

---

Use Case Number: 8

Use Case Name: Sales user adds call note and follow-up task to lead.

User Role: Sales Executive

Business Scenario: Sales rep logs a call and schedules follow-up.

Steps to Test:
1. Open `/crm/leads/:id`.
2. Add note, call, and task quick actions.
3. Verify timeline and reminder/calendar visibility.
4. Verify notification if mentioned user is included.

Expected Result: Note/call/task persist, appear in timeline, reminder is visible, mentions notify users.

Actual Result: Related payload/timeline includes notes, activities, tasks, and system events. Mention notifications are tested. Reminder scheduler/push notification was not fully verified.

Status: Partially Passed

Bugs Found: Reminder delivery not fully verified.

Fix Applied: None.

Evidence: `test_crm_detail_payload_includes_related_records_and_timeline`, `test_crm_note_mentions_create_scoped_notifications`; `crm_notes`, `crm_activities`, `crm_tasks`, `notifications`.

---

Use Case Number: 9

Use Case Name: Sales user sends email/WhatsApp/SMS from CRM.

User Role: Sales Executive

Business Scenario: Sales rep communicates from CRM and needs logged delivery status.

Steps to Test:
1. Open record detail quick actions.
2. Send email via template.
3. Send WhatsApp and SMS.
4. Verify logs, timeline, validation, and delivery status.

Expected Result: Messages are sent or drafted, logged with delivery status, and visible in timeline.

Actual Result: Email template/draft send logs to timeline. WhatsApp/SMS template and send flow is tested with validation. Providers appear mocked/draft rather than production delivery.

Status: Partially Passed

Bugs Found: Production provider delivery not verified.

Fix Applied: None.

Evidence: `test_crm_email_templates_and_draft_send_log_to_timeline`, `test_crm_whatsapp_sms_templates_send_logs_and_timeline`; `crm_email_logs`, `crm_messages`, `crm_message_templates`.

---

Use Case Number: 10

Use Case Name: CRM detects duplicate lead/contact.

User Role: Sales Ops / CRM Admin

Business Scenario: Admin scans and merges duplicate contacts/leads.

Steps to Test:
1. Create duplicate records.
2. Open `/crm/duplicates`.
3. Call duplicate scan/list API.
4. Merge records.
5. Verify related records relink and audit trail.

Expected Result: Duplicates are detected, merge option works, related records relink, and audit/timeline is recorded.

Actual Result: Duplicate detection and merge are tested for contacts and unique custom fields; related deals, quotations, tasks relink; duplicate merge timeline is created; cross-org comparisons are blocked.

Status: Passed

Bugs Found: None.

Fix Applied: None.

Evidence: `test_crm_duplicate_detection_and_merge_relinks_related_records`, `test_crm_duplicate_detection_uses_custom_unique_fields_and_merges_values_safely`, `test_crm_duplicate_detection_never_compares_across_organizations`; `crm_contacts`, `crm_deals`, `crm_quotations`, `crm_tasks`.

---

Use Case Number: 11

Use Case Name: Sales user converts qualified lead to contact, company, and deal.

User Role: Sales Executive

Business Scenario: A qualified lead becomes an account, contact, and opportunity.

Steps to Test:
1. Create qualified lead.
2. Call `POST /api/v1/crm/leads/{id}/convert`.
3. Verify contact/company/deal creation.
4. Verify mapping and converted lead state.

Expected Result: Lead is converted and linked records are created correctly.

Actual Result: Lead conversion test verifies contact/company/deal creation, relationship mapping, and converted lead flag.

Status: Passed

Bugs Found: None.

Fix Applied: None.

Evidence: `test_crm_readiness_acceptance_flow_with_pipeline_quote_reports_and_audit`; `crm_leads`, `crm_contacts`, `crm_companies`, `crm_deals`, `crm_deal_contacts`.

---

Use Case Number: 12

Use Case Name: Sales user creates a new deal manually.

User Role: Sales Executive

Business Scenario: Sales rep creates an opportunity against an account/contact.

Steps to Test:
1. Open `/crm/deals`.
2. Create deal with company/contact, stage, amount, probability, expected close date.
3. Verify `POST /api/v1/crm/deals`.
4. Verify database, validation, RBAC, and audit.

Expected Result: Deal is created with valid links, owner, stage, amount/probability, and close date.

Actual Result: Deal creation is covered in readiness and pipeline tests. Pipeline/stage validation exists. UI route renders.

Status: Passed

Bugs Found: None.

Fix Applied: None.

Evidence: `POST /api/v1/crm/deals`; `test_crm_readiness_acceptance_flow_with_pipeline_quote_reports_and_audit`, `test_crm_multiple_pipelines_stage_management_and_remap`; Playwright `/crm/deals` indirect list calls through dashboard; `crm_deals`.

---

Use Case Number: 13

Use Case Name: Deal moves through pipeline stages.

User Role: Sales Executive

Business Scenario: Rep moves opportunity through Kanban stages.

Steps to Test:
1. Open `/crm/pipeline`.
2. Load `GET /api/v1/crm/deals/kanban`.
3. Move deal stage by patching stage/status.
4. Verify probability update, history, and stale warning.

Expected Result: Kanban drag/drop updates stage/probability and records stage history with stale warnings.

Actual Result: Kanban API and stage update logic exist; stage-change audit/timeline is tested. Browser route renders. Actual drag/drop interaction and stale deal warning as a hard workflow were not fully executed.

Status: Partially Passed

Bugs Found: Drag/drop stage movement not fully proven in browser.

Fix Applied: None.

Evidence: `GET /api/v1/crm/deals/kanban`; `PATCH /api/v1/crm/deals/{id}`; `crm_pipeline_stages`, `crm_deals`, `crm_audit_logs`; Playwright `/crm/pipeline`.

---

Use Case Number: 14

Use Case Name: Sales manager reviews sales pipeline dashboard.

User Role: Sales Manager

Business Scenario: Manager reviews total pipeline, stage-wise value, forecast, and overdue follow-ups.

Steps to Test:
1. Open `/crm` and `/crm/reports`.
2. Verify pipeline metrics and reports APIs.
3. Verify overdue follow-up data.
4. Verify manager permission filtering.

Expected Result: Dashboard shows accurate pipeline value, stage-wise value, forecast, and overdue follow-ups.

Actual Result: Dashboard and report APIs exist, sales funnel/revenue/win-loss reports are tested. Full manager hierarchy forecast and all dashboard math were not independently recalculated in UI.

Status: Partially Passed

Bugs Found: Dashboard forecast/overdue accuracy not fully verified end-to-end in UI.

Fix Applied: None.

Evidence: `GET /api/v1/crm/reports/sales-pipeline`, `monthly-revenue-forecast`, `follow-up-overdue`; `test_crm_readiness_acceptance_flow_with_pipeline_quote_reports_and_audit`.

---

Use Case Number: 15

Use Case Name: Sales user creates quotation from deal.

User Role: Sales Executive

Business Scenario: Sales rep creates a commercial quote from an opportunity.

Steps to Test:
1. Create deal/contact/company.
2. Create quotation and quotation items.
3. Generate PDF.
4. Verify tax, discount, terms, status, and timeline.

Expected Result: Quote persists with items/prices/taxes/discount/terms and generated PDF.

Actual Result: Quotation creation and PDF generation use persisted quote/account/contact/item data; timeline records PDF generation.

Status: Passed

Bugs Found: None.

Fix Applied: None.

Evidence: `test_crm_quotation_pdf_generation_uses_persisted_quote_data`; `crm_quotations`, `crm_quotation_items`; `GET /api/v1/crm/quotations/{id}/pdf`.

---

Use Case Number: 16

Use Case Name: Discount above threshold triggers approval.

User Role: Sales Manager / CFO

Business Scenario: High discount or high-value deal requires approval before final action.

Steps to Test:
1. Create high-value deal/discount.
2. Create approval workflow.
3. Submit approval.
4. Attempt final deal status before approval.
5. Approve/reject and retry.

Expected Result: Approval route identifies approver, blocks final action until approved, handles rejection.

Actual Result: CRM approval workflow submit/approve and final gate are tested. Rejection endpoint exists. Manager/CFO named routing was not proven; workflow is role/user/manager based rather than explicit CFO certification.

Status: Partially Passed

Bugs Found: CFO/manager-specific approval path not fully verified.

Fix Applied: None.

Evidence: `test_crm_approval_workflow_submit_approve_and_final_gate`; `crm_approval_workflows`, `crm_approval_requests`, `crm_approval_request_steps`.

---

Use Case Number: 17

Use Case Name: Approved quotation is emailed to customer.

User Role: Sales Executive

Business Scenario: Approved quote PDF is sent to customer and logged.

Steps to Test:
1. Generate quote PDF.
2. Send quote PDF email.
3. Verify PDF attachment, email log, timeline, and status.

Expected Result: Email sends with PDF attachment, communication timeline logs it, and quote status is updated.

Actual Result: Endpoint generates PDF and creates email draft/log with `pdfUrl`; timeline is updated. Real SMTP delivery and status change to sent/customer delivered were not proven.

Status: Partially Passed

Bugs Found: Production delivery not verified; endpoint returned draft status in test.

Fix Applied: None.

Evidence: `POST /api/v1/crm/quotations/{id}/send-pdf-email`; `test_crm_quotation_pdf_generation_uses_persisted_quote_data`; `crm_email_logs`.

---

Use Case Number: 18

Use Case Name: Deal is marked Closed Won.

User Role: Sales Executive

Business Scenario: Rep marks deal won after approval and quote acceptance.

Steps to Test:
1. Submit approval for final action.
2. Attempt `PATCH /api/v1/crm/deals/{id}` status `Won`.
3. Verify mandatory quote/project handoff fields and workflow trigger.

Expected Result: Closed Won requires mandatory handoff fields, records audit, and triggers downstream workflow.

Actual Result: Final status is blocked until CRM approval is approved; status `Won` persists after approval. Mandatory project handoff fields and downstream PMS trigger are not implemented.

Status: Partially Passed

Bugs Found: Won state does not require project handoff fields or create downstream workflow.

Fix Applied: None.

Evidence: `test_crm_approval_workflow_submit_approve_and_final_gate`; `_normalize_final_status`; `crm_deals`.

---

Use Case Number: 19

Use Case Name: Closed Won deal creates PMS project.

User Role: Sales Executive / Project Manager

Business Scenario: Closed Won deal should hand off to delivery with project template, milestones, and budget.

Steps to Test:
1. Mark deal Closed Won.
2. Search for CRM-to-PMS project creation path.
3. Verify customer link, project template, milestones, budget, owner.

Expected Result: PMS project is created and linked to CRM customer/deal/quote.

Actual Result: No code path found that creates a PMS project from a won CRM deal. CRM Lead-to-Cash UI mentions order/invoice/project handoff conceptually, but backend implementation was not found.

Status: Not Implemented

Bugs Found: Feature missing.

Fix Applied: None.

Evidence: Code search for Closed Won/project/PMS handoff; `CRM_PMS_INVOICE_FLOW_VERIFICATION_REPORT.md` also records this as not implemented.

---

Use Case Number: 20

Use Case Name: Deal is marked Closed Lost.

User Role: Sales Executive

Business Scenario: Rep marks deal lost with reason and competitor for analysis.

Steps to Test:
1. Patch deal status to Lost.
2. Include lost reason and competitor.
3. Verify mandatory validation and win/loss report.

Expected Result: Lost reason and competitor are mandatory and appear in lost-deal reports.

Actual Result: Lost reason is stored and included in win/loss report; competitor breakdown supports custom fields. Mandatory lost reason was not proven/enforced.

Status: Partially Passed

Bugs Found: Lost reason/competitor mandatory validation not proven.

Fix Applied: None.

Evidence: `test_crm_win_loss_reports_are_organization_scoped`; `crm_deals.lost_reason`; `_competitor_breakdown`.

---

Use Case Number: 21

Use Case Name: Sales sequence/cadence runs for a lead.

User Role: Sales Executive

Business Scenario: Lead is enrolled in automated sequence that schedules emails and follow-ups.

Steps to Test:
1. Open `/crm/automation`.
2. Search for cadence/sequence backend APIs.
3. Verify scheduled email/follow-up/reminder creation.

Expected Result: Sequence engine creates scheduled email/follow-up/reminders and prevents duplicates.

Actual Result: `/crm/automation` renders a sales automation page, but no concrete sequence/cadence engine or APIs were found.

Status: Not Implemented

Bugs Found: Feature missing beyond UI concept.

Fix Applied: None.

Evidence: Code search for sequence/cadence; `SalesAutomationPage` in `CRMWorkspacePage.tsx`.

---

Use Case Number: 22

Use Case Name: Sales manager sets monthly quota for sales user.

User Role: Sales Manager

Business Scenario: Manager sets target quota and compares achieved revenue.

Steps to Test:
1. Open `/crm/forecasting`.
2. Search for quota models/APIs.
3. Verify quota creation and dashboard comparison.

Expected Result: Monthly quota persists and appears in quota-vs-achieved dashboard.

Actual Result: Forecasting UI contains quota-style text/metrics, but no persisted quota API/model was found.

Status: Not Implemented

Bugs Found: Persisted quota management missing.

Fix Applied: None.

Evidence: Code search for quota; `ForecastingPage` is frontend-only/static over deals.

---

Use Case Number: 23

Use Case Name: Sales forecast rollup works.

User Role: Sales Manager / Business Owner

Business Scenario: Owner reviews user, manager, team, and branch forecast.

Steps to Test:
1. Open `/crm/forecasting` and `/crm/reports`.
2. Call monthly revenue forecast and salesperson performance reports.
3. Verify rollups by owner/team/branch.

Expected Result: Forecast rollup works by user, manager, team, and branch.

Actual Result: Monthly revenue forecast and salesperson performance report exist and are permission filtered. Team/manager/branch hierarchy rollup was not fully implemented/proven.

Status: Partially Passed

Bugs Found: Branch/team rollup not fully verified.

Fix Applied: None.

Evidence: `monthly_revenue_forecast_report`, `salesperson_performance_report`; `crm_deals.owner_user_id`.

---

Use Case Number: 24

Use Case Name: CRM customer 360 page opens for a customer.

User Role: Sales / Support / Business Owner

Business Scenario: User opens one customer view with related CRM and cross-module activity.

Steps to Test:
1. Open `/crm/customer-360`.
2. Verify CRM companies/contacts/deals/quotes/tasks/communications/files.
3. Verify PMS/invoices/documents/approvals.
4. Verify permissions and leakage.

Expected Result: 360 shows CRM, PMS, invoice, task, communication, document, approval data with no leakage.

Actual Result: UI route renders and CRM related data paths exist for contacts, companies, deals, tasks, activities, quotations, files, and campaigns. Cross-module PMS/invoice/Approval OS data was not implemented in Customer 360.

Status: Partially Passed

Bugs Found: Cross-module Customer 360 incomplete.

Fix Applied: None.

Evidence: `Customer360Page`; CRM related endpoint; Playwright `/crm/customer-360` desktop/mobile; `CUSTOMER_360_GLOBAL_SEARCH_VERIFICATION_REPORT.md`.

---

Use Case Number: 25

Use Case Name: CRM global search finds lead, contact, company, deal, quote.

User Role: CRM Roles

Business Scenario: User searches globally and sees only permitted CRM records.

Steps to Test:
1. Use global search.
2. Search lead/contact/company/deal/quote.
3. Verify permission filtering and quick actions.

Expected Result: Global search returns CRM records with RBAC filtering and no unauthorized records.

Actual Result: CRM entity list search exists per module. Global search component is route/page oriented and HRMS report search exists, but no CRM record-wide global search API was found.

Status: Not Implemented

Bugs Found: CRM record global search missing.

Fix Applied: None.

Evidence: `frontend/src/components/app/GlobalSearch.tsx`; `reportsApi.globalSearch`; CRM list search API only.

---

Use Case Number: 26

Use Case Name: Sales user tries to access restricted admin/settings page.

User Role: Sales Executive

Business Scenario: Salesperson attempts to open CRM admin/settings.

Steps to Test:
1. Open `/crm/admin` as `crm_sales_executive`.
2. Open `/crm/settings` as `crm_sales_executive`.
3. Verify UI route block.
4. Verify backend admin/manage API requirements.

Expected Result: UI route and backend API are both blocked.

Actual Result: Initial verification found frontend CRM route guard allowed every CRM role to every CRM route. Backend admin/manage API permissions were stricter. Fix applied to block sales users from CRM admin/settings/security routes while preserving `/crm/leads`.

Status: Passed

Bugs Found: High - frontend CRM route RBAC was too broad.

Fix Applied: Updated `frontend/src/lib/roles.ts` with CRM admin/manager path restrictions and filtered CRM nav. Verified by build and Playwright RBAC smoke.

Evidence: `frontend/src/lib/roles.ts`; Playwright: sales executive allowed `/crm/leads`, denied `/crm/admin` and `/crm/settings`, CRM org admin allowed `/crm/admin`; `npm run build` passed.

---

Use Case Number: 27

Use Case Name: CRM custom field is created by admin and appears in lead/deal form.

User Role: CRM Admin

Business Scenario: Admin adds a required custom field and sales users save values.

Steps to Test:
1. Open `/crm/settings`.
2. Create custom field.
3. Save custom value on lead/deal.
4. Verify validation and reporting visibility.

Expected Result: Custom field persists, validates required/unique values, and saves values.

Actual Result: Backend tests verify custom field values persist, are org-scoped, required validation is enforced, and unique duplicate conflicts are handled. UI settings route renders for admin roles.

Status: Passed

Bugs Found: None.

Fix Applied: RBAC route fix protects settings from sales users.

Evidence: `test_crm_custom_field_values_are_persisted_and_org_scoped`; `crm_custom_fields`, `crm_custom_field_values`; `/crm/settings`.

---

Use Case Number: 28

Use Case Name: CRM report is generated and exported.

User Role: Sales Manager / CRM Admin

Business Scenario: Manager exports CRM report for review.

Steps to Test:
1. Open `/crm/reports`.
2. Run reports with filters.
3. Export data.
4. Verify accuracy and permission control.

Expected Result: Report filters are accurate, export works, and permissions are enforced.

Actual Result: Win/loss, sales funnel, revenue trend, lead source, conversion, stage, salesperson performance, overdue follow-up, and territory reports exist. Generic entity export exists. Full report export workflow from UI was not proven.

Status: Partially Passed

Bugs Found: Dedicated report export UX not fully proven.

Fix Applied: None.

Evidence: CRM report endpoints in router; `test_crm_win_loss_reports_are_organization_scoped`; `GET /api/v1/crm/{entity}/export`.

---

Use Case Number: 29

Use Case Name: Email/calendar sync setup is tested.

User Role: Sales User / CRM Admin

Business Scenario: User connects calendar provider and syncs meetings.

Steps to Test:
1. Open `/crm/calendar-integrations`.
2. Connect mock/Google/Microsoft provider.
3. Sync meeting.
4. Verify status, logs, failures, labels.

Expected Result: Google/Microsoft setup screens exist, status visible, failures logged, mock clearly labelled.

Actual Result: Calendar integration page renders and explicitly shows Google/Microsoft readiness text. Backend supports mock, google, outlook token placeholders and meeting sync. Production OAuth exchange/failure logging was not fully verified.

Status: Partially Passed

Bugs Found: Production Google/Microsoft connector readiness not certified.

Fix Applied: None.

Evidence: `test_crm_calendar_integrations_and_meeting_sync`; `calendar_integrations`, `crm_meetings`; Playwright `/crm/calendar-integrations`.

---

Use Case Number: 30

Use Case Name: Mobile CRM view is tested.

User Role: Sales Executive

Business Scenario: Salesperson uses CRM on mobile to review leads, notes, follow-up, and communication actions.

Steps to Test:
1. Open `/crm/leads`, `/crm/customer-360`, `/crm/quotations` at `390x844`.
2. Verify content renders without overlay/console errors.
3. Check lead/detail/add note/follow-up/call/email actions and offline queue if implemented.

Expected Result: Mobile lead list/detail/actions work; offline queue works if implemented.

Actual Result: Playwright verified mobile rendering for leads, Customer 360, and quotations with no console errors. Offline queue was not found; mobile action execution was not fully completed in browser.

Status: Partially Passed

Bugs Found: Offline/queued action support not implemented/proven; mobile action execution not fully verified.

Fix Applied: None.

Evidence: Playwright mobile route smoke; `CRMRecordDetailPage` quick actions; no offline queue code found.

