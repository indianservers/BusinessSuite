import { useEffect, useLayoutEffect, useState } from "react";

import { Link, useLocation } from "react-router-dom";

import { ChevronUp, ArrowUpRight, BarChart3, BriefcaseBusiness, CalendarCheck, CheckCheck, ClipboardList, FileText, FolderKanban, Handshake, ListTodo, Receipt, Users, UserRoundPlus, Wallet, type LucideIcon } from "lucide-react";

import { MobileSheet } from "@/components/mobile/MobilePrimitives";

import MobileExperience from "@/components/mobile/MobileExperience";

import MobileTools from "@/components/mobile/MobileTools";

import { useMobile } from "@/components/mobile/useMobile";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/services/api";

import { canAccessRoute } from "@/lib/roles";

import { useAuthStore } from "@/store/authStore";

import "./mobile-module-dock.css";



type Shortcut = [string, string];

type Item = { label: string; icon: LucideIcon; to: string; actions: Shortcut[] };

const item = (label: string, icon: LucideIcon, to: string, actions: Shortcut[]): Item => ({ label, icon, to, actions });

export const mobileModuleMenus: Record<string, Item[]> = {

  crm: [

    item("Leads", UserRoundPlus, "/crm/leads", [["Add lead", "/crm/leads?new=leads"], ["Find leads", "/crm/leads"], ["View lead pipeline", "/crm/leads?view=board"], ["Lead performance", "/crm/reports"]]),

    item("Customers", Users, "/crm/companies", [["Add contact", "/crm/contacts?new=contacts"], ["Add company", "/crm/companies?new=companies"], ["Find customers", "/crm/companies"], ["Customer 360", "/crm/customer-360"]]),

    item("Deals", Handshake, "/crm/deals", [["Create deal", "/crm/deals?new=deals"], ["View pipeline", "/crm/pipeline"], ["View quotes", "/crm/quotes"], ["Sales forecast", "/crm/forecasting"]]),

    item("Follow-ups", CalendarCheck, "/crm/follow-ups", [["Follow-up worklist", "/crm/follow-ups"], ["Follow-up calendar", "/crm/follow-ups/calendar"], ["Customer follow-ups", "/crm/customer-follow-ups"], ["Activity history", "/crm/activities"]]),

  ],

  pms: [

    item("My Work", CheckCheck, "/pms/my-work", [["Today's work", "/pms/my-work"], ["My assignments", "/pms/my-assignments"], ["Work reviews", "/pms/reviews"], ["My notices", "/pms/my-notices"]]),

    item("Projects", FolderKanban, "/pms/projects", [["Create project", "/pms/projects/new"], ["Browse projects", "/pms/projects"], ["Workspace boards", "/pms/workspaces"], ["Project timeline", "/pms/gantt"]]),

    item("Tasks", ListTodo, "/pms/tasks", [["Create task", "/pms/tasks/new"], ["All tasks", "/pms/tasks"], ["Tasks & follow-ups", "/pms/tasks-follow-ups"], ["Backlog & sprints", "/pms/backlog"], ["Task calendar", "/pms/calendar"]]),

    item("Reports", BarChart3, "/pms/reports", [["Project progress", "/pms/analytics/projects"], ["Team workload", "/pms/workload"], ["Team performance", "/pms/analytics/team"], ["Reports & exports", "/pms/reports"]]),

  ],

  srm: [

    item("Customers", Users, "/srm/customer-360", [["Customer overview", "/srm/customer-360"], ["Customer follow-ups", "/srm/follow-ups"], ["Sales history", "/srm/sales-orders"], ["Outstanding balances", "/srm/collections"]]),

    item("Quotes", FileText, "/srm/quotes", [["View quotes", "/srm/quotes"], ["Products & services", "/srm/products-services"], ["Sales contracts", "/srm/contracts"], ["Sales orders", "/srm/sales-orders"]]),

    item("Orders", ClipboardList, "/srm/sales-orders", [["Manage orders", "/srm/sales-orders"], ["Delivery notes", "/srm/inventory/delivery-notes"], ["Invoice drafts", "/srm/invoice-drafts"], ["View invoices", "/srm/invoices"]]),

    item("Payments", Wallet, "/srm/collections", [["Manage collections", "/srm/collections"], ["View invoices", "/srm/invoices"], ["Billing plans", "/srm/billing-plans"], ["Revenue reports", "/srm/reports"]]),

  ],

  hrms: [

    item("People", Users, "/hrms/employees", [["Employee directory", "/hrms/employee-directory"], ["Add employee", "/hrms/employees/new"], ["Onboarding", "/hrms/onboarding"], ["My profile", "/hrms/profile"]]),

    item("Attendance", CalendarCheck, "/hrms/attendance", [["My attendance", "/hrms/my-attendance"], ["Team attendance", "/hrms/attendance"], ["My shift roster", "/hrms/my-roster"], ["Timesheets", "/hrms/timesheets"]]),

    item("Leave", BriefcaseBusiness, "/hrms/leave", [["Apply for leave", "/hrms/leave?new=leave"], ["Leave balances & requests", "/hrms/leave"], ["Request inbox", "/hrms/workflow"], ["Approvals", "/hrms/approval-os"]]),

    item("Payroll", Receipt, "/hrms/payroll", [["My payslips", "/hrms/my-payslips"], ["Manage payroll", "/hrms/payroll"], ["Investment declaration", "/hrms/investment-declaration"], ["Final settlements", "/hrms/fnf-settlements"]]),

  ],

};



