import { Button } from "@/components/ui/button";
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { CalendarDays, Check, ChevronRight, FileText, LayoutTemplate, Loader2, Plug, RefreshCw, Save } from 'lucide-react';
import { api } from '@/services/api';
import { NativeSelect } from '@/components/ui/native-select';
import './ai-workspace.css';
import type { RadarRequest } from './radarRequest';

type Config = { horizon_days: number; include_completed: boolean; timezone: string };
type Deadline = { id:number; task_key:string; title:string; status:string; priority:string; due_date:string|null; days_remaining:number|null; bucket:string; project_id:number };
type Radar = { today:string; through:string; generated_at:string; source:string; config:Config; project:{id:number;name:string}; counts:Record<string,number>; items:Deadline[]; coverage:{scanned:number;complete:boolean;limit:number} };
type Artifact = { id:number; title:string; revision:number; payload:Config };
type Connector = { id:string; name:string; category:string; actions:{name:string;mutates:boolean}[] };
type Connection = { id:number; connector_id:string; name?:string; status?:string };
type Props = { project:string; workspace:string; request:RadarRequest; onAsk:(ids:number[],text:string)=>void; onCreated:()=>void };
const ROOT='/ai-operator';
const defaultConfig=():Config=>({horizon_days:30,include_completed:false,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone});
function failure(e:any){return typeof e?.response?.data?.detail==='string'?e.response.data.detail:'Could not load this workspace data. Check access and try again.';}

