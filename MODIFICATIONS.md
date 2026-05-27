# Business Suite — 10 Modifications Per Module

Generated: 2026-05-23  
Principle: Each module must be fully standalone. Only **2 shared tables** (`users`, `audit_logs`) and **1 shared CSS token file** are allowed. Integration between modules is possible via an optional event-bridge, never via direct FK cross-module joins.

---

## Independence Architecture (First, Read This)

### What Is Shared (Absolute Minimum)

| Shared Asset | Why It Must Be Shared |
|-------------|----------------------|
| `users` table | Single login identity across the suite; contains `id`, `email`, `password_hash`, `role`, `is_active` only |
| `audit_logs` table | Platform-level immutable audit trail; all modules write to it with a `module` column |
| `design-tokens.css` | One CSS file of color/typography/spacing variables. Modules import this; everything else is module-local |

### What Must Be Made Module-Local

| Currently Shared | Move To |
|-----------------|---------|
| `roles`, `permissions`, `role_permissions` | Each module gets `crm_roles`, `pms_roles`, `hrms_roles` with its own permission set |
| `notifications` table | `crm_notifications`, `pms_notifications`, `hrms_notifications` — each module manages its own |
| `workflow_engine` tables | Each module embeds its own lightweight approval engine rather than sharing one |
| `custom_fields` definitions | Module-prefixed: `crm_custom_fields`, `pms_custom_fields`, `hrms_custom_fields` |
| `platform.py` config model | Split into per-module config tables |

### Integration Bridge (Optional, Loosely Coupled)

When multiple modules are installed together, an event bridge allows cross-module automation without direct FK dependencies:

```
integration_events table:
  id, source_module, event_type, source_id, payload (JSON), consumed_by, consumed_at
```

Examples:
- CRM fires `deal.won` → PMS creates a project from template
- HRMS fires `employee.joined` → CRM creates a contact record  
- HRMS fires `employee.left` → PMS auto-reassigns open tasks
- PMS fires `project.completed` → CRM updates deal status to delivered

This one table is the **only cross-module coupling point** beyond `users` and `audit_logs`.

---

## Module 1: CRM — 10 Modifications

### CRM-M1: Module-Local Role & Permission System

**What:** Replace dependency on shared `roles`/`permissions` tables with `crm_roles` and `crm_permissions` tables. Define CRM-specific roles (`crm_admin`, `crm_manager`, `crm_rep`, `crm_viewer`) inside the CRM module.

**Why:** Currently CRM inherits the HRMS role model, which includes HR concepts (`hr_manager`, `payroll_manager`) that mean nothing in a CRM-only deployment. Removing this makes CRM deployable without HRMS.

**New Tables:**
```sql
crm_roles         (id, name, description, created_at)
crm_permissions   (id, name, resource, action)
crm_role_perms    (role_id, permission_id)
crm_user_roles    (user_id, role_id, assigned_at)
```

**Integration hook:** When HRMS is present, a sync adapter can map HRMS employee roles to CRM roles on login. Without HRMS, roles are managed inside CRM settings.

---

### CRM-M2: Invoice & Payment Tracking (Complete Lead-to-Cash)

**What:** Extend quotations into a full invoice-to-payment cycle. A won deal → quotation accepted → invoice raised → payment tracked.

**Why:** Currently the pipeline ends at quotation. Sales teams need to track what's been invoiced and what's been paid without going to a separate accounting tool.

**New Tables:**
```sql
crm_invoices        (id, deal_id, quotation_id, invoice_number, status, issued_date, due_date, total_amount, currency)
crm_invoice_items   (id, invoice_id, description, quantity, unit_price, tax_pct, line_total)
crm_payments        (id, invoice_id, payment_date, amount, method, reference, notes)
crm_credit_notes    (id, invoice_id, reason, amount, issued_date)
```

**Frontend route:** `/crm/invoices`, `/crm/invoices/:id`

**Integration hook:** When PMS is present, a paid invoice can auto-update project billing status via the integration event bridge.

---

### CRM-M3: Two-Way Email Inbox

**What:** Native email inbox inside CRM that syncs with Gmail / Outlook via IMAP/OAuth. Sales reps send and receive emails without leaving CRM. All threads automatically linked to contacts and deals.

