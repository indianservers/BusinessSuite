import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Star, GripVertical } from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { PeopleDialog, DirectoryPagination } from "./DirectoryDialogs";
import { directoryRoot, type DirectoryPerson } from "./peopleWorkspace";
import { workspaceError } from "../../pages/workspaceTypes";

export type DestinationKind = "projects" | "teams" | "batches";
export type DirectoryOperation = "add" | "transfer" | "remove" | "role";
export type DestinationRequest = { kind: DestinationKind; action: DirectoryOperation; sequence: number };
type Destination = { id: number; name: string; kind: DestinationKind; members: number; capacity?: number; available?: number; batch_type?: string; lead?: string; avatars: {name:string}[]; start_date?: string; end_date?: string; status?: string; can_manage: boolean; reason?: string };
type Body = { kind: DestinationKind; action: DirectoryOperation; user_ids: number[]; destination_ids: number[]; source_id?: number; role: "Member" | "Viewer"; reason: string; version?: string };
type Row = { user_id: number; name: string; email: string; destination_id: number; destination_name: string; status: string; reason?: string; current_role?: string; workspace_access_added?: boolean; open_tasks: number; overdue_tasks: number; source?: string };
type Preview = { rows: Row[]; version: string };
type Result = { rows: Row[]; undo_ids: number[]; failed_user_ids: number[] };
type Selection = DirectoryPerson & {workload:{pending:number;overdue:number};memberships:Record<DestinationKind,number[]>};

