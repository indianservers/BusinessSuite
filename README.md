# Business Suite

Database setup: [PostgreSQL local and remote instructions](POSTGRESQL_SETUP.md).

Business Suite is a modular ERP platform for HRMS, Project Management, CRM, and future business apps. The current HRMS app combines core HR, employee self-service, payroll, attendance, leave, documents, compliance, talent, analytics, and AI-assisted workflows in one platform.

## Highlights

- Role-based access for Admin, HR, Manager, CEO, and Employee users
- Employee master data with lifecycle events, documents, certificates, profile completeness, and change approvals
- Employee self-service portal for payslips, leave, attendance, documents, goals, tickets, and assets
- Manager dashboard with team attendance, approvals, calendar, birthdays, and work anniversaries
- Leave management with leave types, balances, ledger, requests, approval/rejection, and team calendar
- Attendance with check-in/out, shifts, holidays, roster foundation, regularization, geo/biometric foundations, and monthly summaries
- Payroll setup wizard for legal entity, pay group, salary components, salary structures, tax cycle, and statutory profiles
- Payroll run console with pre-run checks, employee worksheet, reprocess, approval, exports, payment batch, GL journal, and variance review
- Payslip viewer with HTML preview, PDF generation, print-friendly styling, and bulk publish/email action
- India payroll and compliance foundations for PF, ESI, PT, LWF, gratuity, TDS, Form 16, 24Q, challans, and statutory calendar
- Benefits administration for plans, enrollments, flexi benefits, claims, payroll deductions, ESOP grants, and vesting
- Recruitment, onboarding, background verification, performance, 360 feedback, competencies, skill gaps, and compensation planning foundations
- Engagement module with announcements, polls, recognition wall, reactions, and people moments
- Helpdesk with categories, tickets, replies, SLA tracking, escalation, knowledge base, and AI reply support
- Dynamic custom fields, custom forms, report builder foundations, DE&I analytics, and governed metrics
- Real-time org chart, global search, breadcrumbs, keyboard shortcuts, session timeout warning, and responsive PWA foundation
- Audit logs, error logs, sessions, MFA method records, password policies, consent, retention, legal hold, webhooks, and integration events
- AI assistant foundation for HR, payroll, documents, benefits, performance, hiring, and operations queries

## Tech Stack

- Backend: FastAPI, SQLAlchemy, Alembic, Pydantic, JWT auth
- Database: PostgreSQL for local and production; SQLite for isolated unit tests
- Frontend: React, TypeScript, Vite, Tailwind CSS, React Query, Zustand
- Reporting/files: CSV exports, payslip PDF generation, upload storage
- AI integrations: OpenAI and Anthropic-ready service layer

## Repository Structure

```text
backend/                 FastAPI API, models, schemas, CRUD, migrations, tests
backend/app/apps/        Deployable app modules: HRMS, CRM, Project Management
backend/app/common/      Notes for shared backend platform boundaries
frontend/                React/Vite shell, shared services, UI components
frontend/src/apps/       Deployable frontend modules: HRMS, CRM, Project Management
frontend/src/common/     Notes for shared frontend platform boundaries
docs/                    Gap analysis, todo list, implementation notes
```

## Multi-App Deployment

The suite can load only selected product modules.

Backend:

```env
INSTALLED_APPS=hrms
```

```env
INSTALLED_APPS=crm,project_management
```

Frontend:

```env
VITE_INSTALLED_APPS=hrms
```

```env
VITE_INSTALLED_APPS=crm,project_management
```

See `docs/multi_app_architecture.md` for the module split and next cleanup
step around common people/profile data.

## Local Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Create a backend `.env` when needed:

```env
DATABASE_URL=postgresql+psycopg://user:encoded-password@host:5432/business_suite
BACKEND_CORS_ORIGINS=http://localhost:5173,http://localhost:5174
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
```

## Local Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Optional frontend `.env`:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## Common Commands

```bash
# Backend tests
cd backend
pytest

# Frontend production build
cd frontend
npm run build
```

## Deployment Notes

- Backend and frontend are designed to be hosted separately.
- Frontend API routing is controlled by `VITE_API_BASE_URL` / runtime config.
- Backend database configuration is controlled by `DATABASE_URL`.
- Upload folders are runtime storage and are intentionally ignored by git.

## Current Product Status

The project has moved beyond MVP into a broad HRMS foundation with production-grade database/API coverage across HR, payroll, compliance, talent, documents, workflow, and analytics. Some modules still need final production integrations such as government portal connectors, e-sign, biometric vendor SDKs, WhatsApp Business dispatch, SSO, and scheduled report exports.
