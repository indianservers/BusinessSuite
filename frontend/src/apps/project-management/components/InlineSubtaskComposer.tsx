import { useRef, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { tasksAPI } from "../services/api";
import type { PMSTask, TaskPriority } from "../types";
import { taskAssignees, workspaceError } from "../pages/workspaceTypes";

export default function InlineSubtaskComposer({ parent, onCreated, onCancel }: {
  parent: PMSTask; onCreated: (child: PMSTask) => void; onCancel: () => void;
}) {
  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState<TaskPriority>(parent.priority || "Medium");
  const [due, setDue] = useState("");
  const [inherit, setInherit] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const lock = useRef(false);
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || lock.current) return;
    lock.current = true; setBusy(true); setError("");
    try {
      const child = await tasksAPI.createSubtask(parent.id, { title: title.trim(), status: "To Do", priority,
        due_date: due || undefined, assignee_user_ids: inherit ? taskAssignees(parent) : [] });
      onCreated(child);
    } catch (error) { setError(workspaceError(error)); }
    finally { lock.current = false; setBusy(false); }
  }
  return <form aria-label={`Add subtask to ${parent.title}`} onSubmit={event => void save(event)} onClick={event => event.stopPropagation()} onKeyDown={event => {
    event.stopPropagation();
    if (event.key === "Escape" && !busy) { event.preventDefault(); onCancel(); }
  }} className="space-y-3 rounded-md border border-primary/20 bg-primary/5 p-3">
    <p className="text-xs text-muted-foreground">Subtask of {parent.task_key || parent.title} · starts in To Do</p>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    <fieldset disabled={busy} className="grid gap-2 sm:grid-cols-2">
      <Input autoFocus required maxLength={220} aria-label="Inline subtask title" placeholder="Subtask name" value={title} onChange={event => setTitle(event.target.value)} className="sm:col-span-2" />
      <label className="text-xs">Priority<select aria-label="Inline subtask priority" className="mt-1 h-10 w-full rounded border bg-background px-2 text-sm" value={priority} onChange={event => setPriority(event.target.value as TaskPriority)}>{["Urgent", "High", "Medium", "Low"].map(value => <option key={value}>{value}</option>)}</select></label>
      <label className="text-xs">Due date<Input aria-label="Inline subtask due date" type="date" value={due} onChange={event => setDue(event.target.value)} className="mt-1" /></label>
      <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" checked={inherit} onChange={event => setInherit(event.target.checked)} />Inherit parent assignees</label>
      <div className="flex flex-wrap gap-2 sm:col-span-2"><Button size="sm" disabled={busy || !title.trim()}>{busy ? "Saving…" : "Save subtask"}</Button><Button type="button" size="sm" variant="outline" disabled={busy} onClick={onCancel}>Cancel</Button></div>
    </fieldset>
  </form>;
}
