import { useEffect } from "react";
import { recordSavedEvent, type RecordSaved } from "@/lib/record-changes";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { useWorkspaceContext } from "./useWorkspaceContext";
import { usePageRefresh } from "@/lib/page-refresh";
import { BookOpenCheck, CalendarCheck2, ContactRound, FileCheck2, Handshake, ListTodo, ShieldCheck, Users } from "lucide-react";
import type { DirectoryMetric } from "./WorkspaceDirectory";

type Module = "crm" | "hrms" | "srm" | "fam";
type Data = Record<string, unknown>;
const record = (value: unknown): Data => value && typeof value === "object" && !Array.isArray(value) ? value as Data : {};
/** Read the existing permission-filtered dashboards; do not fetch record lists to
 * reconstruct totals or combine monetary values across currencies. */
export function useWorkspaceOverview(module: Module) {
  const qc = useQueryClient();
  const context = useWorkspaceContext();
  const user = useAuthStore(s => s.user);
  const scope = [user?.id, user?.access?.companyId, sessionStorage.getItem("suite-organization"), sessionStorage.getItem("suite-branch"), JSON.stringify([user?.role, user?.is_superuser, user?.access?.grants[module]])];
  const path = module === "hrms" ? "/employees/workbench/home?scope=organization" : `/${module}/dashboard`;
  const enabled = context.ready && Boolean(user && canAccessRoute(module === "hrms" ? "/hrms/daily-work" : `/${module}/dashboard`, user.role, user.is_superuser));
  const query = useQuery({ queryKey: ["workspace-overview", module, ...scope], enabled, queryFn: ({ signal }) => api.get<Data>(path, { signal }).then(response => response.data), staleTime: 30_000, retry: false });
  usePageRefresh(() => enabled ? query.refetch() : undefined);
  useEffect(() => {
    const saved = (event: Event) => {
      const change = (event as CustomEvent<RecordSaved>).detail;
      const prefix = module === "hrms" ? /\/(employees|leave|attendance|expenses|hr-workbench)(?:\/|$|\?)/ : new RegExp(`/${module}/`);
      if (enabled && prefix.test(change.url)) void qc.invalidateQueries({ queryKey: ["workspace-overview", module] });
    };
    window.addEventListener(recordSavedEvent, saved);
    return () => window.removeEventListener(recordSavedEvent, saved);
  }, [module, enabled, qc]);
  const denied = [401, 403, 404].includes((query.error as { response?: { status?: number } } | null)?.response?.status || 0);
  const data = denied ? {} : query.data || {};
  const summary = record(data.summary);
  const pending = record(data.pending_counts);
  const year = record(data.currentFinancialYear);
  let values: { label: string; value: unknown; icon: DirectoryMetric["icon"] }[] = [];
  if (module === "crm") values = [
    { label: "Leads", value: summary.leads, icon: ContactRound },
    { label: "Open deals", value: summary.openDeals, icon: Handshake },
    { label: "Overdue activities", value: summary.overdueActivities, icon: CalendarCheck2 },
  ];
  if (module === "hrms") values = [
    { label: "Employees in scope", value: data.employee_count, icon: Users },
    { label: "Pending approvals", value: pending.approvals, icon: ShieldCheck },
    { label: "Open punches today", value: data.missing_punches, icon: CalendarCheck2 },
  ];
  if (module === "srm") values = [
    { label: "Sales orders · all time", value: data.total_sales_orders, icon: ListTodo },
    { label: "Pending approvals", value: data.pending_approvals, icon: ShieldCheck },
    { label: "Approved invoices", value: data.approved_invoices, icon: FileCheck2 },
  ];
  if (module === "fam") values = [
    { label: "Financial year", value: year.name, icon: BookOpenCheck },
    { label: "Books status", value: data.booksStatus, icon: ShieldCheck },
    { label: "Base currency", value: data.baseCurrency, icon: BookOpenCheck },
  ];
  const metrics: DirectoryMetric[] = values.flatMap(value => typeof value.value === "number" && Number.isFinite(value.value) || typeof value.value === "string" && value.value.trim() ? [{ ...value, value: value.value as string | number }] : []);
  return { metrics, loading: query.isFetching, error: enabled && query.isError, retry: () => void query.refetch() };
}
