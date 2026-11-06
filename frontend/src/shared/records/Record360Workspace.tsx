import { CrmFieldsReadOnly } from "@/shared/custom-fields/CrmRecordFields";
import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { RichTextContent } from "@/components/rich-text/LazyRichText";
import { RecordMessageDraft } from "./RecordWorkspace";
import "./record-360.css";
import TaskRecordLinks from "./TaskRecordLinks";
import { useCursorPages } from "./useCursorPages";
const RecordTemplatePicker = lazy(()=>import('@/shared/template-design/RecordTemplatePicker'));
const CustomerAccounting = lazy(()=>import("@/shared/accounting/ConnectedAccounting").then(m=>({default:m.CustomerAccounting})));
const QuickAction = lazy(()=>import("@/apps/crm/CRMRecordDetailPage").then(module=>({default:module.QuickActionModal})));

export type RecordKind = "company" | "contact" | "lead" | "deal" | "project" | "task";
export type RecordSource = "crm" | "srm" | "project_management";
type Summary = {id:number;kind:RecordKind;name:string;status?:string;customer?:{id:number;name:string};project?:{id:number;name:string};fields:Record<string,string|number|null>;projects:{id:number;name:string;status:string}[];project_count?:number|null;relations?:{id:number;kind:string;name:string;url:string}[];allowed_actions?:string[];sections:Record<string,string>};
export type WorkItem = {id:string;source:string;source_id:number;title:string;status:string;due_at?:string;assignee_id?:number;priority?:string;project_id?:number;project_name?:string;url:string};
type Page<T> = {items:T[];total:number|null;page:number;per_page:number;has_more?:boolean;next_cursor?:string|null;sections:Record<string,string>};
type Event = {id:string;type:string;title:string;body?:string;occurred_at?:string;actor_id?:number;actor_name?:string;url?:string;source:string};
export function recordScope(user: ReturnType<typeof useAuthStore.getState>["user"]) {return [user?.id,user?.access?.companyId,sessionStorage.getItem("suite-organization"),sessionStorage.getItem("suite-branch"),JSON.stringify(user?.access?.grants)].join(":");}
export function useRecordScope(){
  const user=useAuthStore(s=>s.user),[generation,setGeneration]=useState(0);
  useEffect(()=>{const changed=()=>setGeneration(value=>value+1);const names=['suite:organization-changed','suite:branch-changed','suite:record-access-changed'];names.forEach(name=>window.addEventListener(name,changed));return()=>names.forEach(name=>window.removeEventListener(name,changed));},[]);
  return `${recordScope(user)}:${generation}`;
}
export function recordError(error: unknown) {const value=error as {response?:{data?:{detail?:unknown}}};return typeof value?.response?.data?.detail==="string"?value.response.data.detail:"This section could not be loaded. Retry to refresh it.";}
export const workSourceLabel:Record<string,string>={pms_task:"PMS task",pms_followup:"Task follow-up",service_followup:"Service follow-up",crm_task:"CRM task",crm_activity:"CRM follow-up",crm_meeting:"CRM meeting"};
export function WorkRows({items}:{items:WorkItem[]}) {return <div className="r360-work-list">{items.map(item=><article key={item.id} className="r360-work-item"><div><Link to={item.url}><RichTextContent value={item.title} legacyFormat="plain"/></Link><p>{workSourceLabel[item.source]||item.source} · {item.status}{item.due_at?` · Due ${item.due_at.length===10?item.due_at:new Date(item.due_at).toLocaleString()}`:" · Unscheduled"}{item.project_name?` · ${item.project_name}`:""}</p></div><Link className="r360-open" to={item.url}>Open</Link></article>)}</div>;}
function SectionError({error,retry}:{error:unknown;retry:()=>void}) {return <div role="alert" className="r360-error">{recordError(error)} <Button variant="outline" size="sm" onClick={retry}>Retry</Button></div>;}

