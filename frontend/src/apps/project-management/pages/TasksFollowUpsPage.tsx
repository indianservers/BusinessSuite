import { useCursorPages } from "@/shared/records/useCursorPages";
import { useSearchParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { FeedPager, WorkRows, useRecordScope, recordError, type WorkItem } from "@/shared/records/Record360Workspace";

export default function TasksFollowUpsPage(){
  const scope=useRecordScope(),[params,setParams]=useSearchParams();
  const view=params.get('view')||'mine',search=params.get('search')||'',source=params.get('source')||'';
  const pages=useCursorPages(`${scope}:${params.toString()}`);
  const change=(key:string,value:string)=>setParams(old=>{const next=new URLSearchParams(old);if(value)next.set(key,value);else next.delete(key);if(key!=='page')next.delete('page');return next;},{replace:true});
  const query=useQuery<{items:WorkItem[];total:number|null;page:number;per_page:number;has_more?:boolean;next_cursor?:string|null;sections:Record<string,string>}>({queryKey:['pms-tasks-followups',scope,params.toString(),pages.page,pages.cursor],queryFn:async({signal})=>(await api.get('/record-360/work/queue/items',{params:{view,page:pages.cursor?1:pages.page,cursor:pages.cursor||undefined,cursor_mode:true,search,source_filter:source,project_id:params.get('project')||undefined,customer_id:params.get('customer')||undefined},signal})).data,refetchInterval:60000});
  return <main className="r360-page"><header className="r360-header"><div><p className="r360-eyebrow">PMS</p><h1 className="text-2xl font-semibold">Tasks & Follow-ups</h1><p>Delivery tasks and commitments, linked to their original workflow.</p></div><div className="r360-actions"><Button variant="outline" asChild><Link to="/pms/tasks">Task views</Link></Button><Button variant="outline" asChild><Link to="/pms/tasks/new">Create task</Link></Button><Button asChild><Link to="/pms/follow-ups?new=1">Schedule customer follow-up</Link></Button></div></header>
    <div className="r360-queue-controls"><label>View <NativeSelect aria-label="Work queue view" value={view} onChange={e=>change('view',e.target.value)}>{[['mine','Assigned to me'],['assigned','Assigned by me'],['today','Today'],['overdue','Overdue'],['upcoming','Upcoming'],['completed','Completed'],['all','All accessible work']].map(([value,label])=><option key={value} value={value}>{label}</option>)}</NativeSelect></label><label>Source <NativeSelect aria-label="Work source" value={source} onChange={e=>change('source',e.target.value)}><option value="">All sources</option><option value="pms_task">PMS tasks</option><option value="pms_followup">Task follow-ups</option><option value="service_followup">Service follow-ups</option><option value="crm_task">CRM tasks</option><option value="crm_activity">CRM follow-ups</option><option value="crm_meeting">CRM meetings</option></NativeSelect></label><Input aria-label="Search tasks and follow-ups" placeholder="Search tasks and follow-ups" value={search} onChange={e=>change('search',e.target.value)}/><Button variant="outline" onClick={()=>{pages.reset();void query.refetch();}}>Refresh</Button></div>
    {(params.has('customer')||params.has('project'))&&<p>Filtered by {params.has('customer')?`customer #${params.get('customer')}`:`project #${params.get('project')}`} · <button className="underline" onClick={()=>{setParams({view});}}>Clear scope</button></p>}
    {query.isPending&&<p role="status">Loading work…</p>}{query.isError&&<p role="alert">{recordError(query.error)} <Button variant="outline" onClick={()=>{pages.reset();void query.refetch();}}>Retry</Button></p>}
    {query.data&&<><p className="my-3 text-sm text-muted-foreground">{query.data.total===null?"Accessible work":`${query.data.total} accessible items`}. Open an item to complete, reschedule or update it in its source workflow.</p><WorkRows items={query.data.items}/>{query.data.items.length===0&&<p>No work matches these filters.</p>}<FeedPager pages={pages} data={query.data} busy={query.isFetching}/>{Object.values(query.data.sections).some(state=>state==='restricted')&&<p className="r360-muted mt-4">Some sources require additional module permissions.</p>}</>}
  </main>;
}
