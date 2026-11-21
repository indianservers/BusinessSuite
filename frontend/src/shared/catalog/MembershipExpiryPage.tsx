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

type Kind = "membership" | "subscription";
type Source = "crm" | "srm";
type Period = "two_weeks" | "two_months" | "custom";
type Action = "sms" | "whatsapp" | "reminder";
type Expiry = { id: number; customer_id: number; customer: string; membership?: string; subscription?: string; number: string; expiry: string; status: string; has_phone: boolean };
type Report = { start: string; end: string; today: string; has_more: boolean; can_remind: boolean; items: Expiry[] };
const path = "/customer-plans/expiry-report";
const WhatsAppCloudPanel = lazy(() => import("@/apps/communication/WhatsAppCloudPanel"));
const periods = [
  { id: "two_weeks", label: "Next 2 weeks" },
  { id: "two_months", label: "Next 2 months" },
  { id: "custom", label: "Custom range" },
] as const;

export default function MembershipExpiryPage({ source, kind = "membership", embedded = false }: { source: Source; kind?: Kind; embedded?: boolean }) {
  const scope = useRecordScope();
  return <ExpiryReport key={`${scope}:${kind}`} scope={scope} source={source} kind={kind} embedded={embedded}/>;
}

function ExpiryReport({ source, scope, kind, embedded }: { source: Source; scope: string; kind: Kind; embedded: boolean }) {
  const label = kind === "membership" ? "Membership" : "Subscription";
  const [period, setPeriod] = useState<Period>("two_weeks");
  const [range, setRange] = useState({ start: "", end: "" });
  const [values, setValues] = useState(range);
  const [page, setPage] = useState(1);
  const [action, setAction] = useState<{ row: Expiry; type: Action }>();
  const query = useQuery({
    queryKey: ["membership-expiry", scope, source, kind, period, range, page],
    enabled: period !== "custom" || !!range.start && !!range.end,
    retry: false,
    queryFn: ({ signal }) => api.get<Report>(path, {
      params: { source, kind, period, page, ...(period === "custom" ? range : {}) },
      recordCache: false, signal,
    }).then(result => result.data),
  });
  const report = query.data;
  const actionsFor = (row: Expiry) => <div className="flex flex-wrap gap-2">
    <Button variant="outline" size="sm" disabled={!row.has_phone} onClick={() => setAction({ row, type: "sms" })}>SMS</Button>
    <Button variant="outline" size="sm" disabled={!row.has_phone} onClick={() => setAction({ row, type: "whatsapp" })}>WhatsApp</Button>
    {report?.can_remind && row.expiry >= report.today && <Button variant="outline" size="sm" onClick={() => setAction({ row, type: "reminder" })}>Set reminder</Button>}
  </div>;

  return <section className="sc-page space-y-4" aria-label={`${label} expiry`}>
    {!embedded && <header className="sc-hero">
      <div><h1>{label} Expiry Report<span><CalendarClock size={23}/></span></h1><p>Review expiring {label.toLowerCase()}s and follow up with customers.</p></div>
      <Button asChild variant="outline"><Link to={source === "crm" ? "/crm/reminders" : "/srm/send-reminders"}>Reminders</Link></Button>
    </header>}
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
    {period === "custom" && <form className="flex flex-wrap items-end gap-3" onSubmit={event => {
      event.preventDefault(); setRange(values); setPage(1);
    }}>
      <label className="grid gap-1 text-sm">Expiry from<Input type="date" required max={values.end || undefined} value={values.start} onChange={event => setValues({ ...values, start: event.target.value })}/></label>
      <label className="grid gap-1 text-sm">Expiry to<Input type="date" required min={values.start || undefined} value={values.end} onChange={event => setValues({ ...values, end: event.target.value })}/></label>
      <Button type="submit">Apply dates</Button>
    </form>}
    {query.isFetching && <p role="status">Loading {label.toLowerCase()}s…</p>}
    {query.isError && <div role="alert"><p>{catalogError(query.error)}</p><Button variant="outline" onClick={() => void query.refetch()}>Retry</Button></div>}
    {report && <>
      <p className="text-sm text-muted-foreground">{report.start} to {report.end}, inclusive</p>
      {report.items.length === 0 ? <p>No {label.toLowerCase()}s expire in this date range.</p> : <>
      {embedded && <ul className="grid gap-2 sm:hidden" aria-label={`Expiring ${label.toLowerCase()}s`}>
        {report.items.map(row => <li key={row.id} className="space-y-2 rounded-lg border bg-card p-3">
          <Link className="break-words font-semibold underline underline-offset-2" to={`/${source}/customers/${row.customer_id}/360`}>{row.customer}</Link>
          <p className="break-words text-sm">{row.subscription ?? row.membership}</p>
          <p className="text-sm text-muted-foreground">Expires <time dateTime={row.expiry}>{row.expiry}</time> · <span className="capitalize">{row.status}</span></p>
          {actionsFor(row)}
        </li>)}
      </ul>}
      <div className={`overflow-x-auto rounded-lg border bg-card ${embedded ? "hidden sm:block" : ""}`}>
        <table className="w-full text-left text-sm">
          <caption className="sr-only">{label}s by expiry date</caption>
          <thead><tr className="border-b bg-muted/50">
            {["Customer", label, "Expiry date", "Status", "Actions"].map(label => <th key={label} scope="col" className="px-3 py-2">{label}</th>)}
          </tr></thead>
          <tbody>{report.items.map(row => <tr key={row.id} className="border-b last:border-0">
            <th scope="row" className="px-3 py-2 font-medium"><Link className="underline underline-offset-2" to={`/${source}/customers/${row.customer_id}/360`}>{row.customer}</Link></th>
            <td className="px-3 py-2">{row.subscription ?? row.membership}<small className="block text-muted-foreground">{row.number}</small></td>
            <td className="whitespace-nowrap px-3 py-2">{row.expiry}</td>
            <td className="px-3 py-2 capitalize">{row.status}</td>
            <td className="px-3 py-2">{actionsFor(row)}</td>
          </tr>)}</tbody>
        </table>
      </div></>}
      {(page > 1 || report.has_more) && <nav className="flex items-center gap-3" aria-label={`${label} report pages`}>
        <Button variant="outline" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</Button>
        <span>Page {page}</span>
        <Button variant="outline" disabled={!report.has_more || page >= 10000} onClick={() => setPage(page + 1)}>Next</Button>
      </nav>}
    </>}
    {action && <ExpiryAction row={action.row} type={action.type} source={source} kind={kind} close={() => setAction(undefined)}/>}
  </section>;
}

