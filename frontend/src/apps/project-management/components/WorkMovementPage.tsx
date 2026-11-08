import { withRecordViewHost } from "@/shared/data-grid/RecordViewHost";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { Plus, RefreshCw, Search } from "lucide-react";
import { useRecordView } from "@/lib/smart-cache/use-record-view";
import { NativeSelect } from "@/components/ui/native-select";
import PipelineBoard from "@/shared/pipeline/PipelineBoard";
import WorkspaceViewBar, { type WorkspaceView } from "@/shared/workspace/WorkspaceViewBar";
import RecordLensViews from "@/shared/workspace/RecordLensViews";
import GridTable from "@/shared/data-grid/GridTable";
import { projectsAPI, tasksAPI } from "../services/api";
import { usePMSRealtime } from "../realtime";
import { arrangeTask } from "./SprintMoveBoard";
import { workspaceError } from "../pages/workspaceTypes";
import type { PMSProject, PMSTaskListItem } from "../types";
import "./WorkMovementPage.css";

const statuses = ["Backlog", "To Do", "In Progress", "In Review", "Blocked", "Done", "Cancelled"];
const colours: Record<string,string> = {Backlog:"#94a3b8", "To Do":"#658be3", "In Progress":"#8b5cf6", "In Review":"#d6a344", Blocked:"#dc6b83", Done:"#22a48c", Cancelled:"#94a3b8"};
const closed = (status:string) => ["Done","Completed","Closed","Cancelled"].includes(status);
const modes = ["board","list","gallery","gantt","timeline","calendar","workload","team","activity","mindmap","whiteboard"];