**Why:** Currently CRM logs sent emails but has no inbox; reps switch between Gmail and CRM constantly, losing context and creating data gaps.

**New Tables:**
```sql
crm_email_accounts  (id, user_id, provider, email_address, oauth_token, sync_status, last_synced_at)
crm_email_threads   (id, account_id, thread_id_external, subject, participants, linked_contact_id, linked_deal_id)
crm_email_messages  (id, thread_id, message_id_external, from_address, direction, body_html, sent_at, is_read)
```

**Frontend route:** `/crm/inbox`, `/crm/inbox/:threadId`

---

### CRM-M4: Subscription & Contract Renewal Management

**What:** Track recurring contracts: start date, renewal date, MRR/ARR value, auto-renewal flag, churn risk score. Automated renewal reminders to account owners.

**Why:** CRM closes deals but forgets them. For SaaS or retainer businesses, the majority of revenue is renewals — which are invisible in the current system.

**New Tables:**
```sql
crm_subscriptions       (id, deal_id, account_id, plan_name, billing_cycle, mrr, arr, start_date, renewal_date, auto_renew, status)
crm_renewal_reminders   (id, subscription_id, reminder_days_before, last_sent_at, assignee_id)
crm_churn_signals       (id, subscription_id, signal_type, signal_value, recorded_at)
```

**Frontend route:** `/crm/subscriptions`, `/crm/renewals`

---

### CRM-M5: Multi-Step Email Sequencer

**What:** Automated outreach sequences — a named cadence of steps (email D+0, call D+3, WhatsApp D+7, email D+10). Leads/contacts enrolled in a sequence and steps execute automatically or as reminders.

**Why:** Currently only single-message templates exist. Sales reps manage follow-up manually in sticky notes. A sequencer turns best-practice outreach into a repeatable process.

**New Tables:**
```sql
crm_sequences           (id, name, description, entity_type, created_by, is_active)
crm_sequence_steps      (id, sequence_id, step_order, step_type, delay_days, template_id, subject_override)
crm_sequence_enrollments(id, sequence_id, entity_id, entity_type, current_step, enrolled_at, completed_at, status)
crm_sequence_step_logs  (id, enrollment_id, step_id, executed_at, outcome)
```

**Frontend route:** `/crm/sequences`, `/crm/sequences/:id`

---

### CRM-M6: Customer Health Score (Post-Sale)

**What:** After a deal is won, track ongoing customer health using configurable signals (support ticket volume, product usage, payment history, engagement). Auto-flag at-risk accounts.

**Why:** Sales focus ends at deal close. Without health tracking, customer success is reactive — churn is noticed only after it happens.

**New Tables:**
```sql
crm_health_metrics      (id, name, weight, source, aggregation_method)
crm_health_scores       (id, account_id, computed_score, grade, computed_at, breakdown JSON)
crm_health_signals      (id, account_id, metric_id, signal_value, recorded_at)
```

**Frontend route:** `/crm/customer-health`, visible in `/crm/customer-360`

---

### CRM-M7: Meeting Intelligence (AI Summaries + Action Items)

**What:** After a meeting is logged, AI auto-generates a summary, extracts action items, and creates CRM tasks for each action item. Sales managers get a digest of all meeting outcomes.

**Why:** Meeting notes are the most inconsistently filled field in any CRM. AI extraction removes the discipline requirement and ensures follow-up doesn't fall through cracks.

**Schema change:** Extend `CRMMeeting`:
```sql
ALTER TABLE crm_meetings ADD COLUMN transcript_text TEXT;
ALTER TABLE crm_meetings ADD COLUMN ai_summary TEXT;
ALTER TABLE crm_meetings ADD COLUMN action_items_json JSON;
ALTER TABLE crm_meetings ADD COLUMN intelligence_status VARCHAR(20);
```

**New API:** `POST /crm/meetings/{id}/extract-intelligence`

---

### CRM-M8: Document E-Sign Workflow

**What:** Send quotations and contracts for e-signature directly from CRM. Track signature status (sent, viewed, signed, declined). Store signed PDFs against the deal record.

**Why:** Currently quotations are PDFs emailed externally and signed via third-party tools. There is no status visibility inside CRM — sales ops doesn't know if a contract has been signed.

**New Tables:**
```sql
crm_esign_requests  (id, document_type, document_id, signer_email, signer_name, provider, status, sent_at, signed_at, document_url)
crm_esign_events    (id, request_id, event_type, occurred_at, metadata JSON)
```

