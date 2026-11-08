import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/services/api";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { NativeSelect } from "@/components/ui/native-select";
import ProjectQuickTask from "@/apps/project-management/pages/ProjectQuickTask";
import type { PMSTaskListResponse } from "@/apps/project-management/types";

/** Use the same task store and composer as the shared task workspace. */
export default function TaskQuickCreate({ close, saved, initialProjectId, workspaceId, initialWorkType="Task" }: { close: () => void; saved: () => void; initialProjectId?:number; workspaceId?:number; initialWorkType?:"Task"|"Story"|"Bug" }) {
  const navigate=useNavigate();
  const [options,setOptions]=useState<PMSTaskListResponse>();
  const [projectId,setProjectId]=useState("");
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  useEffect(()=>{let active=true;api.get<PMSTaskListResponse>("/project-management/tasks",{params:{page:1,pageSize:1,workspaceId},progress:false}).then(({data})=>{if(active){setOptions(data);setProjectId(String(data.filters.projects.find(project=>project.can_manage_tasks&&project.id===initialProjectId)?.id||data.filters.projects.find(project=>project.can_manage_tasks)?.id||""));}}).catch(()=>{if(active)setError("Could not load projects. Reopen the form to retry.");});return()=>{active=false;};},[initialProjectId,workspaceId]);
  const projects=options?.filters.projects.filter(project=>project.can_manage_tasks)||[];
  return <Dialog open onOpenChange={open=>{if(!open&&!busy)close();}}><DialogContent className="max-h-[90dvh] max-w-2xl overflow-y-auto"><DialogTitle>Create task</DialogTitle>{error&&<p role="alert">{error}</p>}{!options&&!error&&<p role="status">Loading task options…</p>}{options&&<><label>Project<NativeSelect aria-label="New task project" disabled={busy} value={projectId} onChange={event=>setProjectId(event.target.value)}>{projects.map(project=><option key={project.id} value={project.id}>{project.name}</option>)}</NativeSelect></label>{!projects.length&&<p>No projects are available for creating tasks.</p>}{projectId&&<ProjectQuickTask key={projectId} initialWorkType={initialWorkType} compact projectId={Number(projectId)} projectName={projects.find(project=>String(project.id)===projectId)?.name||"Project"} initialStatus="To Do" statuses={options.filters.statuses} onBusy={setBusy} onCreated={async()=>{saved();close();}} onFullForm={query=>{close();navigate(`/pms/tasks/new?${query}`);}}/>}</>}</DialogContent></Dialog>;
}
