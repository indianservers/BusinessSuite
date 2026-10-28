import { useRefreshableEffect } from "@/lib/page-refresh";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  PointerSensor,
  closestCorners,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { CheckCircle2, ChevronDown, ChevronRight, GripVertical, ListChecks, Play, Plus, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn, formatDate, statusColor } from "@/lib/utils";
import CreateTaskModal from "../components/CreateTaskModal";
import { backlogAPI, projectsAPI, sprintsAPI, tasksAPI } from "../services/api";
import type { PMSBacklogResponse, PMSBacklogSprint, PMSProject, PMSTaskListItem } from "../types";

type ContainerId = "backlog" | `sprint-${number}`;

const sortOptions = [
  { value: "rank", label: "Rank" },
  { value: "priority", label: "Priority" },
  { value: "createdDate", label: "Created date" },
];

export default function BacklogPage() {
  const [projects, setProjects] = useState<PMSProject[]>([]);
  const [projectId, setProjectId] = useState("");
  const [data, setData] = useState<PMSBacklogResponse | null>(null);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("rank");
  const [activeTask, setActiveTask] = useState<PMSTaskListItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showTaskModal, setShowTaskModal] = useState(false);
  const [showSprintForm, setShowSprintForm] = useState(false);
  const [collapsedCompleted, setCollapsedCompleted] = useState(true);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  useEffect(() => {
    projectsAPI.list().then((items) => {
      setProjects(items);
      const firstId = String(items[0]?.id || "");
      setProjectId(firstId);
    }).catch((err) => setError(err?.response?.data?.detail || "Unable to load projects."));
  }, []);

  useRefreshableEffect(() => {
    if (!projectId) {
      setLoading(false);
      return;
    }
    loadBacklog(Number(projectId));
  }, [projectId, sortBy]);

  const activeSprint = data?.sprints.find((sprint) => sprint.status === "Active") || null;
  const futureSprints = data?.sprints.filter((sprint) => sprint.status === "Planned") || [];
  const completedSprints = data?.sprints.filter((sprint) => sprint.status === "Completed") || [];
  const visibleBacklog = useMemo(() => filterTasks(data?.backlog || [], search), [data?.backlog, search]);
  const visibleActiveSprint = activeSprint ? { ...activeSprint, tasks: filterTasks(activeSprint.tasks, search) } : null;
  const visibleFutureSprints = futureSprints.map((sprint) => ({ ...sprint, tasks: filterTasks(sprint.tasks, search) }));
  const visibleCompletedSprints = completedSprints.map((sprint) => ({ ...sprint, tasks: filterTasks(sprint.tasks, search) }));

  async function loadBacklog(id = Number(projectId)) {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      setData(await backlogAPI.get(id, { search: search.trim() || undefined, sortBy }));
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to load backlog.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDragEnd(event: DragEndEvent) {
    const activeId = String(event.active.id);
    const overId = event.over ? String(event.over.id) : "";
    setActiveTask(null);
    if (!data || !activeId.startsWith("task-") || !overId) return;
    const taskId = Number(activeId.replace("task-", ""));
    const destination = findDestination(overId, data);
    if (!destination) return;
    const source = findTaskContainer(taskId, data);
    if (!source || source === destination.containerId && destination.beforeTaskId === taskId) return;

    const previous = data;
    const next = moveTaskLocally(data, taskId, destination.containerId, destination.beforeTaskId);
    setData(next);
    try {
      if (destination.containerId === "backlog") {
        await tasksAPI.removeFromSprint(taskId);
        await backlogAPI.reorder(next.project.id, next.backlog.map((task) => task.id));
      } else {
        const sprintId = Number(destination.containerId.replace("sprint-", ""));
        await tasksAPI.moveToSprint(taskId, sprintId);
        const sprintTasks = next.sprints.find((sprint) => sprint.id === sprintId)?.tasks || [];
        await sprintsAPI.reorderTasks(sprintId, sprintTasks.map((task) => task.id));
      }
      await loadBacklog(next.project.id);
    } catch (err: any) {
      setData(previous);
      setError(err?.response?.data?.detail || "Unable to move task.");
    }
  }

  const createSprint = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") || "").trim();
    const startDate = String(form.get("start_date") || "");
    const endDate = String(form.get("end_date") || "");
    if (!projectId || !name || !startDate || !endDate) return;
    await sprintsAPI.create(Number(projectId), {
      name,
      goal: String(form.get("goal") || ""),
      status: "Planned",
      start_date: startDate,
      end_date: endDate,
      capacity_hours: Number(form.get("capacity_hours") || 0),
    } as any);
    event.currentTarget.reset();
    setShowSprintForm(false);
    loadBacklog(Number(projectId));
  };

  const startSprint = async (sprint: PMSBacklogSprint) => {
    await sprintsAPI.start(sprint.id);
    loadBacklog(Number(projectId));
  };

  const completeSprint = async (sprint: PMSBacklogSprint) => {
    const carryForward = futureSprints.find((item) => item.id !== sprint.id)?.id;
    await sprintsAPI.complete(sprint.id, carryForward);
    loadBacklog(Number(projectId));
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="page-title">Backlog</h1>
          <p className="page-description">Groom unscheduled work, plan sprint scope, and drag tasks between backlog and sprints.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => setShowTaskModal(true)} disabled={!projectId}><Plus className="h-4 w-4" />Create task</Button>
          <Button variant="outline" onClick={() => setShowSprintForm((value) => !value)} disabled={!projectId}><Plus className="h-4 w-4" />Create sprint</Button>
        </div>
      </div>

      <Card>
        <CardContent className="grid gap-3 p-4 lg:grid-cols-[16rem_1fr_12rem_auto] lg:items-end">
          <Field label="Project">
            <select value={projectId} onChange={(event) => setProjectId(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
              {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select>
          </Field>
          <Field label="Search">
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => event.key === "Enter" && loadBacklog()} className="pl-9" placeholder="Search key, title, description" />
            </div>
          </Field>
          <Field label="Sort backlog">
            <select value={sortBy} onChange={(event) => setSortBy(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
              {sortOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </Field>
          <Button variant="outline" onClick={() => loadBacklog()} disabled={!projectId}>Refresh</Button>
        </CardContent>
      </Card>

      {showSprintForm ? (
        <Card>
          <CardHeader><CardTitle>Create sprint</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={createSprint} className="grid gap-3 md:grid-cols-[1fr_1fr_10rem_10rem_8rem_auto] md:items-end">
              <Field label="Name"><Input name="name" required /></Field>
              <Field label="Goal"><Input name="goal" /></Field>
              <Field label="Start"><Input name="start_date" type="date" required /></Field>
              <Field label="End"><Input name="end_date" type="date" required /></Field>
              <Field label="Capacity"><Input name="capacity_hours" type="number" min="0" defaultValue="40" /></Field>
              <Button type="submit">Create</Button>
            </form>
          </CardContent>
        </Card>
      ) : null}

      {error ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
      {loading ? <div className="skeleton h-96 rounded-lg" /> : null}

      {!loading && data ? (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={(event) => setActiveTask(findTaskById(Number(String(event.active.id).replace("task-", "")), data))}
          onDragEnd={handleDragEnd}
          onDragCancel={() => setActiveTask(null)}
        >
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(24rem,0.9fr)]">
            <BacklogSection id="backlog" title="Product backlog" subtitle={`${visibleBacklog.length} unscheduled tasks`} tasks={visibleBacklog} />
            <div className="space-y-4">
              {visibleActiveSprint ? (
                <SprintSection sprint={visibleActiveSprint} onStart={startSprint} onComplete={completeSprint} />
              ) : <EmptySprint />}
              {visibleFutureSprints.map((sprint) => <SprintSection key={sprint.id} sprint={sprint} onStart={startSprint} onComplete={completeSprint} />)}
              {completedSprints.length ? (
                <Card>
                  <CardHeader className="p-4">
                    <button type="button" onClick={() => setCollapsedCompleted((value) => !value)} className="flex w-full items-center justify-between text-left">
                      <CardTitle className="flex items-center gap-2 text-base">
                        {collapsedCompleted ? <ChevronRight className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                        Completed sprints
                      </CardTitle>
                      <Badge variant="outline">{completedSprints.length}</Badge>
                    </button>
                  </CardHeader>
                  {!collapsedCompleted ? <CardContent className="space-y-3 p-4 pt-0">{visibleCompletedSprints.map((sprint) => <SprintSection key={sprint.id} sprint={sprint} onStart={startSprint} onComplete={completeSprint} compact />)}</CardContent> : null}
                </Card>
              ) : null}
            </div>
          </div>
          <DragOverlay>{activeTask ? <TaskRow task={activeTask} dragging /> : null}</DragOverlay>
        </DndContext>
      ) : null}

      {projectId ? (
        <CreateTaskModal
          isOpen={showTaskModal}
          onClose={() => setShowTaskModal(false)}
          projectId={Number(projectId)}
          onTaskCreated={(_task, createAnother) => {
            if (!createAnother) setShowTaskModal(false);
            loadBacklog(Number(projectId));
          }}
        />
      ) : null}
    </div>
  );
}

function BacklogSection({ id, title, subtitle, tasks }: { id: ContainerId; title: string; subtitle: string; tasks: PMSTaskListItem[] }) {
  const { setNodeRef, isOver } = useDroppable({ id });
  return (
    <Card ref={setNodeRef} className={cn(isOver && "ring-2 ring-primary")}>
      <CardHeader className="p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-base"><ListChecks className="h-5 w-5" />{title}</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
          </div>
          <PointsBadge tasks={tasks} />
        </div>
      </CardHeader>
      <CardContent className="space-y-2 p-4 pt-0">
        <SortableContext items={tasks.map((task) => `task-${task.id}`)} strategy={verticalListSortingStrategy}>
          {tasks.map((task) => <SortableTaskRow key={task.id} task={task} />)}
        </SortableContext>
        {!tasks.length ? <EmptyDropText text="Drop tasks here or create a new task." /> : null}
      </CardContent>
    </Card>
  );
}

function SprintSection({ sprint, onStart, onComplete, compact = false }: { sprint: PMSBacklogSprint; onStart: (sprint: PMSBacklogSprint) => void; onComplete: (sprint: PMSBacklogSprint) => void; compact?: boolean }) {
  const id = `sprint-${sprint.id}` as ContainerId;
  const { setNodeRef, isOver } = useDroppable({ id });
  return (
    <Card ref={setNodeRef} className={cn(isOver && "ring-2 ring-primary")}>
      <CardHeader className="p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">{sprint.name}<Badge className={statusColor(sprint.status)}>{sprint.status}</Badge></CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">{formatDate(sprint.start_date)} - {formatDate(sprint.end_date)}</p>
            {!compact ? <p className="mt-1 text-sm text-muted-foreground">{sprint.goal || "No sprint goal."}</p> : null}
          </div>
          <div className="flex flex-wrap gap-2">
            <PointsBadge tasks={sprint.tasks} />
            <Button size="sm" onClick={() => onStart(sprint)} disabled={sprint.status !== "Planned"}><Play className="h-4 w-4" />Start</Button>
            <Button size="sm" variant="outline" onClick={() => onComplete(sprint)} disabled={sprint.status !== "Active"}><CheckCircle2 className="h-4 w-4" />Complete</Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 p-4 pt-0">
        <SortableContext items={sprint.tasks.map((task) => `task-${task.id}`)} strategy={verticalListSortingStrategy}>
          {sprint.tasks.map((task) => <SortableTaskRow key={task.id} task={task} />)}
        </SortableContext>
        {!sprint.tasks.length ? <EmptyDropText text={sprint.status === "Completed" ? "Completed sprint is locked for normal moves." : "Drop backlog tasks here."} /> : null}
      </CardContent>
    </Card>
  );
}

function SortableTaskRow({ task }: { task: PMSTaskListItem }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: `task-${task.id}` });
  return (
    <div ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition }} className={cn(isDragging && "opacity-40")}>
      <TaskRow task={task} dragHandle={{ ...attributes, ...listeners }} />
    </div>
  );
}