export default function DirectoryDestinations({ selected, dragging, request, onChanged, onClose }: { selected: number[]; dragging: boolean; request?: DestinationRequest; onChanged: () => void; onClose?: () => void }) {
  const user = useAuthStore(s=>s.user), qc = useQueryClient();
  const scope = `${user?.id}:${user?.access?.companyId}`;
  const [kind,setKind] = useState<DestinationKind>("projects"), [action,setAction] = useState<DirectoryOperation>("add");
  const [q,setQ] = useState(""), [sourceQ,setSourceQ] = useState(""), [page,setPage] = useState(1), [targets,setTargets] = useState<number[]>([]), [source,setSource] = useState(0);
  const [role,setRole] = useState<"Member"|"Viewer">("Member"), [reason,setReason] = useState("Directory membership update");
  const [pinned,setPinned] = useState<string[]>([]), [recent,setRecent] = useState<string[]>([]), [hover,setHover] = useState<number>();
  const [preview,setPreview] = useState<Preview>(), [body,setBody] = useState<Body>(), [result,setResult] = useState<Result>();
  const [busy,setBusy] = useState(false), [error,setError] = useState(""), [announcement,setAnnouncement] = useState(""), [undoExpires,setUndoExpires] = useState(0), [undoAvailable,setUndoAvailable] = useState(false);
  useEffect(()=>{ try { const stored=JSON.parse(localStorage.getItem(`pms-destinations:${scope}`)||"{}");setPinned(stored.pinned||[]);setRecent(stored.recent||[]); } catch {setPinned([]);setRecent([]);} setTargets([]);setPreview(undefined);setResult(undefined); },[scope]);
  useEffect(()=>{ if(request){setKind(request.kind);setAction(request.action);setTargets([]);setPage(1);setQ("");setSource(0);setPreview(undefined);setResult(undefined);} },[request]);
  useEffect(()=>{setUndoAvailable(undoExpires>Date.now());const timeout=setTimeout(()=>setUndoAvailable(false),Math.max(0,undoExpires-Date.now()));return()=>clearTimeout(timeout);},[undoExpires]);
  const remember = (pins:string[],recents:string[]) => {setPinned(pins);setRecent(recents);try{localStorage.setItem(`pms-destinations:${scope}`,JSON.stringify({pinned:pins,recent:recents}));}catch{/* Session preferences still work. */}};
  const preferred=[...new Set([...pinned,...recent])].filter(key=>key.startsWith(`${kind}:`)).map(key=>key.split(":")[1]).join(",");
  const destinations=useQuery({queryKey:["people-workspace","destinations",scope,kind,q,page,preferred],queryFn:async()=>(await api.get<{items:Destination[];pages:number;total:number}>(`${directoryRoot}/actions/destinations`,{params:{kind,q,page,preferred},progress:false})).data});
  const sourceOptions=useQuery({queryKey:["people-workspace","source-destinations",scope,kind,sourceQ],enabled:action==="transfer",queryFn:async()=>(await api.get<{items:Destination[]}>(`${directoryRoot}/actions/destinations`,{params:{kind,q:sourceQ},progress:false})).data});
  const selection=useQuery({queryKey:["people-workspace","selection-summary",scope,[...selected].sort((a,b)=>a-b).join(",")],enabled:!!selected.length,queryFn:async()=>(await api.get<{people:Selection[]}>(`${directoryRoot}/actions/selection`,{params:{ids:selected.join(",")},progress:false})).data});
  const selectKind=(value:DestinationKind)=>{setKind(value);setTargets([]);setSource(0);setPage(1);setQ("");if(value!=="projects"&&action==="role")setAction("add");};
  const makeBody=(ids=selected,destinationIds=targets):Body=>({kind,action,user_ids:ids,destination_ids:destinationIds,source_id:source||undefined,role,reason:reason.trim()});
  const runPreview=async(payload:Body)=>{
    if(!payload.user_ids.length||!payload.destination_ids.length){setError("Select members and at least one destination first.");return;}
    setBusy(true);setError("");setResult(undefined);setBody(payload);
    try{const {data}=await api.post<Preview>(`${directoryRoot}/actions/preview`,payload);setPreview(data);setAnnouncement(`Preview ready for ${payload.user_ids.length} members.`);}catch(e){setError(workspaceError(e));}finally{setBusy(false);}
  };
  const apply=async()=>{
    if(!body||!preview)return;setBusy(true);setError("");
    try{
      const {data}=await api.post<Result>(`${directoryRoot}/actions/apply`,{...body,version:preview.version});setResult(data);setPreview(undefined);setUndoExpires(Date.now()+300000);
      remember(pinned,[...body.destination_ids.map(id=>`${body.kind}:${id}`),...recent.filter(key=>!body.destination_ids.some(id=>key===`${body.kind}:${id}`))].slice(0,15));
      await qc.invalidateQueries({queryKey:["people-workspace"]});onChanged();setAnnouncement("Membership operation finished. Review individual results.");
    }catch(e){setError(workspaceError(e));setPreview(undefined);}finally{setBusy(false);}
  };
  const drop=(event:React.DragEvent,destination:Destination)=>{
    event.preventDefault();setHover(undefined);
    try{const ids=JSON.parse(event.dataTransfer.getData("application/x-pms-members"));if(!Array.isArray(ids)||ids.length>100||ids.some(id=>!Number.isInteger(id)))throw new Error("Choose members from this directory.");void runPreview(makeBody(ids,[destination.id]));}catch{setError("Choose members from this directory, or use the keyboard/touch destination checkboxes.");}
  };
  const undo=async()=>{
    if(!result)return;setBusy(true);const failed:number[]=[];let undone=0;
    for(const id of result.undo_ids){try{await api.post(`${directoryRoot}/actions/${id}/undo`);undone++;}catch(e){failed.push(id);setError(workspaceError(e));}}
    setResult({...result,undo_ids:failed});setAnnouncement(`${undone} member additions undone. ${failed.length} require review.`);await qc.invalidateQueries({queryKey:["people-workspace"]});onChanged();setBusy(false);
  };
  return <aside className={`pd-destinations ${dragging?"is-dragging":""}`} aria-label="Membership destinations">
    <header><div><h2>Destinations</h2><p>{dragging?`Drop ${selected.length} selected members to review changes.`:"Drag members here, or select destinations below."}</p></div><GripVertical size={18}/><button className="pd-close-destinations pd-button" onClick={onClose}>Close destinations</button></header>
    <div role="tablist" aria-label="Destination types" className="pd-destination-tabs">{(["projects","teams","batches"] as const).map(value=><button role="tab" tabIndex={kind===value?0:-1} onKeyDown={event=>{const tabs:DestinationKind[]=["projects","teams","batches"];let index=tabs.indexOf(kind);if(event.key==="ArrowRight")index=(index+1)%3;else if(event.key==="ArrowLeft")index=(index+2)%3;else if(event.key==="Home")index=0;else if(event.key==="End")index=2;else return;event.preventDefault();selectKind(tabs[index]);(event.currentTarget.parentElement?.querySelectorAll("button")[index] as HTMLButtonElement)?.focus();}} aria-selected={kind===value} key={value} onClick={()=>selectKind(value)}>{value}</button>)}</div>
    <label>Find {kind}<input value={q} onChange={e=>{setQ(e.target.value);setPage(1);}} placeholder="Search destinations" /></label>
    <div className="pd-destination-config"><label>Operation<select value={action} onChange={e=>{setAction(e.target.value as DirectoryOperation);setSource(0);}}><option value="add">Add · keep existing memberships</option><option value="transfer">Transfer from a chosen source</option><option value="remove">Remove direct memberships</option><option value="role" disabled={kind!=="projects"}>Change project role</option></select></label>
      {action==="transfer"&&<><label>Find source<input value={sourceQ} onChange={e=>setSourceQ(e.target.value)}/></label><label>Source<select value={source} onChange={e=>setSource(Number(e.target.value))}><option value={0}>Choose source</option>{sourceOptions.data?.items.filter(d=>d.can_manage).map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select></label></>}
      {action==="role"&&<label>New role<select value={role} onChange={e=>setRole(e.target.value as "Member"|"Viewer")}><option>Member</option><option>Viewer</option></select></label>}
    </div>
    <div className="pd-selection-slot">{!!selected.length&&<details className="pd-selection-workload"><summary>{selected.length} selected · workload & membership comparison</summary>{selection.isLoading&&<p role="status">Loading workload…</p>}{selection.data?.people.map(person=><div key={person.id}><strong>{person.name}</strong><small>{person.workload.pending} open · {person.workload.overdue} overdue</small></div>)}{selection.isError&&<p role="alert">Could not load comparison. <button onClick={()=>selection.refetch()}>Retry</button></p>}</details>}</div>
    {error&&<p role="alert" className="pd-error">{error}</p>}
    {destinations.isLoading&&<p role="status">Loading destinations…</p>}{destinations.isError&&<p role="alert">Could not load destinations. <button onClick={()=>destinations.refetch()}>Retry</button></p>}
    <div className="pd-drop-list">{destinations.data?.items.map(destination=>{
      const key=`${kind}:${destination.id}`,already=selection.data?.people.filter(p=>p.memberships[kind].includes(destination.id)).length||0;
      const eligible=selection.data?.people.filter(p=>p.status==="active"&&(kind!=="batches"||destination.batch_type!=="Intern"||p.classification==="Intern")).length||0;
      const full=kind==="batches"&&(action==="add"||action==="transfer")&&destination.available===0&&selected.length>already;
      const disabled=!destination.can_manage||full||(dragging&&kind==="batches"&&selection.data!==undefined&&!eligible);
      const why=!destination.can_manage?destination.reason:full?"This batch is full. Choose another destination or free capacity first.":disabled?"No selected active interns match this batch.":undefined;
      return <article key={key} className={`pd-drop-target ${hover===destination.id?"drop-hover":""} ${disabled?"drop-disabled":""} ${targets.includes(destination.id)?"chosen":""}`} aria-label={`${destination.name} destination`} aria-disabled={disabled} title={why}
        onDragOver={event=>{event.preventDefault();event.dataTransfer.dropEffect=disabled?"none":"copy";if(!disabled)setHover(destination.id);}}
        onDragLeave={()=>setHover(undefined)} onDrop={event=>{if(disabled){event.preventDefault();setError(why||"Destination is unavailable");}else drop(event,destination);}}>
        <div className="pd-drop-title"><label><input type="checkbox" aria-label={`Choose ${destination.name}`} disabled={disabled} checked={targets.includes(destination.id)} onChange={e=>setTargets(current=>e.target.checked?[...current,destination.id]:current.filter(id=>id!==destination.id))}/><strong>{destination.name}</strong></label><button aria-label={`${pinned.includes(key)?"Unpin":"Pin"} ${destination.name}`} aria-pressed={pinned.includes(key)} onClick={()=>remember(pinned.includes(key)?pinned.filter(k=>k!==key):[key,...pinned].slice(0,30),recent)}><Star size={15} fill={pinned.includes(key)?"currentColor":"none"}/></button></div>
        <div className="pd-tags">{pinned.includes(key)&&<span>Pinned</span>}{recent.includes(key)&&<span>Recently used</span>}{destination.status&&<span>{destination.status}</span>}</div>
        <p>{destination.members} members{destination.capacity!=null?` / ${destination.capacity} places · ${destination.available} available`:""}</p>
        {!!selected.length&&<small>{already} already members{destination.capacity!=null?` · Up to ${Math.max(0,eligible-already)} new places needed`:""}</small>}
        {destination.lead&&<small>Lead: {destination.lead}</small>}{destination.start_date&&<small>{destination.start_date} – {destination.end_date}</small>}
        <div className="pd-destination-avatars">{destination.avatars.map((p,i)=><span key={i} title={p.name}>{p.name.split(" ").map(s=>s[0]).slice(0,2).join("")}</span>)}</div>{why&&<small>{why}</small>}
      </article>;
    })}</div>
    {destinations.data&&!destinations.data.items.length&&<p>No matching destinations. <button onClick={()=>{setQ("");setPage(1);}}>Clear search</button></p>}
    <DirectoryPagination page={page} pages={destinations.data?.pages||1} onChange={setPage}/>
    <label>Reason<input value={reason} maxLength={1000} onChange={e=>setReason(e.target.value)}/></label>
    <button className="pd-primary w-full" disabled={busy||!selected.length||!targets.length||reason.trim().length<3||(action==="transfer"&&!source)} onClick={()=>void runPreview(makeBody())}>{busy?"Preparing…":`Review ${action} (${selected.length} members)`}</button>
    <p className="pd-scope-note">Only authorized destinations are available. Transfers and removals preserve open work by requiring handover first.</p>
    <p className="sr-only" role="status" aria-live="polite">{announcement}</p>
    <PeopleDialog open={!!preview||!!result} onClose={()=>{if(!busy){setPreview(undefined);setResult(undefined);}}} title={result?"Operation results":"Review membership changes"} description={body?`${body.action} · ${body.kind} · ${body.user_ids.length} members. ${body.action==="add"?"Existing memberships are retained.":"Review the affected memberships before applying."}`:"Review individual outcomes."}>
      <div className="pd-operation-results"><table><thead><tr><th>Member</th><th>Destination / change</th><th>Workload</th><th>Result</th></tr></thead><tbody>{(result?.rows||preview?.rows||[]).map((row,i)=><tr key={i}><td><strong>{row.name}</strong><small>{row.email}</small></td><td>{row.destination_name}{row.source&&<small>Transfer from {row.source}</small>}{row.workspace_access_added&&<small>Workspace Member access will also be added</small>}{body?.action==="role"&&<small>{row.current_role} → {body.role}</small>}</td><td>{row.open_tasks} open / {row.overdue_tasks} overdue</td><td data-status={row.status}>{row.status.replace(/_/g," ")}{row.reason&&<small>{row.reason}</small>}</td></tr>)}</tbody></table></div>
      {error&&<p role="alert" className="pd-error">{error}</p>}{announcement&&result&&<p role="status">{announcement}</p>}
      <div className="pd-dialog-actions">{preview&&<button className="pd-primary" disabled={busy||!preview.rows.some(r=>r.status==="ready")} onClick={()=>void apply()}>{busy?"Applying…":"Apply reviewed changes"}</button>}
        {result&&!!result.failed_user_ids.length&&body&&<button className="pd-button" disabled={busy} onClick={()=>void runPreview({...body,user_ids:result.failed_user_ids,version:undefined})}>Review and retry failed members</button>}
        {result&&!!result.undo_ids.length&&<button className="pd-button" disabled={busy||!undoAvailable} onClick={()=>void undo()}>{undoAvailable?"Undo eligible additions (5 minutes)":"Undo expired"}</button>}
        <button className="pd-button" disabled={busy} onClick={()=>{setPreview(undefined);setResult(undefined);}}>Done</button>
      </div>
    </PeopleDialog>
  </aside>;
}
