import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import MoveBoard from "@/components/interaction/MoveBoard";
import { projectsAPI, tasksAPI } from "../services/api";
import { usePMSRealtime } from "../realtime";
import { arrangeTask } from "./SprintMoveBoard";
import type { PMSProject, PMSTaskListItem } from "../types";
const statuses = [
  "Backlog",
  "To Do",
  "In Progress",
  "In Review",
  "Blocked",
  "Done",
  "Cancelled",
];
export default function WorkMovementPage({ title }: { title: string }) {
  const [projects, setProjects] = useState<PMSProject[]>([]);
  const [project, setProject] = useState(0);
  const [tasks, setTasks] = useState<PMSTaskListItem[]>([]);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const projectRef = useRef(project);
  projectRef.current = project;
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    projectsAPI
      .list()
      .then((rows) => {
        setProjects(rows);
        setProject(rows[0]?.id || 0);
      })
      .catch(() => setError("Unable to load accessible projects."));
  }, []);
  async function load(id = project) {
    if (!id) return;
    setError("");
    try {
      const result = await tasksAPI.listAll({
        projectId: id,
        pageSize: 200,
        sortBy: "position",
        sortOrder: "asc",
      });
      if (id === projectRef.current) setTasks(result.items);
    } catch {
      setError("Unable to refresh work. Your previous view has been retained.");
    }
  }
  useEffect(() => {
    setTasks([]);
    setLoading(true);
    void load().finally(() => setLoading(false));
  }, [project]);
  usePMSRealtime({
    projectId: project || undefined,
    onEvent: () => void load(),
    showToast: false,
  });
  const canManage = projects.find((p) => p.id === project)?.can_manage_tasks;
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap justify-between gap-3">
        <div>
          <h1 className="page-title">{title}</h1>
          <p className="page-description">
            Move real project work between stages. Every change is saved and
            checked against your access.
          </p>
        </div>
        <Link
          to={`/pms/tasks/new?projectId=${project}`}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
        >
          Add task
        </Link>
      </div>
      <div className="flex flex-wrap gap-3">
        <select
          aria-label="Work project"
          className="h-10 max-w-xs rounded-lg border border-input bg-background px-3 text-sm"
          value={project}
          onChange={(e) => setProject(Number(e.target.value))}
        >
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <input
          aria-label="Search work cards"
          className="h-10 max-w-xs rounded-lg border border-input bg-background px-3 text-sm"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search work"
        />
        <button onClick={() => void load()}>Refresh</button>
        <Link to="/pms/my-work">My Work</Link>
        <Link to="/pms/gantt">Timeline</Link>
        <Link to="/pms/workload">Workload</Link>
      </div>
      {error && (
        <p role="alert" className="move-error">
          {error}
        </p>
      )}
      {loading && <p role="status">Loading work…</p>}
      <MoveBoard
        label={`${title} stages`}
        disabled={!canManage || loading}
        groups={statuses.map((s) => ({ id: s, label: s }))}
        items={tasks
          .filter((t) =>
            `${t.task_key} ${t.title}`
              .toLowerCase()
              .includes(search.toLowerCase()),
          )
          .map((t) => ({
            id: t.id,
            label: t.title,
            group: t.status,
            content: (
              <div className="text-xs text-muted-foreground">
                <Link to={`/pms/tasks/${t.id}`} className="text-primary">
                  {t.task_key}
                </Link>
                <p>
                  {t.assignee_name || "Unassigned"} · {t.priority}
                </p>
                {t.due_date && <p>Due {t.due_date}</p>}
              </div>
            ),
          }))}
        onMove={async ({ item, group, beforeId }) => {
          try {
            await arrangeTask(Number(item.id), {
              group_by: "status",
              status: group,
              before_id: beforeId,
            });
          } finally {
            await load();
          }
        }}
      />
      <p className="text-xs text-muted-foreground">
        Showing up to 200 accessible tasks for this project.
      </p>
    </div>
  );
}
