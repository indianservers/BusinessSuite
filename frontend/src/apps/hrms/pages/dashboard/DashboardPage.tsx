import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQueries, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { RefreshCw, Users, Clock, CalendarDays, DollarSign, ArrowRight } from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { usePageTitle } from "@/hooks/use-page-title";
import { Button } from "@/components/ui/button";
import ModuleWorkflowBoard from "@/shared/workflow-board/ModuleWorkflowBoard";
import { PersonalHighlights } from "./PersonalHighlights";
import "./hrms-dashboard.css";

type Section = "workforce" | "attendance" | "leave" | "payroll" | "onboarding" | "probation" | "exits" | "compliance";
type Context = { business_date: string; timezone: string; currency: string; scope: string; personal: boolean; sections: Section[]; permissions: string[]; superuser: boolean; departments: {id:number;name:string}[]; locations: {id:number;name:string}[]; employment_types:string[] };
type Row = {id:string;employee_id:number|null;name:string;detail:string;date:string|null;status:string;href:string};
type Data = {section:Section;context:{as_of:string;business_date:string;timezone:string;from_date:string;to_date:string;previous_from:string;previous_to:string};metrics:Record<string,number|string|null>;series:Record<string,string|number>[];rows:Row[];total_rows:number;notes:string[]};
const titles: Record<Section,string> = {workforce:"Workforce",attendance:"Attendance",leave:"Leave approvals & availability",payroll:"Payroll controls",onboarding:"Onboarding blockers",probation:"Probation milestones",exits:"Exit readiness",compliance:"Compliance deadlines"};
const endpoint = "/reports/hrms-dashboard";
const sectionNames:Section[] = ["workforce","attendance","leave","payroll","onboarding","probation","exits","compliance"];
function subtract(day:string, days:number) { const date=new Date(day+"T12:00:00Z");date.setUTCDate(date.getUTCDate()-days);return date.toISOString().slice(0,10); }
function number(data:Data|undefined,key:string) { const value=data?.metrics[key];return typeof value === "number" ? value : null; }
function change(current:number|null, previous:number|null) { if(current===null||previous===null)return "Comparison unavailable"; const difference=current-previous;return `${difference>0?"+":""}${difference.toLocaleString()} versus previous period${previous ? ` (${((difference/Math.abs(previous))*100).toFixed(1)}%)` : "; prior value was zero"}`; }

function SectionState({query,children,zone}:{query:UseQueryResult<Data,Error>;children:React.ReactNode;zone:string}) {
 return <>{query.isPending && <p className="hrd-loading" role="status">Loading this section…</p>}{query.isError && <div role="alert" className="hrd-error">{query.data ? "Refresh failed. Previous values are stale." : "Unavailable. This section could not be verified."}<Button variant="outline" size="sm" onClick={()=>void query.refetch()}>Retry section</Button></div>}{query.data && <><p className="hrd-freshness">{query.isFetching?"Refreshing… · ":""}{query.isError?"Stale · ":""}Updated {new Date(query.data.context.as_of).toLocaleString(undefined,{timeZone:zone})} · {zone}</p>{children}</>}</>;
}

