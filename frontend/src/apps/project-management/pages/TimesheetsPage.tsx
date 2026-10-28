import { useRefreshableEffect } from "@/lib/page-refresh";
import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Clock, Send, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatDate, statusColor } from "@/lib/utils";
import { projectsAPI, pmsUsersAPI, tasksAPI, timesheetsAPI } from "../services/api";
import type { PMSMentionUser, PMSProject, PMSTask, PMSTimesheet } from "../types";

type TimesheetRow = {
  key: string;
  projectId: string;
  taskId: string;
  description: string;
  isBillable: boolean;
  cells: Record<string, string>;
  logIds: Record<string, number>;
};

const emptyRow = (days: string[], projectId = ""): TimesheetRow => ({
  key: crypto.randomUUID(),
  projectId,
  taskId: "",
  description: "",
  isBillable: true,
  cells: Object.fromEntries(days.map((day) => [day, ""])),
  logIds: {},
});

export default function TimesheetsPage() {
  const [weekStart, setWeekStart] = useState(startOfWeek(new Date()));
  const [projects, setProjects] = useState<PMSProject[]>([]);
  const [tasksByProject, setTasksByProject] = useState<Record<string, PMSTask[]>>({});
  const [sheet, setSheet] = useState<PMSTimesheet | null>(null);
  const [rows, setRows] = useState<TimesheetRow[]>([]);
  const [approvals, setApprovals] = useState<PMSTimesheet[]>([]);
  const [users, setUsers] = useState<PMSMentionUser[]>([]);
  const [approvalStatus, setApprovalStatus] = useState("submitted");
  const [approvalUserId, setApprovalUserId] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const days = useMemo(() => Array.from({ length: 7 }, (_, index) => addDays(weekStart, index)), [weekStart]);
  const editable = !sheet || sheet.status === "draft" || sheet.status === "rejected";

  useRefreshableEffect(() => {
    projectsAPI.list().then((items) => {
      setProjects(items);
      items.slice(0, 5).forEach((project) => loadTasks(project.id));
    }).catch(() => setProjects([]));
    pmsUsersAPI.search({ limit: 25 }).then(setUsers).catch(() => setUsers([]));
  }, []);

  useRefreshableEffect(() => {
    loadSheet();
  }, [weekStart]);

  useRefreshableEffect(() => {
    loadApprovals();
  }, [approvalStatus, approvalUserId, weekStart]);

  async function loadTasks(projectId: number) {
    if (tasksByProject[String(projectId)]) return;
    const tasks = await tasksAPI.list(projectId).catch(() => []);
    setTasksByProject((current) => ({ ...current, [String(projectId)]: tasks }));
  }

  async function loadSheet() {
    setLoading(true);
    setError(null);
    try {
      const week = formatIsoDate(weekStart);
      const existing = await timesheetsAPI.list({ weekStart: week });
      const current = existing[0] || await timesheetsAPI.create({ week_start_date: week });
      setSheet(current);
      setRows(toRows(current, days));
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to load weekly timesheet.");
    } finally {
      setLoading(false);
    }
  }

  async function loadApprovals() {
    try {
      const items = await timesheetsAPI.list({
        weekStart: formatIsoDate(weekStart),
        status: approvalStatus || undefined,
        userId: approvalUserId ? Number(approvalUserId) : undefined,
      });
      setApprovals(items.filter((item) => item.id !== sheet?.id));
    } catch {
      setApprovals([]);
    }
  }

  function updateRow(rowKey: string, patch: Partial<TimesheetRow>) {
    setRows((items) => items.map((item) => item.key === rowKey ? { ...item, ...patch } : item));
  }

  function updateCell(rowKey: string, day: string, value: string) {
    setRows((items) => items.map((item) => item.key === rowKey ? { ...item, cells: { ...item.cells, [day]: value } } : item));
  }

  async function saveDraft() {
    setSaving(true);
    setError(null);
    try {
      const entries = rows.flatMap((row) => days.map((day) => {
        const minutes = Math.round(Number(row.cells[day] || 0) * 60);
        if (!row.projectId || minutes <= 0) return null;
        return {
          time_log_id: row.logIds[day],
          project_id: Number(row.projectId),
          task_id: row.taskId ? Number(row.taskId) : undefined,
          log_date: day,
          duration_minutes: minutes,
          description: row.description || undefined,
          is_billable: row.isBillable,
        };
      }).filter(Boolean)).filter(Boolean) as any[];
      const saved = sheet
        ? await timesheetsAPI.update(sheet.id, { week_start_date: formatIsoDate(weekStart), entries })
        : await timesheetsAPI.create({ week_start_date: formatIsoDate(weekStart), entries });
      setSheet(saved);
      setRows(toRows(saved, days));
      await loadApprovals();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to save timesheet.");
    } finally {
      setSaving(false);
    }
  }

  async function submit() {
    if (!sheet) return;
    await saveDraft();
    const submitted = await timesheetsAPI.submit(sheet.id);
    setSheet(submitted);
    setRows(toRows(submitted, days));
    await loadApprovals();
  }

  async function approve(item: PMSTimesheet) {
    await timesheetsAPI.approve(item.id);
    await loadApprovals();
  }

  async function reject(item: PMSTimesheet) {
    const reason = window.prompt("Rejection comments");
    if (!reason) return;
    await timesheetsAPI.reject(item.id, reason);
    await loadApprovals();
  }

  const totals = useMemo(() => {
    const daily = Object.fromEntries(days.map((day) => [day, rows.reduce((sum, row) => sum + Number(row.cells[day] || 0), 0)]));
    const total = Object.values(daily).reduce((sum, value) => sum + Number(value), 0);
    return { daily, total };
  }, [days, rows]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Weekly timesheets</h1>
        <p className="page-description">Log task hours by week, submit for approval, and review submitted team timesheets.</p>
      </div>

      {error ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}

      <div className="grid gap-3 md:grid-cols-4">
        <Metric label="Weekly hours" value={`${totals.total.toFixed(1)}h`} />
        <Metric label="Status" value={sheet?.status || "draft"} />
        <Metric label="Billable" value={`${((sheet?.billable_minutes || 0) / 60).toFixed(1)}h`} />
        <Metric label="Non-billable" value={`${((sheet?.non_billable_minutes || 0) / 60).toFixed(1)}h`} />
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <CardTitle className="flex items-center gap-2"><Clock className="h-5 w-5" />My weekly grid</CardTitle>
            <div className="flex flex-wrap items-center gap-2">
              <Input type="date" value={formatIsoDate(weekStart)} onChange={(event) => setWeekStart(startOfWeek(new Date(`${event.target.value}T00:00:00`)))} className="w-40" />
              {sheet ? <Badge className={statusColor(sheet.status)}>{sheet.status}</Badge> : null}
              <Button variant="outline" onClick={() => setRows((items) => [...items, emptyRow(days, projects[0] ? String(projects[0].id) : "")])} disabled={!editable}>Add row</Button>
              <Button variant="outline" onClick={saveDraft} disabled={!editable || saving}>{saving ? "Saving..." : "Save draft"}</Button>
              <Button onClick={submit} disabled={!editable || !sheet || saving}><Send className="h-4 w-4" />Submit</Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {sheet?.rejection_reason ? <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">Rejected: {sheet.rejection_reason}</div> : null}
          {loading ? <div className="skeleton h-48 rounded-lg" /> : (
            <div className="overflow-x-auto">
              <table className="min-w-[980px] w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b bg-muted/40 text-left">
                    <Th>Project</Th>
                    <Th>Task</Th>
                    <Th>Billable</Th>
                    {days.map((day) => <Th key={day}>{shortDay(day)}<br /><span className="font-normal text-muted-foreground">{day.slice(5)}</span></Th>)}
                    <Th>Total</Th>
                    <Th><span /></Th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.key} className="border-b">
                      <Td>
                        <select value={row.projectId} disabled={!editable} onChange={(event) => { updateRow(row.key, { projectId: event.target.value, taskId: "" }); if (event.target.value) loadTasks(Number(event.target.value)); }} className="h-9 w-44 rounded-md border bg-background px-2">
                          <option value="">Project</option>
                          {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
                        </select>
                      </Td>
                      <Td>
                        <select value={row.taskId} disabled={!editable} onChange={(event) => updateRow(row.key, { taskId: event.target.value })} className="h-9 w-56 rounded-md border bg-background px-2">
                          <option value="">Project time</option>
                          {(tasksByProject[row.projectId] || []).map((task) => <option key={task.id} value={task.id}>{task.task_key} - {task.title}</option>)}
                        </select>
                      </Td>
                      <Td><input type="checkbox" disabled={!editable} checked={row.isBillable} onChange={(event) => updateRow(row.key, { isBillable: event.target.checked })} /></Td>
                      {days.map((day) => <Td key={day}><Input disabled={!editable} type="number" min="0" step="0.25" value={row.cells[day] || ""} onChange={(event) => updateCell(row.key, day, event.target.value)} className="w-20" /></Td>)}
                      <Td className="font-semibold">{rowTotal(row, days).toFixed(1)}h</Td>
                      <Td><Button variant="ghost" size="sm" disabled={!editable} onClick={() => setRows((items) => items.filter((item) => item.key !== row.key))}>Remove</Button></Td>
                    </tr>
                  ))}
                  {!rows.length ? <tr><td colSpan={days.length + 5} className="p-8 text-center text-muted-foreground">No rows yet. Add a row to log time.</td></tr> : null}
                </tbody>
                <tfoot>
                  <tr className="bg-muted/30 font-semibold">
                    <Td>Daily total</Td><Td></Td><Td></Td>
                    {days.map((day) => <Td key={day}>{Number(totals.daily[day] || 0).toFixed(1)}h</Td>)}
                    <Td>{totals.total.toFixed(1)}h</Td><Td></Td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <CardTitle>Manager approvals</CardTitle>
            <div className="grid gap-2 md:grid-cols-3">
              <Field label="Status">
                <select value={approvalStatus} onChange={(event) => setApprovalStatus(event.target.value)} className="h-10 rounded-md border bg-background px-3 text-sm">
                  <option value="submitted">Submitted</option>
                  <option value="approved">Approved</option>
                  <option value="rejected">Rejected</option>
                  <option value="">All</option>
                </select>
              </Field>
              <Field label="User">
                <select value={approvalUserId} onChange={(event) => setApprovalUserId(event.target.value)} className="h-10 rounded-md border bg-background px-3 text-sm">
                  <option value="">All accessible users</option>
                  {users.map((user) => <option key={user.id} value={user.id}>{user.email}</option>)}
                </select>
              </Field>
              <Field label="Week"><Input type="date" value={formatIsoDate(weekStart)} onChange={(event) => setWeekStart(startOfWeek(new Date(`${event.target.value}T00:00:00`)))} /></Field>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {approvals.map((item) => (
            <div key={item.id} className="rounded-lg border p-4">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">User #{item.user_id}</span>
                    <Badge className={statusColor(item.status)}>{item.status}</Badge>
                    <Badge variant="outline">{formatDate(item.week_start_date)}</Badge>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">{(item.total_minutes / 60).toFixed(1)}h total / {(item.billable_minutes / 60).toFixed(1)}h billable / {item.entries.length} entries</p>
                  {item.rejection_reason ? <p className="mt-2 text-sm text-amber-700">{item.rejection_reason}</p> : null}
                </div>
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => approve(item)} disabled={item.status !== "submitted"}><CheckCircle2 className="h-4 w-4" />Approve</Button>
                  <Button size="sm" variant="outline" onClick={() => reject(item)} disabled={item.status !== "submitted"}><XCircle className="h-4 w-4" />Reject</Button>
                </div>
              </div>
            </div>
          ))}
          {!approvals.length ? <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">No timesheets match the approval filters.</div> : null}
        </CardContent>
      </Card>
    </div>
  );
}

