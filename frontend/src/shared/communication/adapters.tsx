import { useCommunicationScope } from "./scope";
import { useAuthStore } from "@/store/authStore";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import { MessageSquare } from "lucide-react";
import { api } from "@/services/api";
import { workspaceError } from "@/apps/project-management/pages/workspaceTypes";
import type { CommunicationWorkspaceProps, CommunicationModule, CommunicationContext } from "./types";

export const moduleAdapters: Record<CommunicationModule,string> = { PMS:"project_management", CRM:"crm", HRMS:"hrms", InternHub:"project_management", Sales:"srm", Finance:"fam", Support:"hrms", Administration:"project_management" };
export const moduleMessageRoutes: Record<CommunicationModule,string> = { PMS:"/pms/messages", CRM:"/crm/messages", HRMS:"/hrms/messages", InternHub:"/pms/messages", Sales:"/srm/messages", Finance:"/fam/messages", Support:"/hrms/messages", Administration:"/pms/messages" };

/** Resolves an approved record before opening its one canonical conversation. */
export function ContextualChat({ module="PMS", workspaceId, context }: CommunicationWorkspaceProps) {
  const navigate=useNavigate();
  const actor=useCommunicationScope();
  const [wid,setWid]=useState(workspaceId || 0),[busy,setBusy]=useState(false),[error,setError]=useState("");
  const workspaces=useQuery({queryKey:["messaging-workspaces",actor],queryFn:async()=>(await api.get<{id:number;name:string}[]>("/collaboration/workspaces")).data});
  const selected=wid || workspaces.data?.[0]?.id || 0;
  if(!context) return <p>Choose a record to open its discussion.</p>;
  return <div className="space-y-3"><p className="text-sm text-muted-foreground">Internal discussion for {context.type} #{context.id}. Record access is checked whenever the conversation is opened.</p><label className="block text-sm">Workspace<select className="ml-2 rounded border bg-background p-2" value={selected} onChange={e=>setWid(Number(e.target.value))}>{workspaces.data?.map(w=><option key={w.id} value={w.id}>{w.name}</option>)}</select></label>{workspaces.isError&&<p role="alert">{workspaceError(workspaces.error)}</p>}{!workspaces.isPending&&!selected&&<p>Join an authorized workspace to start a discussion.</p>}<button className="rounded border bg-primary px-4 py-2 text-sm text-primary-foreground" disabled={!selected||busy} onClick={()=>{setBusy(true);setError("");void api.post<{conversation_id:number}>("/collaboration/context-conversations",{workspace_id:selected,module:moduleAdapters[module],entity_type:context.type,entity_id:context.id}).then(({data})=>navigate(`${moduleMessageRoutes[module]}?workspace=${selected}&conversation=${data.conversation_id}`)).catch(e=>setError(workspaceError(e))).finally(()=>setBusy(false));}}>{busy?"Opening…":"Open record discussion"}</button>{error&&<p role="alert">{error}</p>}</div>;
}

export function ConversationLauncher(props: CommunicationWorkspaceProps & { label?:string }) {
  const [open,setOpen]=useState(false);
  return <Dialog.Root open={open} onOpenChange={setOpen}><Dialog.Trigger asChild><button className="inline-flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm"><MessageSquare size={15}/>{props.label||"Discuss with team"}</button></Dialog.Trigger><Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-[205] bg-black/40"/><Dialog.Content className="fixed left-1/2 top-1/2 z-[206] w-[min(94vw,500px)] -translate-x-1/2 -translate-y-1/2 space-y-4 rounded-xl border bg-background p-6 shadow-xl"><Dialog.Title className="font-semibold">Record conversation</Dialog.Title><Dialog.Description className="text-sm text-muted-foreground">Open the shared conversation using your current account.</Dialog.Description><ContextualChat {...props}/><Dialog.Close className="rounded border px-3 py-2 text-sm">Close</Dialog.Close></Dialog.Content></Dialog.Portal></Dialog.Root>;
}

export function TaskConversationSource({taskId}:{taskId:number}) {
  const actor=useCommunicationScope();
  const result=useQuery({queryKey:["communication-task-source",actor,taskId],enabled:!!taskId,queryFn:async()=>(await api.get<{source:{source_url:string}|null}>(`/collaboration/tasks/${taskId}/source`)).data});
  const navigate=useNavigate();
  return result.data?.source ? <button className="text-sm text-primary underline" onClick={()=>navigate(result.data!.source!.source_url)}>View source conversation ↗</button> : null;
}
