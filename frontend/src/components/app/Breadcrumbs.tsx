import { useEffect, useState } from "react";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute, getRoleNav } from "@/lib/roles";
import { modules } from "@/lib/moduleCatalog";
import { Link, useLocation } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import { getProductForContext } from "@/lib/products";

const labels: Record<string, string> = {
  hrms: "HRMS",
  crm: "CRM",
  pms: "PMS",
  srm: "SRM",
  fam: "FAM",
  inventory: "Inventory",
  dashboard: "Dashboard",
  employees: "Employees",
  attendance: "Attendance",
  timesheets: "Timesheets",
  workflow: "Workflow",
  notifications: "Notifications",
  leave: "Leave",
  payroll: "Payroll",
  recruitment: "Recruitment",
  performance: "Talent",
  helpdesk: "Helpdesk",
  reports: "Reports",
  company: "Company",
  settings: "Settings",
  assets: "Assets",
  onboarding: "Onboarding",
  documents: "Documents",
  exit: "Exit",
  profile: "Profile",
  "ai-assistant": "AI Assistant",
  "advanced-analytics": "Advanced Analytics",
  "lead-to-cash": "Lead-to-Cash",
  forecasting: "Forecasting",
  "customer-360": "Customer 360",
  "import-export": "Import & Export",
  "dependency-management": "Dependency Management",
  "resource-planning": "Resource Planning",
  "agile-execution": "Agile Execution",
  "project-financials": "Project Financials",
  "risk-register": "Risk Register",
  "sales-orders": "Sales Orders",
  contracts: "Contracts",
  engagements: "Engagements",
  "billing-plans": "Billing Plans",
  "financial-years": "Financial Years",
  "chart-of-accounts": "Chart of Accounts",
  "ledger-groups": "Ledger Groups",
  ledgers: "Ledgers",
  "opening-balances": "Opening Balances",
  "voucher-types": "Voucher Types",
  vouchers: "Vouchers",
  journal: "Journal",
  "day-book": "Day Book",
  "ledger-entries": "Ledger Entries",
  parties: "Parties",
  customers: "Customers",
  vendors: "Vendors",
  ar: "Accounts Receivable",
  ap: "Accounts Payable",
  aging: "Aging",
  outstanding: "Outstanding",
  "bill-references": "Bill References",
  "bill-allocations": "Bill Allocations",
  integrations: "Integrations",
  "posting-jobs": "Posting Jobs",
  "posting-rules": "Posting Rules",
  banking: "Banking",
  "bank-accounts": "Bank Accounts",
  "payment-modes": "Payment Modes",
  "bank-statements": "Bank Statements",
  "bank-reconciliation": "Bank Reconciliation",
  "bank-book": "Bank Book",
  "cash-book": "Cash Book",
  contra: "Contra",
  "bank-charges": "Bank Charges",
  "cost-centers": "Cost Centers",
  branches: "Branches",
  audit: "Audit",
  "invoice-drafts": "Invoice Drafts",
  invoices: "Invoices",
  collections: "Collections",
  "revenue-recognition": "Revenue Recognition",
  profitability: "Profitability",
};

export default function Breadcrumbs() {
  const location = useLocation();
  const user = useAuthStore((s) => s.user);
  const [title, setTitle] = useState(document.title);
  useEffect(() => {
    const element = document.querySelector("title");
    if (!element) return;
    const observer = new MutationObserver(() => setTitle(document.title));
    observer.observe(element, {
      childList: true,
      characterData: true,
      subtree: true,
    });
    setTitle(document.title);
    return () => observer.disconnect();
  }, []);
  const parts = location.pathname.split("/").filter(Boolean);
  const module = modules.find((m) => m.homePath === `/${parts[0]}`);
  const nav = getRoleNav(user?.role, user?.is_superuser, location.pathname);
  return (
    <nav
      aria-label="Breadcrumb"
      className="suite-breadcrumbs mb-4 flex items-center gap-1 text-xs text-muted-foreground"
    >
      <Link to="/dashboard">All applications</Link>
      {parts.map((part, index) => {
        const path = `/${parts.slice(0, index + 1).join("/")}`;
        const active = index === parts.length - 1;
        const pageTitle = title.split(" - ")[0];
        const isRecord = /^\d+$/.test(part);
        const label =
          index === 0 && module
            ? module.name
            : nav.find((item) => item.to === path)?.label ||
              (isRecord
                ? active &&
                  pageTitle &&
                  pageTitle !== getProductForContext(location.pathname).name
                  ? pageTitle
                  : `Record #${part}`
                : labels[part] ||
                  part
                    .replace(/-/g, " ")
                    .replace(/\b\w/g, (letter) => letter.toUpperCase()));
        return (
          <span key={path} className="flex min-w-0 items-center gap-1">
            <ChevronRight className="h-3 w-3 shrink-0" aria-hidden="true" />
            {active ? (
              <span aria-current="page" className="font-medium text-foreground">
                {label}
              </span>
            ) : canAccessRoute(path, user?.role, user?.is_superuser) ? (
              <Link to={path}>{label}</Link>
            ) : (
              <span>{label}</span>
            )}
          </span>
        );
      })}
    </nav>
  );
}
