import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/hooks/use-toast";
export default function ExpenseClaimForm({ employeeId }: { employeeId: number }) {
  const userId = useAuthStore(s => s.user?.id), qc = useQueryClient();
  const draftKey = `hrms-expense-draft:${userId}:${employeeId}`;
  const empty = { claim_type: "Travel", expense_date: new Date().toLocaleDateString("en-CA"), amount: "", currency: "INR", description: "" };
  const [form, setForm] = useState(() => { try { return { ...empty, ...JSON.parse(sessionStorage.getItem(draftKey) || "{}").form }; } catch { return empty; } });
  const [pendingId, setPendingId] = useState<number | null>(() => { try { return JSON.parse(sessionStorage.getItem(draftKey) || "{}").pendingId || null; } catch { return null; } });
  const [file, setFile] = useState<File | null>(null);
  useEffect(() => { sessionStorage.setItem(draftKey, JSON.stringify({ form, pendingId })); }, [draftKey, form, pendingId]);
  const submit = useMutation({ mutationFn: async () => {
    const id = pendingId || (await api.post("/expenses/claims", { ...form, employee_id: employeeId })).data.id as number;
    setPendingId(id);
    if (file) {
      const body = new FormData(); body.append("file", file);
      const response = await api.post<{ duplicate_claim_ids: number[] }>(`/expenses/claims/${id}/receipt`, body, { headers: { "Content-Type": "multipart/form-data" } });
      if (response.data.duplicate_claim_ids.length) toast({ title: "Potential duplicate receipt", description: `This receipt also appears on claim IDs ${response.data.duplicate_claim_ids.join(", ")}. Ask the reviewer to check before payment.` });
    } else if (pendingId) throw new Error("Choose the receipt again to retry its upload.");
  }, onSuccess: () => { setForm(empty); setPendingId(null); setFile(null); sessionStorage.removeItem(draftKey); qc.invalidateQueries({ queryKey: ["expense-statement"] }); qc.invalidateQueries({ queryKey: ["my-team"] }); toast({ title: "Expense claim submitted" }); }, onError: (error: unknown) => { const detail = (error as { response?: { data?: { detail?: unknown } }; message?: string }).response?.data?.detail; toast({ title: "Expense submission needs attention", description: typeof detail === "string" ? detail : (error as Error).message || "Your entered values are preserved. Retry when ready.", variant: "destructive" }); } });
  return <Card><CardHeader><CardTitle className="text-base">Submit an expense</CardTitle></CardHeader><CardContent><form className="grid gap-3 sm:grid-cols-2" onSubmit={e => { e.preventDefault(); submit.mutate(); }}>
    {pendingId && <p role="status" className="text-sm sm:col-span-2">Claim #{pendingId} was created. Re-select its receipt and retry the upload; this will not create another claim.</p>}
    <label className="text-sm">Category<Input required disabled={!!pendingId} value={form.claim_type} onChange={e => setForm({ ...form, claim_type: e.target.value })} /></label><label className="text-sm">Expense date<Input required disabled={!!pendingId} type="date" max={new Date().toLocaleDateString("en-CA")} value={form.expense_date} onChange={e => setForm({ ...form, expense_date: e.target.value })} /></label>
    <label className="text-sm">Claim amount<Input required disabled={!!pendingId} type="number" min="0.01" step="0.01" value={form.amount} onChange={e => setForm({ ...form, amount: e.target.value })} /></label><label className="text-sm">Currency<select className="mt-1 h-10 w-full rounded border bg-background px-2" disabled={!!pendingId} value={form.currency} onChange={e => setForm({ ...form, currency: e.target.value })}>{["INR", "USD", "AED", "EUR", "GBP"].map(c => <option key={c}>{c}</option>)}</select></label>
    <label className="text-sm sm:col-span-2">Business purpose<Input required disabled={!!pendingId} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} /></label><label className="text-sm sm:col-span-2">Receipt (PDF, PNG or JPEG, up to 5 MB)<Input type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={e => setFile(e.target.files?.[0] || null)} /></label>
    <p className="text-xs text-muted-foreground sm:col-span-2">Text drafts are saved in this browser session. Selected receipt files must be chosen again after a reload.</p><Button disabled={submit.isPending || (!!pendingId && !file)}>{submit.isPending ? "Submitting…" : pendingId ? "Retry receipt upload" : "Submit expense claim"}</Button>
  </form></CardContent></Card>;
}
