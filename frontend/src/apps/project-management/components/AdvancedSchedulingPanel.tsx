import GridTable from "@/shared/data-grid/GridTable";
import ReportDeliverySchedule from "@/components/reports/ReportDeliverySchedule";
import { decodeDownloadError } from "@/lib/decode-download-error";
import { useEffect, useState } from "react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { workspaceError } from "../pages/workspaceTypes";

type Calendar = {weekdays:number[];holidays:string[]};
type PlanTask = {id:number;task_key:string;title:string;start_date:string;due_date:string;duration_workdays:number;slack_workdays:number|null};
type Plan = {basis?:string;revision:string;calendar:Calendar;tasks:PlanTask[];changes:(PlanTask&{old_start_date:string|null;old_due_date:string|null})[];critical_task_ids:number[];complete:boolean;excluded_task_ids:number[];finish_date:string|null};
type Analysis = Plan & {baselines:{id:string;name:string;created_at:string}[];variance:{id:number;task_key:string;title:string;start_date:string|null;due_date:string|null;baseline_due_date:string|null;due_variance_days:number|null;in_baseline:boolean}[];removed_baseline_task_count:number};

export default function AdvancedSchedulingPanel({projectId,canManage,onApplied}:{projectId:number;canManage:boolean;onApplied:()=>void}) {
 const base=`/project-management/projects/${projectId}`;
 const [analysis,setAnalysis]=useState<Analysis>();const [preview,setPreview]=useState<Plan>();
 const [calendar,setCalendar]=useState<Calendar>({weekdays:[0,1,2,3,4],holidays:[]});const [holidayText,setHolidayText]=useState("");
 const [baseline,setBaseline]=useState("");const [name,setName]=useState("");const [reload,setReload]=useState(0);
 const [task,setTask]=useState("");const [start,setStart]=useState("");const [end,setEnd]=useState("");
 const [levelResources,setLevelResources]=useState(false);
 const [busy,setBusy]=useState(false);const [error,setError]=useState("");const [notice,setNotice]=useState("");
 useEffect(()=>{const controller=new AbortController();setAnalysis(undefined);setPreview(undefined);setError("");
  void api.get<Analysis>(`${base}/schedule-analysis`,{params:baseline?{baseline_id:baseline}:{},signal:controller.signal}).then(r=>{if(!controller.signal.aborted){setAnalysis(r.data);setCalendar(r.data.calendar);setHolidayText(r.data.calendar.holidays.join("\n"));}}).catch(e=>{if(!controller.signal.aborted)setError(workspaceError(e));});
  return()=>controller.abort();
 },[base,baseline,reload]);
 const invalidate=()=>{setPreview(undefined);setNotice("");};
 function request(){return {level_resources:levelResources,calendar:{...calendar,holidays:holidayText.split(/[\s,]+/).filter(Boolean)},...(task?{task_id:Number(task),start_date:start,due_date:end}:{})};}
 async function buildPreview(){setBusy(true);setError("");setNotice("");setPreview(undefined);try{const r=await api.post<Plan>(`${base}/schedule-preview`,request());setPreview(r.data);}catch(e){setError(workspaceError(e));}finally{setBusy(false);}}
 async function apply(){if(!preview)return;setBusy(true);setError("");try{const r=await api.post<{updated:number}>(`${base}/schedule-apply`,{...request(),expected_revision:preview.revision});setNotice(`${r.data.updated} task schedules updated`);setPreview(undefined);setTask("");setReload(v=>v+1);onApplied();}catch(e){setError(workspaceError(e));setPreview(undefined);}finally{setBusy(false);}}
 async function capture(){if(!analysis)return;setBusy(true);setError("");setNotice("");try{const r=await api.post<{id:string}>(`${base}/schedule-baselines`,{name,expected_revision:analysis.revision});setName("");setBaseline(r.data.id);setReload(v=>v+1);setNotice("Baseline captured. Previous baselines are retained.");}catch(e){setError(workspaceError(e));}finally{setBusy(false);}}
 async function exportReport(format:"csv"|"xlsx"){setBusy(true);setError("");try{const r=await api.get(`${base}/schedule-variance/export`,{params:{format,baseline_id:baseline||undefined},responseType:"blob"});const url=URL.createObjectURL(r.data);const a=document.createElement("a");a.href=url;a.download=`schedule-variance.${format}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){setError(workspaceError(await decodeDownloadError(e)));}finally{setBusy(false);}}
 const plan=preview||analysis;
 const inputClass="mt-1 min-h-10 min-w-0 w-full rounded border bg-background px-3";
 return <section className="space-y-4 rounded-lg border bg-card p-4" aria-label="Advanced project scheduling">
  <header><h2 className="text-lg font-semibold">Advanced scheduling</h2><p className="text-sm text-muted-foreground">Preview dependency cascades before applying. Zero-lag finish-to-start begins on the next working day. Existing starts are lower bounds. Optional resource leveling uses assignee capacity and remaining effort within this project.</p><Button variant="outline" disabled={busy} onClick={()=>setReload(v=>v+1)}>Refresh advanced analysis</Button></header>
  {error&&<p role="alert" className="text-destructive">{error}<Button variant="outline" disabled={busy} onClick={()=>setReload(v=>v+1)}>Reload schedule analysis</Button></p>}
  {notice&&<p role="status">{notice}</p>}
  {!analysis&&!error&&<p role="status">Loading schedule analysis…</p>}
  {analysis&&<>
   <fieldset disabled={busy||!canManage} className="space-y-3"><legend className="font-medium">Project work calendar</legend>
    <div className="flex flex-wrap gap-3">{["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map((day,i)=><label key={day} className="flex min-h-10 items-center gap-2"><input type="checkbox" checked={calendar.weekdays.includes(i)} onChange={e=>{setCalendar(c=>({...c,weekdays:e.target.checked?[...c.weekdays,i]:c.weekdays.filter(d=>d!==i)}));invalidate();}}/>{day}</label>)}</div>
    <label className="block text-sm">Project holidays (YYYY-MM-DD, one per line)<textarea aria-label="Project holidays" className={inputClass} rows={2} value={holidayText} onChange={e=>{setHolidayText(e.target.value);invalidate();}}/></label>
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3"><label className="text-sm">Move a task (optional)<NativeSelect aria-label="Move scheduled task" className={inputClass} value={task} onChange={e=>{const selected=analysis.variance.find(t=>t.id===Number(e.target.value));setTask(e.target.value);setStart(selected?.start_date||"");setEnd(selected?.due_date||"");invalidate();}}><option value="">Enforce current dependencies</option>{analysis.variance.map(t=><option key={t.id} value={t.id}>{t.task_key} · {t.title}</option>)}</NativeSelect></label>
    {task&&<><label className="text-sm">New start<input aria-label="Planned start date" type="date" className={inputClass} value={start} onChange={e=>{setStart(e.target.value);invalidate();}}/></label><label className="text-sm">New due date<input aria-label="Planned due date" type="date" className={inputClass} value={end} onChange={e=>{setEnd(e.target.value);invalidate();}}/></label></>}</div>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={levelResources} onChange={e=>{setLevelResources(e.target.checked);invalidate();}}/>Level project resources (estimates required; other projects excluded)</label>
    {levelResources&&<p className="text-xs text-muted-foreground">Up to 200 tasks, 50 assignees and 366 calendar days. Remaining effort is split equally across assignees. Daily working capacity includes applicable holidays and approved leave. Other project work is not reserved.</p>}
    <Button disabled={!analysis||!calendar.weekdays.length} onClick={()=>void buildPreview()}>{levelResources?"Preview resource plan":"Preview dependency plan"}</Button>
   </fieldset>
   {!canManage&&<p className="text-sm text-muted-foreground">Read-only analysis. Task-management access is required to plan or capture baselines.</p>}
   {plan&&<div className="space-y-2"><h3 className="font-medium">Calculated plan · finish {plan.finish_date||"not available"}</h3><p className="text-sm text-muted-foreground">{plan.basis || "Calculated dates are recommendations until applied. Slack is measured in project working days."}</p>
    {!plan.complete&&<p role="status">Partial analysis: date every task and resolve incomplete dependencies before applying a complete plan. {plan.excluded_task_ids.length} tasks lack a full date range.</p>}
    <div className="overflow-x-auto"><GridTable gridId="AdvancedSchedulingPanel:records-1" className="w-full text-left text-sm"><thead><tr>{["Task","Calculated start","Calculated due","Working days","Slack","Path"].map(h=><th key={h} className="whitespace-nowrap p-2">{h}</th>)}</tr></thead><tbody>{plan.tasks.map(t=><tr key={t.id} className="border-t"><td className="p-2">{t.task_key} · {t.title}</td><td className="whitespace-nowrap p-2">{t.start_date}</td><td className="whitespace-nowrap p-2">{t.due_date}</td><td className="p-2">{t.duration_workdays}</td><td className="p-2">{t.slack_workdays??"—"}</td><td className="p-2">{t.slack_workdays===null?"Resource constrained":t.slack_workdays===0?(plan.complete?"Critical":"Zero slack (partial)"):"Has slack"}</td></tr>)}</tbody></GridTable></div>
   </div>}
   {preview&&<div className="space-y-2 rounded border p-3"><h3 className="font-medium">Impact preview · {preview.changes.length} tasks change</h3>{preview.changes.map(c=><p key={c.id} className="text-sm">{c.task_key}: {c.old_start_date||"undated"}–{c.old_due_date||"undated"} → {c.start_date}–{c.due_date}</p>)}<Button disabled={busy||!canManage||!preview.complete} onClick={()=>void apply()}>{levelResources?"Apply resource plan":"Apply dependency plan"}</Button><p className="text-xs text-muted-foreground">Changes apply together. A concurrent date, dependency or status change requires a new preview. Completed/cancelled tasks are never moved automatically.</p></div>}
   {!!analysis.baselines.length&&<ReportDeliverySchedule key={projectId} endpoint={`/project-management/report-delivery/pms/${projectId}/delivery-schedule`}/>}
   <div className="space-y-3 border-t pt-3"><h3 className="font-medium">Baselines and schedule variance</h3><p className="text-xs text-muted-foreground">Up to 20 named baselines are retained per project. Capturing a baseline never replaces an earlier snapshot.</p>
    {!!analysis.baselines.length&&<div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy} onClick={()=>void exportReport("csv")}>Export variance CSV</Button><Button variant="outline" disabled={busy} onClick={()=>void exportReport("xlsx")}>Export variance Excel</Button></div>}
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2"><label className="text-sm">Compare baseline<NativeSelect aria-label="Compare schedule baseline" className={inputClass} disabled={busy} value={baseline} onChange={e=>setBaseline(e.target.value)}><option value="">Latest baseline</option>{analysis.baselines.map(b=><option key={b.id} value={b.id}>{b.name} · {new Date(b.created_at).toLocaleString()}</option>)}</NativeSelect></label>
    {canManage&&<form className="flex flex-wrap items-end gap-2" onSubmit={e=>{e.preventDefault();void capture();}}><label className="flex-1 text-sm">New baseline name<input aria-label="Baseline name" required maxLength={100} disabled={busy} className={inputClass} value={name} onChange={e=>setName(e.target.value)}/></label><Button disabled={busy||!name.trim()||analysis.baselines.length>=20}>Capture baseline</Button></form>}</div>
    {!!analysis.baselines.length&&<><p className="text-sm text-muted-foreground">Current due date minus captured due date, in calendar days. Positive means later. Newly added/undated tasks have no variance. Removed baseline tasks: {analysis.removed_baseline_task_count}.</p><div className="overflow-x-auto"><GridTable gridId="AdvancedSchedulingPanel:records-2" className="w-full text-left text-sm"><thead><tr><th className="p-2">Task</th><th className="p-2">Baseline due</th><th className="p-2">Current due</th><th className="p-2">Variance (days)</th></tr></thead><tbody>{analysis.variance.map(t=><tr key={t.id} className="border-t"><td className="p-2">{t.task_key}</td><td className="whitespace-nowrap p-2">{t.baseline_due_date||"Not captured"}</td><td className="whitespace-nowrap p-2">{t.due_date||"Undated"}</td><td className="p-2">{t.due_variance_days??"—"}</td></tr>)}</tbody></GridTable></div></>}
   </div>
  </>}
 </section>;
}
