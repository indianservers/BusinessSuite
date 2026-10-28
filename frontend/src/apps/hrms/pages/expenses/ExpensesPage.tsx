import { useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import EmployeeSearchSelect from "../../components/EmployeeSearchSelect";
import ExpenseClaimForm from "./ExpenseClaimForm";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { assetUrl, formatCurrencyPrecise as formatCurrency, formatDate } from "@/lib/utils";
import { toast } from "@/hooks/use-toast";
import { usePageTitle } from "@/hooks/use-page-title";
type Claim = { id: number; claim_number: string; claim_type: string; expense_date: string; amount: string; approved_amount: string; currency: string; status: string; payroll_run_id: number | null; payroll_reimbursement_id: number | null; reimbursed_at: string | null; reimbursement_reference: string | null; remarks: string | null; receipt_url: string | null; duplicate_receipt_claim_ids?: number[] };
type Statement = { employee_id: number; employee_name: string; totals: { currency: string; claimed: string; approved: string; outstanding: string; paid: string; pending_review: string; rejected: string }[]; claims: Claim[]; can_submit: boolean; can_manager_review: boolean; can_finance_review: boolean };
const errorText = (error: unknown) => { const d = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail; return typeof d === "string" ? d : "Check the values and try again."; };

export default function ExpensesPage() {
  usePageTitle("Employee expenses");
  const user = useAuthStore(s => s.user);
  const [params] = useSearchParams();
  const [employee, setEmployee] = useState(params.get("employee_id") || String(user?.employee_id || ""));
  const [dates, setDates] = useState({ from_date: "", to_date: "" });
  const [status, setStatus] = useState("all");
  const [review, setReview] = useState<{ claim: Claim; action: string } | null>(null);
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [reference, setReference] = useState("");
  const qc = useQueryClient();
  const statement = useQuery({ queryKey: ["expense-statement", user?.id, employee, dates], queryFn: () => api.get<Statement>(`/expenses/statements/${employee}`, { params: { from_date: dates.from_date || undefined, to_date: dates.to_date || undefined } }).then(r => r.data), enabled: !!employee });
  const mutation = useMutation({ mutationFn: () => api.put(`/expenses/claims/${review!.claim.id}/${review!.action}`, review!.action === "reimburse" ? { reimbursement_reference: reference.trim(), remarks: notes.trim() } : { status: reference, approved_amount: amount, remarks: notes.trim() }), onSuccess: () => { setReview(null); for (const key of ["expense-statement", "my-team", "employee-360"]) qc.invalidateQueries({ queryKey: [key] }); toast({ title: "Expense updated" }); }, onError: error => toast({ title: "Expense update failed", description: errorText(error), variant: "destructive" }) });
  const open = (claim: Claim, action: string) => { setReview({ claim, action }); setNotes(""); setAmount(claim.status === "submitted" ? claim.amount : claim.approved_amount); setReference(action === "manager-review" ? "manager_approved" : action === "finance-review" ? "finance_approved" : ""); };
  const download = () => {
    if (!statement.data) return;
    // Quote values and prevent user-entered text from becoming spreadsheet formulas.
    const quote = (value: unknown) => { const s = String(value ?? ""); return '"' + (/^[=+@\-\t\r]/.test(s) ? "'" + s : s).replace(/"/g, '""') + '"'; };
    const rows = [["Claim", "Date", "Category", "Currency", "Claimed", "Approved", "Status", "Payment reference"], ...statement.data.claims.map(c => [c.claim_number, c.expense_date, c.claim_type, c.currency, c.amount, c.approved_amount, c.status, c.reimbursement_reference || ""])];
    const url = URL.createObjectURL(new Blob([rows.map(r => r.map(quote).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8" })); const link = document.createElement("a"); link.href = url; link.download = `employee-${employee}-expenses.csv`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return <div className="space-y-5"><header><h1 className="text-2xl font-semibold">Employee expense statements</h1><p className="text-sm text-muted-foreground">Claims, final approvals, outstanding reimbursements and payments, separated by currency.</p></header>
    <div className="grid gap-4 rounded-lg border bg-card p-4 md:grid-cols-3"><EmployeeSearchSelect endpoint="/expenses/employees" value={employee} onChange={setEmployee} /><label className="text-sm">From date<Input type="date" value={dates.from_date} onChange={e => setDates({ ...dates, from_date: e.target.value })} /></label><label className="text-sm">To date<Input type="date" value={dates.to_date} onChange={e => setDates({ ...dates, to_date: e.target.value })} /></label></div>
    {!employee && <p className="text-sm text-muted-foreground">Select an employee to view their statement.</p>}
    {employee && statement.isPending && <p role="status">Loading expense statement…</p>}{statement.isError && <div role="alert"><p>Statement could not load. {errorText(statement.error)}</p><Button onClick={() => statement.refetch()}>Retry statement</Button></div>}
    {statement.data && !statement.isError && <><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold">{statement.data.employee_name}</h2><div className="flex gap-2"><Button variant="outline" onClick={() => statement.refetch()}>Refresh statement</Button><Button variant="outline" onClick={download}>Export statement</Button></div></div>
      {statement.data.can_submit && <ExpenseClaimForm key={`${user?.id}-${employee}`} employeeId={Number(employee)} />}
      <p className="text-xs text-muted-foreground">Approved means finance approved. Outstanding is the approved amount not yet paid; pending review and rejected amounts are separate.</p>
      {statement.data.totals.map(total => <dl key={total.currency} className="grid gap-3 rounded-lg border bg-card p-4 sm:grid-cols-2 lg:grid-cols-6">{[["Claimed", total.claimed], ["Approved", total.approved], ["Outstanding", total.outstanding], ["Paid", total.paid], ["Pending review", total.pending_review], ["Rejected", total.rejected]].map(([label, value]) => <div key={label}><dt className="text-xs text-muted-foreground">{label} · {total.currency}</dt><dd className="text-lg font-semibold">{formatCurrency(Number(value), total.currency)}</dd></div>)}</dl>)}
      <Card><CardHeader><CardTitle className="text-base">Claims</CardTitle></CardHeader><CardContent className="space-y-3"><label className="block text-sm">Claim status<select className="ml-2 rounded border bg-background p-2" value={status} onChange={e => setStatus(e.target.value)}><option value="all">All statuses</option>{[...new Set(statement.data.claims.map(c => c.status))].map(s => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}</select></label>
        {statement.data.claims.filter(c => status === "all" || c.status === status).map(c => <article key={c.id} className="space-y-2 rounded-lg border p-4"><div className="flex flex-wrap justify-between gap-3"><p className="font-medium">{c.claim_number} · {c.claim_type}</p><Badge variant="outline">{c.status.replace(/_/g, " ")}</Badge></div><p className="text-sm">{formatDate(c.expense_date)} · Claimed {formatCurrency(Number(c.amount), c.currency)} · Approved {formatCurrency(Number(c.approved_amount), c.currency)}</p>{c.remarks && <p className="break-words text-sm text-muted-foreground">Review notes: {c.remarks}</p>}{c.reimbursement_reference && <p className="break-all text-sm">Paid reference: {c.reimbursement_reference}</p>}{c.reimbursed_at && <p className="text-xs">Paid {formatDate(c.reimbursed_at)}</p>}{c.payroll_run_id && <Link className="text-sm underline" to="/hrms/payroll">Included in payroll run #{c.payroll_run_id}</Link>}
          {!!c.duplicate_receipt_claim_ids?.length && <p className="text-sm text-amber-700">Potential duplicate receipt on claim IDs {c.duplicate_receipt_claim_ids.join(", ")}. Review before approval.</p>}<div className="flex flex-wrap gap-2">{c.receipt_url && <Button size="sm" variant="outline" asChild><a href={assetUrl(c.receipt_url)} target="_blank" rel="noreferrer">View receipt</a></Button>}{c.status === "submitted" && statement.data.can_manager_review && <Button size="sm" variant="outline" onClick={() => open(c, "manager-review")}>Manager review</Button>}{c.status === "manager_approved" && statement.data.can_finance_review && <Button size="sm" variant="outline" onClick={() => open(c, "finance-review")}>Finance review</Button>}{c.status === "finance_approved" && !c.payroll_run_id && !c.payroll_reimbursement_id && statement.data.can_finance_review && <Button size="sm" variant="outline" onClick={() => open(c, "reimburse")}>Record payment</Button>}</div>
        </article>)}{!statement.data.claims.length && <p className="text-sm text-muted-foreground">No claims in this period.</p>}
      </CardContent></Card>
      {review && <Card><CardHeader><CardTitle className="text-base">{review.claim.claim_number} · {review.action.replace(/-/g, " ")}</CardTitle></CardHeader><CardContent><form className="space-y-3" onSubmit={e => { e.preventDefault(); mutation.mutate(); }}>{review.action === "reimburse" ? <label className="block text-sm">Bank / payment reference<Input required value={reference} onChange={e => setReference(e.target.value)} /></label> : <><label className="block text-sm">Decision<select className="ml-2 rounded border bg-background p-2" value={reference} onChange={e => setReference(e.target.value)}><option value={review.action === "manager-review" ? "manager_approved" : "finance_approved"}>Approve</option><option value="rejected">Reject</option></select></label><label className="block text-sm">Approved amount ({review.claim.currency})<Input required type="number" min="0" max={review.claim.amount} step="0.01" value={amount} onChange={e => setAmount(e.target.value)} /></label></>}
        <label className="block text-sm">Review notes / reason<Input required minLength={3} value={notes} onChange={e => setNotes(e.target.value)} /></label><div className="flex gap-2"><Button disabled={mutation.isPending || notes.trim().length < 3}>Save expense update</Button><Button type="button" variant="outline" disabled={mutation.isPending} onClick={() => setReview(null)}>Cancel</Button></div></form></CardContent></Card>}
    </>}
  </div>;
}
