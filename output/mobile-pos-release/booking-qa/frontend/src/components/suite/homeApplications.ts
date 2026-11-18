import { CalendarDays, Users, Zap, LayoutGrid, UserRound, Filter, Handshake, ListChecks, Flag, ShoppingCart, Package, BookOpen, Landmark, type LucideIcon } from "lucide-react";
import { modules, type ModuleIndexItem } from "@/lib/moduleCatalog";
export const homeCategories = ["All apps", "Operations", "People", "Customers", "Finance"];
type Metadata = { key: string; title: string; description: string; category: string; chips: [LucideIcon, string][] };
const metadata: Metadata[] = [
  { key: "power_apps", title: "Power Apps", description: "Build, automate & connect business tools.", category: "Operations", chips: [[Zap, "Low-code apps"], [LayoutGrid, "Automations"]] },
  { key: "hrms", title: "AI HRMS", description: "Human Resource Management for your workforce.", category: "People", chips: [[UserRound, "Employee lifecycle"], [CalendarDays, "Attendance & Leave"]] },
  { key: "crm", title: "VyaparaCRM", description: "Customer Relationship Management for business growth.", category: "Customers", chips: [[Filter, "Lead management"], [Handshake, "Deals & Pipeline"]] },
  { key: "pms", title: "KaryaFlow PMS", description: "Project Management Software to plan, track and deliver.", category: "Operations", chips: [[ListChecks, "Task & Sprint"], [Flag, "Milestones"]] },
  { key: "srm", title: "Sales & POS", description: "Sales, services & inventory to run your business.", category: "Operations", chips: [[ShoppingCart, "Sales & POS"], [Package, "Inventory & Stock"]] },
  { key: "fam", title: "Finance & Accounting", description: "Manage finance, accounts and compliance with confidence.", category: "Finance", chips: [[BookOpen, "Accounts & Ledgers"], [Landmark, "Branches & Cost Centers"]] },
  { key: "appointments", title: "Schedule & Appointments", description: "Book appointments, assign services and manage availability.", category: "People", chips: [[CalendarDays, "Calendar & Bookings"], [Users, "Team availability"]] },
];
export type HomeApplication = Metadata & { module: ModuleIndexItem };
export const homeApplications: HomeApplication[] = metadata.map(item => ({ ...item, module: modules.find(module => module.key === item.key)! }));
