import * as Dialog from "@radix-ui/react-dialog";
import { FormEvent, useEffect, useRef, useState } from "react";
import { X, FilePlus2, ClipboardList, Bug, Lightbulb, BarChart3, Layers3, CalendarDays, Link2, Paperclip, Repeat2, ChevronRight, Sparkles, Bold, Italic, Underline, List, ListOrdered, Code2, Eye, Folder, Type, Users, Flag, Circle, Tag, FileText, Image as ImageIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { tagsAPI, tasksAPI, pmsUsersAPI, sprintsAPI, filesAPI, projectsAPI } from "../services/api";
import type { PMSTag, PMSTask, TaskPriority, TaskStatus, PMSMentionUser, PMSSprint } from "../types";
import { beginProgress } from "@/components/app/AsyncProgress";
import { api } from "@/services/api";
import AssigneePicker from "./AssigneePicker";
import "./CreateTaskModal.css";

const statuses: TaskStatus[] = ["Backlog", "To Do", "In Progress", "In Review", "Blocked", "Done"];
const priorities: TaskPriority[] = ["Low", "Medium", "High", "Urgent"];
const typeIcons: Record<string, typeof ClipboardList> = { Task: ClipboardList, Bug, Feature: Lightbulb, Improvement: BarChart3, Epic: Layers3 };

export default function CreateTaskModal({ isOpen, onClose, projectId, onTaskCreated, workspacePeople, projects, initialDueDate = "", initialWorkType = "Task" }: {
  isOpen: boolean; onClose: () => void; projectId: number;
  onTaskCreated: (task: PMSTask, createAnother?: boolean) => void;
  workspacePeople?: PMSMentionUser[]; projects?: { id: number; name: string }[];
  initialDueDate?: string;
  initialWorkType?: "Task" | "Story" | "Bug";
}) {
  const titleRef = useRef<HTMLInputElement>(null);
  const descriptionRef = useRef<HTMLTextAreaElement>(null);
  const [selectedProjectId, setSelectedProjectId] = useState(projectId);
  const [projectOptions, setProjectOptions] = useState(projects || []);
  const [title, setTitle] = useState("");
  const [workType, setWorkType] = useState<string>(initialWorkType);
  const [workTypes, setWorkTypes] = useState(["Task", "Bug", "Feature", "Improvement", "Epic"]);
  const [description, setDescription] = useState("");
  const [preview, setPreview] = useState(false);
  const [status, setStatus] = useState<TaskStatus>("To Do");
  const [priority, setPriority] = useState<TaskPriority>("Medium");
  const [dueDate, setDueDate] = useState("");
  useEffect(() => { if (isOpen) setDueDate(initialDueDate); }, [isOpen, initialDueDate]);
  const [startDate, setStartDate] = useState("");
  const [assignees, setAssignees] = useState<number[]>([]);
  const [people, setPeople] = useState<PMSMentionUser[]>([]);
  const [storyPoints, setStoryPoints] = useState("");
  const [availableTags, setAvailableTags] = useState<PMSTag[]>([]);
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);
  const [newTagName, setNewTagName] = useState("");
  const [sprints, setSprints] = useState<PMSSprint[]>([]);
  const [sprintId, setSprintId] = useState("");
  const [dependencyId, setDependencyId] = useState("");
  const [taskOptions, setTaskOptions] = useState<PMSTask[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [recurrence, setRecurrence] = useState("");
  const [recurrenceUntil, setRecurrenceUntil] = useState("");
  const [createAnother, setCreateAnother] = useState(false);
  const [quickOption, setQuickOption] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [optionsError, setOptionsError] = useState("");
  const created = useRef<PMSTask | null>(null);
  const completed = useRef(new Set<string>());

  useEffect(() => { setSelectedProjectId(projectId); }, [projectId]);
  useEffect(() => { setWorkType(initialWorkType); }, [initialWorkType]);
  useEffect(() => {
    if (!isOpen) return;
    let active = true;
    if (projects) setProjectOptions(projects);
    else projectsAPI.list().then(data => { if (active) setProjectOptions(data); }).catch(() => undefined);
    api.get("/project-management/task-types").then(({ data }) => {
      if (active && Array.isArray(data.types)) setWorkTypes([...new Set(["Task", "Bug", "Feature", "Improvement", "Epic", ...data.types.filter((t: { archived: boolean; name: string }) => !t.archived && t.name !== "Sub-task").map((t: { name: string }) => t.name)])] as string[]);
    }).catch(() => undefined);
    tagsAPI.list().then(data => { if (active) setAvailableTags(data); }).catch(() => undefined);
    return () => { active = false; };
  }, [isOpen, projects]);
  useEffect(() => {
    if (!isOpen || !selectedProjectId) return;
    let active = true; setSprintId(""); setDependencyId(""); setOptionsError(""); setSprints([]); setTaskOptions([]);
    Promise.allSettled([sprintsAPI.list(selectedProjectId), tasksAPI.list(selectedProjectId), workspacePeople ? Promise.resolve(workspacePeople) : pmsUsersAPI.search({ projectId: selectedProjectId, limit: 100 })])
      .then(([nextSprints, tasks, collaborators]) => { if (!active) return;
        if (nextSprints.status === "fulfilled") setSprints(nextSprints.value);
        if (tasks.status === "fulfilled") setTaskOptions(tasks.value);
        if (collaborators.status === "fulfilled") setPeople(collaborators.value);
        if ([nextSprints, tasks, collaborators].some(result => result.status === "rejected")) setOptionsError("Some project options could not load. Close and reopen the form to retry.");
      });
    return () => { active = false; };
  }, [isOpen, selectedProjectId, workspacePeople]);

  function format(before: string, after = before) {
    const editor = descriptionRef.current; if (!editor) return;
    const start = editor.selectionStart, end = editor.selectionEnd;
    setDescription(description.slice(0, start) + before + description.slice(start, end) + after + description.slice(end));
    requestAnimationFrame(() => { editor.focus(); editor.setSelectionRange(start + before.length, end + before.length); });
  }
  function reset() {
    setTitle(""); setDescription(""); setDueDate(""); setStartDate(""); setAssignees([]); setStoryPoints(""); setSelectedTagIds([]); setNewTagName(""); setFiles([]); setDependencyId(""); setRecurrence(""); setRecurrenceUntil(""); setPreview(false); created.current = null; completed.current.clear();
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) { setError("Task title is required."); titleRef.current?.focus(); return; }
    if (startDate && dueDate && startDate > dueDate) { setError("Start date cannot be after due date."); return; }
    if (recurrence && !dueDate) { setError("Choose a due date for the first occurrence."); return; }
    if (recurrenceUntil && dueDate && recurrenceUntil < dueDate) { setError("Recurrence must end on or after the due date."); return; }
    if (storyPoints && (!Number.isInteger(Number(storyPoints)) || Number(storyPoints) < 0)) { setError("Story points must be a non-negative whole number."); return; }
    if (!selectedProjectId) { setError("Choose a project first."); return; }
    const finish = beginProgress("Creating task"); setSubmitting(true); setError(null);
    try {
      if (!created.current) created.current = await tasksAPI.create(selectedProjectId, {
        work_type: workType, title: title.trim(), description: description || undefined,
        task_key: `TSK-${Date.now().toString().slice(-6)}`, status, priority,
        start_date: startDate || undefined, due_date: dueDate || undefined, assignee_user_ids: assignees,
        story_points: storyPoints === "" ? undefined : Number(storyPoints), sprint_id: sprintId ? Number(sprintId) : undefined,
        recurrence_rule: recurrence || undefined, recurrence_interval: 1, recurrence_until: recurrenceUntil || undefined,
      });
      const task = created.current;
      for (const tagId of selectedTagIds) if (!completed.current.has(`tag-${tagId}`)) { await tasksAPI.addTagById(task.id, tagId); completed.current.add(`tag-${tagId}`); }
      if (newTagName.trim() && !completed.current.has("new-tag")) {
        const tag = availableTags.find(t => t.name.toLowerCase() === newTagName.trim().toLowerCase()) || await tagsAPI.create({ name: newTagName.trim() });
        setAvailableTags(current => current.some(t => t.id === tag.id) ? current : [...current, tag]);
        await tasksAPI.addTagById(task.id, tag.id); completed.current.add("new-tag");
      }
      if (dependencyId && !completed.current.has("dependency")) { await tasksAPI.addDependency(task.id, Number(dependencyId)); completed.current.add("dependency"); }
      for (let i = 0; i < files.length; i++) if (!completed.current.has(`file-${i}`)) { await filesAPI.uploadToTask(task.id, files[i]); completed.current.add(`file-${i}`); }
      const saved = await tasksAPI.get(task.id);
      finish(); onTaskCreated(saved, createAnother); reset();
      if (!createAnother) onClose(); else requestAnimationFrame(() => titleRef.current?.focus());
    } catch (err: any) {
      finish(false);
      setError(`${created.current ? "Task saved. Some extras failed; retry to finish without creating a duplicate. " : ""}${typeof err?.response?.data?.detail === "string" ? err.response.data.detail : err?.message || "Unable to save task."}`);
    } finally { setSubmitting(false); }
  }
  if (!isOpen) return null;
  const locked = submitting || !!created.current;
  return <Dialog.Root open={isOpen} onOpenChange={open => { if (!open && !submitting) onClose(); }}><Dialog.Portal>
    <Dialog.Overlay className="task-compose-overlay" />
    <Dialog.Content asChild onOpenAutoFocus={event => { event.preventDefault(); titleRef.current?.focus(); }} onEscapeKeyDown={event => { if (submitting) event.preventDefault(); }} onInteractOutside={event => event.preventDefault()}>
      <form onSubmit={submit} className="task-compose">
        <header className="task-compose-header"><span className="compose-heading-icon"><FilePlus2 /></span><div><Dialog.Title>Create New Task</Dialog.Title><Dialog.Description>Add a new task to keep your project on track</Dialog.Description></div><button type="button" aria-label="Close task form" disabled={submitting} onClick={onClose}><X /></button></header>
        <div className="task-compose-scroll">
          {error && <div role="alert" className="compose-error">{error}</div>}
          {optionsError && <div role="status" className="compose-error">{optionsError}</div>}
          <fieldset disabled={locked} className="task-compose-grid">
            <div className="task-compose-fields">
              <section className="compose-type"><label>Work item type</label><div role="group" aria-label="Work item type">{workTypes.map(type => { const Icon = typeIcons[type] || ClipboardList; return <button key={type} type="button" aria-pressed={workType === type} className={workType === type ? "selected" : ""} onClick={() => setWorkType(type)}><Icon />{type}{workType === type && <span className="type-check">✓</span>}</button>; })}</div></section>
              <div className="compose-pair">
                <div className="compose-field"><Folder /><div><label htmlFor="task-project">Project</label><select id="task-project" required value={selectedProjectId || ""} onChange={e => { setSelectedProjectId(Number(e.target.value)); setAssignees([]); }}><option value="" disabled>Choose project</option>{!projectOptions.some(p => p.id === selectedProjectId) && selectedProjectId > 0 && <option value={selectedProjectId}>Current project</option>}{projectOptions.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></div></div>
                <div className="compose-field"><Type /><div><label htmlFor="task-title">Title <span className="required">*</span></label><Input ref={titleRef} id="task-title" required maxLength={500} placeholder="What needs to be done?" value={title} onChange={e => setTitle(e.target.value)} /></div></div>
              </div>
              <div className="compose-field compose-description"><FileText /><div><label htmlFor="task-description">Description</label><div className="compose-editor"><div className="compose-toolbar"><select aria-label="Text style" onChange={e => { if (e.target.value) format(e.target.value, ""); e.target.value = ""; }}><option value="">Normal</option><option value="# ">Heading 1</option><option value="## ">Heading 2</option><option value="> ">Quote</option></select>{[{Icon:Bold,label:"Bold",before:"**"},{Icon:Italic,label:"Italic",before:"*"},{Icon:Underline,label:"Underline",before:"<u>",after:"</u>"},{Icon:List,label:"Bulleted list",before:"\n- ",after:""},{Icon:ListOrdered,label:"Numbered list",before:"\n1. ",after:""},{Icon:Link2,label:"Insert link",before:"[",after:"](https://)"},{Icon:Code2,label:"Code",before:"`"}].map(({Icon,label,before,after}) => <button key={label} type="button" aria-label={label} title={label} onClick={() => { setPreview(false); format(before, after); }}><Icon /></button>)}<button type="button" aria-label="Attach an image" title="Attach an image" onClick={() => setQuickOption("files")}><ImageIcon /></button><button type="button" className="preview-button" aria-pressed={preview} onClick={() => setPreview(!preview)}><Eye />{preview ? "Edit" : "Preview"}</button></div>{preview ? <div className="compose-preview"><DescriptionPreview text={description} /></div> : <textarea ref={descriptionRef} id="task-description" placeholder="Add details, context, or acceptance criteria…" value={description} onChange={e => setDescription(e.target.value)} />}</div></div></div>
              <div className="compose-pair">
                <div className="compose-field"><CalendarDays /><div><label htmlFor="task-start">Start date</label><Input id="task-start" type="date" value={startDate} onChange={e => setStartDate(e.target.value)} /></div></div>
                <div className="compose-field"><CalendarDays /><div><label htmlFor="task-due">Due date</label><Input id="task-due" type="date" min={startDate || undefined} value={dueDate} onChange={e => setDueDate(e.target.value)} /></div></div>
                <div className="compose-field"><Users /><div><label>Assignees</label><AssigneePicker people={people} value={assignees} onChange={setAssignees} /></div></div>
                <div className="compose-field"><Flag /><div><label>Priority</label><div className="compose-priorities" role="group" aria-label="Priority">{priorities.map(p => <button key={p} type="button" className={`priority-${p.toLowerCase()} ${priority === p ? "selected" : ""}`} aria-pressed={priority === p} onClick={() => setPriority(p)}><span />{p}</button>)}</div></div></div>
                <div className="compose-field"><Circle /><div><label htmlFor="task-status">Status</label><select id="task-status" value={status} onChange={e => setStatus(e.target.value as TaskStatus)}>{statuses.map(s => <option key={s}>{s}</option>)}</select></div></div>
                <div className="compose-field"><Tag /><div><label htmlFor="task-tags">Tags</label><select id="task-tags" value="" onChange={e => { const id = Number(e.target.value); if (id) setSelectedTagIds(ids => [...ids, id]); }}><option value="">Select existing tag or create new</option>{availableTags.filter(t => !selectedTagIds.includes(t.id)).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select><div className="compose-tags">{availableTags.filter(t => selectedTagIds.includes(t.id)).map(t => <button type="button" key={t.id} onClick={() => setSelectedTagIds(ids => ids.filter(id => id !== t.id))}>{t.name}<X /></button>)}</div><Input aria-label="New tag name" placeholder="New tag name (optional)" value={newTagName} onChange={e => setNewTagName(e.target.value)} /></div></div>
              </div>
              <details className="compose-advanced"><summary>More options</summary><label htmlFor="task-story-points">Story points</label><Input id="task-story-points" type="number" min="0" step="1" value={storyPoints} onChange={e => setStoryPoints(e.target.value)} /></details>
            </div>
            <aside className="task-compose-aside"><div className="compose-illustration"><img src="/images/karya-task-clipboard.webp" alt="" /><h3>Create and assign a task</h3><p>Keep your team aligned and<br />move work forward.</p></div><h3 className="quick-title">Quick options</h3>
              {[{key:"sprint",Icon:CalendarDays,title:"Add to sprint",copy:sprintId ? sprints.find(s => s.id === Number(sprintId))?.name : "Assign to a sprint"},{key:"dependency",Icon:Link2,title:"Link to another item",copy:dependencyId ? "Dependency selected" : "Create a dependency"},{key:"files",Icon:Paperclip,title:"Attach files",copy:files.length ? `${files.length} file(s) selected` : "Add documents, screenshots"},{key:"recurrence",Icon:Repeat2,title:"Set as recurring",copy:recurrence || "Create a repeating task"}].map(({key,Icon,title: optionTitle,copy}) => <div key={key} className="compose-quick"><button type="button" aria-expanded={quickOption === key} onClick={() => setQuickOption(quickOption === key ? "" : key)}><span><Icon /></span><div><strong>{optionTitle}</strong><small>{copy}</small></div><ChevronRight /></button>{quickOption === key && <div className="quick-content">{key === "sprint" && <select aria-label="Sprint" value={sprintId} onChange={e => setSprintId(e.target.value)}><option value="">No sprint</option>{sprints.filter(s => s.status !== "Completed" && s.status !== "Cancelled").map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>}{key === "dependency" && <><p>This task waits for:</p><select aria-label="Depends on task" value={dependencyId} onChange={e => setDependencyId(e.target.value)}><option value="">No dependency</option>{taskOptions.map(t => <option key={t.id} value={t.id}>{t.title}</option>)}</select></>}{key === "files" && <><input aria-label="Task attachments" type="file" multiple onChange={e => { const picked = Array.from(e.target.files || []); if (picked.some(f => f.size > 3 * 1024 * 1024)) { setError("Each attachment must be 3 MB or smaller."); return; } setFiles(current => [...current, ...picked]); }} /><small>Up to 3 MB per file.</small>{files.map((f,i) => <div key={`${f.name}-${i}`} className="compose-file">{f.name}<button type="button" aria-label={`Remove ${f.name}`} onClick={() => setFiles(current => current.filter((_,index) => index !== i))}><X /></button></div>)}</>}{key === "recurrence" && <><select aria-label="Repeat frequency" value={recurrence} onChange={e => setRecurrence(e.target.value)}><option value="">Does not repeat</option><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option></select><label htmlFor="repeat-until">Repeat until (optional)</label><Input id="repeat-until" type="date" min={dueDate || undefined} value={recurrenceUntil} onChange={e => setRecurrenceUntil(e.target.value)} /></>}</div>}</div>)}
              <div className="compose-tips"><Lightbulb /><div><h4>Tips</h4><ul><li>Use a clear and descriptive title</li><li>Add assignees and a due date</li><li>Use tags to organize your work</li></ul></div></div>
            </aside>
          </fieldset>
        </div>
        <footer className="task-compose-footer"><label><input type="checkbox" checked={createAnother} disabled={submitting} onChange={e => setCreateAnother(e.target.checked)} />Create another task after saving</label><div><Button type="button" variant="outline" disabled={submitting} onClick={onClose}>Cancel</Button><Button type="submit" disabled={submitting}><Sparkles />{submitting ? "Creating…" : created.current ? "Retry extras" : "Create task"}</Button></div></footer>
      </form>
    </Dialog.Content></Dialog.Portal></Dialog.Root>;
}

function DescriptionPreview({ text }: { text: string }) {
  return <>{text.split("\n").map((line, index) => {
    const heading = line.match(/^(#{1,2}) (.*)/); const list = line.match(/^(?:- |\d+\. )(.*)/);
    const content = (heading?.[2] || list?.[1] || line).split(/(\*\*.*?\*\*|\*[^*]+\*|`[^`]+`|<u>.*?<\/u>|\[.*?\]\(.*?\))/g).map((part,i) => {
      if (part.startsWith("**")) return <strong key={i}>{part.slice(2,-2)}</strong>;
      if (part.startsWith("*")) return <em key={i}>{part.slice(1,-1)}</em>;
      if (part.startsWith("`")) return <code key={i}>{part.slice(1,-1)}</code>;
      if (part.startsWith("<u>")) return <u key={i}>{part.slice(3,-4)}</u>;
      const link = part.match(/^\[(.*?)\]\((.*?)\)$/); if (link && /^https?:\/\//i.test(link[2])) return <a key={i} href={link[2]} target="_blank" rel="noreferrer">{link[1]}</a>;
      return part;
    });
    return heading ? <h4 key={index}>{content}</h4> : <p key={index}>{list ? "• " : ""}{content.length ? content : <br />}</p>;
  })}</>;
}

