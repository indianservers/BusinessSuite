# Mega HRMS Database Schema Blueprint

This is the long-term database shape for a domain-neutral HRMS. It is intentionally broader than the current implementation so the product can grow into technology, manufacturing, BFSI, retail, healthcare, education, public sector, and field-service domains without rebuilding the data model.

## Design Principles

- Multi-tenant first: every operational table should carry `tenant_id`; country/domain configuration should be data-driven.
- Core worker identity first: a person, worker, employment, assignment, and position should be separate concepts.
- Effective dating: job, compensation, policy, assignment, and compliance records need `effective_from`, `effective_to`, and `status`.
- Configurable workflow: approvals, forms, fields, notifications, and feature flags should be modeled, not hardcoded.
- Audit and compliance by default: sensitive HR data must support field-level audit, retention, masking, legal hold, and consent.
- Domain packs: manufacturing, BFSI, retail, healthcare, education, and field-service rules should attach to the same core employee and organization model.

## Platform and Tenant

| Table | Key columns | Purpose |
| --- | --- | --- |
| `tenants` | id, name, slug, status, timezone, default_locale | Customer account. |
| `tenant_domains` | tenant_id, domain_code, is_primary | Enables industry packs such as BFSI or manufacturing. |
| `feature_flags` | tenant_id, feature_key, enabled, rollout_rules_json | Turns modules and features on/off. |
| `subscriptions` | tenant_id, plan_code, start_date, end_date, status | Commercial package. |
| `localization_packs` | country_code, state_code, module, config_json | Country/state rules. |
| `number_sequences` | tenant_id, object_type, prefix, next_number | Employee IDs, candidate IDs, payroll run IDs. |

## Organization Master

| Table | Key columns | Purpose |
| --- | --- | --- |
| `legal_entities` | tenant_id, name, registration_no, tax_no, country | Employer/legal entity. |
| `business_units` | tenant_id, legal_entity_id, name, code | Strategic units. |
| `locations` | tenant_id, legal_entity_id, name, address_json, geo_json | Office, plant, store, hospital, campus, site. |
| `branches` | tenant_id, legal_entity_id, location_id, name, code | Branches. |
| `departments` | tenant_id, parent_id, branch_id, name, code, head_worker_id | Department tree. |
| `cost_centers` | tenant_id, code, name, finance_mapping_json | Finance allocation. |
| `grades` | tenant_id, name, level, band_id | Grade/level. |
| `bands` | tenant_id, name, min_level, max_level | Job banding. |
| `job_families` | tenant_id, name, description | Job family. |
| `job_profiles` | tenant_id, job_family_id, title, description, skill_requirements_json | Role definition. |
| `positions` | tenant_id, job_profile_id, department_id, grade_id, budgeted_headcount, status | Position management. |

## People and Employment

| Table | Key columns | Purpose |
| --- | --- | --- |
| `persons` | tenant_id, legal_name, preferred_name, dob, gender, nationality | Human identity. |
| `person_contacts` | person_id, type, value, is_primary, verified_at | Email, phone. |
| `person_addresses` | person_id, type, address_json, effective_from | Address history. |
| `person_dependents` | person_id, name, relationship, dob, nominee_percent | Family/nominee. |
| `workers` | tenant_id, person_id, worker_number, worker_type, status | Employee/contractor/intern. |
| `employments` | worker_id, legal_entity_id, start_date, end_date, employment_type, status | Employment contract. |
| `assignments` | employment_id, position_id, department_id, manager_worker_id, work_location, effective_from, effective_to | Job assignment history. |
| `employee_profiles` | worker_id, bio, interests, research_work, health_summary, profile_photo_url | Extended profile. |
| `employee_identifiers` | worker_id, identifier_type, identifier_value, country_code, expiry_date | PAN, Aadhaar, UAN, SSN, visa. |
| `employee_bank_accounts` | worker_id, bank_name, masked_account_no, ifsc_swift, account_type, effective_from | Payroll bank data. |
| `employee_status_events` | worker_id, event_type, event_date, reason, comments | Joining, confirmation, transfer, exit. |

## Access, Security, and Audit

