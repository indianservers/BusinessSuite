import { RichTextContent } from "@/components/rich-text/RichTextContent";
import RunningTimer from "../components/RunningTimer";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { Edit2, Timer, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatDate } from "@/lib/utils";
import { projectsAPI, tasksAPI, timeLogsAPI } from "../services/api";
import type { PMSProject, PMSTask, PMSTimeLog } from "../types";

type TimeFormState = {
  projectId: string;
  taskId: string;
  logDate: string;
  startTime: string;
  endTime: string;
  minutes: string;
  description: string;
  isBillable: boolean;
};

const initialForm = (projectId = ""): TimeFormState => ({
  projectId,
  taskId: "",
  logDate: new Date().toLocaleDateString("en-CA"),
  startTime: "",
  endTime: "",
  minutes: "60",
  description: "",
  isBillable: true,
});

export default function TimeTrackingPage() {
  const [projects, setProjects] = useState<PMSProject[]>([]);
  const [tasks, setTasks] = useState<PMSTask[]>([]);
  const [logs, setLogs] = useState<PMSTimeLog[]>([]);
  const [form, setForm] = useState<TimeFormState>(initialForm());
  const [editingId, setEditingId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    projectsAPI.list()
      .then((items) => {
        setProjects(items);
        const firstProjectId = String(items[0]?.id || "");
        setForm(initialForm(firstProjectId));
      })
      .catch((err) => setError(err?.response?.data?.detail || "Unable to load projects."));
    loadLogs();
  }, []);

  useEffect(() => {
    if (!form.projectId) {
      setTasks([]);
      return;
    }
    tasksAPI.list(Number(form.projectId)).then(setTasks).catch(() => setTasks([]));
    loadLogs(Number(form.projectId));
  }, [form.projectId]);

  const totals = useMemo(() => {
    const total = logs.reduce((sum, log) => sum + Number(log.duration_minutes || 0), 0);
    const billable = logs.filter((log) => log.is_billable).reduce((sum, log) => sum + Number(log.duration_minutes || 0), 0);
    return { total, billable, nonBillable: total - billable };
  }, [logs]);

  async function loadLogs(projectId?: number) {
    setLoading(true);
    try {
      const items = await timeLogsAPI.list(0, 100, projectId ? { project_id: projectId } : undefined);
      setLogs(items);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to load time logs.");
    } finally {
      setLoading(false);
    }
  }

  const updateForm = (patch: Partial<TimeFormState>) => setForm((current) => ({ ...current, ...patch }));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const projectId = Number(form.projectId);
    const rawDuration = form.minutes.trim().toLowerCase();
    const durationParts = /^(?:(\d+(?:\.\d+)?)\s*h)?\s*(?:(\d+(?:\.\d+)?)\s*m)?$/.exec(rawDuration);
    const durationMinutes = /^\d+(?:\.\d+)?$/.test(rawDuration) ? Math.ceil(Number(rawDuration))
      : durationParts && (durationParts[1] || durationParts[2]) ? Math.ceil(Number(durationParts[1] || 0) * 60 + Number(durationParts[2] || 0)) : NaN;
    if (!projectId) {
      setError("Select a project before logging time.");
      return;
    }
    if (!Number.isFinite(durationMinutes) || durationMinutes <= 0) {
      setError("Duration must be greater than zero.");
      return;
    }
    setSaving(true);
    setError(null);
    const payload = {
      project_id: projectId,
      task_id: form.taskId ? Number(form.taskId) : undefined,
      log_date: form.logDate,
      start_time: form.startTime ? `${form.logDate}T${form.startTime}:00` : undefined,
      end_time: form.endTime ? `${form.logDate}T${form.endTime}:00` : undefined,
      duration_minutes: durationMinutes,
      description: form.description.trim() || undefined,
      is_billable: form.isBillable,
    };
    try {
      const saved = editingId ? await timeLogsAPI.update(editingId, payload) : await timeLogsAPI.create(payload);
      setLogs((items) => editingId ? items.map((item) => item.id === saved.id ? saved : item) : [saved, ...items]);
      setEditingId(null);
      setForm(initialForm(form.projectId));
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to save time log.");
    } finally {
      setSaving(false);
    }
  };

  const editLog = (log: PMSTimeLog) => {
    setEditingId(log.id);
    setForm({
      projectId: String(log.project_id),
      taskId: log.task_id ? String(log.task_id) : "",
      logDate: log.log_date,
      startTime: log.start_time ? log.start_time.slice(11, 16) : "",
      endTime: log.end_time ? log.end_time.slice(11, 16) : "",
      minutes: String(log.duration_minutes),
      description: log.description || "",
      isBillable: log.is_billable,
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setForm(initialForm(form.projectId));
  };

  const deleteLog = async (log: PMSTimeLog) => {
    const previous = logs;
    setLogs((items) => items.filter((item) => item.id !== log.id));
    try {
      await timeLogsAPI.delete(log.id);
    } catch (err: any) {
      setLogs(previous);
      setError(err?.response?.data?.detail || "Unable to delete time log.");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Time tracking</h1>
        <p className="page-description">Log task effort from the PMS backend and review billable/non-billable totals.</p>
      </div>

      <RunningTimer projects={projects} onSaved={() => { void loadLogs(form.projectId ? Number(form.projectId) : undefined); }} />
      <div className="grid gap-4 md:grid-cols-3">
        <Metric label="Total logged" minutes={totals.total} />
        <Metric label="Billable" minutes={totals.billable} />
        <Metric label="Non-billable" minutes={totals.nonBillable} />
      </div>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Timer className="h-5 w-5" />{editingId ? "Edit time log" : "Log time"}</CardTitle></CardHeader>
        <CardContent>
          {error ? <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
          <form onSubmit={submit} className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <Field label="Project">
                <select value={form.projectId} onChange={(event) => updateForm({ projectId: event.target.value, taskId: "" })} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                  <option value="">Select project</option>
                  {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
                </select>
              </Field>
              <Field label="Task">
                <select value={form.taskId} onChange={(event) => updateForm({ taskId: event.target.value })} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                  <option value="">Project-level time</option>
                  {tasks.map((task) => <option key={task.id} value={task.id}>{task.task_key} - {task.title}</option>)}
                </select>
              </Field>
              <Field label="Date"><Input type="date" value={form.logDate} onChange={(event) => updateForm({ logDate: event.target.value })} required /></Field>
              <Field label="Duration (minutes or 3h 20m)"><Input type="text" placeholder="60 or 1h 30m" value={form.minutes} onChange={(event) => updateForm({ minutes: event.target.value })} required /></Field>
              <Field label="Start time"><Input type="time" value={form.startTime} onChange={(event) => updateForm({ startTime: event.target.value })} /></Field>
              <Field label="End time"><Input type="time" value={form.endTime} onChange={(event) => updateForm({ endTime: event.target.value })} /></Field>
              <Field label="Billable">
                <label className="flex h-10 items-center gap-2 rounded-md border px-3 text-sm">
                  <input type="checkbox" checked={form.isBillable} onChange={(event) => updateForm({ isBillable: event.target.checked })} />
                  {form.isBillable ? "Billable" : "Non-billable"}
                </label>
              </Field>
              <Field label="Description"><Input value={form.description} onChange={(event) => updateForm({ description: event.target.value })} placeholder="What did you work on?" /></Field>
            </div>
            <div className="flex flex-wrap justify-end gap-2">
              {editingId ? <Button type="button" variant="outline" onClick={cancelEdit}>Cancel</Button> : null}
              <Button type="submit" disabled={saving}>{saving ? "Saving..." : editingId ? "Save time log" : "Log time"}</Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Backend time logs</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {loading ? <div className="skeleton h-32 rounded-lg" /> : null}
          {!loading && !logs.length ? <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">No time logs found.</div> : null}
          {logs.map((log) => (
            <div key={log.id} className="rounded-lg border p-3 text-sm">
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">{formatMinutes(log.duration_minutes)}</span>
                    <Badge variant={log.is_billable ? "default" : "outline"}>{log.is_billable ? "Billable" : "Non-billable"}</Badge>
                    <Badge variant="outline">{log.approval_status}</Badge>
                    {log.task_id ? <Badge variant="secondary">Task #{log.task_id}</Badge> : <Badge variant="secondary">Project time</Badge>}
                  </div>
                  <div className="mt-2 text-muted-foreground"><RichTextContent value={log.description || "No description"}/></div>
                  <p className="mt-2 text-xs text-muted-foreground">
                    {formatDate(log.log_date)}
                    {log.start_time ? ` / ${formatTime(log.start_time)}` : ""}
                    {log.end_time ? ` - ${formatTime(log.end_time)}` : ""}
                    {` / User #${log.user_id}`}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button type="button" size="sm" variant="outline" onClick={() => editLog(log)}><Edit2 className="h-4 w-4" />Edit</Button>
                  <Button type="button" size="sm" variant="ghost" onClick={() => deleteLog(log)}><Trash2 className="h-4 w-4" />Delete</Button>
                </div>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="space-y-2"><Label className="text-xs uppercase text-muted-foreground">{label}</Label>{children}</div>;
}

function Metric({ label, minutes }: { label: string; minutes: number }) {
  return <Card><CardContent className="p-5"><p className="text-sm text-muted-foreground">{label}</p><p className="mt-2 text-3xl font-semibold">{formatMinutes(minutes)}</p></CardContent></Card>;
}

function formatMinutes(minutes: number) {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (!hours) return `${mins}m`;
  return `${hours}h ${mins}m`;
}

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
