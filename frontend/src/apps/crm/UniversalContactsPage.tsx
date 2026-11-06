import CrmRecordFields, { useCrmFieldForm, CrmFieldsReadOnly } from "@/shared/custom-fields/CrmRecordFields";
import Record360Workspace from "@/shared/records/Record360Workspace";
import GridTable from "@/shared/data-grid/GridTable";
import PhoneActions from "@/components/PhoneActions";
import BranchAvailability, { type BranchAvailabilityValue } from "@/shared/BranchAvailability";
import FinancialDataTab, { type FinancialData } from "./FinancialDataTab";

import { CommunicationDraftEditor, primaryEntries, transportEntries, type CommunicationEntry, BirthdayEditor, ContactCommunicationPanel } from "@/shared/master-data/CommunicationEditor";

import CompanySelect, { SharedNumberConfirmation } from "@/shared/master-data/CompanySelect";

import PersonRecordPreview from "@/components/PersonRecordPreview";

import CompactActions from "@/components/actions/CompactActions";

import { ActionButton, IconActionButton, MoreActionsMenu } from "@/components/actions";

import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";

import { Link, useSearchParams } from "react-router-dom";

import { useQuery, useQueryClient } from "@tanstack/react-query";

import { ArrowDownUp, Check, Copy, Download, Grid2X2, List, Mail, MessageSquare, Phone, MoreHorizontal, Pencil, Plus, RefreshCw, Search, Settings2, Star, Tag, Trash2, Users, X } from "lucide-react";
import { WhatsAppIcon } from "@/components/actions/BrandIcons";
import { communicationBlocked, whatsappNumber } from "@/shared/records/RecordWorkspace";
const EmailComposer = lazy(() => import("./CRMRecordDetailPage").then(m => ({default:m.EmailComposeModal})));
const WhatsAppComposer = lazy(() => import("./RelationshipWhatsAppDialog"));
const MessageComposer = lazy(() => import("./CRMRecordDetailPage").then(m => ({default:m.MessageComposeModal})));

import { api } from "@/services/api";

import { useRecordView } from "@/lib/smart-cache/use-record-view";

import { useAuthStore } from "@/store/authStore";

import { Button } from "@/components/ui/button";

import { Input } from "@/components/ui/input";

import { NativeSelect } from "@/components/ui/native-select";

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

import { dealError } from "./deals/deal-utils";

import CRMDataTransfer from "./CRMDataTransfer";

import "./universal-contacts.css";



type Contact = {gstNumber?: string; bankAccountCount?: number; upiCount?: number; unconvertedLeadIds?: number[]; id: number; name: string; email?: string; phone?: string; phoneCountryCode?: string; organization?: string; companyId?:number;roles?:string[];lifecycleStage?:string; ownerId?: number; status: string; tags: string[]; lastInteraction?: string; nextFollowUp?: string; createdAt?: string; updatedAt?: string; notes?: string; version: string; deletedAt?: string};

type Lead = {id: number; name: string; status: string; converted: boolean};

type Detail = Contact & {leads: Lead[]; related: {related?: Record<string, unknown[]>; timeline?: Record<string, unknown>[]}};

type Directory = {items: Contact[]; total: number; stats: Record<string, number>; canManage: boolean; canPermanentlyDelete: boolean; canConvert: boolean; canExport: boolean; classifications: string[]};

type Condition = {field: string; operator: string; value: string};

type Column = "gstNumber" | "bankAccounts" | "upi" | "name" | "email" | "phone" | "tags" | "owner" | "status" | "lastInteraction" | "nextFollowUp" | "updated" | "created";

type Preferences = {financialColumnsVersion?: number; columns: Column[]; widths: Partial<Record<Column, number>>; card: boolean; favorites: number[]; presets: {name: string; filters: Condition[]; match: string}[]};

const root = "/crm/contact-directory";

const columns: Column[] = ["gstNumber", "bankAccounts", "upi", "name", "email", "phone", "tags", "owner", "status", "lastInteraction", "nextFollowUp", "updated", "created"];

const titles: Record<Column, string> = {gstNumber: "Company GST number", bankAccounts: "Bank accounts", upi: "UPI IDs", name: "Contact / organization", email: "Email", phone: "Phone", tags: "Relationships", owner: "Owner", status: "Status", lastInteraction: "Last interaction", nextFollowUp: "Next follow-up", updated: "Updated", created: "Created"};

const defaultPreferences: Preferences = {financialColumnsVersion: 1, columns: ["name", "email", "phone", "tags", "owner", "status", "nextFollowUp", "updated", "gstNumber", "bankAccounts", "upi"], widths: {}, card: false, favorites: [], presets: []};

const date = (value?: string) => value ? new Date(value).toLocaleDateString(undefined, {day: "numeric", month: "short", year: "numeric"}) : "—";

const badgeClass = (tag: string) => ({lead: "blue", prospect: "cyan", customer: "green", vendor: "orange", partner: "gold", friend: "pink", consultant: "teal", investor: "violet"}[tag.toLowerCase()] || "neutral");

function Badges({tags}: {tags: string[]}) { return <div className="uc-badges">{tags.map(tag => <span key={tag} className={`uc-badge uc-${badgeClass(tag)}`}>{tag}</span>)}</div>; }

function loadPreferences(key: string): Preferences { try { const value = JSON.parse(localStorage.getItem(key) || "null"); return value ? {...defaultPreferences, ...value, columns: value.columns ? [...new Set<Column>([...value.columns.filter((x: Column) => columns.includes(x)), ...(value.financialColumnsVersion === 1 ? [] : ["gstNumber", "bankAccounts", "upi"] as Column[])])] : defaultPreferences.columns, financialColumnsVersion: 1} : defaultPreferences; } catch { return defaultPreferences; } }



export default function UniversalContactsPage({ title = "Universal Contacts" }: { title?: string }) {

  const user = useAuthStore(s => s.user);

  const scope = [user?.id, user?.access?.companyId, sessionStorage.getItem("suite-branch")].join(":");

  return <DirectoryWorkspace key={scope} title={title}/>;

}