**Providers:** DocuSign, Adobe Sign, DigiSigner (via webhook callbacks)  
**Frontend route:** Inline in `/crm/quotations/:id` and `/crm/deals/:id`

---

### CRM-M9: Module-Local Notification Engine

**What:** Replace dependency on shared `notifications` table with `crm_notifications` that has CRM-specific event types, channel routing (email/in-app/WhatsApp), and per-user preferences stored in `crm_notification_preferences`.

**Why:** Currently CRM writes to the shared HRMS notification table. In a CRM-only deployment, that table doesn't exist. CRM needs its own notification stack.

**New Tables:**
```sql
crm_notifications           (id, user_id, event_type, title, body, entity_type, entity_id, is_read, created_at)
crm_notification_preferences(id, user_id, event_type, email_enabled, inapp_enabled, whatsapp_enabled)
crm_notification_queue      (id, notification_id, channel, status, attempts, last_attempted_at, sent_at)
```

---

### CRM-M10: AI Deal Coach

**What:** A persistent AI assistant scoped to each deal that reads the full deal history (activities, emails, notes, stage changes) and proactively offers coaching: "This deal has been stuck in Proposal for 14 days — here are 3 actions that worked on similar deals."

**Why:** The current AI assistant is module-wide and reactive (user asks, it answers). A deal-specific proactive coach uses the full deal context to surface insights reps would otherwise miss.

**New Table:**
```sql
crm_deal_ai_insights (id, deal_id, insight_type, insight_text, confidence, generated_at, is_dismissed, dismissed_by)
```

**New API:** `GET /crm/deals/{id}/ai-insights`, `POST /crm/deals/{id}/ai-insights/dismiss/{insightId}`  
**Frontend:** Inline panel in `/crm/deals/:id`

---

## Module 2: PMS — 10 Modifications

### PMS-M1: Module-Local Member & Role System

**What:** Replace dependency on shared `users`/`roles` with `pms_workspace_members` and `pms_roles` (`pms_admin`, `pms_manager`, `pms_lead`, `pms_member`, `pms_viewer`, `pms_client`). Allow external contractors and clients to be added as workspace members without needing a system user account.

**Why:** Currently PMS members must exist in the `users` table — which requires an HRMS record. In a PMS-only deployment, you can't add a freelancer or client without creating an HRMS employee record. This breaks independence.

**New Tables:**
```sql
pms_workspace_members (id, user_id NULLABLE, guest_email, guest_name, role_id, workspace_id, invited_at, joined_at, is_active)
pms_roles             (id, name, permissions_json)
pms_workspace         (id, name, slug, owner_user_id, created_at)
```

---

### PMS-M2: Project Budget & Expense Tracker

**What:** Full budget management per project: define planned budget (phases, categories), log actual expenses, track burn rate, and generate budget health reports.

**Why:** Currently `PMSProject` has a `budget` field (single number) but no breakdown or actual expense tracking. Project managers flying blind on spend is a top complaint in project management tools.

**New Tables:**
```sql
pms_budget_lines    (id, project_id, category, phase, planned_amount, currency)
pms_expenses        (id, project_id, budget_line_id, submitted_by, description, amount, expense_date, receipt_url, status, approved_by)
pms_budget_snapshots(id, project_id, snapshot_date, planned_total, actual_total, forecast_total)
```

**Frontend route:** `/pms/projects/:projectId/budget`

**Integration hook:** When CRM is present, a `crm_invoice.paid` event can update `pms_budget_lines.actual_amount` automatically.

---

### PMS-M3: Code Repository Integration

**What:** Connect GitHub or GitLab repositories to PMS projects. Link commits and pull requests to tasks. Auto-transition tasks when a PR is merged. Show code activity on sprint boards.

**Why:** Engineering teams use Git as their source of truth but manually update task status. A Git integration collapses two tools into one workflow and gives managers real delivery visibility.

**New Tables:**
```sql
pms_repo_integrations (id, project_id, provider, repo_url, webhook_secret, access_token_enc, created_at)
pms_commits           (id, integration_id, commit_sha, message, author_email, committed_at, linked_task_id)
pms_pull_requests     (id, integration_id, pr_number, title, state, author_email, opened_at, merged_at, linked_task_id)
```

