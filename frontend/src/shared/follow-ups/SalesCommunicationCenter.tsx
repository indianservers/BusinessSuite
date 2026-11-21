import FollowUpSummary from "./FollowUpSummary";
import { useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { CalendarClock, History, MessageSquare, ShoppingBag, SlidersHorizontal } from "lucide-react";
import SendReminders from "@/apps/communication/center/SendReminders";
import MembershipExpiryPage from "@/shared/catalog/MembershipExpiryPage";
import { catalogError } from "@/shared/catalog/api";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { NativeSelect } from "@/components/ui/native-select";
import { Input } from "@/components/ui/input";
import { canAccessRoute } from "@/lib/roles";
import { useRecordScope } from "@/lib/record-scope";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";

const sections = [
  { id: "purchasers", label: "Purchasers", Icon: ShoppingBag },
  { id: "memberships", label: "Membership expiry", Icon: CalendarClock },
  { id: "subscriptions", label: "Subscription expiry", Icon: CalendarClock },
  { id: "follow-ups", label: "Scheduled follow-ups", Icon: MessageSquare },
] as const;
type Section = typeof sections[number]["id"];
const channels = { sms: "SMS", whatsapp: "WhatsApp", email: "Email" } as const;
type Channel = keyof typeof channels;
type Recipient = {
  id: number;
  name: string;
  last_purchase?: string;
  offerings: { id: number; name: string; kind: string }[];
  channels: Partial<Record<Channel, { available: boolean; reason?: string }>>;
};
type Audience = { items: Recipient[]; has_more: boolean };
type Filters = { kind: string; start: string; end: string; search: string };
const blankFilters: Filters = { kind: "", start: "", end: "", search: "" };
const audiencePath = "/srm/reporting/offering-audience";

export default function SalesCommunicationCenter() {
  const scope = useRecordScope();
  return <Center key={scope} scope={scope}/>;
}

function Center({ scope }: { scope: string }) {
  const user = useAuthStore(state => state.user);
  const [section, setSection] = useState<Section>("purchasers");
  return <section className="min-w-0 space-y-4" aria-labelledby="sales-communications-title">
    <div className="rounded-2xl border bg-card p-4 sm:p-6">
      <h1 id="sales-communications-title" className="text-xl font-semibold sm:text-2xl">Sales Communication Center</h1>
      <p className="mt-2 text-sm text-muted-foreground">Follow up with customers after a purchase and prepare renewal reminders before memberships or subscriptions expire.</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button asChild variant="outline"><Link to="/srm/follow-ups"><CalendarClock className="h-4 w-4"/>Follow-up queue</Link></Button>
        {canAccessRoute("/crm/delivery-logs", user?.role, user?.is_superuser) && <Button asChild variant="outline"><Link to="/crm/delivery-logs"><History className="h-4 w-4"/>Delivery history</Link></Button>}
      </div>
    </div>
    <nav aria-label="Sales communication sections" className="sales-communication-sections grid grid-cols-2 gap-2 lg:grid-cols-4">
      {sections.map(({ id, label, Icon }) => <Button key={id} type="button" variant={section === id ? "default" : "outline"}
        aria-pressed={section === id} className="h-auto min-h-11 justify-start whitespace-normal px-2 text-left sm:px-3" onClick={() => setSection(id)}>
        <Icon className="h-4 w-4 shrink-0" aria-hidden="true"/>{label}
      </Button>)}
    </nav>
    {section === "purchasers" && <Purchasers scope={scope}/>}
    {section === "memberships" && <MembershipExpiryPage source="srm" kind="membership" embedded/>}
    {section === "subscriptions" && <MembershipExpiryPage source="srm" kind="subscription" embedded/>}
    {section === "follow-ups" && <section className="space-y-3 rounded-xl border bg-card p-4" aria-label="Scheduled follow-ups">
      <FollowUpSummary base="/srm/follow-ups"/>
      {canAccessRoute("/crm/send-reminders", user?.role, user?.is_superuser) ? <SendReminders embedded/>
        : <p className="text-sm">Open the follow-up queue to review reminders in your Sales workspace.</p>}
    </section>}
  </section>;
}

function Purchasers({ scope }: { scope: string }) {
  const filterId = useId();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [draft, setDraft] = useState<Filters>(blankFilters);
  const [filters, setFilters] = useState<Filters>(blankFilters);
  const [page, setPage] = useState(1);
  const [recipient, setRecipient] = useState<{ row: Recipient; channel: Channel }>();
  const params = Object.fromEntries(Object.entries(filters).filter(([, value]) => value.trim()));
  const audience = useQuery({
    queryKey: ["sales-communication-audience", scope, filters, page],
    retry: false,
    queryFn: ({ signal }) => api.get<Audience>(audiencePath, { params: { ...params, page }, signal, recordCache: false }).then(result => result.data),
  });
  return <section aria-label="Purchasers" className="space-y-4 rounded-xl border bg-card p-4">
    <Button type="button" variant="outline" className="min-h-11 sm:hidden" aria-expanded={filtersOpen}
      aria-controls={filterId} onClick={() => setFiltersOpen(open => !open)}>
      <SlidersHorizontal className="h-4 w-4" aria-hidden="true"/>Purchaser filters
      {Object.keys(params).length > 0 && <span>({Object.keys(params).length})</span>}
    </Button>
    <form id={filterId} aria-label="Purchaser filters" className={`${filtersOpen ? "grid" : "hidden"} gap-3 sm:grid sm:grid-cols-2 lg:grid-cols-4`} onSubmit={event => {
      event.preventDefault();
      setRecipient(undefined);
      setPage(1);
      setFilters(draft);
      setFiltersOpen(false);
    }}>
      <label className="grid gap-1 text-sm">Offering type<NativeSelect value={draft.kind} onChange={event => setDraft({ ...draft, kind: event.target.value })}>
        <option value="">All offerings</option><option value="product">Products</option><option value="service">Services</option><option value="membership">Memberships</option><option value="subscription">Subscriptions</option>
      </NativeSelect></label>
      <label className="grid gap-1 text-sm">Customer name<Input value={draft.search} maxLength={100} onChange={event => setDraft({ ...draft, search: event.target.value })}/></label>
      <label className="grid gap-1 text-sm">Purchased from<Input type="date" max={draft.end || undefined} value={draft.start} onChange={event => setDraft({ ...draft, start: event.target.value })}/></label>
      <label className="grid gap-1 text-sm">Purchased through<Input type="date" min={draft.start || undefined} value={draft.end} onChange={event => setDraft({ ...draft, end: event.target.value })}/></label>
      <Button className="min-h-11 justify-self-start" type="submit">Find customers</Button>
    </form>
    {audience.isPending && <p role="status">Loading purchasers…</p>}
    {audience.isError && <div role="alert" className="space-y-2"><p>{catalogError(audience.error)}</p><Button type="button" variant="outline" onClick={() => void audience.refetch()}>Retry</Button></div>}
    {audience.data && (audience.data.items.length === 0 ? <p>No purchasers match these filters.</p> :
      <ul className="grid gap-2" aria-label="Purchasing customers">
        {audience.data.items.map(row => <li key={row.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3">
          <div className="min-w-0"><Link className="break-words font-semibold underline underline-offset-2" to={`/srm/customers/${row.id}/360`}>{row.name}</Link>
            {row.last_purchase && <p className="text-sm text-muted-foreground">Latest purchase {row.last_purchase}</p>}
            <p className="break-words text-sm text-muted-foreground">{row.offerings.map(offering => offering.name).join(", ")}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {(Object.keys(channels) as Channel[]).filter(channel => row.channels[channel]?.available).map(channel =>
              <Button key={channel} variant="outline" className="min-h-11" onClick={() => setRecipient({ row, channel })}>{channels[channel]}</Button>)}
            {!Object.values(row.channels).some(channel => channel?.available) &&
              <p className="text-xs text-muted-foreground">No eligible contact channel</p>}
          </div>
        </li>)}
      </ul>)}
    {audience.data && (page > 1 || audience.data.has_more) && <nav className="flex flex-wrap items-center gap-2" aria-label="Purchaser pages">
      <Button variant="outline" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</Button>
      <span>Page {page}</span>
      <Button variant="outline" disabled={!audience.data.has_more || page >= 10000} onClick={() => setPage(page + 1)}>Next</Button>
    </nav>}
    {recipient && <PurchaseDraft key={`${recipient.row.id}:${recipient.channel}`} scope={scope} {...recipient} params={params} close={() => setRecipient(undefined)}/>}
  </section>;
}

function PurchaseDraft({ scope, row, channel, params, close }: { scope: string; row: Recipient; channel: Channel; params: Record<string, string>; close: () => void }) {
  const [edited, setEdited] = useState<string>();
  const draft = useQuery({
    queryKey: ["purchase-message", scope, row.id, channel, params],
    gcTime: 0,
    retry: false,
    refetchOnWindowFocus: false,
    queryFn: ({ signal }) => api.post<{ compose_url: string; body: string }>(`${audiencePath}/preview`,
      { kind: params.kind, start: params.start, end: params.end, customer_id: row.id, channel }, { signal, readOnlyPreview: true }).then(result => result.data),
  });
  const label = channels[channel];
  const body = edited ?? draft.data?.body ?? "";
  const composeUrl = draft.data?.compose_url;
  const href = composeUrl && body.trim() && editComposeUrl(composeUrl, channel, body);
  return <Dialog open onOpenChange={open => { if (!open) close(); }}>
    <DialogContent className="max-sm:top-[calc(var(--mobile-viewport-height,100dvh)/2)] max-sm:max-h-[calc(var(--mobile-viewport-height,100dvh)-1rem)]">
      <DialogTitle>Prepare {label} follow-up</DialogTitle>
      <DialogDescription>Review the message for {row.name} before opening {label}.</DialogDescription>
      {draft.isFetching && <p role="status">Checking customer contact preferences…</p>}
      {draft.isError && <p role="alert">{catalogError(draft.error)}</p>}
      {draft.data && <>
        <label className="grid gap-2 text-sm">Message<textarea rows={4} maxLength={1000} value={body} onChange={event => setEdited(event.target.value)} className="rounded-md border bg-background p-3 text-base"/></label>
        {href ? <Button asChild><a href={href} target={channel === "whatsapp" ? "_blank" : undefined} rel={channel === "whatsapp" ? "noreferrer" : undefined}>Open {label} draft</a></Button>
          : <Button disabled>Open {label} draft</Button>}
      </>}
    </DialogContent>
  </Dialog>;
}


function editComposeUrl(value: string, channel: Channel, body: string) {
  try {
    const url = new URL(value);
    const allowed = channel === "sms" ? url.protocol === "sms:" :
      channel === "email" ? url.protocol === "mailto:" :
      url.origin === "https://wa.me";
    if (!allowed) return undefined;
    url.searchParams.set(channel === "whatsapp" ? "text" : "body", body);
    url.search = url.search.replace(/\+/g, "%20");
    return url.href;
  } catch {
    return undefined;
  }
}
