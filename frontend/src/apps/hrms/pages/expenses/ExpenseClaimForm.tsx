import {useMobile} from "@/components/mobile/useMobile";
import { useLocation } from "react-router-dom";
import RequestReviewContext from "../../components/RequestReviewContext";
import { announceCreated } from "@/shared/creation/CreationOutcome";
import "./expenses-mobile.css";
import { CurrencySelect } from "@/lib/validation/business";
import { defaultText, defaultNumber, defaultId, defaultOwner, defaultPaymentTerms, defaultDateAfter, formDefaults, displayDate, displayNumber } from "@/lib/form-defaults";
import { NativeSelect } from "@/components/ui/native-select";
import {SmartCreateSection} from "@/shared/creation/SmartCreateSection";
import CompactForm from "@/components/forms/CompactForm";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/hooks/use-toast";
export default function ExpenseClaimForm({ employeeId }: { employeeId: number }) {
  const phone=useMobile(480);
  const location=useLocation();
  const [completionRevision, setCompletionRevision] = useState(0);
  const userId = useAuthStore(s => s.user?.id), qc = useQueryClient();
  const draftKey = `hrms-expense-draft:${userId}:${employeeId}`;
  const empty = { claim_type: "Travel", expense_date: new Date().toLocaleDateString("en-CA"), amount: "", currency: defaultText("currency", "hrms"), description: "" };
  const [form, setForm] = useState(() => { try { return { ...empty, ...JSON.parse(sessionStorage.getItem(draftKey) || "{}").form }; } catch { return empty; } });
  const [pendingId, setPendingId] = useState<number | null>(() => { try { return JSON.parse(sessionStorage.getItem(draftKey) || "{}").pendingId || null; } catch { return null; } });
  const [file, setFile] = useState<File | null>(null);
  useEffect(() => { sessionStorage.setItem(draftKey, JSON.stringify({ form, pendingId })); }, [draftKey, form, pendingId]);
  const submit = useMutation({ mutationFn: async () => {
    if (file && (!/\.(pdf|png|jpe?g)$/i.test(file.name) || !file.size || file.size > 5 * 1024 * 1024)) throw new Error("Choose a non-empty PDF, PNG or JPEG receipt up to 5 MB.");
    const id = pendingId || (await api.post("/expenses/claims", { ...form, employee_id: employeeId })).data.id as number;
    setPendingId(id);
    if (file) {
      const body = new FormData(); body.append("file", file);
      const response = await api.post<{ duplicate_claim_ids: number[] }>(`/expenses/claims/${id}/receipt`, body, { headers: { "Content-Type": "multipart/form-data" } });
      if (response.data.duplicate_claim_ids.length) toast({ title: "Potential duplicate receipt", description: `This receipt also appears on claim IDs ${response.data.duplicate_claim_ids.join(", ")}. Ask the reviewer to check before payment.` });
    } else if (pendingId) throw new Error("Choose the receipt again to retry its upload.");
    return id;
  }, onSuccess: (id) => { announceCreated({ title: `Expense claim #${id} submitted`, status: "Awaiting manager review", href: `/hrms/expenses?employee_id=${employeeId}`, next: [{label:"Track claim",href:`/hrms/expenses?employee_id=${employeeId}`}] }); setCompletionRevision(value=>value+1); setForm(empty); setPendingId(null); setFile(null); sessionStorage.removeItem(draftKey); qc.invalidateQueries({ queryKey: ["expense-statement"] }); qc.invalidateQueries({ queryKey: ["my-team"] }); toast({ title: "Expense claim submitted" }); }, onError: (error: unknown) => { const detail = (error as { response?: { data?: { detail?: unknown } }; message?: string }).response?.data?.detail; toast({ title: "Expense submission needs attention", description: typeof detail === "string" ? detail : (error as Error).message || "Your entered values are preserved. Retry when ready.", variant: "destructive" }); } });
  const submissionDetail = (submit.error as {response?:{data?:{detail?:unknown}}}|null)?.response?.data?.detail;
  return <SmartCreateSection title="Submit expense claim" autoOpen={location.hash === "#new-record"} mobileSheet={phone} completionRevision={completionRevision} closeOnRecordSaved={false}><Card className="hrms-expense-claim-form"><CardHeader><CardTitle className="text-base">Submit an expense</CardTitle></CardHeader><CardContent><RequestReviewContext kind="expense" employeeId={employeeId}/><CompactForm className="grid gap-3 sm:grid-cols-2" onSubmit={e => { e.preventDefault(); if (!submit.isPending) submit.mutate(); }}>
    {submit.isError && <p role="alert" className="text-sm text-destructive sm:col-span-2">{typeof submissionDetail === "string" ? submissionDetail : "Could not submit this expense. Your entered values are retained."}</p>}
    {pendingId && <p role="status" className="text-sm sm:col-span-2">Claim #{pendingId} was created. Re-select its receipt and retry the upload; this will not create another claim.</p>}
    <label className="text-sm">Category<Input required disabled={!!pendingId} value={form.claim_type} onChange={e => setForm({ ...form, claim_type: e.target.value })} /></label><label className="text-sm">Expense date<Input required disabled={!!pendingId} type="date" max={new Date().toLocaleDateString("en-CA")} value={form.expense_date} onChange={e => setForm({ ...form, expense_date: e.target.value })} /></label>
    <label className="text-sm">Claim amount<Input required disabled={!!pendingId} type="number" min="0.01" step="0.01" value={form.amount} onChange={e => setForm({ ...form, amount: e.target.value })} /></label><label className="text-sm">Currency<CurrencySelect disabled={!!pendingId} value={form.currency} onChange={currency => setForm({ ...form, currency })}/></label>
    <label className="text-sm sm:col-span-2">Business purpose<Input required disabled={!!pendingId} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} /></label><label className="text-sm sm:col-span-2">Receipt (PDF, PNG or JPEG, up to 5 MB)<Input type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={e => setFile(e.target.files?.[0] || null)} /></label>
    <p className="text-xs text-muted-foreground sm:col-span-2">Text drafts are saved in this browser session. Selected receipt files must be chosen again after a reload.</p><Button data-save-action={phone?"":undefined} disabled={submit.isPending || (!!pendingId && !file)}>{submit.isPending ? "Submitting…" : pendingId ? "Retry receipt upload" : "Submit expense claim"}</Button>
  </CompactForm></CardContent></Card></SmartCreateSection>;
}
