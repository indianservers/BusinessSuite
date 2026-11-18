import { syncScope } from "@/shared/record-sync/store";
import { useMobileContext } from "@/components/mobile/useMobileContext";
import { useMobile } from "@/components/mobile/useMobile";
import { MobileDisclosure } from "@/components/mobile/MobilePrimitives";
import "./task-types-mobile.css";
import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import { standardRecordGroups } from "@/shared/data-grid/record-group-fields";
import { NativeSelect } from "@/components/ui/native-select";
import CompactForm from "@/components/forms/CompactForm";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CheckSquare, Diamond, ClipboardList, Calendar, Bug, Building, Package, Target, MessageSquare, Wallet } from "lucide-react";
import { api } from "@/services/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { workspaceError } from "./workspaceTypes";
const icons = { task: CheckSquare, milestone: Diamond, form: ClipboardList, meeting: Calendar, bug: Bug, account: Building, asset: Package, goal: Target, request: MessageSquare, finance: Wallet };
type Type = { id: number | null; name: string; plural_name?: string; description: string; category: string; icon: keyof typeof icons; color: string; default_priority: string; archived: boolean; builtin: boolean; usage: number };
const initial = { name: "", plural_name: "", description: "", category: "General", icon: "task", color: "#7c3aed", default_priority: "Medium", archived: false };
const presets = [
  ["Milestone", "Delivery", "milestone", "Track a key delivery checkpoint."], ["Form Response", "Operations", "form", "Track an intake submission and follow-up."], ["Item", "Operations", "asset", "Track a general work item."], ["Meeting Note", "Operations", "meeting", "Capture decisions and meeting actions."],
  ["Account", "Sales & CRM", "account", "Coordinate client-account work."], ["Asset", "Operations", "asset", "Coordinate asset-related work."], ["Campaign", "Marketing", "goal", "Plan campaign deliverables."], ["Content", "Marketing", "task", "Prepare and review content."], ["Deal", "Sales & CRM", "finance", "Coordinate commercial work."], ["Goal", "Strategy", "goal", "Track work toward a goal."], ["Initiative", "Strategy", "goal", "Coordinate a strategic initiative."], ["Key Result", "Strategy", "goal", "Track work toward a measurable outcome."], ["Lead", "Sales & CRM", "account", "Coordinate lead follow-up."], ["Objective", "Strategy", "goal", "Organize objective-related work."], ["Person", "Operations", "account", "Coordinate people-related work."], ["Project", "Delivery", "task", "Track project-related coordination."], ["Request", "Support", "request", "Triage and fulfil a request."], ["Resource", "Operations", "asset", "Coordinate resource-related work."], ["User Story", "Software", "task", "Describe an end-user requirement."],
  ["VAT Return", "Practice", "finance", "Prepare, review and submit a VAT return."], ["Audit Engagement", "Practice", "form", "Coordinate audit work and evidence."], ["Transfer Pricing", "Practice", "finance", "Prepare transfer-pricing deliverables."], ["Client Query", "Practice", "request", "Track information requested from a client."], ["Review Sign-off", "Practice", "milestone", "Track reviewer approval work."], ["Billing Follow-up", "Practice", "finance", "Coordinate billing follow-up work."],
];
export default function TaskTypesPage() {
  const scope=useMobileContext();return <TaskTypesContent key={scope}/>;
}
function TaskTypesContent() {
  const navigate = useNavigate();
  const phone=useMobile(480);
  const saving=useRef(false),mounted=useRef(true),ownerScope=useRef(syncScope());
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  const owns=(owned:boolean,scope:string)=>!owned||mounted.current&&scope===syncScope();
  const [completed,setCompleted]=useState(0),[formRevision,setFormRevision]=useState(0);
  const savedIntent=useRef<{name:string;configureFields:boolean}|null>(null);
  const [awaitingRead,setAwaitingRead]=useState(false);
  const [types, setTypes] = useState<Type[]>([]);
  const [manage, setManage] = useState(false);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [archived, setArchived] = useState(false);
  const [draft, setDraft] = useState(initial);
  const [editing, setEditing] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [ready,setReady]=useState(false),[sourceError,setSourceError]=useState(false),[sourceRevision,setSourceRevision]=useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  async function load() { const owned=phone,scope=syncScope();const { data } = await api.get<{ types: Type[]; can_manage: boolean }>("/project-management/task-types");if(!owns(owned,scope))return; setTypes(data.types); setManage(data.can_manage);setReady(true); }
  useEffect(() => { let active = true;const owned=phone,scope=syncScope();const current=()=>active&&owns(owned,scope);setLoading(true); api.get<{ types: Type[]; can_manage: boolean }>("/project-management/task-types").then(({ data }) => { if (current()) { setTypes(data.types); setManage(data.can_manage);setReady(true);setSourceError(false); } }).catch(error => { if (current()) {setError(workspaceError(error));setSourceError(true);} }).finally(() => { if (current()) setLoading(false); }); return () => { active = false; }; }, [sourceRevision]);
  function finishSaved(){
    const intent=savedIntent.current;if(!intent||!mounted.current||ownerScope.current!==syncScope())return;
    savedIntent.current=null;setAwaitingRead(false);setDraft(initial);setEditing(null);setNotice("Task type saved");setCompleted(v=>v+1);
    if(intent.configureFields)navigate(`/pms/custom-fields?taskType=${encodeURIComponent(intent.name.trim())}`);
  }
  async function reloadSaved(){
    if(saving.current||!savedIntent.current||ownerScope.current!==syncScope())return;
    const scope=syncScope();
    saving.current=true;setBusy(true);setError("");
    try{await load();finishSaved();}catch(error){if(owns(true,scope))setError(workspaceError(error));}finally{if(owns(true,scope)){saving.current=false;setBusy(false);}}
  }
  async function save(payload: typeof initial, id: number | null = null, configureFields = false) {
    if (busy||phone&&(saving.current||savedIntent.current||ownerScope.current!==syncScope()||!manage)) return; if(phone)saving.current=true; setBusy(true); setError(""); setNotice("");
    const owned=phone,scope=syncScope();
    try {
      if (id) await api.put(`/project-management/task-types/${id}`, payload); else await api.post("/project-management/task-types", payload);
      if(!owns(owned,scope))return;
      if(owned){savedIntent.current={name:payload.name,configureFields};setAwaitingRead(true);setFormRevision(v=>v+1);await load();finishSaved();}
      else{setDraft(initial);setEditing(null);setNotice("Task type saved");await load();if(configureFields)navigate(`/pms/custom-fields?taskType=${encodeURIComponent(payload.name.trim())}`);}
    }
    catch (error) { if(owns(owned,scope))setError(workspaceError(error)); } finally { if(owns(owned,scope)){saving.current=false;setBusy(false);} }
  }
  function cancelEdit(){
    if(phone){
      if(saving.current||savedIntent.current)return;
      const original=types.find(type=>type.id===editing);
      const baseline=editing?{...initial,...original,plural_name:original?.plural_name||""}:initial;
      const changed=(Object.keys(initial) as (keyof typeof initial)[]).some(key=>draft[key]!==baseline[key]);
      if(changed&&!window.confirm("Discard changes to this task type?"))return;
      setFormRevision(v=>v+1);setError("");setNotice("");
    }
    setEditing(null);setDraft(initial);
  }
  function closePhoneDraft(){
    if(savedIntent.current)return;
    setEditing(null);setDraft(initial);setError("");
  }
  const locked=busy||phone&&awaitingRead;
  const recovery=phone&&awaitingRead&&<div><p role="status">Task type saved. Reload the list before continuing.</p><Button type="button" disabled={busy} onClick={()=>void reloadSaved()}>Reload saved task types</Button></div>;
  const categories = [...new Set([...types.map(type => type.category), ...presets.map(preset => preset[1])])].sort();
  const visible = types.filter(type => (archived || !type.archived) && (!category || type.category === category) && `${type.name} ${type.description}`.toLowerCase().includes(search.trim().toLowerCase()));
  const Icon = icons[draft.icon as keyof typeof icons] || CheckSquare;
  const control = "h-10 rounded-md border bg-background px-3 text-sm";
  return <main className="task-types-page mx-auto max-w-6xl space-y-5"><header><h1 className="page-title">Task Types</h1><p className="page-description">Give different work a clear identity, purpose and default priority. Types classify PMS tasks; they do not create CRM accounts, invoices or other module records.</p></header><Link className="text-sm text-primary underline" to="/pms/settings">Settings</Link>
    {error && <p role="alert" className="text-destructive">{error}</p>}{notice && <p role="status">{notice}</p>}{recovery}{phone&&sourceError&&<Button variant="outline" disabled={loading||busy} onClick={()=>{setError("");setSourceRevision(v=>v+1);}}>Retry task types</Button>}
    <div className="task-types-filters flex flex-wrap items-center gap-3"><Input className="max-w-sm" aria-label="Search task types" placeholder="Search types…" value={search} onChange={event => setSearch(event.target.value)} /><NativeSelect aria-label="Task type category" className={control} value={category} onChange={event => setCategory(event.target.value)}><option value="">All categories</option>{categories.map(category => <option key={category}>{category}</option>)}</NativeSelect><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={archived} onChange={event => setArchived(event.target.checked)} />Include archived</label></div>
    {loading ? <p role="status">Loading types…</p> : phone&&!ready ? null : <GroupedRecords scope="apps/project-management/pages/TaskTypesPage:cards-1" items={(visible) || []} fields={standardRecordGroups((visible) || [])} gridClassName="grid gap-4 md:grid-cols-2" renderItem={(type,_index,closePreview) => { const TypeIcon = icons[type.icon] || CheckSquare; return <article key={type.name} className="task-type-record space-y-3 rounded-lg border p-4"><div className="flex items-start gap-3"><TypeIcon className="mt-1 h-5 w-5 shrink-0" style={{ color: type.color }} /><div className="min-w-0"><h2 className="break-words font-semibold">{type.name}{type.name === "Task" && <span className="ml-2 text-xs font-normal text-muted-foreground">Default</span>}</h2><p className="text-xs text-muted-foreground">{type.category} · {type.builtin ? "Built-in" : type.archived ? "Archived" : "Custom"} · {type.usage} accessible active tasks</p></div></div><p className="text-sm text-muted-foreground">{type.description}</p><p className="text-xs">Default priority: {type.default_priority} · Plural: {type.plural_name || `${type.name}s`}</p><Link className="inline-block text-sm text-primary underline" to={`/pms/custom-fields?taskType=${encodeURIComponent(type.name)}`}>Configure type fields</Link>{manage && !type.builtin && <div className="flex gap-2"><Button size="sm" variant="outline" disabled={locked} onClick={() => { const startEdit=()=>{setEditing(type.id);setDraft({ name: type.name, plural_name: type.plural_name || "", description: type.description, category: type.category, icon: type.icon, color: type.color, default_priority: type.default_priority, archived: type.archived });};if(phone&&closePreview)closePreview(startEdit);else startEdit(); }}>Edit {type.name}</Button><Button size="sm" variant="ghost" disabled={locked} onClick={() => void save({ name: type.name, plural_name: type.plural_name || "", description: type.description, category: type.category, icon: type.icon, color: type.color, default_priority: type.default_priority, archived: !type.archived }, type.id)}>{type.archived ? "Restore" : "Archive"} {type.name}</Button></div>}</article>; }}/>}
    {!loading && !visible.length && (!phone||ready) && <p>No task types match these filters.</p>}
    {manage && <SmartCreateSection title={phone&&editing!==null?"Edit task type":"Save and create fields"} size="standard" mobileSheet={phone} onClose={phone?closePhoneDraft:undefined} savedRevision={phone?formRevision:0} completionRevision={phone?completed:0} closeOnRecordSaved={!phone} autoOpen={phone&&editing!==null}><CompactForm aria-busy={phone?busy:undefined} className="task-type-form space-y-4 rounded-xl border p-5" onSubmit={event => { event.preventDefault(); void save(draft, editing, (event.nativeEvent as SubmitEvent).submitter?.getAttribute("value") === "fields"); }}><h2 className="font-semibold">{editing ? "Edit type" : "Create task type"}</h2>{phone&&error&&<p role="alert" className="text-destructive">{error}</p>}{recovery}<fieldset disabled={locked} className="grid gap-3 sm:grid-cols-2"><label className="text-sm">Name<Input required maxLength={40} disabled={!!editing} value={draft.name} onChange={event => setDraft({ ...draft, name: event.target.value })} /></label><label className="text-sm">Plural name<Input maxLength={60} placeholder="e.g. VAT Returns" value={draft.plural_name} onChange={event => setDraft({ ...draft, plural_name: event.target.value })} /></label><label className="text-sm">Category<Input required maxLength={60} value={draft.category} onChange={event => setDraft({ ...draft, category: event.target.value })} /></label><label className="text-sm sm:col-span-2">Description<textarea maxLength={1000} className="mt-1 w-full rounded-md border bg-background p-2" value={draft.description} onChange={event => setDraft({ ...draft, description: event.target.value })} /></label><label className="text-sm">Icon<NativeSelect aria-label="Task type icon" className={`${control} ml-2`} value={draft.icon} onChange={event => setDraft({ ...draft, icon: event.target.value })}>{Object.keys(icons).map(icon => <option key={icon}>{icon}</option>)}</NativeSelect></label><label className="text-sm">Color<input aria-label="Task type color" type="color" className="ml-2 inline-block h-8 w-12" value={draft.color} onChange={event => setDraft({ ...draft, color: event.target.value })} /></label><label className="text-sm">Default priority<NativeSelect aria-label="Type default priority" className={`${control} ml-2`} value={draft.default_priority} onChange={event => setDraft({ ...draft, default_priority: event.target.value })}>{["Low", "Medium", "High", "Urgent"].map(priority => <option key={priority}>{priority}</option>)}</NativeSelect></label><div className="flex items-center gap-2 text-sm"><Icon className="h-5 w-5" style={{ color: draft.color }} />{draft.name || "Type preview"}</div><div className="flex gap-2"><Button data-save-action data-task-type-save disabled={locked}>{busy ? "Saving…" : "Save type"}</Button><Button value="fields" disabled={locked} variant="outline">Save and create fields</Button>{editing && <Button type="button" variant="outline" onClick={cancelEdit}>Cancel edit</Button>}</div></fieldset><p className="text-xs text-muted-foreground">Names are stable identifiers. Archiving prevents new assignments while keeping existing tasks intact. Default priority is applied when selecting a type in the task creation form and can be overridden.</p></CompactForm></SmartCreateSection>}
    {(!phone||ready)&&<MobileDisclosure title="Recommended types" maxWidth={480} className="task-types-presets"><section className="space-y-3"><h2 className="text-lg font-semibold">Recommended types</h2><p className="text-sm text-muted-foreground">Practice-specific presets alongside general work types. Adding a preset creates a real definition.</p><div className="grid gap-3 md:grid-cols-2">{presets.filter(([name, group, , description]) => !types.some(type => type.name.toLowerCase() === name.toLowerCase()) && (!category || category === group) && `${name} ${description}`.toLowerCase().includes(search.toLowerCase())).map(([name, category, icon, description]) => <article key={name} className="flex items-start justify-between gap-3 rounded-lg border p-3"><div><h3 className="text-sm font-semibold">{name}</h3><p className="text-xs text-muted-foreground">{description} · {category}</p></div>{manage && <Button size="sm" variant="outline" disabled={locked} aria-label={`Add ${name}`} onClick={() => void save({ ...initial, name, category, icon, description })}>Add</Button>}</article>)}</div></section></MobileDisclosure>}
  </main>;
}