| Table | Key columns | Purpose |
| --- | --- | --- |
| `users` | tenant_id, worker_id, email, password_hash, status, last_login_at | Login account. |
| `roles` | tenant_id, name, is_system | Role definitions. |
| `permissions` | key, module, action | Permission catalog. |
| `role_permissions` | role_id, permission_id | Role grants. |
| `user_roles` | user_id, role_id, scope_json | Scoped access. |
| `sessions` | user_id, device_json, ip_address, expires_at | Session tracking. |
| `audit_events` | tenant_id, actor_user_id, object_type, object_id, action, diff_json | Audit trail. |
| `field_audit_events` | tenant_id, object_type, object_id, field_name, old_hash, new_hash | Sensitive field audit. |
| `data_retention_rules` | tenant_id, object_type, retention_period, action | Retention. |
| `privacy_requests` | tenant_id, person_id, request_type, status | GDPR-style privacy flows. |
| `metric_definitions` | tenant_id, code, module, formula_json, owner_role | Governed analytics metric catalog. |
| `report_schedules` | report_definition_id, cron_expression, recipients_json, last_run_at | Scheduled report exports and manual schedule runs. |
| `domain_pack_registry` | tenant_id/company_id, pack_key, status, config_json | Enables extensible industry/domain packs per tenant or company. |

## Workflow and Configuration

| Table | Key columns | Purpose |
| --- | --- | --- |
| `custom_fields` | tenant_id, object_type, key, label, data_type, validation_json | Dynamic fields. |
| `custom_field_values` | tenant_id, object_type, object_id, field_id, value_json | Dynamic values. |
| `form_templates` | tenant_id, module, name, schema_json, status | Configurable forms. |
| `workflow_definitions` | tenant_id, module, trigger_key, version, status | Workflow model. |
| `workflow_steps` | workflow_id, step_order, step_type, assignee_rule_json | Approval/task steps. |
| `workflow_instances` | workflow_id, object_type, object_id, status, started_by | Running workflow. |
| `workflow_tasks` | instance_id, step_id, assignee_user_id, status, due_at | Task queue. |
| `notification_templates` | tenant_id, channel, event_key, subject, body | Email/SMS/push templates. |
| `notifications` | tenant_id, recipient_user_id, event_key, payload_json, read_at | Notification inbox. |

## Recruitment and Onboarding

| Table | Key columns | Purpose |
| --- | --- | --- |
| `hiring_plans` | tenant_id, department_id, fiscal_year, planned_roles | Headcount demand. |
| `job_requisitions` | tenant_id, position_id, hiring_manager_id, openings, status | Approved hiring need. |
| `job_postings` | requisition_id, channel, title, description, status | Published job. |
| `candidates` | tenant_id, name, email, phone, source, owner_user_id | Candidate master. |
| `candidate_applications` | candidate_id, requisition_id, stage, status | Candidate in job pipeline. |
| `candidate_documents` | candidate_id, document_type, file_url, parsed_json | Resume and docs. |
| `interviews` | application_id, round_name, scheduled_at, mode, status | Interview rounds. |
| `interview_feedback` | interview_id, interviewer_worker_id, score, feedback_json | Evaluation. |
| `offers` | application_id, compensation_json, joining_date, status | Offer management. |
| `onboarding_templates` | tenant_id, name, role_scope_json | Template. |
| `onboarding_instances` | worker_id, template_id, status, started_at | New hire onboarding. |
| `onboarding_tasks` | instance_id, task_name, owner_rule, status | Tasks. |

## Attendance, Leave, and Workforce Management

| Table | Key columns | Purpose |
| --- | --- | --- |
| `shift_templates` | tenant_id, name, start_time, end_time, break_rules_json | Shift definition. |
| `shift_rosters` | tenant_id, location_id, period_start, period_end, status | Published roster. |
| `shift_assignments` | roster_id, worker_id, shift_id, work_date, status | Worker shift. |
| `attendance_events` | worker_id, event_type, event_time, source, geo_json, device_json | Punch events. |
| `attendance_days` | worker_id, work_date, status, worked_minutes, late_minutes | Daily summary. |
| `attendance_regularizations` | worker_id, work_date, reason, status | Corrections. |
| `leave_types` | tenant_id, code, name, accrual_rule_json, carry_forward_rule_json | Leave policy. |
| `leave_balances` | worker_id, leave_type_id, year, opening, accrued, used, balance | Balance. |
| `leave_requests` | worker_id, leave_type_id, from_date, to_date, status | Leave request. |
| `overtime_requests` | worker_id, work_date, minutes, reason, status | Overtime. |
| `timesheets` | worker_id, period_start, period_end, status | Timesheet header. |
| `timesheet_entries` | timesheet_id, project_id, task, work_date, hours | Project time. |

