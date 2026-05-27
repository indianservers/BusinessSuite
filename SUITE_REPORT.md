# Business Suite — Detailed Technical Report

Generated: 2026-05-23  
Branch: codex/crm-database-persistence  
Stack: FastAPI + React/TypeScript + MySQL

---

## Table of Contents

1. [Platform Overview](#1-platform-overview)
2. [Architecture Summary](#2-architecture-summary)
3. [HRMS Module](#3-hrms-module)
   - Routes
   - Database Models
   - Features
4. [CRM Module](#4-crm-module)
   - Routes
   - Database Models
   - Features
5. [PMS Module (KaryaFlow)](#5-pms-module-karyaflow)
   - Routes
   - Database Models
   - Features
6. [Common Shared Features](#6-common-shared-features)
7. [Unique Per-Module Features](#7-unique-per-module-features)
8. [AI Agents Framework](#8-ai-agents-framework)
9. [Authentication & Security](#9-authentication--security)
10. [Configuration & Deployment](#10-configuration--deployment)
11. [Tech Stack](#11-tech-stack)
12. [Counts & Metrics](#12-counts--metrics)

---

## 1. Platform Overview

**Business Suite** is a modular, multi-tenant ERP platform built for Indian businesses. It ships three independently deployable product modules — HRMS, CRM, and Project Management (PMS/KaryaFlow) — backed by a single FastAPI server and a shared React shell.

Each module can be toggled via environment variable (`INSTALLED_APPS` / `VITE_INSTALLED_APPS`), so a client can run only HRMS, only CRM+PMS, or all three together. Auth, audit logging, notifications, AI agents, and the workflow engine are platform-level and shared across all modules.

---

## 2. Architecture Summary

```
backend/
├── app/
│   ├── api/v1/              # HRMS REST endpoints (42 route files)
│   ├── apps/
│   │   ├── crm/             # CRM module (models, schema, API router)
│   │   ├── project_management/  # PMS module (models, schema, API router)
│   │   └── hrms/            # HRMS app init
│   ├── ai_agents/           # Multi-model AI framework (30 files)
│   ├── models/              # SQLAlchemy ORM models (HRMS – 26 files)
│   ├── schemas/             # Pydantic request/response schemas
│   ├── services/            # Business logic services
│   ├── crud/                # Generic CRUD base + employee CRUD
│   ├── core/                # Config, security, deps, middleware
│   └── db/                  # DB session, Alembic migrations
frontend/
├── src/
│   ├── apps/
│   │   ├── hrms/            # HRMS frontend (40+ pages)
│   │   ├── crm/             # CRM frontend
│   │   └── project-management/  # PMS frontend (30+ pages)
│   ├── pages/               # Shared pages (ModuleIndexPage, ModuleProfilePage, AI agents)
│   ├── components/          # Reusable UI (layout, AI chat, Shadcn/ui)
│   ├── services/            # api.ts, aiAgentsApi.ts
│   ├── store/               # Zustand auth store
│   └── App.tsx              # Root router with lazy module loading
```

**Data layer:** MySQL (production) / SQLite-compatible (local). ORM via SQLAlchemy, migrations via Alembic.  
**Frontend build:** Vite + React 18 + TypeScript + Tailwind CSS + React Query + Zustand.  
**Cross-cutting:** JWT auth, MFA, RBAC, audit middleware, rate limiting, GZip, AI agents.

---

## 3. HRMS Module

### 3.1 Frontend Routes (`/hrms/*`)

| Path | Page Component | Purpose |
|------|---------------|---------|
| `/hrms` | DashboardPage | HR admin dashboard |
| `/hrms/dashboard` | DashboardPage | HR admin dashboard |
| `/hrms/manager-dashboard` | ManagerDashboardPage | Team lead / manager view |
| `/hrms/ess` | ESSPortalPage | Employee self-service portal |
| `/hrms/employee-directory` | EmployeeDirectoryPage | Browse all employees |
| `/hrms/employees` | EmployeesPage | HR employee list with actions |
| `/hrms/employees/new` | AddEmployeePage | Create new employee |
| `/hrms/employees/:id` | EmployeeDetailPage | Employee full profile |
| `/hrms/probation` | ProbationPage | Probation tracking & confirmation |
| `/hrms/attendance` | AttendancePage | Attendance log, regularization |
| `/hrms/attendance/shift-roster` | ShiftRosterPage | Shift & roster management |
| `/hrms/timesheets` | TimesheetsPage | Timesheet submission & approvals |
| `/hrms/workflow` | WorkflowInboxPage | Approval inbox |
| `/hrms/workflow-designer` | WorkflowDesignerPage | Build approval workflows |
| `/hrms/notifications` | NotificationsPage | In-app notification center |
| `/hrms/leave` | LeavePage | Leave requests, balances, calendar |
| `/hrms/payroll` | PayrollPage | Full payroll run console |
| `/hrms/fnf-settlements` | FnFSettlementPage | Full & final settlement |
| `/hrms/investment-declaration` | InvestmentDeclarationPage | Tax investment declarations |
| `/hrms/recruitment` | RecruitmentPage | Job openings, pipeline |
| `/hrms/performance` | PerformancePage | Appraisals, goals, feedback |
| `/hrms/benefits` | BenefitsPage | Plans, enrollments, claims |
| `/hrms/lms` | LMSPage | Learning management |
| `/hrms/statutory-compliance` | StatutoryCompliancePage | PF/ESI/PT compliance calendar |
| `/hrms/background-verification` | BackgroundVerificationPage | BGV requests & reports |
| `/hrms/whatsapp-ess` | WhatsAppESSPage | WhatsApp self-service config |
| `/hrms/custom-fields` | CustomFieldsPage | Dynamic field definitions |
| `/hrms/enterprise` | EnterprisePage | Multi-org / enterprise settings |
| `/hrms/engagement` | EngagementPage | Announcements, polls, recognition |
| `/hrms/helpdesk` | HelpdeskPage | Tickets, SLA, knowledge base |
| `/hrms/reports` | ReportsPage | HR & payroll analytics |
| `/hrms/advanced-analytics` | AdvancedAnalyticsPage | DE&I, workforce analytics |
| `/hrms/logs` | AdminLogsPage | Audit & error log viewer |
| `/hrms/company` | CompanyPage | Org structure, branches, departments |
| `/hrms/org-chart` | OrgChartPage | Real-time org chart |
| `/hrms/settings` | SettingsPage | Platform & module settings |
| `/hrms/assets` | AssetsPage | Asset allocation list |
| `/hrms/onboarding` | OnboardingPage | New hire checklist management |
| `/hrms/documents` | DocumentsPage | Employee document vault |
| `/hrms/exit` | ExitPage | Exit clearance & FnF |
| `/hrms/ai-assistant` | AIAssistantPage | HR AI assistant |
| `/hrms/profile` | ProfilePage | User profile & ESS |

**Auth routes:** `/hrms/login` → LoginPage (module-specific login)

### 3.2 Backend API Endpoints (`/api/v1/`)

| Route File | Key Endpoints |
|-----------|--------------|
| **auth.py** | POST `/auth/login`, POST `/auth/logout`, POST `/auth/refresh`, GET/POST `/auth/mfa/*`, GET `/auth/roles`, GET `/auth/permissions` |
| **users.py** | GET `/users/`, GET `/users/{id}`, POST `/users/`, PATCH `/users/{id}` |
| **employees.py** | GET `/employees/`, GET `/employees/directory`, GET `/employees/me`, POST `/employees/`, GET/PATCH `/employees/{id}`, GET `/employees/{id}/photo`, POST `/employees/change-requests`, GET `/employees/lifecycle-events` |
| **company.py** | CRUD `/company/branches`, `/company/departments`, `/company/designations`, `/company/locations`, `/company/cost-centers`, `/company/grade-bands`, `/company/positions` |
| **attendance.py** | POST `/attendance/check-in`, POST `/attendance/check-out`, GET `/attendance/shifts`, GET `/attendance/holidays`, POST `/attendance/regularization`, POST `/attendance/month-lock`, GET `/attendance/biometric-devices` |
| **leave.py** | CRUD `/leave/types`, `/leave/requests`, `/leave/approvals`, GET `/leave/balances`, GET `/leave/calendar`, GET `/leave/ledger` |
| **payroll.py** | Full payroll: `/payroll/setup/*` (components, structures, pay groups, calendars, periods), `/payroll/runs`, `/payroll/records`, `/payroll/approve-run`, `/payroll/publish-payslips`, `/payroll/export`, `/payroll/tax/*`, `/payroll/statutory/*` |
| **payroll_bank_advice.py** | `/payroll/bank-advice/generate`, `/payroll/bank-advice/formats` |
| **leave_payroll.py** | Leave encashment processing, LOP calculations |
| **tax_declaration.py** | `/tax-declaration/cycles`, `/tax-declaration/submissions`, `/tax-declaration/proofs` |
| **statutory.py** | `/statutory/pf-rules`, `/statutory/esi-rules`, `/statutory/gratuity`, `/statutory/challans`, `/statutory/return-files` |
| **statutory_compliance.py** | `/compliance/checklist`, `/compliance/deadlines` |
| **hrms_compliance_exports.py** | `/compliance/pf-ecr`, `/compliance/esi`, `/compliance/pt`, `/compliance/form-16`, `/compliance/24q` |
| **form16.py** | `/form16/generate`, `/form16/send`, `/form16/list` |
| **probation.py** | `/probation/status`, `/probation/confirmation`, `/probation/extension` |
| **recruitment.py** | CRUD `/recruitment/job-openings`, `/recruitment/applications`, `/recruitment/candidates`, `/recruitment/offers`, `/recruitment/interviews` |
| **onboarding.py** | CRUD `/onboarding/tasks`, `/onboarding/checklists`, `/onboarding/documents` |
| **background_verification.py** | `/background-verification/requests`, `/background-verification/reports` |
| **performance.py** | `/performance/appraisals`, `/performance/goals`, `/performance/feedback-360`, `/performance/competencies` |
| **benefits.py** | `/benefits/plans`, `/benefits/enrollments`, `/benefits/claims`, `/benefits/esop-grants` |
| **engagement.py** | `/engagement/announcements`, `/engagement/polls`, `/engagement/recognition-wall`, `/engagement/people-moments` |
| **helpdesk.py** | `/helpdesk/tickets`, `/helpdesk/categories`, `/helpdesk/knowledge-base`, `/helpdesk/sla` |
| **lms.py** | `/lms/courses`, `/lms/enrollments`, `/lms/assessments` |
| **timesheets.py** | `/timesheets/submit`, `/timesheets/approve`, `/timesheets/list` |
| **assets.py** | `/assets/allocate`, `/assets/return`, `/assets/list` |
| **documents.py** | POST `/documents/upload`, GET `/documents/`, GET/DELETE `/documents/{id}`, POST `/documents/{id}/verify`, GET `/documents/expiring` |
| **exit.py** | `/exit/requests`, `/exit/clearance`, `/exit/final-settlement` |
| **fnf.py** | `/fnf/calculate`, `/fnf/approve`, `/fnf/disburse` |
| **shift_roster.py** | `/shift-roster/assignments`, `/shift-roster/schedules` |
| **profile_change_requests.py** | `/profile-changes/request`, `/profile-changes/approve` |
| **custom_fields.py** | `/custom-fields/create`, `/custom-fields/list`, `/custom-fields/values/upsert` |
| **reports.py** | `/reports/hr-analytics`, `/reports/payroll-analytics`, `/reports/employee-lifecycle`, `/reports/custom-reports` |
| **notifications.py** | GET `/notifications/`, POST `/notifications/send`, PATCH `/notifications/preferences` |
| **workflow.py** | `/workflow/definitions`, `/workflow/instances` |
| **workflow_engine.py** | `/workflow-engine/execute`, `/workflow-engine/approve` |
| **enterprise.py** | Multi-org / multi-tenant configuration endpoints |
| **sso.py** | `/sso/providers`, `/sso/callback` |
| **whatsapp_ess.py** | `/whatsapp-ess/chat` |
| **logs.py** | `/logs/audit`, `/logs/errors`, `/logs/sessions` |
| **ai.py** | `/ai/chat`, `/ai/parse-resume`, `/ai/predict-attrition`, `/ai/payroll-anomalies` |

### 3.3 Database Models (`backend/app/models/`)

| Model File | Key Tables / Entities |
|-----------|----------------------|
| **user.py** | User, Role, Permission, UserSession, MFAMethod, LoginAttempt, PasswordPolicy, ConsentRecord, LegalHold |
| **employee.py** | Employee (core), EmployeeAddress, EmployeeBankAccount, EmployeeDocument, EmployeeSkill, EmployeeEducation, EmployeeExperience, EmployeeLifecycleEvent, EmployeeChangeRequest, EmployeeCustomFieldValue |
| **company.py** | LegalEntity, Branch, Department, Designation, CostCenter, GradeBand, Position, Location, OrgNode |
| **attendance.py** | AttendanceShift, ShiftRoster, HolidayCalendar, AttendancePunch, AttendanceRegularization, MonthLock, BiometricDevice, GeoFenceZone |
| **leave.py** | LeaveType, LeaveBalance, LeaveRequest, LeaveLedgerEntry, LeaveCalendar |
| **payroll.py** | SalaryComponent, SalaryStructure, SalaryStructureItem, PayGroup, PayrollCalendar, PayrollPeriod, PayrollRun, PayrollRecord, PayrollRunEmployee, PayslipComponent, TaxRegime, TaxSlab, LoanAccount, LoanInstallment, ArrearRun, PayrollVarianceNote |
| **statutory.py** | PFRule, ESIRule, PTRule, LWFRule, GratuityRule, PFChallan, ESIChallan, PTChallan, StatutoryReturnFile, ECRFile |
| **tax_declaration.py** | TaxDeclarationCycle, TaxDeclaration, TaxDeclarationItem, TaxDeclarationProof |
| **recruitment.py** | JobOpening, JobApplication, Candidate, InterviewSchedule, OfferLetter |
| **onboarding.py** | OnboardingTemplate, OnboardingTask, OnboardingChecklistItem |
| **performance.py** | AppraisalCycle, Appraisal, Goal, GoalProgress, FeedbackRequest, Feedback360, Competency, CompetencyAssessment |
| **benefits.py** | BenefitPlan, BenefitEnrollment, BenefitClaim, BenefitDeduction, ESOPGrant, ESOPVestingSchedule |
| **helpdesk.py** | HelpdeskCategory, HelpdeskTicket, TicketReply, TicketSLAPolicy, KnowledgeBaseArticle |
| **engagement.py** | Announcement, Poll, PollOption, PollVote, RecognitionPost, RecognitionReaction, PeopleMoment |
| **lms.py** | LMSCourse, LMSModule, LMSEnrollment, LMSAssessment, LMSScore |
| **timesheet.py** | TimesheetEntry, TimesheetApproval |
| **asset.py** | AssetCategory, Asset, AssetAllocation, AssetHandover |
| **document.py** | EmployeeDocumentRecord, DocumentVerification, DocumentExpiry |
| **exit.py** | ExitRequest, ExitClearanceItem, ExitInterview, FnFInitiation |
| **background_verification.py** | BGVRequest, BGVReport, BGVVendor |
| **notification.py** | Notification, NotificationPreference |
| **workflow_engine.py** | WorkflowDefinition, WorkflowInstance, WorkflowTask, WorkflowTransition |
| **statutory_compliance.py** | ComplianceCalendar, ComplianceDeadline, ComplianceCertification |
| **sso.py** | SSOProvider, SSOSession |
| **platform.py** | PlatformConfig, FeatureFlag, CustomFieldDefinition |
| **whatsapp_ess.py** | WhatsAppSession, WhatsAppMessage |
| **audit.py** | AuditLog |
| **target.py** | PerformanceTarget, TargetProgress |

### 3.4 Feature Summary

| Feature Area | What's Included |
|-------------|----------------|
| **Employee Master** | Personal info, job details, bank accounts, addresses, compliance data, documents, skills, education, experience, lifecycle events, change approval workflow, profile completeness scoring |
| **Self-Service (ESS)** | Payslip download, leave application, attendance view, goal tracking, helpdesk ticket raise, asset view, investment declaration |
| **Manager Dashboard** | Team attendance matrix, pending approvals, team calendar, birthday/anniversary alerts |
| **Company Setup** | Legal entity, branches, departments, designations, cost centers, grade bands, positions, locations, org chart |
| **Attendance** | Check-in/out, shift configuration, holiday calendar, roster management, regularization requests, monthly lock, geo-fence & biometric device foundations |
| **Leave** | Leave types (CL/SL/PL/custom), balance allocation, accrual rules, request & multi-level approval, ledger, team calendar |
| **Payroll** | Setup wizard (components, structures, pay groups, periods), payroll run console, pre-run validation, employee worksheet, reprocess, multi-level approval, payslip PDF, bulk email, bank advice (NEFT/RTGS), GL journal export, variance review |
| **Tax & Compliance** | Tax regime selection, slabs, TDS calculation, Form 16 generation, 24Q filing, PF/ESI/PT/LWF rules, challans, statutory calendar, ECR file generation |
| **Full & Final** | FnF calculation, approval, disbursement, leave encashment, gratuity, LOP adjustment |
| **Recruitment** | Job openings, application tracking, candidate database, interview scheduling, offer letter generation |
| **Onboarding** | Task checklists, document collection workflow, new hire portal |
| **Background Verification** | Request management, vendor assignment, report tracking |
| **Performance** | Appraisal cycles, goal/OKR setting, 360-degree feedback, competency mapping, skill gap analysis |
| **Benefits** | Health/insurance plans, enrollments, flexi benefits, claims processing, payroll deductions, ESOP grants, vesting schedules |
| **Engagement** | Company announcements, polls/surveys, recognition wall with reactions, people moments (birthdays/work anniversaries) |
| **Helpdesk** | Ticket raise/assign/close, SLA policies, escalation, knowledge base articles, AI-assisted replies |
| **Learning (LMS)** | Course catalog, enrollments, module tracking, assessments, scores |
| **Documents** | Upload, categorization, document verification, expiry alerts, bulk management |
| **Exit Management** | Exit request, clearance tracker, exit interview, FnF initiation |
| **Assets** | Allocation, return, handover records |
| **Timesheets** | Daily/weekly submission, manager approval |
| **Probation** | Tracking, confirmation, extension workflow |
| **Reports & Analytics** | HR analytics, payroll analytics, employee lifecycle, DE&I, custom report builder foundations |
| **Workflow Engine** | Dynamic multi-step approval workflows with conditions, escalation, SLA |
| **WhatsApp ESS** | Conversational leave, payslip, attendance queries via WhatsApp Business |
| **Custom Fields** | Admin-defined dynamic fields for any entity |
| **Enterprise** | Multi-org, multi-legal-entity setup, feature flags per org |
| **SSO** | SAML/OAuth2 single sign-on provider integration |
| **AI Assistant** | Natural language HR queries, resume parsing, attrition prediction, payroll anomaly detection |

---

## 4. CRM Module

### 4.1 Frontend Routes (`/crm/*`)

| Path | View / Purpose |
|------|---------------|
| `/crm` | Dashboard (pipeline overview) |
| `/crm/profile` | Module profile page |
| `/crm/leads` | Lead list view |
| `/crm/leads/:id` | Lead detail record |
| `/crm/contacts` | Contact list |
| `/crm/contacts/:id` | Contact detail |
| `/crm/accounts` | Account/company list |
| `/crm/accounts/:id` | Account detail |
| `/crm/companies` | Alias for accounts |
| `/crm/companies/:id` | Company detail |
| `/crm/deals` | Deal list |
| `/crm/deals/:id` | Deal detail |
| `/crm/pipeline` | Visual pipeline / kanban |
| `/crm/pipeline-settings` | Pipeline & stage configuration |
| `/crm/activities` | All activities feed |
| `/crm/tasks` | Task list |
| `/crm/calendar` | Activity calendar |
| `/crm/calendar-integrations` | Google / Outlook sync config |
| `/crm/webhooks` | Webhook configuration |
| `/crm/campaigns` | Marketing campaigns |
| `/crm/products` | Product catalog |
| `/crm/quotations` | Quotation list |
| `/crm/quotations/:id` | Quotation detail / PDF |
| `/crm/approval-settings` | Approval workflow definitions |
| `/crm/my-approvals` | Pending approvals inbox |
| `/crm/duplicates` | Duplicate detection & merge |
| `/crm/territories` | Territory definitions |
| `/crm/tickets` | Customer support tickets |
| `/crm/files` | File asset library |
| `/crm/reports` | Sales analytics |
| `/crm/automation` | Automation rules |
| `/crm/lead-to-cash` | End-to-end lead→deal→invoice flow |
| `/crm/forecasting` | Revenue forecasting |
| `/crm/customer-360` | 360° customer view |
| `/crm/import-export` | Data import / export |
| `/crm/settings` | CRM settings |
| `/crm/lead-scoring` | Lead scoring rule builder |
| `/crm/feature-checklist` | Implementation checklist |
| `/crm/admin` | CRM admin panel |

**Auth route:** `/crm/login` → LoginPage

### 4.2 Backend API Endpoints (`backend/app/apps/crm/api/router.py`)

| Category | Key Endpoints |
|----------|--------------|
| **Leads** | CRUD `/crm/leads/`, GET `/crm/leads/{id}`, POST `/crm/leads/bulk`, POST `/crm/leads/{id}/score`, POST `/crm/leads/{id}/convert`, GET `/crm/leads/auto-assign` |
| **Contacts** | CRUD `/crm/contacts/`, GET `/crm/contacts/{id}`, GET `/crm/contacts/{id}/timeline`, POST `/crm/contacts/{id}/verify-email` |
| **Companies/Accounts** | CRUD `/crm/companies/`, GET `/crm/companies/{id}`, GET `/crm/companies/{id}/hierarchy`, PATCH `/crm/companies/{id}/parent` |
| **Deals** | CRUD `/crm/deals/`, PATCH `/crm/deals/{id}/stage`, GET `/crm/deals/forecast`, GET `/crm/deals/lost-reasons` |
| **Pipeline** | CRUD `/crm/pipelines/`, `/crm/pipelines/{id}/stages`, PATCH `/crm/pipeline-stages/{id}/reorder` |
| **Activities** | CRUD `/crm/tasks/`, `/crm/meetings/`, `/crm/call-logs/`, `/crm/email-logs/`, GET `/crm/activities/feed` |
| **Notes** | CRUD `/crm/notes/`, POST `/crm/notes/{id}/mentions` |
| **Communication** | CRUD `/crm/email-templates/`, POST `/crm/send-email`, CRUD `/crm/message-templates/`, POST `/crm/send-message` |
| **Calendar** | CRUD `/crm/calendar-integrations/`, POST `/crm/calendar-integrations/{id}/sync` |
| **Products** | CRUD `/crm/products/`, `/crm/products/{id}` |
| **Quotations** | CRUD `/crm/quotations/`, GET `/crm/quotations/{id}/pdf`, POST `/crm/quotations/{id}/send` |
| **Territories** | CRUD `/crm/territories/`, POST `/crm/territories/{id}/assign-users`, POST `/crm/territories/auto-assign` |
| **Lead Scoring** | CRUD `/crm/lead-scoring-rules/`, POST `/crm/leads/{id}/recalculate-score` |
| **Custom Fields** | CRUD `/crm/custom-fields/`, POST `/crm/custom-fields/values/upsert` |
| **Approvals** | CRUD `/crm/approval-workflows/`, POST `/crm/approval-requests/`, PATCH `/crm/approval-requests/{id}/approve`, PATCH `/crm/approval-requests/{id}/reject` |
| **Webhooks** | CRUD `/crm/webhooks/`, POST `/crm/webhooks/{id}/test`, GET `/crm/webhooks/{id}/deliveries` |
| **Files** | POST `/crm/files/upload`, GET `/crm/files/`, DELETE `/crm/files/{id}` |
| **Enrichment** | POST `/crm/enrich/preview`, POST `/crm/enrich/apply`, GET `/crm/enrich/history` |
| **Duplicates** | POST `/crm/duplicates/scan`, POST `/crm/duplicates/merge`, GET `/crm/duplicates/list` |
| **Reports** | GET `/crm/reports/funnel`, GET `/crm/reports/win-loss`, GET `/crm/reports/revenue-trends`, GET `/crm/reports/territory-performance`, GET `/crm/reports/rep-leaderboard` |
| **Owners** | GET `/crm/owners/`, PATCH `/crm/records/{entity}/{id}/owner` |
| **Data Import/Export** | POST `/crm/import/leads`, POST `/crm/import/contacts`, GET `/crm/export/{entity}` |

### 4.3 Database Models (`backend/app/apps/crm/models.py`)

| Model | Purpose |
|-------|---------|
| **CRMOwner** | Links user accounts as CRM record owners |
| **CRMCompany** | Company/account master (industry, size, website, parent) |
| **CRMContact** | Individual contacts linked to companies |
| **CRMLead** | Sales leads with score, source, stage |
| **CRMLeadScoringRule** | Attribute-based scoring rules |
| **CRMDeal** | Opportunities with amount, close date, probability |
| **CRMDealProduct** | Products attached to deals |
| **CRMPipeline** | Named sales pipelines |
| **CRMPipelineStage** | Ordered stages per pipeline |
| **CRMTask** | Actionable to-do items linked to any entity |
| **CRMMeeting** | Scheduled meetings with attendees |
| **CRMCallLog** | Outbound/inbound call records |
| **CRMEmailLog** | Email send/receive history |
| **CRMNote** | Free-text notes on any CRM entity |
| **CRMNoteMention** | @mention links within notes |
| **CRMActivity** | Generic activity stream entry |
| **CRMProduct** | Product/service catalog |
| **CRMQuotation** | Sales quotation header |
| **CRMQuotationItem** | Line items per quotation |
| **CRMTerritory** | Geographic/segment territory definitions |
| **CRMTerritoryUser** | User-territory assignments |
| **CRMEmailTemplate** | Reusable email body templates |
| **CRMMessageTemplate** | SMS/WhatsApp message templates |
| **CRMMessage** | Sent/received message history |
| **CRMCustomField** | Dynamic field definitions per entity type |
| **CRMCustomFieldValue** | Stored values for custom fields |
| **CRMCalendarIntegration** | Google/Outlook calendar sync config |
| **CRMApprovalWorkflow** | Workflow definition (entity, trigger, steps) |
| **CRMApprovalStep** | Individual step in a workflow |
| **CRMApprovalRequest** | In-flight approval instance |
| **CRMApprovalRequestStep** | Per-step tracking for an instance |
| **CRMWebhook** | Outbound webhook configuration |
| **CRMWebhookDelivery** | Individual webhook delivery log |
| **CRMFileAsset** | Uploaded file/document |
| **CRMEnrichmentLog** | Data enrichment history |

### 4.4 Feature Summary

| Feature Area | What's Included |
|-------------|----------------|
| **Lead Management** | Capture, scoring rules, auto-assignment, qualification, stage progression, bulk operations, conversion to contact/deal |
| **Contact Management** | Individual contacts, lifecycle stages, company linkage, email verification, activity timeline |
| **Account Management** | Company profiles, parent-child hierarchy, industry/size segmentation |
| **Deal Pipeline** | Configurable pipelines, stage drag-and-drop, probability weighting, revenue forecasting |
| **Activity Tracking** | Tasks, calls, meetings, emails — all linked to any entity, unified feed |
| **Notes & Mentions** | Rich notes on any record, @mention team members |
| **Communication** | Email templates, bulk email, SMS/WhatsApp via message templates |
| **Calendar Integration** | Google Calendar & Outlook sync, meeting creation from CRM |
| **Quotations** | Quote creation with product line items, PDF generation, email dispatch, status tracking |
| **Product Catalog** | Centralized product/service pricing for use in deals and quotations |
| **Territory Management** | Rule-based territory definitions, user assignment, auto-assignment of leads |
| **Lead Scoring** | Configurable attribute-based scoring rules, real-time score recalculation |
| **Approval Workflows** | Multi-step configurable approvals for deals, discounts, quotations with escalation |
| **Webhooks** | Event-triggered outbound webhooks with delivery tracking and retry |
| **Data Enrichment** | Preview & apply enrichment from external sources, enrichment history |
| **Duplicate Management** | Scan for duplicate leads/contacts, merge records |
| **Custom Fields** | Dynamic field builder per entity (lead, contact, deal, company) |
| **Customer 360** | Unified view of all interactions, deals, files for a company/contact |
| **Lead-to-Cash** | End-to-end flow from lead capture through deal, quotation to invoice |
| **Reports** | Sales funnel, win/loss analysis, revenue trends, territory performance, rep leaderboard |
| **Import/Export** | Bulk CSV import for leads/contacts, entity exports |
| **Automation** | Rule-based automation (create task on deal stage change, etc.) |
| **Campaigns** | Marketing campaign management |
| **AI (CRM)** | Lead scoring suggestions, deal insights via CRM AI adapter |

---

## 5. PMS Module (KaryaFlow)

### 5.1 Frontend Routes (`/pms/*`)

| Path | Page Component | Purpose |
|------|---------------|---------|
| `/pms` | ProjectManagementHomePage | PMS home dashboard |
| `/pms/profile` | ModuleProfilePage | Module info |
| `/pms/command-center` | CommandCenterPage | High-level command center |
| `/pms/enterprise-engine` | EnterpriseEnginePage | Enterprise project governance |
| `/pms/product-launch` | ProductLaunchPage | Product launch planner |
| `/pms/portfolio` | PortfolioPage | Multi-project portfolio view |
| `/pms/dependency-management` | PMSOperationsPage (dependencies) | Cross-project dependencies |
| `/pms/resource-planning` | PMSOperationsPage (resources) | Resource allocation |
| `/pms/agile-execution` | PMSOperationsPage (agile) | Agile execution hub |
| `/pms/project-financials` | PMSOperationsPage (financials) | Project budget & financials |
| `/pms/risk-register` / `/pms/risks` | RisksPage | Risk register |
| `/pms/projects` | ProjectsList | All projects list |
| `/pms/projects/new` | CreateProjectPage | New project form |
| `/pms/projects/:projectId` | ProjectDashboard | Project dashboard |
| `/pms/projects/:projectId/board` | KanbanBoard | Project Kanban |
| `/pms/projects/:projectId/timeline` | GanttPage | Gantt chart |
| `/pms/projects/:projectId/gantt` | GanttPage | Gantt (alias) |
| `/pms/projects/:projectId/milestones` | MilestonesPage | Milestone tracker |
| `/pms/projects/:projectId/files` | FilesPage | Project files |
| `/pms/projects/:projectId/reports` | ReportsPage | Project reports |
| `/pms/projects/:projectId/risks` | RisksPage | Project-level risks |
| `/pms/tasks` | TaskListPage | Global task list |
| `/pms/tasks/:taskId` | TaskDetail | Task detail |
| `/pms/projects/:projectId/tasks/:taskId` | TaskDetail | Task detail (project context) |
| `/pms/work-hub` / `/pms/impact` / `/pms/ai-planner` | ImpactWorkHubPage | AI-powered work hub |
| `/pms/timeline-plus` / `/pms/dependency-timeline` | TimelineDependenciesPage | Timeline with dependencies |
| `/pms/automation-ai` / `/pms/automation` | AutomationAIPage | AI automation rules |
| `/pms/software` / `/pms/issues` | SoftwarePlanningPage | Software/issue tracker |
| `/pms/live` / `/pms/teams-live` | LiveWorkManagementPage | Live team work management |
| `/pms/backlog` | BacklogPage | Product backlog |
| `/pms/roadmap` | RoadmapPage | Epic/release roadmap |
| `/pms/workload` / `/pms/capacity` | WorkloadPage | Team workload & capacity |
| `/pms/releases` | SoftwarePlanningPage | Release planning |
| `/pms/calendar` | CalendarPage | Project calendar |
| `/pms/gantt` | GanttPage | Module-level Gantt |
| `/pms/sprints` | SprintsPage | Sprint management |
| `/pms/files` | FilesPage | Module-level files |
| `/pms/time-tracking` | TimeTrackingPage | Time tracking |
| `/pms/timesheets` | TimesheetsPage | Timesheets |
| `/pms/reports` | ReportsPage | PMS reports |
| `/pms/client-portal` | ClientPortalPage | Client-facing portal |
| `/pms/settings` | SettingsPage | PMS settings |
| `/pms/admin` | AdminPage | PMS admin |
| `/pms/goals`, `/pms/forms`, `/pms/templates`, `/pms/components`, `/pms/workflows`, `/pms/security`, `/pms/dependencies`, `/pms/navigator`, `/pms/apps`, `/pms/dashboards`, `/pms/plans` | CommandCenterPage | Misc command-center views |
| `/pms/issue-navigator-pro`, `/pms/backlog-grooming`, `/pms/sprint-lifecycle`, `/pms/blueprints`, `/pms/resource-utilization` | EnterpriseEnginePage | Enterprise execution tools |

**Auth route:** `/pms/login` → LoginPage

### 5.2 Backend API Endpoints (`backend/app/apps/project_management/api/router.py`)

| Category | Key Endpoints |
|----------|--------------|
| **Clients** | CRUD `/pms/clients/`, GET `/pms/clients/{id}/projects` |
| **Projects** | CRUD `/pms/projects/`, GET `/pms/projects/{id}/dashboard`, GET `/pms/projects/{id}/health`, POST `/pms/projects/{id}/members`, GET `/pms/projects/{id}/budget` |
| **Epics** | CRUD `/pms/epics/`, GET `/pms/projects/{id}/roadmap` |
| **Components** | CRUD `/pms/components/` |
| **Releases** | CRUD `/pms/releases/`, GET `/pms/releases/{id}/readiness` |
| **Boards** | CRUD `/pms/boards/`, CRUD `/pms/board-columns/`, PATCH `/pms/board-columns/{id}/reorder` |
| **Sprints** | CRUD `/pms/sprints/`, POST `/pms/sprints/{id}/start`, POST `/pms/sprints/{id}/complete`, GET `/pms/sprints/{id}/burndown`, GET `/pms/sprints/{id}/velocity`, GET `/pms/sprints/{id}/capacity` |
| **Backlog** | GET `/pms/projects/{id}/backlog`, PATCH `/pms/backlog/prioritize`, POST `/pms/backlog/bulk-move` |
| **Tasks** | CRUD `/pms/tasks/`, GET `/pms/tasks/{id}`, POST `/pms/tasks/bulk`, PATCH `/pms/tasks/{id}/status`, POST `/pms/tasks/{id}/dependencies`, GET `/pms/tasks/by-sprint/{sprintId}`, PATCH `/pms/tasks/{id}/estimate` |
| **Subtasks** | POST `/pms/tasks/{id}/subtasks`, PATCH `/pms/subtasks/{id}` |
| **Checklist** | CRUD `/pms/tasks/{id}/checklist` |
| **Time Logs** | POST `/pms/tasks/{id}/time-logs`, GET `/pms/projects/{id}/time-report` |
| **Files** | POST `/pms/upload`, GET `/pms/files/`, DELETE `/pms/files/{id}` |
| **Activity** | GET `/pms/tasks/{id}/activity`, GET `/pms/projects/{id}/activity` |
| **Gantt** | GET `/pms/projects/{id}/gantt-data` |
| **Milestones** | CRUD `/pms/milestones/` |
| **Risks** | CRUD `/pms/risks/` |
| **Portfolio** | GET `/pms/portfolio/overview`, GET `/pms/portfolio/health` |
| **Reports** | GET `/pms/reports/velocity`, GET `/pms/reports/burndown`, GET `/pms/reports/time-by-member` |
| **Realtime** | WebSocket `/pms/ws/{projectId}` (task updates, sprint events, presence) |

### 5.3 Database Models (`backend/app/apps/project_management/models.py`)

| Model | Purpose |
|-------|---------|
| **PMSClient** | Client/vendor organizations |
| **PMSProject** | Project header (name, type, budget, timeline, health status) |
| **PMSProjectMember** | User-to-project membership with roles |
| **PMSEpic** | Epics for grouping features/stories |
| **PMSComponent** | Technical components (services, libraries) in a project |
| **PMSRelease** | Versioned releases with readiness tracking |
| **PMSBoard** | Kanban/Scrum boards per project |
| **PMSBoardColumn** | Columns in a board with WIP limits |
| **PMSSprint** | Sprint container (goal, start/end, capacity) |
| **PMSTask** | User story / task / bug with estimates, priority, labels |
| **PMSTaskDependency** | Blocked-by / blocks relationships between tasks |
| **PMSTimeLog** | Hour log entries per task per user |
| **PMSChecklistItem** | Sub-checklist items within tasks |
| **PMSFileAsset** | Attachments on tasks or projects |
| **PMSActivity** | Immutable activity history events |

### 5.4 Feature Summary

| Feature Area | What's Included |
|-------------|----------------|
| **Project Management** | Multi-project setup, member roles, budget allocation, health dashboard, client association |
| **Portfolio View** | Cross-project health, status, budget roll-up |
| **Epic & Roadmap** | Epic grouping, visual roadmap timeline |
| **Sprints** | Sprint creation, capacity planning, velocity tracking, burndown chart, start/complete lifecycle |
| **Backlog** | Prioritized backlog, story pointing, bulk sprint assignment, grooming view |
| **Kanban Board** | Drag-and-drop columns, WIP limits, swimlanes |
| **Task Management** | User stories, bugs, subtasks, dependencies (blocked-by/blocks), estimates, labels, priority, attachments |
| **Gantt / Timeline** | Visual Gantt chart with dependencies, milestone markers |
| **Time Tracking** | Log hours per task, project-level time reports |
| **Timesheets** | Weekly timesheet submission and approval |
| **Milestones** | Milestone tracking with status |
| **Release Planning** | Versioned releases, task-to-release assignment, readiness indicator |
| **Component Tracking** | Technical component tagging for tasks |
| **Workload & Capacity** | Per-member workload view, capacity planning per sprint |
| **Risk Register** | Risk identification, impact, probability, mitigation tracking |
| **Dependency Management** | Task and cross-project dependency visualization |
| **Automation & AI** | Automation rules, AI-assisted sprint planning and task assignment |
| **Realtime Collaboration** | WebSocket bridge for live updates, presence, and task push |
| **Client Portal** | Client-accessible read-only project progress view |
| **Reports** | Velocity, burndown, time-by-member |
| **Files** | Project and task-level file uploads |
| **Software Planning** | Issue navigator, sprint lifecycle, backlog grooming (enterprise) |
| **Live Work Management** | Real-time team work board |
| **AI Planner** | AI-powered sprint planning and impact analysis |

---

## 6. Common Shared Features

These features are built once at the platform level and available to all modules:

### Authentication & Access Control
- **JWT tokens** — access + refresh pair, configurable expiry
- **MFA** — TOTP, email OTP, SMS OTP with recovery codes
- **RBAC** — Role/Permission M2M; roles include `super_admin`, `hr_manager`, `ceo`, `manager`, `employee`, `crm_*`, `pms_*`
- **Session management** — device tracking, trusted-device whitelist
- **Password policies** — min length, complexity, expiry, lockout after failed attempts
- **Login attempt audit** — every success/failure logged

### AI Agents Framework
- Multi-turn chat with conversation history
- Tool calling (read/write data via API tools)
- Multi-model: OpenAI GPT-4 and Anthropic Claude adapters
- Per-module AI adapters (HRMS, CRM, PMS, Cross-module)
- Approval workflow for AI-proposed data changes
- Audit log of all AI interactions
- Rate limiting and cost tracking
- Input/output sanitization (advanced security)

### Notifications
- In-app notification center
- Email dispatch via SMTP
- Notification preferences per user

### Workflow Engine
- Dynamic multi-step approval workflows
- Condition-based routing
- SLA and escalation support
- Reusable across all modules

### Audit & Observability
- `AuditLogMiddleware` — logs every API request (user, method, path, status, duration, request ID)
- Error log viewer
- Session audit trail
- AI interaction audit

### Custom Fields
- Admin-definable dynamic fields for any entity
- Reused in HRMS (employees), CRM (leads, contacts, deals, companies), future modules

### Document Management
- Upload with MIME validation
- Document verification workflow
- Expiry tracking and alerts

### File Assets
- Each module manages its own file assets (CRMFileAsset, PMSFileAsset, HRMS DocumentRecord)
- Shared upload validation rules (10 MB limit, allowed extensions: pdf, doc, docx, jpg, jpeg, png)

### Cross-Module Routes
| Route | Purpose |
|-------|---------|
| `/login`, `/hrms/login`, `/crm/login`, `/pms/login` | Module-specific login pages |
| `/` | ModuleIndexPage (auto-redirects based on installed apps) |
| `/ai-agents/*` | AI agent management (shared) |

### Configuration
- `INSTALLED_APPS` backend env var toggles which module APIs load
- `VITE_INSTALLED_APPS` frontend env var toggles which module routes are registered
- Rate limiting: 60 requests/minute (configurable)
- CORS: configured per deployment

---

## 7. Unique Per-Module Features

### Exclusive to HRMS
| Feature | Why HRMS Only |
|---------|--------------|
| **Payroll engine** | Salary structures, runs, payslips, bank advice, GL export — not applicable to CRM/PMS |
| **Statutory compliance** | PF/ESI/PT/LWF/Gratuity/TDS/Form-16/24Q — India-specific HR compliance |
| **Full & Final Settlement** | Employee exit payout calculations |
| **Leave management** | Leave types, balances, accrual, ledger — HR-specific |
| **Attendance + biometric** | Punch tracking, shift rosters, geo-fence — workforce management |
| **Recruitment pipeline** | Job openings → interviews → offers — HR function |
| **Onboarding checklists** | New hire process — HR function |
| **Background verification** | Pre-employment checks |
| **Performance & 360 feedback** | Appraisal cycles, competencies — people management |
| **Benefits administration** | Health plans, ESOP, claims — HR function |
| **Engagement** | Announcements, polls, recognition — employee experience |
| **Learning Management (LMS)** | Courses, enrollments, assessments |
| **WhatsApp ESS** | Conversational HR self-service over WhatsApp |
| **Probation management** | Trial period confirmation/extension |
| **DE&I analytics** | Diversity, equity & inclusion metrics |
| **Org chart** | Real-time org hierarchy visualization |
| **SSO** | Enterprise single sign-on (HR-led identity) |
| **Enterprise multi-org** | Multi-legal-entity payroll & HR setup |
| **Tax declarations** | Investment proofs, regime selection |
| **AI: Resume parsing** | Extract structured data from uploaded resumes |
| **AI: Attrition prediction** | ML-based flight-risk scoring for employees |
| **AI: Payroll anomaly detection** | Flag unusual payroll component values |

### Exclusive to CRM
| Feature | Why CRM Only |
|---------|-------------|
| **Lead scoring rules** | Attribute-weighted scoring — sales qualification |
| **Sales pipeline** | Kanban deal stages — sales process |
| **Revenue forecasting** | Deal probability × amount roll-up |
| **Quotation generation** | Proposals with line items and PDF |
| **Product catalog** | Products/services for deal and quote line items |
| **Territory management** | Geographic/segment-based rep assignment |
| **Data enrichment** | Company/contact data augmentation from external sources |
| **Duplicate detection & merge** | CRM-specific data hygiene |
| **Webhook delivery tracking** | CRM event-driven integration |
| **Calendar integration** | Google/Outlook sync for sales meetings |
| **Lead-to-cash flow** | End-to-end sales → billing pipeline |
| **Customer 360 view** | Full interaction history per company/contact |
| **Win/loss analysis** | Sales outcome reporting |
| **Rep leaderboard** | Sales performance comparison |
| **Marketing campaigns** | Campaign management |

### Exclusive to PMS
| Feature | Why PMS Only |
|---------|-------------|
| **Sprint planning** | Agile velocity/capacity/burndown — software delivery |
| **Kanban WIP limits** | Column-level work-in-progress constraints |
| **Gantt / timeline** | Visual project timeline with dependencies |
| **Task dependencies** | Blocked-by/blocks graph — project scheduling |
| **Epics & roadmap** | Feature grouping and strategic roadmap view |
| **Releases** | Version-based release readiness tracking |
| **Components** | Technical component tracking for software projects |
| **Portfolio management** | Cross-project health and budget roll-up |
| **Risk register** | Formal risk identification and mitigation |
| **Realtime WebSocket** | Live board updates and presence — collaboration |
| **Client portal** | External client project visibility |
| **Workload / capacity** | Per-member utilization view for resource planning |
| **Milestones** | Project milestone tracking |
| **AI sprint planner** | AI-suggested sprint composition |
| **Live work management** | Real-time team activity board |

---

## 8. AI Agents Framework

**Location:** `backend/app/ai_agents/` (30 files)

### Architecture

```
orchestrator.py          ← Routes user message to right module adapter
├── hrms_ai_adapter.py   ← HR tools: payroll calc, leave, attrition, docs
├── crm_ai_adapter.py    ← Sales tools: lead score, deal pipeline, territory
├── pms_ai_adapter.py    ← Project tools: sprint plan, task assign, timeline
└── cross_module_ai_adapter.py  ← Cross-module queries
```

### Components

| File | Role |
|------|------|
| `models.py` | DB models for conversations, messages, tool calls |
| `schemas.py` | Pydantic schemas for AI API |
| `prompts.py` | System prompts per module |
| `api.py` | `/ai/chat` endpoint, conversation history |
| `openai_service.py` | OpenAI streaming + function calling |
| `conversations.py` | Conversation history management |
| `approvals.py` | Approval request creation for AI-proposed changes |
| `approval_executor.py` | Execute approved AI actions |
| `registry.py` | Agent type registration |
| `system_prompt_builder.py` | Dynamic context-aware prompt builder |
| `rate_limit.py` | Per-user AI API rate limiting |
| `audit.py` | AI interaction audit logging |
| `advanced_security.py` | Input sanitization, output filtering |
| `ai_tool_registry_service.py` | Tool registration system |
| `ai_tool_execution_service.py` | Tool execution engine |
| `ai_tool_definition_builder.py` | Dynamic tool definitions from API metadata |
| `definitions.py` | Static tool schemas |
| `tool_schemas.py` | Tool parameter validation |

### AI Capabilities by Module

**HRMS AI:**
- Natural language HR queries (employee info, leave balances, payslips)
- Resume parsing — extracts structured data from PDF/DOCX
- Attrition prediction — ML-based flight-risk scoring
- Payroll anomaly detection — flags unusual component values
- Helpdesk AI reply suggestions

**CRM AI:**
- Lead scoring suggestions
- Deal insight generation
- Territory assignment recommendations
- Email template suggestions

**PMS AI:**
- Sprint composition suggestions
- Task assignment optimization
- Timeline risk identification
- Impact analysis for scope changes

**Cross-Module:**
- Employee-project assignment (HRMS ↔ PMS)
- Customer-to-deal linking queries (CRM ↔ PMS)

---

## 9. Authentication & Security

**Location:** `backend/app/core/security.py`, `backend/app/core/config.py`, `backend/app/core/deps.py`

### Auth Flow
1. User POSTs credentials to `/api/v1/auth/login`
2. Server verifies password hash (bcrypt), checks lockout policy
3. If MFA enrolled: returns MFA challenge; user submits TOTP/OTP
4. Server issues **access token** (JWT, 60 min) + **refresh token** (JWT, 7 days)
5. `UserSession` record created with device fingerprint
6. All subsequent requests: `Authorization: Bearer <access_token>`
7. Token refresh via `/auth/refresh`; logout invalidates session

### Key Functions
| Function | Purpose |
|----------|---------|
| `verify_access_token()` | Validates JWT with secret key |
| `verify_refresh_token()` | Validates refresh token |
| `get_password_hash()` | bcrypt hash |
| `verify_password()` | bcrypt comparison |
| `RequirePermission(perm)` | FastAPI dependency enforcing a named permission |
| `require_roles(*roles)` | FastAPI dependency enforcing a role set |

### Middleware Stack (applied in order)
1. `RequestIDMiddleware` — injects `X-Request-ID` header
2. `CORSMiddleware` — origin allowlist from config
3. `GZipMiddleware` — response compression
4. `AuditLogMiddleware` — logs method, path, user, status, duration to AuditLog table
5. Rate limiter — 60 req/min per IP (configurable)

### Roles
`super_admin`, `hr_admin`, `hr_manager`, `payroll_manager`, `ceo`, `manager`, `employee`, `crm_admin`, `crm_manager`, `crm_rep`, `pms_admin`, `pms_manager`, `pms_member`

---

## 10. Configuration & Deployment

### Backend Environment Variables (`backend/.env`)

```env
# Database
DATABASE_URL=mysql+pymysql://user:password@host:3306/aihrms

# Module selection
INSTALLED_APPS=hrms,crm,project_management

# Security
SECRET_KEY=<random-256-bit>
REFRESH_SECRET_KEY=<random-256-bit>
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
BACKEND_CORS_ORIGINS=http://localhost:5173,http://localhost:5174

# Email
MAIL_SERVER=smtp.example.com
MAIL_PORT=587
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_FROM=noreply@example.com

# AI
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# Uploads
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE_MB=10
ALLOWED_EXTENSIONS=pdf,doc,docx,jpg,jpeg,png

# Rate limiting
RATE_LIMIT_PER_MINUTE=60

# Background jobs
REDIS_URL=redis://localhost:6379
CELERY_BROKER_URL=redis://localhost:6379/0
```

### Frontend Environment Variables (`frontend/.env`)

```env
VITE_INSTALLED_APPS=hrms,crm,project_management
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

### Local Dev Setup

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate         # Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev                   # serves on http://localhost:5173
```

### Production Deployment
- Backend and frontend are **independently hosted** (separate origins)
- Frontend uses `VITE_API_BASE_URL` to point to backend
- Uploads stored in `uploads/` directory (not git-tracked)
- Database: MySQL 8.x in production
- Migrations: `alembic upgrade head` on each deploy

---

## 11. Tech Stack

### Backend
| Layer | Technology |
|-------|-----------|
| Framework | FastAPI (Python 3.11+) |
| ORM | SQLAlchemy 2.x |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Auth | PyJWT, passlib (bcrypt) |
| Background Jobs | Celery + Redis |
| AI — OpenAI | `openai` Python SDK |
| AI — Anthropic | `anthropic` Python SDK |
| PDF Generation | (payslip PDF, quotation PDF) |
| CSV / Excel | openpyxl, csv |

### Frontend
| Layer | Technology |
|-------|-----------|
| Framework | React 18 |
| Language | TypeScript |
| Build | Vite |
| Styling | Tailwind CSS + Shadcn/ui (Radix primitives) |
| State | Zustand |
| Server state | React Query (TanStack Query) |
| Routing | React Router v6 |
| HTTP | Axios |
| Charts | D3.js (custom) |
| Dates | date-fns |
| Icons | Lucide React |

### Infrastructure
| Concern | Technology |
|---------|-----------|
| Database | MySQL 8 (prod), SQLite (local) |
| Cache / Queue | Redis |
| File Storage | Local `uploads/` (S3-ready) |
| Realtime | WebSocket (PMS module) |

---

## 12. Counts & Metrics

| Metric | Count |
|--------|-------|
| **Backend route files (HRMS)** | 42 files in `api/v1/` |
| **CRM API router** | 1 file (~240 KB, 200+ endpoints) |
| **PMS API router** | 1 file (~3.6 MB, 300+ endpoints) |
| **HRMS database model files** | 26 files |
| **CRM database models** | 35 models in single file |
| **PMS database models** | 15 models in single file |
| **HRMS frontend pages** | 43 page components |
| **CRM frontend routes** | 41 routes |
| **PMS frontend routes** | 58 routes |
| **Shared frontend components** | 30+ (layout + AI + Shadcn/ui) |
| **AI agent files** | 30 files in `ai_agents/` |
| **AI model adapters** | 4 (HRMS, CRM, PMS, Cross-module) |
| **Total backend Python files** | 100+ |
| **Total frontend TypeScript files** | 150+ |

---

*This report reflects the state of the codebase as of 2026-05-23 on branch `codex/crm-database-persistence`. For architecture decisions and module split strategy, see `docs/multi_app_architecture.md`.*
