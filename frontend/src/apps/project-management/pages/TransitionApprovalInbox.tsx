import { useEffect, useRef, useState } from "react";
import { useMobile } from "@/components/mobile/useMobile";
import { useMobileContext } from "@/components/mobile/useMobileContext";
import { syncScope } from "@/shared/record-sync/store";
import { Link } from "react-router-dom";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { workspaceError } from "./workspaceTypes";
import "./transition-approvals-mobile.css";

type Review={id:number;task_id:number;title:string;target:string;current:boolean};
export default function TransitionApprovalInbox(){
 const scope=useMobileContext();
 return <InboxContents key={scope}/>;
}
function InboxContents(){
 const phone=useMobile(480),pending=useRef(false);
 const mounted=useRef(true);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 const [loading,setLoading]=useState(true);
 const [rows,setRows]=useState<Review[]>();const [error,setError]=useState("");
 async function load(){if(phone&&pending.current)return; const owned=phone,scope=syncScope(); const current=()=>!owned||mounted.current&&scope===syncScope(); if(owned){pending.current=true;setLoading(true);}try{const {data}=await api.get<Review[]>("/project-management/transition-approvals/inbox");if(current()){setRows(data);setError("");}}catch(e){if(current())throw e;}finally{if(current()){pending.current=false;setLoading(false);}}}
 useEffect(()=>{void load().catch(e=>setError(workspaceError(e)));},[]);
 return <main className="transition-inbox mx-auto max-w-4xl space-y-4 p-4"><header className="flex flex-wrap justify-between gap-2"><h1 className="page-title">Transition approval inbox</h1><Button variant="outline" disabled={phone&&loading} onClick={()=>void load().catch(e=>setError(workspaceError(e)))}>Refresh inbox</Button></header>
  <p className="text-sm text-muted-foreground">Reviews assigned to you by project workflows. Open a task to review its saved details and approve or reject the transition.</p>
  {error&&<p role="alert" className="text-destructive">{error}</p>}
  {phone&&loading&&<p role="status">{rows ? "Refreshing reviews…" : "Loading reviews…"}</p>}
  {phone&&error&&rows&&<p role="status">Showing last loaded reviews. Refresh inbox to try again.</p>}
  {rows?.length===0&&<p>No pending transition reviews.</p>}
  {rows?.map(r=><div key={r.id} className="border-b py-3"><Link className="font-medium underline" to={`/pms/tasks/${r.task_id}?tab=review`}>{r.title}</Link><p className="text-sm">Requested status: {r.target}{!r.current?" · Out of date; the requester must submit a fresh request":""}</p></div>)}
 </main>;
}
