import { useRefreshableEffect } from "@/lib/page-refresh";
/**
 * KaryaFlow - Kanban Board with Drag & Drop
 * Interactive Kanban board using DnD Kit for task management
 * This is the CORE Click & Drag feature
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  DndContext,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
  DragStartEvent,
  DragOverlay,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import {
  Bolt,
  ChevronDown,
  Clock3,
  Filter,
  Loader,
  MoreHorizontal,
  Plus,
  Search,
  Settings,
  Sparkles,
  Users,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useKanbanStore, useProjectStore, useTaskStore } from "../store";
import { kanbanAPI, projectsAPI } from "../services/api";
import { usePMSRealtime } from "../realtime";

import TaskViewPicker from "../components/TaskViewPicker";
import KanbanColumn from "../components/KanbanColumn";
import CreateTaskModal from "../components/CreateTaskModal";

/**
 * Kanban Board Main Component
 * Implements drag-and-drop with click handling
 */
const KanbanBoard: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const projectIdNum = parseInt(projectId || "0");

  const { board, setBoard, loading, setLoading } = useKanbanStore();
  const { selectedProject, setSelectedProject } = useProjectStore();
  const { tasks, setTasks, addTask, updateTask } = useTaskStore();

  const [activeId, setActiveId] = useState<number | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [query, setQuery] = useState("");
  const [epicFilter, setEpicFilter] = useState("All epics");
  const [groupBy, setGroupBy] = useState("Choices");
  const [assigneeFilter, setAssigneeFilter] = useState<number | "all">("all");
  const [priorityFilter, setPriorityFilter] = useState("All priorities");

  // Configure sensors for drag & drop
  const sensors = useSensors(
    useSensor(PointerSensor, {
      distance: 8,
      activationConstraint: {
        delay: 100,
        tolerance: 5,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const loadBoard = useCallback(async (active = true) => {
      if (!projectIdNum) return;
      try {
        setLoading(true);
        if (!selectedProject || selectedProject.id !== projectIdNum) {
          const project = await projectsAPI.get(projectIdNum);
          if (active) setSelectedProject(project);
        }
        const boardData = await kanbanAPI.getBoard(projectIdNum);
        if (!active) return;
        setBoard(boardData);

        // Flatten all tasks from columns
        const allTasks = boardData.columns?.flatMap((col) => col.tasks || []) || [];
        setTasks(allTasks);
      } catch (err: any) {
        setError("Failed to load Kanban board");
        console.error("Error loading board:", err);
      } finally {
        if (active) {
          setLoading(false);
          setHasLoaded(true);
        }
      }
    }, [projectIdNum, selectedProject, setBoard, setLoading, setSelectedProject, setTasks]);

  // Load board and tasks
  useRefreshableEffect(() => {
    let active = true;
    loadBoard(active);
    return () => {
      active = false;
    };
  }, [loadBoard]);

  usePMSRealtime({
    projectId: projectIdNum || undefined,
    onEvent: (event) => {
      if (event.type.startsWith("task.") || event.type === "sprint.updated" || event.type === "project.updated") {
        loadBoard(true);
      }
    },
    onFallbackPoll: () => loadBoard(true),
    showToast: false,
  });

  // Handle drag start
  const handleDragStart = (event: DragStartEvent) => {
    if (selectedProject?.can_manage_tasks === false) return;
    const { active } = event;
    setActiveId(active.id as number);
  };

  const activeTask = useMemo(() => tasks.find((task) => task.id === activeId), [activeId, tasks]);
  const filteredTasks = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return tasks.filter((task) => {
      const searchable = `${task.task_key} ${task.title} ${task.description || ""}`.toLowerCase();
      const matchesQuery = !normalizedQuery || searchable.includes(normalizedQuery);
      const matchesAssignee = assigneeFilter === "all" || task.assignee_user_id === assigneeFilter;
      const matchesPriority = priorityFilter === "All priorities" || task.priority === priorityFilter;
      const matchesEpic =
        epicFilter === "All epics" ||
        (epicFilter === "Client Portal" && /client|approval|portal/i.test(task.title)) ||
        (epicFilter === "Reliability" && /bug|blocked|fix|error|reliability/i.test(task.title)) ||
        (epicFilter === "Operations" && !/client|approval|portal|bug|blocked|fix|error|reliability/i.test(task.title));
      return matchesQuery && matchesAssignee && matchesPriority && matchesEpic;
    });
  }, [assigneeFilter, epicFilter, priorityFilter, query, tasks]);

  const boardStats = useMemo(() => {
    const total = filteredTasks.length;
    const done = filteredTasks.filter((task) => task.status === "Done").length;
    const points = filteredTasks.reduce((sum, task) => sum + (task.story_points || 0), 0);
    const overdue = filteredTasks.filter((task) => task.due_date && new Date(task.due_date) < new Date() && task.status !== "Done").length;
    return { total, done, points, overdue, progress: total ? Math.round((done / total) * 100) : 0 };
  }, [filteredTasks]);

  const assigneeIds = useMemo(() => {
    const ids = tasks.map((task) => task.assignee_user_id).filter((id): id is number => Boolean(id));
    return Array.from(new Set(ids)).slice(0, 6);
  }, [tasks]);

  // Handle drag end (DROP) - Main reordering logic
  const handleDragEnd = async (event: DragEndEvent) => {
    if (selectedProject?.can_manage_tasks === false) return;
    const { active, over } = event;
    setActiveId(null);

    if (!over) return;

    const activeTaskId = active.id as number;
    const overElement = over.id as string | number;

    // Determine target column and position
    let targetColumnId: number | null = null;
    let targetPosition: number = 0;

    // If dropping over another task
    if (typeof overElement === "number") {
      const overTask = tasks.find((t) => t.id === overElement);
      if (overTask) {
        targetColumnId = overTask.column_id || null;
        targetPosition = overTask.position || 0;
      }
    } else if (typeof overElement === "string" && overElement.startsWith("column-")) {
      // Dropping over a column
      targetColumnId = parseInt(overElement.replace("column-", ""));
      targetPosition = 0;
    }

    if (!targetColumnId || !board) return;

    try {
      // Send reorder request to backend
      await kanbanAPI.reorderTask(projectIdNum, {
        task_id: activeTaskId,
        column_id: targetColumnId,
        position: targetPosition,
      });

      // Update local state optimistically
      const task = tasks.find((t) => t.id === activeTaskId);
      if (task) {
        updateTask({
          ...task,
          column_id: targetColumnId,
          position: targetPosition,
        });
      }
    } catch (err: any) {
      setError("Failed to reorder task");
      console.error("Error reordering task:", err);
    }
  };

  if (!selectedProject && !loading && hasLoaded) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-gray-500">Project not found</p>
      </div>
    );
  }

  if (loading || !hasLoaded) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader className="animate-spin text-blue-600" size={32} />
      </div>
    );
  }

  if (!board) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-gray-500">Board not found</p>
      </div>
    );
  }

  const project = selectedProject;
  if (!project) return null;

  return (
    <div className="min-h-screen bg-[#f7f8fb]">
      <TaskViewPicker projectId={projectIdNum || undefined} />
      <div className="border-b bg-white">
        <div className="px-6 py-5">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                <span>Projects</span>
                <span>/</span>
                <span>{project.project_key}</span>
                <Badge variant="outline" className="rounded-md">Scrum board</Badge>
              </div>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">Board</h1>
              <p className="mt-1 text-sm text-muted-foreground">{project.name} sprint execution with realtime click-and-drag work movement.</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="h-9 rounded-md bg-emerald-100 px-3 text-emerald-800 hover:bg-emerald-100">
                {boardStats.progress}% complete
              </Badge>
              <Button variant="outline" size="sm"><Bolt className="h-4 w-4" />Automation</Button>
              <Button variant="outline" size="sm"><Clock3 className="h-4 w-4" />4 days remaining</Button>
              <Button size="sm">Complete sprint</Button>
              <Button variant="ghost" size="icon" className="h-9 w-9"><MoreHorizontal className="h-4 w-4" /></Button>
            </div>
          </div>

          <div className="mt-5 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <div className="flex flex-1 flex-wrap items-center gap-3">
              <div className="relative w-full sm:w-64">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search board" className="h-10 pl-9" />
              </div>
              <div className="flex -space-x-2">
                {assigneeIds.map((id, index) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setAssigneeFilter(assigneeFilter === id ? "all" : id)}
                    className={`flex h-9 w-9 items-center justify-center rounded-full border-2 border-white text-xs font-semibold text-white shadow-sm ${assigneeFilter === id ? "ring-2 ring-blue-500" : ""}`}
                    style={{ backgroundColor: ["#2563eb", "#16a34a", "#db2777", "#9333ea", "#ea580c", "#0891b2"][index % 6] }}
                    title={`Assignee ${id}`}
                  >
                    U{id}
                  </button>
                ))}
                <button type="button" onClick={() => setAssigneeFilter("all")} className="flex h-9 min-w-9 items-center justify-center rounded-full border-2 border-white bg-slate-100 px-2 text-xs font-semibold text-slate-600 shadow-sm">
                  +3
                </button>
              </div>
              <Button variant="outline" size="sm" onClick={() => navigate("/pms/workspaces")}><Users className="h-4 w-4" />Workspace & members</Button>
              <select value={epicFilter} onChange={(event) => setEpicFilter(event.target.value)} className="h-10 rounded-md border bg-background px-3 text-sm">
                <option>All epics</option>
                <option>Client Portal</option>
                <option>Reliability</option>
                <option>Operations</option>
              </select>
              <select value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value)} className="h-10 rounded-md border bg-background px-3 text-sm">
                <option>All priorities</option>
                <option>Low</option>
                <option>Medium</option>
                <option>High</option>
                <option>Urgent</option>
              </select>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" size="sm"><Sparkles className="h-4 w-4" />AI suggest work</Button>
              <Button variant="outline" size="sm"><Filter className="h-4 w-4" />Filter</Button>
              <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Group by</span>
              <button type="button" className="inline-flex h-10 items-center gap-2 rounded-md border bg-background px-3 text-sm font-medium" onClick={() => setGroupBy(groupBy === "Choices" ? "Assignee" : "Choices")}>
                {groupBy}<ChevronDown className="h-4 w-4" />
              </button>
              <Button variant="ghost" size="icon" className="h-9 w-9"><Settings className="h-4 w-4" /></Button>
            </div>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <SprintMetric label="Sprint scope" value={`${boardStats.total} work items`} />
            <SprintMetric label="Story points" value={`${boardStats.points} pts`} />
            <SprintMetric label="Done" value={`${boardStats.done} completed`} />
            <SprintMetric label="Needs attention" value={`${boardStats.overdue} overdue`} danger={boardStats.overdue > 0} />
          </div>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="bg-red-50 border-b border-red-200 px-6 py-4">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      {/* Kanban Board Container */}
      <div className="overflow-x-auto p-6">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <div className="flex min-h-[650px] gap-4">
            {board.columns?.map((column) => (
              <SortableContext
                key={column.id}
                items={
                  tasks
                    .filter((t) => filteredTasks.some((filtered) => filtered.id === t.id) && t.column_id === column.id)
                    .map((t) => t.id) || []
                }
                strategy={verticalListSortingStrategy}
              >
                <KanbanColumn
                  onChanged={()=>loadBoard(true)}
                  column={column}
                  tasks={filteredTasks.filter((t) => t.column_id === column.id)}
                  onAddTask={() => setShowCreateModal(true)}
                  readOnly={selectedProject?.can_manage_tasks === false}
                  onOpenTask={(task) => navigate(`/pms/projects/${projectIdNum}/tasks/${task.id}`)}
                />
              </SortableContext>
            ))}
          </div>

          {/* Drag overlay - shows what's being dragged */}
          <DragOverlay>
            {activeTask ? (
              <div className="min-w-72 rounded-lg border bg-white p-4 shadow-2xl ring-2 ring-blue-500">
                <p className="text-sm font-semibold text-slate-900">{activeTask.title}</p>
                <p className="mt-2 text-xs text-muted-foreground">{activeTask.task_key} is moving...</p>
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      </div>

      {/* Create Task Modal */}
      <CreateTaskModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        projectId={projectIdNum}
        onTaskCreated={(task, createAnother) => {
          addTask(task);
          if (!createAnother) setShowCreateModal(false);
        }}
      />
    </div>
  );
};

function SprintMetric({ label, value, danger = false }: { label: string; value: string; danger?: boolean }) {
  return (
    <div className="rounded-lg border bg-slate-50 px-3 py-2">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={`mt-1 text-sm font-semibold ${danger ? "text-red-700" : "text-slate-950"}`}>{value}</p>
    </div>
  );
}

export default KanbanBoard;

