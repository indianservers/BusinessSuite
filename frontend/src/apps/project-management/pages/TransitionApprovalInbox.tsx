import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { workspaceError } from "./workspaceTypes";

type Review={id:number;task_id:number;title:string;target:string;current:boolean};
export default function TransitionApprovalInbox(){
 const [rows,setRows]=useState<Review[]>();const [error,setError]=useState("");
 async function load(){const {data}=await api.get<Review[]>("/project-management/transition-approvals/inbox");setRows(data);setError("");}
 useEffect(()=>{void load().catch(e=>setError(workspaceError(e)));},[]);
 return <main className="mx-auto max-w-4xl space-y-4 p-4"><header className="flex flex-wrap justify-between gap-2"><h1 className="page-title">Transition approval inbox</h1><Button variant="outline" onClick={()=>void load().catch(e=>setError(workspaceError(e)))}>Refresh inbox</Button></header>
  <p className="text-sm text-muted-foreground">Reviews assigned to you by project workflows. Open a task to review its saved details and approve or reject the transition.</p>
  {error&&<p role="alert" className="text-destructive">{error}</p>}
  {rows?.length===0&&<p>No pending transition reviews.</p>}
  {rows?.map(r=><div key={r.id} className="border-b py-3"><Link className="font-medium underline" to={`/pms/tasks/${r.task_id}`}>{r.title}</Link><p className="text-sm">Requested status: {r.target}{!r.current?" · Out of date; the requester must submit a fresh request":""}</p></div>)}
 </main>;
}