/** Same content in a directory pane, modal or full page; domain forms are passed in. */
export default function Record360Workspace({kind,id,source="crm",actions,details,onAction}:{kind:RecordKind;id:number;source?:RecordSource;actions?:ReactNode;details?:ReactNode;onAction?:(action:"note"|"task"|"call"|"meeting"|"email")=>void}) {
  const scope=useRecordScope(), location=useLocation();
  const [filter,setFilter]=useState("all"),[expanded,setExpanded]=useState(false);
  const workPages=useCursorPages(`${scope}:${source}:${kind}:${id}`),historyPages=useCursorPages(`${scope}:${source}:${kind}:${id}:${filter}`);
  const page=historyPages.page,workPage=workPages.page;
  const [draft,setDraft]=useState<"email"|"whatsapp">();
  const [action,setAction]=useState<"note"|"task"|"call"|"meeting">();
  useEffect(()=>{setDraft(undefined);setAction(undefined);},[scope,kind,id]);
  const base=`/record-360/${kind}/${id}`;
  const query=useQuery<Summary>({retry:false,queryKey:["record-360",scope,source,kind,id],queryFn:async({signal})=>(await api.get(base,{params:{source},signal})).data});
  const work=useQuery<Page<WorkItem>>({retry:false,queryKey:["record-360-work",scope,source,kind,id,workPage,workPages.cursor],enabled:!!query.data,queryFn:async({signal})=>(await api.get(`${base}/work`,{params:{source,page:workPages.cursor?1:workPage,cursor:workPages.cursor||undefined,cursor_mode:true},signal})).data});
  const history=useQuery<Page<Event>>({retry:false,queryKey:["record-360-events",scope,source,kind,id,page,filter,historyPages.cursor],enabled:!!query.data,queryFn:async({signal})=>(await api.get(`${base}/events`,{params:{source,page:historyPages.cursor?1:page,event_type:filter,cursor:historyPages.cursor||undefined,cursor_mode:true},signal})).data});
  const record=query.data;
  const refresh=()=>{workPages.reset();historyPages.reset();void query.refetch();void work.refetch();void history.refetch();};
  useEffect(()=>{const changed=()=>{workPages.reset();historyPages.reset();void query.refetch();void work.refetch();void history.refetch();};window.addEventListener("suite:record-mutated",changed);return()=>window.removeEventListener("suite:record-mutated",changed);},[scope,source,kind,id,workPage,page,filter]);
  const module=source==="project_management"?"pms":source;
  const fullPath=kind==="company"?`/${module}/customers/${id}/360`:kind==="task"?`/pms/tasks/${id}`:kind==="project"?`/pms/projects/${id}`:`/crm/${kind}s/${id}`;
  const messageRecord={name:record?.name||"Record",email:typeof record?.fields.email==="string"?record.fields.email:undefined,phone:typeof record?.fields.phone==="string"?record.fields.phone:undefined,phone_country_code:typeof record?.fields.phone_country_code==="string"?record.fields.phone_country_code:undefined,status:record?.status};
  return <section className="r360" aria-label={`${kind} 360 view`}>
    {query.isPending&&<p role="status">Loading record 360…</p>}
    {query.isError&&<SectionError error={query.error} retry={()=>void query.refetch()}/>}
    {record&&<><header className="r360-header"><div><p className="r360-eyebrow">{kind} · 360°</p><h2>{record.name}</h2><p>{record.status||""}</p></div><div className="r360-actions">{(source==='crm'||source==='srm')&&['company','contact','lead','deal'].includes(kind)&&<Suspense fallback={null}><RecordTemplatePicker entity={kind==='company'?'account':kind as 'lead'|'contact'|'deal'} recordId={id} source={source}/></Suspense>}{actions}{location.pathname!==fullPath&&<Button variant="outline" size="sm" asChild><Link to={fullPath}>Open full record</Link></Button>}<Button variant="outline" size="sm" onClick={refresh}>Refresh</Button></div></header>
      <div className="r360-layout"><aside className="r360-summary"><h3>Summary</h3><dl>{Object.entries(record.fields).filter(([,value])=>value!==null&&value!=="").map(([key,value])=><div key={key}><dt>{key.replace(/_/g," ")}</dt><dd>{String(value)}</dd></div>)}</dl>
        {record.customer&&kind!=="company"&&<section><h3>Customer</h3><Link to={`/${module}/customers/${record.customer.id}/360`}>{record.customer.name}</Link></section>}
        {record.project&&<section><h3>Project</h3><Link to={`/pms/projects/${record.project.id}`}>{record.project.name}</Link></section>}
        {!details&&source==="crm"&&["lead","contact","company","deal"].includes(kind)&&<CrmFieldsReadOnly entity={kind==="company"?"companies":`${kind}s`} recordId={id} companySource={kind==="company"?source:undefined}/>}
        {kind==="task"&&<TaskRecordLinks key={`${scope}:${id}`} taskId={id}/>}
        {record.projects.length>0&&<section><h3>Related projects</h3>{record.projects.map(project=><p key={project.id}><Link to={`/pms/projects/${project.id}`}>{project.name}</Link> · {project.status}</p>)}{(record.project_count||0)>record.projects.length&&<p>Showing {record.projects.length} of {record.project_count}. <Link to={`/pms/tasks-follow-ups?customer=${id}`}>View all delivery work</Link></p>}</section>}
        {!!record.relations?.length&&<section><h3>People & deals</h3>{record.relations.map(relation=><p key={`${relation.kind}:${relation.id}`}><Link to={relation.url}>{relation.name}</Link> · {relation.kind}</p>)}</section>}
        {details&&<details className="r360-details"><summary>Details & related records</summary><div key={scope}>{details}</div></details>}
      </aside><div className="r360-content">
        <nav className="r360-composer" aria-label="Record activity actions">{([['task','Activity'],['note','Notes'],['meeting','Meeting'],['call','Call'],['email','Email']] as const).filter(([value])=>value==="email"?!!onAction:record.allowed_actions?record.allowed_actions.includes(value):!!onAction).map(([value,label])=><Button key={value} variant="ghost" size="sm" onClick={()=>onAction?onAction(value):value!=="email"&&setAction(value)}>{label}</Button>)}
          {!onAction&&messageRecord.email&&<Button variant="ghost" size="sm" onClick={()=>setDraft("email")}>Email</Button>}{messageRecord.phone&&<Button variant="ghost" size="sm" onClick={()=>setDraft("whatsapp")}>WhatsApp</Button>}
          {record.customer&&<Button variant="ghost" size="sm" asChild><Link to={`/${module}/follow-ups?new=1&customer=${record.customer.id}${kind==="deal"?`&deal=${id}`:""}`}>Schedule follow-up</Link></Button>}
          {kind==="task"&&<Button variant="ghost" size="sm" asChild><Link to={`/pms/tasks/${id}?tab=followups`}>Task follow-up</Link></Button>}
        </nav>
        {(source==="crm"||source==="srm")&&["company","contact","lead","deal"].includes(kind)&&<Suspense fallback={<p>Loading connected accounting…</p>}><CustomerAccounting key={`${scope}:${kind}:${id}`} kind={kind} id={id} source={source}/></Suspense>}
        <section aria-label="Focus" className="r360-focus"><header><h3>Focus</h3><span>Work linked to this {kind}</span></header>
          {work.isPending&&<p role="status">Loading commitments…</p>}{work.isError&&<SectionError error={work.error} retry={()=>{workPages.reset();void work.refetch();}}/>}
          {work.data&&<><WorkRows items={work.data.items.filter(item=>!["completed","done","cancelled","missed"].includes(item.status.toLowerCase()))}/>{work.data.items.length===0&&<p>No work is linked to this record.</p>}<FeedPager pages={workPages} data={work.data} busy={work.isFetching}/></>}
        </section>
        <section aria-label="History" className="r360-history"><header><h3>History</h3><label>Filter <NativeSelect aria-label="History event type" value={filter} onChange={e=>{setFilter(e.target.value);}}>{["all","activity","note","file","history","followup","commercial","email","whatsapp","call","meeting"].map(value=><option key={value} value={value}>{value==="all"?"All events":value}</option>)}</NativeSelect></label><label><input type="checkbox" checked={expanded} onChange={e=>setExpanded(e.target.checked)}/> Expand all</label></header>
          {history.isPending&&<p role="status">Loading history…</p>}{history.isError&&<SectionError error={history.error} retry={()=>{historyPages.reset();void history.refetch();}}/>}
          {history.data?.items.map(event=><details key={`${event.id}:${expanded}`} open={expanded} className="r360-event"><summary><strong>{event.url?<Link to={event.url}>{event.title}</Link>:event.title}</strong><small>{event.occurred_at?new Date(event.occurred_at).toLocaleString():"Timestamp unavailable"} · {event.source.replace(/_/g," ")}{` · ${event.actor_name||(event.actor_id?`User #${event.actor_id}`:"System")}`}</small></summary>{event.body&&<RichTextContent value={event.body} legacyFormat="plain"/>}</details>)}
          {history.data?.items.length===0&&<p>No recorded history for this filter.</p>}
          {history.data&&<FeedPager pages={historyPages} data={history.data} busy={history.isFetching}/>}
          {history.data&&Object.values(history.data.sections).some(state=>state==="restricted")&&<p className="r360-muted">Some source sections are restricted by your permissions.</p>}
        </section>
      </div></div></>}
    {draft&&<RecordMessageDraft record={messageRecord} channel={draft} close={()=>setDraft(undefined)}/>}
    {action&&record&&<Suspense fallback={<p role="status">Loading activity form…</p>}><QuickAction action={action} kind={kind==="company"?"accounts":kind==="contact"?"contacts":kind==="lead"?"leads":"deals"} entity={kind==="company"?"companies":`${kind}s`} recordId={id} record={{...record.fields,id,name:record.name,full_name:record.name,status:record.status}} onClose={()=>setAction(undefined)} onDone={()=>{setAction(undefined);refresh();}}/></Suspense>}
  </section>;
}
export function Pager({page,total,perPage,onChange}:{page:number;total:number;perPage:number;onChange:(page:number)=>void}) {return total>perPage?<nav className="r360-pager" aria-label="Pagination"><Button size="sm" variant="outline" disabled={page<=1} onClick={()=>onChange(page-1)}>Previous</Button><span>Page {page} of {Math.max(1,Math.ceil(total/perPage))}</span><Button size="sm" variant="outline" disabled={page*perPage>=total} onClick={()=>onChange(page+1)}>Next</Button></nav>:null;}

export function FeedPager({pages,data,busy=false}:{pages:ReturnType<typeof useCursorPages>;data:{total:number|null;per_page:number;has_more?:boolean;next_cursor?:string|null};busy?:boolean}){
  const more=data.has_more??(pages.page*data.per_page<(data.total||0));
  if(pages.page===1&&!more)return null;
  return <nav className="r360-pager" aria-label="Pagination"><Button size="sm" variant="outline" disabled={busy||pages.page<=1} onClick={pages.previous}>Previous</Button><span>Page {pages.page}{data.total!==null?` of ${Math.max(1,Math.ceil(data.total/data.per_page))}`:""}</span><Button size="sm" variant="outline" disabled={busy||!more} onClick={()=>pages.next(data.next_cursor||null)}>Next</Button></nav>;
}
