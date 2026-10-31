import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/services/api";
import MoveBoard from "@/components/interaction/MoveBoard";
import { backlogAPI } from "../services/api";
import type { PMSBacklogResponse } from "../types";

export async function arrangeTask(
  id: number,
  payload: Record<string, unknown>,
) {
  const { data } = await api.get(`/project-management/task-studio/tasks/${id}`);
  await api.post(`/project-management/my-work/tasks/${id}/arrange`, {
    ...payload,
    version: data.version,
  });
}

export default function SprintMoveBoard({
  projectId,
  onSaved,
}: {
  projectId: number;
  onSaved?: () => void;
}) {
  const [data, setData] = useState<PMSBacklogResponse>();
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setData(undefined);
    backlogAPI
      .get(projectId, { sortBy: "rank" })
      .then((d) => {
        if (active) setData(d);
      })
      .catch(() => {
        if (active) setError("Unable to load sprint assignments.");
      });
    return () => {
      active = false;
    };
  }, [projectId]);
  if (!data)
    return (
      <p role={error ? "alert" : "status"}>
        {error || "Loading sprint assignments…"}
      </p>
    );
  const groups = [
    { id: "backlog", label: "Backlog" },
    ...data.sprints
      .filter((s) => s.status !== "Completed")
      .map((s) => ({
        id: String(s.id),
        label: `${s.name} · ${s.status}`,
        disabled: !["Planned", "Active"].includes(s.status),
      })),
  ];
  const tasks = [
    ...data.backlog,
    ...data.sprints
      .filter((s) => s.status !== "Completed")
      .flatMap((s) => s.tasks),
  ];
  return (
    <MoveBoard
      label="Sprint assignments"
      groups={groups}
      disabled={data.project.can_manage_tasks === false}
      items={tasks.map((t) => ({
        id: t.id,
        label: t.title,
        group: t.sprint_id ? String(t.sprint_id) : "backlog",
        content: (
          <Link className="text-xs text-primary" to={`/pms/tasks/${t.id}`}>
            {t.task_key} · {t.status}
          </Link>
        ),
      }))}
      onMove={async ({ item, group, beforeId }) => {
        try {
          await arrangeTask(Number(item.id), {
            group_by: "sprint",
            sprint_id: group === "backlog" ? null : Number(group),
            before_id: beforeId,
          });
        } finally {
          setData(await backlogAPI.get(projectId, { sortBy: "rank" }));
        }
        onSaved?.();
      }}
    />
  );
}