function TaskRow({ task, dragHandle, dragging = false }: { task: PMSTaskListItem; dragHandle?: Record<string, unknown>; dragging?: boolean }) {
  const tagNames = (task.tags || []).map((tag) => typeof tag === "string" ? tag : tag.name);
  return (
    <div className={cn("rounded-md border bg-background p-3 shadow-sm", dragging && "w-[36rem] shadow-lg")}>
      <div className="flex items-start gap-3">
        <button type="button" className="mt-1 rounded p-1 text-muted-foreground hover:bg-muted" aria-label={`Drag ${task.task_key}`} {...dragHandle}>
          <GripVertical className="h-4 w-4" />
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-primary">{task.task_key}</span>
            <Badge className={statusColor(task.priority)}>{task.priority}</Badge>
            <Badge variant="outline">{task.status}</Badge>
            <span className="text-sm text-muted-foreground">{task.story_points ?? 0} pts</span>
          </div>
          <p className="mt-1 truncate font-medium">{task.title}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span>{task.assignee_name || "Unassigned"}</span>
            {tagNames.slice(0, 4).map((tag) => <Badge key={tag} variant="outline" className="h-5 rounded px-1.5 text-[11px]">{tag}</Badge>)}
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="space-y-2"><Label className="text-xs uppercase text-muted-foreground">{label}</Label>{children}</div>;
}

function PointsBadge({ tasks }: { tasks: PMSTaskListItem[] }) {
  const points = tasks.reduce((sum, task) => sum + Number(task.story_points || 0), 0);
  return <Badge variant="secondary">{tasks.length} tasks / {points} pts</Badge>;
}

function EmptyDropText({ text }: { text: string }) {
  return <div className="rounded-md border border-dashed p-4 text-center text-sm text-muted-foreground">{text}</div>;
}

function EmptySprint() {
  return <Card><CardContent className="p-6 text-sm text-muted-foreground">No active sprint. Create or start a planned sprint to begin execution.</CardContent></Card>;
}

function filterTasks(tasks: PMSTaskListItem[], query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return tasks;
  return tasks.filter((task) => {
    const tagText = (task.tags || []).map((tag) => typeof tag === "string" ? tag : tag.name).join(" ");
    return [task.task_key, task.title, task.description, task.priority, task.status, tagText].some((value) => String(value || "").toLowerCase().includes(normalized));
  });
}

function findTaskById(taskId: number, data: PMSBacklogResponse) {
  return [data.backlog, ...data.sprints.map((sprint) => sprint.tasks)].flat().find((task) => task.id === taskId) || null;
}

function findTaskContainer(taskId: number, data: PMSBacklogResponse): ContainerId | null {
  if (data.backlog.some((task) => task.id === taskId)) return "backlog";
  const sprint = data.sprints.find((item) => item.tasks.some((task) => task.id === taskId));
  return sprint ? `sprint-${sprint.id}` : null;
}

function findDestination(overId: string, data: PMSBacklogResponse): { containerId: ContainerId; beforeTaskId?: number } | null {
  if (overId === "backlog" || overId.startsWith("sprint-")) return { containerId: overId as ContainerId };
  if (!overId.startsWith("task-")) return null;
  const taskId = Number(overId.replace("task-", ""));
  const containerId = findTaskContainer(taskId, data);
  return containerId ? { containerId, beforeTaskId: taskId } : null;
}

function moveTaskLocally(data: PMSBacklogResponse, taskId: number, containerId: ContainerId, beforeTaskId?: number): PMSBacklogResponse {
  const movingTask = findTaskById(taskId, data);
  if (!movingTask) return data;
  const remove = (tasks: PMSTaskListItem[]) => tasks.filter((task) => task.id !== taskId);
  const insert = (tasks: PMSTaskListItem[]) => {
    const next = remove(tasks);
    const index = beforeTaskId ? next.findIndex((task) => task.id === beforeTaskId) : -1;
    next.splice(index >= 0 ? index : next.length, 0, { ...movingTask, sprint_id: containerId === "backlog" ? undefined : Number(containerId.replace("sprint-", "")) });
    return next;
  };
  return {
    ...data,
    backlog: containerId === "backlog" ? insert(data.backlog) : remove(data.backlog),
    sprints: data.sprints.map((sprint) => {
      const id = `sprint-${sprint.id}` as ContainerId;
      return { ...sprint, tasks: id === containerId ? insert(sprint.tasks) : remove(sprint.tasks) };
    }),
  };
}
