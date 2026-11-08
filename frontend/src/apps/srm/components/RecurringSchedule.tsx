import { useState, type FormEvent } from "react";
import { isAxiosError } from "axios";
import { useMutation, useQuery } from "@tanstack/react-query";
import { srmApi } from "../api";
import type { SRMRecord } from "../types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";

export default function RecurringSchedule({ plans, onSaved }: { plans: SRMRecord[]; onSaved: () => void }) {
  const [plan, setPlan] = useState("");
  const [start, setStart] = useState("");
  const [amount, setAmount] = useState("");
  const [count, setCount] = useState("12");
  const [terms, setTerms] = useState("30");
  const [automatic, setAutomatic] = useState(false);
  const [notify, setNotify] = useState(true);
  const [ongoing, setOngoing] = useState(false);
  const [interval, setRepeatInterval] = useState("1");
  const [subject, setSubject] = useState("");
  const [notes, setNotes] = useState("");
  const [conditions, setConditions] = useState("");
  const [end, setEnd] = useState("");
  const [template, setTemplate] = useState<"standard" | "compact" | "detailed">("standard");
  const [paymentMode, setPaymentMode] = useState("");
  const [salesperson, setSalesperson] = useState("");
  const [orderNumber, setOrderNumber] = useState("");
  const options = useQuery({ queryKey: ["srm", "recurringInvoiceOptions"], queryFn: srmApi.recurringInvoiceOptions });
  const [message, setMessage] = useState("");
  const eligible = plans.filter(p => p.recurrence_rule && !["completed", "cancelled"].includes(String(p.status)));
  const mutation = useMutation({
    mutationFn: () => srmApi.createRecurringSchedule(Number(plan), { start_date: start, amount, occurrences: Number(count), payment_terms_days: Number(terms), automatic_drafts: automatic, notify_on_creation: notify, never_expires: ongoing, interval: Number(interval), end_date: ongoing ? undefined : end || undefined, invoice_template: template, payment_mode_id: paymentMode ? Number(paymentMode) : undefined, salesperson_id: salesperson ? Number(salesperson) : undefined, order_number: orderNumber, subject, customer_notes: notes, terms: conditions }),
    onSuccess: result => { setMessage(`${result.created} occurrences created; ${result.skipped} existing dates skipped. ${result.created === 0 ? "Existing occurrences were preserved." : automatic ? "Due occurrences will become invoice drafts while the plan is active." : "Approve milestones before invoicing."}`); onSaved(); },
    onError: error => setMessage(isAxiosError(error) && typeof error.response?.data?.detail === "string" ? error.response.data.detail : "Schedule could not be created. Check the plan's recurrence, dates, amount, and your permissions."),
  });
  function submit(event: FormEvent) { event.preventDefault(); setMessage(""); mutation.mutate(); }
  return <details className="rounded-lg border p-4"><summary className="cursor-pointer font-medium">Recurring billing schedule</summary>
    <p className="my-3 text-sm text-muted-foreground">Create dated milestones in an existing recurring plan. Existing dates are skipped. Automatic drafts require an active plan; invoices retain the usual approval process.</p>
    <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      <label className="text-sm">Billing plan<NativeSelect className="block h-10 w-full rounded-md border bg-background px-3" required value={plan} onChange={e => setPlan(e.target.value)}><option value="">Select recurring plan</option>{eligible.map(p => <option key={String(p.id)} value={String(p.id)}>{String(p.name)} · {String(p.recurrence_rule)}</option>)}</NativeSelect></label>
      <label className="text-sm">First billing date<Input required type="date" value={start} onChange={e => setStart(e.target.value)}/></label>
      <label className="text-sm">Repeat interval<Input required type="number" min="1" max="120" step="1" value={interval} onChange={e => setRepeatInterval(e.target.value)} title="Use 2 with a monthly plan to repeat every two months."/></label>
      <label className="text-sm">End date (optional)<Input type="date" min={start} disabled={ongoing} value={end} onChange={e => setEnd(e.target.value)}/></label>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={ongoing} onChange={e => setOngoing(e.target.checked)}/>Never expires</label>
      <label className="text-sm">PDF template<NativeSelect className="block h-10 w-full rounded-md border bg-background px-3" value={template} onChange={e => setTemplate(e.target.value as typeof template)}><option value="standard">Standard</option><option value="compact">Compact</option><option value="detailed">Detailed</option></NativeSelect></label>
      <label className="text-sm">Expected payment mode<NativeSelect className="block h-10 w-full rounded-md border bg-background px-3" value={paymentMode} onChange={e => setPaymentMode(e.target.value)}><option value="">Company default</option>{options.data?.payment_modes.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</NativeSelect></label>
      <label className="text-sm">Salesperson<NativeSelect className="block h-10 w-full rounded-md border bg-background px-3" value={salesperson} onChange={e => setSalesperson(e.target.value)}><option value="">Not assigned</option>{options.data?.users.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</NativeSelect></label>
      <label className="text-sm">Order number<Input maxLength={80} value={orderNumber} onChange={e => setOrderNumber(e.target.value)}/></label>
      <label className="text-sm">Amount per occurrence<Input required type="number" min="0.01" step="0.01" value={amount} onChange={e => setAmount(e.target.value)}/></label>
      <label className="text-sm">{ongoing ? "Initial occurrences" : "Occurrences"}<Input required type="number" min="1" max="120" step="1" value={count} onChange={e => setCount(e.target.value)}/></label>
      <label className="text-sm">Payment terms (days)<Input required type="number" min="0" max="365" step="1" value={terms} onChange={e => setTerms(e.target.value)}/></label>
      <label className="text-sm">Subject<Input maxLength={180} value={subject} onChange={e => setSubject(e.target.value)}/></label>
      <label className="text-sm">Customer notes<textarea className="w-full rounded border p-2" maxLength={4000} value={notes} onChange={e => setNotes(e.target.value)}/></label>
      <label className="text-sm">Terms and conditions<textarea className="w-full rounded border p-2" maxLength={4000} value={conditions} onChange={e => setConditions(e.target.value)}/></label>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={automatic} onChange={e => setAutomatic(e.target.checked)}/>Create invoice drafts automatically when due</label>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={notify} onChange={e => setNotify(e.target.checked)}/>Notify me in the app when a draft is created</label>
      <Button className="self-end" disabled={mutation.isPending || !plan} type="submit">{mutation.isPending ? "Creating…" : "Create schedule"}</Button>
    </form><p role="status" className="mt-3 text-sm">{message}</p>
  </details>;
}
