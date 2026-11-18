import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import type { PMSTask, PMSMentionUser } from "../types";
import { useSmartCreation } from "@/shared/creation/SmartCreationProvider";
export default function CreateTaskModal({
  isOpen,
  onClose,
  projectId,
  initialDueDate = "",
  initialWorkType = "Task",
  initialTitle = "",
  initialStatus = "",
  onTaskCreated,
}: {
  isOpen: boolean;
  onClose: () => void;
  projectId: number;
  onTaskCreated: (task: PMSTask, createAnother?: boolean) => void;
  workspacePeople?: PMSMentionUser[];
  projects?: { id: number; name: string }[];
  initialDueDate?: string;
  initialWorkType?: "Task" | "Story" | "Bug";
  initialTitle?: string;
  initialStatus?: string;
}) {
  const navigate = useNavigate();
  const creation = useSmartCreation();
  const opened = useRef(false);
  useEffect(() => {
    if (!isOpen) {
      opened.current = false;
      return;
    }
    if (opened.current) return;
    opened.current = true;
    const query = new URLSearchParams();
    if (projectId) query.set("projectId", String(projectId));
    if (initialDueDate) query.set("dueDate", initialDueDate);
    if (initialStatus) query.set("status", initialStatus);
    if (initialTitle) query.set("title", initialTitle);
    if (initialWorkType) query.set("workType", initialWorkType);
    const destination = `/pms/tasks/new?${query}`;
    const handled = creation?.open(destination, record => { if (record) onTaskCreated(record as PMSTask); });
    onClose();
    if (!handled) navigate(destination);
  }, [
    isOpen,
    projectId,
    initialDueDate,
    initialWorkType,
    initialTitle,
    initialStatus,
    onClose,
    navigate,
    creation,
    onTaskCreated,
  ]);
  return null;
}
