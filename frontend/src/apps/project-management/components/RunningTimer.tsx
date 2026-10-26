import { RichTextContent } from "@/components/rich-text/RichTextContent";
import { useEffect, useRef, useState } from "react";
import * as AlertDialog from "@radix-ui/react-alert-dialog";
import { Link } from "react-router-dom";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { tasksAPI } from "../services/api";
import type { PMSProject, PMSTask } from "../types";
import { workspaceError } from "../pages/workspaceTypes";
type Timer = { session_key: string; project_id: number; task_id: number | null; started_at: string; description: string; is_billable: boolean; timezone: string };
export default function RunningTimer({ projects, onSaved, fixedTask }: { projects: PMSProject[]; onSaved: () => void; fixedTask?: PMSTask }) {
  const [timer, setTimer] = useState<Timer | null>(null);
  const [project, setProject] = useState("");
  const [task, setTask] = useState("");
  const [tasks, setTasks] = useState<PMSTask[]>([]);
  const [note, setNote] = useState("");
  const [billable, setBillable] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [now, setNow] = useState(Date.now());
  const [discard, setDiscard] = useState(false);
  const startKey = useRef<string | null>(null);
  const lock = useRef(false);
  async function refresh() { const { data } = await api.get<Timer | null>("/project-management/timer"); setTimer(data); }
  useEffect(() => {
    let active = true;
    api.get<Timer | null>("/project-management/timer").then(({ data }) => { if (active) setTimer(data); }).catch(error => { if (active) setError(workspaceError(error)); }).finally(() => { if (active) setLoading(false); });
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => { active = false; clearInterval(tick); };
  }, []);
  useEffect(() => {
    if (fixedTask) { setProject(String(fixedTask.project_id)); setTask(String(fixedTask.id)); setTasks([fixedTask]); return; }
    if (!project) { setTasks([]); return; }
    let active = true; setTasks([]); setTask("");
    tasksAPI.list(Number(project)).then(data => { if (active) setTasks(data); }).catch(error => { if (active) setError(workspaceError(error)); });
    return () => { active = false; };
  }, [project, fixedTask?.id]);
  async function act(action: "start" | "stop" | "discard") {
    if (lock.current) return; lock.current = true; setBusy(true); setError(""); setNotice("");
    try {
      if (action === "start") {
        startKey.current ||= crypto.randomUUID();
        const { data } = await api.post<Timer>("/project-management/timer/start", { project_id: fixedTask?.project_id || Number(project), task_id: fixedTask?.id || (task ? Number(task) : null), description: note, is_billable: billable, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC", session_key: startKey.current });
        setTimer(data); startKey.current = null;
      } else if (timer) {
        const { data } = await api.post(`/project-management/timer/${action}`, { session_key: timer.session_key });
        setTimer(null); setDiscard(false);
        setNotice(action === "stop" ? `Saved ${data.duration_minutes ?? "tracked"} ${data.duration_minutes === 1 ? "minute" : "minutes"} to your time logs` : "Timer discarded without logging time");
        if (action === "stop") onSaved();
      }
    } catch (error) { setError(workspaceError(error)); try { await refresh(); } catch { /* Keep the last known timer so stop can be retried. */ } }
    finally { lock.current = false; setBusy(false); }
  }
  const seconds = timer ? Math.max(0, Math.floor((now - new Date(timer.started_at).getTime()) / 1000)) : 0;
  const clock = `${String(Math.floor(seconds / 3600)).padStart(2, "0")}:${String(Math.floor(seconds / 60) % 60).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  const control = "mt-1 h-10 w-full rounded-md border bg-background px-3 text-sm";
  return <section className="space-y-4 rounded-xl border bg-card p-5" aria-label="Running time tracker">
    <header className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold">Track time</h2><Link className="text-sm text-primary underline" to="/pms/timesheets">My timesheets</Link></header>
    {error && <p role="alert" className="text-destructive">{error}</p>}{notice && <p role="status">{notice}</p>}
    {loading ? <p role="status">Loading timer…</p> : timer ? <>
      <p className="font-mono text-3xl tabular-nums" aria-label="Timer elapsed">{clock}</p><p className="text-sm">{projects.find(project => project.id === timer.project_id)?.name || `Project ${timer.project_id}`} · {timer.task_id ? <Link className="text-primary underline" to={`/pms/tasks/${timer.task_id}`}>Task #{timer.task_id}</Link> : "Project-level time"} · {timer.is_billable ? "Billable" : "Non-billable"}</p>{timer.description && <div className="whitespace-pre-wrap text-sm text-muted-foreground"><RichTextContent value={timer.description}/></div>}<div className="flex flex-wrap gap-2"><Button disabled={busy} onClick={() => void act("stop")}>Stop and save</Button><Button variant="outline" disabled={busy} onClick={() => setDiscard(true)}>Discard timer</Button></div>
    </> : <form className="space-y-3" onSubmit={event => { event.preventDefault(); void act("start"); }}><fieldset disabled={busy} className="grid gap-3 sm:grid-cols-2"><label className="text-sm">Project<select required disabled={!!fixedTask} aria-label="Timer project" className={control} value={project} onChange={event => { setProject(event.target.value); startKey.current = null; }}><option value="" disabled>Choose project</option>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label><label className="text-sm">Task<select disabled={!!fixedTask} aria-label="Timer task" className={control} value={task} onChange={event => { setTask(event.target.value); startKey.current = null; }}><option value="">Project-level time</option>{tasks.map(task => <option key={task.id} value={task.id}>{task.task_key} · {task.title}</option>)}</select></label><label className="text-sm sm:col-span-2">Notes<Input aria-label="Timer notes" maxLength={10000} value={note} onChange={event => { setNote(event.target.value); startKey.current = null; }} /></label><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={billable} onChange={event => { setBillable(event.target.checked); startKey.current = null; }} />Billable</label><Button disabled={busy || !project}>{busy ? "Starting…" : "Start timer"}</Button></fieldset></form>}
    {fixedTask && timer && timer.task_id !== fixedTask.id && <p role="status" className="text-sm text-amber-700">Your timer is running on another task. Stop and save it before starting this task.</p>}
    <p className="text-xs text-muted-foreground">One timer per account. It keeps running across reloads. Saving rounds up to the next whole minute and records the time on the start date in your browser time zone.</p>
    <Button size="sm" variant="ghost" disabled={busy || loading} onClick={() => { void refresh().catch(error => setError(workspaceError(error))); }}>Refresh timer</Button>
    <AlertDialog.Root open={discard} onOpenChange={value => { if (!busy) setDiscard(value); }}><AlertDialog.Portal><AlertDialog.Overlay className="fixed inset-0 z-50 bg-black/40" /><AlertDialog.Content className="fixed left-1/2 top-1/2 z-50 w-[calc(100%_-_2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 space-y-4 rounded-lg border bg-background p-5"><AlertDialog.Title className="font-semibold">Discard tracked time?</AlertDialog.Title><AlertDialog.Description className="text-sm text-muted-foreground">This stops the timer without creating a time log.</AlertDialog.Description><div className="flex justify-end gap-2"><AlertDialog.Cancel asChild><Button variant="outline" disabled={busy}>Keep tracking</Button></AlertDialog.Cancel><Button variant="destructive" disabled={busy} onClick={() => void act("discard")}>Discard time</Button></div></AlertDialog.Content></AlertDialog.Portal></AlertDialog.Root>
  </section>;
}
