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
  const product = getProductForContext(location.pathname);
  const parts = location.pathname.split("/").filter(Boolean);
  if (!parts.length) return null;
  return (
    <nav className="mb-4 flex items-center gap-1 text-xs text-muted-foreground">
      <Link to={product.homePath} className="hover:text-foreground">{product.shortName}</Link>
      {parts.map((part, index) => {
        if (index === 0 && pathProductLabel(part)) return null;
        const path = `/${parts.slice(0, index + 1).join("/")}`;
        const active = index === parts.length - 1;
        return (
          <span key={path} className="flex items-center gap-1">
            <ChevronRight className="h-3 w-3" />
            {active ? (
              <span className="font-medium text-foreground">{labels[part] || part}</span>
            ) : (
              <Link to={path} className="hover:text-foreground">{labels[part] || part}</Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}

function pathProductLabel(part: string) {
  return part === "hrms" || part === "crm" || part === "pms" || part === "srm" || part === "fam" || part === "inventory";
}

