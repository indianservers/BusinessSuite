import { useCommunicationScope } from "./scope";
import { useState } from "react";
import { useQuery,useQueryClient } from "@tanstack/react-query";
import { CalendarDays } from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { workspaceError } from "@/apps/project-management/pages/workspaceTypes";
type Meeting={id:number;title:string;start_at:string;end_at:string;meeting_url:string};
export function MeetingPanel({wid,rid,canSchedule=false}:{wid:number;rid:number;canSchedule?:boolean}){
  const scope=useCommunicationScope();
  const user=useAuthStore(s=>s.user),qc=useQueryClient(),url=`/collaboration/workspaces/${wid}/chat/conversations/${rid}/meetings`;
  const query=useQuery({queryKey:["communication-meetings",scope,wid,rid],queryFn:async()=>(await api.get<{meetings:Meeting[]}>(url,{progress:false})).data});
  const [open,setOpen]=useState(false),[title,setTitle]=useState(""),[start,setStart]=useState(""),[end,setEnd]=useState(""),[link,setLink]=useState(""),[busy,setBusy]=useState(false),[error,setError]=useState(""),[requestId,setRequestId]=useState("");
  return <section><h3><CalendarDays size={14}/>Upcoming meetings</h3>{query.data?.meetings.map(m=><div className="ce-meeting" key={m.id}><strong>{m.title}</strong><time>{new Date(m.start_at).toLocaleString()}</time>{m.meeting_url.startsWith("https://")&&<a href={m.meeting_url} target="_blank" rel="noopener noreferrer">Join meeting ↗</a>}</div>)}{!query.data?.meetings.length&&<p>No scheduled meetings in this conversation.</p>}
    {canSchedule&&<button onClick={()=>{setOpen(v=>!v);setRequestId(crypto.randomUUID());}}>Schedule meeting</button>}{open&&<form onSubmit={e=>{e.preventDefault();setBusy(true);setError("");void api.post(url,{client_id:requestId,title,start_at:new Date(start).toISOString(),end_at:new Date(end).toISOString(),timezone:Intl.DateTimeFormat().resolvedOptions().timeZone,meeting_url:link}).then(()=>{setOpen(false);return qc.invalidateQueries({queryKey:["communication-meetings"]});}).catch(e=>setError(workspaceError(e))).finally(()=>setBusy(false));}}><fieldset disabled={busy}><label>Meeting title<input required maxLength={220} value={title} onChange={e=>setTitle(e.target.value)}/></label><label>Start<input required type="datetime-local" value={start} onChange={e=>setStart(e.target.value)}/></label><label>End<input required type="datetime-local" value={end} onChange={e=>setEnd(e.target.value)}/></label><label>HTTPS meeting link<input type="url" placeholder="https://…" value={link} onChange={e=>setLink(e.target.value)}/></label><button type="submit">{busy?"Scheduling…":"Save meeting"}</button></fieldset></form>}{(error||query.isError)&&<p role="alert">{error||workspaceError(query.error)}</p>}</section>;
}
