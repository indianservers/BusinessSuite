import "./hr-daily-work.css";
import { ArrowUpRight, CalendarDays, ClipboardCheck, Clock3, LogOut, Search, UserPlus } from "lucide-react";
import ModuleWorkflowBoard from "@/shared/workflow-board/ModuleWorkflowBoard";
import { NativeSelect } from "@/components/ui/native-select";
import HRTransfer from "./HRTransfer";
import { useMobile } from "@/components/mobile/useMobile";
import {useEffect,useState} from "react";
import {Link,useNavigate,useSearchParams} from "react-router-dom";
import {useQuery,useQueryClient} from "@tanstack/react-query";
import {api} from "@/services/api";
import {useAuthStore} from "@/store/authStore";
import {getRoleKey} from "@/lib/roles";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Dialog,DialogContent,DialogTitle} from "@/components/ui/dialog";
import {HR,PersonSearch,HRQuickAdd,errorText,Person} from "./shared";
import EmployeeActions from "./EmployeeActions";
import {hrScope,useHRWork} from "./state";

// Attendance APIs can return UTC timestamps without an offset (for example SQLite).
function attendanceInstant(value:string){return new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value)?value:value+"Z");}

export default function HRDailyWork(){
 const mobile = useMobile();
 const navigate=useNavigate(),qc=useQueryClient(),user=useAuthStore(s=>s.user),key=hrScope(user?.id,user?.access?.companyId),prefs=useHRWork(s=>s.scopes[key]),saveContext=useHRWork(s=>s.context);
 const role=getRoleKey(user?.role,user?.is_superuser),manager=role!=="employee";
 const [params,setParams]=useSearchParams(),view=params.get("view")||"home",scope=params.get("scope")||(manager?"organization":"mine");
 const today=new Date(),month=params.get("month")||prefs?.context.month||String(today.getMonth()+1),year=params.get("year")||prefs?.context.year||String(today.getFullYear()),employeeId=params.get("employee_id")||prefs?.context.employee_id||"",department=params.get("department_id")||prefs?.context.department_id||"",branch=params.get("branch_id")||prefs?.context.branch_id||"";
 const [transfer,setTransfer]=useState(false);
 const [quick,setQuick]=useState(params.get("new")==="employee"),[selected,setSelected]=useState<string[]>([]),[reason,setReason]=useState(""),[results,setResults]=useState<any[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState(""),[correction,setCorrection]=useState<any>(),[inTime,setInTime]=useState(""),[outTime,setOutTime]=useState(""),[breaks,setBreaks]=useState("0");
 useEffect(()=>{saveContext(key,{month,year,employee_id:employeeId,department_id:department,branch_id:branch});},[key,month,year,employeeId,department,branch]);
 const update=(field:string,value:string)=>{const next=new URLSearchParams(params);if(value)next.set(field,value);else next.delete(field);setParams(next,{replace:true});};
 const home=useQuery({queryKey:["hr-work-home",key,scope],queryFn:()=>api.get<any>(`${HR}/home`,{params:{scope}}).then(r=>r.data)});
 const attendance=useQuery({queryKey:["hr-work-exceptions",key,scope,month,year,employeeId,department,branch],queryFn:()=>api.get<any>(`${HR}/attendance-exceptions`,{params:{scope,month,year,employee_id:employeeId||undefined,department_id:department||undefined,branch_id:branch||undefined}}).then(r=>r.data),enabled:view==="attendance"});
 const approvals=useQuery({queryKey:["hr-work-approvals",key,scope],queryFn:()=>api.get<any>(`${HR}/approvals`,{params:{scope}}).then(r=>r.data),enabled:view==="approvals"});
 const [approvalReview,setApprovalReview]=useState<{key:string;decision:string;name:string;description:string}>();
 const [reviewReason,setReviewReason]=useState("");
 async function decide(decision:string,keys=selected,decisionReason=reason){setBusy(true);setError("");try{const r=await api.post(`${HR}/approvals/decide`,{keys,decision,reason:decisionReason});setApprovalReview(undefined);setResults(r.data.results);setSelected(r.data.results.filter((i:any)=>!i.ok).map((i:any)=>i.key));await qc.invalidateQueries({queryKey:["hr-work-approvals"]});await qc.invalidateQueries({queryKey:["hr-work-home"]});}catch(e){setError(errorText(e));}finally{setBusy(false);}}
 const local=(value:string)=>{if(!value)return "";const d=attendanceInstant(value);return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16);};
 async function correct(){setBusy(true);setError("");try{await api.post(`${HR}/attendance/${correction.id}/correct`,{check_in:inTime?new Date(inTime).toISOString():null,check_out:outTime?new Date(outTime).toISOString():null,break_minutes:Number(breaks),reason});setCorrection(undefined);await qc.invalidateQueries({queryKey:["hr-work-exceptions"]});await qc.invalidateQueries({queryKey:["hr-work-home"]});}catch(e){setError(errorText(e));}finally{setBusy(false);}}
 const shortcuts = [
  { label: "Attendance", to: "/hrms/my-attendance", icon: Clock3 },
  { label: "Apply leave", to: "/hrms/leave?new=leave", icon: CalendarDays },
  { label: "Approvals", to: "/hrms/daily-work?view=approvals", icon: ClipboardCheck },
  { label: "Employee search", to: "/hrms/daily-work?view=people", icon: Search },
 ];
 const metrics = [
  { label: "Pending approvals", count: home.data?.pending_counts?.approvals, view: "approvals", icon: ClipboardCheck },
  { label: "Open punches today", count: home.data?.missing_punches, view: "attendance", icon: Clock3 },
  { label: "Upcoming / recent joiners", count: home.data?.joiner_count, view: "people", icon: UserPlus },
  { label: "Open exits", count: home.data?.exit_count, view: "people", icon: LogOut },
 ];

 const lifecycle = <section className="grid gap-4 md:grid-cols-2"><div className="rounded-xl border p-4"><h2 className="font-semibold">Joiners to prepare</h2>{home.data?.joiners.map((p:any)=><Link className="mt-3 block rounded border p-3 text-sm" key={p.id} to={`/hrms/employees/${p.id}`}>{p.name} · {p.employee_code}<span className="block text-xs">Joining {p.joining_date} · Open joiner checklist</span></Link>)}{!home.data?.joiners.length&&<p className="mt-2 text-sm">No joiners in the coming 30 days or previous 7 days within scope.</p>}</div><div className="rounded-xl border p-4"><h2 className="font-semibold">Exits requiring coordination</h2>{home.data?.exits.map((e:any)=><Link key={e.id} className="mt-3 block rounded border p-3 text-sm" to={`/hrms/employees/${e.employee_id}`}>{e.employee?.name||`Employee #${e.employee_id}`} · {e.employee?.employee_code} · Exit #{e.id} · {e.status}<span className="block">Last working day: {e.last_working_date||"Not set"}</span></Link>)}{!home.data?.exits.length&&<p className="mt-2 text-sm">No open exits within your permitted scope.</p>}</div></section>;

 return <main className="hr-daily-work mx-auto max-w-[1600px] space-y-5 p-2 sm:p-4">
  <header className="hr-daily-work-header">
    <div>
      <h1 className="page-title">HR daily work</h1>
      <p className="page-description">People, exceptions, approvals and employee lifecycle.</p>
    </div>
    <div className="hr-daily-work-actions">
      {home.data?.can_create && <Button onClick={()=>setQuick(true)}><UserPlus aria-hidden="true" size={17} />Quick Add Employee</Button>}
      <Button variant="outline" asChild><Link to="/hrms/payroll">Guided payroll</Link></Button>
      {home.data?.can_manage && <Button variant="outline" onClick={()=>setTransfer(true)}>Bulk employee changes</Button>}
    </div>
  </header>
  <nav aria-label="HR work views" className="hr-daily-work-views">
    {[["home","Daily overview"],["people","People & lifecycle"],["attendance","Attendance exceptions"],["approvals","Approval inbox"]].map(([value,label])=>
      <Button key={value} aria-pressed={view===value} variant={view===value?"default":"ghost"} onClick={()=>update("view",value)}>
        {label}{value==="approvals" && home.data?.pending_counts?.approvals != null ? ` (${home.data.pending_counts.approvals})` : ""}
      </Button>
    )}
  </nav>
  <div className="hr-daily-work-scope grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
    <PersonSearch select={p=>{update("employee_id",String(p.id));navigate(`/hrms/employees/${p.id}`);}}/>
    <NativeSelect aria-label="HR work scope" className="rounded border p-2" value={scope} onChange={e=>update("scope",e.target.value)}>
      <option value="mine">My Work</option><option value="team">My Team</option><option value="organization">Organization (permitted scope)</option>
    </NativeSelect>
  </div>
  {home.data && <details className="hr-daily-work-scope-note">
    <summary>Scope and last update</summary>
    <p>{home.data.scope_note} {home.data.refreshed_at && `Updated ${new Date(home.data.refreshed_at).toLocaleString()}.`}</p>
  </details>}
 {home.isError&&<p role="alert">{errorText(home.error)} <button onClick={()=>home.refetch()}>Retry overview</button></p>}{error&&<p role="alert">{error}</p>}
 {view==="home"&&<>
  <section aria-label="Daily totals" className="hr-daily-work-metrics">
    {metrics.map(({label,count,view:target,icon:Icon})=><button key={label} type="button" className="hr-daily-work-metric" onClick={()=>update("view",target)}>
      <span className="hr-daily-work-icon"><Icon size={17} aria-hidden="true"/></span>
      <span className="hr-daily-work-count">{count ?? "—"}</span>
      <span className="hr-daily-work-label">{label}</span>
    </button>)}
  </section>
  <nav aria-label="HR shortcuts" className="hr-daily-work-shortcuts">
    {shortcuts.map(({label,to,icon:Icon})=><Link key={label} to={to}>
      <Icon size={16} aria-hidden="true"/><span>{label}</span><ArrowUpRight className="hr-daily-work-link-arrow" size={14} aria-hidden="true"/>
    </Link>)}
  </nav>
  {mobile ? <details className="hr-daily-work-disclosure">
    <summary>Workflow board</summary>
    <ModuleWorkflowBoard module="hrms" />
  </details> : <ModuleWorkflowBoard module="hrms" />}
  {mobile ? <details className="hr-daily-work-disclosure">
    <summary>Joiners and exits</summary>
    {lifecycle}
  </details> : lifecycle}
 </>}
 {view==="people"&&<section className="space-y-4"><p className="text-sm">Find an employee above, or select one for their unified action panel. The full employee form remains available for detailed records.</p><PersonSearch label="Select employee to manage" select={p=>update("employee_id",String(p.id))}/>{employeeId&&<EmployeeActions key={employeeId} id={Number(employeeId)}/>}<div className="flex flex-wrap gap-3 text-sm"><Link className="underline" to="/hrms/employees">Full employee list</Link><Link className="underline" to="/hrms/probation">Probation deadlines and reviews</Link><Link className="underline" to="/hrms/onboarding">Onboarding templates</Link><Link className="underline" to="/hrms/exit">Exit case management</Link></div></section>}
 {view==="attendance"&&<section className="space-y-4"><h2 className="text-lg font-semibold">Attendance exceptions</h2><div className="flex flex-wrap items-end gap-3"><label className="text-sm">Month<Input aria-label="Exception month" type="month" value={`${year}-${month.padStart(2,"0")}`} onChange={e=>{const [y,m]=e.target.value.split("-");const next=new URLSearchParams(params);next.set("year",y);next.set("month",String(Number(m)));setParams(next,{replace:true});}}/></label><Button variant="outline" onClick={()=>{saveContext(key,{employee_id:""});const next=new URLSearchParams(params);next.delete("employee_id");setParams(next,{replace:true});}}>All permitted employees</Button><Link className="text-sm underline" to={`/hrms/attendance?month=${month}&year=${year}${employeeId?`&employee_id=${employeeId}`:""}`}>Attendance register</Link></div><p className="text-xs">{attendance.data?.boundary} Hours reflect recorded calculations; payable days follow payroll rules, leave and monthly locks.</p>{attendance.isPending&&<p role="status">Loading attendance exceptions…</p>}{attendance.isError&&<p role="alert">{errorText(attendance.error)} <button onClick={()=>attendance.refetch()}>Retry exceptions</button></p>}{attendance.data?.items.map((r:any)=><article key={r.id} className="flex flex-wrap justify-between gap-3 rounded-xl border p-4"><div><Link className="font-semibold underline" to={`/hrms/employees/${r.employee.id}`}>{r.employee.name} · {r.employee.employee_code}</Link><p className="text-sm">{r.date} · {r.issues.join(" · ")}</p><p className="text-xs">Recorded hours: {r.hours} · Expected shift: {r.expected_hours} · Overtime: {r.overtime}</p><p className="text-xs">{r.remarks}</p></div><Button disabled={!r.can_correct} variant="outline" onClick={()=>{setCorrection(r);setInTime(local(r.check_in));setOutTime(local(r.check_out));setReason("");setBreaks("0");setError("");}}>Correct attendance</Button>{!r.can_correct&&<p className="text-xs">Attendance management permission is required.</p>}</article>)}{attendance.data&&!attendance.data.items.length&&<p>No recorded exceptions match these filters.</p>}</section>}
 {view==="approvals"&&<section className="space-y-4"><h2 className="text-lg font-semibold">Unified HR approval inbox</h2><p className="text-sm">Leave, attendance corrections, expenses and timesheets. Pending counts and decisions use the original source records. <Button asChild variant="outline"><Link className="underline" to="/hrms/approval-os">Open configured approval workflows</Link></Button></p><p className="text-xs">{approvals.data?.boundary}</p><div className="flex flex-wrap gap-2">{Object.entries(approvals.data?.counts||{}).map(([k,n])=><span className="rounded border p-2 text-sm capitalize" key={k}>{k}: {String(n)}</span>)}</div>{selected.length > 0 && <label className="block text-sm">Decision / correction reason<Input aria-label="Approval decision reason" value={reason} onChange={e=>setReason(e.target.value)} placeholder="Explain the review"/></label>}<div className="flex flex-wrap gap-2"><Button variant="outline" onClick={()=>setSelected(approvals.data?.items.filter((i:any)=>i.can_decide).map((i:any)=>i.key)||[])}>Select eligible requests</Button>{selected.length > 0 && <><Button disabled={busy||!selected.length||reason.trim().length<3} onClick={()=>void decide("approve")}>Approve selected ({selected.length})</Button><Button variant="outline" disabled={busy||!selected.length||reason.trim().length<3} onClick={()=>void decide("request_correction")}>Request correction</Button></>}</div>{results.map(r=><p role={r.ok?"status":"alert"} key={r.key} className="rounded border p-2 text-sm">{r.key}: {r.ok?"Saved":r.error}</p>)}{results.some(r=>!r.ok)&&<Button variant="outline" disabled={busy||reason.trim().length<3} onClick={()=>void decide("approve",results.filter(r=>!r.ok).map(r=>r.key))}>Retry failed approvals</Button>}{approvals.isPending&&<p role="status">Loading approval sources…</p>}{approvals.isError&&<p role="alert">{errorText(approvals.error)} <button onClick={()=>approvals.refetch()}>Retry approvals</button></p>}{approvals.data?.items.map((i:any)=><article className="space-y-2 rounded-xl border p-4" key={i.key}><div className="flex flex-wrap items-center justify-between gap-3"><label className="flex items-center gap-2"><input type="checkbox" disabled={!i.can_decide} checked={selected.includes(i.key)} onChange={e=>setSelected(s=>e.target.checked?[...s,i.key]:s.filter(k=>k!==i.key))}/><strong>{i.employee.name} · {i.employee.employee_code}</strong></label><span className="text-sm capitalize">{i.kind} · {i.status}</span></div><p className="text-sm">{i.description}</p>{i.amount&&<p className="font-medium">{i.reference} · {i.currency} {Number(i.amount).toLocaleString()}</p>}{i.period_start&&<p className="text-sm">{i.period_start} → {i.period_end} · {i.total_hours} hours</p>}{i.requested_check_in&&<p className="text-sm">Requested punches: {new Date(i.requested_check_in).toLocaleString()} → {i.requested_check_out?new Date(i.requested_check_out).toLocaleString():"Not provided"}</p>}{i.entries?.map((e:any,index:number)=><p className="text-xs" key={index}>{e.date}: {e.task} · {e.hours} hours</p>)}{i.review_comment&&<p className="rounded border p-2 text-sm">Review / correction feedback: {i.review_comment}</p>}{i.from_date&&<p className="text-sm">{i.from_date} → {i.to_date} · {i.days} days</p>}<p className="text-xs">Approval path: {i.approval_path.join(" → ")}</p><p className="text-sm">Current approver: {i.current_approver} · Waiting: {i.waiting_hours===null?"Submission time unavailable":`${i.waiting_hours} hours`}</p><p className="text-xs">{i.path_source}</p>{i.team_absences?.length>0&&<div className="text-xs">Team availability: {i.team_absences.map((a:any)=>`${a.employee.name} on approved leave ${a.from_date}–${a.to_date}`).join("; ")}</div>}{i.restricted_reason&&<p className="text-xs">{i.restricted_reason}</p>}<div className="flex flex-wrap gap-2">{i.can_decide&&<><Button size="sm" disabled={busy} onClick={()=>{setReviewReason("");setApprovalReview({key:i.key,decision:"approve",name:i.employee.name,description:i.description});}}>Approve</Button><Button size="sm" variant="outline" disabled={busy} onClick={()=>{setReviewReason("");setApprovalReview({key:i.key,decision:"reject",name:i.employee.name,description:i.description});}}>Reject</Button></>}<Button asChild variant="outline"><Link className="p-2 text-sm underline" to={i.url}>Open original request</Link></Button></div></article>)}{approvals.data&&!approvals.data.items.length&&<p>No pending requests in this scope.</p>}</section>}
 {transfer&&<HRTransfer close={()=>setTransfer(false)} saved={()=>{void qc.invalidateQueries({queryKey:["hr-person-actions"]});void home.refetch();}}/>}
 {quick&&<HRQuickAdd close={()=>setQuick(false)} saved={id=>{setQuick(false);navigate(`/hrms/employees/${id}`);}}/>}
 {correction&&<Dialog open onOpenChange={open=>{if(!open&&!busy)setCorrection(undefined);}}><DialogContent className="hr-daily-work-dialog max-md:!top-[calc((100dvh-var(--mobile-keyboard-inset,0px))/2)] max-md:!max-h-[calc(var(--mobile-viewport-height,100dvh)-16px)] max-md:[&_input]:text-base"><DialogTitle>Correct attendance</DialogTitle><p className="text-sm">{correction.employee.name} · {correction.employee.employee_code} · {correction.date}. Month and employee filters will be preserved.</p><section className="grid grid-cols-1 gap-3 rounded border p-3 text-sm sm:grid-cols-2" aria-label="Attendance correction comparison"><div><h3 className="font-semibold">Recorded punches</h3><p>Check-in: {correction.check_in ? attendanceInstant(correction.check_in).toLocaleString() : "Missing punch"}</p><p>Check-out: {correction.check_out ? attendanceInstant(correction.check_out).toLocaleString() : "Missing punch"}</p><p>Hours: {correction.hours}</p></div><div><h3 className="font-semibold">Proposed correction</h3><p>Check-in: {inTime ? new Date(inTime).toLocaleString() : "Not entered"}</p><p>Check-out: {outTime ? new Date(outTime).toLocaleString() : "Not entered"}</p><p>Unpaid break: {breaks} minutes</p></div></section><label>Check-in (your local time)<Input aria-label="Corrected check-in" type="datetime-local" value={inTime} onChange={e=>setInTime(e.target.value)}/></label><label>Check-out (your local time)<Input aria-label="Corrected check-out" type="datetime-local" value={outTime} onChange={e=>setOutTime(e.target.value)}/></label><label>Unpaid breaks (minutes)<Input aria-label="Unpaid break minutes" type="number" min="0" value={breaks} onChange={e=>setBreaks(e.target.value)}/></label><p className="text-xs">Recorded hours = elapsed interval minus entered breaks. Overtime = hours above the configured shift duration. Payable days remain subject to leave and payroll rules.</p><label>Correction reason<Input aria-label="Attendance correction reason" value={reason} onChange={e=>setReason(e.target.value)}/></label>{error&&<p role="alert">{error}</p>}<div className="contents max-md:sticky max-md:bottom-0 max-md:z-10 max-md:grid max-md:grid-cols-[auto_minmax(0,1fr)] max-md:gap-2 max-md:border-t max-md:bg-background max-md:py-2">
  <Button type="button" variant="outline" className="min-h-11 md:hidden" disabled={busy} onClick={()=>setCorrection(undefined)}>Cancel</Button>
  <Button className="max-md:min-h-11 max-md:whitespace-normal" disabled={busy||!inTime||!outTime||reason.trim().length<3} onClick={()=>void correct()}>Save attendance correction</Button>
</div></DialogContent></Dialog>}
 {approvalReview&&<Dialog open onOpenChange={open=>{if(!open&&!busy)setApprovalReview(undefined);}}><DialogContent className="hr-daily-work-dialog"><DialogTitle>{approvalReview.decision==="approve"?"Approve request":"Reject request"} · {approvalReview.name}</DialogTitle><p className="text-sm">{approvalReview.description}</p><label className="block text-sm">Decision reason<Input aria-label="Individual approval reason" value={reviewReason} onChange={event=>setReviewReason(event.target.value)}/></label><Button disabled={busy||reviewReason.trim().length<3} onClick={()=>void decide(approvalReview.decision,[approvalReview.key],reviewReason)}>{busy?"Saving…":"Confirm decision"}</Button></DialogContent></Dialog>}</main>;
}
