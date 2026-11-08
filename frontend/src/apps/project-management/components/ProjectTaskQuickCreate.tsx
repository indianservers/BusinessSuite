import { useEffect, useRef } from "react";
import { useSmartCreation } from "@/shared/creation/SmartCreationProvider";
import { useNavigate } from "react-router-dom";

type TaskQuickCreateProps = { close: () => void; saved: () => void; initialProjectId?: number; workspaceId?: number; initialWorkType?: "Task" | "Story" | "Bug" };

/** Every task entry point uses the suite's shared creation surface. */
export default function TaskQuickCreate(props: TaskQuickCreateProps) {
  const creation = useSmartCreation();
  const navigate = useNavigate();
  const attempted = useRef(false);
  useEffect(() => {
    if (attempted.current) return;
    attempted.current = true;
    const params = new URLSearchParams({ workType: props.initialWorkType || "Task" });
    if (props.initialProjectId) params.set("projectId", String(props.initialProjectId));
    if (props.workspaceId) params.set("workspace", String(props.workspaceId));
    const destination = `/pms/tasks/new?${params}`;
    const handled = creation?.open(destination, props.saved);
    props.close();
    if (!handled) navigate(destination);
  }, [creation, navigate, props.initialProjectId, props.workspaceId, props.initialWorkType, props.saved, props.close]);
  return null;
}