**Webhook endpoint:** `POST /pms/integrations/git-webhook`  
**Frontend:** Git tab on task detail (`/pms/tasks/:taskId`)

---

### PMS-M4: Meeting Notes & Action Items

**What:** Structured meeting notes per project or sprint. Every meeting has a template (agenda, attendees, decisions, action items). Action items become PMS tasks automatically. AI can summarize discussion bullets.

**Why:** Project decisions made in meetings are invisible in the current system — they live in email threads. Capturing them in PMS closes the loop between conversation and execution.

**New Tables:**
```sql
pms_meeting_notes   (id, project_id, sprint_id NULLABLE, title, meeting_date, attendee_ids JSON, agenda TEXT, notes TEXT, ai_summary TEXT, created_by)
pms_action_items    (id, meeting_note_id, description, assignee_id, due_date, linked_task_id NULLABLE, status)
```

**Frontend route:** `/pms/projects/:projectId/meetings`, inline on sprint review

---

### PMS-M5: OKR Module (Objectives & Key Results)

**What:** Define company/team OKRs. Link epics and projects to key results. Track progress automatically as tasks are completed. Provide a strategy-to-execution alignment view.

**Why:** Currently PMS tracks execution (tasks, sprints) but has no connection to strategic goals. Teams work hard without visibility into whether their work moves the needle on what matters.

**New Tables:**
```sql
pms_objectives      (id, workspace_id, owner_id, title, time_period, status, progress_pct)
pms_key_results     (id, objective_id, title, target_value, current_value, unit, progress_pct)
pms_okr_links       (id, key_result_id, linked_type, linked_id)   -- linked_type: project|epic|task
pms_okr_check_ins   (id, key_result_id, checked_by, value_at_checkin, note, checked_at)
```

**Frontend route:** `/pms/okrs`, linked from project dashboard  
**Integration hook:** When HRMS is present, OKR progress feeds into performance appraisal as evidence.

---

### PMS-M6: Project Template Library

**What:** Save any project as a reusable template (board columns, epics, standard task types, sprint structure, roles). When creating a new project, pick a template. Templates can be shared across workspaces.

**Why:** Every software project, marketing campaign, or product launch follows roughly the same structure. Currently each new project starts blank, wasting setup time and creating inconsistency.

**New Tables:**
```sql
pms_templates           (id, name, description, category, created_by, is_public, version)
pms_template_epics      (id, template_id, title, description, order)
pms_template_tasks      (id, template_epic_id, title, task_type, estimate, labels JSON)
pms_template_columns    (id, template_id, name, order, wip_limit)
pms_template_roles      (id, template_id, role_name, permissions JSON)
```

**Frontend route:** `/pms/templates` (library), `/pms/projects/new` (template picker)

---

### PMS-M7: Resource Availability & Open Assignment Board

**What:** A board where managers post open tasks/roles they need filled. Team members with matching skills self-assign. Shows availability calendar (busy/free) per member.

**Why:** Currently workload management is top-down only (manager assigns). In organizations with many parallel projects, a self-service assignment board surfaces capacity that managers can't see.

**New Tables:**
```sql
pms_member_availability (id, member_id, date, available_hours, is_blocked, block_reason)
pms_open_assignments    (id, task_id, skills_required JSON, posted_by, posted_at, claimed_by NULLABLE, claimed_at NULLABLE)
pms_member_skills       (id, member_id, skill_name, level)
```

**Integration hook:** When HRMS is present, `pms_member_availability` syncs from HRMS approved leave via the event bridge (no direct FK).

---

### PMS-M8: Client Deliverable Approval Workflow

**What:** Define deliverables per project milestone. Share specific deliverables with clients through the client portal. Clients approve or request revisions. Approval status is tracked on the project timeline.

**Why:** Currently the client portal is read-only. Clients can see progress but cannot participate in formal acceptance. This forces approval conversations back to email, losing traceability.

**New Tables:**
```sql
pms_deliverables        (id, project_id, milestone_id NULLABLE, title, description, file_url, status, submitted_at, submitted_by)
pms_client_approvals    (id, deliverable_id, client_member_id, decision, comments, decided_at)
pms_revision_requests   (id, deliverable_id, requested_by, description, requested_at, resolved_at)
```

