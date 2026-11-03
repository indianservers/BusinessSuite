import { openRecordPreview } from "@/components/RecordQuickPreview";
import { Eye } from "lucide-react";
import { WhatsAppIcon } from "@/components/actions/BrandIcons";
import { RecordMessageDraft, whatsappNumber, communicationBlocked } from "@/shared/records/RecordWorkspace";
import CompactActions from "@/components/actions/CompactActions";
import { useEffect, useMemo, useRef, useState } from "react";

import { useQuery, useQueryClient } from "@tanstack/react-query";

import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { Building2, CalendarClock, CalendarDays, Gift, Mail, Package, Phone, Plus, RefreshCw, Users, X } from "lucide-react";

import { api } from "@/services/api";

import { Button } from "@/components/ui/button";

import { Input } from "@/components/ui/input";

import { NativeSelect } from "@/components/ui/native-select";

import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";

import { SharedDataGrid, type GridColumn, type GridDataSource, type GridResult } from "@/shared/data-grid";

import { useAuthStore } from "@/store/authStore";

import { useDebounced } from "@/shared/catalog/api";

import { ProductPicker, type GrowthRecord } from "./GrowthWorkspace";

import "./follow-up-workspace.css";



type Relationship = GrowthRecord & { owner_id?: number; owner_name?: string; priority?: string; last_contact?: string };

type Listing = { can_export?: boolean; items: Relationship[]; total: number; counts: Record<string, number>; buckets: Record<string, number> };

type Owner = { id: number; name: string; email: string };

type Pending = { id: number; title: string; due_at: string; channel: string; notes?: string; priority?: string; owner_id?: number; version?: string; metadata?: { next_action?: string; reminder_at?: string; offering_kind?: string; offering_id?: number } };

type Timeline = { id?: number; type: string; title: string; occurredAt?: string; record?: { body?: string; description?: string; outcome?: string } };

const root = "/crm/growth";

const labels: Record<string, string> = { all: "All records", leads: "Leads", contacts: "Contacts", companies: "Customers / companies", deals: "Deals" };

const failure = (error: unknown) => { const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail; return typeof detail === "string" ? detail : "Unable to complete this request. Please try again."; };

const date = (value?: string) => value ? new Date(value).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "No follow-up scheduled";

const localInput = (value: string | Date) => { const d = new Date(value); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16); };

const initials = (name: string) => name.split(/[\s@.]+/).filter(Boolean).slice(0, 2).map(part => part[0]).join("").toUpperCase();

function Due({ value }: { value?: string }) { return <span className={`fu-due ${!value ? "missing" : new Date(value) < new Date() ? "overdue" : "planned"}`}><CalendarDays size={13} />{date(value)}</span>; }



