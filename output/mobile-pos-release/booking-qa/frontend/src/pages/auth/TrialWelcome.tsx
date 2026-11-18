import CompanySampleData from "@/shared/data-transfer/CompanySampleData";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/services/api";
import { type Data, message } from "@/platform/shared";

export default function TrialWelcome({data,refresh}:{data:Data;refresh:()=>void}){
 const [busy,setBusy]=useState(false),[error,setError]=useState("");const [completed,setCompleted]=useState<Data>(data.completed);
 useEffect(()=>setCompleted(data.completed),[data.completed]);
 async function update(step:string,complete=true){setBusy(true);setCompleted(old=>({...old,[step]:complete?new Date().toISOString():null}));try{const {data:next}=await api.post("/access/onboarding",{step,complete});setCompleted(next.completed);refresh()}catch(err){setCompleted(data.completed);setError(message(err))}finally{setBusy(false)}}
 return <main className="signup-policy"><h1>Welcome to your workspace</h1><p>Your approved applications are ready. Choose a useful first step, or skip this checklist for now.</p>{error&&<p role="alert">{error}</p>}<ul>{[["profile","Review your company profile","/settings/company/profile"],["team","Invite your team","/settings/users"],["first_action","Complete your first useful task",data.modules[0]?.url||"/dashboard"]].map(([step,label,url])=><li key={step}><label><input type="checkbox" checked={!!completed[step]} disabled={busy} onChange={e=>void update(step,e.target.checked)}/>{label}</label> · <Link to={url}>{step==="first_action"?"Open an approved application":"Open"}</Link></li>)}</ul>{data.sample_data_requested&&<p>You requested sample data. Importing it remains optional and can be undone. Review the optional import below.</p>}{data.sample_data_requested&&<CompanySampleData/>}<p>Your applications: {data.modules.map((m:Data)=><Link key={m.key} to={m.url} style={{marginRight:16}}>{m.key.split("_").join(" ")}</Link>)}</p><button className="signup-primary" disabled={busy} onClick={()=>void update("dismissed")}>Continue to my workspace</button><p><small>Checklist completion is self-reported. No records or team invitations are created by checking a box.</small></p></main>;
}
