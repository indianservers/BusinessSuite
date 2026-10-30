import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import type { PMSTask, PMSMentionUser } from "../types";
export default function CreateTaskModal({
  isOpen,
  onClose,
  projectId,
  initialDueDate = "",
  initialWorkType = "Task",
  initialTitle = "",
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
}) {
  const navigate = useNavigate();
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
    if (initialTitle) query.set("title", initialTitle);
    if (initialWorkType) query.set("workType", initialWorkType);
    onClose();
    navigate(`/pms/tasks/new?${query}`);
  }, [
    isOpen,
    projectId,
    initialDueDate,
    initialWorkType,
    initialTitle,
    onClose,
    navigate,
  ]);
  return null;
}
