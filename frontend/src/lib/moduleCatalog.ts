import {
  BarChart3,
  BookOpen,
  Boxes,
  CalendarDays,
  Check,
  Crosshair,
  Database,
  FileText,
  Folder,
  Landmark,
  Layers3,
  List,
  Package,
  PieChart,
  ShoppingCart,
  Store,
  UserRound,
  Users,
  type LucideIcon,
} from "lucide-react";
import type { ProductKey } from "./products";
export type ModuleIndexItem = {
  key: string;
  name: string;
  label: string;
  description: string;
  icon: LucideIcon;
  homePath: string;
  loginPath: string;
  productKey?: ProductKey;
};
export const modules: ModuleIndexItem[] = [
  {
    key: "power_apps",
    name: "Power Apps",
    label: "Build, automate & connect",
    description:
      "A dedicated platform for automations, approvals, forms, apps, and governed business tools.",
    icon: Layers3,
    homePath: "/power-apps",
    loginPath: "/login?next=%2Fpower-apps",
  },
  {
    key: "hrms",
    name: "AI HRMS",
    label: "Human Resource Management",
    description:
      "Employees, payroll, attendance, leave, recruitment, and self-service.",
    icon: Users,
    homePath: "/hrms",
    loginPath: "/login?next=%2Fhrms",
    productKey: "hrms",
  },
  {
    key: "crm",
    name: "VyaparaCRM",
    label: "Customer Relationship Management",
    description:
      "Leads, customers, deals, activities, campaigns, quotes, and sales follow-ups.",
    icon: Users,
    homePath: "/crm",
    loginPath: "/login?next=%2Fcrm",
    productKey: "crm",
  },
  {
    key: "pms",
    name: "KaryaFlow PMS",
    label: "Project Management Software",
    description:
      "Projects, tasks, sprints, milestones, reports, workload, risks, and delivery plans.",
    icon: Boxes,
    homePath: "/pms",
    loginPath: "/login?next=%2Fpms",
    productKey: "project_management",
  },
  {
    key: "srm",
    name: "Sales & Inventory Management",
    label: "Sales, Inventory & POS",
    description:
      "Manage sales orders, POS, products, stock, delivery, billing, invoices, collections, and profitability.",
    icon: Package,
    homePath: "/srm",
    loginPath: "/login?next=%2Fsrm",
    productKey: "srm",
  },
  {
    key: "fam",
    name: "Finance & Accounting Management",
    label: "Finance & Accounting",
    description:
      "Manage financial settings, chart of accounts, ledgers, opening balances, branches, cost centers, and audit-ready books.",
    icon: Landmark,
    homePath: "/fam",
    loginPath: "/login?next=%2Ffam",
    productKey: "fam",
  },
];

export const features: Record<string, [LucideIcon, string][]> = {
  power_apps: [
    [Boxes, "Apps"],
    [Check, "Approvals"],
    [List, "Automations"],
  ],
  hrms: [
    [UserRound, "People"],
    [FileText, "Payroll"],
    [CalendarDays, "Attendance"],
  ],
  crm: [
    [Crosshair, "Leads"],
    [BarChart3, "Deals"],
    [Users, "Customers"],
  ],
  pms: [
    [Folder, "Projects"],
    [List, "Tasks"],
    [Users, "Teams"],
  ],
  srm: [
    [ShoppingCart, "Orders"],
    [Database, "Stock"],
    [Store, "POS"],
  ],
  fam: [
    [FileText, "Invoices"],
    [BookOpen, "Ledgers"],
    [PieChart, "Reports"],
  ],
};
