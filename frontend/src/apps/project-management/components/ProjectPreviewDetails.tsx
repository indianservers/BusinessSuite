import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { tasksAPI, milestonesAPI, activityAPI } from "../services/api";
import { formatDate } from "@/lib/utils";
import { workspaceError } from "../pages/workspaceTypes";
import type { PMSTask, PMSMilestone, PMSActivity } from "../types";
export default function ProjectPreviewDetails({
  projectId,
}: {
  projectId: number;
}) {
  const [tab, setTab] = useState(""),
    [loading, setLoading] = useState(false),
    [error, setError] = useState("");
  const [tasks, setTasks] = useState<PMSTask[]>([]),
    [milestones, setMilestones] = useState<PMSMilestone[]>([]),
    [activity, setActivity] = useState<PMSActivity[]>([]);
  useEffect(() => {
    if (!tab) return;
    let active = true;
    setLoading(true);
    setError("");
    const work =
      tab === "tasks"
        ? tasksAPI.list(projectId, 0, 10).then((rows) => {
            if (active) setTasks(rows);
          })
        : tab === "milestones"
          ? milestonesAPI.list(projectId, 0, 10).then((rows) => {
              if (active) setMilestones(rows);
            })
          : activityAPI.list(projectId, { limit: 10 }).then((rows) => {
              if (active) setActivity(rows);
            });
    void work
      .catch((e) => {
        if (active) setError(workspaceError(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [tab, projectId]);
  return (
    <section className="portfolio-preview-details">
      <div
        className="flex flex-wrap gap-2"
        role="group"
        aria-label="Preview details"
      >
        {["tasks", "milestones", "activity"].map((t) => (
          <button
            key={t}
            aria-pressed={tab === t}
            className="rounded-md border px-3 py-2 text-xs capitalize aria-pressed:bg-primary/10"
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>
      {loading ? (
        <p role="status">Loading {tab}…</p>
      ) : error ? (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      ) : tab === "tasks" ? (
        <>
          <p className="mt-3 text-xs text-muted-foreground">
            First 10 tasks ·{" "}
            <Link
              className="text-primary"
              to={`/pms/projects/${projectId}/board`}
            >
              View all tasks
            </Link>
          </p>
          {tasks.length ? (
            tasks.map((t) => (
              <Link
                key={t.id}
                className="block border-b py-3 text-xs"
                to={`/pms/projects/${projectId}/tasks/${t.id}`}
              >
                <b>
                  {t.task_key} · {t.title}
                </b>
                <span className="mt-1 block text-muted-foreground">
                  {t.status} · {formatDate(t.due_date || null)}
                </span>
              </Link>
            ))
          ) : (
            <p className="py-3 text-xs text-muted-foreground">
              No tasks added yet.
            </p>
          )}
        </>
      ) : tab === "milestones" ? (
        <>
          <p className="mt-3 text-xs text-muted-foreground">
            First 10 milestones ·{" "}
            <Link
              className="text-primary"
              to={`/pms/projects/${projectId}/milestones`}
            >
              View all milestones
            </Link>
          </p>
          {milestones.length ? (
            milestones.map((m) => (
              <div key={m.id} className="border-b py-3 text-xs">
                <b>{m.name}</b>
                <p className="mt-1 text-muted-foreground">
                  {m.status} · {formatDate(m.due_date || null)}
                </p>
              </div>
            ))
          ) : (
            <p className="py-3 text-xs text-muted-foreground">
              No milestones added yet.
            </p>
          )}
        </>
      ) : tab === "activity" ? (
        <>
          <p className="mt-3 text-xs text-muted-foreground">Recent activity</p>
          {activity.length ? (
            activity.map((a) => (
              <div key={a.id} className="border-b py-3 text-xs">
                <p>{a.summary}</p>
                <small className="text-muted-foreground">
                  {formatDate(a.created_at)}
                </small>
              </div>
            ))
          ) : (
            <p className="py-3 text-xs text-muted-foreground">
              No activity recorded yet.
            </p>
          )}
        </>
      ) : null}
    </section>
  );
}
