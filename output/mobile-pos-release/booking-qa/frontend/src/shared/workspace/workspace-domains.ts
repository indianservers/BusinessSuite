import type { DirectoryAction } from "./WorkspaceDirectory";
import { Activity, BookOpenCheck, Boxes, CalendarCheck2, CalendarDays, ContactRound, FileCheck2, FolderKanban, GitBranch, Handshake, Landmark, ListTodo, Scale, ShieldCheck, ShoppingCart, Users, Wallet } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type WorkspaceDomainModule = "crm" | "hrms" | "srm" | "fam";
type Domain = { name: string; path: string; description: string; category: string; icon: LucideIcon };
type Definition = { title: string; description: string; icon: LucideIcon; notice: string; domains: Domain[]; actions: DirectoryAction[] };
export const operationalWorkspaceDefinitions: Record<WorkspaceDomainModule, Definition> = {
  crm: {
    title: "Sales & Customer Workspaces", description: "Build relationships, move opportunities forward and stay close to every customer.", icon: ContactRound,
    notice: "Choose a focus for your sales day, from the first enquiry to your next customer conversation.",
    domains: [
      { name: "Leads", path: "/crm/leads", description: "Capture enquiries, qualify prospects and convert leads using your existing sales process.", category: "Relationships", icon: ContactRound },
      { name: "Customers & contacts", path: "/crm/contacts", description: "A connected directory of customer relationships, owners and contact history.", category: "Relationships", icon: Users },
      { name: "Deals & pipelines", path: "/crm/deals", description: "Manage opportunities, deal stages, pipeline health and closing decisions.", category: "Revenue", icon: Handshake },
      { name: "Follow-ups & activities", path: "/crm/follow-ups", description: "Plan calls, meetings and next actions. Keep overdue commitments in view.", category: "Execution", icon: CalendarDays },
      { name: "Quotes & proposals", path: "/crm/quotes", description: "Prepare quotes with your product catalog and existing approval workflows.", category: "Revenue", icon: FileCheck2 },
      { name: "Sales insights", path: "/crm/reports", description: "Explore conversion, forecasts and sales outcomes in your authorized reports.", category: "Insights", icon: Activity },
    ], actions: [{ label: "Create lead", href: "/crm/leads?new=lead", icon: ContactRound }, { label: "Add contact", href: "/crm/contacts?new=contact", icon: Users }, { label: "Create deal", href: "/crm/deals?new=deal", icon: Handshake }, { label: "Add activity", href: "/crm/activities?new=activity", icon: CalendarDays }],
  },
  hrms: {
    title: "People Workspaces", description: "Bring people, attendance and approvals together for a well-organized team.", icon: Users,
    notice: "Find your people, coordinate daily operations and keep team requests moving.",
    domains: [
      { name: "People & organization", path: "/hrms/employees", description: "Find employees, department assignments and reporting relationships.", category: "People", icon: Users },
      { name: "Attendance & scheduling", path: "/hrms/attendance", description: "Review attendance, exceptions and shift schedules within your assigned scope.", category: "Operations", icon: CalendarCheck2 },
      { name: "Leave", path: "/hrms/leave", description: "Manage leave requests, balances and decisions with the existing approval process.", category: "Operations", icon: CalendarDays },
      { name: "Approvals", path: "/hrms/approval-os", description: "Review requests and decisions that need your attention.", category: "Operations", icon: ShieldCheck },
      { name: "Employee documents", path: "/hrms/documents", description: "Access authorized employee documents and document workflows.", category: "People", icon: FileCheck2 },
      { name: "Recruitment", path: "/hrms/recruitment", description: "Coordinate hiring, open positions and candidate journeys.", category: "People", icon: FolderKanban },
    ], actions: [{ label: "Add employee", href: "/hrms/employees/new", icon: Users }, { label: "Review approvals", href: "/hrms/approval-os", icon: ShieldCheck }, { label: "View attendance", href: "/hrms/attendance", icon: CalendarCheck2 }, { label: "Organization chart", href: "/hrms/org-chart", icon: GitBranch }],
  },
  srm: {
    title: "Sales & Operations Workspaces", description: "Keep checkout, orders, stock and customer payments moving together.", icon: ShoppingCart,
    notice: "Move from customer orders to checkout, fulfillment and collections in one connected suite.",
    domains: [
      { name: "Appointments", path: "/srm/appointments", description: "Schedule providers and resources, complete services and create shared invoices.", category: "Industry operations", icon: CalendarCheck2 },
      { name: "Construction operations", path: "/srm/construction", description: "Approve BOQ, certify site measurements and bill through the existing ledger.", category: "Industry operations", icon: FolderKanban },
      { name: "Point of sale", path: "/srm/pos", description: "Open checkout and manage cashier sessions using your existing POS controls.", category: "Sales", icon: ShoppingCart },
      { name: "Sales orders", path: "/srm/sales-orders", description: "Follow customer orders from creation through fulfillment and billing.", category: "Sales", icon: ListTodo },
      { name: "Products & services", path: "/srm/products", description: "Maintain your shared catalog, categories and product information.", category: "Inventory", icon: Boxes },
      { name: "Stock overview", path: "/srm/inventory/stock-summary", description: "Review stock availability and movements within your authorized inventory scope.", category: "Inventory", icon: Boxes },
      { name: "Invoices", path: "/srm/invoices", description: "Manage customer invoices with the existing billing and posting workflow.", category: "Payments", icon: FileCheck2 },
      { name: "Collections", path: "/srm/collections", description: "Track customer payments, allocations and outstanding collection work.", category: "Payments", icon: Wallet },
    ], actions: [{ label: "New sale", href: "/srm/pos", icon: ShoppingCart }, { label: "Create order", href: "/srm/sales-orders?new=salesOrder", icon: ListTodo }, { label: "Add product", href: "/srm/products?new=catalog", icon: Boxes }, { label: "Create invoice", href: "/srm/invoices?new=invoice", icon: FileCheck2 }],
  },
  fam: {
    title: "Finance & Accounting Workspaces", description: "A precise, connected home for accounts, transactions and financial controls.", icon: Landmark,
    notice: "Keep daily accounting, cash flow and reconciliation close at hand.",
    domains: [
      { name: "Accounts & ledgers", path: "/fam/chart-of-accounts", description: "Explore your chart of accounts and ledger structure.", category: "Accounting", icon: BookOpenCheck },
      { name: "Journals & transactions", path: "/fam/journal", description: "Review journal entries and voucher activity within existing posting controls.", category: "Accounting", icon: FileCheck2 },
      { name: "Receivables", path: "/fam/ar", description: "Review customer dues, aging and outstanding receivables.", category: "Cash flow", icon: Wallet },
      { name: "Payables", path: "/fam/ap", description: "Manage supplier dues and payment priorities in the existing payables workflow.", category: "Cash flow", icon: Wallet },
      { name: "Bank reconciliation", path: "/fam/bank-reconciliation", description: "Match statement activity and review reconciliation status.", category: "Controls", icon: Scale },
      { name: "Financial statements", path: "/fam/financial-statements", description: "Open authorized financial statements and accounting reports.", category: "Controls", icon: Activity },
    ], actions: [{ label: "Create voucher", href: "/fam/vouchers/new", icon: FileCheck2 }, { label: "View receivables", href: "/fam/ar", icon: Wallet }, { label: "View payables", href: "/fam/ap", icon: Wallet }, { label: "Reconcile account", href: "/fam/bank-reconciliation", icon: Scale }],
  },
};

export const workspaceDomainViewIds = { crm: ["leads", "contacts", "deals", "activities", "quotes", "reports"], hrms: ["employees", "attendance", "leave", "approvals", "documents", "recruitment"], srm: ["appointments", "construction", "pos", "orders", "products", "stock", "invoices", "collections"], fam: ["accounts", "journals", "receivables", "payables", "reconciliation", "statements"] };
