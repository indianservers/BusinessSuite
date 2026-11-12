import { Button } from "@/components/ui/button";
import { matchesWorkFocus, localWorkDate, workFocusOptions, type WorkFocus } from "./workspaceFocus";
import "./WorkspaceFocus.css";
import { CustomFieldsForm, type FieldDraft } from "../components/CustomFields";
import LocalRecordGrid from "@/shared/data-grid/LocalRecordGrid";
import { personalRows, type GridPersonalFilter } from "@/shared/data-grid/personal-filter";
import { filterRules, sanitizeQuery } from "@/shared/data-grid/state";
import { localGridSource } from "@/shared/data-grid/local-source";
import { emptyQuery, type GridColumn, type GridQuery } from "@/shared/data-grid/types";
import { NativeSelect } from "@/components/ui/native-select";
import CompactForm from "@/components/forms/CompactForm";
import {useAuthStore} from "@/store/authStore";
import { ManagePersonButton } from "../components/people/PersonIdentity";
import { useRefreshableEffect } from "@/lib/page-refresh";
import { CustomFieldCell, useCustomFieldRecords } from "../components/CustomFields";
import { RichTextField, RichTextContent, richTextPlainText } from "@/components/rich-text/LazyRichText";
import { StatusSelect } from "@/design-system/components";
import RecordActions from "../components/RecordActions";
import { beginProgress } from "@/components/app/AsyncProgress";
import { useEffect, useMemo, useState, type ReactNode, type RefObject } from "react";
import { Link } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import { DndContext, DragOverlay, PointerSensor, KeyboardSensor, useSensor, useSensors, useDroppable, pointerWithin, rectIntersection, type DragEndEvent, type CollisionDetection } from "@dnd-kit/core";
import { SortableContext, useSortable, sortableKeyboardCoordinates, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { AlertCircle, Ban, CalendarClock, Clock3, ArrowUpRight, CalendarDays, CheckCircle2, Circle, Flag, Folder, GripVertical, MessageSquare, Plus, Search, Send, ShieldCheck, Users, X } from "lucide-react";
import { tasksAPI, commentsAPI } from "../services/api";
import TaskCustomFields from "../components/TaskCustomFields";
import TaskPropertyStrip from "../components/TaskPropertyStrip";
import TaskStatusControl from "../components/TaskStatusControl";
import TaskEditReview from "../components/TaskEditReview";
import {useRecordScope} from "@/shared/records/Record360Workspace";
import {useMobileDraftGuard} from "@/components/mobile/useMobileDraftGuard";
import UnsavedTaskDialog from "../components/UnsavedTaskDialog";
import AssigneePicker from "../components/AssigneePicker";
import type { PMSComment, TaskPriority } from "../types";
import { type WorkspaceMember as Member, type WorkspaceProject as Project, type WorkTask as Task, personName, tones, taskBucket as bucket, taskAssignees, workspaceError } from "./workspaceTypes";

const lanes = [{ status: "To Do", label: "To do", color: "#8894a7" }, { status: "In Progress", label: "In progress", color: "#7864e9" }, { status: "In Review", label: "In review", color: "#e4a54c" }, { status: "Done", label: "Done", color: "#319c88" }];
const dateLabel = (value?: string) => value ? new Date(value + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "No due date";
const collision: CollisionDetection = args => {
  const hits = pointerWithin(args);
  // A teammate drop zone takes priority over an individual card inside it.
  const people = hits.filter(h => String(h.id).startsWith("person:"));
  return people.length ? people : hits.length ? hits.filter(h => String(h.id).startsWith("task-")).length ? hits.filter(h => String(h.id).startsWith("task-")) : hits : rectIntersection(args);
};
type Props = {
  tasks: Task[]; members: Member[]; projects: Project[]; view: "board" | "list" | "people" | "calendar" | "workload" | "activity";
  renderPlanning?: (tasks: Task[]) => ReactNode;
  onViewChange?: (view: Props["view"]) => void;
  searchInputRef?: RefObject<HTMLInputElement>; query: string;
  projectFilter: string; setProjectFilter: (v: string) => void; assigneeFilter: string; setAssigneeFilter: (v: string) => void;
  canEdit: boolean; updateTask: (task: Task, changes: Partial<Task>) => Promise<boolean>; onOpen: (id: number) => void;
  onRefresh: () => Promise<void>; onInvite?: () => void; onError: (s: string) => void; onNotice: (s: string) => void;
  onClearSearch?: () => void;
  onQueryChange?:(value:string)=>void;onCreateTask?:()=>void;workspaceId?:number;
  renderMemberActions: (m: Member) => ReactNode;
};
export function WorkspaceAvatar({ email, tone = "lilac", large = false }: { email: string; tone?: string; large?: boolean }) {
  return <span title={email} className={`ws-avatar ${tone} ${large ? "large" : ""}`}>{personName(email).split(" ").slice(0, 2).map(s => s[0]).join("").toUpperCase()}</span>;
}
export function WorkspaceWork({ tasks, members, projects, view, query, projectFilter, setProjectFilter, assigneeFilter, setAssigneeFilter, canEdit, updateTask, onOpen, onRefresh, onInvite, onError, onNotice, onClearSearch, renderMemberActions,onQueryChange,onCreateTask,workspaceId,renderPlanning,searchInputRef,onViewChange }: Props) {
  const viewer=useAuthStore(s=>s.user);
  const viewKey=`pms-board-view-${viewer?.id}-${viewer?.access?.companyId}-${workspaceId||"shared"}`;
  const [page,setPage]=useState(1),[pageSize,setPageSize]=useState(25);
  const [tableQuery,setTableQuery]=useState<GridQuery>();
  const [personalFilter,setPersonalFilter]=useState<GridPersonalFilter>();
  const [savedViewsHost,setSavedViewsHost]=useState<HTMLDivElement|null>(null);
  const [hasFilterSnapshot,setHasFilterSnapshot]=useState(false);
  useEffect(()=>{try{setHasFilterSnapshot(!!localStorage.getItem(viewKey));}catch{setHasFilterSnapshot(false);}},[viewKey]);
  const [focus, setFocus] = useState<WorkFocus>("all");
  const [today, setToday] = useState(localWorkDate);
  useEffect(() => { const timer = window.setInterval(() => setToday(localWorkDate()), 30000); return () => window.clearInterval(timer); }, []);
  useEffect(() => setFocus("all"), [viewKey]);
  const [peopleRole, setPeopleRole] = useState("");
  const [priority, setPriority] = useState("");
  const [status,setStatus]=useState("");const [workType,setWorkType]=useState("");
  const [draggedId, setDraggedId] = useState<number | null>(null);
  const [quickLane, setQuickLane] = useState<string | null>(null);
  const [quickTitle, setQuickTitle] = useState("");
  const [quickFields,setQuickFields]=useState<FieldDraft>({});
  const [adding, setAdding] = useState(false);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }), useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }));
  const createProjectId = Number(projectFilter) || projects[0]?.id;
  useEffect(()=>setQuickFields({}),[createProjectId]);
  const baseMatches = useMemo(() => tasks.filter(t => (!query || `${t.title} ${t.task_key} ${t.description || ""}`.toLowerCase().includes(query.toLowerCase())) && (!projectFilter || t.project_id === Number(projectFilter)) && (!assigneeFilter || (assigneeFilter === "unassigned" ? !taskAssignees(t).length : taskAssignees(t).includes(Number(assigneeFilter)))) && (!priority || t.priority === priority)&&(!status||t.status===status)&&(!workType||(t.work_type||"Task")===workType)), [tasks, query, projectFilter, assigneeFilter, priority,status,workType]);
  const custom=useCustomFieldRecords("task",view!=="people"&&view!=="activity"?baseMatches.map(t=>t.id):[]);
  const customColumns=[...new Map(Object.values(custom.records).flatMap(r=>r.fields).map(f=>[f.id,f])).values()];
  const projectFor = (id: number) => projects.find(p => p.id === id);
  const memberFor = (id?: number | null) => members.find(m => m.user_id === id);
  const columns:GridColumn<Task>[] = [
          { id: "title", title: "Task", width: 300, accessor: task => task.title, render: task => <button className="ws-list-title" onClick={() => onOpen(task.id)}><Circle size={15}/><span><small>{task.task_key}</small>{task.title}</span></button> },
          { id: "project", title: "Project", accessor: task => projectFor(task.project_id)?.name },
          { id: "status", title: "Status", type: "status", render: task => <StatusSelect label={`Status for ${task.title}`} value={task.status} disabled={!canEdit} options={[...lanes.map(l=>l.status),"Blocked"]} onSave={status=>updateTask(task,{status})}/> },
          { id: "assignees", title: "Assignees", width: 220, accessor: task => taskAssignees(task).map(id => personName(memberFor(id)?.email || "Unknown")).join(", "), render: task => <AssigneePicker label={`Assignees for ${task.title}`} disabled={!canEdit} people={members.filter(m=>m.role!=="Guest").map(m=>({id:m.user_id,email:m.email}))} value={taskAssignees(task)} onChange={ids=>updateTask(task,{assignee_user_ids:ids})}/> },
          { id: "due_date", title: "Due date", type: "date", render: task => dateLabel(task.due_date) },
          { id: "priority", title: "Priority", type: "status", render: task => <span data-priority-badge data-priority={task.priority} className={`ws-priority ${task.priority.toLowerCase()}`}><Flag size={11}/>{task.priority}</span> },
          ...customColumns.map(f=>({ id: `cf:${f.id}`, title: f.name, accessor:(task:Task)=>custom.records[task.id]?.fields.find(item=>item.id===f.id)?.value, render:(task:Task)=>{const record=custom.records[task.id];const field=record?.fields.find(item=>item.id===f.id);return field?<CustomFieldCell entity="task" id={task.id} field={field} canEdit={record.can_edit} onSaved={custom.reload}/>:"—";} })),
        ];
  const matchingFilters = personalRows(localGridSource("workspace-task-filters",baseMatches,columns,task=>String(task.id)).summaryRows!(tableQuery || emptyQuery()),personalFilter,task=>String(task.id));
  const filtered = matchingFilters.filter(task => matchesWorkFocus(task, focus, today));
  const tableFilterCount = tableQuery ? filterRules(tableQuery.filters).length : 0;
  const focusIcons = { all: Folder, overdue: AlertCircle, today: CalendarClock, blocked: Ban, unassigned: Users, unscheduled: Clock3 };
  useEffect(()=>setPage(1),[query,projectFilter,assigneeFilter,priority,status,workType,pageSize,focus]);
  const pageTasks=filtered.slice((page-1)*pageSize,page*pageSize);
  const visiblePeople = members.filter(member => (!peopleRole || member.role === peopleRole)
    && (!query || `${personName(member.email)} ${member.email} ${member.role}`.toLowerCase().includes(query.toLowerCase())));
  function exportPeople() {
    const cell = (value: string) => `"${(/^[=+@\-\t\r]/.test(value) ? "'" + value : value).replace(/"/g, '""')}"`;
    const csv = [["Member ID", "Name", "Email", "Role"], ...visiblePeople.map(member => [String(member.id), personName(member.email), member.email, member.role])].map(row => row.map(cell).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = "workspace-people.csv";
    anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    onNotice(`${visiblePeople.length} people exported`);
  }
  async function drop(event: DragEndEvent) {
    setDraggedId(null);
    if (!canEdit || !event.over || event.active.id === event.over.id) return;
    const task = tasks.find(t => t.id === parseInt(String(event.active.id).replace("task-", ""), 10));
    if (!task) return;
    const destination = String(event.over.id);
    if (destination.startsWith("person:")) {
      const id = Number(destination.split(":")[1]) || null;
      if (await updateTask(task, { assignee_user_ids: id ? [...new Set([...taskAssignees(task), id])] : [] })) onNotice(id ? `Assigned to ${personName(memberFor(id)?.email || "teammate")}` : "Task unassigned");
    } else {
      const target = tasks.find(t => t.id === parseInt(destination.replace("task-", ""), 10));
      const status = target ? bucket(target.status) : destination.replace("status:", "");
      if (!lanes.some(l => l.status === status)) return;
      const position = target && target.project_id === task.project_id ? target.position : tasks.filter(t => t.project_id === task.project_id && bucket(t.status) === status).length;
      if (await updateTask(task, { status, position })) onNotice(`Moved to ${lanes.find(l => l.status === status)?.label}`);
    }
  }
  async function quickAdd(status: string) {
    if (!quickTitle.trim() || !createProjectId || adding) return;
    setAdding(true);
    const finish = beginProgress("Creating task");
    try { await tasksAPI.create(createProjectId, { title: quickTitle.trim(), task_key: `T-${crypto.randomUUID().slice(0, 8).toUpperCase()}`, custom_fields:quickFields, status: status as any, priority: (priority || "Medium") as TaskPriority, assignee_user_id: assigneeFilter && assigneeFilter !== "unassigned" && memberFor(Number(assigneeFilter))?.role !== "Guest" ? Number(assigneeFilter) : undefined }); if (assigneeFilter && memberFor(Number(assigneeFilter))?.role === "Guest") setAssigneeFilter(""); onClearSearch?.(); setQuickTitle(""); setQuickFields({}); setQuickLane(null); await onRefresh(); onNotice("Task created"); finish(); }
    catch (e) { finish(false); await onRefresh().catch(() => undefined); onError(workspaceError(e)); } finally { setAdding(false); }
  }
  const filterContext = {query,projectFilter,assigneeFilter,priority,status,workType,focus,personalKind:personalFilter?.kind||null};
  function restoreFilters(saved:Record<string,unknown>) {
    // Older named table layouts have no collection context; keep current filters.
    if(!Object.keys(saved).length)return;
    if("personalKind" in saved)personalFilter?.apply(saved.personalKind==="favorites"||saved.personalKind==="frequent"?saved.personalKind:null);
    const text=(key:string)=>typeof saved[key]==="string"?saved[key] as string:"";
    onQueryChange?.(text("query"));
    setProjectFilter(projects.some(p=>String(p.id)===text("projectFilter"))?text("projectFilter"):"");
    setAssigneeFilter(text("assigneeFilter")==="unassigned"||members.some(m=>String(m.user_id)===text("assigneeFilter"))?text("assigneeFilter"):"");
    setPriority(text("priority"));setStatus(text("status"));setWorkType(text("workType"));
    setFocus(workFocusOptions.some(option=>option.id===saved.focus)?saved.focus as WorkFocus:"all");
    if(["list","board","calendar","workload"].includes(String(saved.presentation)))onViewChange?.(saved.presentation as Props["view"]);
  }
  function saveFilterSnapshot() {
    try{localStorage.setItem(viewKey,JSON.stringify({...filterContext,tableQuery}));setHasFilterSnapshot(true);onNotice("Personal filter snapshot saved in this browser");}
    catch{onError("Could not save filters in this browser. Your current filters are unchanged.");}
  }
  function restoreFilterSnapshot() {
    try{
      const saved=JSON.parse(localStorage.getItem(viewKey)||"null");
      if(!saved||typeof saved!=="object"||Array.isArray(saved))throw new Error("Invalid snapshot");
      restoreFilters(saved);
      if(saved.tableQuery&&typeof saved.tableQuery==="object"&&saved.tableQuery.filters)setTableQuery(sanitizeQuery(saved.tableQuery,columns));
      else setTableQuery(current=>({...current||emptyQuery(),search:"",filters:{logic:"and",rules:[]},path:[],page:1}));
      onNotice("Workspace filters restored");
    }catch{onError("Could not restore this filter snapshot. Save it again.");}
  }
  const renderCard = (task: Task, compact = false, context = "") => <WorkCard sortableId={`task-${task.id}${context}`} key={task.id} task={task} members={members} project={projectFor(task.project_id)} disabled={!canEdit} onOpen={() => onOpen(task.id)} compact={compact} onChanged={onRefresh} />;
  return <>
    {view !== "people" && view !== "activity" && <div className="ws-filterbar"><div className="ws-filter-controls">{onQueryChange&&<label className="wb-task-search"><Search size={16}/><input ref={searchInputRef} aria-label="Search tasks in workspace" value={query} placeholder="Search tasks by title, description, ID..." onChange={e=>onQueryChange(e.target.value)}/></label>}<label><Folder size={14} /><NativeSelect aria-label="Filter project" value={projectFilter} onChange={e => setProjectFilter(e.target.value)}><option value="">All projects</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</NativeSelect></label><label><Users size={14} /><NativeSelect aria-label="Filter assignee" value={assigneeFilter} onChange={e => setAssigneeFilter(e.target.value)}><option value="">All assignees</option><option value="unassigned">Unassigned</option>{members.map(m => <option key={m.id} value={m.user_id}>{personName(m.email)}</option>)}</NativeSelect></label><details className="wb-task-more-filters"><summary>More filters{([status,priority,workType].filter(Boolean).length + tableFilterCount) > 0 && ` (${[status,priority,workType].filter(Boolean).length + tableFilterCount})`}</summary><div><label><NativeSelect aria-label="Filter task status" value={status} onChange={e=>setStatus(e.target.value)}><option value="">All statuses</option>{[...new Set([...lanes.map(l=>l.status),"Blocked","Cancelled",...tasks.map(t=>t.status)])].map(value=><option key={value}>{value}</option>)}</NativeSelect></label><label><Flag size={14} /><NativeSelect aria-label="Filter priority" value={priority} onChange={e => setPriority(e.target.value)}><option value="">All priorities</option>{["Low", "Medium", "High", "Urgent", "Critical"].map(p => <option key={p}>{p}</option>)}</NativeSelect></label><label><NativeSelect aria-label="Filter task type" value={workType} onChange={e=>setWorkType(e.target.value)}><option value="">All task types</option>{[...new Set(["Task","Story","Bug",...tasks.map(t=>t.work_type||"Task")])].map(value=><option key={value}>{value}</option>)}</NativeSelect></label></div></details><div ref={setSavedViewsHost} className="wb-saved-views"/>{(query || projectFilter || assigneeFilter || priority || status || workType || focus!=="all" || !!tableQuery?.filters.rules.length || personalFilter?.ids!==undefined) && <button className="ws-clear" onClick={() => { personalFilter?.apply(null); setProjectFilter(""); setAssigneeFilter(""); setPriority("");setStatus("");setWorkType(""); setFocus("all"); setTableQuery(current=>({...current||emptyQuery(),search:"",filters:{logic:"and",rules:[]},page:1,path:[]})); onClearSearch?.(); }}>Clear filters<X size={12} /></button>}</div><span>{filtered.length} of {tasks.length} task{filtered.length !== 1 ? "s" : ""}</span></div>}
    {view !== "people" && view !== "activity" && <nav className="ws-focus-strip" aria-label="Focus work by attention needed">{workFocusOptions.map(option => { const Icon = focusIcons[option.id]; const count = matchingFilters.filter(task => matchesWorkFocus(task, option.id, today)).length; return <button key={option.id} type="button" className={`ws-focus-${option.id}`} aria-pressed={focus===option.id} onClick={()=>setFocus(option.id)}><Icon size={16} aria-hidden="true"/><span>{option.label}</span><strong>{count}</strong></button>; })}</nav>}
    {personalFilter?.kind&&<p role="status" className="text-xs text-muted-foreground">{personalFilter.kind==="favorites"?"Favorites":"Frequent"} applies across task views. <button type="button" className="underline" onClick={()=>personalFilter.apply(null)}>Show all matching tasks</button></p>}
    {tableFilterCount > 0 && <p role="status" className="text-xs text-muted-foreground">{tableFilterCount} advanced {tableFilterCount === 1 ? "condition applies" : "conditions apply"} to all task views. Edit conditions in List → Filters, or clear all filters.</p>}
    {custom.error&&<p role="alert" className="text-sm text-destructive">Custom fields could not load. {custom.error} <Button type="button" variant="outline" onClick={custom.reload}>Retry fields</Button></p>}
    <DndContext sensors={sensors} collisionDetection={collision} onDragStart={e => setDraggedId(parseInt(String(e.active.id).replace("task-", ""), 10))} onDragEnd={e => { void drop(e); }} onDragCancel={() => setDraggedId(null)}>
      {view !== "people" && view !== "activity" && <div className={`ws-assignment-bar ${draggedId ? "dragging" : ""}`}><span><Users size={14} />{draggedId ? "Drop to assign" : "Your team"}</span><div>{members.filter(m => m.role !== "Guest").map((m, i) => <PersonDrop key={m.id} member={m} tone={tones[i % tones.length]} disabled={!canEdit} />)}<PersonDrop disabled={!canEdit} /></div>{onInvite && <button aria-label="Invite a teammate" className="ws-add-person" onClick={onInvite}><Plus size={14} /></button>}</div>}
      {view === "board" && <div className="ws-board">{lanes.map(lane => { const items = filtered.filter(t => bucket(t.status) === lane.status); return <StatusLane key={lane.status} {...lane} count={items.length} disabled={!canEdit}><SortableContext items={items.map(t => `task-${t.id}`)} strategy={verticalListSortingStrategy}>{items.map(t => renderCard(t))}</SortableContext>{!items.length && <div className="ws-lane-empty"><Circle size={19} /><span>{lane.status === "Done" ? "Good things take teamwork." : "A little breathing room."}</span></div>}{canEdit && (quickLane === lane.status ? <CompactForm className="ws-quick-add" onKeyDown={e => { if (e.key === "Escape") { e.preventDefault(); setQuickLane(null); } }} onSubmit={e => { e.preventDefault(); void quickAdd(lane.status); }}><input autoFocus aria-label={`New task in ${lane.label}`} placeholder="What needs to get done?" value={quickTitle} onChange={e => setQuickTitle(e.target.value)} required /><CustomFieldsForm placement="quick_create" entity="task" workType="Task" projectId={createProjectId} values={quickFields} onChange={setQuickFields}/><div><small>{projectFor(createProjectId)?.name || "Create a project first"}</small><button type="button" aria-label="Cancel quick add" onClick={() => setQuickLane(null)}><X size={14} /></button><Button type="submit" variant="default" className="ws-mini-primary" disabled={adding || !createProjectId}>Add</Button></div></CompactForm> : <Button type="submit" variant="default" className="ws-add-task suite-task-button" onClick={() => { setQuickLane(lane.status); setQuickTitle(""); }}><Plus size={15} />Add task</Button>)}</StatusLane>; })}</div>}
      {view !== "people" && view !== "activity" && <div className="ws-table-wrap" hidden={view!=="list"} style={view!=="list"?{display:"none"}:undefined}><LocalRecordGrid<Task> gridId={`pms-workspace-work-${workspaceId || "shared"}`} compactControls hideSearch={!!onQueryChange} rows={filtered} getRowId={task => String(task.id)} onOpen={task => onOpen(task.id)} renderRowActions={(task,actions)=><RecordActions preview={false} record={{...task,key:task.task_key,project_name:projectFor(task.project_id)?.name}} canEdit={canEdit} people={members.filter(m=>m.role!=="Guest").map(m=>({id:m.user_id,name:personName(m.email)}))} onOpen={()=>onOpen(task.id)} onChanged={onRefresh} extraActions={actions.map(action=>({label:action.label,icon:action.icon?<action.icon size={15}/>:undefined,disabled:action.disabled?.(task),danger:action.danger,run:()=>{void action.run(task);}}))}>{menu=><span>{menu}</span>}</RecordActions>}
        onPersonalFilterChange={setPersonalFilter}
        savedViewsHost={savedViewsHost} savedViewsLabel="Saved views" viewContext={{...filterContext,presentation:view}} onViewContextChange={restoreFilters}
        savedViewsExtra={<section className="wb-filter-snapshot" aria-label="Last filter snapshot"><strong>Last filter snapshot</strong><p>Quick save for this workspace. Named views above also include table layout and workspace filters.</p><button type="button" className="udg-control" onClick={saveFilterSnapshot}>Save filter snapshot</button>{hasFilterSnapshot&&<button type="button" className="udg-control" onClick={restoreFilterSnapshot}>Restore filter snapshot</button>}</section>}
        columns={columns} queryState={tableQuery} onQueryChange={next=>{if(next.search)onQueryChange?.(next.search);setTableQuery(next.search?{...next,search:""}:next);}} onClearFilters={()=>{personalFilter?.apply(null);setProjectFilter("");setAssigneeFilter("");setPriority("");setStatus("");setWorkType("");setFocus("all");onClearSearch?.();}}
        bulkActions={canEdit ? [{ id:"done",label:"Mark done",confirm:records=>`Mark ${records.length} selected tasks done?`,run:async records=>{const outcomes=await Promise.allSettled(records.map(task=>updateTask(task,{status:"Done"})));const failed=outcomes.filter(result=>result.status==="rejected"||!result.value).length;if(failed)throw new Error(`${failed} task updates failed. Review selected records before retrying.`);onNotice(`${records.length} tasks completed`);} }] : []}
      />{!filtered.length && <div className="ws-empty-results wb-empty"><img src="/module-art/pms.webp" width="135" height="135" alt=""/><h2>No tasks match this view</h2><p>Try adjusting your filters, switch to another project or workspace, or create your first task to get started.</p><div>{canEdit&&onCreateTask&&<Button type="submit" variant="default" className="ws-button ws-primary" onClick={onCreateTask}><Plus size={17}/>Create your first task</Button>}<Link className="ws-button ws-outline" to={`/pms/projects${workspaceId?`?workspace=${workspaceId}`:""}`}><Folder size={17}/>Browse projects</Link></div></div>}</div>}
      {view==="list"&&<></>}
      {view === "people" && <><div className="ws-people-heading"><div><h2>Meet your people<span data-count-badge data-count-tone="purple">{members.length}</span></h2><p>The right people, with the right work, in one place.</p></div><span><ShieldCheck size={14} />Workspace roles keep access clear</span></div><div className="mb-4 flex flex-wrap items-center gap-3"><label className="text-sm font-medium">Workspace role <NativeSelect aria-label="Filter people by role" className="ml-2 rounded-md border bg-background px-3 py-2" value={peopleRole} onChange={event => setPeopleRole(event.target.value)}><option value="">All roles ({members.length})</option>{["Owner", "Admin", "Member", "Guest"].map(role => <option key={role} value={role}>{role} ({members.filter(member => member.role === role).length})</option>)}</NativeSelect></label><span role="status" className="text-sm text-muted-foreground">{visiblePeople.length} people shown</span>{onInvite && <Button variant="outline" type="button" className="ws-button ws-outline" disabled={!visiblePeople.length} onClick={exportPeople}>Export filtered people</Button>}</div><details className="mb-5 rounded-lg border bg-background p-4"><summary className="cursor-pointer font-medium">Understand workspace access</summary><div className="mt-3 grid gap-3 sm:grid-cols-2">{[["Owner", "Manages the workspace and appoints administrators. The owner cannot be removed through member controls."], ["Admin", "Manages projects, invitations, members and guests. Only the owner can manage administrators."], ["Member", "Creates and updates tasks, assigns collaborators and adds comments."], ["Guest", "Has read-only workspace access. Guests cannot be assigned tasks."]].map(([role, description]) => <div key={role} className="rounded-md bg-muted/40 p-3"><strong>{role}</strong><p className="mt-1 text-sm text-muted-foreground">{description}</p></div>)}</div></details>{!visiblePeople.length && <p role="status" className="mb-4 rounded-lg border border-dashed p-6 text-center">No people match this search and role filter.</p>}<div className="ws-people-grid">{visiblePeople.map((m, i) => { const work = tasks.filter(t => taskAssignees(t).includes(m.user_id) && bucket(t.status) !== "Done"); return <PersonPanel key={m.id} member={m} disabled={!canEdit}><div className={`ws-person-cover ${tones[i % tones.length]}`}><WorkspaceAvatar email={m.email} tone={tones[i % tones.length]} large /><span className="ws-person-role">{m.role}</span></div><div className="ws-person-body"><h3>{m.name || personName(m.email)}</h3><p>{m.email}</p><div className="ws-person-stats"><span><strong>{work.length}</strong>open tasks</span><span><strong>{tasks.filter(t => taskAssignees(t).includes(m.user_id) && bucket(t.status) === "Done").length}</strong>completed</span></div><SortableContext items={work.slice(0, 3).map(t => `task-${t.id}:person-${m.user_id}`)} strategy={verticalListSortingStrategy}><div className="ws-person-tasks">{work.slice(0, 3).map(t => renderCard(t, true, `:person-${m.user_id}`))}{work.length > 3 && <small>+{work.length - 3} more tasks</small>}{!work.length && <p>{m.role === "Guest" ? "Read-only workspace access" : "Ready for the next great thing."}</p>}</div></SortableContext><div className="ws-person-footer"><ManagePersonButton userId={m.user_id} />{renderMemberActions(m)}<Button variant="outline" type="button" aria-label={`Copy member ID for ${m.email}`} onClick={() => { void navigator.clipboard.writeText(String(m.id)).then(() => onNotice("Member ID copied")).catch(() => onError("Unable to copy member ID. Check clipboard access and retry.")); }}>Copy member ID</Button></div></div></PersonPanel>; })}{onInvite && <button className="ws-invite-card" onClick={onInvite}><span><Plus size={26} /></span><strong>Better with your team.</strong><p>Add registered people directly<br />to build something great together.</p><span className="ws-invite-card-link">Add existing person<ArrowUpRight size={14} /></span></button>}</div></>}
      {renderPlanning?.(filtered)}
      <DragOverlay dropAnimation={null}>{draggedId && tasks.find(t => t.id === draggedId) ? <div className="ws-drag-preview"><GripVertical size={15} /><strong>{tasks.find(t => t.id === draggedId)?.title}</strong><span>Drop to move or assign</span></div> : null}</DragOverlay>
    </DndContext>
  </>;
}
function StatusLane({ status, label, color, count, disabled, children }: { status: string; label: string; color: string; count: number; disabled: boolean; children: ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({ id: `status:${status}`, disabled });
  return <section ref={setNodeRef} aria-label={`${label} column`} className={`ws-lane ${isOver ? "over" : ""}`} style={{ "--lane-color": color } as React.CSSProperties}><header><i /><h2>{label}</h2><span data-count-badge data-count-tone="purple">{count}</span></header><div className="ws-lane-body">{children}</div></section>;
}
function WorkCard({ task, members, project, sortableId, disabled, onOpen, compact = false, onChanged }: { task: Task; members: Member[]; project?: Project; sortableId: string; disabled: boolean; onOpen: () => void; compact?: boolean; onChanged: () => Promise<void> }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: sortableId, disabled });
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const overdue = task.due_date && new Date(task.due_date + "T00:00:00") < today && bucket(task.status) !== "Done";
  return <RecordActions record={{...task, key:task.task_key, project_name:project?.name}} canEdit={!disabled} people={members.filter(m=>m.role!=="Guest").map(m=>({id:m.user_id,name:personName(m.email)}))} onOpen={onOpen} onChanged={onChanged}>{menu => <article data-priority-row data-priority={task.priority} tabIndex={0} ref={setNodeRef} data-testid={`task-card-${task.id}`} className={`ws-task-card ${compact ? "compact" : ""} ${isDragging ? "is-dragging" : ""}`} style={{ transform: CSS.Transform.toString(transform), transition }}><div className="ws-card-top"><span className="ws-card-project">{project?.name || task.task_key}</span>{menu}<button className="ws-grip" aria-label={`Drag ${task.title}`} disabled={disabled} {...attributes} {...listeners}><GripVertical size={15} /></button></div><button className="ws-card-title" onClick={onOpen}>{task.title}</button>{!compact && <><div data-priority-row data-priority={task.priority} className="ws-card-tags"><span data-priority-badge data-priority={task.priority} className={`ws-priority ${task.priority.toLowerCase()}`}><Flag size={10} />{task.priority}</span>{task.status === "Blocked" && <span className="ws-blocked">Blocked</span>}</div>{task.description && <div className="ws-card-description"><RichTextContent value={task.description}/></div>}<footer><span className={overdue ? "overdue" : ""}><CalendarDays size={12} />{dateLabel(task.due_date)}</span><span className="ws-card-meta">{!!task.comments_count && <span><MessageSquare size={12} />{task.comments_count}</span>}{taskAssignees(task).length ? <span className="ws-small-avatars">{taskAssignees(task).map(id => { const person = members.find(m => m.user_id === id); return person ? <WorkspaceAvatar key={id} email={person.email} tone={tones[id % tones.length]} /> : null; })}</span> : <span className="ws-unassigned" title="Unassigned"><Users size={12} /></span>}</span></footer></>}</article>}</RecordActions>;
}
function PersonDrop({ member, tone, disabled }: { member?: Member; tone?: string; disabled: boolean }) {
  const { setNodeRef, isOver } = useDroppable({ id: `person:${member?.user_id || 0}`, disabled });
  return <div ref={setNodeRef} data-testid={`assign-${member?.user_id || 0}`} className={`ws-person-drop ${isOver ? "over" : ""}`} title={member ? `Assign to ${personName(member.email)}` : "Unassign task"}>{member ? <WorkspaceAvatar email={member.email} tone={tone} /> : <span className="ws-unassigned"><Users size={13} /></span>}<span>{member ? personName(member.email).split(" ")[0] : "Unassigned"}</span></div>;
}
function PersonPanel({ member, disabled, children }: { member: Member; disabled: boolean; children: ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({ id: `person:${member.user_id}`, disabled: disabled || member.role === "Guest" });
  return <section ref={setNodeRef} aria-label={`${personName(member.email)} member card`} className={`ws-person-panel ${isOver ? "over" : ""}`}>{children}</section>;
}

type TaskDrawerProps = { task?: Task; members: Member[]; canEdit: boolean; onClose: () => void; onUpdate: Props["updateTask"]; onRefresh: () => Promise<void>; onError: (s: string) => void; error?: string };
export function TaskDrawer(props:TaskDrawerProps){
  const scope=useRecordScope();
  return <ScopedTaskDrawer key={`${scope}:${props.task?.id||"closed"}`} {...props}/>;
}
function ScopedTaskDrawer({ task:serverTask, members, canEdit, onClose, onUpdate, onRefresh, onError, error = "" }:TaskDrawerProps) {
  const [openedTask,setOpenedTask]=useState(serverTask);
  const [failedEdit,setFailedEdit]=useState<{task:Task;changes:Partial<Task>;latest?:Task}|null>(null);
  const [savingProperty,setSavingProperty]=useState(false);
  const [localDrafts,setLocalDrafts]=useState<{estimated_hours?:string;description?:string}>({});
  const task=failedEdit?{...failedEdit.task,...failedEdit.changes}:openedTask;
  const saveProperty=async(changes:Partial<Task>,reviewed?:Task)=>{
    if(!task||!canEdit||savingProperty||discardAction||(failedEdit&&!reviewed))return false;
    setSavingProperty(true);
    try{
      const saved=await onUpdate(reviewed||task,changes);
      if(saved){
        setFailedEdit(null);
        setLocalDrafts(current=>({...current,...("estimated_hours" in changes?{estimated_hours:undefined}:{}),...("description" in changes?{description:undefined}:{})}));
        try{const latest=await tasksAPI.get(task.id);setOpenedTask({...task,...latest});onError("");}
        catch(e){setOpenedTask({...task,...changes});onError(`Task was saved, but its latest values could not be loaded. Reopen the task before editing again. ${workspaceError(e)}`);}
      }
      else setFailedEdit({task,changes});
      return saved;
    }catch(e){setFailedEdit({task,changes});onError(workspaceError(e));return false;}
    finally{setSavingProperty(false);}
  };
  const reviewLatest=async()=>{
    if(!task)return;
    setSavingProperty(true);
    try{const latest=await tasksAPI.get(task.id);setFailedEdit(current=>current?{...current,latest:{...task,...latest}}:null);onError("");}
    catch(e){onError(workspaceError(e));}
    finally{setSavingProperty(false);}
  };
  const discardEdit=async()=>{
    setSavingProperty(true);
    try{const latest=await tasksAPI.get(task!.id);await onRefresh();setOpenedTask({...task!,...latest});setFailedEdit(null);setLocalDrafts({});onError("");}
    catch(e){onError(workspaceError(e));}
    finally{setSavingProperty(false);}
  };
  const [comments, setComments] = useState<PMSComment[]>([]);
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [discardAction,setDiscardAction]=useState<(()=>void)|null>(null);
  const requestLeave=useMobileDraftGuard({enabled:!!task,dirty:!!failedEdit||Object.values(localDrafts).some(value=>value!==undefined)||!!richTextPlainText(comment).trim(),draftKey:JSON.stringify([task?.id,failedEdit?.changes,localDrafts,comment]),pending:()=>savingProperty||sending,onDiscard:()=>{setFailedEdit(null);setLocalDrafts({});setComment("");},message:"Discard your unsaved task changes and comment?",confirmDiscard:confirm=>setDiscardAction(()=>confirm)});
  useEffect(() => { setComment(""); }, [task?.id]);
  useRefreshableEffect(() => {
    setComments([]); if (!task) return;
    let active = true; setLoading(true);
    commentsAPI.listForTask(task.id).then(data => { if (active) setComments(data); }).catch(e => { if (active) onError(workspaceError(e)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [task?.id, serverTask?.comments_count]);
  return <><UnsavedTaskDialog onDiscard={discardAction} onKeep={()=>setDiscardAction(null)}/><Dialog.Root open={!!task} onOpenChange={open => { if (!open && requestLeave(onClose)) onClose(); }}><Dialog.Portal><Dialog.Overlay className="ws-overlay" /><Dialog.Content className="ws-modal ws-drawer" onInteractOutside={event=>{if(discardAction)event.preventDefault();}} onEscapeKeyDown={event => { if (discardAction || document.querySelector("[data-radix-menu-content]")) event.preventDefault(); }}><Dialog.Close className="ws-modal-close" aria-label="Close task"><X size={19} /></Dialog.Close>{task && <><RecordActions preview={false} record={{...task,key:task.task_key}} canEdit={canEdit} people={members.filter(m=>m.role!=="Guest").map(m=>({id:m.user_id,name:personName(m.email)}))} onChanged={async deleted=>{await onRefresh();if(deleted)onClose();else if(!failedEdit){const latest=await tasksAPI.get(task.id);setOpenedTask({...task,...latest});}}}>{menu=><div tabIndex={0}><div className="ws-drawer-key flex items-center justify-between">TASK / {task.task_key}{menu}</div><Dialog.Title>{task.title}</Dialog.Title><Dialog.Description>Task details and team conversation</Dialog.Description></div>}</RecordActions>{error && <div className="ws-alert" role="alert">{error}</div>}{failedEdit&&<TaskEditReview changes={failedEdit.changes} latest={failedEdit.latest} busy={savingProperty} canEdit={canEdit} people={members.map(person=>({id:person.user_id,name:person.name||personName(person.email)}))} onReview={()=>void reviewLatest()} onApply={()=>void saveProperty(failedEdit.changes,failedEdit.latest)} onDiscard={()=>void discardEdit()}/>}<TaskPropertyStrip
 status={<TaskStatusControl taskId={task.id} version={task.updated_at} value={task.status} disabled={!canEdit||savingProperty||!!failedEdit} onSave={status=>saveProperty({status})} approvalHref={`/pms/tasks/${task.id}`}/>}
 assignees={<AssigneePicker projectId={task.project_id} disabled={!canEdit||savingProperty||!!failedEdit} people={members.filter(m=>m.role!=="Guest").map(m=>({id:m.user_id,email:m.email}))} value={taskAssignees(task)} onChange={ids=>saveProperty({assignee_user_ids:ids})}/>}
 priority={<NativeSelect aria-label="Task priority" className="w-full rounded-md border bg-background p-2" disabled={!canEdit||savingProperty||!!failedEdit} value={task.priority} onChange={e=>{void saveProperty({priority:e.target.value});}}>{["Low","Medium","High","Urgent","Critical"].map(p=><option key={p}>{p}</option>)}</NativeSelect>}
 estimate={<input className="w-full rounded-md border bg-background p-2" aria-label="Task estimated hours" type="number" min="0" step="0.5" disabled={!canEdit||savingProperty||!!failedEdit} key={`${task.id}:${task.estimated_hours}`} defaultValue={task.estimated_hours??""} onChange={e=>{const value=e.target.value;setLocalDrafts(current=>({...current,estimated_hours:Number(value)===Number(task.estimated_hours??0)?undefined:value}));}} onBlur={e=>{const hours=e.target.value===""?undefined:Number(e.target.value);if(hours!==undefined&&Number.isFinite(hours)&&hours>=0&&hours!==Number(task.estimated_hours))void saveProperty({estimated_hours:hours});}}/>}
 start={<input className="w-full rounded-md border bg-background p-2" aria-label="Task start date" disabled={!canEdit||savingProperty||!!failedEdit} type="date" value={task.start_date||""} onChange={e=>{if(e.target.value)void saveProperty({start_date:e.target.value});}}/>}
 due={<input className="w-full rounded-md border bg-background p-2" aria-label="Task due date" disabled={!canEdit||savingProperty||!!failedEdit} type="date" value={task.due_date||""} onChange={e=>{if(e.target.value)void saveProperty({due_date:e.target.value});}}/>}
/><div className="ws-task-description"><h3>Description</h3><RichTextField data-legacy-format="markdown" aria-label="Task description" key={`${task.id}:${task.description}`} disabled={!canEdit||savingProperty||!!failedEdit} defaultValue={task.description || ""} onChange={e=>setLocalDrafts(current=>({...current,description:e.target.value===(task.description||"")?undefined:e.target.value}))} placeholder="Add context, a brief, or a useful link…" onBlur={e => { if (e.target.value !== (task.description || "")) void saveProperty( { description: e.target.value }); }} /></div><TaskCustomFields key={task.id} taskId={task.id} projectId={task.project_id} /><div className="ws-conversation"><h3><MessageSquare size={16} />Conversation<span data-count-badge data-count-tone="purple">{comments.length}</span></h3>{loading ? <p>Loading conversation…</p> : comments.map(c => { const author = members.find(m => m.user_id === c.author_user_id); return <article key={c.id}><WorkspaceAvatar email={author?.email || "Teammate"} /><div><strong>{author ? personName(author.email) : "Teammate"}</strong><time>{new Date(c.created_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</time><div><RichTextContent value={c.body}/></div></div></article>; })}{!loading && !comments.length && <p className="ws-conversation-empty">A question, an update, a little context.<br />Keep the conversation close to the work.</p>}{canEdit && <CompactForm onSubmit={e => { e.preventDefault(); if (!comment.trim() || sending) return; setSending(true); commentsAPI.addToTask(task.id, { body: comment.trim(), body_format: "plain", is_internal: false }).then(async () => { setComment(""); onError(""); await onRefresh(); }).catch(e => onError(workspaceError(e))).finally(() => setSending(false)); }}><RichTextField data-legacy-format="markdown" aria-label="Write a comment" value={comment} onChange={e => setComment(e.target.value)} placeholder="Share an update or ask a question…" required /><button aria-label="Send comment" className="ws-button ws-primary" disabled={sending || !comment.trim()}><Send size={15} />Send</button></CompactForm>}</div><Button asChild variant="outline"><Link className="ws-full-task" to={`/pms/tasks/${task.id}`}>Open full task details<ArrowUpRight size={14} /></Link></Button></>}</Dialog.Content></Dialog.Portal></Dialog.Root></>;
}
