import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Banknote, ClipboardList, Package, Receipt, RefreshCw, TrendingUp } from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCurrency, formatDate } from "@/lib/utils";
import { toast } from "@/hooks/use-toast";

type Salary = { id: number; ctc: string; effective_from: string; effective_to: string | null; payroll_type: string };
type Overview = {
  employee_id: number; as_of: string; currency: string;
  access: { payroll: boolean; assets: boolean; expenses: boolean; profile_changes: boolean };
  salary: Salary | null; salary_history: Salary[];
  increments: { id: number; current_ctc: string; proposed_ctc: string; effective_from: string; reason: string | null; status: string }[];
  assets: { id: number; name: string; asset_tag: string; serial_number: string | null; assigned_date: string; condition: string | null; acknowledged: boolean }[];
  expenses: { id: number; claim_number: string; claim_type: string; expense_date: string; amount: string; approved_amount: string; currency: string; status: string; reimbursed_at: string | null; payment_reference: string | null; payroll_run_id: number | null }[];
  pending_actions: { id: string; title: string; section: string; owner: string }[];
};

export default function Employee360Panel({ employeeId, onOpenTab, isOwnProfile }: {
  employeeId: number; onOpenTab: (tab: string) => void; isOwnProfile: boolean;
}) {
  const qc = useQueryClient();
  const userId = useAuthStore(s => s.user?.id);
  const key = ["employee-360", userId, employeeId];
  const [expenseStatus, setExpenseStatus] = useState("all");
  const overview = useQuery({ queryKey: key, queryFn: () => api.get<Overview>(`/employees/${employeeId}/360`).then(r => r.data) });
  const acknowledge = useMutation({
    mutationFn: (id: number) => api.put(`/assets/assignments/${id}/acknowledge`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: key }); toast({ title: "Asset receipt acknowledged" }); },
    onError: () => toast({ title: "Could not acknowledge asset. Please try again.", variant: "destructive" }),
  });
  const jump = (section: string) => {
    if (section === "profile") { onOpenTab("personal"); return; }
    document.getElementById(`employee-${employeeId}-${section}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    document.getElementById(`employee-${employeeId}-${section}`)?.focus({ preventScroll: true });
  };
  if (overview.isPending) return <p role="status" className="p-6 text-muted-foreground">Loading salary, assets, expenses and pending actions…</p>;
  if (overview.isError) return <div role="alert" className="rounded-lg border p-6"><p>Employee 360 could not be loaded. Your access may have changed or the service may be unavailable.</p><Button variant="outline" onClick={() => overview.refetch()}>Try again</Button></div>;
  const data = overview.data;
  const expenseTotals = new Map<string, { claimed: number; approved: number; paid: number; awaitingPayment: number }>();
  for (const claim of data.expenses) {
    const currency = claim.currency || data.currency;
    const total = expenseTotals.get(currency) || { claimed: 0, approved: 0, paid: 0, awaitingPayment: 0 };
    total.claimed += Number(claim.amount);
    if (["finance_approved", "reimbursed", "paid"].includes(claim.status.toLowerCase()) || claim.reimbursed_at) {
      total.approved += Number(claim.approved_amount);
      if (claim.reimbursed_at || ["reimbursed", "paid"].includes(claim.status.toLowerCase())) total.paid += Number(claim.approved_amount);
      else total.awaitingPayment += Number(claim.approved_amount);
    }
    expenseTotals.set(currency, total);
  }
  const visibleClaims = data.expenses.filter(c => expenseStatus === "all" || c.status === expenseStatus);
  const sectionProps = (name: string) => ({ id: `employee-${employeeId}-${name}`, tabIndex: -1, className: "scroll-mt-6" });
  const restricted = <p className="text-sm text-muted-foreground">This section is restricted by your access permissions.</p>;
  return <div className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 className="text-xl font-semibold">Employee 360</h2><p className="text-sm text-muted-foreground">Pay, equipment, claims and next steps in one place.</p></div>
      <Button variant="outline" disabled={overview.isFetching} onClick={() => overview.refetch()}><RefreshCw className="mr-2 h-4 w-4" />{overview.isFetching ? "Refreshing…" : "Refresh overview"}</Button>
    </div>
    {overview.isRefetchError && <p role="alert" className="text-sm text-destructive">Refresh failed. Displayed information may be out of date.</p>}
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2 text-base"><ClipboardList className="h-5 w-5" />Pending actions <Badge variant="outline">{data.pending_actions.length}</Badge></CardTitle></CardHeader>
      <CardContent>{data.pending_actions.length ? <ul className="divide-y">{data.pending_actions.map(action => <li key={action.id} className="flex flex-wrap items-center justify-between gap-3 py-3"><div><p className="text-sm font-medium">{action.title}</p><p className="text-xs text-muted-foreground">Waiting on: {action.owner}</p></div><Button size="sm" variant="outline" onClick={() => jump(action.section)}>View details</Button></li>)}</ul> : <p className="text-sm text-muted-foreground">No pending actions in the sections you can access.</p>}</CardContent>
    </Card>
    <div className="grid items-start gap-5 xl:grid-cols-2">
      <section {...sectionProps("salary")}><Card>
        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Banknote className="h-5 w-5" />Salary</CardTitle></CardHeader>
        <CardContent className="space-y-4">{!data.access.payroll ? restricted : <>
          {data.salary ? <div><p className="text-sm text-muted-foreground">Current annual CTC · {data.currency}</p><p className="text-2xl font-semibold">{formatCurrency(Number(data.salary.ctc), data.currency)}</p><p className="text-xs text-muted-foreground">Effective {formatDate(data.salary.effective_from)} · {data.salary.payroll_type.replace(/_/g, " ")}</p><p className="mt-2 text-xs text-muted-foreground">CTC is employer cost, not take-home pay.</p></div> : <p className="text-sm">No salary is effective today.</p>}
          <Button size="sm" variant="outline" onClick={() => onOpenTab("payroll")}>Open salary setup</Button>
          <details><summary className="cursor-pointer text-sm font-medium">Salary history ({data.salary_history.length})</summary><ul className="mt-2 divide-y">{data.salary_history.map(row => <li key={row.id} className="py-2 text-sm"><div className="flex flex-wrap justify-between gap-2"><span>{formatCurrency(Number(row.ctc), data.currency)}</span><Badge variant="outline">{row.id === data.salary?.id ? "Current" : row.effective_from > data.as_of ? "Scheduled" : "Historical"}</Badge></div><p className="text-xs text-muted-foreground">{formatDate(row.effective_from)}{row.effective_to ? ` – ${formatDate(row.effective_to)}` : " onwards"}</p></li>)}</ul>{!data.salary_history.length && <p className="mt-2 text-sm text-muted-foreground">No salary assignments recorded.</p>}</details>
        </>}</CardContent>
      </Card></section>
      <section {...sectionProps("increments")}><Card>
        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><TrendingUp className="h-5 w-5" />Increments & revisions</CardTitle></CardHeader>
        <CardContent>{!data.access.payroll ? restricted : data.increments.length ? <ul className="divide-y">{data.increments.map(row => {
          const old = Number(row.current_ctc), proposed = Number(row.proposed_ctc);
          return <li key={row.id} className="space-y-1 py-3 text-sm"><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">{formatCurrency(old, data.currency)} → {formatCurrency(proposed, data.currency)}</span><Badge variant="outline">{row.status}</Badge></div><p className="text-xs text-muted-foreground">Effective {formatDate(row.effective_from)} · {old > 0 ? `${((proposed - old) / old * 100).toFixed(1)}% change` : "Initial compensation"}</p>{row.reason && <p className="break-words">{row.reason}</p>}</li>;
        })}</ul> : <p className="text-sm text-muted-foreground">No increment requests recorded. Salary assignments are listed separately in salary history.</p>}</CardContent>
      </Card></section>
      <section {...sectionProps("assets")}><Card>
        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Package className="h-5 w-5" />Assigned assets</CardTitle></CardHeader>
        <CardContent>{!data.access.assets ? restricted : data.assets.length ? <ul className="divide-y">{data.assets.map(row => <li key={row.id} className="space-y-2 py-3 text-sm"><div className="flex flex-wrap justify-between gap-2"><span className="font-medium">{row.name} · {row.asset_tag}</span><Badge variant="outline">{row.acknowledged ? "Acknowledged" : "Awaiting acknowledgement"}</Badge></div><p className="text-xs text-muted-foreground">Serial: {row.serial_number || "Not recorded"} · Assigned {formatDate(row.assigned_date)} · Condition: {row.condition || "Not recorded"}</p>{isOwnProfile && !row.acknowledged && <Button size="sm" variant="outline" disabled={acknowledge.isPending} onClick={() => acknowledge.mutate(row.id)}>Acknowledge receipt</Button>}</li>)}</ul> : <p className="text-sm text-muted-foreground">No assets currently assigned.</p>}</CardContent>
      </Card></section>
      <section {...sectionProps("expenses")}><Card>
        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Receipt className="h-5 w-5" />Employee expenses</CardTitle></CardHeader>
        <CardContent className="space-y-4">{!data.access.expenses ? restricted : <>
          {[...expenseTotals].map(([currency, total]) => <dl key={currency} className="grid grid-cols-2 gap-3 rounded-lg border p-3 text-sm">{[["Claimed", total.claimed], ["Finance approved", total.approved], ["Paid", total.paid], ["Awaiting payment", total.awaitingPayment]].map(([label, amount]) => <div key={String(label)}><dt className="text-xs text-muted-foreground">{label} · {currency}</dt><dd className="font-medium">{formatCurrency(Number(amount), currency)}</dd></div>)}</dl>)}
          {data.expenses.length > 0 && <label className="block text-sm">Claim status<select className="ml-2 rounded-md border bg-background p-2" value={expenseStatus} onChange={e => setExpenseStatus(e.target.value)}><option value="all">All statuses</option>{[...new Set(data.expenses.map(c => c.status))].map(status => <option key={status} value={status}>{status.replace(/_/g, " ")}</option>)}</select></label>}
          <ul className="divide-y">{visibleClaims.map(row => <li key={row.id} className="space-y-1 py-3 text-sm"><div className="flex flex-wrap justify-between gap-2"><span className="font-medium">{row.claim_number}</span><Badge variant="outline">{row.status.replace(/_/g, " ")}</Badge></div><p>{row.claim_type} · {formatDate(row.expense_date)}</p><p>Claimed {formatCurrency(Number(row.amount), row.currency || data.currency)} · Approved {formatCurrency(Number(row.approved_amount), row.currency || data.currency)}</p>{row.payroll_run_id && <p className="text-xs text-muted-foreground">Payroll run #{row.payroll_run_id}</p>}{row.payment_reference && <p className="break-all text-xs text-muted-foreground">Payment reference: {row.payment_reference}</p>}{row.reimbursed_at && <p className="text-xs text-muted-foreground">Reimbursed {formatDate(row.reimbursed_at)}</p>}</li>)}</ul>
          {!visibleClaims.length && <p className="text-sm text-muted-foreground">{data.expenses.length ? "No claims match this status." : "No expense claims recorded."}</p>}
        </>}</CardContent>
      </Card></section>
    </div>
  </div>;
}
