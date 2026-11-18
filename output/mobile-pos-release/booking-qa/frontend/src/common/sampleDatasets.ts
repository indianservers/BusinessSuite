export type SampleDatasetCategory = {
  id: string;
  name: string;
  description: string;
  apps: Array<"HRMS" | "CRM" | "Project Management">;
  examples: string[];
  suggestedRecords: string;
};

export const sampleDatasetCategories: SampleDatasetCategory[] = [
  {
    id: "organizations",
    name: "Organizations & Workspaces",
    description: "Tenant profiles, industries, currencies, locations, and workspace settings.",
    apps: ["HRMS", "CRM", "Project Management"],
    examples: ["Apex Digital Solutions", "GreenField Realty", "BrightPath Academy"],
    suggestedRecords: "8-12 organizations",
  },
  {
    id: "users-roles",
    name: "Users, Roles & Permissions",
    description: "Admins, managers, members, clients, sales teams, support agents, and viewers.",
    apps: ["HRMS", "CRM", "Project Management"],
    examples: ["Super Admin", "Project Manager", "Sales Executive", "Client"],
    suggestedRecords: "25-40 users",
  },
  {
    id: "teams-departments",
    name: "Teams & Departments",
    description: "Functional teams, reporting groups, cost centers, sales territories, and delivery pods.",
    apps: ["HRMS", "CRM", "Project Management"],
    examples: ["Engineering", "Sales North", "Client Delivery", "Support Desk"],
    suggestedRecords: "10-18 teams",
  },
  {
    id: "employees",
    name: "Employees & Profiles",
    description: "Employee master records, designations, managers, joining details, and profile completeness.",
    apps: ["HRMS"],
    examples: ["Employee directory", "Manager hierarchy", "Work anniversaries"],
    suggestedRecords: "80-150 employees",
  },
  {
    id: "attendance-leave",
    name: "Attendance, Leave & Timesheets",
    description: "Daily attendance, shifts, holidays, leave requests, balances, and weekly timesheets.",
    apps: ["HRMS", "Project Management"],
    examples: ["WFH punches", "Annual leave", "Billable timesheet entries"],
    suggestedRecords: "300-800 events",
  },
  {
    id: "payroll-benefits",
    name: "Payroll, Benefits & Finance",
    description: "Salary structures, payroll runs, benefits enrollment, deductions, reimbursements, and payslips.",
    apps: ["HRMS"],
    examples: ["Monthly payroll", "ESI/PF deductions", "Flexi benefit claims"],
    suggestedRecords: "6-12 payroll cycles",
  },
  {
    id: "leads",
    name: "Leads & Lead Sources",
    description: "CRM leads categorized by source, rating, status, industry, owner, and follow-up date.",
    apps: ["CRM"],
    examples: ["Website leads", "Referral leads", "Event leads", "Hot leads"],
    suggestedRecords: "100-250 leads",
  },
  {
    id: "accounts-contacts",
    name: "Companies & Contacts",
    description: "Customer accounts, contacts, lifecycle stages, account status, and communication preferences.",
    apps: ["CRM"],
    examples: ["Apex Digital Solutions", "Procurement contact", "Decision maker"],
    suggestedRecords: "50 companies, 120 contacts",
  },
  {
    id: "deals-pipelines",
    name: "Deals & Sales Pipelines",
    description: "Deals across stages with amount, probability, expected revenue, owner, and close dates.",
    apps: ["CRM"],
    examples: ["ERP Implementation Deal", "Annual Software License", "Support Renewal"],
    suggestedRecords: "40-100 deals",
  },
  {
    id: "crm-activities",
    name: "CRM Activities & Follow-ups",
    description: "Calls, emails, meetings, notes, tasks, demos, proposals, and overdue follow-ups.",
    apps: ["CRM"],
    examples: ["Discovery call", "Proposal follow-up", "Product demo"],
    suggestedRecords: "200-500 activities",
  },
  {
    id: "projects",
    name: "Projects & Workspaces",
    description: "Project records with managers, clients, budgets, priorities, progress, and health.",
    apps: ["Project Management"],
    examples: ["Website Redesign", "Mobile App Development", "ERP Implementation"],
    suggestedRecords: "10-25 projects",
  },
  {
    id: "tasks-kanban",
    name: "Tasks, Kanban & Dependencies",
    description: "Backlog items, board columns, assignees, priorities, due dates, blockers, and dependencies.",
    apps: ["Project Management"],
    examples: ["To Do", "In Progress", "In Review", "Blocked", "Done"],
    suggestedRecords: "150-400 tasks",
  },
  {
    id: "milestones-sprints",
    name: "Milestones, Sprints & Approvals",
    description: "Delivery milestones, sprint plans, capacity, velocity, client approvals, and rejection reasons.",
    apps: ["Project Management"],
    examples: ["Phase 1 Sign-off", "Sprint 12", "Client approval pending"],
    suggestedRecords: "30 milestones, 12 sprints",
  },
  {
    id: "files-documents",
    name: "Files, Documents & Attachments",
    description: "Metadata for uploaded files, versions, visibility rules, linked entities, and shared deliverables.",
    apps: ["HRMS", "CRM", "Project Management"],
    examples: ["Offer letter", "Quote PDF", "Scope document", "Client deliverable"],
    suggestedRecords: "150-300 files",
  },
  {
    id: "reports-audit",
    name: "Reports, Notifications & Audit Logs",
    description: "Dashboard metrics, notifications, audit trails, exports, insights, and system activity.",
    apps: ["HRMS", "CRM", "Project Management"],
    examples: ["Overdue alerts", "Audit log", "Revenue report", "Project health insight"],
    suggestedRecords: "500-1,000 events",
  },
];