## Payroll, Benefits, and Finance

| Table | Key columns | Purpose |
| --- | --- | --- |
| `pay_groups` | tenant_id, legal_entity_id, frequency, currency | Payroll grouping. |
| `salary_components` | tenant_id, code, type, taxable, formula_json | Earnings/deductions. |
| `salary_structures` | tenant_id, name, currency, effective_from | Structure. |
| `salary_structure_lines` | structure_id, component_id, amount_type, value | Structure lines. |
| `employee_salary_assignments` | worker_id, structure_id, ctc, effective_from | Salary history. |
| `payroll_runs` | tenant_id, pay_group_id, month, year, status, locked_at | Payroll cycle. |
| `payroll_records` | run_id, worker_id, gross, deductions, net, status | Employee payroll. |
| `payroll_record_lines` | payroll_record_id, component_id, amount | Line items. |
| `payslips` | payroll_record_id, file_url, published_at | Payslips. |
| `tax_declarations` | worker_id, year, declaration_json, status | Tax planning. |
| `tax_proofs` | declaration_id, document_type, amount, file_url, status | Proofs. |
| `reimbursements` | worker_id, category, amount, claim_date, status | Claims. |
| `loans_advances` | worker_id, type, principal, emi, balance, status | Loan/advance. |
| `benefit_plans` | tenant_id, name, eligibility_rule_json | Benefits. |
| `benefit_enrollments` | worker_id, plan_id, effective_from, status | Enrollment. |
| `accounting_exports` | payroll_run_id, export_file_url, status | Finance integration. |

## Performance, Skills, Learning, and Compensation

| Table | Key columns | Purpose |
| --- | --- | --- |
| `goal_cycles` | tenant_id, name, from_date, to_date, status | OKR cycle. |
| `goals` | tenant_id, owner_worker_id, parent_goal_id, title, target_value, progress | Goals. |
| `goal_checkins` | goal_id, checkin_date, progress, comment | Goal updates. |
| `review_cycles` | tenant_id, name, type, from_date, to_date, status | Review cycle. |
| `review_templates` | tenant_id, name, schema_json | Review form. |
| `reviews` | cycle_id, subject_worker_id, reviewer_worker_id, status, rating | Review. |
| `review_responses` | review_id, question_key, response_json | Review answers. |
| `feedback` | from_worker_id, to_worker_id, type, message, visibility | Continuous feedback. |
| `one_on_ones` | manager_worker_id, worker_id, scheduled_at, notes | 1:1. |
| `skills` | tenant_id, name, category, description | Skill library. |
| `competencies` | tenant_id, name, framework_id | Competencies. |
| `worker_skills` | worker_id, skill_id, proficiency, source, verified_at | Skill matrix. |
| `courses` | tenant_id, title, provider, mode, duration | Learning catalog. |
| `learning_assignments` | worker_id, course_id, due_date, status | Course assignment. |
| `certifications` | tenant_id, name, issuing_body, validity_months | Certification master. |
| `worker_certifications` | worker_id, certification_id, issue_date, expiry_date, file_url | Certification tracking. |
| `compensation_cycles` | tenant_id, name, budget, status | Compensation planning. |
| `compensation_reviews` | cycle_id, worker_id, current_pay, proposed_pay, bonus, equity | Compensation review. |

## Documents, Policies, and Service Delivery

