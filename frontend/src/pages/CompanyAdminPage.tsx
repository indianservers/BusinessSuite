import { Link } from "react-router-dom";
import { BarChart3, Settings, Users, ArrowUpRight } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";

export default function CompanyAdminPage() {
  const user = useAuthStore(state => state.user);
  const entries = [
    {title:"Settings", description:"Company details, branches, defaults and application configuration.", to:"/settings", icon:Settings},
    {title:"Insights · Analytics", description:"Business performance, reports, dashboards and trends across your authorized applications.", to:"/analytics", icon:BarChart3},
    ...(user?.is_superuser || user?.access?.isAccessAdmin ? [{title:"Users & access",description:"Manage company users, roles and permissions.",to:"/admin/access",icon:Users}] : []),
  ].filter(entry => canAccessRoute(entry.to, user?.role, user?.is_superuser));
  return <main className="mx-auto max-w-5xl space-y-6 p-6"><header><p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Company workspace</p><h1 className="mt-2 text-3xl font-semibold">Company Admin</h1><p className="mt-2 text-muted-foreground">Manage your company and review business insights.</p></header><div className="grid gap-4 md:grid-cols-2">{entries.map(entry=><Link key={entry.to} to={entry.to} className="group rounded-xl border bg-card p-6 shadow-sm hover:border-primary"><div className="flex items-center justify-between"><entry.icon className="h-6 w-6 text-primary"/><ArrowUpRight className="h-4 w-4 text-muted-foreground"/></div><h2 className="mt-5 text-lg font-semibold">{entry.title}</h2><p className="mt-2 text-sm text-muted-foreground">{entry.description}</p></Link>)}</div></main>;
}