export default function AIWorkspacePanel({project,workspace,request,onAsk,onCreated}:Props){
 const [tab,setTab]=useState<'preview'|'templates'|'saved'|'connections'>('templates');
 const [config,setConfig]=useState<Config>(defaultConfig),[radar,setRadar]=useState<Radar|null>(null);
 const [saved,setSaved]=useState<Artifact[]>([]),[active,setActive]=useState<Artifact|null>(null),[title,setTitle]=useState('Deadline Radar');
 const [loading,setLoading]=useState(false),[saving,setSaving]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const [refresh,setRefresh]=useState(0),[selected,setSelected]=useState<number[]>([]),[filter,setFilter]=useState('all'),[search,setSearch]=useState('');
 const [connectors,setConnectors]=useState<Connector[]>([]),[connections,setConnections]=useState<Connection[]>([]),[connectionError,setConnectionError]=useState(''),[connectionLoading,setConnectionLoading]=useState(false);
 const generation=useRef(0);
 useEffect(()=>{generation.current++;setRadar(null);setSaved([]);setActive(null);setSelected([]);setConfig(defaultConfig());setTitle('Deadline Radar');setError('');setNotice('');},[project,workspace]);
 useEffect(()=>{if(request.id){setTab('preview');setFilter(request.filter||'all');if(request.horizon)setConfig(old=>({...old,horizon_days:request.horizon!}));setRefresh(n=>n+1);setNotice('Deadline Radar uses current project tasks. No model call is needed to build this preview.');}},[request]);
 useEffect(()=>{
  if(!project)return;let live=true;setLoading(true);setError('');setRadar(null);setSelected([]);
  api.get<Radar>(`${ROOT}/workspace/deadline-radar`,{params:{project_id:Number(project),...config}}).then(r=>{if(live)setRadar(r.data);}).catch(e=>{if(live)setError(failure(e));}).finally(()=>{if(live)setLoading(false);});
  return()=>{live=false;};
 },[project,workspace,config,refresh]);
 useEffect(()=>{if(!project)return;let live=true;api.get(`${ROOT}/workbench/items`,{params:{project_id:Number(project)}}).then(r=>{if(live)setSaved(r.data.items.filter((x:any)=>x.kind==='deadline_radar'));}).catch(e=>{if(live)setError(failure(e));});return()=>{live=false;};},[project,workspace,refresh]);
 useEffect(()=>{
  if(tab!=='connections')return;let live=true;setConnectionLoading(true);setConnectionError('');setConnectors([]);setConnections([]);
  Promise.all([api.get('/power-apps/integrations/catalog'),api.get('/power-apps/integrations/connections',{params:{environment:'development'}})]).then(([catalog,accounts])=>{if(live){setConnectors(catalog.data.items);setConnections(accounts.data.items);}}).catch(e=>{if(live)setConnectionError(failure(e));}).finally(()=>{if(live)setConnectionLoading(false);});return()=>{live=false;};
 },[tab,workspace]);
 async function save(){
  if(!project)return;const version=generation.current;setSaving(true);setError('');setNotice('');
  const body={project_id:Number(project),kind:'deadline_radar',title:title.trim()||'Deadline Radar',payload:config,...(active?{revision:active.revision}:{})};
  try{const r=active?await api.put(`${ROOT}/workbench/items/${active.id}`,body):await api.post(`${ROOT}/workbench/items`,body);if(version===generation.current){setActive(r.data);setNotice('Artifact saved. Reopening it reads fresh project data.');setRefresh(x=>x+1);}}
  catch(e){if(version===generation.current)setError(failure(e));}finally{setSaving(false);}
 }
 const rows=(radar?.items||[]).filter(row=>(filter==='all'||row.bucket===filter)&&`${row.title} ${row.task_key}`.toLowerCase().includes(search.toLowerCase()));
 return <section className="ai-artifact-panel" aria-label="AI artifact workspace">
  <header className="ai-artifact-header"><div><span className="ai-eyebrow">ARTIFACT WORKSPACE</span><h2>From a request to a working view</h2></div><CalendarDays size={22}/></header>
  <nav className="ai-artifact-tabs" aria-label="Artifact navigation">{([
   ['preview','Preview',CalendarDays],['templates','Templates',LayoutTemplate],['saved','Saved',FileText],['connections','Connections',Plug]
  ] as const).map(([id,label,Icon])=><button key={id} type="button" aria-pressed={tab===id} onClick={()=>setTab(id)}><Icon size={15}/>{label}{id==='saved'&&saved.length>0?` (${saved.length})`:''}</button>)}</nav>
  {notice&&<p role="status" className="ai-artifact-notice"><Check size={16}/>{notice}</p>}
  {error&&tab!=='connections'&&<div role="alert" className="ai-artifact-error">{error}<Button variant="outline" type="button" onClick={()=>setRefresh(x=>x+1)}>Retry</Button></div>}
  {tab==='templates'&&<div className="ai-template-content"><span className="ai-eyebrow">START WITH AN OUTCOME</span><h3>Plan less. See what needs attention.</h3><p>Reusable views powered by your existing project data.</p><button className="ai-template-card" onClick={()=>{setActive(null);setTitle('Deadline Radar');setConfig(defaultConfig());setTab('preview');onCreated();}}><CalendarDays size={28}/><span><strong>Deadline Radar</strong><small>Overdue work, upcoming deadlines and missing dates in one live view.</small><em>PMS · Live project tasks</em></span><ChevronRight size={18}/></button><p className="ai-panel-caption">Choose a project in Context to connect the template. Building a preview does not change any tasks.</p></div>}
  {tab==='saved'&&<div className="ai-template-content"><h3>Your project artifacts</h3><p>Saved configurations reopen with fresh data and current permissions.</p>{!project?<p>Choose a project in Context to see its artifacts.</p>:saved.length===0?<p>No saved radars yet. Open Deadline Radar, then save the artifact.</p>:saved.map(item=><button className="ai-template-card" key={item.id} onClick={()=>{setActive(item);setTitle(item.title);setConfig(item.payload);setTab('preview');}}><CalendarDays size={20}/><span><strong>{item.title}</strong><small>{item.payload.horizon_days} day horizon · revision {item.revision}</small></span><ChevronRight size={16}/></button>)}</div>}
  {tab==='connections'&&<div className="ai-template-content"><h3>Existing suite connectors</h3><p>These are your development environment connections. Deadline Radar currently reads PMS tasks; external accounts are managed by the existing connector workspace.</p><Link className="ai-panel-link" to="/power-apps/connectors?environment=development">Manage connections <ChevronRight size={14}/></Link>{connectionLoading&&<p role="status">Loading connector catalog…</p>}{connectionError&&<p role="alert" className="ai-artifact-error">{connectionError}</p>}<div className="ai-connector-list">{connectors.map(c=>{const accounts=connections.filter(a=>a.connector_id===c.id);return <div key={c.id}><Plug size={17}/><span><strong>{c.name}</strong><small>{c.category} · {c.actions?.length||0} supported actions</small></span><span className="ai-connection-label">{accounts.length?`${accounts.length} configured`:'Not configured'}</span></div>;})}</div><p className="ai-panel-caption">Configured accounts are not a claim of a verified live provider connection. Credentials remain in the existing server vault.</p></div>}
  {tab==='preview'&&<div className="ai-radar-content">
   <div className="ai-radar-title"><div><span className="ai-eyebrow">LIVE ARTIFACT · PMS</span><input aria-label="Artifact title" maxLength={180} value={title} onChange={e=>setTitle(e.target.value)}/><p>{radar?.project.name||'Connect a project to begin'}</p></div><div className="ai-radar-actions"><button aria-label="Refresh Deadline Radar" title="Refresh live data" disabled={!project||loading} onClick={()=>setRefresh(x=>x+1)}><RefreshCw size={16}/></button><Button type="submit" variant="outline" disabled={!radar||saving||loading} onClick={()=>void save()}>{saving?<Loader2 size={15}/>:<Save size={15}/>} {active?'Save changes':'Save artifact'}</Button></div></div>
   <div className="ai-radar-controls"><label>Horizon<NativeSelect aria-label="Deadline horizon" value={config.horizon_days} onChange={e=>setConfig({...config,horizon_days:Number(e.target.value)})}>{Array.from(new Set([7,14,30,60,90,365,config.horizon_days])).sort((a,b)=>a-b).map(n=><option key={n} value={n}>Next {n} days</option>)}</NativeSelect></label><label className="ai-completed-toggle"><input type="checkbox" checked={config.include_completed} onChange={e=>setConfig({...config,include_completed:e.target.checked})}/>Include completed</label></div>
   {!project?<div className="ai-radar-empty"><CalendarDays size={36}/><h3>Connect your work</h3><p>Open Context and choose a project. Its tasks become a live Deadline Radar without copying records or configuring a new connector.</p></div>:loading?<div role="status" className="ai-radar-empty"><Loader2 className="animate-spin"/><p>Reading authorized project tasks…</p></div>:radar&&<>
    <div className="ai-radar-stats">{[['overdue','Overdue'],['today','Due today'],['upcoming','Upcoming'],['undated','No date']].map(([key,label])=><button key={key} data-urgent={key==='overdue'&&radar.counts[key]>0} aria-pressed={filter===key} onClick={()=>setFilter(filter===key?'all':key)}><strong>{radar.counts[key]}</strong><span>{label}</span></button>)}</div>
    <div className="ai-radar-filter"><input aria-label="Search deadline tasks" placeholder="Find a task…" value={search} onChange={e=>setSearch(e.target.value)}/><NativeSelect aria-label="Deadline status filter" value={filter} onChange={e=>setFilter(e.target.value)}>{[['all','All visible work'],['overdue','Overdue'],['today','Due today'],['upcoming','Upcoming'],['undated','No date'],['completed','Completed']].map(([id,label])=><option key={id} value={id}>{label}</option>)}</NativeSelect></div>
    {!radar.coverage.complete&&<p role="status" className="ai-artifact-error">Showing the earliest {radar.coverage.limit} tasks only. Counts are partial; narrow the project for complete coverage.</p>}
    <p className="ai-panel-caption">{radar.today} → {radar.through} · {config.timezone} · {radar.coverage.scanned} tasks scanned{radar.coverage.complete?' · Complete project coverage':''}. {radar.counts.later} open tasks beyond this horizon.</p>
    <div className="ai-radar-task-list" aria-label="Deadline tasks">{rows.length===0?<p className="ai-radar-empty">No tasks match this view. Try another filter or horizon.</p>:rows.map(row=><div data-priority-row data-priority={row.priority} className="ai-radar-task" key={row.id}><input type="checkbox" aria-label={`Select ${row.task_key||row.title} for AI`} checked={selected.includes(row.id)} disabled={selected.length>=25&&!selected.includes(row.id)} onChange={e=>setSelected(ids=>e.target.checked?[...ids,row.id]:ids.filter(id=>id!==row.id))}/><div><Link to={`/pms/tasks/${row.id}`}>{row.title}</Link><small>{row.task_key} · {row.status} · {row.priority}</small></div><span className={`ai-deadline-badge ai-deadline-${row.bucket}`}>{row.bucket==='completed'?'Completed':row.days_remaining===null?'No date':row.days_remaining<0?`${Math.abs(row.days_remaining)}d overdue`:row.days_remaining===0?'Today':`In ${row.days_remaining}d`}<small>{row.due_date||'Needs scheduling'}</small></span></div>)}</div>
    <div className="ai-radar-footer"><span>{selected.length} selected · up to 25</span><button disabled={!selected.length} onClick={()=>onAsk(selected,'Review the selected tasks and propose a practical deadline recovery plan. Ask before changing dates.')}>Discuss in chat <ChevronRight size={14}/></button></div>
    <p className="ai-panel-caption">Updated {new Date(radar.generated_at).toLocaleTimeString()} · {radar.source}. Changes proposed in chat require the existing operator approval.</p>
   </>}
  </div>}
 </section>;
}
