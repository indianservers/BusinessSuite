# Enterprise Journey Blueprint

Date: 2026-06-04

## Design Principle

A 2026 business operating system should not ask users to move data between modules. Every journey should move through one connected record graph: customer, employee, project, money, document, approval, and risk.

## Customer Acquisition Journey

| Step | Actor | Actions | System Automation | AI Opportunities |
|---|---|---|---|---|
| Lead | Marketing/sales rep | Capture inquiry from form, WhatsApp, call, import, campaign | Deduplicate, enrich, score, route by territory/source | Predict quality, suggest owner, summarize intent |
| Contact | Sales rep | Validate person, consent, role, communication preference | Link to account, activity timeline, consent ledger | Infer stakeholder role and buying influence |
| Opportunity | Sales rep/manager | Create deal, value, stage, products, close date | Stage checklist, probability, next action, stale-deal alert | Predict win chance, objections, best next step |
| Quote | Sales rep/finance | Build quote with products/services, taxes, discounts | Price rules, margin check, versioning, template rendering | Draft proposal narrative and scope |
| Approval | Sales manager/CFO | Review discount, margin, credit, terms | Approval route by amount/risk/SLA, audit trail | Explain approval risk and exceptions |
| Deal Won | Sales manager | Mark won, confirm scope, handoff owner | Create customer success/project kickoff package | Detect delivery risks from quote terms |
| Project | Project manager | Select template, plan milestones, assign team | Create PMS project, copy quote scope/budget, notify team | Generate plan, WBS, risks, staffing suggestions |
| Delivery | Delivery team | Execute tasks, log time, manage changes | Track milestones, dependencies, risks, utilization | Predict slippage and recommend corrective action |
| Invoice | Finance | Bill milestone/time/materials | Generate invoice draft/export from approved delivery | Validate invoice against quote and work logs |
| Collection | Finance/sales | Track receivables and follow up | Payment reminders, escalation, credit holds | Predict collection risk and draft reminders |
| Support | Support/CSM | Handle issues, renewal, upsell | Ticket/customer health, SLA, renewal workflow | Summarize account health and upsell timing |

## Employee Journey

| Step | Actor | Actions | System Automation | AI Opportunities |
|---|---|---|---|---|
| Recruitment | HR/recruiter | Raise vacancy, publish job, source candidates | Job approvals, pipeline stages, interview scheduling | Match resumes to role and culture signals |
| Interview | Hiring panel | Score interviews, add feedback | Panel reminders, scorecards, conflict checks | Summarize feedback and identify concerns |
| Offer | HR/manager | Prepare CTC, approvals, offer letter | Compensation guardrails, approval routing, e-sign | Draft offer and detect compensation anomalies |
| Joining | HR/employee | Collect documents, create employee, assign assets | Onboarding checklist, accounts, induction tasks | Personalized onboarding assistant |
| Attendance | Employee/manager | Punch, regularize, approve exceptions | Geo/device validation, roster rules, missing punch alerts | Explain exceptions and suggest corrections |
| Payroll | HR/payroll/CFO | Process salary, statutory, reimbursements | Payroll readiness checks, bank/statutory exports | Validate payroll, detect anomalies/fraud |
| Appraisal | Manager/HR | Goals, reviews, ratings, calibration | Review cycles, reminders, normalization | Summarize performance evidence |
| Promotion | Manager/HR/CFO | Raise promotion/transfer/comp change | Approval workflow, org update, payroll effective date | Predict retention impact and pay equity |
| Exit | HR/manager/finance | Resignation, clearance, FNF, knowledge transfer | Exit checklist, asset recovery, FNF payroll | Attrition reason clustering and replacement plan |

## Project Journey

| Step | Actor | Actions | System Automation | AI Opportunities |
|---|---|---|---|---|
| Request | Business owner/client/sales | Submit project request or handoff from deal | Intake form, classification, duplicate check | Convert brief into project charter |
| Approval | PMO/finance/leadership | Approve scope, budget, priority | Approval matrix, budget guardrails, portfolio capacity | Recommend approve/defer based on ROI and capacity |
| Planning | Project manager | Build WBS, milestones, dependencies, baseline | Template selection, date shift, dependency validation | Generate plan and risk register |
| Resource Allocation | PM/resource manager | Assign people, skills, allocation percentage | HR leave/capacity sync, overbooking warnings | Recommend staff mix and substitutions |
| Execution | Team leads/team | Run tasks, sprints, files, approvals, changes | Status updates, reminders, dependency alerts | Summarize progress and unblock suggestions |
| Monitoring | PMO/COO/client | Review risks, health, budget, utilization | Dashboards, SLA alerts, variance analysis | Predict slippage, burn overrun, quality risk |
| Billing | Finance/PM | Approve milestone/time invoices | Invoice draft/export, revenue recognition, margin rollup | Detect billing leakage and missing billables |
| Closure | PM/client/finance | Final acceptance, lessons, archive, renewal | Closure checklist, satisfaction survey, asset/archive lock | Create lessons learned and upsell recommendations |

