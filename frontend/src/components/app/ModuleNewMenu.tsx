import {lazy,Suspense,useState} from "react";
const HRQuickAdd=lazy(()=>import("@/apps/hrms/workbench/shared").then(m=>({default:m.HRQuickAdd})));
const CRMQuickCreate=lazy(()=>import("@/apps/crm/SalesActions").then(m=>({default:m.CRMQuickCreate})));
import { Building2, CalendarDays, CheckCircle2, FileText, LifeBuoy, Receipt, ShoppingBag, UserPlus, Users, Wallet } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute, getRoleKey } from "@/lib/roles";
import NewMenu, { type NewAction } from "./NewMenu";
import PMSQuickAddMenu from "@/apps/project-management/components/PMSQuickAddMenu";

export default function ModuleNewMenu() {
  const { pathname } = useLocation();
  const [crmQuick,setCRMQuick]=useState("");
  const [hrQuick,setHRQuick]=useState(false);
  const navigate = useNavigate();
  const user = useAuthStore(s => s.user);
  const role = String(user?.role || "").toLowerCase();
  const hrRole = getRoleKey(user?.role, user?.is_superuser);
  const privileged = !!user?.is_superuser || ["super_admin", "admin"].includes(role);
  const actions: NewAction[] = [];
  const add = (label: string, description: string, icon: NewAction["icon"], path: string, allowed = true, disabled = false) => {
    if (allowed && canAccessRoute(path.split(/[?#]/)[0], user?.role, user?.is_superuser)) actions.push({ label, description, icon, disabled, onSelect: () => navigate(path) });
  };
  if (pathname.startsWith("/crm")) {
    const manages = privileged || ["crm_super_admin", "crm_org_admin", "crm_sales_manager", "crm_sales_executive"].includes(role);
    const quick=(label:string,type:string,icon:NewAction["icon"],path:string)=>{if(manages&&canAccessRoute(path,user?.role,user?.is_superuser))actions.push({label,description:`Quick capture ${label.toLowerCase()}`,icon,onSelect:()=>setCRMQuick(type)});};
    quick("Lead","lead",UserPlus,"/crm/leads");quick("Contact","contact",Users,"/crm/contacts");quick("Customer company","company",Building2,"/crm/companies");quick("Deal","deal",Wallet,"/crm/deals");quick("Task","task",CheckCircle2,"/crm/tasks");quick("Activity","activity",CalendarDays,"/crm/activities");
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
    if(["admin","hr"].includes(hrRole)&&canAccessRoute("/hrms/employees/new",user?.role,user?.is_superuser))actions.push({label:"Add Employee",description:"Quick employee capture; finish details later",icon:UserPlus,onSelect:()=>setHRQuick(true)});
    add("Correct Attendance", "Review missing punches and incomplete shifts", CalendarDays, "/hrms/daily-work?view=attendance", ["admin","hr","manager"].includes(hrRole));
    add("Generate Letter", "Open employee letters and certificates", FileText, "/hrms/letters-certificates", ["admin","hr"].includes(hrRole));
    add("Apply Leave", "Apply for time off", CalendarDays, "/hrms/leave?new=leave", !!user?.employee_id);
    add("Support ticket", user?.employee_id ? "Ask your support team for help" : "Link an employee profile to raise tickets", LifeBuoy, "/hrms/helpdesk?new=ticket", true, !user?.employee_id);
  }
  return pathname.startsWith("/pms") ? <PMSQuickAddMenu /> : <><NewMenu actions={actions} />{hrQuick&&<Suspense fallback={<p role="status">Loading employee capture…</p>}><HRQuickAdd close={()=>setHRQuick(false)} saved={id=>{setHRQuick(false);navigate(`/hrms/employees/${id}`);}}/></Suspense>}{pathname.startsWith("/crm")&&crmQuick&&<Suspense fallback={<p role="status">Loading quick capture…</p>}><CRMQuickCreate key={crmQuick} type={crmQuick} close={()=>setCRMQuick("")} saved={()=>window.dispatchEvent(new CustomEvent("crm:records-changed"))}/></Suspense>}</>;
}
