import { useRef, useState } from "react";
import * as Popover from "@radix-ui/react-popover";
import RecordActions, { RecordSummary } from "./RecordActions";
import {
  personName,
  taskBucket,
  type WorkTask,
  type WorkspaceMember,
} from "../pages/workspaceTypes";

export default function CalendarTaskChip({
  task,
  sourceDay,
  color,
  canEdit,
  busy,
  members,
  projectName,
  onOpen,
  onChanged,
}: {
  task: WorkTask;
  sourceDay?: string;
  color: string;
  canEdit: boolean;
  busy: boolean;
  members: WorkspaceMember[];
  projectName?: string;
  onOpen: (id: number) => void;
  onChanged?: () => void | Promise<void>;
}) {
  const [quickView, setQuickView] = useState(false);
  const dragging = useRef(false);
  const record = { ...task, key: task.task_key, project_name: projectName };
  const people = members
    .filter((member) => member.role !== "Guest")
    .map((member) => ({ id: member.user_id, name: personName(member.email) }));
  const open = () => {
    setQuickView(false);
    onOpen(task.id);
  };
  return (
    <RecordActions
      record={record}
      people={people}
      canEdit={canEdit && !busy}
      preview={!quickView}
      onOpen={open}
      onChanged={onChanged}
    >
      {(menu) => (
        <div
          className="pms-calendar-chip"
          onClick={(e) => e.stopPropagation()}
          onDoubleClick={(e) => e.stopPropagation()}
        >
          <Popover.Root open={quickView} onOpenChange={setQuickView}>
            <Popover.Trigger asChild>
              <button
                className={`wc-task ${taskBucket(task.status) === "Done" ? "done" : ""}`}
                style={{ borderLeftColor: color }}
                draggable={canEdit && !busy}
                onDragStart={(e) => {
                  dragging.current = true;
                  setQuickView(false);
                  e.dataTransfer.setData("text/plain", String(task.id));
                  if (sourceDay)
                    e.dataTransfer.setData(
                      "application/x-karyaflow-day",
                      sourceDay,
                    );
                  e.dataTransfer.effectAllowed = "move";
                }}
                onDragEnd={() => {
                  setTimeout(() => {
                    dragging.current = false;
                  }, 100);
                }}
                onClick={(e) => {
                  if (dragging.current) e.preventDefault();
                }}
                onDoubleClick={(e) => {
                  e.preventDefault();
                  open();
                }}
                title={`${task.task_key}: ${task.title} · Click for preview, double-click to open`}
              >
                <span>
                  {taskBucket(task.status) === "Done" ? "✓ " : ""}
                  {task.title}
                </span>
              </button>
            </Popover.Trigger>
            <Popover.Portal>
              <Popover.Content
                className="pms-calendar-preview"
                aria-label={`Task preview: ${task.title}`}
                align="start"
                sideOffset={8}
                collisionPadding={14}
                onOpenAutoFocus={(e) => e.preventDefault()}
                onClick={(e) => e.stopPropagation()}
                onDoubleClick={(e) => e.stopPropagation()}
              >
                <RecordSummary record={record} people={people} />
                <footer>
                  <button className="pms-preview-open" onClick={open}>
                    Open task
                  </button>
                  <Popover.Close aria-label="Close task preview">
                    Close
                  </Popover.Close>
                </footer>
              </Popover.Content>
            </Popover.Portal>
          </Popover.Root>
          {menu}
        </div>
      )}
    </RecordActions>
  );
}