function DirectoryWorkspace({ title }: { title: string }) {

  const user = useAuthStore(s => s.user);

  const qc = useQueryClient();

  const [params, setParams] = useSearchParams();

  const scope = [user?.id, user?.access?.companyId, sessionStorage.getItem("suite-branch")].join(":");

  const preferenceKey = `suite:contacts:preferences:${scope}`;

  const [prefs, setPrefs] = useState<Preferences>(() => loadPreferences(preferenceKey));

  const [search, setSearch] = useState(params.get("search") || "");

  const [tab, setTab] = useState(params.get("view") === "deleted" ? "Trash" : params.get("entity") === "leads" ? "Lead" : "All");

  const [filters, setFilters] = useState<Condition[]>([]);

  const [match, setMatch] = useState("and");

  const [showFilters, setShowFilters] = useState(false);

  const [sort, setSort] = useState("updated");

  const [direction, setDirection] = useState("desc");

  const [page, setPage] = useState(1);

  const [selected, setSelected] = useState<number[]>([]);

  const [notice, setNotice] = useState("");

  const [error, setError] = useState("");

  const [busy, setBusy] = useState(false);

  const [editing, setEditing] = useState<Contact | "new" | null>(null);
  const [compose, setCompose] = useState<{record:Contact;channel:"email"|"whatsapp"|"sms"} | null>(null);
  const linked = useRef(false);

  const [detailId, setDetailId] = useState<number | null>(null);

  const [confirm, setConfirm] = useState<{action: "trash" | "restore" | "permanent"; ids: number[]} | null>(null);

  const [tagging, setTagging] = useState<number[] | null>(null);

  const [newTag, setNewTag] = useState("");

  const [conversion, setConversion] = useState<{lead: Lead; contact: Contact} | null>(null);

  const [customerType, setCustomerType] = useState("Individual");

  const [correction, setCorrection] = useState<Lead | null>(null);

  const [correctionReason, setCorrectionReason] = useState("");

  const [merge, setMerge] = useState<Contact | null>(null);

  const [mergeTarget, setMergeTarget] = useState<number | null>(null);

  const searchRef = useRef<HTMLInputElement>(null);

  const dragColumn = useRef<Column | null>(null);

  const syncing = useRef(false);

  const [debounced, setDebounced] = useState(search);

  useEffect(() => { const timer = setTimeout(() => {setDebounced(search.trim()); setPage(1);}, 300); return () => clearTimeout(timer); }, [search]);

  useEffect(() => { setPrefs(loadPreferences(preferenceKey)); setSelected([]); setDetailId(null); setEditing(null); }, [preferenceKey]);

  useEffect(() => { localStorage.setItem(preferenceKey, JSON.stringify(prefs)); }, [prefs, preferenceKey]);

  useEffect(() => { const onKey = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "f") {e.preventDefault(); searchRef.current?.focus();} }; window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey); }, []);

  const queryParams = useMemo(() => ({search: debounced, relationship: ["All", "Favorites", "Recently added", "Recently updated", "Trash"].includes(tab) ? "" : tab, deleted: tab === "Trash", recent: tab === "Recently updated", created_recent: tab === "Recently added", page, per_page: 30, sort, direction, filters: JSON.stringify(filters), match, ...(tab === "Favorites" ? {ids: prefs.favorites.join(",") || "0"} : {})}), [debounced, tab, page, sort, direction, filters, match, prefs.favorites]);

  const query = useQuery<Directory>({queryKey: ["universal-contacts", scope, queryParams], queryFn: async () => (await api.get(root, {params: queryParams})).data, staleTime: 60000});

  useRecordView<Directory>(root, queryParams, value => qc.setQueryData(["universal-contacts", scope, queryParams], value), () => {setEditing(null); setDetailId(null); setSelected([]); setConversion(null); setMerge(null); setCorrection(null); setConfirm(null); setTagging(null); qc.removeQueries({queryKey: ["universal-contacts", scope]}); qc.removeQueries({queryKey: ["universal-contact", scope]});});

  const detail = useQuery<Detail>({queryKey: ["universal-contact", scope, detailId], enabled: detailId !== null, queryFn: async () => (await api.get(`${root}/${detailId}`)).data, staleTime: 30000});

  const duplicateQuery = useQuery<{items: Contact[]}>({queryKey: ["contact-duplicates", scope, merge?.id], enabled: !!merge, queryFn: async () => (await api.get(`${root}/${merge?.id}/duplicates`)).data});

  const data = query.data;

  const rows = data?.items || [];

  const canManage = data?.canManage || false;

  const refresh = async () => {await Promise.all([qc.invalidateQueries({queryKey: ["universal-contacts"]}), qc.invalidateQueries({queryKey: ["universal-contact"]}), qc.invalidateQueries({queryKey: ["contact-duplicates"]}), qc.invalidateQueries({queryKey: ["contact-financial"]})]);};

  useEffect(() => { setSelected([]); }, [tab, debounced, page, filters, match]);

  const changeTab = (value: string) => {setTab(value); setPage(1); setParams(current => {const next = new URLSearchParams(current); next.delete("page"); next.set("entity", value === "Lead" ? "leads" : "contacts"); if (value === "Trash") next.set("view", "deleted"); else next.delete("view"); return next;}, {replace: true});};

  const run = async (task: () => Promise<unknown>, success: string) => {setBusy(true); setError(""); setNotice(""); try {await task(); setNotice(success); setSelected([]); await refresh(); return true;} catch (e) {setError(dealError(e)); return false;} finally {setBusy(false);} };

  const sync = async () => {if (syncing.current) return; syncing.current = true; await run(async () => {let result: {linked: number; hasMore: boolean}; do {result = (await api.post(`${root}/backfill`)).data;} while (result.hasMore);}, "Existing business records linked. Employee and user directories retain their own access controls."); syncing.current = false;};
  useEffect(() => {
    if (title !== "Relationship Hub" || !canManage || linked.current) return;
    linked.current = true;
    void sync();
  }, [title, canManage]);

  const favorite = (id: number) => setPrefs(p => ({...p, favorites: p.favorites.includes(id) ? p.favorites.filter(x => x !== id) : [...p.favorites, id]}));

  const copy = async (text: string) => {try {await navigator.clipboard.writeText(text); setNotice("Copied to clipboard.");} catch {setError("Clipboard access is unavailable.");}};

  const openConvert = async (row: Contact) => {setError(""); try { const item: Detail = (await api.get(`${root}/${row.id}`)).data; const lead = item.leads.find(x => !x.converted); if (!lead) {setError("No accessible unconverted lead is linked to this contact."); return;} setCustomerType(row.organization ? "Business" : "Individual"); setConversion({lead, contact: row}); } catch(e) {setError(dealError(e));} };

  const bulkConvert = async () => {await run(async () => {for (const row of rows.filter(x => selected.includes(x.id))) {const item: Detail = (await api.get(`${root}/${row.id}`)).data; const lead = item.leads.find(x => !x.converted); if (!lead) continue; await api.post(`${root}/convert`, {leadId: lead.id, existingContactId: row.id, customerType: row.organization ? "Business" : "Individual"});}}, "Selected eligible leads converted. Existing histories and identities were preserved.");};

  const exportCsv = () => run(async () => { const response = await api.get(`${root}/export`, {params: queryParams, responseType: "blob"}); const url = URL.createObjectURL(response.data); const a = document.createElement("a"); a.href = url; a.download = "contacts.csv"; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }, "Contacts exported.");

  const resize = (event: React.PointerEvent, key: Column) => {event.preventDefault(); const start = event.clientX; const initial = prefs.widths[key] || (key === "name" || key === "tags" ? 240 : 180); const move = (e: PointerEvent) => setPrefs(p => ({...p, widths: {...p.widths, [key]: Math.max(120, initial + e.clientX - start)}})); const up = () => {window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up);}; window.addEventListener("pointermove", move); window.addEventListener("pointerup", up, {once: true});};

  function cell(row: Contact, column: Column) {

    if (column === "gstNumber") return row.gstNumber || "—";

    if (column === "bankAccounts") return row.bankAccountCount || "—";

    if (column === "upi") return row.upiCount || "—";

    if (column === "name") return <button className="uc-identity" onClick={() => setDetailId(row.id)}><span className="uc-avatar">{row.name.split(/\s+/).slice(0, 2).map(x => x[0]).join("")}</span><span><strong>{row.name}</strong><small>{row.organization || "Individual"}</small></span></button>;

    if (column === "tags") return <Badges tags={row.tags} />;

    if (column === "email" || column === "phone") return <span className="uc-copy">{column === "phone" ? <PhoneActions value={row.phone} record={row} /> : row[column] || "—"}{row[column] && <button title={`Copy ${column}`} aria-label={`Copy ${column} for ${row.name}`} onClick={() => void copy(row[column]!)}><Copy size={13}/></button>}</span>;

    if (column === "status") return <span className={`uc-status ${row.status === "Active" ? "is-active" : ""}`}>{row.status}</span>;

    if (column === "owner") return row.ownerId ? <span className="text-muted-foreground">User #{row.ownerId}</span> : "Unassigned";

    return date(column === "updated" ? row.updatedAt : column === "created" ? row.createdAt : row[column]);

  }

  function actions(row: Contact) {
    const blocked = communicationBlocked(row);
    const phone = whatsappNumber(row);
    const messageDisabled = blocked || !canManage || tab === "Trash";

    return <div className="uc-row-actions">

      <button title="Favorite" aria-label={`Favorite ${row.name}`} onClick={() => favorite(row.id)}><Star size={15} fill={prefs.favorites.includes(row.id) ? "currentColor" : "none"}/></button>

      <IconActionButton action="view" aria-label={`View ${row.name}`} tooltip="View contact details" onClick={() => setDetailId(row.id)}/>
      {tab !== "Trash" && <>
        <button aria-label={`Edit ${row.name}`} title="Edit relationship" disabled={!canManage} onClick={()=>setEditing(row)}><Pencil size={15}/></button>
        <button aria-label={`Email ${row.name}`} title={row.email ? "Send email" : "Add an email address first"} disabled={messageDisabled || !row.email} onClick={()=>setCompose({record:row,channel:"email"})}><Mail size={15}/></button>
        <button aria-label={`WhatsApp ${row.name}`} title={phone ? "Send WhatsApp message" : "Add a phone number and country code first"} disabled={messageDisabled || !phone} onClick={()=>setCompose({record:row,channel:"whatsapp"})}><WhatsAppIcon width={15} height={15}/></button>
        <button aria-label={`SMS ${row.name}`} title="Send SMS" disabled={messageDisabled || !phone} onClick={()=>setCompose({record:row,channel:"sms"})}><MessageSquare size={15}/></button>
        <button aria-label={`Call ${row.name}`} title="Call" disabled={blocked || !phone} onClick={()=>{window.location.href=`tel:+${phone}`;}}><Phone size={15}/></button>
        <button aria-label={`Manage tags for ${row.name}`} title="Manage relationship tags" disabled={!canManage} onClick={()=>{setNewTag("");setTagging([row.id]);}}><Tag size={15}/></button>
        <button aria-label={`Delete ${row.name}`} title="Move to trash" disabled={!canManage} onClick={()=>setConfirm({action:"trash",ids:[row.id]})}><Trash2 size={15}/></button>
      </>}

      {canManage && (tab === "Trash" ? <>

        <ActionButton action="complete" tooltip="Restore this contact from Trash" onClick={() => setConfirm({action:"restore",ids:[row.id]})}>Restore</ActionButton>

        {data?.canPermanentlyDelete && <MoreActionsMenu label={`More actions for ${row.name}`} actions={[{id:"permanent",kind:"delete",label:"Permanently delete",danger:true,onSelect:()=>{setError("");setConfirm({action:"permanent",ids:[row.id]});}}]}/>}

      </> : <>

        {data?.canConvert && !!row.unconvertedLeadIds?.length && <ActionButton action="convert" tooltip="Convert this lead into a customer" onClick={() => void openConvert(row)}>Convert to customer</ActionButton>}

        <MoreActionsMenu label={`More actions for ${row.name}`} actions={[

          {id:"edit",kind:"edit",onSelect:()=>setEditing(row)},

          {id:"tag",kind:"tag",label:"Manage tags",onSelect:()=>{setNewTag("");setTagging([row.id]);}},

          {id:"merge",kind:"merge",label:"Merge duplicates",onSelect:()=>{setMergeTarget(null);setMerge(row);}},

          {id:"workspace",kind:"view",label:"Full CRM workspace",href:`/crm/contacts/${row.id}`},

          {id:"trash",kind:"delete",label:"Move to trash",danger:true,onSelect:()=>setConfirm({action:"trash",ids:[row.id]})},

        ]}/>

      </>)}

    </div>;

  }



  return <main className="uc-page">
    {compose && <Suspense fallback={<p role="status">Loading message composer…</p>}>{compose.channel === "whatsapp" ? <WhatsAppComposer record={compose.record} close={()=>setCompose(null)}/> : compose.channel === "email" ? <EmailComposer kind="contacts" record={{...compose.record,full_name:compose.record.name,phone_country_code:compose.record.phoneCountryCode}} onClose={()=>setCompose(null)} onDone={()=>{setCompose(null);void refresh();}}/> : <MessageComposer kind="contacts" initialChannel={compose.channel} record={{...compose.record,full_name:compose.record.name,phone_country_code:compose.record.phoneCountryCode}} onClose={()=>setCompose(null)} onDone={()=>{setCompose(null);void refresh();}}/>}</Suspense>}

    <header className="uc-heading"><div><span className="uc-eyebrow"><Users size={14}/> Business relationships</span><h1>{title}</h1><p>Manage contacts, leads, potential customers, vendors and customers. Edit relationships and send messages without leaving this page.</p></div><div className="uc-toolbar">{canManage && <><Button variant="outline" disabled={busy || tab === "Trash" || !data?.canExport} onClick={() => void exportCsv()}><Download size={15}/> Export</Button><CRMDataTransfer entity="contacts" importOnly importLabel="Import contacts" onImported={() => void refresh()}/><Button onClick={() => setEditing("new")}><Plus size={16}/> Add relationship</Button></>}<details><summary className="uc-icon-button" aria-label="More directory actions"><MoreHorizontal size={18}/></summary><div className="uc-menu">{canManage && <button disabled={busy} onClick={() => void sync()}>Link existing business records</button>}<Link to="/crm/records?entity=deals">Deal records</Link><Link to="/crm/records?entity=companies">Business accounts</Link><Link to="/crm/duplicates">Duplicate management</Link></div></details></div></header>

    <div className="uc-stats">{[["total", "Total contacts", "All"], ["Lead", "Leads", "Lead"], ["Customer", "Customers", "Customer"], ["Vendor", "Vendors", "Vendor"], ["Partner", "Partners", "Partner"], ["recent", "Added this week", "Recently added"]].map(([key, label, value]) => <button key={key} onClick={() => changeTab(value)}><span>{label}</span><strong>{data ? (data.stats[key] || 0).toLocaleString() : "—"}</strong><span className={`uc-stat-mark uc-${badgeClass(key)}`}/></button>)}</div>

    <section className="uc-directory"><nav className="uc-tabs" aria-label="Contact views">{["All", "Lead", "Prospect", "Customer", "Vendor", "Partner", "Favorites", "Recently added", "Recently updated", "Trash"].map(value => <button key={value} aria-current={tab === value ? "page" : undefined} className={tab === value ? "is-selected" : ""} onClick={() => changeTab(value)}>{value === "All" ? "Everyone" : value === "Prospect" ? "Potential customers" : value === "Trash" ? <><Trash2 size={13}/> Trash</> : value}</button>)}</nav>

      <div className="uc-controls"><div className="uc-search"><Search size={16}/><input ref={searchRef} value={search} onChange={e => setSearch(e.target.value)} placeholder="Search name, company, email or phone…" aria-label="Search contacts"/><kbd>Ctrl Shift F</kbd></div><Button size="sm" variant={showFilters ? "default" : "outline"} onClick={() => setShowFilters(!showFilters)}><Settings2 size={14}/> Filters {filters.length > 0 && `(${filters.length})`}</Button><details><summary className="uc-small-button">Columns</summary><div className="uc-menu uc-columns">{columns.map(column => <label key={column}><input type="checkbox" checked={prefs.columns.includes(column)} disabled={column === "name"} onChange={e => setPrefs(p => ({...p, columns: e.target.checked ? [...p.columns, column] : p.columns.filter(x => x !== column)}))}/>{titles[column]}</label>)}</div></details><div className="uc-view-toggle"><button aria-label="Table view" aria-pressed={!prefs.card} onClick={() => setPrefs(p => ({...p, card: false}))}><List size={16}/></button><button aria-label="Card view" aria-pressed={prefs.card} onClick={() => setPrefs(p => ({...p, card: true}))}><Grid2X2 size={16}/></button></div><button aria-label="Refresh contacts" className="uc-icon-button" onClick={() => void refresh()}><RefreshCw size={16} className={query.isFetching ? "animate-spin" : ""}/></button></div>

      {showFilters && <div className="uc-filters"><div className="flex flex-wrap items-center gap-2"><span className="text-sm">Match</span><NativeSelect value={match} onChange={e => {setMatch(e.target.value); setPage(1);}}><option value="and">All conditions (AND)</option><option value="or">Any condition (OR)</option></NativeSelect><Button size="sm" variant="outline" onClick={() => setFilters(f => [...f, {field: "name", operator: "contains", value: ""}])} disabled={filters.length >= 12}>Add condition</Button><Button size="sm" variant="ghost" onClick={() => {setFilters([]); setPage(1);}}>Clear</Button><Button size="sm" variant="outline" onClick={() => {const name = window.prompt("Name this filter preset"); if (name?.trim()) setPrefs(p => ({...p, presets: [...p.presets.filter(x => x.name !== name.trim()), {name: name.trim(), filters, match}]}));}}>Save preset</Button><NativeSelect aria-label="Saved filter presets" value="" onChange={e => {const preset = prefs.presets.find(x => x.name === e.target.value); if (preset) {setFilters(preset.filters); setMatch(preset.match); setPage(1);}}}><option value="">Saved presets</option>{prefs.presets.map(x => <option key={x.name}>{x.name}</option>)}</NativeSelect></div>{filters.map((condition, index) => <div key={index} className="flex flex-wrap gap-2"><NativeSelect aria-label={`Filter ${index + 1} field`} value={condition.field} onChange={e => setFilters(f => f.map((x, i) => i === index ? {...x, field: e.target.value} : x))}>{["name", "email", "phone", "organization", "status", "tag", "owner"].map(x => <option key={x}>{x}</option>)}</NativeSelect><NativeSelect aria-label={`Filter ${index + 1} operator`} value={condition.operator} onChange={e => setFilters(f => f.map((x, i) => i === index ? {...x, operator: e.target.value} : x))}>{["contains", "equals", "empty"].map(x => <option key={x}>{x}</option>)}</NativeSelect><Input aria-label={`Filter ${index + 1} value`} value={condition.value} disabled={condition.operator === "empty"} onChange={e => setFilters(f => f.map((x, i) => i === index ? {...x, value: e.target.value} : x))}/><button aria-label="Remove condition" onClick={() => setFilters(f => f.filter((_, i) => i !== index))}><X size={16}/></button></div>)}</div>}

      {selected.length > 0 && <div className="uc-selection"><strong>{selected.length} selected</strong><CompactActions><button onClick={() => setSelected([])}>Clear selection</button>

{canManage && <>{tab !== "Trash" && <><button onClick={() => {setNewTag(""); setTagging(selected);}}>Add relationship tag</button><button disabled={busy} onClick={() => void run(() => api.post(`${root}/bulk`, {ids: selected, action: "status", status: "Inactive"}), "Contacts marked inactive.")}>Mark inactive</button>{tab === "Lead" && data?.canConvert && <button disabled={busy} onClick={() => void bulkConvert()}>Convert to customers</button>}</>}<button onClick={() => setConfirm({action: tab === "Trash" ? "restore" : "trash", ids: selected})}>{tab === "Trash" ? "Restore" : "Move to trash"}</button></>}</CompactActions></div>}

      {(error || query.error) && <p role="alert" className="uc-alert uc-error">{error || dealError(query.error)}</p>}{notice && <p role="status" className="uc-alert uc-success"><Check size={16}/>{notice}</p>}

      {query.isPending ? <div role="status" className="uc-empty"><RefreshCw className="animate-spin"/><h2>Loading your contacts</h2></div> : query.isError ? <div className="uc-empty"><h2>Contacts could not be loaded</h2><Button variant="outline" onClick={() => void query.refetch()}>Try again</Button></div> : !rows.length ? <div className="uc-empty"><Users size={34}/><h2>{tab === "Trash" ? "Trash is empty" : "No contacts match this view"}</h2><p>{debounced || filters.length ? "Try another search or change your filters." : "Create a contact or link existing business records from the more actions menu."}</p>{canManage && tab === "All" && <Button disabled={busy} variant="outline" onClick={() => void sync()}>Link existing business records</Button>}</div> : prefs.card ? <div className="uc-cards">{rows.map(row => <article key={row.id}><label className="uc-card-check"><input aria-label={`Select ${row.name}`} type="checkbox" checked={selected.includes(row.id)} onChange={e => setSelected(ids => e.target.checked ? [...ids, row.id] : ids.filter(id => id !== row.id))}/></label>{cell(row, "name")}<Badges tags={row.tags}/><p>{row.email || "No email"}</p><p><PhoneActions value={row.phone} record={row} field="phone" /></p><div className="uc-card-meta">{cell(row, "status")}<span>Follow-up {date(row.nextFollowUp)}</span></div>{actions(row)}</article>)}</div> : <div className="uc-table-wrap"><GridTable pinActions gridId="apps/crm/UniversalContactsPage:relationships-v3" className="uc-table"><thead><tr><th className="uc-checkbox"><input type="checkbox" aria-label="Select all contacts on this page" checked={rows.length > 0 && selected.length === rows.length} onChange={e => setSelected(e.target.checked ? rows.map(x => x.id) : [])}/></th>{prefs.columns.map(column => <th key={column} style={{width: prefs.widths[column] || (column === "name" || column === "tags" ? 240 : 180), minWidth: prefs.widths[column] || (column === "name" || column === "tags" ? 240 : 180)}} draggable onDragStart={() => {dragColumn.current = column;}} onDragOver={e => e.preventDefault()} onDrop={() => {const source = dragColumn.current; if (source && source !== column) setPrefs(p => {const next = p.columns.filter(x => x !== source); next.splice(next.indexOf(column), 0, source); return {...p, columns: next};});}}><button onClick={() => {const next = ({gstNumber: "gstNumber", bankAccounts: "bankAccounts", upi: "upi", name: "name", status: "status", created: "created", updated: "updated", nextFollowUp: "followup"} as Record<string, string>)[column]; if (next) {setSort(next); setDirection(d => d === "asc" ? "desc" : "asc"); setPage(1);}}}>{titles[column]}<ArrowDownUp size={11}/></button><span role="separator" aria-label={`Resize ${titles[column]}`} className="uc-resize" onPointerDown={e => resize(e, column)}/></th>)}<th className="uc-actions-heading" style={{width:420}}>Quick actions</th></tr></thead><tbody>{rows.map(row => <tr key={row.id} onContextMenu={e => {e.preventDefault(); setDetailId(row.id);}}><td className="uc-checkbox"><input type="checkbox" aria-label={`Select ${row.name}`} checked={selected.includes(row.id)} onChange={e => setSelected(ids => e.target.checked ? [...ids, row.id] : ids.filter(id => id !== row.id))}/></td>{prefs.columns.map(column => <td key={column}>{cell(row, column)}</td>)}<td>{actions(row)}</td></tr>)}</tbody></GridTable></div>}

      <footer className="uc-pagination"><span>{(data?.total || 0).toLocaleString()} contacts · Page {page} of {Math.max(1, Math.ceil((data?.total || 0) / 30))}{query.isFetching && !query.isPending ? " · Updating…" : ""}</span><div><Button size="sm" variant="outline" disabled={page === 1 || query.isFetching} onClick={() => setPage(p => p - 1)}>Previous</Button><Button size="sm" variant="outline" disabled={page * 30 >= (data?.total || 0) || query.isFetching} onClick={() => setPage(p => p + 1)}>Next</Button></div></footer>

    </section>

    {editing && <ContactEditor key={editing === "new" ? "new" : editing.id} contact={editing} classifications={data?.classifications || []} onClose={() => setEditing(null)} onSave={async (values,keepOpen) => {const success = await run(() => editing === "new" ? api.post(root, values) : api.patch(`${root}/${editing.id}`, values), "Contact saved."); if (success&&!keepOpen) setEditing(null); return success;}} error={error}/>}

    <Dialog open={!!confirm} onOpenChange={open => {if (!open && !busy) setConfirm(null);}}><DialogContent><DialogHeader><DialogTitle>{confirm?.action === "permanent" ? "Permanently delete contact?" : confirm?.action === "restore" ? "Restore contacts?" : "Move contacts to trash?"}</DialogTitle></DialogHeader><p className="text-sm text-muted-foreground">{confirm?.action === "permanent" ? "This cannot be undone. Contacts linked to business history or transactions are protected and cannot be permanently deleted." : `${confirm?.ids.length} contact(s). Business history, transactions, employee records and login accounts are preserved.`}</p>{error && <p role="alert" className="text-destructive">{error}</p>}<div className="flex justify-end gap-2"><Button variant="outline" disabled={busy} onClick={() => setConfirm(null)}>Cancel</Button><Button disabled={busy} onClick={() => void run(() => confirm?.action === "permanent" ? api.delete(`${root}/${confirm.ids[0]}/permanent`) : api.post(`${root}/bulk`, confirm), "Contacts updated.").then(ok => {if (ok) setConfirm(null);})}>{busy ? "Saving…" : "Confirm"}</Button></div></DialogContent></Dialog>

    <Dialog open={tagging !== null} onOpenChange={open => {if (!open) setTagging(null);}}><DialogContent><DialogHeader><DialogTitle>Add a relationship tag</DialogTitle></DialogHeader><Input list="uc-tag-options" maxLength={40} placeholder="Customer, Vendor, Partner, or a custom relationship" value={newTag} onChange={e => setNewTag(e.target.value)}/><datalist id="uc-tag-options">{data?.classifications.map(x => <option key={x}>{x}</option>)}</datalist><p className="text-xs text-muted-foreground">Relationship tags describe business connections. Access roles are managed separately.</p>{error && <p role="alert" className="text-destructive">{error}</p>}<Button disabled={busy || !newTag.trim()} onClick={() => void run(() => api.post(`${root}/bulk`, {ids: tagging, action: "tag", tag: newTag.trim()}), "Relationship tag added.").then(ok => {if(ok) setTagging(null);})}>Apply to {tagging?.length} contact(s)</Button></DialogContent></Dialog>

    <Dialog open={!!conversion} onOpenChange={open => {if (!open) setConversion(null);}}><DialogContent><DialogHeader><DialogTitle>Convert to customer</DialogTitle></DialogHeader><div className="uc-conversion-preview"><strong>{conversion?.contact.name}</strong><p>{conversion?.contact.email} <PhoneActions value={conversion?.contact.phone} record={conversion?.contact} field="phone" /></p><p>{conversion?.contact.organization}</p><Badges tags={conversion?.contact.tags || []}/></div><p className="text-sm text-muted-foreground">Reuse contact #{conversion?.contact.id}. The original lead, notes, deals, attachments and follow-ups remain linked. The lead must satisfy its configured qualification rules.</p><label className="text-sm">Customer type<NativeSelect value={customerType} onChange={e => setCustomerType(e.target.value)}><option>Individual</option><option>Business</option></NativeSelect></label>{error && <p role="alert" className="text-destructive">{error}</p>}<Button disabled={busy} onClick={() => void run(() => api.post(`${root}/convert`, {leadId: conversion?.lead.id, existingContactId: conversion?.contact.id, customerType}), "Lead converted to customer.").then(ok => {if (ok) setConversion(null);})}>{busy ? "Converting…" : "Confirm conversion"}</Button></DialogContent></Dialog>

    <Dialog open={!!correction} onOpenChange={open => {if (!open && !busy) setCorrection(null);}}><DialogContent><DialogHeader><DialogTitle>Correct an erroneous conversion</DialogTitle></DialogHeader><p className="text-sm text-muted-foreground">Return {correction?.name} to Qualified. The original conversion evidence and business history remain intact. Linked transactions block this correction.</p><label className="text-sm">Reason for correction<Input minLength={10} maxLength={1000} value={correctionReason} onChange={e => setCorrectionReason(e.target.value)} placeholder="Explain why this conversion was incorrect"/></label>{error && <p role="alert" className="text-destructive">{error}</p>}<Button disabled={busy || correctionReason.trim().length < 10} onClick={() => void run(() => api.post(`${root}/leads/${correction?.id}/correct-conversion`, {reason: correctionReason.trim()}), "Conversion corrected; history preserved.").then(ok => {if (ok) setCorrection(null);})}>Confirm correction</Button></DialogContent></Dialog>

    <Dialog open={!!merge} onOpenChange={open => {if (!open) setMerge(null);}}><DialogContent><DialogHeader><DialogTitle>Review possible duplicates</DialogTitle></DialogHeader><p className="text-sm">Keep <strong>{merge?.name}</strong> (#{merge?.id}) as the canonical contact. Matched email or phone is evidence for review; verify that both records are the same person.</p>{duplicateQuery.isPending ? <p>Checking duplicates…</p> : duplicateQuery.error ? <p role="alert">{dealError(duplicateQuery.error)}</p> : duplicateQuery.data?.items.length ? duplicateQuery.data.items.map(row => <label className="uc-duplicate" key={row.id}><input type="radio" name="merge-target" checked={mergeTarget === row.id} onChange={() => setMergeTarget(row.id)}/><span><strong>{row.name}</strong><small>#{row.id} · {row.email} · <PhoneActions value={row.phone} record={row} field="phone" /></small><Badges tags={row.tags}/></span></label>) : <p className="text-muted-foreground">No matching email or phone found.</p>}<p className="text-xs text-muted-foreground">Business references move to the survivor and source records remain in the audit trail. Linked employee and user identities require a separate authorized review.</p>{error && <p role="alert" className="text-destructive">{error}</p>}<Button disabled={busy || !mergeTarget} onClick={() => void run(() => api.post("/crm/duplicates/merge", {entityType: "contacts", winnerId: merge?.id, loserIds: [mergeTarget], allowUndetected: true}), "Duplicate contact merged; history preserved.").then(ok => {if(ok) setMerge(null);})}>Confirm merge</Button></DialogContent></Dialog>

    {detailId !== null && !editing && <PersonRecordPreview key={detailId} record={detail.data || data?.items.find(contact => contact.id === detailId) || { id: detailId, name: "Contact profile" }} related={detail.data?.related?.related} loading={detail.isPending} error={detail.error ? dealError(detail.error) : undefined} onClose={() => setDetailId(null)} fullProfileHref={`/crm/contacts/${detailId}`} financial={<FinancialDataTab contactId={detailId} readOnly/>} overview={<><Record360Workspace key={detailId} kind="contact" id={detailId}/>{detail.data && <><Badges tags={detail.data.tags}/><ContactCommunicationPanel id={detailId}/><BirthdayEditor id={detailId}/><section><h3>Contact information</h3><dl><dt>Email</dt><dd>{detail.data.email || "—"}</dd><dt>Phone</dt><dd><PhoneActions value={detail.data.phone} record={detail.data} field="phone" /></dd><dt>Owner</dt><dd>{detail.data.ownerId ? `User #${detail.data.ownerId}` : "Unassigned"}</dd><dt>Status</dt><dd>{detail.data.status}</dd><dt>Next follow-up</dt><dd>{date(detail.data.nextFollowUp)}</dd><dt>Last interaction</dt><dd>{date(detail.data.lastInteraction)}</dd></dl></section></>}</>} work={detail.data && <><section><h3>Linked lead history</h3>{detail.data.leads.length ? detail.data.leads.map(lead => <div key={lead.id} className="uc-linked"><Link to={`/crm/leads/${lead.id}`}>{lead.name} <small>#{lead.id} · {lead.status}</small></Link>{data?.canConvert && !lead.converted && <button onClick={() => {setCustomerType("Individual"); setConversion({lead, contact: detail.data!});}}>Convert to customer</button>}{data?.canConvert && lead.converted && <button onClick={() => {setCorrection(lead); setCorrectionReason(""); setError("");}}>Correct conversion</button>}</div>) : <p className="text-sm text-muted-foreground">No accessible lead records.</p>}</section>{Object.entries(detail.data.related?.related || {}).filter(([, value]) => Array.isArray(value) && value.length > 0).map(([key, value]) => <section key={key}><h3>{key.replace(/([A-Z])/g, " $1")}</h3>{(value as Record<string, unknown>[]).slice(0, 12).map((record, index) => <p className="uc-linked" key={String(record.id || index)}>{String(record.name || record.subject || record.title || (key === "notes" && record.body) || `Record #${record.id || index + 1}`)}</p>)}</section>)}</>} followUp={detail.data && <><section><h3>Notes & follow-ups</h3><p className="whitespace-pre-wrap text-sm">{detail.data.notes || "No notes recorded."}</p>{canManage && <Button variant="link" size="sm" onClick={() => setEditing(detail.data!)}>Add note / schedule follow-up</Button>}</section></>} activity={detail.data && <><CrmFieldsReadOnly entity="contacts" recordId={detail.data.id}/><section><h3>Notes & follow-ups</h3><p className="whitespace-pre-wrap text-sm">{detail.data.notes || "No notes recorded."}</p>{canManage && <Button variant="link" size="sm" onClick={() => setEditing(detail.data!)}>Add note / schedule follow-up</Button>}</section><section><h3>Recent activity</h3>{detail.data.related?.timeline?.length ? detail.data.related.timeline.slice(0, 20).map((event, index) => <div className="uc-linked" key={index}><span>{String(event.title || event.subject || event.event_type || "Activity")}</span></div>) : <p className="text-sm text-muted-foreground">No recent activity recorded.</p>}</section><p className="text-xs text-muted-foreground">Created {date(detail.data.createdAt)} · Updated {date(detail.data.updatedAt)}</p></>} actions={<>{detail.data?.phone && <a className="wf-button" href={`tel:${detail.data.phoneCountryCode || ""}${detail.data.phone}`}>Call</a>}{canManage && detail.data && <button onClick={() => setEditing(detail.data!)}>Edit contact</button>}</>} />}



  </main>;

}



function ContactEditor({contact, classifications, onClose, onSave, error}: {contact: Contact | "new"; classifications: string[]; onClose: () => void; onSave: (value: Record<string, unknown>,keepOpen?:boolean) => Promise<boolean>; error: string}) {
  const customFieldForm=useCrmFieldForm("contacts",contact === "new" ? "create" : "edit",contact === "new" ? undefined : contact.id);

  const [busy, setBusy] = useState(false);

  const record = contact === "new" ? null : contact;

  const [availability, setAvailability] = useState<BranchAvailabilityValue>();
  const [tab, setTab] = useState("Basic details");

  const [form, setForm] = useState({name: record?.name || "", email: record?.email || "", phone: record?.phone || "", phoneCountryCode: record?.phoneCountryCode || "+91", organization: record?.organization || "", status: record?.status || "Active", roles:record?.roles||record?.tags.filter(x=>["Lead","Prospect","Customer","Vendor","Supplier","Partner","Friend","Consultant","Dealer","Distributor","Investor","Other"].includes(x))||["Prospect"],lifecycleStage:record?.lifecycleStage||"Prospect",tags: record?.tags.filter(x=>!["Lead","Prospect","Customer","Vendor","Supplier","Partner","Friend","Consultant","Dealer","Distributor","Investor","Other"].includes(x)) || [], notes: record?.notes || "", nextFollowUp: record?.nextFollowUp ? new Date(new Date(record.nextFollowUp).getTime() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16) : "", version: record?.version, confirmShared:false, sharedReason:""});

  const [channels,setChannels]=useState<CommunicationEntry[]|undefined>();const [channelVersion,setChannelVersion]=useState<string>();

  const [companyId,setCompanyId]=useState(record?.companyId?String(record.companyId):"");

  const [custom, setCustom] = useState("");

  const [financialData, setFinancialData] = useState<FinancialData>();

  const field = (key: keyof typeof form, value: string) => setForm(f => ({...f, [key]: value}));
  const [customError,setCustomError]=useState("");
  const persist=async(keepOpen=false)=>{setBusy(true);setCustomError("");try{const success=await onSave({...form,customFields:customFieldForm.validate(),branch_availability:availability,financialData,companyId:companyId?Number(companyId):null,communication_channels:channels?transportEntries(channels):undefined,communication_version:channelVersion,nextFollowUp:form.nextFollowUp?new Date(form.nextFollowUp).toISOString():null},keepOpen);if(success&&keepOpen){customFieldForm.setValues({});setForm(f=>({...f,name:'',email:'',phone:'',organization:'',status:'Active',roles:['Prospect'],lifecycleStage:'Prospect',tags:[],notes:'',nextFollowUp:'',version:undefined,confirmShared:false,sharedReason:''}));setCompanyId('');setChannels(undefined);setChannelVersion(undefined);setFinancialData(undefined);setAvailability(undefined);setTab('Basic details');setNewFocus(v=>v+1);}}catch(e){setCustomError(dealError(e));}finally{setBusy(false);}};
  const [newFocus,setNewFocus]=useState(0);
  useEffect(()=>{if(newFocus)requestAnimationFrame(()=>document.querySelector<HTMLInputElement>('.uc-editor input[autofocus],.uc-editor input')?.focus());},[newFocus]);


  return <Dialog open onOpenChange={open => {if (!open && !busy) onClose();}}><DialogContent className="uc-editor"><DialogHeader><DialogTitle>{record ? "Edit contact" : "Add contact"}</DialogTitle></DialogHeader><nav className="uc-editor-tabs">{["Basic details", "Company & business", "Relationships & tags", "Financial data", "Notes & follow-ups"].map(x => <button key={x} className={tab === x ? "is-selected" : ""} onClick={() => setTab(x)}>{x}</button>)}</nav><form onSubmit={e=>{e.preventDefault();void persist();}}><div className="uc-editor-fields">{tab === "Basic details" && <><BranchAvailability value={availability} editing={!!record} resource={record ? {table:"crm_contacts",id:record.id} : undefined} disabled={busy} onChange={setAvailability}/><label>Full name *<Input autoFocus required maxLength={180} value={form.name} onChange={e => field("name", e.target.value)}/></label><CommunicationDraftEditor ownerId={record?.id} draft={channels!==undefined} value={channels||primaryEntries(form.email,form.phone,form.phoneCountryCode)} onChange={(entries,revision)=>{setChannels(entries);setChannelVersion(revision);const phone=entries.find(x=>x.kind==="phone"&&x.primary);const email=entries.find(x=>x.kind==="email"&&x.primary);setForm(f=>({...f,phone:phone?.value.replace(/[ ()-]/g,"")||"",phoneCountryCode:phone?.countryCode||"+91",email:email?.value||""}));}}/><label>Status<NativeSelect value={form.status} onChange={e => field("status", e.target.value)}><option>Active</option><option>Inactive</option></NativeSelect></label></>}{tab === "Financial data" && <FinancialDataTab contactId={record?.id} value={financialData} onChange={setFinancialData}/>} {tab === "Company & business" && <><label>Company<CompanySelect value={companyId} onChange={id=>setCompanyId(String(id||""))}/></label>{record && <Link className="text-sm underline" to={`/crm/contacts/${record.id}`}>Manage linked accounts, deals and quotations</Link>}</>}{tab === "Relationships & tags" && <><label>Lifecycle stage<NativeSelect value={form.lifecycleStage} onChange={e=>field("lifecycleStage",e.target.value)}>{["Prospect","Lead","Subscriber","Customer","Evangelist","Inactive","Other"].map(x=><option key={x}>{x}</option>)}</NativeSelect></label><p className="text-sm">Business roles</p><div className="uc-tag-options">{[...new Set([...classifications, ...form.roles])].map(tag => <button key={tag} type="button" aria-pressed={form.roles.includes(tag)} className={`uc-badge uc-${badgeClass(tag)}`} onClick={() => setForm(f => ({...f, roles: f.roles.includes(tag) ? f.roles.filter(x => x !== tag) : [...f.roles, tag]}))}>{form.roles.includes(tag) && <Check size={12}/>} {tag}</button>)}</div><div className="flex gap-2"><Input placeholder="Custom tag" maxLength={40} value={custom} onChange={e => setCustom(e.target.value)}/><Button type="button" variant="outline" onClick={() => {if (custom.trim()) setForm(f => ({...f, tags: [...new Set([...f.tags, custom.trim()])]})); setCustom("");}}>Add tag</Button></div><p className="text-xs text-muted-foreground">Employee information and user access roles remain in their authorized directories.</p></>}{tab === "Notes & follow-ups" && <><label>Notes<textarea className="uc-textarea" rows={5} maxLength={10000} value={form.notes} onChange={e => field("notes", e.target.value)}/></label><label>Next follow-up<Input type="datetime-local" value={form.nextFollowUp} onChange={e => field("nextFollowUp", e.target.value)}/></label></>}</div><SharedNumberConfirmation phone={form.phone} countryCode={form.phoneCountryCode} email={form.email} confirmed={form.confirmShared} reason={form.sharedReason} onChange={(a,b)=>setForm(f=>({...f,confirmShared:a,sharedReason:b}))}/>{error && <p role="alert" className="uc-alert uc-error">{error}</p>}<CrmRecordFields state={customFieldForm}/>{customError&&<p role="alert" className="text-destructive">{customError}</p>}<footer className="flex justify-end gap-2"><Button type="button" variant="outline" disabled={busy} onClick={onClose}>Cancel</Button>{!record&&<Button type="button" variant="outline" disabled={busy||!form.name.trim()} onClick={()=>void persist(true)}>Save & new</Button>}<Button type="submit" disabled={busy || !form.name.trim()}>{busy ? "Saving…" : "Save contact"}</Button></footer></form></DialogContent></Dialog>;

}