**Frontend route:** `/pms/projects/:projectId/deliverables` (internal), `/pms/client-portal/deliverables` (client view)

---

### PMS-M9: Advanced Reporting Dashboard (Configurable Widgets)

**What:** A fully configurable reporting canvas per project or workspace. Drag-and-drop widgets: velocity chart, cost-per-story-point, on-time delivery %, team efficiency, sprint comparison, cumulative flow diagram. Exportable to PDF/Excel.

**Why:** Current reports (`/pms/reports`) are static. Every project manager needs different views of health — a configurable dashboard removes the need for external BI tools.

**New Tables:**
```sql
pms_dashboards      (id, name, owner_id, scope_type, scope_id, is_default)
pms_dashboard_widgets(id, dashboard_id, widget_type, config JSON, position_x, position_y, width, height)
pms_report_snapshots(id, dashboard_id, snapshot_date, data JSON)
```

**Frontend route:** `/pms/dashboards`, `/pms/projects/:projectId/dashboard`

---

### PMS-M10: Module-Local Notification Engine

**What:** Decouple from shared `notifications` table. Build `pms_notifications` with PMS-specific events (task overdue, sprint ending, blocked task, milestone at risk, client approval received) and per-user channel preferences.

**Why:** In a PMS-only deployment, the shared HRMS notification table doesn't exist. PMS needs its own notification pipeline so it can run standalone.

**New Tables:**
```sql
pms_notifications           (id, user_id, workspace_id, event_type, title, body, entity_type, entity_id, is_read, created_at)
pms_notification_preferences(id, user_id, event_type, email_enabled, inapp_enabled, push_enabled)
pms_notification_queue      (id, notification_id, channel, status, attempts, sent_at)
```

---

## Module 3: HRMS — 10 Modifications

### HRMS-M1: Compensation Benchmarking Module

**What:** Import external salary survey data (cut-and-paste or upload). Compare each designation's current pay band against market percentiles (P25, P50, P75, P90). Show compa-ratio per employee. Flag employees paid below market.

**Why:** HR knows salaries are below market when people resign. Benchmarking moves compensation from reactive to proactive. Currently there is no internal salary benchmarking — only the pay structure itself.

**New Tables:**
```sql
hrms_market_surveys         (id, survey_name, survey_year, source, uploaded_at, uploaded_by)
hrms_market_salary_data     (id, survey_id, job_title, industry, location, p25, p50, p75, p90, currency)
hrms_comp_band_analysis     (id, designation_id, survey_id, compa_ratio_p50, above_market_pct, below_market_count, computed_at)
hrms_employee_compa_ratios  (id, employee_id, computed_at, current_ctc, market_p50, compa_ratio, variance_pct)
```

**Frontend route:** `/hrms/compensation-benchmarking`

---

### HRMS-M2: Internal Skills Marketplace (Gig Board)

**What:** Employees register their skills and availability for internal projects. Managers post internal gig opportunities (short-term assignments, project support, cross-functional tasks). Employees apply; manager shortlists. HR approves dual-allocation.

**Why:** Organizations have hidden talent. An internal gig board surfaces skills that managers across departments don't know exist, reducing external hiring for short-term needs.

**New Tables:**
```sql
hrms_employee_skills_profile (id, employee_id, skill_name, level, certified, last_used_date)
hrms_internal_gigs           (id, department_id, posted_by, title, description, skills_required JSON, duration_weeks, start_date, slots, status)
hrms_gig_applications        (id, gig_id, employee_id, cover_note, applied_at, status, reviewed_by, reviewed_at)
hrms_dual_allocations        (id, employee_id, gig_id, start_date, end_date, hours_per_week, approved_by)
```

**Frontend route:** `/hrms/skills-marketplace`

**Integration hook:** When PMS is present, approved dual allocations automatically add the employee as a PMS workspace member via the event bridge.

---

### HRMS-M3: Employee Wellness & Mental Health Module

**What:** Anonymous mood/sentiment pulse (weekly 1-click check-in). EAP (Employee Assistance Programme) resource directory. Wellness challenge tracker (steps, hydration, meditation). Manager alert for sustained low-sentiment patterns (anonymized, aggregated — never individual).

**Why:** Employee mental health is now a compliance and retention issue. HR has no early warning signal currently. Even a simple weekly pulse catches trends before they become attrition events.

