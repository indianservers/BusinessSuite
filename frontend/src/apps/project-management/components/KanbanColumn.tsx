import { useDroppable } from "@dnd-kit/core";
import { AlertTriangle, ChevronsRight, MoreHorizontal, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { PMSBoardColumn, PMSTask } from "../types";
import TaskCard from "./TaskCard";

const columnAccent: Record<string, string> = {
  BACKLOG: "bg-slate-600",
  TODO: "bg-blue-600",
  IN_PROGRESS: "bg-amber-500",
  IN_REVIEW: "bg-violet-600",
  DONE: "bg-emerald-600",
};

export default function KanbanColumn({
  column,
  tasks,
  onAddTask,
  onOpenTask,
  readOnly = false,
  onChanged,
}: {
  column: PMSBoardColumn;
  tasks: PMSTask[];
  onAddTask: () => void;
  onOpenTask?: (task: PMSTask) => void;
  readOnly?: boolean;
  onChanged?: () => Promise<void>;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: `column-${column.id}` });
  const isAtLimit = Boolean(column.wip_limit && tasks.length >= column.wip_limit);
  const storyPoints = tasks.reduce((sum, task) => sum + (task.story_points || 0), 0);
  const blockedCount = tasks.filter((task) => task.is_blocking || task.status === "Blocked").length;
  const accent = columnAccent[column.status_key] || "bg-slate-600";

  return (
    <section
      ref={setNodeRef}
      className={cn(
        "flex w-[300px] shrink-0 flex-col rounded-lg border bg-[#f1f2f6] shadow-sm transition",
        isOver && "ring-2 ring-blue-500 ring-offset-2"
      )}
    >
      <header className="border-b px-3 py-3">
        <div className={cn("mb-3 h-1 rounded-full", accent)} />
        <div className="min-w-0">
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <h2 className="truncate text-xs font-bold uppercase tracking-wide text-slate-700">{column.name}</h2>
              <span className="rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-slate-600 shadow-sm">{tasks.length}</span>
            </div>
            <div className="flex items-center gap-1">
              <Button type="button" aria-label={`Add task to ${column.name}`} disabled={readOnly} size="icon" variant="ghost" className="h-7 w-7" onClick={onAddTask}>
                <Plus className="h-4 w-4" />
              </Button>
              <Button type="button" size="icon" variant="ghost" className="h-7 w-7">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <div className="mt-3 flex items-center justify-between gap-2 text-xs text-muted-foreground">
            <span>{storyPoints} pts</span>
            {column.wip_limit ? (
              <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5", isAtLimit ? "bg-red-100 text-red-700" : "bg-white text-slate-600")}>
                {isAtLimit ? <AlertTriangle className="h-3 w-3" /> : null}
                WIP {tasks.length}/{column.wip_limit}
              </span>
            ) : (
              <span className="rounded-full bg-white px-2 py-0.5 text-slate-600">No WIP limit</span>
            )}
          </div>
          {blockedCount ? (
            <div className="mt-2 flex items-center gap-1 rounded-md bg-red-50 px-2 py-1 text-xs font-medium text-red-700">
              <ChevronsRight className="h-3.5 w-3.5" />
              {blockedCount} blocker{blockedCount === 1 ? "" : "s"} in this lane
            </div>
          ) : null}
        </div>
      </header>
      <div className="flex-1 space-y-3 overflow-y-auto p-3">
        {tasks.length ? (
          tasks.map((task) => <TaskCard key={task.id} task={task} onOpen={onOpenTask} canEdit={!readOnly} onChanged={onChanged} />)
        ) : (
          <button
            type="button"
            disabled={readOnly}
            onClick={onAddTask}
            className="flex h-28 w-full items-center justify-center rounded-lg border border-dashed bg-white/70 text-sm text-muted-foreground hover:border-primary/40 hover:text-foreground"
          >
            {readOnly ? "No tasks" : "Add a task"}
          </button>
        )}
      </div>
    </section>
  );
}

