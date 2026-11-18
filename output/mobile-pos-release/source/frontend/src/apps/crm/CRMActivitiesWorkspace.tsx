import { Navigate, useSearchParams } from "react-router-dom";
import { sharedNotesPath } from "@/lib/shared-notes";
import TaskExperiencePage from "@/apps/project-management/pages/TaskExperiencePage";

export default function CRMActivitiesWorkspace() {
  const [params] = useSearchParams();
  if (params.get("workspaceView") === "notes") {
    const query = new URLSearchParams();
    for (const key of ["note", "new", "project", "task"]) {
      const value = params.get(key);
      if (value) query.set(key, value);
    }
    return <Navigate replace to={sharedNotesPath + (query.size ? `?${query}` : "")} />;
  }
  return <TaskExperiencePage />;
}