export default function FollowUpWorkspace() {

  const [mobile, setMobile] = useState(() => window.matchMedia("(max-width: 640px)").matches);
  useEffect(() => { const media = window.matchMedia("(max-width: 640px)"); const change = () => setMobile(media.matches); media.addEventListener("change", change); return () => media.removeEventListener("change", change); }, []);
  const user = useAuthStore(state => state.user), navigate = useNavigate(), cache = useQueryClient();

  const [params, setParams] = useSearchParams();

  const [draft,setDraft]=useState<{record:Relationship;channel:"email"|"whatsapp"}>();
  const [revision, setRevision] = useState(0), [focus, setFocus] = useState<Relationship>(), [editing, setEditing] = useState<Relationship | "new">();

  const [selected, setSelected] = useState<Relationship[]>([]), [result, setResult] = useState<GridResult<Relationship>>(), [notice, setNotice] = useState("");

  const [bulk, setBulk] = useState<"schedule" | "assign">();

  const [context, setContext] = useState(() => sessionStorage.getItem("suite-branch") || "all");

  const entity = params.get("entity") || "all", bucket = params.get("bucket") || "all", scope = params.get("scope") || "all";

  const kind = params.get("kind") || "", item = params.get("item_id") || "", productName = params.get("product_name") || "";

  const owner = params.get("owner_id") || "", from = params.get("from") || "", to = params.get("to") || "";

  const update = (values: Record<string, string>) => { const next = new URLSearchParams(params); Object.entries(values).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key)); setParams(next, { replace: true }); setSelected([]); setResult(undefined); };

  const refresh = () => { setRevision(value => value + 1); void cache.invalidateQueries({ queryKey: ["followup-detail"] }); void cache.invalidateQueries({ queryKey: ["followup-target"] }); };

  useEffect(() => { const reset = () => { setContext(sessionStorage.getItem("suite-branch") || "all"); setFocus(undefined); setEditing(undefined); setBulk(undefined); setSelected([]); setResult(undefined); refresh(); }; const changed = () => refresh(); window.addEventListener("suite:organization-changed", reset); window.addEventListener("crm:records-changed", changed); return () => { window.removeEventListener("suite:organization-changed", reset); window.removeEventListener("crm:records-changed", changed); }; }, []);

  const owners = useQuery({ queryKey: ["followup-owners", user?.id, user?.access?.companyId, context], queryFn: async () => (await api.get<{ owners: Owner[] }>("/crm/lead-management/settings")).data.owners, staleTime: 60000 });

  const source = useMemo<GridDataSource<Relationship>>(() => { const adapter: GridDataSource<Relationship> = {

    key: JSON.stringify([user?.id, user?.access?.companyId, context, entity, bucket, scope, kind, item, owner, from, to]),

    load: async (query, signal) => {

      const response = await api.get<Listing>(`${root}/records`, { signal, params: { entity, bucket, scope, kind: kind || undefined, item_id: item || undefined, owner_id: owner || undefined, date_from: from ? new Date(`${from}T00:00:00`).toISOString() : undefined, date_to: to ? new Date(`${to}T23:59:59.999`).toISOString() : undefined, active_only: true, timezone_name: Intl.DateTimeFormat().resolvedOptions().timeZone, state: JSON.stringify(query) } });

      return { rows: response.data.items, total: response.data.total, pageTotal: response.data.total, page: query.page, pageSize: query.pageSize, permissions: { export: response.data.can_export !== false }, context: { counts: response.data.counts, buckets: response.data.buckets } };

    },

  };

    adapter.export = async request => {



      let rows: Relationship[] = [];

      if (request.scope === "visible") rows = (await adapter.load(request.query)).rows;

      else {

        for (let page = 1; page <= 100; page++) {

          const batch = await adapter.load({ ...request.query, page, pageSize: 200 });

          if (batch.total > 20000) throw new Error("Narrow your filters to export at most 20,000 relationships.");

          rows.push(...batch.rows);

          if (rows.length >= batch.total) break;

        }

        if (request.scope === "selected") rows = rows.filter(row => request.ids.includes(row.key));

      }

      const response = await api.post(`${root}/export`, { format: request.format, recipients: rows.map(row => ({ entity: row.entity, id: row.id })), columns: request.columns, summary: request.includeSummaries }, { responseType: request.format === "clipboard" ? "text" : "blob" });
      return response.data;

    };

    return adapter;

  }, [user?.id, user?.access?.companyId, context, entity, bucket, scope, kind, item, owner, from, to]);

  const message = (record: Relationship) => { sessionStorage.setItem(`crm-growth:${user?.id || 0}:${user?.access?.companyId || 0}:${context}:recipients`, JSON.stringify({ [record.key]: record })); navigate(`/crm/greetings?entity=${record.entity}`); };

  const columns = useMemo<GridColumn<Relationship>[]>(() => ([

    { id: "name", title: "Relationship", width: 220, minWidth: 150, render: row => <button data-record-open className="fu-relationship" onClick={() => setFocus(row)}><strong>{row.name}</strong><small>{row.company || row.email || "No company recorded"}</small></button> },

    { id: "entity", title: "Type / status", width: 148, render: row => <div className="fu-type"><span>{labels[row.entity]}</span><small>{row.status || "No status"}</small></div> },

    { id: "email", title: "Get in touch", width: 215, render: row => <div className="fu-contact"><span><Mail size={13} />{row.email || "No email recorded"}</span>{row.phone && <a href={`tel:${row.phone_country_code || ""}${row.phone}`}><Phone size={13} />{row.phone_country_code} {row.phone}</a>}</div> },

    { id: "due", title: "Next conversation", type: "datetime", width: 208, render: row => <Due value={row.due} /> },

    { id: "owner_id", title: "Owner", type: "number", width: 155, accessor: row => row.owner_id, render: row => <span className="fu-owner"><i>{initials(row.owner_name || "?")}</i><span title={row.owner_name}>{row.owner_name || "Unassigned"}</span></span> },

    { id: "priority", title: "Priority", width: 100 },

    { id: "last_contact", title: "Last contact", type: "datetime", width: 170, render: row => row.last_contact ? date(row.last_contact) : "No contact logged" },

    { id: "status", title: "Status", width: 120 },

  ] satisfies GridColumn<Relationship>[]).map(column => ({ ...column, groupable: false })), []);

  useEffect(() => { if (result && !params.get("record_id")) setFocus(current => current ? result.rows.find(row => row.key === current.key) : undefined); }, [result]);

  const targetId = params.get("record_id");
  const target = useQuery({ queryKey: ["followup-target", user?.id, user?.access?.companyId, context, entity, targetId], enabled: !!targetId && /^\d+$/.test(targetId) && entity !== "all", queryFn: async () => (await api.get<Listing>(`${root}/records`, { params: { entity, state: JSON.stringify({ filters: { logic: "and", rules: [{ field: "id", operator: "equals", value: targetId }] }, page: 1, pageSize: 1 }) } })).data.items[0] });
  useEffect(() => { if (target.data) setFocus(target.data); }, [target.data]);
  const closeFocus = () => { setFocus(undefined); if (targetId) { const next = new URLSearchParams(params); next.delete("record_id"); setParams(next, { replace: true }); } };
  const counts = result?.context?.counts as Record<string, number> | undefined, buckets = result?.context?.buckets as Record<string, number> | undefined;

  const saved = () => { setEditing(undefined); setNotice("Follow-up saved. Relationship data refreshed."); refresh(); };

  return <main className="crm-followup">

    <header className="fu-header"><div className="fu-heading"><span className="fu-heading-icon"><CalendarClock size={23} /></span><div><h1>Lead & customer follow-ups</h1><p>Manage conversations, next steps and relationship activities.</p></div></div><CompactActions className="fu-header-actions"><Button asChild variant="outline" size="sm"><Link to="/crm/product-customers"><Package size={15} />By product / service</Link></Button><Button asChild variant="outline" size="sm"><Link to="/crm/greetings"><Gift size={15} />Greetings</Link></Button><Button size="sm" onClick={() => setEditing("new")}><Plus size={16} />New follow-up</Button><Button size="icon" variant="outline" aria-label="Refresh follow-ups" onClick={refresh}><RefreshCw size={16} /></Button></CompactActions></header>

    <div className="fu-kpis">{([['leads', Users], ['contacts', Mail], ['companies', Building2], ['deals', Package]] as const).map(([key, Icon]) => <button aria-pressed={entity === key} key={key} onClick={() => update({ entity: entity === key ? "all" : key })}><span className="fu-kpi-icon"><Icon size={23} /></span><span><small>{labels[key]}</small><strong>{counts ? (counts[key] || 0).toLocaleString() : "—"}</strong></span><span className="fu-kpi-caption">Matching filters</span></button>)}</div>

    {targetId && target.error && <p role="alert" className="text-destructive">{failure(target.error)}</p>}
    {notice && <div role="status" className="fu-notice">{notice}<button aria-label="Dismiss notification" onClick={() => setNotice("")}><X size={14} /></button></div>}

    <div className={`fu-layout ${focus ? "has-detail" : ""}`}><section className="fu-workspace" aria-label="Follow-up management">

      <div className="fu-filters"><NativeSelect aria-label="Relationship type" value={entity} onChange={e => update({ entity: e.target.value })}>{Object.entries(labels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</NativeSelect><NativeSelect aria-label="Record scope" value={scope} onChange={e => update({ scope: e.target.value })}><option value="all">All permitted records</option><option value="mine">My records</option><option value="team">My team</option></NativeSelect><NativeSelect aria-label="Assigned owner" value={owner} onChange={e => update({ owner_id: e.target.value })}><option value="">All owners</option>{owners.data?.map(person => <option key={person.id} value={person.id}>{person.name || person.email}</option>)}</NativeSelect><ProductPicker kind={kind} id={item} name={productName} change={(kind, id, name) => update({ kind, item_id: id, product_name: name })} /><details className="fu-date-filter"><summary>Follow-up dates</summary><div><label>From<Input type="date" value={from} onChange={e => update({ from: e.target.value })} onInput={e => update({ from: e.currentTarget.value })} /></label><label>To<Input type="date" value={to} min={from} onChange={e => update({ to: e.target.value })} onInput={e => update({ to: e.currentTarget.value })} /></label><Button size="sm" variant="ghost" onClick={() => update({ from: "", to: "" })}>Clear dates</Button></div></details><Button size="sm" variant="ghost" onClick={() => { setParams({}); setSelected([]); setResult(undefined); }}>Reset scope</Button></div>

      <nav className="fu-buckets" aria-label="Follow-up status">{[['all', 'All active relationships'], ['overdue', 'Overdue'], ['today', 'Today'], ['upcoming', 'Upcoming'], ['missing', 'No next step']].map(([key, label]) => <button aria-pressed={bucket === key} key={key} className={bucket === key ? "active" : ""} onClick={() => update({ bucket: key })}>{key === "all" ? <Package size={15} /> : <CalendarClock size={15} />}{label} <span>({buckets ? (key === "all" ? Object.values(buckets).reduce((a, b) => a + b, 0) : buckets[key] || 0).toLocaleString() : "—"})</span></button>)}<Link to="/crm/follow-ups">Worklist ↗</Link></nav>

      {selected.length > 0 && <div className="fu-bulk"><strong>{selected.length} selected</strong><Button size="sm" variant="outline" disabled={selected.length > 50 || selected.some(row => !row.can_edit)} onClick={() => setBulk("schedule")}>Schedule selected</Button><Button size="sm" variant="outline" disabled={selected.length > 50 || selected.some(row => !row.can_edit)} onClick={() => setBulk("assign")}>Assign follow-ups</Button><Button size="sm" variant="ghost" onClick={() => setSelected([])}>Clear</Button>{selected.length > 50 && <span>Select at most 50 relationships.</span>}</div>}

      <SharedDataGrid<Relationship> key={JSON.stringify([mobile, entity, bucket, scope, kind, item, owner, from, to])} gridId={`crm-relationship-followups-v1-${mobile ? "mobile" : "desktop"}`} title="Relationships" userId={user?.id} organizationId={user?.access?.companyId} workspaceId={context} dataSource={source} columns={columns} getRowId={row => row.key} initialQuery={{ pageSize: 25 }} viewContext={{ entity, bucket, scope, kind, item_id: item, product_name: productName, owner_id: owner, from, to }} onViewContextChange={values => update(Object.fromEntries(Object.entries(values).map(([key, value]) => [key, String(value || "")])))} initialLayout={{ view: mobile ? "cards" : "grid", density: "compact", rowHeight: 56, visibility: { priority: false, last_contact: false, status: false } }} refreshKey={revision} selectedIds={selected.map(row => row.key)} onSelectionChange={rows => setSelected(rows)} onResult={setResult} onOpen={setFocus} onSelectRecord={setFocus} onOpenPopup={row=>openRecordPreview(row,`/crm/${row.entity}`)} statistics={() => null} height={600} rowActions={[{ id: "follow", label: "Follow up", icon: CalendarClock, quick: true, visible: row => row.can_edit, run: row => setEditing(row) }, { id: "message", label: "Email", icon: Mail, quick: true, disabled:row=>!row.email||communicationBlocked(row), run: row=>setDraft({record:row,channel:"email"}) }, {id:"whatsapp",label:"WhatsApp",icon:WhatsAppIcon,quick:true,disabled:row=>!whatsappNumber(row)||communicationBlocked(row),run:row=>setDraft({record:row,channel:"whatsapp"})},{id:"popup",label:"Open popup",icon:Eye,quick:true,run:row=>openRecordPreview(row,`/crm/${row.entity}`)}, { id: "open", label: "Open full record", run: row => navigate(row.url) }]} renderCard={row => <div className="fu-mobile-card"><strong>{row.name}</strong><span>{labels[row.entity]} · {row.status}</span><span>{row.email || row.phone || "No contact details recorded"}</span><Due value={row.due} /></div>} />

    </section>{focus && <RelationshipPanel key={`${context}:${focus.key}`} record={focus} close={closeFocus} edit={() => setEditing(focus)} message={() => message(focus)} revision={revision} changed={refresh} />}</div>

    {draft&&<RecordMessageDraft record={draft.record} channel={draft.channel} close={()=>setDraft(undefined)}/>}
    {editing && <Editor key={editing === "new" ? "new" : editing.key} initial={editing === "new" ? undefined : editing} owners={owners.data || []} close={() => setEditing(undefined)} saved={saved} />}

    {bulk && <BulkEditor changed={refresh} action={bulk} records={selected} owners={owners.data || []} close={() => setBulk(undefined)} saved={message => { setNotice(message); setBulk(undefined); setSelected([]); refresh(); }} />}

  </main>;

}



function Editor({ initial, owners, close, saved }: { initial?: Relationship; owners: Owner[]; close: () => void; saved: () => void }) {

  const user = useAuthStore(state => state.user);

  const authScope = `${user?.id}:${user?.access?.companyId}:${sessionStorage.getItem("suite-branch")}`;

  const [record, setRecord] = useState(initial), [search, setSearch] = useState(""), [activity, setActivity] = useState("");

  const [version, setVersion] = useState<string>();
  const [action, setAction] = useState("schedule"), [title, setTitle] = useState(initial ? `Follow up with ${initial.name}` : "Customer follow-up"), [due, setDue] = useState("");

  const [channel, setChannel] = useState("call"), [notes, setNotes] = useState(""), [outcome, setOutcome] = useState("Connected"), [owner, setOwner] = useState(String(initial?.owner_id || "")), [priority, setPriority] = useState("Medium"), [next, setNext] = useState("");

  const [reminder, setReminder] = useState(""), [offering, setOffering] = useState({ kind: "", id: "", name: "" });

  const [busy, setBusy] = useState(false), [error, setError] = useState("");

  const query = useDebounced(search);

  const choices = useQuery({ queryKey: ["followup-choose", authScope, query], queryFn: async () => (await api.get<Listing>(`${root}/records`, { params: { search: query, active_only: true, per_page: 12 } })).data.items, enabled: !record });

  const pending = useQuery({ queryKey: ["followup-pending", authScope, record?.key], queryFn: async () => (await api.get<{ items: Pending[] }>(`${root}/pending/${record!.entity}/${record!.id}`)).data.items, enabled: !!record, staleTime: 0 });

  const save = async () => { if (!record) return; setBusy(true); setError(""); try { await api.post(`${root}/follow-up`, { entity: record.entity, record_id: record.id, action, activity_id: activity ? Number(activity) : null, activity_version: version || null, due_at: due ? new Date(due).toISOString() : null, title, channel, notes, outcome: action === "complete" ? outcome : "", owner_id: owner ? Number(owner) : null, priority, next_action: next, reminder_at: reminder ? new Date(reminder).toISOString() : null, offering_kind: offering.kind || null, offering_id: offering.id ? Number(offering.id) : null }); saved(); } catch (error) { setError(failure(error)); } finally { setBusy(false); } };

  return <Dialog open onOpenChange={open => { if (!open && !busy) close(); }}><DialogContent className="fu-editor"><DialogTitle>{record ? `Follow up · ${record.name}` : "New follow-up"}</DialogTitle><p className="text-sm text-muted-foreground">Plan a conversation or record an outcome. Times follow your device time zone.</p><fieldset disabled={busy} className="fu-editor-fields">

    {!record ? <><Input autoFocus aria-label="Find a relationship" placeholder="Search name, email, company or phone…" value={search} onChange={e => setSearch(e.target.value)} />{choices.isPending && <p role="status">Loading relationships…</p>}{choices.error && <p role="alert">{failure(choices.error)}</p>}<div className="fu-choices">{choices.data?.filter(row => row.can_edit).map(row => <button key={row.key} onClick={() => { setRecord(row); setTitle(`Follow up with ${row.name}`); setOwner(String(row.owner_id || "")); }}><strong>{row.name}</strong><small>{labels[row.entity]} · {row.email || row.company || "No email recorded"}</small></button>)}{choices.data && !choices.data.some(row => row.can_edit) && <p>No editable relationships match your search.</p>}</div></> : <>

    <div className="fu-form-grid"><label>Action<NativeSelect value={action} onChange={e => { setAction(e.target.value); setActivity(""); setVersion(undefined); setDue(""); setReminder(""); }}><option value="schedule">Schedule / reschedule</option><option value="complete" disabled={!pending.data?.length}>Log outcome & complete</option></NativeSelect></label><label>Existing follow-up<NativeSelect aria-label="Existing follow-up" disabled={pending.isPending || !!pending.error} value={activity} onChange={e => { setActivity(e.target.value); setVersion(undefined); const row = pending.data?.find(item => item.id === Number(e.target.value)); if (row) { setVersion(row.version); setTitle(row.title); setChannel(row.channel); setOwner(String(row.owner_id || "")); setPriority(row.priority || "Medium"); setNotes(row.notes || ""); setNext(row.metadata?.next_action || ""); setReminder(row.metadata?.reminder_at && new Date(row.metadata.reminder_at) > new Date() ? localInput(row.metadata.reminder_at) : ""); setOffering({ kind: row.metadata?.offering_kind || "", id: String(row.metadata?.offering_id || ""), name: "" }); if (action === "schedule") setDue(localInput(row.due_at)); } }}><option value="">{pending.isPending ? "Loading…" : action === "complete" ? "Choose a pending follow-up" : "Create new follow-up"}</option>{pending.data?.map(row => <option key={row.id} value={row.id}>{row.title} · {date(row.due_at)}</option>)}</NativeSelect></label></div>

    {pending.error && <p role="alert" className="text-destructive">{failure(pending.error)}</p>}

    <label>Purpose<Input value={title} maxLength={220} onChange={e => setTitle(e.target.value)} /></label>

    <div className="fu-form-grid"><label>Channel<NativeSelect value={channel} onChange={e => setChannel(e.target.value)}>{['call', 'email', 'whatsapp', 'sms', 'meeting', 'visit', 'other'].map(item => <option key={item} value={item}>{item === "whatsapp" ? "WhatsApp" : item.toUpperCase()}</option>)}</NativeSelect></label><label>{action === "complete" ? "Next follow-up (optional)" : "Follow-up date & time"}<Input aria-label="Follow-up date and time" type="datetime-local" value={due} onChange={e => setDue(e.target.value)} onInput={e => setDue(e.currentTarget.value)} /></label></div>

    <div className="fu-quick-dates">{[['In an hour', 1], ['Tomorrow', 24], ['In 3 days', 72], ['In 7 days', 168], ['In 15 days', 360], ['In 30 days', 720]] .map(([label, hours]) => <Button key={label} size="sm" variant="outline" onClick={() => setDue(localInput(new Date(Date.now() + Number(hours) * 3600000)))}>{label}</Button>)}</div>

    <div className="fu-form-grid"><label>Assigned employee<NativeSelect value={owner} onChange={e => setOwner(e.target.value)}><option value="">Record owner</option>{owners.map(person => <option key={person.id} value={person.id}>{person.name || person.email}</option>)}</NativeSelect></label><label>Priority<NativeSelect value={priority} onChange={e => setPriority(e.target.value)}>{['High', 'Medium', 'Low'].map(value => <option key={value}>{value}</option>)}</NativeSelect></label></div>

    {action === "complete" && <label>Outcome<NativeSelect value={outcome} onChange={e => setOutcome(e.target.value)}>{['Connected', 'Interested', 'No answer', 'Callback requested', 'Not interested', 'Resolved'].map(value => <option key={value}>{value}</option>)}</NativeSelect></label>}

    <label>Product / service<ProductPicker {...offering} change={(kind, id, name) => setOffering({ kind, id, name })} /></label><label>In-app reminder (optional)<Input type="datetime-local" value={reminder} onChange={e => setReminder(e.target.value)} onInput={e => setReminder(e.currentTarget.value)} /><small className="text-muted-foreground">Delivered when the CRM reminder scheduler runs.</small></label><label>Conversation notes<textarea maxLength={4000} rows={3} value={notes} onChange={e => setNotes(e.target.value)} /></label><label>Next action<Input maxLength={1000} value={next} onChange={e => setNext(e.target.value)} placeholder="What should happen next?" /></label>

    </>}

  </fieldset>{error && <p role="alert" className="text-sm text-destructive">{error}</p>}<footer className="fu-editor-footer"><Button disabled={busy} variant="outline" onClick={close}>Cancel</Button><Button disabled={busy || !record || !title.trim() || (action === "schedule" && !due) || (action === "complete" && !activity)} onClick={() => void save()}>{busy ? "Saving…" : action === "complete" ? "Save outcome & next step" : "Save follow-up"}</Button></footer></DialogContent></Dialog>;

}



function RelationshipPanel({ record, close, edit, message, revision, changed }: { record: Relationship; close: () => void; edit: () => void; message: () => void; revision: number; changed: () => void }) {

  const user = useAuthStore(state => state.user);

  const authScope = `${user?.id}:${user?.access?.companyId}:${sessionStorage.getItem("suite-branch")}`;

  const [converting, setConverting] = useState(false);

  const [tab, setTab] = useState("Overview"), [note, setNote] = useState(""), [busy, setBusy] = useState(false), [error, setError] = useState("");

  const data = useQuery({ queryKey: ["followup-detail", authScope, record.entity, record.id, revision], queryFn: async () => (await api.get<{ timeline?: Timeline[]; related?: { notes?: { id: number; body?: string }[] } }>(`/crm/${record.entity}/${record.id}`)).data, staleTime: 15000 });

  useEffect(() => { const escape = (event: KeyboardEvent) => { if (event.key === "Escape") close(); }; window.addEventListener("keydown", escape); return () => window.removeEventListener("keydown", escape); }, [close]);

  const addNote = async () => { setBusy(true); setError(""); try { await api.post("/crm/notes", { body: note, [record.entity === "companies" ? "company_id" : `${record.entity.slice(0, -1)}_id`]: record.id }); setNote(""); changed(); } catch (error) { setError(failure(error)); } finally { setBusy(false); } };

  const files = useQuery({ queryKey: ["followup-detail", authScope, "files", record.key, revision], queryFn: async () => (await api.get<{ items: { id: number; name: string; size: number; url: string }[] }>(`${root}/files/${record.entity}/${record.id}`)).data.items, enabled: tab === "Files" });

  const convert = async () => { setBusy(true); setError(""); try { await api.post("/crm/contact-directory/convert", { leadId: record.id, customerType: "Individual" }); changed(); close(); } catch (error) { setError(failure(error)); } finally { setBusy(false); } };

  const download = async (file: { name: string; url: string }) => {
    setBusy(true); setError("");
    try { const response = await api.get(file.url, { responseType: "blob" }); const url = URL.createObjectURL(response.data); const link = document.createElement("a"); link.href = url; link.download = file.name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
    catch (error) { setError(failure(error)); } finally { setBusy(false); }
  };
  const events = data.data?.timeline || [];
  const shownEvents = events.filter(event => tab === "History" || ["activities", "activity", "call", "meeting", "email", "follow_up"].some(type => event.type.toLowerCase().includes(type)));

  return <aside className="fu-detail" aria-label={`Relationship details: ${record.name}`}><div className="fu-detail-top"><span className="fu-avatar">{initials(record.name)}</span><div><h2>{record.name}</h2><span className="fu-chip">{labels[record.entity]}</span> <small>{record.status}</small></div><button aria-label="Close relationship details" onClick={close}><X size={18} /></button></div><div className="fu-detail-tabs" role="tablist" aria-label="Relationship information">{['Overview', 'Activity', 'Notes', 'History', 'Files'].map(value => <button key={value} role="tab" aria-selected={tab === value} onClick={() => setTab(value)}>{value}</button>)}</div><div className="fu-detail-body" role="tabpanel" aria-label={tab}>

    {tab === "Overview" ? <><dl><dt><Mail size={15} />Email</dt><dd>{record.email ? <a href={`mailto:${record.email}`}>{record.email}</a> : "No email recorded"}</dd><dt><Phone size={15} />Phone</dt><dd>{record.phone ? <a href={`tel:${record.phone_country_code || ""}${record.phone}`}>{record.phone_country_code} {record.phone}</a> : "No phone recorded"}</dd><dt><Building2 size={15} />Company</dt><dd>{record.company || "—"}</dd><dt><CalendarClock size={15} />Next conversation</dt><dd><Due value={record.due} /></dd><dt><Users size={15} />Owner</dt><dd>{record.owner_name || "Unassigned"}</dd></dl><h3>Quick actions</h3><CompactActions className="fu-quick-actions"><Button available={!!(record.can_edit)} variant="outline" disabled={!record.can_edit} onClick={edit}><CalendarClock size={20} />Follow up</Button><Button variant="outline" onClick={message}><Mail size={20} />Message</Button><Button asChild variant="outline"><Link to={record.url}>View record ↗</Link></Button>{record.phone && <Button asChild variant="outline"><a href={`tel:${record.phone_country_code || ""}${record.phone}`}><Phone size={20} />Call</a></Button>}</CompactActions>{record.entity === "leads" && record.can_edit && <div className="mt-3 space-y-2">{converting ? <><p>Convert this lead into a customer using the shared contact directory? Existing identity matches and history will be preserved.</p><Button size="sm" disabled={busy} onClick={() => void convert()}>{busy ? "Converting…" : "Confirm conversion"}</Button><Button size="sm" variant="ghost" disabled={busy} onClick={() => setConverting(false)}>Cancel</Button></> : <Button size="sm" variant="outline" onClick={() => setConverting(true)}>Convert to customer</Button>}{error && <p role="alert">{error}</p>}</div>}<p className="fu-help">Messages open a recipient review before sending.</p></> : <>

    {data.isPending && <p role="status">Loading relationship history…</p>}{data.error && <p role="alert">{failure(data.error)}</p>}

    {tab === "Files" ? <>{files.isPending && <p role="status">Loading linked files…</p>}{files.error && <p role="alert">{failure(files.error)}</p>}{files.data?.map(file => <article key={file.id}><button disabled={busy} className="text-primary underline" onClick={() => void download(file)}>{file.name}</button><small className="block">{Math.ceil(file.size / 1024)} KB</small></article>)}{files.data?.length === 0 && <p className="fu-empty">No linked files.</p>}{error && <p role="alert">{error}</p>}</> : tab === "Notes" ? <>{data.data?.related?.notes?.map(item => <article key={item.id}>{item.body || "Empty note"}</article>)}{!data.isPending && !data.data?.related?.notes?.length && <p className="fu-empty">No notes recorded.</p>}{record.can_edit && <><label>Add a note<textarea aria-label="New relationship note" value={note} rows={4} maxLength={4000} onChange={e => setNote(e.target.value)} /></label><Button size="sm" disabled={busy || !note.trim()} onClick={() => void addNote()}>{busy ? "Saving…" : "Save note"}</Button></>}{error && <p role="alert">{error}</p>}</> : <>{shownEvents.map((event, index) => <article key={`${event.id || index}:${event.type}`}><strong>{event.title || event.type}</strong><time>{date(event.occurredAt)}</time><p>{event.record?.body || event.record?.description || event.record?.outcome}</p></article>)}{!data.isPending && !shownEvents.length && <p className="fu-empty">No recorded interactions yet.</p>}</>}

    </>}

  </div></aside>;

}



function BulkEditor({ action, records, owners, close, saved, changed }: { changed: () => void; action: "schedule" | "assign"; records: Relationship[]; owners: Owner[]; close: () => void; saved: (message: string) => void }) {

  const [owner, setOwner] = useState(""), [due, setDue] = useState(""), [busy, setBusy] = useState(false), [error, setError] = useState("");

  const request = useRef({ fingerprint: "", id: "" });
  const [remaining, setRemaining] = useState(records), [savedCount, setSavedCount] = useState(0);
  const submit = async () => {
    setBusy(true); setError("");
    const payload = { recipients: remaining.map(row => ({ entity: row.entity, id: row.id })), action, owner_id: owner ? Number(owner) : null, due_at: due ? new Date(due).toISOString() : null };
    const fingerprint = JSON.stringify(payload);
    if (request.current.fingerprint !== fingerprint) request.current = { fingerprint, id: crypto.randomUUID() };
    try {
      const response = await api.post(`${root}/follow-ups/bulk`, { ...payload, request_id: request.current.id });
      const failed = response.data.items.filter((row: { saved: boolean }) => !row.saved);
      const totalSaved = savedCount + response.data.saved;
      changed();
      if (failed.length) {
        setSavedCount(totalSaved);
        setRemaining(current => current.filter(row => failed.some((failure: { key: string }) => failure.key === row.key)));
        setError(`${totalSaved} saved. ${failed.map((row: { key: string; message: string }) => `${row.key}: ${row.message}`).join("; ")}`);
      } else saved(`${totalSaved} follow-ups ${action === "assign" ? "assigned" : "scheduled"}.`);
    } catch (error) { setError(failure(error)); } finally { setBusy(false); }
  };

  return <Dialog open onOpenChange={open => { if (!open && !busy) close(); }}><DialogContent><DialogTitle>{action === "assign" ? "Assign pending follow-ups" : "Schedule follow-ups"}</DialogTitle><p className="text-sm">{remaining.length} relationships remaining. {action === "assign" ? "Updates their existing pending follow-ups." : "Creates a new follow-up for each relationship."}</p>{action === "schedule" && <label>Follow-up date & time<Input aria-label="Bulk follow-up time" type="datetime-local" value={due} disabled={busy} onChange={e => setDue(e.target.value)} onInput={e => setDue(e.currentTarget.value)} /></label>}<div className="fu-quick-dates">{action === "schedule" && [["Tomorrow", 24], ["In 3 days", 72]].map(([label, hours]) => <Button key={label} size="sm" variant="outline" disabled={busy} onClick={() => setDue(localInput(new Date(Date.now() + Number(hours) * 3600000)))}>{label}</Button>)}</div><label>Assigned employee<NativeSelect value={owner} disabled={busy} onChange={e => setOwner(e.target.value)}><option value="">{action === "assign" ? "Choose employee" : "Use record owners"}</option>{owners.map(person => <option key={person.id} value={person.id}>{person.name || person.email}</option>)}</NativeSelect></label>{error && <p role="alert" className="text-destructive">{error}</p>}<div className="fu-editor-footer"><Button variant="outline" disabled={busy} onClick={close}>Close</Button><Button disabled={busy || (action === "assign" ? !owner : !due)} onClick={() => void submit()}>{busy ? "Saving…" : "Apply to selected"}</Button></div></DialogContent></Dialog>;

}
