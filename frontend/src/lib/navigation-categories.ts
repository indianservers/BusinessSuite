type NavigationItem = { to: string; group?: string };
type Category = { name: string; paths: readonly string[] };

// Presentation only: permissions and the set of available links are resolved by roles.ts.
const categories: Record<string, readonly Category[]> = {
  project_management: [
    { name: "Overview", paths: ["/pms", "/pms/overview", "/pms/management", "/pms/command-center", "/pms/workspace-tools"] },
    { name: "Tasks & projects", paths: ["/pms/my-work", "/pms/tasks", "/pms/tasks-follow-ups", "/pms/follow-ups", "/pms/navigator", "/pms/issue-navigator-pro", "/pms/projects", "/pms/workspaces", "/pms/product-launch", "/pms/work-hub", "/pms/software", "/pms/issues", "/pms/releases"] },
    { name: "Planning & workload", paths: ["/pms/backlog", "/pms/backlog-grooming", "/pms/sprints", "/pms/sprint-lifecycle", "/pms/agile-execution", "/pms/calendar", "/pms/planner", "/pms/gantt", "/pms/timeline-plus", "/pms/dependency-timeline", "/pms/dependency-management", "/pms/roadmap", "/pms/dependencies", "/pms/workload", "/pms/capacity", "/pms/resource-utilization", "/pms/resource-planning", "/pms/risk-register", "/pms/goals"] },
    { name: "People & teams", paths: ["/pms/members", "/pms/people", "/pms/teams", "/pms/org-chart", "/pms/people-work"] },
    { name: "Collaboration", paths: ["/pms/live", "/pms/teams-live", "/pms/notes", "/pms/messages", "/pms/docs", "/pms/files", "/pms/my-notices", "/pms/client-portal", "/pms/time-tracking", "/pms/timesheets"] },
    { name: "Reports & finances", paths: ["/pms/reports", "/pms/analytics", "/pms/dashboards", "/pms/portfolio", "/pms/project-financials"] },
    { name: "Settings & tools", paths: ["/pms/settings", "/pms/admin", "/pms/plans", "/pms/enterprise-engine", "/pms/blueprints", "/pms/forms", "/pms/templates", "/pms/components", "/pms/workflows", "/pms/apps", "/pms/security", "/pms/automation", "/pms/audit-logs", "/pms/custom-fields", "/pms/task-types", "/pms/tags", "/pms/recovery", "/pms/trash"] },
    { name: "AI tools", paths: ["/pms/operator", "/pms/ai-planner", "/ai-agents"] },
  ],
  hrms: [
    { name: "Overview", paths: ["/hrms", "/hrms/dashboard", "/hrms/admin-home", "/hrms/hr-home", "/hrms/executive-home", "/hrms/ess", "/hrms/role-home"] },
    { name: "People & organization", paths: ["/hrms/employees", "/hrms/employee-directory", "/hrms/profile", "/hrms/profile-management", "/hrms/interns", "/hrms/manager-dashboard", "/hrms/org-chart", "/settings/company-profile", "/hrms/company"] },
    { name: "Attendance & leave", paths: ["/hrms/attendance", "/hrms/my-attendance", "/hrms/my-roster", "/hrms/timesheets", "/hrms/leave"] },
    { name: "Payroll & benefits", paths: ["/hrms/payroll", "/hrms/my-payslips", "/hrms/investment-declaration", "/hrms/fnf-settlements", "/hrms/benefits", "/hrms/expenses"] },
    { name: "Recruitment & employee lifecycle", paths: ["/hrms/recruitment", "/hrms/onboarding", "/hrms/probation", "/hrms/exit"] },
    { name: "Performance & learning", paths: ["/hrms/performance", "/hrms/lms", "/hrms/engagement"] },
    { name: "Approvals & requests", paths: ["/hrms/approval-os", "/hrms/workflow", "/hrms/notifications", "/hrms/forms", "/notifications"] },
    { name: "Documents, assets & support", paths: ["/hrms/documents", "/hrms/letters-certificates", "/hrms/assets", "/hrms/helpdesk", "/hrms/whatsapp-ess", "/hrms/my-assignments"] },
    { name: "Reports & analytics", paths: ["/hrms/reports", "/hrms/advanced-analytics"] },
    { name: "Compliance & verification", paths: ["/hrms/statutory-compliance", "/hrms/background-verification"] },
    { name: "Settings & administration", paths: ["/hrms/settings", "/hrms/logs", "/hrms/custom-fields", "/hrms/enterprise", "/hrms/workflow-designer", "/admin/automation", "/admin/customization"] },
    { name: "AI tools", paths: ["/ai-agents", "/hrms/ai-assistant"] },
  ],
  crm: [
    { name: "Dashboard", paths: ["/crm", "/crm/dashboard"] },
    { name: "Customer growth", paths: ["/crm/product-customers", "/crm/customer-follow-ups", "/crm/greetings"] },
    { name: "Customers & leads", paths: ["/crm/potential-clients", "/crm/records", "/crm/record-metadata", "/crm/leads", "/crm/contacts", "/crm/customers", "/crm/vendors", "/crm/companies", "/crm/customer-360", "/crm/lead-scoring", "/crm/duplicates", "/crm/territories"] },
    { name: "Sales & pipeline", paths: ["/crm/payment-requests", "/crm/deals", "/crm/pipeline", "/crm/templates", "/crm/lead-to-cash", "/crm/products-services", "/crm/products", "/crm/services", "/crm/quotations", "/crm/my-approvals"] },
    { name: "Activities & planning", paths: ["/crm/follow-ups", "/crm/activities", "/crm/tasks", "/crm/calendar", "/crm/gantt", "/crm/calendar-integrations"] },
    { name: "Communication", paths: ["/crm/send-reminders", "/crm/birthdays", "/crm/campaigns", "/crm/webforms", "/crm/forms", "/crm/consents", "/crm/communication-hub", "/crm/email-templates", "/crm/emails", "/crm/whatsapp", "/crm/whatsapp/inbox", "/crm/whatsapp/sent", "/crm/whatsapp/templates", "/crm/whatsapp/profile", "/crm/auto-responses", "/crm/delivery-logs", "/crm/communication-timeline", "/crm/messages"] },
    { name: "Support & files", paths: ["/crm/tickets", "/crm/files"] },
    { name: "Reports & forecasts", paths: ["/crm/reports", "/crm/forecasting"] },
    { name: "Settings & administration", paths: ["/crm/automation", "/crm/import-export", "/crm/settings", "/crm/approval-settings", "/crm/webhooks", "/crm/feature-checklist", "/crm/admin"] },
    { name: "AI tools", paths: ["/ai-agents"] },
  ],
  srm: [
    { name: "Business relationships", paths: ["/srm/customers", "/srm/companies", "/srm/vendors"] },
    { name: "Overview", paths: ["/srm/dashboard", "/srm"] },
    { name: "Sales & contracts", paths: ["/srm/follow-ups", "/srm/sales-orders", "/srm/contracts", "/srm/engagements", "/srm/customer-360", "/srm/gantt"] },
    { name: "Point of sale", paths: ["/srm/pos"] },
    { name: "Products & pricing", paths: ["/srm/inventory/items", "/srm/inventory/products", "/srm/inventory/price-lists", "/srm/inventory/batches"] },
    { name: "Inventory & warehouses", paths: ["/srm/inventory/dashboard", "/srm/inventory/warehouses", "/srm/inventory/stock-summary", "/srm/inventory/opening-stock", "/srm/inventory/delivery-notes", "/srm/inventory/stock-transfers", "/srm/inventory/reconciliation"] },
    { name: "Purchasing & manufacturing", paths: ["/srm/inventory/purchase-orders", "/srm/inventory/manufacturing", "/srm/inventory/reorder-alerts", "/srm/inventory/gantt"] },
    { name: "Billing & collections", paths: ["/srm/payment-requests", "/srm/billing-plans", "/srm/invoice-drafts", "/srm/invoices", "/srm/collections"] },
    { name: "Reports & revenue", paths: ["/srm/reports", "/srm/revenue-recognition", "/srm/profitability", "/srm/inventory/gross-margin", "/srm/inventory/reports"] },
    { name: "Settings & administration", paths: ["/srm/settings", "/srm/forms", "/srm/sales-inventory/source", "/srm/inventory/source"] },
  ],
  fam: [
    { name: "Overview", paths: ["/fam/dashboard", "/fam", "/fam/gantt"] },
    { name: "Accounts & opening balances", paths: ["/fam/chart-of-accounts", "/fam/ledger-groups", "/fam/ledgers", "/fam/opening-balances"] },
    { name: "Transactions & books", paths: ["/fam/voucher-types", "/fam/vouchers", "/fam/journal", "/fam/day-book", "/fam/ledger-entries", "/fam/bill-references", "/fam/bill-allocations"] },
    { name: "Customers & receivables", paths: ["/fam/parties", "/fam/customers", "/fam/ar"] },
    { name: "Purchases & payables", paths: ["/fam/vendors", "/fam/ap", "/fam/purchases", "/fam/purchase-bills", "/fam/expenses", "/fam/purchase-register", "/fam/expense-register", "/fam/vendor-payments", "/fam/payables"] },
    { name: "Banking & reconciliation", paths: ["/fam/banking", "/fam/bank-accounts", "/fam/payment-modes", "/fam/bank-statements", "/fam/bank-reconciliation", "/fam/bank-book", "/fam/cash-book", "/fam/contra", "/fam/bank-charges"] },
    { name: "GST & tax compliance", paths: ["/fam/gst", "/fam/tds"] },
    { name: "Integrations & posting", paths: ["/fam/integrations", "/fam/posting-jobs", "/fam/posting-rules"] },
    { name: "Settings & administration", paths: ["/fam/settings", "/fam/financial-years", "/fam/cost-centers", "/fam/branches", "/fam/audit", "/fam/forms"] },
  ],
  ai_agents: [
    { name: "Agents & conversations", paths: ["/ai-agents"] },
    { name: "Approvals & handoffs", paths: ["/ai-agents/approvals", "/ai-agents/handoff", "/ai-agents/feedback"] },
    { name: "Analytics & usage", paths: ["/ai-agents/analytics", "/ai-agents/usage", "/ai-agents/logs"] },
    { name: "Settings & security", paths: ["/ai-agents/security", "/ai-agents/config"] },
  ],
  ai_copilot: [
    { name: "Assistant & analysis", paths: ["/ai/copilot", "/ai/record-summary", "/ai/deal-coach", "/ai/forecast", "/ai/collection-risk", "/ai/report-explainer"] },
    { name: "Workflows & settings", paths: ["/ai/workflow-builder", "/ai/prompt-templates", "/ai/provider-settings", "/ai/action-log"] },
  ],
};

export function categorizeNavigation<T extends NavigationItem>(items: readonly T[], module: string): T[] {
  const sections = categories[module];
  if (!sections) return [...items];
  const grouped = items.map(item => {
    if (/^\/(crm|srm|hrms|pms|fam)\/import-data$/.test(item.to)) return {...item,group:"Data management"};
    const path = item.to.split("?")[0].replace(/\/+$/, "");
    // Prefer the most specific route (e.g. CRM calendar integrations over calendar).
    const match = sections.flatMap(section => section.paths.map(prefix => ({ section, prefix })))
      .filter(({ prefix }) => path === prefix || path.startsWith(prefix + "/"))
      .sort((a, b) => b.prefix.length - a.prefix.length)[0];
    return { ...item, group: match?.section.name || item.group };
  });
  const order = sections.map(section => section.name);
  const rank = (group?: string) => { const index = order.indexOf(group || ""); return index < 0 ? order.length : index; };
  return grouped.sort((a, b) => rank(a.group) - rank(b.group));
}
