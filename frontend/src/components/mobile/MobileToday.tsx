import { Link, useLocation } from "react-router-dom";
import { ArrowUpRight, CalendarDays } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { suiteScope, useSuitePreferences } from "@/store/suitePreferences";
import { useQuery } from "@tanstack/react-query";
import { api, attendanceApi } from "@/services/api";
import { LoadingState } from "@/components/ui/state";

const destinations: Record<string, [string, string, string][]> = {
  crm: [["Follow-ups", "Your follow-up worklist", "/crm/follow-ups"], ["Tasks", "Your tasks and reminders", "/crm/tasks"], ["Leads", "Review leads and next steps", "/crm/leads"]],
  pms: [["My work", "Your tasks and due dates", "/pms/my-work"], ["My assignments", "Work assigned to you", "/pms/my-assignments"], ["Reviews", "Review submitted work", "/pms/reviews"]],
  srm: [["Follow-ups", "Customer follow-ups", "/srm/follow-ups"], ["Orders", "Review sales orders", "/srm/sales-orders"], ["Collections", "Payments needing attention", "/srm/collections"]],
  hrms: [["Attendance", "Check in and review your punches", "/hrms/my-attendance"], ["Leave", "Your requests and balances", "/hrms/leave"], ["Approvals", "Requests awaiting a decision", "/hrms/workflow"]],
};

export default function MobileToday({ close }: { close: () => void }) {
  const user = useAuthStore(state => state.user), { pathname } = useLocation();
  const recent = useSuitePreferences(state => state.contexts[suiteScope(user?.id, user?.access?.companyId)]?.recent || []);
  const module = pathname.split("/")[1];
  const allowed = (path: string) => path.startsWith("/") && !path.startsWith("//") && canAccessRoute(path.split("?")[0], user?.role, user?.is_superuser);
  const work = useQuery<{ title: string; subtitle: string; path: string }[]>({
    queryKey: ["mobile-today-work", user?.id, user?.access?.companyId, sessionStorage.getItem("suite-branch"), module],
    enabled: !!user && (module === "hrms" ? !!user.employee_id && allowed("/hrms/my-attendance") : module === "pms" ? allowed("/pms/my-work") : ["crm", "srm"].includes(module) && allowed(`/${module}/follow-ups`)),
    staleTime: 30_000,
    queryFn: async () => {
      if (module === "hrms") {
        const { data } = await attendanceApi.getToday();
        return [{ title: data?.check_out ? "Checked out" : data?.check_in ? "Checked in" : "Attendance not started", subtitle: data?.check_in ? `Check-in ${new Date(data.check_in).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "Open attendance to check in", path: "/hrms/my-attendance" }];
      }
      if (module === "pms") {
        const { data } = await api.get("/project-management/tasks", { params: { workView: "mine", pageSize: 8 }, progress: false });
        return (data.items || []).map((task: { id: number; title: string; status?: string; due_date?: string }) => ({ title: task.title, subtitle: [task.status, task.due_date ? `Due ${new Date(task.due_date).toLocaleDateString()}` : ""].filter(Boolean).join(" · "), path: `/pms/tasks/${task.id}` }));
      }
      const { data } = await api.get("/follow-ups", { params: { status: "Due", page: 1, per_page: 8 }, progress: false });
      return (data.items || []).map((row: { id: number; title: string; customer_name?: string; due_at?: string }) => ({ title: row.title, subtitle: row.customer_name || "Follow-up due", path: `/${module}/follow-ups/${row.id}` }));
    },
  });
  return <div className="mobile-today">
    <p className="mobile-today-date"><CalendarDays size={16} aria-hidden="true" />{new Date().toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}</p>
    <div className="mobile-today-links">{(destinations[module] || []).filter(([, , path]) => allowed(path)).map(([title, description, path]) => <Link key={path} to={path} onClick={close}><span><strong>{title}</strong><small>{description}</small></span><ArrowUpRight size={18} aria-hidden="true" /></Link>)}</div>
    {work.isFetching && !work.data && <LoadingState label="Loading your work…" />}
    {work.isError && <p role="alert" className="text-sm">Could not load your work. <button type="button" className="underline" onClick={() => void work.refetch()}>Retry</button></p>}
    {!!work.data?.length && <><h3>{module === "hrms" ? "Your attendance today" : module === "pms" ? "Assigned to you" : "Follow-ups due"}</h3><div className="mobile-today-links">{work.data.filter(row => allowed(row.path)).map(row => <Link key={row.path} to={row.path} onClick={close}><span><strong>{row.title}</strong><small>{row.subtitle}</small></span><ArrowUpRight size={16} aria-hidden="true" /></Link>)}</div></>}
    {work.isSuccess && !work.data.length && <p className="my-3 text-sm text-muted-foreground">{module === "pms" ? "No assignments to show." : "No due follow-ups to show."}</p>}
    {!!recent.filter(path => path !== pathname && path.startsWith(`/${module}/`) && allowed(path)).length && <><h3>Recently opened</h3><div className="mobile-today-links">{recent.filter(path => path !== pathname && path.startsWith(`/${module}/`) && allowed(path)).slice(0, 5).map(path => <Link key={path} to={path} onClick={close}><span>{path.split("?")[0].split("/").filter(Boolean).slice(1).join(" / ").replace(/-/g, " ")}</span><ArrowUpRight size={16} aria-hidden="true" /></Link>)}</div></>}
  </div>;
}
