import { Link } from "react-router-dom";
import { CheckCircle2, Circle, ArrowRight, RefreshCw } from "lucide-react";
import type { Item } from "./SetupReadiness";
import "./setup-guide.css";

type Props = {data?: {items:Item[]; moduleItems?:Item[]; recommendations?:Item[]}; module?:string; loading:boolean; error:boolean; refreshing:boolean; refresh:()=>void};
const labels:Record<string,string> = {company:"Company essentials", crm:"CRM · Sales process", srm:"SRM · Sales & inventory", project_management:"PMS · Project delivery", hrms:"HRMS · People & payroll", fam:"Finance · Accounting"};
export default function SetupGuide({data,module,loading,error,refreshing,refresh}:Props) {
  const items = [...(data?.items || []), ...(data?.moduleItems || []), ...(data?.recommendations || [])].filter(i=>!module || i.module === "company" || i.module === module);
  const required = items.filter(i=>i.required !== false);
  const missing = required.filter(i=>!i.ready);
  const completed = items.filter(i=>i.ready).length;
  const groups = [...new Set(items.map(i=>i.module || "company"))];
  return <section className="setup-guide" aria-label="Workspace setup guide">
    <header className="setup-guide-header"><div><p className="setup-guide-eyebrow">YOUR SETUP GUIDE</p><h2>{module ? `${labels[module].split(" · ")[0]} setup` : "Let's get your workspace ready"}</h2><p>Complete mandatory essentials first, then explore optional improvements.</p></div><button disabled={refreshing} onClick={refresh}><RefreshCw size={15}/>{refreshing ? "Checking…" : "Check again"}</button></header>
    {loading ? <p role="status">Checking current configuration…</p> : error ? <p role="alert">Setup status is unavailable. Check again to retry.</p> : <>
      <div className="setup-guide-progress"><progress aria-label="Setup tasks completed" value={completed} max={items.length || 1}/><span>{completed} of {items.length} complete</span></div>
      <p className="setup-guide-summary" role="status">{missing.length ? `${missing.length} mandatory ${missing.length === 1 ? "item needs" : "items need"} attention` : "Mandatory setup complete"} · Optional tasks never block your work.</p>
      {groups.map(group=>{const rows=items.filter(i=>(i.module || "company")===group);const remaining=rows.filter(i=>!i.ready);return <details className="setup-guide-group" key={`${module}-${group}`} open={remaining.length > 0}>
        <summary><strong>{labels[group] || group}</strong><span>{rows.filter(i=>i.ready).length} of {rows.length} complete</span></summary>
        <ul>{[...rows].sort((a,b)=>Number(a.ready)-Number(b.ready) || Number(a.required===false)-Number(b.required===false)).map(item=><li key={item.id}>
          {item.ready ? <CheckCircle2 size={19} className="setup-guide-done"/> : <Circle size={19}/>}
          <div><div className="setup-guide-task"><strong>{item.title}</strong><span className={item.required===false ? "" : "setup-guide-required"}>{item.required===false ? "Optional" : "Mandatory"}</span>{item.ready && <span>Complete</span>}</div><p>{item.description}</p>
          {!item.ready && (item.canRepair ? <Link to={item.destination}>Set up now <ArrowRight size={14}/></Link> : <small>Ask your company administrator to complete this item.</small>)}</div>
        </li>)}</ul>
      </details>})}
    </>}
  </section>;
}