**New Tables:**
```sql
hrms_wellness_programs      (id, name, type, description, start_date, end_date, is_active)
hrms_wellness_enrollments   (id, program_id, employee_id, enrolled_at, progress_pct, streak_days)
hrms_sentiment_pulses       (id, employee_id, response_date, score_1_to_5, anonymous_token, department_id)
hrms_eap_resources          (id, category, title, url, description, is_external)
hrms_sentiment_dept_summary (id, department_id, week_start, avg_score, response_count, low_count)
```

**Frontend route:** `/hrms/wellness`  
**Note:** `sentiment_pulses` stores individual employee_id only for deduplication; aggregated reporting anonymizes all outputs.

---

### HRMS-M4: Matrix Reporting & Dotted-Line Structure

**What:** Support dual reporting lines — a primary manager (solid line) and one or more functional/project managers (dotted line). Approval workflows, performance reviews, and leave approvals route to the correct manager based on context.

**Why:** Current Employee model has a single `reporting_manager_id`. Matrix organizations (common in IT and consulting) have functional managers separate from admin managers. This affects leave approvals, performance reviews, and project billing.

**Schema changes:**
```sql
-- Extend employees table
ALTER TABLE employees ADD COLUMN functional_manager_id BIGINT REFERENCES employees(id);
ALTER TABLE employees ADD COLUMN reporting_type ENUM('solid','matrix','dual') DEFAULT 'solid';

-- New table for multiple dotted-line relationships
hrms_dotted_line_managers (id, employee_id, manager_id, context, effective_from, effective_to, is_active)

-- Routing rules: which manager gets which approval type
hrms_approval_routing_rules (id, entity_type, condition JSON, route_to ENUM('solid_line','dotted_line','both'), priority)
```

---

### HRMS-M5: Shift Bidding & Open Shift Marketplace

**What:** Managers post open shifts. Eligible employees receive a notification and can bid (claim) the shift. Manager approves one bid. Employees can also propose shift swaps — peer swap requires both employees' consent plus manager approval.

**Why:** Current shift roster is top-down assignment only. In operations-heavy environments (BPO, retail, hospitality), shift flexibility reduces absenteeism. Employees feel agency; managers get coverage without micromanagement.

**New Tables:**
```sql
hrms_open_shifts    (id, branch_id, department_id, shift_id, shift_date, slots_available, posted_by, deadline, status)
hrms_shift_bids     (id, open_shift_id, employee_id, bid_at, status, reviewed_by, reviewed_at)
hrms_shift_swaps    (id, requester_id, target_id, requester_shift_date, target_shift_date, reason, status, manager_approved_by, approved_at)
```

**Frontend route:** `/hrms/shift-marketplace`, visible on `/hrms/attendance/shift-roster`

---

### HRMS-M6: Real-Time Payroll Simulator

**What:** A sandbox "what-if" calculator where HR can simulate: salary revision impact, new deduction addition, tax regime change, or component restructure for one or many employees — and see net impact on take-home, tax, and employer cost without running an actual payroll.

**Why:** Currently HR must request payroll runs or build Excel models outside the system to estimate impact of salary changes. This leads to errors in offer letters and revision letters. A simulator removes the Excel dependency.

**No new permanent tables needed.** Uses existing salary structure and tax rules with a `simulation_mode=true` flag in the calculation engine. Results stored temporarily in:
```sql
hrms_payroll_simulations (id, created_by, name, employee_ids JSON, changes JSON, result_snapshot JSON, created_at, expires_at)
```

**Frontend route:** `/hrms/payroll-simulator` (accessible from `/hrms/payroll`)

---

### HRMS-M7: Government Portal Connectors

**What:** Direct API/file submission to Indian government portals: EPFO (PF ECR upload), ESIC (ESI challan), TRACES (24Q / TDS), PT challan portals. Track submission status, acknowledgement numbers, and failure reasons.

**Why:** Currently compliance exports generate files that HR manually uploads to government portals. This is error-prone and untraceable. API integration removes manual upload and gives audit trail inside HRMS.

**New Tables:**
```sql
hrms_govt_portals           (id, portal_name, portal_type, endpoint_url, auth_type, credentials_enc, is_active)
hrms_govt_submissions       (id, portal_id, submission_type, period, file_path, submitted_at, submitted_by, status, ack_number, response_json, next_retry_at)
hrms_submission_error_logs  (id, submission_id, error_code, error_message, occurred_at)
```

