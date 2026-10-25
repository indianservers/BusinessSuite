import RecordActions from "./RecordActions";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  CalendarDays,
  Check,
  CheckSquare,
  ChevronsDown,
  ChevronsUp,
  CircleAlert,
  Equal,
  GitBranch,
  GripVertical,
  Link2,
  MessageSquare,
  Paperclip,
  Square,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn, formatDate } from "@/lib/utils";
import type { PMSTask } from "../types";

const priorityClass: Record<string, string> = {
  Low: "bg-emerald-50 text-emerald-700 border-emerald-200",
  Medium: "bg-amber-50 text-amber-700 border-amber-200",
  High: "bg-orange-50 text-orange-700 border-orange-200",
  Urgent: "bg-red-50 text-red-700 border-red-200",
};

const priorityIcon = {
  Low: ChevronsDown,
  Medium: Equal,
  High: ChevronsUp,
  Urgent: CircleAlert,
} as const;

export default function TaskCard({ task, onOpen, canEdit=false, onChanged }: { task: PMSTask; onOpen?: (task: PMSTask) => void; canEdit?: boolean; onChanged?: () => Promise<void> }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: task.id, disabled: !canEdit });
  const isOverdue = task.due_date && new Date(task.due_date) < new Date() && task.status !== "Done";
  const PriorityIcon = priorityIcon[task.priority] || Equal;
  const issueType = task.is_blocking || /bug|error|fix|blocked/i.test(task.title) ? "Bug" : task.parent_task_id ? "Sub-task" : task.story_points && task.story_points > 5 ? "Story" : "Task";
  const typeClass =
    issueType === "Bug"
      ? "bg-red-500"
      : issueType === "Story"
        ? "bg-emerald-500"
        : issueType === "Sub-task"
          ? "bg-violet-500"
          : "bg-blue-500";
  const comments = 0;
  const attachments = task.attachment_count || 0;
  const subtaskTotal = task.subtask_count || 0;
  const subtaskDone = task.completed_subtask_count || 0;
  const avatarColor = ["#2563eb", "#16a34a", "#db2777", "#9333ea", "#ea580c", "#0891b2"][(task.assignee_user_id || task.id) % 6];
  const tagNames = (task.tags || []).map((tag) => typeof tag === "string" ? tag : tag.name).filter(Boolean);

  return (
    <RecordActions record={{...task,key:task.task_key}} canEdit={canEdit} preview={!isDragging} onOpen={onOpen ? ()=>onOpen(task) : undefined} onChanged={onChanged}>{menu=><article tabIndex={0}
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn(
        "group rounded-md border bg-white p-3 shadow-sm transition hover:border-blue-400 hover:shadow-md",
        isDragging && "opacity-50 ring-2 ring-blue-500"
      )}
    >
      <div className="flex items-start gap-2">
        <button
          type="button"
          aria-label="Drag task"
          disabled={!canEdit}
          className="mt-0.5 rounded p-1 text-muted-foreground hover:bg-muted"
          {...attributes}
          {...listeners}
        >
          <GripVertical className="h-4 w-4" />
        </button>
        <button type="button" onClick={() => onOpen?.(task)} className="min-w-0 flex-1 text-left">
          <h3 className="mt-2 line-clamp-2 text-sm font-semibold leading-5 text-foreground">{task.title}</h3>
          {task.description ? (
            <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">{task.description}</p>
          ) : null}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className={cn("inline-flex h-4 w-4 items-center justify-center rounded-sm text-white", typeClass)} title={issueType}>
              {issueType === "Bug" ? <CircleAlert className="h-3 w-3" /> : issueType === "Sub-task" ? <Link2 className="h-3 w-3" /> : <Square className="h-2.5 w-2.5 fill-current" />}
            </span>
            <span className="text-xs font-semibold text-slate-500">{task.task_key}</span>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">{task.story_points ?? 0} pts</span>
            <Badge variant="outline" className={cn("h-5 rounded px-1.5 text-[11px]", priorityClass[task.priority])}>
              <PriorityIcon className="mr-1 h-3 w-3" />
              {task.priority}
            </Badge>
          </div>
          {tagNames.length ? (
            <div className="mt-2 flex flex-wrap gap-1">
              {tagNames.slice(0, 3).map((tag) => <Badge key={tag} variant="outline" className="h-5 rounded px-1.5 text-[11px]">{tag}</Badge>)}
              {tagNames.length > 3 ? <span className="text-[11px] text-muted-foreground">+{tagNames.length - 3}</span> : null}
            </div>
          ) : null}
        </button>{menu}
      </div>

      <div className="mt-3 flex items-center justify-between gap-2 border-t pt-3 text-xs text-muted-foreground">
        <div className={cn("inline-flex items-center gap-1", isOverdue && "font-medium text-red-600")}>
          <CalendarDays className="h-3.5 w-3.5" />
          {task.due_date ? formatDate(task.due_date) : "No date"}
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1"><MessageSquare className="h-3.5 w-3.5" />{comments}</span>
          <span className="inline-flex items-center gap-1"><Paperclip className="h-3.5 w-3.5" />{attachments}</span>
          {subtaskTotal ? <span className="inline-flex items-center gap-1"><CheckSquare className="h-3.5 w-3.5" />{subtaskDone}/{subtaskTotal}</span> : null}
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {task.status === "Done" ? <Check className="h-4 w-4 text-emerald-600" /> : <GitBranch className="h-4 w-4 text-slate-400" />}
          <span>{task.is_client_visible ? "Client visible" : "Internal"}</span>
        </div>
        <div
          className="flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold text-white shadow-sm"
          style={{ backgroundColor: avatarColor }}
          title={`Assignee ${task.assignee_user_id || "unassigned"}`}
        >
          {task.assignee_user_id ? `U${task.assignee_user_id}` : "?"}
        </div>
      </div>
    </article>}</RecordActions>
  );
}

