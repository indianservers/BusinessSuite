import { useMutation, useQuery } from "@tanstack/react-query";
import { CalendarClock } from "lucide-react";
import { lazy, Suspense, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { api } from "@/services/api";
import { useRecordScope } from "@/lib/record-scope";
import { useRecordScopeOwner } from "@/hooks/use-record-scope-owner";
import { canAccessRoute } from "@/lib/roles";
import { useAuthStore } from "@/store/authStore";
import { catalogError } from "./api";
import "./catalog.css";
import "./membership-expiry.css";

type Source = "crm" | "srm";
type Period = "two_weeks" | "two_months" | "custom";
type Action = "sms" | "whatsapp" | "reminder";
type Expiry = { id: number; customer_id: number; customer: string; membership: string; number: string; expiry: string; status: string; has_phone: boolean };
type Report = { start: string; end: string; today: string; has_more: boolean; can_remind: boolean; items: Expiry[] };
const path = "/customer-plans/expiry-report";
const WhatsAppCloudPanel = lazy(() => import("@/apps/communication/WhatsAppCloudPanel"));
const periods = [
  { id: "two_weeks", label: "Next 2 weeks" },
  { id: "two_months", label: "Next 2 months" },
  { id: "custom", label: "Custom range" },
] as const;

export default function MembershipExpiryPage({ source }: { source: Source }) {
  const scope = useRecordScope();
  return <ExpiryReport key={scope} scope={scope} source={source}/>;
}

function ExpiryReport({ source, scope }: { source: Source; scope: string }) {
  const [period, setPeriod] = useState<Period>("two_weeks");
  const [range, setRange] = useState({ start: "", end: "" });
  const [values, setValues] = useState(range);
  const [page, setPage] = useState(1);
  const [action, setAction] = useState<{ row: Expiry; type: Action }>();
  const query = useQuery({
    queryKey: ["membership-expiry", scope, source, period, range, page],
    enabled: period !== "custom" || !!range.start && !!range.end,
    retry: false,
    queryFn: ({ signal }) => api.get<Report>(path, {
      params: { source, period, page, ...(period === "custom" ? range : {}) },
      recordCache: false, signal,
    }).then(result => result.data),
  });
  const report = query.data;

  return <main className="sc-page expiry-report space-y-4">
    <header className="sc-hero">
      <div><h1>Membership Expiry Report<span><CalendarClock size={23}/></span></h1><p>Review expiring memberships and follow up with customers.</p></div>
      <Button asChild variant="outline" className="min-h-11"><Link to={source === "crm" ? "/crm/reminders" : "/srm/send-reminders"}>Reminders</Link></Button>
    </header>
    <div className="sc-catalog-bar"><div className="sc-tabs" role="group" aria-label="Expiry period">
      {periods.map(option => <button key={option.id} type="button" aria-pressed={option.id === period} onClick={() => {
        if (option.id === "custom" && !values.start && report) {
          setValues({ start: report.start, end: report.end });
          setRange({ start: report.start, end: report.end });
        }
        setPeriod(option.id);
        setPage(1);
      }}>{option.label}</button>)}
    </div></div>
    {period === "custom" && <form className="expiry-range flex flex-wrap items-end gap-3" onSubmit={event => {
      event.preventDefault();
      if (values.start > values.end) return;
      setRange(values); setPage(1);
    }}>
      <label className="grid min-w-0 gap-1 text-sm">Expiry from<Input className="min-h-11 w-full min-w-0 text-base" type="date" required max={values.end || undefined} value={values.start} onChange={event => setValues(current => ({ ...current, start: event.target.value }))}/></label>
      <label className="grid min-w-0 gap-1 text-sm">Expiry to<Input className="min-h-11 w-full min-w-0 text-base" type="date" required min={values.start || undefined} value={values.end} onChange={event => setValues(current => ({ ...current, end: event.target.value }))}/></label>
      <Button className="min-h-11" type="submit">Apply dates</Button>
      {values.start && values.end && values.start > values.end && <p className="text-sm text-destructive" role="alert">The end date must be on or after the start date.</p>}
    </form>}
    {query.isFetching && <p role="status">Loading memberships…</p>}
    {query.isError && <div role="alert"><p>{catalogError(query.error)}</p><Button variant="outline" onClick={() => void query.refetch()}>Retry</Button></div>}
    {report && <>
      <p className="text-sm text-muted-foreground">{report.start} to {report.end}, inclusive</p>
      {report.items.length === 0 ? <p>No memberships expire in this date range.</p> : <div className="overflow-x-auto rounded-lg border bg-card">
        <table role="table" className="expiry-results w-full text-left text-sm">
          <caption className="sr-only">Memberships by expiry date</caption>
          <thead role="rowgroup"><tr role="row" className="border-b bg-muted/50">
            {["Customer", "Membership", "Expiry date", "Status", "Actions"].map(label => <th key={label} role="columnheader" scope="col" className="px-3 py-2">{label}</th>)}
          </tr></thead>
          <tbody role="rowgroup">{report.items.map(row => <tr key={row.id} role="row" className="border-b last:border-0">
            <th role="rowheader" scope="row" className="px-3 py-2 font-medium"><Link className="underline underline-offset-2" to={`/${source}/customers/${row.customer_id}/360`}>{row.customer}</Link></th>
            <td role="cell" className="px-3 py-2">{row.membership}<small className="block text-muted-foreground">{row.number}</small></td>
            <td role="cell" className="whitespace-nowrap px-3 py-2"><span className="md:hidden">Expires </span>{row.expiry}</td>
            <td role="cell" className="px-3 py-2 capitalize">{row.status}</td>
            <td role="cell" className="expiry-actions px-3 py-2"><div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" className="max-md:min-h-11" disabled={!row.has_phone} onClick={() => setAction({ row, type: "sms" })}>SMS</Button>
              <Button variant="outline" size="sm" className="max-md:min-h-11" disabled={!row.has_phone} onClick={() => setAction({ row, type: "whatsapp" })}>WhatsApp</Button>
              {report.can_remind && row.expiry >= report.today && <Button variant="outline" size="sm" className="max-md:min-h-11" onClick={() => setAction({ row, type: "reminder" })}>Set reminder</Button>}
            </div></td>
          </tr>)}</tbody>
        </table>
      </div>}
      {(page > 1 || report.has_more) && <nav className="flex items-center gap-3" aria-label="Membership report pages">
        <Button variant="outline" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</Button>
        <span>Page {page}</span>
        <Button variant="outline" disabled={!report.has_more || page >= 10000} onClick={() => setPage(page + 1)}>Next</Button>
      </nav>}
    </>}
    {action && <ExpiryAction row={action.row} type={action.type} source={source} close={() => setAction(undefined)}/>}
  </main>;
}

function ExpiryAction({ row, type, source, close }: { row: Expiry; type: Action; source: Source; close: () => void }) {
  const owns = useRecordScopeOwner();
  const user = useAuthStore(state => state.user);
  const [lead, setLead] = useState(14);
  const [draft, setDraft] = useState<string>();
  const [connected, setConnected] = useState(false);
  const reminder = useMutation({
    mutationFn: () => api.post<{ id: number; remind_at: string }>(`${path}/${row.id}/reminder`, { lead_days: lead }, { params: { source } }).then(result => result.data),
  });
  const message = useQuery({
    queryKey: ["expiry-message", useRecordScope(), source, row.id, type],
    enabled: type !== "reminder",
    retry: false,
    queryFn: ({ signal }) => api.post<{ destination: string; body: string }>(`${path}/${row.id}/message`, { channel: type }, {
      params: { source }, readOnlyPreview: true, signal,
    }).then(result => result.data),
  });
  const body = draft ?? message.data?.body ?? "";
  const number = message.data?.destination;
  const channel = type === "sms" ? "SMS" : "WhatsApp";
  const messageHref = number && (type === "sms" ? `sms:${number}?body=${encodeURIComponent(body)}` : `https://wa.me/${number.replace(/\D/g, "")}?text=${encodeURIComponent(body)}`);
  return <Dialog open onOpenChange={open => { if (!open && !reminder.isPending) close(); }}>
    <DialogContent className={`w-[calc(100%-1.5rem)] max-h-[calc(100dvh-1.5rem)] overflow-y-auto rounded-lg ${connected ? "max-w-5xl" : ""}`}>
      <DialogTitle>{type === "reminder" ? "Set expiry reminder" : `${channel} renewal message`}</DialogTitle>
      <DialogDescription>{row.customer} / {row.membership} / {row.expiry}</DialogDescription>
      {type === "reminder" ? <form className="space-y-3" onSubmit={event => { event.preventDefault(); if (owns()) reminder.mutate(); }}>
        <label className="grid gap-1">Days before expiry<Input type="number" required min={0} max={365} value={lead} onChange={event => setLead(Number(event.target.value))}/></label>
        <p className="text-sm text-muted-foreground">The follow-up scheduler sends an in-app reminder to you. If the reminder date has passed, it is picked up on the next run.</p>
        {reminder.isError && <p role="alert">{catalogError(reminder.error)}</p>}
        {reminder.data ? <div className="space-y-2">
          <p role="status">Reminder saved for {new Date(reminder.data.remind_at).toLocaleString()}.</p>
          <Button asChild variant="outline"><Link to={`/${source}/follow-ups/${reminder.data.id}`}>View saved reminder</Link></Button>
        </div>
          : <Button type="submit" disabled={reminder.isPending}>Save reminder</Button>}
      </form> : <>
        {message.isFetching && <p role="status">Checking customer contact details…</p>}
        {message.isError && <p role="alert">{catalogError(message.error)}</p>}
        {message.data && connected && number && !message.isError ? <Suspense fallback={<p role="status">Loading WhatsApp composer…</p>}>
          <WhatsAppCloudPanel embedded initialDraft={{key: `membership-expiry:${row.id}`, to: number, body}}/>
        </Suspense> : message.data && <>
          <label className="grid gap-1">Message<textarea className="w-full rounded border bg-background p-2 text-base" value={body} rows={4} maxLength={1000} onChange={event => setDraft(event.target.value)}/></label>
          <p className="text-sm text-muted-foreground">Review and send to {number} in your messaging app.</p>
          {messageHref && body.trim() && !message.isError && !message.isFetching && <div className="flex flex-wrap gap-2">
            <Button asChild className="min-h-11 max-sm:w-full"><a href={messageHref} target={type === "whatsapp" ? "_blank" : undefined} rel="noopener noreferrer">Open {channel}</a></Button>
            {type === "whatsapp" && canAccessRoute("/crm/whatsapp", user?.role, user?.is_superuser) &&
              <Button className="min-h-11 max-sm:w-full" variant="outline" onClick={() => setConnected(true)}>Use connected WhatsApp</Button>}
          </div>}
        </>}
      </>}
    </DialogContent>
  </Dialog>;
}