function toRows(sheet: PMSTimesheet, days: string[]): TimesheetRow[] {
  const groups = new Map<string, TimesheetRow>();
  sheet.entries.forEach((entry) => {
    const key = `${entry.project_id}:${entry.task_id || "project"}:${entry.is_billable}`;
    if (!groups.has(key)) groups.set(key, { ...emptyRow(days, String(entry.project_id)), key, taskId: entry.task_id ? String(entry.task_id) : "", isBillable: entry.is_billable, description: entry.description || "" });
    const row = groups.get(key)!;
    row.cells[entry.log_date] = entry.duration_minutes ? String(entry.duration_minutes / 60) : "";
    if (entry.time_log_id) row.logIds[entry.log_date] = entry.time_log_id;
  });
  return Array.from(groups.values());
}

function startOfWeek(date: Date) {
  const copy = new Date(date);
  copy.setDate(copy.getDate() - ((copy.getDay() + 6) % 7));
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function addDays(date: Date, days: number) {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + days);
  return formatIsoDate(copy);
}

function formatIsoDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

function rowTotal(row: TimesheetRow, days: string[]) {
  return days.reduce((sum, day) => sum + Number(row.cells[day] || 0), 0);
}

function shortDay(day: string) {
  return new Date(`${day}T00:00:00`).toLocaleDateString([], { weekday: "short" });
}

function Metric({ label, value }: { label: string; value: string }) {
  return <Card><CardContent className="p-4"><p className="text-sm text-muted-foreground">{label}</p><p className="mt-2 text-2xl font-semibold capitalize">{value}</p></CardContent></Card>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="space-y-1"><Label className="text-xs uppercase text-muted-foreground">{label}</Label>{children}</div>;
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="p-2 align-middle font-medium">{children}</th>;
}

function Td({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <td className={`p-2 align-middle ${className}`}>{children}</td>;
}
