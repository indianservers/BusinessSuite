export type DemoLogin = {
  label: string;
  email: string;
  password: string;
  description: string;
};

export const moduleDefaultCredentials = {
  hrms: [
    { label: "HRMS Admin", email: "admin@aihrms.com", password: "Admin@123456", description: "HRMS configuration and system access" },
    { label: "HR Manager", email: "hr@aihrms.com", password: "HR@123456", description: "Employees, leave, payroll, recruitment, HR operations" },
    { label: "Manager", email: "manager@aihrms.com", password: "Manager@123456", description: "Team leave, attendance, performance, reports" },
    { label: "Employee", email: "employee@aihrms.com", password: "Employee@123456", description: "Self-service attendance, leave, payslip, helpdesk" },
  ],
  crm: [
    { label: "CRM Admin", email: "admin@vyaparacrm.com", password: "Password@123", description: "CRM users, settings, reports, automation" },
    { label: "Sales Manager", email: "manager@vyaparacrm.com", password: "Password@123", description: "Pipeline, deals, forecasts, sales team" },
    { label: "Sales Executive", email: "executive@vyaparacrm.com", password: "Password@123", description: "Leads, contacts, activities, assigned deals" },
    { label: "Support Agent", email: "support@vyaparacrm.com", password: "Password@123", description: "Customer records and support tickets" },
    { label: "Marketing", email: "marketing@vyaparacrm.com", password: "Password@123", description: "Campaigns, imports, segments, performance" },
  ],
  project_management: [
    { label: "PMS Admin", email: "admin@karyaflow.com", password: "Password@123", description: "Project settings, users, workflows, reports" },
    { label: "Project Manager", email: "manager@karyaflow.com", password: "Password@123", description: "Projects, tasks, milestones, approvals" },
    { label: "Team Member", email: "member@karyaflow.com", password: "Password@123", description: "Assigned work, board updates, files, time logs" },
    { label: "Client", email: "client@karyaflow.com", password: "Password@123", description: "Client portal, deliverables, approvals" },
  ],
  srm: [
    { label: "SRM Admin", email: "admin@srmflow.com", password: "Password@123", description: "SRM settings, approvals, lifecycle controls" },
    { label: "Sales Manager", email: "sales.manager@srmflow.com", password: "Password@123", description: "Team sales orders, engagements, revenue dashboards" },
    { label: "Sales Executive", email: "sales.executive@srmflow.com", password: "Password@123", description: "Assigned sales orders and engagement handoffs" },
    { label: "Finance Manager", email: "finance@srmflow.com", password: "Password@123", description: "Invoices, approvals, receipts, profitability" },
    { label: "Collections", email: "collections@srmflow.com", password: "Password@123", description: "Aging, reminders, receipts, allocations" },
  ],
  fam: [
    { label: "FAM Admin", email: "admin@financeflow.com", password: "Password@123", description: "Company books, settings, chart, audit controls" },
    { label: "Accountant", email: "accountant@financeflow.com", password: "Password@123", description: "Ledgers, opening balances, cost centers, branches" },
    { label: "Finance Manager", email: "finance.manager@financeflow.com", password: "Password@123", description: "Operational finance setup and books review" },
    { label: "Auditor", email: "auditor@financeflow.com", password: "Password@123", description: "Read-only books and audit logs" },
    { label: "Viewer", email: "viewer@financeflow.com", password: "Password@123", description: "Read-only financial foundation pages" },
  ],
} as const satisfies Record<string, readonly DemoLogin[]>;

export type CredentialModuleKey = keyof typeof moduleDefaultCredentials;
