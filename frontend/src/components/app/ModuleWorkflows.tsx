import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { canAccessRoute } from "@/lib/roles";
import { useAuthStore } from "@/store/authStore";
const workflows = {
  fam: [["Record a voucher", "/fam/vouchers/new"], ["Receivables", "/fam/ar"], ["Payables", "/fam/ap"], ["Reconcile bank", "/fam/bank-reconciliation"]],
  srm: [["Sales orders", "/srm/sales-orders"], ["Invoices", "/srm/invoices"], ["Collections", "/srm/collections"], ["Inventory", "/srm/inventory"]],
  crm: [["Follow up leads", "/crm/leads"], ["Manage pipeline", "/crm/pipeline"], ["Today's tasks", "/crm/tasks"], ["Calendar", "/crm/calendar"]],
};
export default function ModuleWorkflows({ module, dark = false }: { module: keyof typeof workflows; dark?: boolean }) {
  const user = useAuthStore(s => s.user);
  const items = workflows[module].filter(([, path]) => canAccessRoute(path, user?.role, user?.is_superuser));
  if (!items.length) return null;
  return <nav aria-label="Core workflows" className={`flex flex-wrap gap-x-6 gap-y-2 rounded-lg border px-4 py-3 ${dark ? "border-white/10 bg-white/5 text-slate-100" : "bg-card text-card-foreground"}`}>
    {items.map(([label, path]) => <Link key={path} to={path} className="inline-flex items-center gap-2 py-1 text-sm font-medium hover:underline">{label}<ArrowRight size={13} className="opacity-50" /></Link>)}
  </nav>;
}