/** Launch, delivery and work pipelines share the authorized task source and mutations. */
function WorkMovementPage({title}:{title:string}) {
  const navigate = useNavigate();
  const {pathname} = useLocation();
  const [params,setParams] = useSearchParams();
  const [projects,setProjects] = useState<PMSProject[]>([]);
  const [projectsLoading,setProjectsLoading] = useState(true);
  const [projectsError,setProjectsError] = useState("");
  const [moreProjects,setMoreProjects] = useState(false);
  const [tasks,setTasks] = useState<PMSTaskListItem[]>([]);
  const [total,setTotal] = useState(0);
  const [loading,setLoading] = useState(false);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const [notice,setNotice] = useState("");
  const project = Number(params.get("projectId")) || projects[0]?.id || 0;
  const selectedProject = projects.find(row=>row.id===project);
  const projectRef = useRef(project); projectRef.current = project;
  const requestRef = useRef(0);
  const view = modes.includes(params.get("view") || "") ? params.get("view")! : "board";
  const search = params.get("search") || "";
  const visible = tasks.filter(task=>`${task.task_key} ${task.title} ${task.assignee_name || ""}`.toLowerCase().includes(search.toLowerCase()));
  const canManage = !!selectedProject?.can_manage_tasks;
  const scope = `work:${pathname.split("/").pop()}:${project}`;
  function change(key:string,value:string) {setParams(previous=>{const next=new URLSearchParams(previous);if(value)next.set(key,value);else next.delete(key);return next;});}
  async function loadProjects(offset=0) {
    setProjectsLoading(true);setProjectsError("");
    try {const rows=await projectsAPI.list(offset,100,undefined,true);if(!Array.isArray(rows))throw new Error("Projects could not be loaded. Refresh and try again.");setProjects(current=>offset?[...current,...rows.filter(row=>!current.some(existing=>existing.id===row.id))]:rows);setMoreProjects(rows.length===100);}
    catch(e){setProjectsError(workspaceError(e));}
    finally{setProjectsLoading(false);}
  }
  useEffect(()=>{void loadProjects();},[]);
  useEffect(()=>()=>{requestRef.current++;},[]);
  async function load(id=project,clearError=true) {
    if(!id || !selectedProject)return;
    const request=++requestRef.current;
    setLoading(true);if(clearError)setError("");
    try {const result=await tasksAPI.listAll({projectId:id,pageSize:200,sortBy:"position",sortOrder:"asc"},true);if(!Array.isArray(result.items))throw new Error("Tasks could not be loaded. Refresh and try again.");if(id===projectRef.current && request===requestRef.current){setTasks(result.items);setTotal(result.total);}}
    catch(e){if(id===projectRef.current && request===requestRef.current)setError(workspaceError(e));}
    finally{if(id===projectRef.current && request===requestRef.current)setLoading(false);}
  }
  useEffect(()=>{setTasks([]);setTotal(0);setNotice("");setError("");if(selectedProject)void load();else setLoading(false);},[project,!!selectedProject]);
  useEffect(() => {
    const refresh = (event: Event) => { if ((event as CustomEvent<{ entity: string }>).detail.entity === "task") void load(); };
    window.addEventListener("suite:creation-completed", refresh);
    return () => window.removeEventListener("suite:creation-completed", refresh);
  }, [project, selectedProject]);
  usePMSRealtime({projectId:project || undefined,onEvent:()=>void load(),showToast:false});
  useRecordView<{items:PMSTaskListItem[];total:number}>("/project-management/tasks",{projectId:project,pageSize:200,sortBy:"position",sortOrder:"asc"},snapshot=>{if(Array.isArray(snapshot?.items)){setTasks(snapshot.items);setTotal(snapshot.total);}},()=>setTasks([]),!!selectedProject);
  async function move(id:string,status:string,beforeId?:string) {
    if(!canManage || busy || loading)return;
    if(status==="Blocked"){navigate(`/pms/tasks/${id}`);return;}
    setBusy(true);setError("");setNotice("");
    try {await arrangeTask(Number(id),{group_by:"status",status,before_id:beforeId});setNotice(`Task moved to ${status}.`);}
    catch(e){setError(workspaceError(e));throw e;}
    finally{await load(project,false);setBusy(false);}
  }
  const views:WorkspaceView[] = [
    {id:"board",label:"Board",description:"Move actual tasks through delivery stages",color:"#658be3"},
    {id:"list",label:"Table",icon:"table",description:"Compare tasks, owners and deadlines",color:"#22a48c"},
    {id:"gallery",label:"Gallery",description:"A focused card for each work item",color:"#cc79a2"},
    {id:"gantt",label:"Gantt",description:"Delivery windows and task schedules",category:"Plan",color:"#e98279"},
    {id:"timeline",label:"Timeline",description:"See work across time",category:"Plan",color:"#d6a344"},
    {id:"calendar",label:"Calendar",description:"Monthly deadlines and a readable agenda",category:"Plan",color:"#e3a060"},
    {id:"workload",label:"Workload",description:"Task distribution across the team",category:"Plan",color:"#22a48c"},
    {id:"team",label:"Team",description:"Work organised by its owner",category:"Explore",color:"#22a48c"},
    {id:"mindmap",label:"Mind map",description:"Explore work by stage or owner",category:"Explore",color:"#cc79a2"},
    {id:"whiteboard",label:"Whiteboard",description:"Arrange real work cards in a personal layout",category:"Explore",color:"#d6a344"},
    {id:"activity",label:"Activity",description:"Recently updated task records",category:"Collaborate",color:"#658be3"},
    {id:"dashboard",label:"Dashboard",description:"Progress, delivery health and team insights",category:"Explore",href:"/pms/dashboards"},
    {id:"reports",label:"Reports",icon:"dashboard",description:"Task, team and project performance",category:"Explore",href:"/pms/reports"},
    {id:"backlog",label:"Backlog & sprints",icon:"list",description:"Prioritise and plan the delivery backlog",category:"Plan",href:"/pms/backlog"},
    {id:"roadmap",label:"Roadmap",icon:"timeline",description:"Releases, initiatives and delivery planning",category:"Plan",href:"/pms/roadmap"},
    {id:"channel",label:"Channel",description:"Discuss this project with its team",category:"Collaborate",href:project?`/pms/projects/${project}/communication`:"/pms/team-communication"},
    {id:"docs",label:"Docs",description:"Project briefs and shared knowledge",category:"Collaborate",href:"/pms/docs"},
    {id:"files",label:"Files",description:"Assets and deliverables",category:"Collaborate",href:project?`/pms/projects/${project}/files`:"/pms/files"},
  ];
  const open = (id:string) => navigate(`/pms/tasks/${id}`);
  return <section className="wm-workspace" aria-label={title}>
    <header className="wm-header"><div><span className="wm-eyebrow">DELIVERY WORKSPACE</span><h1>{title}</h1><p>Select a project to plan its work, track delivery and collaborate with the team.</p></div>{canManage && <Link className="wm-primary" to={`/pms/tasks/new?projectId=${project}`}><Plus size={15}/>Add task</Link>}</header>
    <div className="wm-controls"><label className="wm-project"><span>Project</span><NativeSelect aria-label="Work project" disabled={projectsLoading||busy} value={project || ""} onChange={event=>change("projectId",event.target.value)}>{!projects.length && <option value="">{projectsLoading?"Loading projects…":"No accessible projects"}</option>}{project>0&&!selectedProject&&<option value={project}>Project not in loaded results</option>}{projects.map(row=><option key={row.id} value={row.id}>{row.name}</option>)}</NativeSelect></label><label className="wm-search"><Search size={15}/><input aria-label="Search work cards" placeholder="Search tasks, codes or owners…" value={search} onChange={event=>change("search",event.target.value)}/></label><button className="wm-secondary" disabled={loading || !selectedProject} onClick={()=>void load()}><RefreshCw size={14} className={loading?"animate-spin":""}/>Refresh</button>{moreProjects&&<button className="wm-secondary" disabled={projectsLoading} onClick={()=>void loadProjects(projects.length)}>Load more projects</button>}</div>
    {projectsError&&<p role="alert" className="wm-error">{projectsError} <button onClick={()=>void loadProjects()}>Retry projects</button></p>}
    {error&&<p role="alert" className="wm-error">{error} <button onClick={()=>void load()}>Retry tasks</button></p>}
    {notice&&<p role="status" className="wm-notice">{notice}</p>}
    <WorkspaceViewBar label="Delivery views" scope={scope} active={view} views={views} onChange={value=>change("view",value)} primary={["board","list","gallery","gantt","timeline","calendar"]}/>
    {loading&&!tasks.length ? <div className="wm-empty" role="status">Loading project work…</div> : !selectedProject ? <div className="wm-empty"><h2>{project?"Choose an accessible project":"Ready for your next project"}</h2><p>{project?"Load more projects or choose a project from the selector above.":"Create a project or join one to start planning real work."}</p><Link to="/pms/projects">Open projects</Link></div> : view==="board" ? <PipelineBoard key={scope} label={`${title} stages`} title={selectedProject.name} description="Every card is a project task. Open it to see its details and next steps." context={{module:"project_management",scope:`project:${project}`,kind:"task"}} disabled={!canManage||busy||loading} loading={loading&&!tasks.length} onOpen={record=>open(record.id)} onMove={({record,stageId,beforeId})=>move(record.id,stageId,beforeId)} stages={[...new Set([...statuses,...tasks.map(task=>task.status)])].map(status=>({id:status,name:status,color:colours[status],canAdd:canManage&&status!=="Blocked",count:visible.filter(task=>task.status===status).length}))} records={visible.map(task=>({id:String(task.id),title:task.title,stageId:task.status,subtitle:task.task_key,owner:task.assignee_name,ownerId:task.assignee_user_id||undefined,priority:task.priority,nextActionAt:task.due_date||undefined,isClosed:closed(task.status),labelColor:colours[task.status],activity:task.due_date&&!closed(task.status)?new Date(`${task.due_date}T23:59:59`)<new Date()?"overdue":"scheduled":undefined,activityLabel:task.due_date?`Due ${task.due_date}`:"No deadline"}))} onAdd={canManage?status=>navigate(`/pms/tasks/new?projectId=${project}&status=${encodeURIComponent(status)}`):undefined} notice={`${visible.length} of ${total} project tasks · Search applies to the loaded result.`}/> : view==="list" ? <div className="wm-table"><GridTable gridId={`delivery:${scope}`} aria-label={`${title} tasks`} pinActions><thead><tr><th>Task</th><th>Owner</th><th>Due date</th><th>Priority</th><th>Status</th></tr></thead><tbody>{visible.map(task=><tr data-priority-row data-priority={task.priority} key={task.id}><td><button onClick={()=>open(String(task.id))}><strong>{task.title}</strong><small>{task.task_key}</small></button></td><td>{task.assignee_name||"Unassigned"}</td><td>{task.due_date||"Unscheduled"}</td><td>{task.priority}</td><td><NativeSelect aria-label={`Status for ${task.title}`} disabled={!canManage||busy||loading} value={task.status} onChange={event=>{void move(String(task.id),event.target.value).catch(()=>{});}}>{[...new Set([...statuses,task.status])].map(status=><option key={status}>{status}</option>)}</NativeSelect></td></tr>)}</tbody></GridTable>{!visible.length&&<p className="wm-empty">No tasks match your search.</p>}</div> : <RecordLensViews key={`${scope}:${view}`} scope={scope} view={view} records={visible.map(task=>({id:String(task.id),title:task.title,subtitle:task.task_key,status:task.status,owner:task.assignee_name,start:task.start_date,due:task.due_date,updated:task.updated_at,color:colours[task.status],tags:[task.priority]}))} onOpen={record=>open(record.id)}/>}
    {selectedProject&&<footer className="wm-footer"><span>{total>tasks.length?`Showing the first ${tasks.length} of ${total} tasks.`:`${total} tasks in this project.`}</span><Link to={`/pms/tasks?projectId=${project}`}>Open full task workspace →</Link></footer>}
  </section>;
}

export default withRecordViewHost(WorkMovementPage);