export default function MobileModuleDock() {

  const location = useLocation();

  const user = useAuthStore(state => state.user);

  const [selected, setSelected] = useState<Item | null>(null);

  const mobile = useMobile();

  useLayoutEffect(() => setSelected(null), [location.key]);
  useLayoutEffect(() => { if (!mobile) setSelected(null); }, [mobile]);

  const module = location.pathname.split("/")[1];

  const menus = mobileModuleMenus[module];

  const allowed = (to: string) => canAccessRoute(to.split("?")[0], user?.role, user?.is_superuser);

  const actions = selected?.actions.filter(([, to]) => allowed(to)) || [];

  const badges = useQuery<Record<string, number>>({

    queryKey: ["mobile-action-badges", user?.id, user?.access?.companyId, module],

    queryFn: async (): Promise<Record<string, number>> => {

      if ((module === "crm" || module === "srm") && allowed(`/${module}/follow-ups`)) { const r = await api.get("/follow-ups/statistics", { progress: false }); return { "Follow-ups": Number(r.data.Overdue || 0) }; }

      if (module === "pms" && allowed("/pms/my-work")) { const r = await api.get("/project-management/tasks", { params: { workView: "mine", pageSize: 1 }, progress: false }); return { "My Work": Number(r.data.summary?.overdue || 0), Tasks: Number(r.data.summary?.in_review || 0) }; }

      if (module === "hrms" && /admin|manager|hr|ceo/i.test(user?.role || "")) { const r = await api.get("/leave/requests", { params: { status: "Pending" }, progress: false }); const rows = Array.isArray(r.data) ? r.data : r.data.items; return { Leave: Array.isArray(rows) ? rows.length : 0 }; }

      return {};

    }, enabled: mobile && !!menus && !!user, staleTime: 30000, refetchInterval: 60000, retry: false,

  });

  const memoryKey = `mobile-tab:${user?.id}:${user?.access?.companyId}`;

  useEffect(() => { if (!mobile || !menus) return; const entry = menus.find(entry => entry.to === location.pathname); if (entry && !new URLSearchParams(location.search).has("new")) { try { sessionStorage.setItem(`${memoryKey}:${entry.to}`, location.pathname + location.search); } catch { /* Optional browser persistence. */ } } }, [mobile, menus, location.pathname, location.search, memoryKey]);

  if (!mobile || !menus) return null;

  const matches = (to: string) => location.pathname === to.split("?")[0] || location.pathname.startsWith(to.split("?")[0] + "/");

  const aliases: Record<string, Record<string, string>> = { pms: { workspaces: "Projects", gantt: "Projects", portfolio: "Projects", reviews: "My Work", "my-assignments": "My Work", analytics: "Reports", workload: "Reports" }, crm: { contacts: "Customers", "customer-360": "Customers", accounts: "Customers", pipeline: "Deals", quotes: "Deals", quotations: "Deals", activities: "Follow-ups" }, srm: { invoices: "Payments", collections: "Payments", "invoice-drafts": "Orders", contracts: "Quotes", "products-services": "Quotes" }, hrms: { "my-attendance": "Attendance", "my-roster": "Attendance", timesheets: "Attendance", "employee-directory": "People", profile: "People", onboarding: "People", "my-payslips": "Payroll", "investment-declaration": "Payroll", "approval-os": "Leave", workflow: "Leave" } };

  const alias = aliases[module]?.[location.pathname.split("/")[2]] || (module === "pms" && /^\/pms\/?$/.test(location.pathname) ? "Projects" : undefined);

  const current = menus.find(entry => entry.label === alias) || menus.find(entry => matches(entry.to)) || menus.find(entry => entry.actions.some(([, to]) => matches(to))) || menus[0];

  const moduleRole = user?.access?.grants[module === "pms" ? "project_management" : module]?.role || user?.role || "";
  const personal = !user?.is_superuser && /employee|intern|self|member/i.test(moduleRole);
  const manager = !personal && /manager|lead|hr/i.test(moduleRole);

  const destination = (entry: Item) => {

    const preferred = personal && module === "hrms" ? ({ People: "/hrms/profile", Attendance: "/hrms/my-attendance", Payroll: "/hrms/my-payslips" } as Record<string, string>)[entry.label] : undefined;

    let remembered: string | null = null; try { remembered = sessionStorage.getItem(`${memoryKey}:${entry.to}`); } catch { /* No saved state. */ }

    return preferred && allowed(preferred) ? preferred : allowed(entry.to) ? (remembered?.split("?")[0] === entry.to ? remembered : entry.to) : entry.actions.find(([, to]) => allowed(to))?.[1];

  };

  const rank = (label: string) => personal ? Number(/^(My |Apply|Today)/.test(label)) : manager ? Number(/Team|Approvals|review|workload|performance/i.test(label)) : Number(/^(Add |Create |Manage )/.test(label));
  const orderedActions = [...actions].sort(([a],[b])=>rank(b)-rank(a));

  return <>

    <MobileExperience /><MobileTools />

    <nav className="mobile-module-dock" aria-label={`${module.toUpperCase()} mobile navigation`}>

      {menus.map(entry => {

        const Icon = entry.icon;

        const active = current === entry;

        const target = destination(entry);

        const count = badges.data?.[entry.label] || 0;

        return <div className={`mobile-dock-item ${active ? "is-active" : ""}`} key={entry.label}>

          {target ? <Link to={target} aria-label={entry.label} aria-describedby={count > 0 ? `mobile-count-${module}-${entry.label.replace(/\W/g, "")}` : undefined} aria-current={active ? "page" : undefined} className="mobile-dock-destination"><span className="mobile-dock-icon"><Icon size={22} strokeWidth={1.8} aria-hidden="true" />{count > 0 && <span id={`mobile-count-${module}-${entry.label.replace(/\W/g, "")}`} className="mobile-dock-badge" aria-label={`${count} need attention`}>{count > 99 ? "99+" : count}</span>}</span><span>{entry.label}</span></Link> : <span className="mobile-dock-destination" aria-disabled="true"><Icon size={22}/><span>{entry.label}</span></span>}



        </div>;

      })}

    </nav>

    <button type="button" className="mobile-dock-quick" aria-label={`${current.label} quick actions`} aria-haspopup="dialog" aria-expanded={!!selected} onClick={() => setSelected(current)}><ChevronUp size={15}/>{current.label} actions</button>

    <MobileSheet open={!!selected} onClose={() => setSelected(null)} title={selected?.label || "Quick actions"}>

      <span className="mobile-dock-eyebrow">{module === "srm" ? "SALES" : module.toUpperCase()} · QUICK ACTIONS</span>

      <div className="mobile-dock-actions">{orderedActions.map(([label, to]) => <Link key={label} to={to} onClick={() => setSelected(null)}><span>{label}</span><ArrowUpRight size={18} aria-hidden="true" /></Link>)}</div>

    </MobileSheet>

  </>;

}