**Frontend route:** `/hrms/govt-submissions` (accessible from `/hrms/statutory-compliance`)

---

### HRMS-M8: Recognition & Rewards Points Store

**What:** Extend the engagement module with a points-based recognition system. Managers award points with a reason. Employees accumulate points and redeem them in a rewards catalog (gift vouchers, extra leave, merchandise). HR configures the catalog and point budgets.

**Why:** Current recognition wall has reactions but no tangible rewards. Research shows points-based recognition with redemption increases participation by 3-5x. This also provides HR an engagement lever that doesn't require budget approval for each award.

**New Tables:**
```sql
hrms_reward_programs    (id, name, points_per_award_range, monthly_budget_per_manager, active_from, active_to)
hrms_reward_points      (id, employee_id, awarded_by, program_id, points, reason, recognition_post_id NULLABLE, awarded_at)
hrms_reward_catalog     (id, item_name, description, image_url, points_cost, stock_qty NULLABLE, item_type, is_active)
hrms_reward_redemptions (id, employee_id, catalog_item_id, points_spent, status, requested_at, fulfilled_at, fulfillment_ref)
hrms_points_balances    (id, employee_id, total_earned, total_redeemed, current_balance, last_updated)
```

**Frontend route:** `/hrms/rewards-store` (employee), rewards section in `/hrms/engagement` (manager/HR)

---

### HRMS-M9: AI-Powered Interview Intelligence

**What:** Structured interview scorecards per job role with role-specific questions. Interviewers fill scorecards in app. AI detects potential bias phrases in written feedback and suggests neutral alternatives. Auto-ranks candidates per scorecard scores. Panel debrief with aggregated scores.

**Why:** Currently recruitment tracks applications and offers but interview quality is invisible. Scorecards ensure structured evaluation; bias detection protects the company from discriminatory hiring patterns.

**New Tables:**
```sql
hrms_interview_scorecards   (id, job_opening_id, name, competencies JSON, created_by)
hrms_scorecard_questions    (id, scorecard_id, competency, question_text, weight, response_type)
hrms_interview_evaluations  (id, application_id, scorecard_id, interviewer_id, interview_date, scores JSON, overall_score, notes, bias_flags JSON)
hrms_panel_debriefs         (id, application_id, conducted_at, consensus_decision, aggregated_scores JSON, notes)
```

**Frontend route:** Inline in `/hrms/recruitment` — interview stage detail  
**New API:** `POST /hrms/recruitment/evaluations/{id}/bias-check` → returns flagged phrases

---

### HRMS-M10: Module-Local Notification Engine (Consolidate)

**What:** HRMS already has a `notifications` table but it's shared. Rename and isolate it to `hrms_notifications` with HRMS-specific event types, retry queue, channel routing (email, in-app, WhatsApp, SMS) per user preference, and a management console for HR admins to see delivery status.

**Why:** In an HRMS-only deployment this is fine as-is, but isolating the table and engine means CRM and PMS can run their own without conflict. It also unlocks a proper notification management UI that HR admins currently lack.

**New Tables:**
```sql
hrms_notifications              (id, user_id, event_type, title, body, entity_type, entity_id, is_read, created_at)
hrms_notification_preferences   (id, user_id, event_type, email_enabled, inapp_enabled, whatsapp_enabled, sms_enabled)
hrms_notification_queue         (id, notification_id, channel, status, attempts, scheduled_at, sent_at, error_message)
hrms_notification_templates     (id, event_type, channel, subject_template, body_template, is_active)
```

**Deprecate:** Shared `notifications` table — migrate existing data into `hrms_notifications` with a one-time script.  
**Frontend route:** Notification bell icon, `/hrms/notifications` (existing), new admin view at `/hrms/settings/notifications`

---

## Summary: What Is Shared vs What Is Module-Local

### 2 Shared Tables (Absolute Minimum)

| Table | Columns | Owner |
|-------|---------|-------|
| `users` | `id`, `email`, `password_hash`, `is_active`, `created_at`, `updated_at` | Platform (not any module) |
| `audit_logs` | `id`, `user_id`, `module`, `action`, `entity_type`, `entity_id`, `diff JSON`, `ip`, `created_at` | Platform |

