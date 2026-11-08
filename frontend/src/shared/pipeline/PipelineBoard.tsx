import { usePipelinePreferences, useRecordedStageAges, PipelineDrawer, PipelinePreferencesPanel, PipelineHistory, type PipelineContext } from "./PipelineExperience";
import { useState, type ReactNode, type CSSProperties } from "react";
import { DndContext, DragOverlay, PointerSensor, KeyboardSensor, useSensor, useSensors, useDroppable, pointerWithin, closestCenter, type DragEndEvent } from "@dnd-kit/core";
import { SortableContext, useSortable, sortableKeyboardCoordinates, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { AlertTriangle, Clock3, GripVertical, LayoutGrid, List, Plus, Search, SlidersHorizontal, Layers3, PlayCircle, CircleCheck, CircleDot, UsersRound, TrendingUp, ArrowUpRight, CalendarDays, ListChecks, Paperclip, Flag, Sparkles, X, CheckSquare2, FileCheck2, Handshake, UserRoundSearch, Ban } from "lucide-react";
import "./pipeline.css";

export type PipelineStage = { id: string; name: string; summary?: ReactNode; count?: number; disabled?: boolean; canAdd?:boolean; color?: string; wipLimit?: number; agingDays?:number; probability?:number };
export type PipelineRecord = { id: string; stageId: string; title: string; subtitle?: ReactNode; value?: ReactNode; owner?: string; ownerId?: number; stageAgeDays?: number; nextActionAt?: string; isClosed?: boolean; stalled?:boolean; labelColor?: string; activity?: "overdue" | "missing" | "scheduled"; activityLabel?: string; disabled?: boolean; content?: ReactNode; description?:string; priority?:string; tags?:string[]; attachmentCount?:number; progress?:{completed:number;total:number;label?:string} };
export type PipelineMove = { record: PipelineRecord; stageId: string; beforeId?: string };
export type PipelineAction = { id: string; label: string; tone?: "success" | "danger"; onAction: (record: PipelineRecord) => void | Promise<void> };
export type PipelineBoardProps = {
  label: string; title?:string; description?:string; stages: PipelineStage[]; records: PipelineRecord[]; toolbar?: ReactNode;
  onMove?: (move: PipelineMove) => void | Promise<void>; onOpen?: (record: PipelineRecord) => void;
  onAdd?: (stageId: string) => void; disabled?: boolean; reorder?: boolean; loading?: boolean;
  actions?: PipelineAction[]; notice?: ReactNode; viewState?:Record<string,string|boolean>; onApplyView?:(state:Record<string,string|boolean>)=>void; context?:PipelineContext; renderDetails?:(record:PipelineRecord)=>ReactNode; onNextAction?:(record:PipelineRecord)=>void;
};

/** Shared presentation. Every mutation is committed by a domain adapter. */
export default function PipelineBoard({ label, title, description, stages, records, toolbar, onMove, onOpen, onAdd, disabled=false, reorder=true, loading=false, actions=[], notice, context, renderDetails, onNextAction, viewState, onApplyView }: PipelineBoardProps) {
  const [active,setActive]=useState<PipelineRecord>();
  const [settings,setSettings]=useState(false),[selectedId,setSelectedId]=useState<string>();
  const experience=usePipelinePreferences(context,label,viewState,onApplyView),p=experience.preferences;
  const ages=useRecordedStageAges(context,records);
  const enriched=records.map(r=>{const metadata=ages[r.id];const age=metadata?.days??r.stageAgeDays;const next=metadata?.next_action_at||r.nextActionAt;const threshold=stages.find(s=>s.id===r.stageId)?.agingDays;return {...r,nextActionAt:next,activity:!r.isClosed&&metadata&&"next_action_at" in metadata?(next?new Date(next)<new Date()?"overdue" as const:"scheduled" as const:"missing" as const):r.activity,activityLabel:next?`Next action: ${new Date(next).toLocaleString()}`:r.activityLabel,stageAgeDays:age,stalled:!r.isClosed&&age!==undefined&&!!threshold&&age>=threshold};});
  const selected=enriched.find(r=>r.id===selectedId);
  const filtered=enriched.filter(r=>(!p.search||`${r.title} ${typeof r.subtitle==="string"?r.subtitle:""}`.toLowerCase().includes(p.search.toLowerCase()))&&(!p.owner||r.owner?.toLowerCase().includes(p.owner.toLowerCase()))&&(p.queue==="all"||p.queue==="mine"&&r.ownerId===experience.userId&&!!experience.userId||p.queue==="attention"&&(r.activity==="overdue"||r.activity==="missing"||r.stalled)||p.queue==="overdue"&&r.activity==="overdue"||p.queue==="unassigned"&&!r.ownerId&&!r.owner));
  const sorted=p.sort==="manual"?filtered:[...filtered].sort((a,b)=>p.sort==="name"?a.title.localeCompare(b.title):p.sort==="age"?(b.stageAgeDays??-1)-(a.stageAgeDays??-1):(a.nextActionAt?new Date(a.nextActionAt).getTime():Infinity)-(b.nextActionAt?new Date(b.nextActionAt).getTime():Infinity));
  const visible=sorted.map(r=>({...r,subtitle:p.fields.includes("subtitle")?r.subtitle:undefined,owner:p.fields.includes("owner")?r.owner:undefined,value:p.fields.includes("value")?r.value:undefined,activity:p.fields.includes("activity")?r.activity:undefined,nextActionAt:p.fields.includes("activity")?r.nextActionAt:undefined,content:p.fields.includes("content")?r.content:undefined,description:p.fields.includes("content")?r.description:undefined,tags:p.fields.includes("content")?r.tags:undefined,progress:p.fields.includes("content")?r.progress:undefined,stageAgeDays:p.fields.includes("age")?r.stageAgeDays:undefined}));
  const open=(r:PipelineRecord)=>{if(context||renderDetails)setSelectedId(r.id);else onOpen?.(r);};
  const [busy,setBusy]=useState(false),[error,setError]=useState(""),[message,setMessage]=useState("");
  const sensors=useSensors(useSensor(PointerSensor,{activationConstraint:{distance:6}}),useSensor(KeyboardSensor,{coordinateGetter:sortableKeyboardCoordinates}));
  async function commit(move: PipelineMove) {
    const target=stages.find(s=>s.id===move.stageId);
    if(!onMove || disabled || busy || (p.sort!=="manual" && move.record.stageId===move.stageId) || move.record.disabled || !target || target.disabled || (!reorder && move.record.stageId===move.stageId)) return;
    setBusy(true);setError("");
    try { await onMove(move);setMessage(`Move requested for ${move.record.title} to ${target.name}.`); }
    catch(e) { setError(pipelineError(e)); } finally {setBusy(false);}
  }
  async function end(event:DragEndEvent) {
    const record=records.find(r=>`record:${r.id}`===event.active.id);setActive(undefined);
    if(!record || !event.over || disabled || busy || record.disabled || (event.delta.x===0 && event.delta.y===0)) return;
    const action=actions.find(a=>`action:${a.id}`===event.over?.id);
    if(action) {setBusy(true);setError("");try {await action.onAction(record);} catch(e){setError(pipelineError(e));}finally{setBusy(false);}return;}
    const target=records.find(r=>`record:${r.id}`===event.over?.id);
    const stage=stages.find(s=>`stage:${s.id}`===event.over?.id);
    const stageId=target?.stageId || stage?.id;
    if(stageId && record.id!==target?.id) {
      let beforeId=target?.id;
      if(target && record.stageId===stageId && reorder && p.sort==="manual") {
        const siblings=records.filter(r=>r.stageId===stageId);
        const sourceIndex=siblings.findIndex(r=>r.id===record.id);
        const targetIndex=siblings.findIndex(r=>r.id===target.id);
        if(sourceIndex<targetIndex) beforeId=siblings[targetIndex+1]?.id;
      }
      await commit({record,stageId,beforeId});
    }
  }
  const finished=enriched.filter(r=>r.isClosed).length,attention=enriched.filter(r=>!r.isClosed&&(r.activity==="overdue"||r.stalled)).length;
  const owners=[...new Set(enriched.map(r=>r.owner).filter((owner):owner is string=>!!owner&&owner!=="—"))];
  const noun=context?.module==="project_management"?"tasks":context?.module==="hrms"?"candidates":context?.module==="crm"?"deals":"records";
  const completion=enriched.length?Math.round(finished/enriched.length*100):0;
  return <section className={`pipeline-workspace pipeline-density-${p.density}`} aria-label={label} aria-busy={busy||loading}>
    <header className="pipeline-hero"><div className="pipeline-hero-copy"><span className="pipeline-eyebrow"><Sparkles size={13}/> {context?.module==="project_management"?"PROJECT DELIVERY":context?.module==="hrms"?"TALENT & RECRUITMENT":context?.module==="crm"?"CUSTOMER GROWTH":"SALES OPERATIONS"}</span><h2>{title||label}</h2><p>{description||"A clear view of your work. Every stage, every next step, in one place."}</p><div className="pipeline-hero-meta"><span><span className="pipeline-live-dot"/> {loading?"Refreshing board":"Live workspace"}</span><span>{stages.length} stages</span><span>Metrics reflect loaded {noun}</span></div></div><div className="pipeline-hero-art" aria-hidden="true"><Layers3 size={36}/><span><CircleCheck size={20}/></span><span><TrendingUp size={18}/></span></div></header>
    <div className="pipeline-metrics" aria-label="Pipeline overview">
      <Metric icon={<Layers3 size={22}/>} label={`Loaded ${noun}`} value={enriched.length} detail="Across this board" tone="violet"/>
      <Metric icon={<PlayCircle size={22}/>} label="Active" value={enriched.length-finished} detail="Open work to move forward" tone="blue"/>
      <Metric icon={<AlertTriangle size={22}/>} label="Needs attention" value={attention} detail="Overdue or stalled work" tone="amber"/>
      <Metric icon={<UsersRound size={22}/>} label="Owners" value={owners.length} detail={owners.length?<span className="pipeline-avatar-stack">{owners.slice(0,3).map(owner=><span key={owner} title={owner}>{initials(owner)}</span>)}{owners.length>3&&<span>+{owners.length-3}</span>}</span>:"No named owners on loaded cards"} tone="violet"/>
      <div className="pipeline-metric pipeline-metric-completion"><div className="pipeline-completion-ring" style={{"--completion":`${completion}%`} as CSSProperties} role="progressbar" aria-label="Closed records" aria-valuenow={completion} aria-valuemin={0} aria-valuemax={100}><span>{completion}%</span></div><div><span className="pipeline-metric-label">{context?.module==="project_management"?"Completion":"Closed"}</span><strong>{finished}<small> / {enriched.length}</small></strong><span className="pipeline-metric-detail">Completed or closed outcomes</span></div></div>
    </div>
    <div className="pipeline-toolbar">{toolbar}<button type="button" className="pipeline-icon-button" aria-label="Board options and saved views" onClick={()=>setSettings(true)}><SlidersHorizontal size={16}/></button></div>
    {(p.queue!=="all"||p.search||p.owner)&&<div className="pipeline-notice">{visible.length} of {records.length} loaded records · {p.queue}<button type="button" className="ml-3 underline" onClick={()=>experience.update({queue:"all",search:"",owner:""})}>Clear view filters</button></div>}
    <div className="pipeline-sr-only" role="status" aria-live="polite">{message}</div>
    {error && <p className="pipeline-error" role="alert">{error}</p>}
    {notice && <div className="pipeline-notice">{notice}</div>}
    {loading && <p className="pipeline-notice" role="status">Loading {label.toLowerCase()}…</p>}
    <DndContext sensors={sensors} collisionDetection={args=>{const hits=pointerWithin(args);if(hits.length){const specific=hits.filter(h=>!String(h.id).startsWith("stage:"));return specific.length?specific:hits;}return closestCenter({...args,droppableContainers:args.droppableContainers.filter(container=>container.id!==args.active.id)});}} onDragStart={e=>setActive(records.find(r=>`record:${r.id}`===e.active.id))} onDragCancel={()=>setActive(undefined)} onDragEnd={e=>void end(e)}>
      <div className="pipeline-lanes">{stages.map(stage=><Lane key={stage.id} stage={stage} records={visible.filter(r=>r.stageId===stage.id)} stages={stages} disabled={disabled||busy||loading} reorder={reorder&&p.sort==="manual"} onMove={onMove?commit:undefined} onOpen={open} onAdd={onAdd} index={stages.indexOf(stage)} noun={noun}/>)}</div>
      {!loading&&!stages.length && <p className="pipeline-notice">No stages configured for this pipeline.</p>}
      {active && actions.length>0 && <div className="pipeline-drop-actions">{actions.map(a=><ActionDrop key={a.id} action={a}/>)}</div>}
      <DragOverlay>{active ? <div className="pipeline-card pipeline-overlay"><CardBody record={active}/></div>:null}</DragOverlay>
    </DndContext>
    <PipelineDrawer open={settings} onClose={()=>setSettings(false)} title="Board options"><PipelinePreferencesPanel state={experience}/></PipelineDrawer>
    <PipelineDrawer open={!!selected} onClose={()=>setSelectedId(undefined)} title={selected?.title||"Record details"}>{selected&&<>
      {renderDetails?renderDetails(selected):<><p className="text-sm text-muted-foreground">{selected.subtitle}</p><dl className="pipeline-detail-summary"><dt>Stage</dt><dd>{stages.find(s=>s.id===selected.stageId)?.name}</dd><dt>Owner</dt><dd>{selected.owner||"Unassigned"}</dd><dt>Value / effort</dt><dd>{selected.value||"—"}</dd><dt>Next action</dt><dd>{selected.nextActionAt?new Date(selected.nextActionAt).toLocaleString():selected.activityLabel||"Not scheduled"}</dd><dt>Time in stage</dt><dd>{selected.stageAgeDays===undefined?"Not yet recorded":`${selected.stageAgeDays} days`}</dd></dl>{selected.content}</>}
      <div className="flex gap-2 my-4">{onOpen&&<button type="button" className="pipeline-primary" onClick={()=>{setSelectedId(undefined);onOpen(selected);}}>Open full record</button>}{onNextAction&&<button type="button" className="pipeline-primary" disabled={disabled} onClick={()=>onNextAction(selected)}>Schedule next action</button>}</div>
      {context?.kind&&<PipelineHistory context={context} recordId={selected.id}/>}</>}
    </PipelineDrawer>
  </section>;
}
function initials(name:string){if(/^[A-Z]{1,3}$/.test(name.trim()))return name.trim();return name.trim().split(/\s+/).slice(0,2).map(word=>word[0]).join("").toUpperCase();}
function stageVisual(name:string,index=0){
  if(/lost|reject|cancel|block|withdraw/i.test(name))return {color:"#d97736",icon:Ban};
  if(/done|complete|won|hired|signed|closed|resolved/i.test(name))return {color:"#18945b",icon:CircleCheck};
  if(/review|assess|verif|approval/i.test(name))return {color:"#238b74",icon:FileCheck2};
  if(/progress|demo|interview|fulfil|meeting/i.test(name))return {color:"#8438eb",icon:PlayCircle};
  if(/contact|screen|qualif|research/i.test(name))return {color:"#3974e9",icon:UserRoundSearch};
  if(/proposal|negotiat|offer/i.test(name))return {color:"#a548c5",icon:Handshake};
  if(/todo|to do|planning/i.test(name))return {color:"#3679ee",icon:CheckSquare2};
  return {color:["#7672a3","#3974e9","#8438eb","#238b74","#bb7c32"][index%5],icon:Layers3};
}
function Metric({icon,label,value,detail,tone}:{icon:ReactNode;label:string;value:number;detail:ReactNode;tone:string}){return <div className={`pipeline-metric pipeline-metric-${tone}`}><span className="pipeline-metric-icon">{icon}</span><div><span className="pipeline-metric-label">{label}</span><strong>{value}</strong><span className="pipeline-metric-detail">{detail}</span></div></div>;}
function Lane({stage,records,stages,disabled,reorder,onMove,onOpen,onAdd,index,noun}:{stage:PipelineStage;records:PipelineRecord[];stages:PipelineStage[];disabled:boolean;reorder:boolean;index:number;noun:string;onMove?: (m:PipelineMove)=>Promise<void>;onOpen?:PipelineBoardProps["onOpen"];onAdd?:PipelineBoardProps["onAdd"]}) {
  const {setNodeRef,isOver}=useDroppable({id:`stage:${stage.id}`,disabled:disabled||stage.disabled||!onMove});
  const visual=stageVisual(stage.name,index),StageIcon=visual.icon;const color=stage.color&&/^#[0-9a-f]{3,8}$/i.test(stage.color)?stage.color:visual.color;
  return <section ref={setNodeRef} style={{"--stage-color":color} as CSSProperties} className={`pipeline-lane ${isOver?"pipeline-lane-over":""}`} aria-label={stage.name}>
    <header className="pipeline-stage-header"><span className="pipeline-stage-icon"><StageIcon size={22}/></span><div className="pipeline-stage-heading"><h3>{stage.name}</h3><div className="pipeline-stage-summary">{stage.summary ?? `${stage.count ?? records.length} records`}{stage.wipLimit? <span className={(stage.count??records.length)>=stage.wipLimit?"pipeline-capacity-full":""}>Capacity {stage.count??records.length}/{stage.wipLimit}</span>:null}{stage.probability!==undefined&&<span className="pipeline-probability">{stage.probability}% probability</span>}</div></div>{onAdd&&stage.canAdd!==false&&!stage.disabled&&<button type="button" className="pipeline-icon-button" disabled={disabled} aria-label={`Add to ${stage.name}`} onClick={()=>onAdd(stage.id)}><Plus size={14}/></button>}</header>{stage.wipLimit&&<div className="pipeline-lane-meter" title="Stage capacity used"><span style={{width:`${Math.min(100,(stage.count??records.length)/stage.wipLimit*100)}%`}}/></div>}
    <SortableContext items={records.map(r=>`record:${r.id}`)} strategy={verticalListSortingStrategy}><div className="pipeline-lane-body">{records.map(r=><RecordCard key={r.id} record={r} stages={stages} disabled={disabled||!!stage.disabled||!!r.disabled||!onMove} reorder={reorder} onMove={onMove} onOpen={onOpen}/>)}{!records.length&&<div className="pipeline-empty"><div className="pipeline-empty-art" aria-hidden="true"><span/><StageIcon size={44}/><span/></div><strong>No {noun} {index===0?"yet":`in ${stage.name}`}</strong><p>{index===0?"Start here to build your pipeline and plan what comes next.":`Move ${noun} here when they are ready for this stage.`}</p>{onAdd&&stage.canAdd!==false?<button type="button" disabled={disabled||stage.disabled} onClick={()=>onAdd(stage.id)}><Plus size={15}/> Add record</button>:<span className="pipeline-empty-hint"><ArrowUpRight size={13}/> Ready for the next step</span>}</div>}</div></SortableContext>
  </section>;
}
function RecordCard({record,stages,disabled,reorder,onMove,onOpen}:{record:PipelineRecord;stages:PipelineStage[];disabled:boolean;reorder:boolean;onMove?: (m:PipelineMove)=>Promise<void>;onOpen?:PipelineBoardProps["onOpen"]}) {
  const {setNodeRef,attributes,listeners,transform,transition,isDragging}=useSortable({id:`record:${record.id}`,disabled});
  const stage=stages.find(s=>s.id===record.stageId);const visual=stageVisual(stage?.name||""),RecordIcon=visual.icon;
  return <article data-priority-row data-priority={record.priority} ref={setNodeRef} style={{"--card-accent":record.labelColor||visual.color,transform:CSS.Transform.toString(transform),transition} as CSSProperties} className={`pipeline-card ${isDragging?"pipeline-card-dragging":""}`}>
    <div className="pipeline-card-top"><RecordIcon className="pipeline-record-icon" size={16}/><button type="button" className="pipeline-card-title" onClick={()=>onOpen?.(record)} disabled={!onOpen}>{record.title}</button>{!disabled&&<button type="button" className="pipeline-handle" {...attributes} {...listeners} aria-label={`Move ${record.title}`}><GripVertical size={13}/></button>}</div>
    <CardBody record={record} stage={stage} hideTitle/>
    {!disabled&&onMove&&<details className="pipeline-move-menu"><summary aria-label={`Move ${record.title} to another stage`}>Move to…</summary><div><label>Stage<select aria-label={`Destination for ${record.title}`} value={record.stageId} onChange={e=>void onMove({record,stageId:e.target.value})}>{stages.map(s=><option key={s.id} value={s.id} disabled={s.disabled}>{s.name}</option>)}</select></label>{reorder&&<button type="button" onClick={()=>void onMove({record,stageId:record.stageId})}>Move to bottom</button>}</div></details>}
  </article>;
}
function CardBody({record,stage,hideTitle=false}:{record:PipelineRecord;stage?:PipelineStage;hideTitle?:boolean}) {const progress=record.progress;return <>
  {!hideTitle&&<strong>{record.title}</strong>}
  {record.subtitle&&<div className="pipeline-card-subtitle">{record.subtitle}</div>}
  <div className="pipeline-card-badges">{record.priority&&<span data-priority-badge data-priority={record.priority} className={`pipeline-priority pipeline-priority-${record.priority.toLowerCase()}`}><Flag size={10}/>{record.priority}</span>}{stage&&<span className="pipeline-status-badge"><CircleDot size={11}/>{stage.name}</span>}{record.activity&&<span className={`pipeline-activity pipeline-activity-${record.activity}`} role="img" aria-label={record.activityLabel||record.activity} title={record.activityLabel||record.activity}>{record.activity==="missing"?<AlertTriangle size={15}/>:<Clock3 size={15}/>}</span>}</div>
  {record.description&&<p className="pipeline-card-description">{record.description.replace(/<[^>]*>/g," ").replace(/&nbsp;/g," ").replace(/&amp;/g,"&")}</p>}
  {!!record.tags?.length&&<div className="pipeline-card-tags">{record.tags.slice(0,3).map(tag=><span key={tag}>{tag}</span>)}{record.tags.length>3&&<span>+{record.tags.length-3}</span>}</div>}
  {progress&&progress.total>0&&<div className="pipeline-checklist"><div><span><ListChecks size={14}/>{progress.label||"Checklist"}</span><span>{progress.completed} / {progress.total}</span></div><progress aria-label={progress.label||"Checklist progress"} value={progress.completed} max={progress.total}/></div>}
  {record.value!==undefined&&<div className="pipeline-card-value">{record.value}</div>}
  {(record.owner||record.nextActionAt||!!record.attachmentCount)&&<div className="pipeline-card-footer">{record.owner&&<span className="pipeline-owner" title={record.owner}>{initials(record.owner)}</span>}{record.nextActionAt&&<span className="pipeline-card-next"><CalendarDays size={13}/>{new Date(record.nextActionAt).toLocaleDateString(undefined,{month:"short",day:"numeric"})}</span>}{!!record.attachmentCount&&<span className="pipeline-card-attachments" title={`${record.attachmentCount} attachments`}><Paperclip size={13}/>{record.attachmentCount}</span>}</div>}
  {record.stageAgeDays!==undefined&&<div className={`pipeline-card-age ${record.stalled?"pipeline-stalled":""}`}><Clock3 size={11}/>{record.stalled?"Stalled · ":""}{record.stageAgeDays}d in stage</div>}
  {record.content}
  </>;}

function ActionDrop({action}:{action:PipelineAction}){const {setNodeRef,isOver}=useDroppable({id:`action:${action.id}`});return <div ref={setNodeRef} className={`pipeline-action-drop ${action.tone||""} ${isOver?"active":""}`}>{action.label}</div>;}
export function PipelineViewSwitch({view,onChange}:{view:"board"|"list";onChange:(v:"board"|"list")=>void}){return <div className="pipeline-view-switch" aria-label="Record view"><button type="button" aria-label="Board view" aria-pressed={view==="board"} onClick={()=>onChange("board")}><LayoutGrid size={16}/></button><button type="button" aria-label="List view" aria-pressed={view==="list"} onClick={()=>onChange("list")}><List size={16}/></button></div>;}
export function PipelineSearch({value,onChange,placeholder="Search records"}:{value:string;onChange:(s:string)=>void;placeholder?:string}){return <label className="pipeline-search"><Search size={15}/><input aria-label={placeholder} value={value} onChange={e=>onChange(e.target.value)} placeholder={placeholder}/>{value&&<button type="button" aria-label={`Clear ${placeholder.toLowerCase()}`} onClick={()=>onChange("")}><X size={13}/></button>}</label>;}
export function pipelineError(error:unknown){const e=error as {response?:{data?:{detail?:unknown}};message?:string};return typeof e.response?.data?.detail==="string"?e.response.data.detail:e.message||"Could not save the move. Refresh and try again.";}
