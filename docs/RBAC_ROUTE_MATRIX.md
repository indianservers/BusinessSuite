# HRMS RBAC Route Matrix

Date: 2026-06-04  
Scope: Frontend HRMS route/menu/search RBAC only  
Roles verified: Admin, HR, Employee, hr_company_admin, hr_workflow_admin, hr_custom_field_admin

## Certification Notes

- Frontend route guards are enforced through `canAccessRoute`.
- Direct URL denial renders the standard `403 Access Denied` page with role, requested page and required permission.
- Global Search filters results through the same route permission helper.
- Backend/API authorization is outside this matrix and must remain separately certified.

## Route Matrix

| Route | Page / Component | Allowed roles | Denied roles | Visible in UI | Direct URL protected | Search can expose | Expected result |
|---|---|---|---|---|---|---|---|
| `/hrms` | HRMS entry | Admin, HR, Employee, delegated HR | Non-HRMS roles | Yes | Yes | Yes | Opens HRMS role home or entry. |
| `/hrms/dashboard` | Dashboard | Admin, HR | Employee | Admin/HR | Yes | Yes, permitted roles only | Employee gets 403. |
| `/hrms/role-home` | Role home | Admin, HR | Employee | No | Yes | No | Employee gets 403. |
| `/hrms/admin-home` | Admin home | Admin | HR, Employee, delegated HR | Admin | Yes | No | Non-admin gets 403. |
| `/hrms/hr-home` | HR home | Admin, HR, delegated HR | Employee | HR/delegated HR | Yes | No | Employee gets 403. |
| `/hrms/executive-home` | Executive home | Admin | HR, Employee, delegated HR | No | Yes | No | Non-admin gets 403 in tested roles. |
| `/hrms/manager-dashboard` | Manager dashboard | Admin, HR | Employee | No | Yes | No | Employee gets 403. |
| `/hrms/ess` | ESS dashboard | Admin, HR, Employee, delegated HR | None tested | Employee | Yes | Yes | Employee opens self-service. |
| `/hrms/profile` | My Profile | Admin, HR, Employee, delegated HR | None tested | Employee/profile menu | Yes | Yes | Employee opens own profile surface. |
| `/hrms/my-attendance` | My Attendance | Admin, HR, Employee, delegated HR | None tested | Employee | Yes | No | Employee opens self attendance only. |
| `/hrms/my-roster` | My Roster | Admin, HR, Employee, delegated HR | None tested | Employee | Yes | No | Employee opens self roster only. |
| `/hrms/my-payslips` | My Payslips | Admin, HR, Employee, delegated HR | None tested | Employee | Yes | No | Employee opens self payslip viewer. |
| `/hrms/documents` | Documents | Admin, HR, Employee, delegated HR | None tested | Employee/Admin/HR | Yes | No | Employee sees self documents surface. |
| `/hrms/workflow` | My Requests / Inbox | Admin, HR, Employee, delegated HR | None tested | All tested roles | Yes | No | Employee sees self requests only. |
| `/hrms/workflow/admin` | Approval administration pattern | Admin, HR, delegated HR | Employee | No | Yes | No | Employee gets 403. |
| `/hrms/notifications` | Notifications | Admin, HR, delegated HR | Employee | HR/Admin only | Yes | No | Employee gets 403 and topbar bell is hidden. |
| `/hrms/employee-directory` | Employee directory | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/employees` | Employee master | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/employees/new` | Employee creation | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/employees/:id` | Employee detail | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/employees/bulk-import` | Bulk employee import pattern | Admin, HR, delegated HR | Employee | No | Yes | No | Employee gets 403. |
| `/hrms/employee-master` | Legacy employee master pattern | Admin only by fallback | HR, Employee, delegated HR | No | Yes | No | Employee gets 403. |
| `/hrms/probation` | Probation | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/attendance` | Attendance register | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/attendance/bulk-import` | Attendance bulk import pattern | Admin, HR, delegated HR | Employee | No | Yes | No | Employee gets 403. |
| `/hrms/attendance/shift-roster` | Shift roster admin | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/timesheets` | Timesheets | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/leave` | Leave | Admin, HR, Employee, delegated HR | None tested | All tested roles | Yes | No | Employee can apply/track leave. |
| `/hrms/payroll` | Payroll operations | Admin, HR, delegated HR | Employee | HR/Admin | Yes | Yes, permitted roles only | Employee gets 403. |
| `/hrms/payroll/setup` | Payroll setup pattern | Admin, HR, delegated HR | Employee | No | Yes | No | Employee gets 403. |
| `/hrms/payroll/run` | Payroll run pattern | Admin, HR, delegated HR | Employee | No | Yes | No | Employee gets 403. |
| `/hrms/payroll/tools` | Payroll tools pattern | Admin, HR, delegated HR | Employee | No | Yes | No | Employee gets 403. |
| `/hrms/payroll/reports` | Payroll reports pattern | Admin, HR, delegated HR | Employee | No | Yes | No | Employee gets 403. |
| `/hrms/payroll/bulk-publish` | Payroll bulk publish pattern | Admin, HR, delegated HR | Employee | No | Yes | No | Employee gets 403. |
| `/hrms/payroll/bulk-export` | Payroll bulk export pattern | Admin, HR, delegated HR | Employee | No | Yes | No | Employee gets 403. |
| `/hrms/investment-declaration` | Investment declaration | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/fnf-settlements` | F&F settlement | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/benefits` | Benefits | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/recruitment` | Recruitment | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/performance` | Performance | Admin, HR, delegated HR | Employee | HR/Admin | Yes | Yes, permitted roles only | Employee gets 403. |
| `/hrms/lms` | LMS | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/engagement` | Engagement | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/statutory-compliance` | Statutory compliance | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/background-verification` | BGV | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/whatsapp-ess` | WhatsApp ESS admin | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/helpdesk` | Helpdesk | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/reports` | Reports | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/advanced-analytics` | Advanced analytics | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/company` | Company setup | Admin, hr_company_admin | HR, Employee, other delegated HR | Admin/delegated company only | Yes | Yes, permitted roles only | Regular HR and employee get 403. |
| `/hrms/workflow-designer` | Workflow designer | Admin, hr_workflow_admin | HR, Employee, other delegated HR | Admin/delegated workflow only | Yes | No | Regular HR and employee get 403. |
| `/hrms/custom-fields` | Custom fields | Admin, hr_custom_field_admin | HR, Employee, other delegated HR | Admin/delegated custom field only | Yes | No | Regular HR and employee get 403. |
| `/hrms/enterprise` | Enterprise settings | Admin | HR, Employee, delegated HR | Admin | Yes | No | Non-admin gets 403. |
| `/hrms/settings` | Settings | Admin | HR, Employee, delegated HR | Admin | Yes | No | Non-admin gets 403. |
| `/hrms/security` | Security settings pattern | Admin only by fallback | HR, Employee, delegated HR | No | Yes | No | Non-admin gets 403. |
| `/hrms/logs` | Audit logs | Admin | HR, Employee, delegated HR | Admin | Yes | No | Non-admin gets 403. |
| `/hrms/audit-log` | Audit log pattern | Admin only by fallback | HR, Employee, delegated HR | No | Yes | No | Employee gets 403. |
| `/hrms/org-chart` | Org chart | Admin, HR, delegated HR | Employee | HR/Admin | Yes | Search item points to company and is filtered | Employee gets 403. |
| `/hrms/assets` | Assets | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/onboarding` | Onboarding | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/exit` | Exit | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |
| `/hrms/ai-assistant` | AI assistant | Admin, HR, delegated HR | Employee | HR/Admin | Yes | No | Employee gets 403. |

## Delegated HR Validation

| Role | Additional route granted | Routes still denied | UI exposure |
|---|---|---|---|
| `hr_company_admin` | `/hrms/company` | Workflow Designer, Custom Fields, Enterprise, Settings, Logs, Security | Company only under delegated admin. |
| `hr_workflow_admin` | `/hrms/workflow-designer` | Company, Custom Fields, Enterprise, Settings, Logs, Security | Workflow Designer only under delegated admin. |
| `hr_custom_field_admin` | `/hrms/custom-fields` | Company, Workflow Designer, Enterprise, Settings, Logs, Security | Custom Fields only under delegated admin. |

