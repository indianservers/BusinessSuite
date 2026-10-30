type NavigationItem = { to: string; group?: string };
type Category = { name: string; paths: readonly string[] };

// Presentation only: permissions and the set of available links are resolved by roles.ts.
const categories: Record<string, readonly Category[]> = {
  hrms: [
    { name: "Overview", paths: ["/hrms", "/hrms/dashboard", "/hrms/admin-home", "/hrms/hr-home", "/hrms/executive-home", "/hrms/ess", "/hrms/role-home"] },
    { name: "People & organization", paths: ["/hrms/employees", "/hrms/employee-directory", "/hrms/profile", "/hrms/profile-management", "/hrms/interns", "/hrms/manager-dashboard", "/hrms/org-chart", "/settings/company-profile", "/hrms/company"] },
    { name: "Attendance & leave", paths: ["/hrms/attendance", "/hrms/my-attendance", "/hrms/my-roster", "/hrms/timesheets", "/hrms/leave"] },
    { name: "Payroll & benefits", paths: ["/hrms/payroll", "/hrms/my-payslips", "/hrms/investment-declaration", "/hrms/fnf-settlements", "/hrms/benefits", "/hrms/expenses"] },
    { name: "Recruitment & employee lifecycle", paths: ["/hrms/recruitment", "/hrms/onboarding", "/hrms/probation", "/hrms/exit"] },
    { name: "Performance & learning", paths: ["/hrms/performance", "/hrms/lms", "/hrms/engagement"] },
    { name: "Approvals & requests", paths: ["/hrms/approval-os", "/hrms/workflow", "/hrms/notifications", "/hrms/forms", "/notifications"] },
    { name: "Documents, assets & support", paths: ["/hrms/documents", "/hrms/letters-certificates", "/hrms/assets", "/hrms/helpdesk", "/hrms/whatsapp-ess", "/hrms/my-assignments"] },
    { name: "Reports & analytics", paths: ["/hrms/reports", "/hrms/advanced-analytics", "/analytics"] },
    { name: "Compliance & verification", paths: ["/hrms/statutory-compliance", "/hrms/background-verification"] },
    { name: "Settings & administration", paths: ["/hrms/settings", "/hrms/logs", "/hrms/custom-fields", "/hrms/enterprise", "/hrms/workflow-designer", "/admin/automation", "/admin/customization"] },
    { name: "AI tools", paths: ["/ai-agents", "/hrms/ai-assistant"] },
  ],
  crm: [
    { name: "Overview", paths: ["/crm"] },
    { name: "Customers & leads", paths: ["/crm/leads", "/crm/contacts", "/crm/companies", "/crm/customer-360", "/crm/lead-scoring", "/crm/duplicates", "/crm/territories"] },
    { name: "Sales & pipeline", paths: ["/crm/deals", "/crm/pipeline", "/crm/lead-to-cash", "/crm/products", "/crm/quotations", "/crm/my-approvals"] },
    { name: "Activities & planning", paths: ["/crm/activities", "/crm/tasks", "/crm/calendar", "/crm/gantt", "/crm/calendar-integrations"] },
    { name: "Marketing & campaigns", paths: ["/crm/campaigns", "/crm/webforms", "/crm/forms", "/crm/consents", "/crm/templates"] },
    { name: "Communication", paths: ["/crm/communication-hub", "/crm/email-templates", "/crm/emails", "/crm/whatsapp", "/crm/auto-responses", "/crm/delivery-logs", "/crm/communication-timeline", "/crm/messages"] },
    { name: "Support & files", paths: ["/crm/tickets", "/crm/files"] },
    { name: "Reports & forecasts", paths: ["/crm/reports", "/crm/forecasting", "/analytics"] },
    { name: "Settings & administration", paths: ["/crm/automation", "/crm/import-export", "/crm/settings", "/crm/approval-settings", "/crm/webhooks", "/crm/feature-checklist", "/crm/admin"] },
    { name: "AI tools", paths: ["/ai-agents"] },
  ],
  srm: [
    { name: "Overview", paths: ["/srm/dashboard", "/srm"] },
    { name: "Sales & contracts", paths: ["/srm/sales-orders", "/srm/contracts", "/srm/engagements", "/srm/customer-360", "/srm/gantt"] },
    { name: "Point of sale", paths: ["/srm/pos"] },
    { name: "Products & pricing", paths: ["/srm/inventory/items", "/srm/inventory/products", "/srm/inventory/price-lists", "/srm/inventory/batches"] },
    { name: "Inventory & warehouses", paths: ["/srm/inventory/dashboard", "/srm/inventory/warehouses", "/srm/inventory/stock-summary", "/srm/inventory/opening-stock", "/srm/inventory/delivery-notes", "/srm/inventory/stock-transfers", "/srm/inventory/reconciliation"] },
    { name: "Purchasing & manufacturing", paths: ["/srm/inventory/purchase-orders", "/srm/inventory/manufacturing", "/srm/inventory/reorder-alerts", "/srm/inventory/gantt"] },
    { name: "Billing & collections", paths: ["/srm/billing-plans", "/srm/invoice-drafts", "/srm/invoices", "/srm/collections"] },
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