function ExpiryAction({ row, type, source, kind, close }: { row: Expiry; type: Action; source: Source; kind: Kind; close: () => void }) {
  const owns = useRecordScopeOwner();
  const user = useAuthStore(state => state.user);
  const [lead, setLead] = useState(14);
  const [draft, setDraft] = useState<string>();
  const [connected, setConnected] = useState(false);
  const reminder = useMutation({
    mutationFn: () => api.post<{ id: number; remind_at: string }>(`${path}/${row.id}/reminder`, { lead_days: lead }, { params: { source, kind } }).then(result => result.data),
  });
  const message = useQuery({
    queryKey: ["expiry-message", useRecordScope(), source, kind, row.id, type],
    enabled: type !== "reminder",
    retry: false,
    queryFn: ({ signal }) => api.post<{ destination: string; body: string }>(`${path}/${row.id}/message`, { channel: type }, {
      params: { source, kind }, readOnlyPreview: true, signal,
    }).then(result => result.data),
  });
  const body = draft ?? message.data?.body ?? "";
  const number = message.data?.destination;
  const channel = type === "sms" ? "SMS" : "WhatsApp";
  const messageHref = number && (type === "sms" ? `sms:${number}?body=${encodeURIComponent(body)}` : `https://wa.me/${number.replace(/\D/g, "")}?text=${encodeURIComponent(body)}`);
  return <Dialog open onOpenChange={open => { if (!open && !reminder.isPending) close(); }}>
    <DialogContent className={connected ? "max-h-[calc(100dvh-2rem)] max-w-5xl overflow-y-auto" : undefined}>
      <DialogTitle>{type === "reminder" ? "Set expiry reminder" : `${channel} renewal message`}</DialogTitle>
      <DialogDescription>{row.customer} / {row.subscription ?? row.membership} / {row.expiry}</DialogDescription>
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
          <WhatsAppCloudPanel embedded initialDraft={{key: `${kind}-expiry:${row.id}`, to: number, body}}/>
        </Suspense> : message.data && <>
          <label className="grid gap-1">Message<textarea className="rounded border bg-background p-2" value={body} rows={4} maxLength={1000} onChange={event => setDraft(event.target.value)}/></label>
          <p className="text-sm text-muted-foreground">Review and send to {number} in your messaging app.</p>
          {messageHref && body.trim() && !message.isError && !message.isFetching && <div className="flex flex-wrap gap-2">
            <Button asChild><a href={messageHref} target={type === "whatsapp" ? "_blank" : undefined} rel="noopener noreferrer">Open {channel}</a></Button>
            {type === "whatsapp" && canAccessRoute("/crm/whatsapp", user?.role, user?.is_superuser) &&
              <Button variant="outline" onClick={() => setConnected(true)}>Use connected WhatsApp</Button>}
          </div>}
        </>}
      </>}
    </DialogContent>
  </Dialog>;
}