export default function DashboardPage() {
 usePageTitle("HRMS dashboard");
 const {user,isAuthenticated}=useAuthStore();
 const client=useQueryClient();
 const [params,setParams]=useSearchParams();
 const branch=sessionStorage.getItem("suite-branch"), tenant=sessionStorage.getItem("suite-tenant");
 const identity=[user?.id,user?.access?.companyId,branch,tenant,user?.role,JSON.stringify(user?.access?.grants)];
 const context=useQuery({queryKey:["hrms-dashboard-context",...identity],enabled:isAuthenticated&&!!user,queryFn:({signal})=>api.get<Context>(endpoint+"/context",{signal,progress:false}).then(r=>r.data),retry:false,refetchInterval:60_000});
 const ctx=context.data;
 const to=params.get("to_date") || ctx?.business_date || "";
 const from=params.get("from_date") || (to?subtract(to,29):"");
 const department=params.get("department_id") || "", location=params.get("location_id") || "", employment=params.get("employment_type") || "";
 const [draft,setDraft]=useState({from,to,department,location,employment});
 useEffect(()=>setDraft({from,to,department,location,employment}),[from,to,department,location,employment]);
 const filters={from_date:from,to_date:to,department_id:department||undefined,location_id:location||undefined,employment_type:employment||undefined};
 const valid=!!from&&!!to&&from<=to&&(new Date(to).getTime()-new Date(from).getTime())/86400000<=365;
 const queries=useQueries({queries:sectionNames.map(section=>({queryKey:["hrms-dashboard-section",...identity,section,filters,ctx?.business_date],enabled:!!ctx&&ctx.sections.includes(section)&&valid,queryFn:({signal}:{signal:AbortSignal})=>api.get<Data>(endpoint+"/"+section,{params:filters,signal,progress:false}).then(r=>r.data),retry:false,refetchInterval:300_000}))});
 const get=(section:Section)=>queries[sectionNames.indexOf(section)];
 const workforce=get("workforce"),attendance=get("attendance"),leave=get("leave"),payroll=get("payroll");
 const money=(value:number)=>new Intl.NumberFormat(undefined,{style:"currency",currency:ctx?.currency||"INR"}).format(value);
 const can=(permission:string)=>!!ctx&&(ctx.superuser||ctx.permissions.includes(permission));
 const selected=params.get("section") as Section|null;
 const detailsAllowed=!!selected&&sectionNames.includes(selected)&&!!ctx?.sections.includes(selected);
 const detailFilters={...filters,record_status:params.get("record_status")||undefined,record_date:params.get("record_date")||undefined};
 const detailQuery=useQuery({queryKey:["hrms-dashboard-section",...identity,selected,"details",detailFilters,ctx?.business_date],enabled:detailsAllowed&&valid,queryFn:({signal})=>api.get<Data>(endpoint+"/"+selected,{params:detailFilters,signal,progress:false}).then(r=>r.data),retry:false});
 const selection=detailsAllowed?detailQuery:null;
 const selectedRows=selection?.data?.rows||[];
 const drill=(section:Section,status?:string,day?:string)=>{const next=new URLSearchParams(params);next.set("from_date",from);next.set("to_date",to);next.set("section",section);next.delete("record_status");next.delete("record_date");if(status)next.set("record_status",status);if(day)next.set("record_date",day);return `?${next.toString()}#hrd-details`;};
 const refresh=()=>Promise.all([client.invalidateQueries({queryKey:["hrms-dashboard-context"]}),client.invalidateQueries({queryKey:["hrms-dashboard-section"]}),client.invalidateQueries({queryKey:["hrms-dashboard-personal"]}),client.invalidateQueries({queryKey:["dashboard-workflow","hrms"]})]);
 const busy=context.isFetching||queries.some(q=>q.isFetching)||detailQuery.isFetching;
 const metrics=[
  {section:"workforce" as Section,title:"Employee records",value:number(workforce.data,"total"),detail:`${number(workforce.data,"active")??"Unavailable"} active / probation`,icon:Users,href:drill("workforce")},
  {section:"attendance" as Section,title:"Present today",value:number(attendance.data,"present"),detail:`${number(attendance.data,"wfh")??"Unavailable"} remote · ${number(attendance.data,"absent")??"Unavailable"} recorded absent`,icon:Clock,href:drill("attendance","Present",ctx?.business_date)},
  {section:"leave" as Section,title:ctx?.personal?"My pending leave":"Pending leave approvals",value:number(leave.data,"pending"),detail:`Oldest: ${number(leave.data,"oldest_days")??"Unavailable"} days`,icon:CalendarDays,href:drill("leave","Pending")},
  {section:"payroll" as Section,title:"Net payroll in period",value:payroll.data?.series.length?money(number(payroll.data,"net")||0):null,detail:payroll.data?.series.length?change(number(payroll.data,"net"),number(payroll.data,"previous_net")):"No completed payroll in this period",icon:DollarSign,href:drill("payroll")},
 ];
 const actions=[
  {label:"My attendance",href:"/hrms/my-attendance",show:!!user?.employee_id}, {label:"Apply leave",href:"/hrms/leave",show:can("leave_apply")},
  {label:"My payslips",href:"/hrms/my-payslips",show:!!user?.employee_id&&can("payroll_view")}, {label:"My documents",href:"/hrms/documents",show:!!user?.employee_id},
  {label:"Add employee",href:"/hrms/employees/new",show:can("employee_create")&&!ctx?.personal}, {label:"Run payroll",href:"/hrms/payroll",show:can("payroll_run")&&!ctx?.personal},
  {label:"Review approvals",href:"/hrms/manager-dashboard",show:can("leave_approve")}, {label:"View reports",href:"/hrms/reports",show:can("reports_view")&&!ctx?.personal},
 ];
 return <div className="hrd-dashboard">
  <header className="hrd-header"><div><h1>{ctx?.personal?"My HR workspace":"HRMS dashboard"}</h1><p>{ctx?.scope||"Loading authorized workspace…"}{ctx&&` · Business date ${ctx.business_date} · ${ctx.timezone}`}</p></div><Button variant="outline" disabled={busy} onClick={()=>void refresh()}><RefreshCw size={16}/>{busy?"Refreshing…":"Refresh dashboard"}</Button></header>
  {context.isError&&<p role="alert" className="hrd-error">{ctx?"Workspace settings refresh failed; settings may be stale.":"Workspace settings are unavailable."}<Button onClick={()=>void context.refetch()}>Retry workspace</Button></p>}
  {context.isPending&&<p role="status">Loading workspace settings…</p>}
  {ctx&&<>
   <form className="hrd-filters" onSubmit={e=>{e.preventDefault();const next=new URLSearchParams();next.set("from_date",draft.from);next.set("to_date",draft.to);if(draft.department)next.set("department_id",draft.department);if(draft.location)next.set("location_id",draft.location);if(draft.employment)next.set("employment_type",draft.employment);setParams(next);}}>
    <label>From<input type="date" required value={draft.from} max={draft.to} onChange={e=>setDraft({...draft,from:e.target.value})}/></label><label>To<input type="date" required value={draft.to} min={draft.from} onChange={e=>setDraft({...draft,to:e.target.value})}/></label>
    <label>Department<select aria-label="Department" value={draft.department} onChange={e=>setDraft({...draft,department:e.target.value})}><option value="">All permitted departments</option>{ctx.departments.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
    <label>Location<select aria-label="Location" value={draft.location} onChange={e=>setDraft({...draft,location:e.target.value})}><option value="">All permitted locations</option>{ctx.locations.map(l=><option key={l.id} value={l.id}>{l.name}</option>)}</select></label>
    <label>Employment type<select aria-label="Employment type" value={draft.employment} onChange={e=>setDraft({...draft,employment:e.target.value})}><option value="">All employment types</option>{ctx.employment_types.map(t=><option key={t}>{t}</option>)}</select></label><Button disabled={!draft.from||!draft.to||draft.from>draft.to||(new Date(draft.to).getTime()-new Date(draft.from).getTime())/86400000>365}>Apply filters</Button><Button type="button" variant="ghost" onClick={()=>setParams({})}>Reset filters</Button>
   </form>
   <p className="hrd-note">Period: {from} to {to}. Workforce filters apply to HR summary sections; the recruitment board has its own filters. Today, current queues, and upcoming deadlines are labeled separately.</p>
   {!valid&&<p role="alert">Choose an ordered reporting period of at most 366 days.</p>}
   {valid&&<>
   <div className="hrd-metrics">{metrics.filter(m=>ctx.sections.includes(m.section)).map(m=>{const query=get(m.section);return <article className="hrd-metric" key={m.section}><m.icon size={22}/><h2>{m.title}</h2><Link to={m.href} className="hrd-value">{m.value??(query.isPending?"Loading…":query.isError?"Unavailable":m.section==="payroll"?"No completed run":"Unavailable")}</Link><p>{query.data?m.detail:query.isPending?"Loading this section…":"Awaiting verified data."}</p>{query.isError&&<p role="alert">{query.data?"Stale — refresh failed":"Could not verify this metric"}</p>}</article>;})}</div>
   {actions.some(a=>a.show)&&<nav className="hrd-actions" aria-label="HR quick actions">{actions.filter(a=>a.show).map(a=><Link key={a.label} to={a.href}>{a.label}<ArrowRight size={15}/></Link>)}</nav>}
   {ctx.sections.map(section=>{const query=get(section), data=query.data;return <section className="hrd-section" key={section} aria-labelledby={`hrd-${section}`}><div className="hrd-section-title"><h2 id={`hrd-${section}`}>{titles[section]}</h2><Link to={drill(section)}>View matching records</Link></div><SectionState query={query} zone={ctx.timezone}>
    {section==="workforce"&&data&&<><p>{change(number(data,"headcount"),number(data,"previous_headcount"))} · {number(data,"joined")} joined in the selected period</p><p className="hrd-note">Comparison dates: {data.context.to_date} versus {subtract(data.context.from_date,1)}.</p><div className="hrd-bars" aria-label="Active headcount by department">{data.series.map(r=><div key={String(r.department)}><span>{r.department}: {r.count} employees</span><progress max={Math.max(number(data,"active")||0,1)} value={Number(r.count)} aria-label={`${r.department}: ${r.count} of ${number(data,"active")} active employees`}/></div>)}</div><DataTable caption="Active headcount by department (employees)" columns={["department","count"]} rows={data.series}/></>}
    {section==="attendance"&&data&&<><div className="hrd-facts"><p><strong>{number(data,"rate")===null?"Not available":`${number(data,"rate")}%`}</strong> recorded attendance rate</p><p>{number(data,"present_equivalent")} present-equivalent days / {number(data,"denominator")} recorded working days</p><p>{number(data,"missing_punches")} incomplete punch pairs today · {number(data,"not_marked")} active employees without a recorded entry today</p>{ctx.personal&&<p><strong>My Week:</strong> {number(data,"week_days")} days with presence · {number(data,"week_hours")} recorded hours, Monday through today.</p>}</div><DataTable caption={`Today's recorded attendance (${ctx.business_date}) — employees`} columns={["status","count"]} rows={data.series}/></>}
    {section==="leave"&&data&&<><div className="hrd-facts"><p><strong>{number(data,"available_days")} days</strong> {ctx.personal?"my available leave":"available leave across permitted employees"}</p><p>{number(data,"starting_soon")} pending requests start within three days · Oldest pending request: {number(data,"oldest_days")} days</p></div><DataTable caption="Approved leave and handover coverage — today through the next seven days" columns={["date","on_leave","without_handover"]} rows={data.series}/></>}
    {section==="payroll"&&data&&<><p>Latest scoped run: {data.metrics.latest_run??"None"} · {data.metrics.status}</p><p>{data.metrics.latest_run?`${number(data,"issue_count")} bank export blockers` : "Readiness has not been validated; no run with employee records exists in this workforce scope."}</p><p>{data.metrics.status&&["locked","paid"].includes(String(data.metrics.status).toLowerCase())?"Payroll is locked; post-lock changes require authorization.":"Payroll lock is not confirmed."}</p><div className="hrd-bars" aria-label={`Monthly payroll in ${ctx.currency}`}>{data.series.map(row=><div key={String(row.month)}><span>{row.month}</span><div><label>Gross: {money(Number(row.gross))}<progress aria-label={`Gross payroll ${row.month} in ${ctx.currency}`} max={Math.max(...data.series.map(r=>Math.max(Number(r.gross),Number(r.net))),1)} value={Number(row.gross)}/></label><label>Net: {money(Number(row.net))}<progress aria-label={`Net payroll ${row.month} in ${ctx.currency}`} max={Math.max(...data.series.map(r=>Math.max(Number(r.gross),Number(r.net))),1)} value={Math.max(Number(row.net),0)}/></label></div></div>)}</div><DataTable caption={`Completed payroll by month (${ctx.currency}); ${from} to ${to}`} columns={["month","gross","net"]} rows={data.series} money={money}/></>}
    {["onboarding","probation","compliance"].includes(section)&&data&&<p><strong>{number(data,"overdue")}</strong> overdue · <strong>{number(data,"upcoming")}</strong> upcoming within 30 days</p>}
    {section==="exits"&&data&&<p><strong>{number(data,"open")}</strong> open exits · <strong>{number(data,"blocked")}</strong> with incomplete readiness</p>}
    {data?.notes.map(note=><p className="hrd-note" key={note}>{note}</p>)}
    {data&&!["attendance","workforce","leave"].includes(section)&&<Records rows={data.rows.slice(0,5)}/>}
   </SectionState></section>;})}
   {selection&&selected&&<section id="hrd-details" className="hrd-section" tabIndex={-1}><h2>{titles[selected]} — matching records</h2><SectionState query={selection} zone={ctx.timezone}><p>{selectedRows.length} displayed from {selection.data?.total_rows} source records. At most 250 matching records are returned; use workforce filters to narrow the scope.{params.get("record_status")&&` Status: ${params.get("record_status")}.`}{params.get("record_date")&&` Date: ${params.get("record_date")}.`}</p><Records rows={selectedRows}/></SectionState></section>}
   {ctx.personal&&user?.employee_id&&<PersonalHighlights employeeId={user.employee_id} identity={identity}/>}
   {can("recruitment_view")&&!ctx.personal&&<ModuleWorkflowBoard module="hrms"/>}
   </>}
  </>}
 </div>;
}

function DataTable({caption,columns,rows,money}:{caption:string;columns:string[];rows:Record<string,string|number>[];money?:(value:number)=>string}) {
 if(!rows.length)return <p className="hrd-note">No recorded data for {caption.toLowerCase()}.</p>;
 return <div className="hrd-table-wrap"><table><caption>{caption}</caption><thead><tr>{columns.map(c=><th scope="col" key={c}>{c.replace(/_/g," ")}</th>)}</tr></thead><tbody>{rows.map((row,i)=><tr key={i}>{columns.map(c=><td key={c}>{money&&["gross","net"].includes(c)?money(Number(row[c])):row[c]}</td>)}</tr>)}</tbody></table></div>;
}
function Records({rows}:{rows:Row[]}) {return rows.length?<ul className="hrd-records">{rows.map(r=><li key={r.id}><div><strong>{r.name}</strong><p>{r.detail}</p><p className="hrd-note">{r.date||"No deadline"} · {r.status}</p></div><Link to={r.href}>Open record<ArrowRight size={14}/></Link></li>)}</ul>:<p className="hrd-note">No matching records in this scope.</p>;}
