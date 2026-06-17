export type WowFeature = {
  title: string;
  subtitle: string;
  path: string;
  module: "suite" | "crm" | "hrms" | "project_management";
  impact: "AI" | "Automation" | "Insight" | "Mobile" | "Workflow";
};

export const wowFeatures: WowFeature[] = [
  { title: "AI Command Center", subtitle: "Ask for records, reports, and actions in natural language.", path: "/ai/copilot", module: "suite", impact: "AI" },
  { title: "Customer 360 Timeline", subtitle: "Open the combined customer, deal, ticket, invoice, and message story.", path: "/crm/customer-360", module: "crm", impact: "Insight" },
  { title: "Employee 360 Timeline", subtitle: "Jump to employee profile, attendance, payroll, documents, and approvals.", path: "/hrms/employees", module: "hrms", impact: "Insight" },
  { title: "Smart Work Inbox", subtitle: "Prioritize approvals, overdue work, requests, and exceptions.", path: "/workflow", module: "suite", impact: "Workflow" },
  { title: "Predictive Lead Scoring", subtitle: "Use lead score views for conversion-focused follow-up.", path: "/crm/lead-scoring", module: "crm", impact: "AI" },
  { title: "Attendance Anomaly Detection", subtitle: "Review missed punches, geo mismatches, and shift issues.", path: "/hrms/attendance", module: "hrms", impact: "Insight" },
  { title: "Payroll Pre-Run Auditor", subtitle: "Catch LOP, arrears, loans, tax, and statutory issues before payroll.", path: "/hrms/payroll", module: "hrms", impact: "Workflow" },
  { title: "WhatsApp CRM Automation", subtitle: "Open WhatsApp journeys for leads, tickets, reminders, and campaigns.", path: "/crm/whatsapp", module: "crm", impact: "Automation" },
  { title: "AI Follow-Up Assistant", subtitle: "Get next-best-action prompts for leads, tickets, and HR requests.", path: "/ai/deal-coach", module: "suite", impact: "AI" },
  { title: "Voice Notes to Actions", subtitle: "Capture spoken work and route it to the right module action.", path: "/ai/workflow-builder", module: "suite", impact: "AI" },
  { title: "Role-Based Cockpit Dashboards", subtitle: "Switch into dashboards tuned for executive, HR, sales, support, and finance roles.", path: "/business-os/dashboard", module: "suite", impact: "Insight" },
  { title: "Cross-Module Risk Alerts", subtitle: "Spot revenue, support, HR, and delivery risk across modules.", path: "/business-os/ai", module: "suite", impact: "Insight" },
  { title: "Smart Document Vault", subtitle: "Use document hubs for employee, customer, and compliance files.", path: "/hrms/documents", module: "hrms", impact: "Automation" },
  { title: "Approval Flow Designer", subtitle: "Design approval routes for leave, payroll, quotes, expenses, and deals.", path: "/workflow-designer", module: "suite", impact: "Workflow" },
  { title: "Live SLA Heatmap", subtitle: "Open urgent CRM and employee support queues before SLA breach.", path: "/crm/tickets", module: "crm", impact: "Insight" },
  { title: "AI Report Builder", subtitle: "Build analytics, forecasts, funnels, and exports from guided prompts.", path: "/analytics/report-builder", module: "suite", impact: "AI" },
  { title: "Guided Onboarding Wizard", subtitle: "Configure branches, shifts, policies, payroll, pipelines, and users.", path: "/hrms/onboarding", module: "hrms", impact: "Workflow" },
  { title: "Gamified Sales & Support Scorecards", subtitle: "Review team performance, streaks, SLA wins, and conversion progress.", path: "/crm/reports", module: "crm", impact: "Insight" },
  { title: "Mobile-First Manager Mode", subtitle: "Approve, assign, escalate, and follow up from the mobile workspace.", path: "/mobile", module: "suite", impact: "Mobile" },
  { title: "Automation Marketplace", subtitle: "Launch prebuilt recipes for lead, ticket, payroll, approval, and reminder flows.", path: "/admin/automation/blueprints", module: "suite", impact: "Automation" },
];

export function getWowFeaturesForContext(productKey?: string) {
  if (!productKey || productKey === "business_os") return wowFeatures;
  return wowFeatures.filter((feature) => feature.module === "suite" || feature.module === productKey);
}
