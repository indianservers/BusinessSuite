import WorkspaceCalendar from "./WorkspaceCalendar";
import { useState } from "react";
import { Link } from "react-router-dom";
import { personName, taskAssignees, taskBucket, type WorkTask, type WorkspaceMember, type WorkspaceProject } from "./workspaceTypes";

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
export default function WorkspacePlanning({ view, tasks, members, projects, onOpen, canEdit = false, onCreate, onUpdate, onRefresh }: {
  onRefresh?: () => Promise<void>; view: "calendar" | "workload"; tasks: WorkTask[]; members: WorkspaceMember[]; projects: WorkspaceProject[]; onOpen: (id: number) => void; canEdit?: boolean; onCreate?: (day: string, project: string) => void; onUpdate?: (task: WorkTask, changes: Partial<WorkTask>) => Promise<boolean>;
}) {
  const [month, setMonth] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  const [project, setProject] = useState("");
  const filtered = tasks.filter(t => !project || t.project_id === Number(project));
  const start = new Date(month.getFullYear(), month.getMonth(), 1 - (month.getDay() + 6) % 7);
  const days = Array.from({ length: 42 }, (_, i) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + i));
  if (view === "calendar" && onCreate && onUpdate) return <WorkspaceCalendar tasks={tasks} members={members} projects={projects} onOpen={onOpen} canEdit={canEdit} onCreate={onCreate} onUpdate={onUpdate} onRefresh={onRefresh} />;
  return <section className="ws-planning" aria-label={view === "calendar" ? "Workspace calendar" : "Workspace workload"}>
    <header><h2>{view === "calendar" ? "Calendar" : "Team workload"}</h2><select aria-label="Planning project" value={project} onChange={e => setProject(e.target.value)}><option value="">All workspace projects</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></header>
    {view === "calendar" ? <>
      <div className="ws-calendar-controls"><button aria-label="Previous month" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}>←</button><strong>{month.toLocaleDateString(undefined, { month: "long", year: "numeric" })}</strong><button aria-label="Next month" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}>→</button><button onClick={() => setMonth(new Date(new Date().getFullYear(), new Date().getMonth(), 1))}>Today</button></div>
      <p>Tasks appear on their due date, or start date when no due date is set. Open a task to change its schedule.</p>
      <div className="ws-calendar-grid">{["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(d => <strong key={d}>{d}</strong>)}{days.map(day => <div key={iso(day)} className={day.getMonth() !== month.getMonth() ? "outside" : ""}><time dateTime={iso(day)}>{day.getDate()}</time>{filtered.filter(t => (t.due_date || t.start_date) === iso(day)).map(t => <button key={t.id} onClick={() => onOpen(t.id)} title={`${t.title} · ${t.status}`}><span>{t.status === "Done" ? "✓ " : ""}{t.title}</span></button>)}</div>)}</div>
      <h3>Unscheduled · {filtered.filter(t => !t.due_date && !t.start_date).length}</h3><div className="ws-planning-tasks">{filtered.filter(t => !t.due_date && !t.start_date).map(t => <button key={t.id} onClick={() => onOpen(t.id)}>{t.title}</button>)}</div>
    </> : <>
      <p>Open tasks across this workspace. Estimated effort is split equally between collaborators; shared tasks count once for each assigned member.</p>
      <div className="ws-workload-grid">{members.filter(m => m.role !== "Guest").map(m => {
        const work = filtered.filter(t => taskAssignees(t).includes(m.user_id) && taskBucket(t.status) !== "Done");
        const hours = work.reduce((sum, t) => sum + Number(t.estimated_hours || 0) / Math.max(taskAssignees(t).length, 1), 0);
        return <article key={m.id}><h3>{personName(m.email)}</h3><p>{m.email}</p><strong>{work.length} open tasks · {Number(hours.toFixed(1))} estimated hours</strong><small>{work.filter(t => !t.estimated_hours).length} tasks need an estimate</small><div className="ws-planning-tasks">{work.map(t => <button key={t.id} onClick={() => onOpen(t.id)}>{t.title}<small>{taskAssignees(t).length > 1 ? "Shared task" : t.priority}{t.due_date ? ` · Due ${t.due_date}` : " · No due date"}</small></button>)}</div></article>;
      })}</div>
      <h3>Unassigned work</h3><div className="ws-planning-tasks">{filtered.filter(t => !taskAssignees(t).length && taskBucket(t.status) !== "Done").map(t => <button key={t.id} onClick={() => onOpen(t.id)}>{t.title}</button>)}</div>
    </>}
    <div className="ws-planning-links"><h3>Gantt & dependencies</h3><p>Schedule tasks, connect dependencies, and adjust dates in each project’s timeline.</p>{projects.filter(p => !project || p.id === Number(project)).map(p => <Link key={p.id} to={`/pms/projects/${p.id}/gantt`}>{p.name} — Gantt & dependencies ↗</Link>)}</div>
  </section>;
}
