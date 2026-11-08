import { SmartCreateAction } from "@/shared/creation/SmartCreateAction";
import {useEffect,useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {Link} from 'react-router-dom';
import {api} from '@/services/api';
import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {NativeSelect} from '@/components/ui/native-select';
import {useRecordScope} from '@/shared/records/Record360Workspace';
import ActionFields from '@/apps/power-apps/applications/integrations/ActionFields';
import {integrationApi,message,type Action} from '@/apps/power-apps/applications/integrations/integrationApi';

type Job={id:number;version:number;name:string;provider:string;enabled:boolean;automatic:boolean;state:string;pages:number;changed:number;last_error?:string;module:string;batches:string[]};
const kinds:Record<string,string>={upsert_contact:'contacts',create_contact:'contacts',create_draft:'contacts',enrich_person:'contacts',create_ticket:'activities',create_card:'tasks'};
export default function ConnectorWorkflows({module='',environment='development'}:{module?:string;environment?:string}){
 const scope=useRecordScope();
 return <details className="rounded-lg border p-4"><summary className="cursor-pointer font-semibold">Sync & native module workflows</summary><WorkflowContent key={`${scope}:${environment}:${module}`} scope={scope} module={module} environment={environment}/></details>;
}
function WorkflowContent({scope,module,environment}:{scope:string;module:string;environment:string}){
 const [connectionId,setConnectionId]=useState(''),[source,setSource]=useState<Record<string,unknown>>({}),[name,setName]=useState(''),[automatic,setAutomatic]=useState(false),[applyNew,setApplyNew]=useState(false),[allowCredits,setAllowCredits]=useState(false),[projectId,setProjectId]=useState(''),[interval,setInterval]=useState(15),[leadNameQuestion,setLeadNameQuestion]=useState(''),[leadEmailQuestion,setLeadEmailQuestion]=useState('');
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const [actionId,setActionId]=useState(''),[recordId,setRecordId]=useState(''),[settings,setSettings]=useState<Record<string,unknown>>({}),[preview,setPreview]=useState<{payload:Record<string,unknown>;source_hash:string}>(),[confirmed,setConfirmed]=useState(false),[requestId,setRequestId]=useState(()=>crypto.randomUUID());
 const root='/power-apps/integrations';
 const query=useQuery({queryKey:['connector-workflow-options',scope,environment],queryFn:async()=>{
   const [catalog,connections,targets,discovery]=await Promise.all([integrationApi.catalog(),integrationApi.connections(environment),api.get<{targets:Record<string,{module:string;entity:string}>}>(root+'/sync/catalog'),api.get<{items:{id:string;modules:string[]}[]}>(root+'/discovery')]);
   return {catalog,connections,targets:targets.data.targets,modules:discovery.data.items};
 }});
 const jobs=useQuery({queryKey:['connector-sync-jobs',scope,environment],queryFn:async()=>(await api.get<{items:Job[]}>(root+'/sync/jobs',{params:{environment}})).data.items,enabled:query.isSuccess,refetchInterval:30000});
 const eligible=query.data?.connections.filter(c=>c.enabled&&query.data?.targets[c.connector_id]&&(!module||query.data.modules.find(p=>p.id===c.connector_id)?.modules.includes(module)))||[];
 const connection=eligible.find(c=>String(c.id)===connectionId),connector=query.data?.catalog.find(c=>c.id===connection?.connector_id),target=query.data?.targets[connection?.connector_id||''];
 const pageAction=connector?.actions.find(a=>a.id==='sync_page');
 const pageForm=pageAction?{...pageAction,input_schema:{...pageAction.input_schema,properties:Object.fromEntries(Object.entries(pageAction.input_schema.properties||{}).filter(([key])=>key!=='cursor')),required:pageAction.input_schema.required?.filter(key=>key!=='cursor')}}:undefined;
 const actions=connector?.actions.filter(a=>a.mutates&&kinds[a.id])||[];
 const action=actions.find(a=>a.id===actionId),kind=kinds[actionId];
 const records=useQuery({queryKey:['connector-native-sources',scope,kind],queryFn:async()=>(await api.get<{items:{id:number;label:string}[]}>(root+'/sync/sources/'+kind)).data.items,enabled:!!kind});
 const projects=useQuery({queryKey:['connector-native-projects',scope],queryFn:async()=>(await api.get<Record<string,{value:string;label:string}[]>>('/imports/pms/lookups/tasks')).data.project_id||[],enabled:target?.module==='pms'});
 useEffect(()=>{setSource({});setSettings({});setPreview(undefined);setRecordId('');setActionId('');setConfirmed(false);setAllowCredits(false);setRequestId(crypto.randomUUID());},[connectionId]);
 useEffect(()=>{setPreview(undefined);setConfirmed(false);setRequestId(crypto.randomUUID());},[actionId,recordId,settings]);
 async function act(fn:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await fn();}catch(e){setError(message(e));}finally{setBusy(false);}}
 const nativeFields=new Set(['email','first_name','last_name','name','title','text']);
 const settingsAction:Action|undefined=action?{...action,input_schema:{...action.input_schema,properties:Object.fromEntries(Object.entries(action.input_schema.properties||{}).filter(([key])=>!nativeFields.has(key))),required:action.input_schema.required?.filter(key=>!nativeFields.has(key))}}:undefined;
 function workflow(){return {connection_id:Number(connectionId),action_id:actionId,source_kind:kind,source_id:Number(recordId),settings,request_id:requestId};}
 return <div className="space-y-4 pt-4">
  <p>Sync pages into the existing import workspace, review changes, or run a confirmed workflow from a native record. Existing records are preserved during automatic imports.</p>
  {query.isLoading&&<p role="status">Loading authorized connections…</p>}{query.isError&&<p role="alert">Connector workflows require Integration Studio access and native module permissions. {message(query.error)}</p>}
  {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
  <Button variant="outline" disabled={busy||query.isFetching} onClick={()=>void act(async()=>{await query.refetch();await jobs.refetch();})}>Refresh workflow connections</Button>
  <label>Authorized connection<NativeSelect aria-label="Workflow connection" value={connectionId} onChange={e=>setConnectionId(e.target.value)}><option value="">Choose an existing connection</option>{eligible.map(c=><option value={c.id} key={c.id}>{c.name} · {c.health}</option>)}</NativeSelect></label>
  {query.isSuccess&&!eligible.length&&<p>Connect a supported provider in <Link className="underline" to="/power-apps/integrations">Integration Studio</Link> first.</p>}
  {connection&&pageForm&&<section className="space-y-3 rounded border p-4"><h3 className="font-semibold">Incoming sync → {target?.module.toUpperCase()} {target?.entity}</h3>
   <label>Schedule name<Input value={name} onChange={e=>setName(e.target.value)}/></label>
   <ActionFields connector={connector!.id} action={pageForm} value={source} onChange={setSource} disabled={busy}/>
   {connector?.id==='linkedin_lead_forms'&&<div className="space-y-2"><p>Map your LinkedIn form question IDs to native lead fields.</p><label>Full name question ID<Input value={leadNameQuestion} onChange={e=>setLeadNameQuestion(e.target.value)} /></label><label>Email question ID<Input value={leadEmailQuestion} onChange={e=>setLeadEmailQuestion(e.target.value)} /></label></div>}
   {target?.module==='pms'&&<label>Destination project<NativeSelect aria-label="Destination project" value={projectId} onChange={e=>setProjectId(e.target.value)}><option value="">Choose a writable project</option>{projects.data?.map(p=><option key={p.value} value={p.value}>{p.label}</option>)}</NativeSelect></label>}
   <label className="block"><input type="checkbox" checked={automatic} onChange={e=>setAutomatic(e.target.checked)}/> Run automatically in the existing worker</label>
   <label>Repeat interval in minutes<Input type="number" min={5} max={1440} value={interval} onChange={e=>setInterval(Number(e.target.value))}/></label>
   <label className="block"><input type="checkbox" checked={applyNew} onChange={e=>setApplyNew(e.target.checked)}/> Automatically import valid new records; review updates separately</label>
   {connector?.id==='surfe'&&<label className="block"><input type="checkbox" checked={allowCredits} onChange={e=>setAllowCredits(e.target.checked)}/> Allow Surfe enrichment result retrieval to consume provider credits</label>}
   <SmartCreateAction title="Create sync job"><Button disabled={busy||!name.trim()||!connectionId||(target?.module==='pms'&&!projectId)} onClick={()=>void act(async()=>{await api.post(root+'/sync/jobs',{connection_id:Number(connectionId),name,source,automatic,apply_new_records:applyNew,allow_credit_usage:allowCredits,mapping:connector?.id==='linkedin_lead_forms'?{full_name:leadNameQuestion,email:leadEmailQuestion}:{},interval_minutes:interval,constants:target?.module==='pms'?{project_id:projectId}:{}},{params:{environment}});await jobs.refetch();setNotice('Sync job saved. Run it below or leave automatic sync enabled.');})}>Create sync job</Button></SmartCreateAction>
  </section>}
  {jobs.error&&<p role="alert">{message(jobs.error)}</p>}
  {jobs.data?.filter(j=>!module||query.data?.modules.find(p=>p.id===j.provider)?.modules.includes(module)).map(job=><article className="rounded border p-4 space-y-2" key={job.id}><h3 className="font-semibold">{job.name}</h3><p>{job.enabled?job.state:'paused'} · {job.pages} pages · {job.changed} changed records · {job.automatic?'Automatic':'Manual'}</p>{job.last_error&&<p role="alert">{job.last_error}</p>}<div className="flex gap-2"><Button disabled={busy||!job.enabled} onClick={()=>void act(async()=>{await api.post(root+`/sync/jobs/${job.id}/run`,{},{params:{environment}});await jobs.refetch();})}>Sync next page</Button>{job.provider==='surfe'&&job.state==='error'&&<Button variant="outline" disabled={busy||!job.enabled} onClick={()=>void act(async()=>{if(!window.confirm('I reviewed the previous Surfe request. Retry with a new request that may consume provider credits?'))return;await api.post(root+`/sync/jobs/${job.id}/reviewed-retry`,{expected_version:job.version,confirmed:true},{params:{environment}});await jobs.refetch();})}>Reviewed retry (uses credits)</Button>}<Button variant="outline" disabled={busy} onClick={()=>void act(async()=>{await api.put(root+`/sync/jobs/${job.id}`,{expected_version:job.version,enabled:!job.enabled,automatic:job.automatic},{params:{environment}});await jobs.refetch();})}>{job.enabled?'Pause':'Resume'}</Button></div>{job.batches.slice(-5).map(id=><p key={id}><Link className="underline" to={`/${job.module}/import-data?batch=${id}`}>Review native import {id.slice(0,8)}</Link></p>)}</article>)}
  {connection&&actions.length>0&&<section className="space-y-3 rounded border p-4"><h3 className="font-semibold">Outgoing native workflow</h3><label>Workflow<NativeSelect aria-label="Workflow" value={actionId} onChange={e=>setActionId(e.target.value)}><option value="">Choose a workflow</option>{actions.map(a=><option value={a.id} key={a.id}>{a.name}</option>)}</NativeSelect></label>
   {kind&&<label>Native {kind}<NativeSelect aria-label="Native source record" value={recordId} onChange={e=>setRecordId(e.target.value)}><option value="">Choose an accessible record</option>{records.data?.map(r=><option key={r.id} value={r.id}>{r.label}</option>)}</NativeSelect></label>}{records.error&&<p role="alert">{message(records.error)}</p>}
   {settingsAction&&<ActionFields connector={connector!.id} action={settingsAction} value={settings} onChange={setSettings} disabled={busy}/>}
   <Button variant="outline" disabled={busy||!recordId||!actionId} onClick={()=>void act(async()=>{const {data}=await api.post(root+'/sync/workflow/preview',workflow(),{params:{environment}});setPreview(data);})}>Preview native workflow</Button>
   {preview&&<><dl>{Object.entries(preview.payload).map(([key,value])=><div className="grid grid-cols-2 gap-2" key={key}><dt>{key.replace(/_/g,' ')}</dt><dd>{String(value)}</dd></div>)}</dl><label className="block"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/> Confirm this external write{connector?.id==='surfe'?' and provider credit usage':''}</label><Button disabled={busy||!confirmed||!connection.writes_enabled} onClick={()=>void act(async()=>{await api.post(root+'/sync/workflow/execute',{...workflow(),expected_hash:preview.source_hash,confirmed},{params:{environment}});setNotice('Workflow completed. The provider request journal contains its result.');setPreview(undefined);setConfirmed(false);})}>Run confirmed workflow</Button>{!connection.writes_enabled&&<p>Enable writes on this connection before running the workflow.</p>}</>}
  </section>}
 </div>;
}