All other tables are owned by a single module and prefixed accordingly (`crm_*`, `pms_*`, `hrms_*`).

### 1 Shared CSS File

```
frontend/src/styles/design-tokens.css
```
Contains only CSS custom properties (variables):
- Color palette (primary, neutral, semantic — success/warning/error)
- Typography scale (font-size, line-height, font-weight)
- Spacing scale (--space-1 through --space-16)
- Border radius, shadow levels
- Animation durations

Each module has its own `crm.css`, `pms.css`, `hrms.css` that import `design-tokens.css` and can override tokens with module-specific brand colors if needed.

### Integration Bridge (When Multiple Modules Co-Exist)

```sql
integration_events (
  id            BIGINT PRIMARY KEY,
  source_module ENUM('hrms','crm','pms'),
  event_type    VARCHAR(100),  -- e.g. 'deal.won', 'employee.joined', 'sprint.completed'
  source_id     VARCHAR(100),
  payload       JSON,
  consumed_by   VARCHAR(100),  -- which module consumed it
  consumed_at   TIMESTAMP NULLABLE,
  created_at    TIMESTAMP
)
```

**Cross-module automation examples:**

| Trigger | Action |
|---------|--------|
| CRM `deal.won` | PMS creates project from template with client name from deal |
| HRMS `employee.joined` | CRM creates contact record (name, email, department) |
| HRMS `employee.left` | PMS auto-reassigns open tasks; CRM flags owned leads for reassignment |
| PMS `project.completed` | CRM updates deal/subscription status to "delivered" |
| HRMS `leave.approved` | PMS blocks member availability on those dates |
| CRM `invoice.paid` | PMS marks budget line as received |
| PMS `okr.progress_updated` | HRMS performance appraisal records evidence (via link, no FK) |

This table is the **only permitted cross-module coupling** beyond the two shared tables.

---

## Modification Priority Ranking (Effort vs Value)

| # | Module | Modification | Effort | Value | Priority |
|---|--------|-------------|--------|-------|---------|
| 1 | CRM | Invoice & Payment Tracking | Medium | Very High | Ship First |
| 2 | HRMS | Payroll Simulator | Low | High | Ship First |
| 3 | PMS | Project Template Library | Low | High | Ship First |
| 4 | CRM | Multi-Step Sequencer | Medium | High | Q1 |
| 5 | HRMS | Compensation Benchmarking | Medium | High | Q1 |
| 6 | PMS | Code Repository Integration | Medium | High | Q1 |
| 7 | CRM | Document E-Sign | Medium | High | Q1 |
| 8 | HRMS | Govt Portal Connectors | High | Very High | Q2 |
| 9 | PMS | OKR Module | Medium | High | Q2 |
| 10 | CRM | Customer Health Score | Medium | High | Q2 |
| 11 | HRMS | Rewards Store | Low | Medium | Q2 |
| 12 | PMS | Client Deliverable Approvals | Low | High | Q2 |
| 13 | CRM | Two-Way Email Inbox | High | High | Q3 |
| 14 | HRMS | Matrix Reporting | Medium | High | Q3 |
| 15 | PMS | Budget & Expense Tracker | Medium | High | Q3 |
| 16 | CRM | Meeting Intelligence | Low | Medium | Q3 |
| 17 | HRMS | Wellness Module | Medium | Medium | Q3 |
| 18 | PMS | Resource Marketplace | Medium | Medium | Q3 |
| 19 | CRM | Subscription Renewals | Medium | High | Q3 |
| 20 | All | Local Notification Engines | Medium | Medium | Prerequisite for independence |
| 21 | All | Local Role/Permission System | Medium | High | Prerequisite for independence |
| 22 | HRMS | Shift Bidding | Medium | Medium | Q4 |
| 23 | HRMS | Interview Intelligence | High | Medium | Q4 |
| 24 | CRM | AI Deal Coach | Medium | High | Q4 |
| 25 | PMS | Advanced Dashboard | Medium | Medium | Q4 |
| 26 | PMS | Meeting Notes | Low | Medium | Q4 |

---

*Each modification above is self-contained within its module. No modification creates a direct FK dependency on another module's tables. Integration between modules happens exclusively via the `integration_events` table or optional sync adapters that are only loaded when both modules are installed.*