| Table | Key columns | Purpose |
| --- | --- | --- |
| `document_templates` | tenant_id, module, name, body, variables_json | Template. |
| `documents` | tenant_id, owner_type, owner_id, document_type, file_url, status | Repository. |
| `generated_documents` | template_id, owner_type, owner_id, file_url, generated_at | Letters. |
| `policies` | tenant_id, name, version, file_url, status | Policies. |
| `policy_acknowledgements` | policy_id, worker_id, acknowledged_at | Acceptance. |
| `helpdesk_categories` | tenant_id, name, sla_hours, owner_rule_json | Category. |
| `helpdesk_tickets` | tenant_id, requester_worker_id, category_id, subject, status, priority | Ticket. |
| `helpdesk_replies` | ticket_id, author_user_id, message, is_internal | Conversation. |
| `knowledge_articles` | tenant_id, category_id, title, body, status | Self-service KB. |

## Assets, Travel, and Exit

| Table | Key columns | Purpose |
| --- | --- | --- |
| `asset_categories` | tenant_id, name, depreciation_rule_json | Category. |
| `assets` | tenant_id, category_id, asset_tag, serial_no, status, location_id | Asset inventory. |
| `asset_assignments` | asset_id, worker_id, assigned_at, returned_at, condition_json | Assignment. |
| `travel_requests` | worker_id, purpose, itinerary_json, budget, status | Travel request. |
| `travel_expenses` | travel_request_id, expense_json, status | Travel expense. |
| `exit_records` | worker_id, resignation_date, last_working_date, reason, status | Exit case. |
| `exit_checklist_templates` | tenant_id, role_scope_json, checklist_json | Exit template. |
| `exit_checklist_items` | exit_record_id, owner_rule, task, status | Exit tasks. |
| `exit_interviews` | exit_record_id, answers_json, risk_flags_json | Exit feedback. |

## Domain Pack Tables

| Domain | Tables |
| --- | --- |
| Manufacturing | `manufacturing_safety_incidents`, `manufacturing_ppe_issuances`, `manufacturing_medical_fitness_records`, `production_shift_handovers`, `manufacturing_contract_labor_batches` |
| BFSI | `regulatory_certifications`, `segregation_of_duties_rules`, `policy_attestations`, `investigation_cases`, `evidence_files` |
| Retail and Field | `store_staffing_plans`, `field_routes`, `field_visit_logs`, `mobile_task_lists`, `offline_sync_batches` |
| Healthcare | `clinical_credentials`, `license_registrations`, `on_call_rosters`, `vaccination_records`, `department_privileges` |
| Education | `faculty_workloads`, `course_allocations`, `research_publications`, `grant_assignments`, `academic_calendar_events` |
| Public Sector and NGO | `project_allocations`, `donor_funding_lines`, `field_allowance_rules`, `compliance_inspections` |

## Analytics and AI

| Table | Key columns | Purpose |
| --- | --- | --- |
| `metric_definitions` | tenant_id, key, name, formula_sql, owner_module | Governed metrics. |
| `hr_analytics_drilldowns` | tenant_id, metric_key, filters_json, generated_at | Cached drilldown outputs for pay equity, span, manager effectiveness, attrition, absenteeism, and DE&I. |
| `dashboard_definitions` | tenant_id, name, layout_json, visibility_json | Dashboards. |
| `report_definitions` | tenant_id, name, query_json, schedule_json | Custom reports. |
| `report_schedules` | report_definition_id, cron_expression, recipients_json, last_run_at | Scheduled/manual report export metadata. |
| `data_exports` | tenant_id, object_type, file_url, status | Export jobs. |
| `ai_prompts` | tenant_id, use_case, prompt_template, version | AI prompt management. |
| `ai_runs` | tenant_id, use_case, input_hash, output_json, actor_user_id | AI audit. |
| `prediction_scores` | tenant_id, model_key, object_type, object_id, score, explanation_json | Attrition, risk, anomaly. |

## Migration Strategy

1. Keep current tables as the MVP operational layer.
2. Add tenant-aware versions when multi-company hosting is required.
3. Split employee data into `persons`, `workers`, `employments`, and `assignments` before global/domain packs.
4. Introduce workflow/custom-field/config tables before adding many one-off approval columns.
5. Add domain pack tables only when the corresponding feature pack is enabled for a tenant.
6. Create materialized reporting views after transactional modules stabilize.
