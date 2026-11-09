import { sharedNotesPath, createSharedNotePath } from "@/lib/shared-notes";

import {lazy,Suspense,useState,useEffect,type ReactNode} from "react";
const CRMQuickCreate=lazy(()=>import("@/apps/crm/SalesActions").then(m=>({default:m.CRMQuickCreate})));
import { Bell, Building2, CalendarDays, CheckCircle2, FileText, LifeBuoy, Receipt, ShoppingBag, UserPlus, Users, Wallet } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute, getRoleKey } from "@/lib/roles";
import NewMenu, { type NewAction } from "./NewMenu";
import PMSQuickAddMenu from "@/apps/project-management/components/PMSQuickAddMenu";

export default function ModuleNewMenu({ children }: { children?: (actions: NewAction[]) => ReactNode } = {}) {
  const { pathname, search } = useLocation();
  const [crmQuick,setCRMQuick]=useState("");
  useEffect(() => { setCRMQuick(""); }, [pathname]);
  const routerNavigate = useNavigate();
  const navigate = (path: string) => {
    if (!/^\/(srm|crm)(\/|$)/.test(pathname)) return routerNavigate(path);
    const destination = new URL(path, window.location.origin), current = new URLSearchParams(search);
    for (const key of ["customer_id", "company_id", "contact_id", "sales_order_id", "contract_id", "engagement_id"]) {
      const value = current.get(key);
      if (value && /^\d+$/.test(value) && !destination.searchParams.has(key)) destination.searchParams.set(key, value);
    }
    const record = pathname.match(/^\/srm\/(customers|sales-orders|contracts|engagements)\/(\d+)(?:\/360)?$/);
    if (record) destination.searchParams.set(({ customers: "customer_id", "sales-orders": "sales_order_id", contracts: "contract_id", engagements: "engagement_id" } as Record<string, string>)[record[1]], record[2]);
    const crmRecord = pathname.match(/^\/crm\/(companies|customers|contacts)\/(\d+)(?:\/360)?$/);
    if (crmRecord) destination.searchParams.set(crmRecord[1] === "contacts" ? "contact_id" : "company_id", crmRecord[2]);
    return routerNavigate(destination.pathname + destination.search + destination.hash);
  };

  const user = useAuthStore(s => s.user);
  const role = String(user?.role || "").toLowerCase();
  const hrRole = getRoleKey(user?.role, user?.is_superuser);
  const privileged = !!user?.is_superuser || ["super_admin", "admin"].includes(role);
  const moduleKey = ({crm:"crm",hrms:"hrms",srm:"srm",fam:"fam",pms:"project_management"} as Record<string,string>)[pathname.split("/")[1]];
  const moduleGrant = user?.access?.grants[moduleKey];
  const notesGrant = user?.access?.grants.project_management;
  const noteActions: NewAction[] = !pathname.startsWith("/pms") && canAccessRoute(sharedNotesPath, user?.role, user?.is_superuser) &&
    (user?.is_superuser || !user?.access?.managed || notesGrant?.enabled && notesGrant.actions.includes("create"))
    ? [{ label: "Note", description: "Create a note in the shared Notes workspace", icon: FileText, menuPaths: [sharedNotesPath], onSelect: () => routerNavigate(createSharedNotePath) }] : [];
  if (!user?.is_superuser && moduleGrant && (!moduleGrant.enabled || !moduleGrant.actions.some(action=>["create","edit","assign"].includes(action)))) return children ? <>{children(noteActions)}</> : <NewMenu actions={noteActions} />;
  const actions: NewAction[] = [...noteActions];
  const add = (label: string, description: string, icon: NewAction["icon"], path: string, allowed = true, disabled = false) => {
    if (allowed && (!moduleGrant || user?.is_superuser || moduleGrant.actions.includes("create") || ["Apply Leave", "Support ticket", "Correct Attendance", "Generate Letter"].includes(label)) && canAccessRoute(path.split(/[?#]/)[0], user?.role, user?.is_superuser)) actions.push({ label, description, icon, disabled, menuPaths: label === "Correct Attendance" ? [] : [path.split(/[?#]/)[0].replace(/\/(new|create)$/, "")], onSelect: () => navigate(path) });
  };
  if (pathname.startsWith("/crm")) {
    const manages = !!user?.is_superuser || (moduleGrant ? moduleGrant.enabled && moduleGrant.actions.includes("create") : privileged || ["crm_super_admin", "crm_org_admin", "crm_sales_manager", "crm_sales_executive"].includes(role));
    const quick=(label:string,type:string,icon:NewAction["icon"],path:string)=>{if(manages&&(user?.is_superuser||!moduleGrant||moduleGrant.permissions.some(p=>["crm_admin","crm_manage",`crm_${({lead:"leads",customer:"companies",reminder:"activities",contact:"contacts",company:"companies",deal:"deals",task:"activities",activity:"activities"} as Record<string,string>)[type]}_manage`].includes(p)))&&canAccessRoute(path,user?.role,user?.is_superuser))actions.push({label,description:`Quick capture ${label.toLowerCase()}`,icon,menuPaths:[path],onSelect:()=>type === "reminder" ? setCRMQuick(type) : navigate(type === "task" ? "/pms/tasks/new" : `${path}?new=${type === "customer" ? "customers" : type === "company" ? "companies" : type === "activity" ? "activities" : type + "s"}`)});};
    quick("Add Lead","lead",UserPlus,"/crm/leads");quick("Add Customer","customer",Users,"/crm/customers");quick("Reminder","reminder",Bell,"/crm/tasks");quick("Contact","contact",Users,"/crm/contacts");quick("Company","company",Building2,"/crm/companies");quick("Deal","deal",Wallet,"/crm/deals");quick("Task","task",CheckCircle2,"/crm/tasks");quick("Activity","activity",CalendarDays,"/crm/activities");
    add("Product", "Manage the CRM product catalog", ShoppingBag, "/crm/products?new=products", manages && (!!user?.is_superuser || !moduleGrant || moduleGrant.permissions.some(p=>["crm_admin","crm_manage","crm_products_manage"].includes(p))));
    add("Service", "Manage the CRM service catalog", ShoppingBag, "/crm/services?new=services", manages && (!!user?.is_superuser || !moduleGrant || moduleGrant.permissions.some(p=>["crm_admin","crm_manage","crm_products_manage"].includes(p))));
    add("Quote", "Prepare a quote for a customer", FileText, "/crm/quotes?new=quotes", manages && (!!user?.is_superuser || !moduleGrant || moduleGrant.permissions.some(p=>["crm_admin","crm_manage","crm_quotes_manage"].includes(p))));
    add("Support ticket", "Record a customer support request", LifeBuoy, "/crm/tickets?new=tickets", manages || role === "crm_support_agent");
    add("Campaign", "Plan a marketing campaign", CalendarDays, "/crm/campaigns?new=campaigns", privileged || ["crm_super_admin", "crm_org_admin", "crm_marketing_user"].includes(role));
  } else if (pathname.startsWith("/srm")) {
    const manages = privileged || ["srm_admin", "srm_sales_manager", "srm_sales_executive"].includes(role);
    add("Sales order", "Draft an order for your customer", ShoppingBag, "/srm/sales-orders#new-record", manages);
    add("Contract", "Prepare a commercial agreement", FileText, "/srm/contracts#new-record", manages);
    add("Engagement", "Set up delivery for your customer", Users, "/srm/engagements#new-record", manages);
    add("Billing plan", "Plan milestones and recurring billing", CalendarDays, "/srm/billing-plans#new-record", manages);
    add("Invoice draft", "Prepare an invoice without sending it", Receipt, "/srm/invoice-drafts#new-record", privileged || ["srm_admin", "srm_finance_manager"].includes(role));
  } else if (pathname.startsWith("/fam")) {
    const manages = privileged || ["fam_admin", "accountant", "finance_manager", "fam_finance_manager"].includes(role);
    add("Voucher", "Prepare a balanced accounting draft", Receipt, "/fam/vouchers/new", manages);
    add("Customer", "Create a customer and linked ledger", UserPlus, "/fam/customers#new-record", manages);
    add("Vendor", "Create a supplier and linked ledger", Building2, "/fam/vendors#new-record", manages);
    add("Purchase bill", "Capture a vendor bill draft", FileText, "/fam/purchase-bills/new", manages);
    add("Expense claim", "Record an expense for review", Wallet, "/fam/expenses/new", manages);
  } else if (pathname.startsWith("/hrms")) {
    if((user?.is_superuser || (moduleGrant ? moduleGrant.actions.includes("create") && moduleGrant.permissions.includes("employee_create") : ["admin","hr"].includes(hrRole)))&&canAccessRoute("/hrms/employees/new",user?.role,user?.is_superuser))actions.push({label:"Add Employee",description:"Create an employee with the complete guided form",icon:UserPlus,menuPaths:["/hrms/employees"],onSelect:()=>navigate("/hrms/employees/new")});
    add("Correct Attendance", "Review missing punches and incomplete shifts", CalendarDays, "/hrms/daily-work?view=attendance", ["admin","hr","manager"].includes(hrRole));
    add("Generate Letter", "Open employee letters and certificates", FileText, "/hrms/letters-certificates?new=letter", ["admin","hr"].includes(hrRole));
    add("Apply Leave", "Apply for time off", CalendarDays, "/hrms/leave?new=leave", !!user?.employee_id);
    add("Support ticket", user?.employee_id ? "Ask your support team for help" : "Link an employee profile to raise tickets", LifeBuoy, "/hrms/helpdesk?new=ticket", true, !user?.employee_id);
  }
  // Only expose creation destinations with a real form/intent; reports and audit pages stay navigation-only.
  const definitionCreate = (permissions: string[]) => !!user?.is_superuser || (user?.access
    ? Object.values(user.access.grants).some(grant => grant.enabled && grant.actions.includes("create") && permissions.some(permission => grant.permissions.includes(permission)))
    : privileged);
  if (["crm", "srm", "fam", "hrms", "pms"].includes(pathname.split("/")[1])) {
    const root = "/" + pathname.split("/")[1];
    add("Form", "Open a blank form draft", FileText, `${root}/forms/new`, !!user?.is_superuser || (moduleGrant ? moduleGrant.enabled && moduleGrant.actions.includes("create") : privileged));
  }
  if (pathname.startsWith("/srm")) {
    const manages = !!user?.is_superuser || (moduleGrant ? moduleGrant.enabled && moduleGrant.actions.includes("create") : privileged || ["srm_admin", "srm_sales_manager", "srm_sales_executive"].includes(role));
    add("Customer", "Create a customer", UserPlus, "/srm/customers?new=company", manages);
    add("Vendor", "Create a vendor", Building2, "/srm/vendors?new=company", manages);
    add("Catalog item", "Add a product or service", ShoppingBag, "/srm/inventory/products?new=item", manages);
    const catalogAction = actions.find(action => action.label === "Catalog item");
    if (catalogAction) catalogAction.menuPaths = ["/srm/inventory/products", "/srm/inventory/items", "/srm/products", "/srm/products-services", "/srm/services", "/srm/pos/products"];
  }
  if (pathname.startsWith("/hrms")) add("Asset", "Register company equipment", ShoppingBag, "/hrms/assets#new-record", definitionCreate(["asset_manage", "hr_asset_manage"]));
  if (pathname.startsWith("/crm")) add("Email", "Open the email composer", FileText, "/crm/emails?new=email", definitionCreate(["communication_email_send"]));
  if (pathname.startsWith("/analytics")) {
    add("Report", "Open the report builder", FileText, "/analytics/report-builder?new=report", definitionCreate(["analytics_manage", "analytics_admin"]));
    if (actions.length) actions[actions.length - 1].menuPaths = ["/analytics/reports", "/analytics/report-builder"];
    add("Report schedule", "Choose report, recipients and frequency", CalendarDays, "/analytics/scheduled-reports?new=schedule", definitionCreate(["analytics_schedule"]));
  }
  if (pathname.startsWith("/admin/customization")) add("Field", "Configure a new custom field", FileText, "/admin/customization/fields?new=field", definitionCreate(["customization_manage", "customization_fields_manage"]));
  if (pathname.startsWith("/admin/customization")) {
    for (const [kind, label] of [["modules", "Module"], ["buttons", "Record action"], ["validation-rules", "Validation rule"], ["related-lists", "Related list"], ["layouts", "Layout"], ["views", "Saved view"], ["kanban", "Kanban board"], ["picklists", "Picklist"]]) {
      add(label, `Configure a new ${label.toLowerCase()}`, FileText, `/admin/customization/${kind}?new=${kind}`, definitionCreate(["customization_manage", "customization_admin"]));
    }
  }
  return pathname.startsWith("/pms") ? <PMSQuickAddMenu>{children ? pmsActions => children([...pmsActions, ...actions]) : undefined}</PMSQuickAddMenu> : <>{children ? children(actions) : <NewMenu actions={actions} />}{pathname.startsWith("/crm")&&crmQuick&&<Suspense fallback={<p role="status">Loading quick capture…</p>}><CRMQuickCreate key={crmQuick} type={crmQuick} close={()=>setCRMQuick("")} saved={()=>{window.dispatchEvent(new CustomEvent("crm:records-changed"));}}/></Suspense>}</>;
}
