import * as Dialog from "@radix-ui/react-dialog";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { tagsAPI, tasksAPI, pmsUsersAPI } from "../services/api";
import type { PMSTag, PMSTask, TaskPriority, TaskStatus, PMSMentionUser } from "../types";
import { beginProgress } from "@/components/app/AsyncProgress";
import AssigneePicker from "./AssigneePicker";

const statuses: TaskStatus[] = ["Backlog", "To Do", "In Progress", "In Review", "Blocked", "Done"];
const priorities: TaskPriority[] = ["Low", "Medium", "High", "Urgent"];

export default function CreateTaskModal({
  isOpen,
  onClose,
  projectId,
  onTaskCreated,
  workspacePeople,
  projects,
  initialWorkType = "Task",
}: {
  isOpen: boolean;
  onClose: () => void;
  projectId: number;
  onTaskCreated: (task: PMSTask) => void;
  workspacePeople?: PMSMentionUser[];
  projects?: { id: number; name: string }[];
  initialWorkType?: "Task" | "Story" | "Bug";
}) {
  const [selectedProjectId, setSelectedProjectId] = useState(projectId);
  useEffect(() => { setSelectedProjectId(projectId); }, [projectId]);
  const titleRef = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState("");
  const [workType, setWorkType] = useState(initialWorkType);
  useEffect(() => { setWorkType(initialWorkType); }, [initialWorkType]);
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState<TaskStatus>("To Do");
  const [priority, setPriority] = useState<TaskPriority>("Medium");
  const [dueDate, setDueDate] = useState("");
  const [startDate, setStartDate] = useState("");
  const [assignees, setAssignees] = useState<number[]>([]);
  const [people, setPeople] = useState<PMSMentionUser[]>([]);
  const [storyPoints, setStoryPoints] = useState("");
  const [availableTags, setAvailableTags] = useState<PMSTag[]>([]);
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);
  const [newTagName, setNewTagName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    tagsAPI.list().then(setAvailableTags).catch(() => setAvailableTags([]));
    if (workspacePeople) { setPeople(workspacePeople); return; }
    pmsUsersAPI.search({ projectId: selectedProjectId, limit: 25 }).then(setPeople).catch(() => setError("Unable to load collaborators. Close and reopen this form to retry."));
  }, [isOpen, selectedProjectId, workspacePeople]);

  const selectedTags = useMemo(
    () => availableTags.filter((tag) => selectedTagIds.includes(tag.id)),
    [availableTags, selectedTagIds]
  );

  if (!isOpen) return null;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim()) {
      setError("Task title is required.");
      return;
    }
    if (startDate && dueDate && startDate > dueDate) {
      setError("Start date cannot be after due date.");
      return;
    }
    const parsedStoryPoints = storyPoints === "" ? undefined : Number(storyPoints);
    if (parsedStoryPoints !== undefined && (!Number.isInteger(parsedStoryPoints) || parsedStoryPoints < 0)) {
      setError("Story points must be a non-negative whole number.");
      return;
    }
    if (!selectedProjectId) { setError("Choose a project first."); return; }
    const finish = beginProgress("Creating task");
    try {
      setSubmitting(true);
      setError(null);
      const key = title
        .trim()
        .split(/\s+/)
        .map((word) => word[0])
        .join("")
        .slice(0, 3)
        .toUpperCase();
      const task = await tasksAPI.create(selectedProjectId, {
        work_type: workType,
        title,
        description: description || undefined,
        task_key: `${key || "TSK"}-${Date.now().toString().slice(-4)}`,
        status,
        priority,
        due_date: dueDate || undefined,
        start_date: startDate || undefined,
        assignee_user_ids: assignees,
        story_points: parsedStoryPoints,
      });
      const attachedTags: PMSTag[] = [];
      for (const tagId of selectedTagIds) {
        attachedTags.push(await tasksAPI.addTagById(task.id, tagId));
      }
      if (newTagName.trim()) {
        const tag = await tagsAPI.create({ name: newTagName.trim() });
        attachedTags.push(await tasksAPI.addTagById(task.id, tag.id));
      }
      onTaskCreated({ ...task, tags: attachedTags });
      finish();
      setTitle("");
      setDescription("");
      setDueDate("");
      setStartDate("");
      setAssignees([]);
      setStoryPoints("");
      setSelectedTagIds([]);
      setNewTagName("");
    } catch (err: any) {
      finish(false);
      setError(err?.response?.data?.detail || err?.message || "Failed to create task.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog.Root open={isOpen} onOpenChange={open => { if (!open && !submitting) onClose(); }}><Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" /><Dialog.Content asChild onOpenAutoFocus={event => { event.preventDefault(); titleRef.current?.focus(); }} onEscapeKeyDown={event => { if (submitting) event.preventDefault(); }} onInteractOutside={event => event.preventDefault()}>
      <form onSubmit={submit} className="fixed left-1/2 top-1/2 z-50 max-h-[92dvh] w-[calc(100%_-_2rem)] -translate-x-1/2 -translate-y-1/2 max-w-2xl overflow-y-auto rounded-lg border bg-background shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <Dialog.Title className="text-lg font-semibold">Create task</Dialog.Title><Dialog.Description className="sr-only">Create a task in the selected project. Escape closes this form and keeps your draft.</Dialog.Description>
          <Button type="button" aria-label="Close task form" disabled={submitting} variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        <fieldset disabled={submitting} className="space-y-4 p-5">
          <label className="block">Work item type<select aria-label="Work item type" className="mt-1 h-11 w-full rounded-md border bg-background px-3" value={workType} onChange={e => setWorkType(e.target.value as typeof workType)}>{["Task", "Story", "Bug"].map(type => <option key={type}>{type}</option>)}</select></label>
          {projects && <div className="space-y-2"><Label htmlFor="task-project">Project</Label><select id="task-project" required value={selectedProjectId || ""} onChange={e => setSelectedProjectId(Number(e.target.value))} className="h-10 w-full rounded-md border bg-background px-3 text-sm"><option value="" disabled>Choose project</option>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select></div>}
          {error ? <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div> : null}
          <div className="space-y-2">
            <Label htmlFor="task-title">Title</Label>
            <Input ref={titleRef} id="task-title" value={title} onChange={(event) => setTitle(event.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="task-description">Description</Label>
            <textarea
              id="task-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              className="min-h-24 w-full rounded-md border bg-background px-3 py-2 text-sm"
            />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label>Start date<Input aria-label="Task start date" type="date" value={startDate} onChange={e => setStartDate(e.target.value)} /></label>
            <div><Label>Assignees</Label><AssigneePicker people={people} value={assignees} onChange={setAssignees} /></div>
          </div>
          <div className="grid gap-4 sm:grid-cols-4">
            <div className="space-y-2">
              <Label htmlFor="task-status">Status</Label>
              <select id="task-status" value={status} onChange={(event) => setStatus(event.target.value as TaskStatus)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                {statuses.map((item) => <option key={item}>{item}</option>)}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="task-priority">Priority</Label>
              <select id="task-priority" value={priority} onChange={(event) => setPriority(event.target.value as TaskPriority)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                {priorities.map((item) => <option key={item}>{item}</option>)}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="task-due">Due date</Label>
              <Input id="task-due" type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="task-story-points">Story points</Label>
              <Input id="task-story-points" type="number" min="0" step="1" value={storyPoints} onChange={(event) => setStoryPoints(event.target.value)} />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="task-tags">Tags</Label>
            <div className="flex flex-wrap gap-2">
              {selectedTags.map((tag) => (
                <Badge key={tag.id} variant="outline" className="gap-1">
                  {tag.name}
                  <button type="button" onClick={() => setSelectedTagIds((ids) => ids.filter((id) => id !== tag.id))} aria-label={`Remove ${tag.name}`}>
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
            <div className="grid gap-2 sm:grid-cols-[1fr_1fr]">
              <select
                id="task-tags"
                value=""
                onChange={(event) => {
                  const value = Number(event.target.value);
                  if (value) setSelectedTagIds((ids) => ids.includes(value) ? ids : [...ids, value]);
                }}
                className="h-10 rounded-md border bg-background px-3 text-sm"
              >
                <option value="">Select existing tag</option>
                {availableTags.filter((tag) => !selectedTagIds.includes(tag.id)).map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}
              </select>
              <Input value={newTagName} onChange={(event) => setNewTagName(event.target.value)} placeholder="Create new tag on save" />
            </div>
          </div>
        </fieldset>
        <div className="flex justify-end gap-2 border-t px-5 py-4">
          <Button type="button" variant="outline" disabled={submitting} onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={submitting}>{submitting ? "Creating..." : "Create task"}</Button>
        </div>
      </form>
    </Dialog.Content></Dialog.Portal></Dialog.Root>
  );
}

