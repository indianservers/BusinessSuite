import React, { useState } from "react";
import { api } from "@/services/api";
import { useRefreshableEffect } from "@/lib/page-refresh";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { Bootstrap, errorMessage } from "./api";

const root = "/crm/lead-management";
type Process = {enabled: boolean; pipelineId?: number; managerId?: number; ownerIds: number[]; stages: string[]};
type Metrics = {counts: Record<string, number>; definition: string};
export function SalesProcessPanel({bootstrap, search, stage, owner, revision, changed}: {bootstrap: Bootstrap; search: string; stage: string; owner: string; revision: number; changed: () => void}) {
  const [metrics, setMetrics] = useState<Metrics>();
  const [process, setProcess] = useState<Process>();
  const [manager, setManager] = useState(String(bootstrap.userId));
  const [owners, setOwners] = useState<number[]>([bootstrap.userId]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useRefreshableEffect(() => {
    let active = true;
    setError("");
    Promise.all([api.get<Metrics>(`${root}/meeting-metrics`, {params: {search, stage, owner: owner || undefined}}), api.get<Process>(`${root}/sales-process`)]).then(([m, p]) => {
      if (!active) return;
      setMetrics(m.data); setProcess(p.data);
      if (p.data.managerId) setManager(String(p.data.managerId));
      if (p.data.ownerIds.length) setOwners(p.data.ownerIds);
    }).catch(e => {if(active) setError(errorMessage(e));});
    return () => {active = false;};
  }, [search, stage, owner, revision]);
  return <section aria-label="Consultation and demo performance" className="lm-sales-process">
    <h2>Consultations & demos</h2>
    <div className="lm-metrics">{["Scheduled", "Confirmed", "Attended", "No-show", "Rescheduled"].map(name => <div className="lm-meeting-metric" key={name}><span>{name}</span><strong>{metrics?.counts[name] ?? "—"}</strong></div>)}</div>
    <p className="text-xs text-muted-foreground">{metrics?.definition || "Meeting counts across permitted leads. Loading…"}</p>
    {error && <p role="alert">{error}</p>}
    <details><summary>Sales process & automation {process?.enabled ? "· Enabled" : "· Setup required"}</summary>
      <p>Leads: New → Contacted → Qualified → Convert to opportunity.</p>
      <p>Deals: Consultation Scheduled → Demo Completed → Proposal Sent → Negotiation → Won / Lost.</p>
      <ul className="list-disc pl-5 text-sm"><li>Assign new leads immediately using round-robin.</li><li>Remind the owner after 24 hours without first contact.</li><li>Booking a demo creates a CRM calendar event.</li><li>Recording demo attendance creates a next-day follow-up task.</li><li>Proposal Sent creates a task and an in-app reminder after two days.</li><li>No response for seven days alerts the selected sales manager.</li><li>Lost leads require a reason.</li><li>After 30 days, remind the owner to nurture leads with recorded permission.</li></ul>
      <p className="text-xs text-muted-foreground">Timed reminders run through the CRM worker or protected scheduler. Customer status is applied when the deal is Won. External calendar sync depends on a connected provider.</p>
      {bootstrap.canAdmin && <form className="grid gap-3 mt-3" onSubmit={async e => {e.preventDefault(); setBusy(true);setError("");try {await api.post(`${root}/sales-process/setup`,{ownerIds:owners,managerId:Number(manager)});changed();}catch(e){setError(errorMessage(e));}finally{setBusy(false);}}}>
        <label>Sales manager<NativeSelect value={manager} onChange={e=>setManager(e.target.value)}>{bootstrap.owners.map(o=><option key={o.id} value={o.id}>{o.name}</option>)}</NativeSelect></label>
        <fieldset><legend>Assignment pool</legend>{bootstrap.owners.map(o=><label className="lm-check" key={o.id}><input type="checkbox" checked={owners.includes(o.id)} onChange={e=>setOwners(current=>e.target.checked?[...current,o.id]:current.filter(id=>id!==o.id))}/>{o.name}</label>)}</fieldset>
        <Button disabled={busy || !owners.length} type="submit">{busy ? "Saving…" : process?.enabled ? "Update sales automation" : "Enable sales process & automation"}</Button>
      </form>}
    </details>
  </section>;
}

type Meeting = {id:number;title:string;status:string;start_time:string;end_time:string;outcome?:string};
export function LeadMeetingOutcomes({id, canManage, disabled, changed}: {id: number; canManage: boolean; disabled?: boolean; changed: () => void}) {
  const [meetings,setMeetings]=useState<Meeting[]>([]);
  const [revision,setRevision]=useState(0);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const [replacement,setReplacement]=useState<Record<number,string>>({});
  const [consent,setConsent]=useState(false);
  const [evidence,setEvidence]=useState("");
  const [saved,setSaved]=useState("");
  const [purpose,setPurpose]=useState("consultation");
  const [startAt,setStartAt]=useState("");
  useRefreshableEffect(()=>{let active=true;api.get<Meeting[]>(`${root}/leads/${id}/meetings`).then(r=>{if(active)setMeetings(r.data);}).catch(e=>{if(active)setError(errorMessage(e));});return()=>{active=false;};},[id,revision]);
  useRefreshableEffect(()=>{let active=true;api.get<{allowed:boolean;evidence:string}>(`${root}/leads/${id}/nurture-consent`).then(r=>{if(active){setConsent(r.data.allowed);setEvidence(r.data.evidence);}}).catch(e=>{if(active)setError(errorMessage(e));});return()=>{active=false;};},[id]);
  const update = async (meeting:Meeting,status:string) => {
    setBusy(true);setError("");
    try {await api.patch(`${root}/leads/${id}/meetings/${meeting.id}`,{status,...(status==="Rescheduled"?{startAt:replacement[meeting.id]?new Date(replacement[meeting.id]).toISOString():null}:{})});setRevision(v=>v+1);changed();}catch(e){setError(errorMessage(e));}finally{setBusy(false);}
  };
  return <details className="lm-sales-process"><summary>Consultations, demo outcomes & nurture permission</summary>
    {error&&<p role="alert">{error}</p>}
    {canManage&&<form className="flex flex-wrap items-end gap-2 my-3" onSubmit={async e=>{e.preventDefault();setBusy(true);setError("");try{await api.post(`${root}/leads/${id}/activity`,{type:"meeting",purpose,outcome:purpose==="demo"?"Product demonstration":"Requirements consultation",startAt:new Date(startAt).toISOString(),responded:false});setStartAt("");setRevision(v=>v+1);changed();}catch(e){setError(errorMessage(e));}finally{setBusy(false);}}}><label>Meeting type<NativeSelect value={purpose} onChange={e=>setPurpose(e.target.value)}><option value="consultation">Consultation</option><option value="demo">Product demo</option></NativeSelect></label><label>Starts at<input required type="datetime-local" value={startAt} onChange={e=>setStartAt(e.target.value)}/></label><Button type="submit" disabled={busy||disabled||!startAt}>Book calendar event</Button></form>}
    {!meetings.length&&<p>No meetings recorded. Use “Log call or meeting outcome” to schedule a consultation or demo.</p>}
    {meetings.map(meeting=><article key={meeting.id} className="rounded border p-3 my-2"><strong>{meeting.title}</strong><p>{new Date(meeting.start_time).toLocaleString()} · {meeting.status}</p>
      {canManage&&["Scheduled","Confirmed"].includes(meeting.status)&&<div className="flex flex-wrap gap-2"><Button size="sm" disabled={busy||disabled||meeting.status==="Confirmed"} onClick={()=>void update(meeting,"Confirmed")}>Confirm</Button><Button size="sm" disabled={busy||disabled} onClick={()=>void update(meeting,"Attended")}>Attended</Button><Button size="sm" disabled={busy||disabled} onClick={()=>void update(meeting,"No-show")}>No-show</Button><Button size="sm" variant="outline" disabled={busy||disabled} onClick={()=>void update(meeting,"Cancelled")}>Cancel</Button><label>Replacement time<input type="datetime-local" value={replacement[meeting.id]||""} onChange={e=>setReplacement(v=>({...v,[meeting.id]:e.target.value}))}/></label><Button size="sm" disabled={busy||disabled||!replacement[meeting.id]} onClick={()=>void update(meeting,"Rescheduled")}>Reschedule</Button></div>}
    </article>)}
    {canManage&&<form className="grid gap-2" onSubmit={async e=>{e.preventDefault();setBusy(true);setSaved("");setError("");try{await api.put(`${root}/leads/${id}/nurture-consent`,{allowed:consent,evidence});setSaved(consent?"Nurture permission saved":"Nurture permission withdrawn");changed();}catch(e){setError(errorMessage(e));}finally{setBusy(false);}}}><label className="lm-check"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/>Permission to receive nurture follow-ups</label><label>Permission evidence / withdrawal reason<input required maxLength={1000} value={evidence} onChange={e=>setEvidence(e.target.value)} placeholder="For example: permission given during call on 15 Nov"/></label><Button type="submit" disabled={busy||disabled||!evidence.trim()}>Record nurture permission</Button>{saved&&<p role="status">{saved}</p>}<p className="text-xs">Nurture reminders are internal tasks for the owner. Permission changes are recorded in the lead history.</p></form>}
  </details>;
}

