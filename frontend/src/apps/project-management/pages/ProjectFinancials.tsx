import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw, Search } from "lucide-react";
import { api } from "@/services/api";
import { defaultText, defaultsScope } from "@/lib/form-defaults";
import { formatCurrencyPrecise } from "@/lib/utils";
import GridTable from "@/shared/data-grid/GridTable";
import { NativeSelect } from "@/components/ui/native-select";
import { workspaceError } from "./workspaceTypes";
import "../components/WorkMovementPage.css";

type FinancialRow = {project_id:number;project_key:string;project_name:string;status:string;billing_status:string;budget_amount:number|string;actual_cost:number|string;estimated_hours:number|string;actual_hours:number|string;billable_hours:number|string;variance_amount:number|string};
const number = (value:unknown) => Number.isFinite(Number(value)) ? Number(value) : 0;
export default function ProjectFinancials() {
  const [search,setSearch] = useState("");
  const [project,setProject] = useState("");
  const currency = defaultText("currency", "project_management") || "INR";
  const money = (value:unknown) => formatCurrencyPrecise(number(value),currency);
  const query = useQuery({queryKey:["pms-project-financials",defaultsScope()],queryFn:async()=> (await api.get<{items:FinancialRow[]}>("/project-management/reports/budget-vs-actual",{recordCache:false})).data});
  const all = query.data?.items || [];
  const rows = all.filter(row=>(!project||String(row.project_id)===project)&&`${row.project_name} ${row.project_key} ${row.billing_status}`.toLowerCase().includes(search.toLowerCase()));
  const sum = (key:keyof FinancialRow) => rows.reduce((total,row)=>total+number(row[key]),0);
  return <section className="wm-workspace" aria-label="Project financials">
    <header className="wm-header"><div><span className="wm-eyebrow">DELIVERY PERFORMANCE</span><h1>Project financials</h1><p>Recorded budgets, costs and billable effort for the projects you can access.</p></div><Link className="wm-secondary" to="/pms/reports">Open reports</Link></header>
    <div className="wm-controls"><label className="wm-project"><span>Project</span><NativeSelect aria-label="Financial project" value={project} onChange={event=>setProject(event.target.value)}><option value="">All accessible projects</option>{all.map(row=><option key={row.project_id} value={row.project_id}>{row.project_name}</option>)}</NativeSelect></label><label className="wm-search"><Search size={15}/><input aria-label="Search project financials" value={search} onChange={event=>setSearch(event.target.value)} placeholder="Search projects, codes or billing status…"/></label><button className="wm-secondary" disabled={query.isFetching} onClick={()=>void query.refetch()}><RefreshCw size={14}/>Refresh</button>{(search||project)&&<button className="wm-secondary" onClick={()=>{setSearch("");setProject("");}}>Clear filters</button>}</div>
    {query.isError&&<p role="alert" className="wm-error">{workspaceError(query.error)} <button onClick={()=>void query.refetch()}>Retry</button></p>}
    {query.isPending?<p className="wm-empty" role="status">Loading project financials…</p>:<>
      <div className="wm-financial-metrics">{[["Recorded budget",money(sum("budget_amount"))],["Recorded cost",money(sum("actual_cost"))],["Budget remaining",money(sum("variance_amount"))],["Billable hours",`${sum("billable_hours").toLocaleString(undefined,{maximumFractionDigits:2})}h`]].map(([label,value])=><div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
      <p className="text-xs text-muted-foreground">Amounts shown in {currency}. Budget remaining is budget less recorded cost; it is not recognized profit or an invoice balance.</p>
      <div className="wm-table"><GridTable gridId="pms-project-financials" aria-label="Project budget and actual cost" pinActions><thead><tr><th>Project</th><th>Budget</th><th>Actual cost</th><th>Budget remaining</th><th>Planned hours</th><th>Logged hours</th><th>Billable hours</th><th>Billing status</th></tr></thead><tbody>{rows.map(row=><tr key={row.project_id}><td><Link to={`/pms/projects/${row.project_id}`}><strong>{row.project_name}</strong><small className="block">{row.project_key}</small></Link></td><td>{money(row.budget_amount)}</td><td>{money(row.actual_cost)}</td><td className={number(row.variance_amount)<0?"text-destructive":""}>{money(row.variance_amount)}</td><td>{number(row.estimated_hours).toLocaleString()}h</td><td>{number(row.actual_hours).toLocaleString(undefined,{maximumFractionDigits:2})}h</td><td>{number(row.billable_hours).toLocaleString(undefined,{maximumFractionDigits:2})}h</td><td>{row.billing_status||"Unbilled"}</td></tr>)}</tbody></GridTable></div>
      {!rows.length&&<div className="wm-empty"><h2>No project financials match</h2><p>{all.length?"Clear the filters or choose another project.":"Financials appear when you have access to a project."}</p><Link to="/pms/projects">Open projects</Link></div>}
      <footer className="wm-footer"><span>{rows.length} matching projects · Totals follow the filters above.</span><Link to="/pms/time-tracking">Review time entries →</Link></footer>
    </>}
  </section>;
}
