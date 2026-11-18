import { Button } from "@/components/ui/button";
import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import CreateTaskModal from "../components/CreateTaskModal";
import PipelineDomainDetails from "@/shared/pipeline/PipelineDomainDetails";
import { PipelineDrawer } from "@/shared/pipeline/PipelineExperience";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Plus, Settings2 } from "lucide-react";
import { api } from "@/services/api";
import { NativeSelect } from "@/components/ui/native-select";
import PipelineBoard, { PipelineSearch, PipelineViewSwitch } from "@/shared/pipeline/PipelineBoard";
import PipelineStageEditor from "@/shared/pipeline/PipelineStageEditor";
import { useRefreshableEffect } from "@/lib/page-refresh";
import { kanbanAPI, projectsAPI } from "../services/api";
import { arrangeTask } from "../components/SprintMoveBoard";
import { usePMSRealtime } from "../realtime";
import type { PMSBoard, PMSProject } from "../types";

export default function KanbanBoard() {
  const {projectId}=useParams(); const id=Number(projectId); const navigate=useNavigate();
  const [board,setBoard]=useState<PMSBoard>();
  const [boardId,setBoardId]=useState<number>(),[boards,setBoards]=useState<Array<{id:number;name:string}>>([]);
  const [creating,setCreating]=useState(false),[newName,setNewName]=useState(""),[template,setTemplate]=useState("delivery");
  const [creatingBusy,setCreatingBusy]=useState(false);
  const [taskCreating,setTaskCreating]=useState(false),[taskStage,setTaskStage]=useState("To Do");
  useEffect(()=>{setBoardId(undefined);},[id]);
  const [project,setProject]=useState<PMSProject>();
  const [loading,setLoading]=useState(true),[error,setError]=useState("");
  const [query,setQuery]=useState(""),[priority,setPriority]=useState("");
  const [editing,setEditing]=useState(false),[revision,setRevision]=useState(0);
  const loadGeneration=useRef(0),inFlight=useRef<string>(),loadedKey=useRef("");
  const load=useCallback(async()=>{
    const key=`${id}:${boardId||"default"}`;
    if(inFlight.current===key)return;
    inFlight.current=key;
    const generation=++loadGeneration.current;
    if(loadedKey.current!==key)setLoading(true);
    if(!id){setLoading(false);setError("Choose a project to open its board.");return;}
    try {const [b,p]=await Promise.all([kanbanAPI.getBoard(id,boardId),projectsAPI.get(id)]);if(generation!==loadGeneration.current)return;loadedKey.current=key;setBoard(b);setProject(p);setError("");const choices=await api.get(`/project-management/projects/${id}/boards`);if(generation===loadGeneration.current)setBoards(choices.data.items||[{id:b.id,name:b.name}]);}
    catch(e){if(generation!==loadGeneration.current)return;setError((e as {response?:{data?:{detail?:string}}}).response?.data?.detail||"Could not load project board.");}
    finally {if(generation===loadGeneration.current){inFlight.current=undefined;setLoading(false);}}
  },[id,boardId]);
  useRefreshableEffect(()=>{void load();},[load]);
  usePMSRealtime({projectId:id||undefined,onEvent:e=>{if(e.type.startsWith("task.")||e.type==="project.updated")void load();},onFallbackPoll:()=>void load(),showToast:false});
  const allTasks=useMemo(()=>board?.columns?.flatMap(c=>c.tasks||[])||[],[board]);
  const tasks=allTasks.filter(t=>(!query||`${t.task_key} ${t.title}`.toLowerCase().includes(query.toLowerCase()))&&(!priority||t.priority===priority));
  const columns=[...(board?.columns||[])].sort((a,b)=>a.position-b.position);
  const readOnly=project?.can_manage_tasks===false;
  const newTask=(stageId?:string)=>{const c=columns.find(c=>String(c.id)===stageId);const status=c?({BACKLOG:"Backlog",TODO:"To Do",IN_PROGRESS:"In Progress",IN_REVIEW:"In Review",DONE:"Done"} as Record<string,string>)[c.status_key]||c.name:"To Do";setTaskStage(status);setTaskCreating(true);};
  return <div className="space-y-3 bg-background p-4 min-w-0">
    <header className="flex items-center justify-between gap-3"><div><p className="text-xs text-muted-foreground">Projects / {project?.project_key}</p><h1 className="sr-only">{project?.name||"Project"} · Board</h1></div><button type="button" className="text-sm text-primary" onClick={()=>navigate(`/pms/projects/${id}`)}>Project overview</button></header>
    {error&&<p role="alert" className="pipeline-error">{error} <Button variant="outline" type="button" onClick={()=>void load()}>Retry</Button></p>}
    {editing&&board&&<PipelineDrawer wide open={editing} onClose={()=>setEditing(false)} title="Customize project pipeline"><PipelineStageEditor key={`${board.id}:${revision}`} name={board.name} stages={columns.map(c=>({id:String(c.id),name:c.name,statusKey:c.status_key,count:c.task_count,wip_limit:c.wip_limit,aging_days:c.aging_days||14}))} onCancel={()=>setEditing(false)} onSave={async draft=>{await api.put(`/project-management/projects/${id}/board/configuration`,{...draft,board_id:board.id,expected_name:board.name,expected_stages:columns.map(c=>({id:c.id,name:c.name,status_key:c.status_key,position:c.position}))});await load();setRevision(v=>v+1);setEditing(false);}}/></PipelineDrawer>}
    <PipelineBoard title={`${project?.name||"Project"} · Board`} description={`${project?.project_key||"Project delivery"} · Plan, collaborate and move work forward with a shared view of every stage.`} label="Project task pipeline" viewState={{search:query,priority}} onApplyView={v=>{setQuery(String(v.search||""));setPriority(String(v.priority||""));}} context={{module:"project_management",scope:`project:${id}:board:${board?.id||"default"}`,kind:"task"}} renderDetails={r=><PipelineDomainDetails module="project_management" id={r.id} canEdit={!readOnly}/>} onAdd={!readOnly?newTask:undefined} disabled={readOnly||!project||loading||!!boardId&&boardId!==board?.id} loading={loading} notice={`${Math.max(0,(board?.total_project_tasks||allTasks.length)-allTasks.length)} tasks in other project statuses. Counts and effort reflect this board and its filters.`}
      toolbar={<><PipelineViewSwitch view="board" onChange={v=>{if(v==="list")navigate(`/pms/tasks?projectId=${id}`);}}/>{!readOnly&&<button type="button" className="pipeline-primary" onClick={()=>newTask()}><Plus size={14}/>Task</button>}<PipelineSearch value={query} onChange={setQuery} placeholder="Search tasks"/><div className="pipeline-toolbar-end"><NativeSelect aria-label="Task priority" value={priority} onChange={e=>setPriority(e.target.value)}><option value="">All priorities</option>{[...new Set(allTasks.map(t=>t.priority))].map(p=><option key={p}>{p}</option>)}</NativeSelect><select aria-label="Project pipeline" value={boardId||board?.id||""} onChange={e=>{setBoardId(Number(e.target.value));setEditing(false);}}>{(boards.length?boards:board?[{id:board.id,name:board.name}]:[]).map(b=><option key={b.id} value={b.id}>{b.name}</option>)}</select>{project?.can_edit_project&&<Button variant="default" type="button" onClick={()=>setCreating(true)}>New pipeline</Button>}{project?.can_edit_project!==false&&!readOnly&&<button type="button" className="pipeline-icon-button" aria-label="Customize project pipeline" disabled={loading||!!boardId&&boardId!==board?.id} onClick={()=>setEditing(v=>!v)}><Settings2 size={16}/></button>}</div></>}
      stages={columns.map(c=>({id:String(c.id),name:c.name,wipLimit:c.wip_limit,agingDays:c.aging_days||14,count:c.task_count,summary:`${tasks.filter(t=>t.column_id===c.id).length} tasks · ${tasks.filter(t=>t.column_id===c.id).reduce((sum,t)=>sum+(t.story_points||0),0)} pts${c.wip_limit?` · WIP ${c.wip_limit}`:""}`}))}
      records={tasks.sort((a,b)=>a.position-b.position).map(t=>({id:String(t.id),stageId:String(t.column_id),title:t.title,subtitle:t.task_key,priority:t.priority,description:t.description,tags:t.tags?.map(tag=>typeof tag==="string"?tag:tag.name),attachmentCount:t.attachment_count,progress:t.subtask_count?{completed:t.completed_subtask_count||0,total:t.subtask_count,label:"Subtasks"}:undefined,isClosed:t.status==="Done"||t.status==="Cancelled",ownerId:t.assignee_user_id,nextActionAt:t.due_date,owner:t.assignee_name||(t.assignee_user_id?`U${t.assignee_user_id}`:undefined),value:t.story_points?`${t.story_points} points`:undefined,labelColor:t.priority==="High"||t.priority==="Urgent"?"#bc4248":undefined,activity:t.due_date&&new Date(`${t.due_date.slice(0,10)}T23:59:59`)<new Date()&&t.status!=="Done"?"overdue":undefined,activityLabel:"Task overdue"}))}
      onOpen={r=>navigate(`/pms/projects/${id}/tasks/${r.id}`)}
      onMove={async({record,stageId,beforeId})=>{const column=columns.find(c=>String(c.id)===stageId);if(!column)throw new Error("Destination column no longer exists. Refresh the board.");const status=({BACKLOG:"Backlog",TODO:"To Do",IN_PROGRESS:"In Progress",IN_REVIEW:"In Review",DONE:"Done"} as Record<string,string>)[column.status_key]||column.name;await arrangeTask(Number(record.id),{group_by:"status",status,before_id:beforeId?Number(beforeId):undefined});await load();}}
      actions={readOnly?[]:columns.filter(c=>c.status_key==="DONE").map(c=>({id:String(c.id),label:"Complete",tone:"success",onAction:async record=>{await arrangeTask(Number(record.id),{group_by:"status",status:"Done"});await load();}}))}
    />
    <CreateTaskModal isOpen={taskCreating} onClose={()=>setTaskCreating(false)} projectId={id} initialStatus={taskStage} onTaskCreated={()=>{void load();}} />
    <PipelineDrawer open={creating} onClose={()=>setCreating(false)} title="Create a project pipeline"><SmartCreateSection title="Create pipeline" size="compact"><form className="pipeline-settings-panel" onSubmit={async e=>{e.preventDefault();setCreatingBusy(true);try{const response=await api.post(`/project-management/projects/${id}/boards`,{name:newName,template});setBoards(b=>[...b,response.data]);setBoardId(response.data.id);setCreating(false);setNewName("");}catch(e){setError((e as {response?:{data?:{detail?:string}}}).response?.data?.detail||"Could not create pipeline");}finally{setCreatingBusy(false);}}}><p>Named boards show this project's existing tasks through their workflow statuses.</p><label>Pipeline name<input required maxLength={140} value={newName} onChange={e=>setNewName(e.target.value)}/></label><label>Template<select value={template} onChange={e=>setTemplate(e.target.value)}><option value="delivery">Delivery</option><option value="support">Support</option><option value="simple">Simple workflow</option></select></label><Button variant="default" type="submit" disabled={creatingBusy} className="pipeline-primary">Create pipeline</Button></form></SmartCreateSection></PipelineDrawer>
  </div>;
}
