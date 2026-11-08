import {useState} from "react";
import {useQuery} from "@tanstack/react-query";
import {Link} from "react-router-dom";
import {api} from "@/services/api";
import {Button} from "@/components/ui/button";
import {Card,CardHeader,CardTitle,CardContent} from "@/components/ui/card";
import {formatDate} from "@/lib/utils";

type HistoryRow={id:number;entity:string;field:string;action:string;before:string|null;after:string|null;actor_id:number|null;at:string};
type Checks={certifications:Array<{id:number;name:string;expires:string;status:string}>;documents:Array<{id:number;name:string;status:string;expired:boolean}>;mandatory_tasks:Array<{id:number;name:string;due:string|null}>;pending_requests:number;scheduled_transfers:Array<{id:number;effective:string;status:string}>};
export default function EmployeeReliabilityPanel({employeeId}:{employeeId:number}) {
 const [days,setDays]=useState(90);
 const checks=useQuery({queryKey:["employee-profile-checks",employeeId,days],queryFn:()=>api.get<Checks>(`/employees/${employeeId}/profile-checks`,{params:{days},recordCache:false}).then(r=>r.data)});
 const history=useQuery({queryKey:["employee-profile-history",employeeId],queryFn:()=>api.get<{items:HistoryRow[]}>(`/employees/${employeeId}/history`,{recordCache:false}).then(r=>r.data.items)});
 const refresh=()=>{void checks.refetch();void history.refetch();};
 return <div className="space-y-4"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold">Profile checks & history</h2><Button variant="outline" onClick={refresh}>Refresh checks & history</Button></div>
 {(checks.isError||history.isError)&&<p role="alert">Could not load profile checks. Your saved profile is unchanged. <button className="underline" onClick={refresh}>Retry</button></p>}
 {(checks.isPending||history.isPending)&&<p role="status">Loading profile checks…</p>}
 {checks.data&&<><Card><CardHeader><CardTitle>Certification expiry alerts</CardTitle></CardHeader><CardContent className="space-y-3"><label className="flex items-center gap-3">Reminder window<select aria-label="Certification reminder window" className="rounded border bg-background p-2" value={days} onChange={e=>setDays(Number(e.target.value))}>{[30,60,90].map(d=><option value={d} key={d}>{d} days</option>)}</select></label>{checks.data.certifications.length?checks.data.certifications.map(c=><div key={c.id} className="rounded border p-3"><strong>{c.name}</strong><p>{c.status} · {formatDate(c.expires)}</p><Link className="underline" to={`?tab=certifications`}>Review certification</Link></div>):<p>No certifications expire within this window.</p>}</CardContent></Card>
 <Card><CardHeader><CardTitle>Documents, approvals & effective dates</CardTitle></CardHeader><CardContent className="space-y-3"><p>{checks.data.pending_requests} pending profile change requests. <Link className="underline" to="/hrms?view=approvals">Review requests</Link></p>{checks.data.documents.map(d=><p key={d.id}>{d.name}: {d.status}{d.expired?" · Expired":""}</p>)}{!checks.data.documents.length&&<p>No visible document records. Required documents are defined by the assigned onboarding template.</p>}{checks.data.mandatory_tasks.map(t=><p key={t.id}>Required: {t.name}{t.due?` · Due ${formatDate(t.due)}`:""}</p>)}{checks.data.scheduled_transfers.map(t=><p key={t.id}>Transfer #{t.id}: {t.status} · {formatDate(t.effective)}</p>)}<p><Link className="underline" to={`?tab=documents`}>Open employee documents</Link></p><p>Schedule promotions, transfers and manager changes from HRMS daily work → Transfer / promote. Existing assignments remain effective until the scheduled change is applied.</p></CardContent></Card></>}
 <Card><CardHeader><CardTitle>Profile change history</CardTitle></CardHeader><CardContent className="space-y-3">{history.data?.length?history.data.map(h=><article key={h.id} className="rounded border p-3 break-words"><strong>{h.field.replace(/_/g," ")} · {h.action}</strong><p className="text-sm">{h.before??"Empty"} → {h.after??"Empty"}</p><p className="text-xs text-muted-foreground">{h.entity.replace(/_/g," ")} · {h.at?new Date(h.at).toLocaleString():""} · Actor {h.actor_id??"System"}</p></article>):!history.isPending&&<p>No recorded profile changes yet. Earlier edits may have only field names in the employee timeline.</p>}<p className="text-xs text-muted-foreground">Private values and document links are withheld from history.</p></CardContent></Card>
 </div>;
}
