import { RichTextContent } from "@/components/rich-text/RichTextContent";
import {
  useEffect,
  useId,
  useRef,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import * as Context from "@radix-ui/react-context-menu";
import * as Dropdown from "@radix-ui/react-dropdown-menu";
import * as Dialog from "@radix-ui/react-dialog";
import {
  MoreHorizontal,
  ArrowUpRight,
  Copy,
  Check,
  ChevronRight,
  Trash2,
  X,
} from "lucide-react";
import { projectsAPI, tasksAPI } from "../services/api";
import { workspaceError } from "../pages/workspaceTypes";
import type { TaskPriority, TaskStatus } from "../types";
import "./RecordActions.css";

export type RecordInfo = {
  id: number;
  title: string;
  key?: string;
  description?: string | null;
  status?: string;
  priority?: string;
  due_date?: string | null;
  start_date?: string | null;
  project_id?: number;
  project_name?: string;
  assignee_user_ids?: number[];
  assignee_user_id?: number | null;
};
type Action = {
  label: string;
  icon?: ReactNode;
  run?: () => void;
  danger?: boolean;
  selected?: boolean;
  children?: Action[];
};
type Props = {
  record: RecordInfo;
  kind?: "task" | "project";
  canEdit?: boolean;
  preview?: boolean;
  people?: { id: number; name: string }[];
  onOpen?: () => void;
  onChanged?: (deleted?: boolean) => void | Promise<void>;
  children: (menuButton: ReactNode) => ReactElement;
};
const done = (status?: string) =>
  ["Done", "Completed", "Closed", "Resolved"].includes(status || "");
const dateLabel = (value?: string | null) =>
  value
    ? new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : "Not scheduled";

export function RecordSummary({
  record,
  kind = "task",
  people = [],
}: {
  record: RecordInfo;
  kind?: "task" | "project";
  people?: Props["people"];
}) {
  const ids =
    record.assignee_user_ids ??
    (record.assignee_user_id ? [record.assignee_user_id] : []);
  return (
    <div className="pms-record-summary">
      <p className="pms-record-eyebrow">
        {kind === "task" ? "Task" : "Project"} · {record.key || `#${record.id}`}
      </p>
      <h3>{record.title}</h3>
      {record.project_name && (
        <p className="pms-record-project">{record.project_name}</p>
      )}
      <div className="pms-record-pills">
        {record.status && <span>{record.status}</span>}
        {record.priority && <span>{record.priority} priority</span>}
      </div>
      <div className="pms-record-description"><RichTextContent value={record.description || "No description added yet."}/></div>
      <dl>
        <div>
          <dt>Start</dt>
          <dd>{dateLabel(record.start_date)}</dd>
        </div>
        <div>
          <dt>Due</dt>
          <dd>{dateLabel(record.due_date)}</dd>
        </div>
        {kind === "task" && (
          <div>
            <dt>Assignees</dt>
            <dd>
              {ids.length
                ? ids
                    .map(
                      (id) =>
                        people.find((person) => person.id === id)?.name ||
                        `User #${id}`,
                    )
                    .join(", ")
                : "Unassigned"}
            </dd>
          </div>
        )}
      </dl>
    </div>
  );
}

export default function RecordActions({
  record,
  kind = "task",
  canEdit = false,
  preview = true,
  people,
  onOpen,
  onChanged,
  children,
}: Props) {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);
  const [contextGeneration, setContextGeneration] = useState(0);
  const contextTrigger = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!menuOpen && !contextOpen) return;
    const closeTopMenu = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopImmediatePropagation();
      setMenuOpen(false);
      if (contextOpen) {
        setContextOpen(false);
        setContextGeneration((value) => value + 1);
        requestAnimationFrame(() => contextTrigger.current?.focus());
      }
    };
    window.addEventListener("keydown", closeTopMenu, true);
    return () => window.removeEventListener("keydown", closeTopMenu, true);
  }, [menuOpen, contextOpen]);
  const [hoverOpen, setHoverOpen] = useState(false);
  const [previewPosition, setPreviewPosition] = useState({ left: 12, top: 12 });
  const hoverTimer = useRef<ReturnType<typeof setTimeout>>();
  const previewId = useId();
  const hidePreview = () => {
    clearTimeout(hoverTimer.current);
    setHoverOpen(false);
  };
  useEffect(() => {
    const hide = () => {
      clearTimeout(hoverTimer.current);
      setHoverOpen(false);
    };
    const onScroll = () => setHoverOpen(false);
    document.addEventListener("pointerdown", hide, true);
    document.addEventListener("scroll", onScroll, true);
    document.addEventListener("keydown", hide, true);
    window.addEventListener("resize", hide);
    window.addEventListener("pms:record-overlay", hide);
    return () => {
      clearTimeout(hoverTimer.current);
      document.removeEventListener("pointerdown", hide, true);
      document.removeEventListener("scroll", onScroll, true);
      document.removeEventListener("keydown", hide, true);
      window.removeEventListener("resize", hide);
      window.removeEventListener("pms:record-overlay", hide);
    };
  }, []);
  const [confirmTrash, setConfirmTrash] = useState(false);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [message, setMessage] = useState("");
  const href = `/pms/${kind === "task" ? "tasks" : "projects"}/${record.id}`;
  const open = () => {
    setHoverOpen(false);
    onOpen ? onOpen() : navigate(href);
  };
  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => setMessage(""), 6000);
      return () => clearTimeout(timer);
    }
  }, [message]);
  const run = async (
    operation: () => Promise<unknown>,
    success: string,
    deleted = false,
  ) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setHoverOpen(false);
    let saved = false;
    try {
      await operation();
      saved = true;
      setConfirmTrash(false);
      setMessage(success);
      await onChanged?.(deleted);
    } catch (e) {
      setMessage(
        saved
          ? `${success} Refresh the view to load the latest saved data.`
          : workspaceError(e),
      );
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };
  const copy = (value: string, success: string) => {
    if (!navigator.clipboard?.writeText) {
      setMessage(
        "Clipboard is unavailable. Open the record to copy its address.",
      );
      return;
    }
    void navigator.clipboard
      .writeText(value)
      .then(() => setMessage(success))
      .catch(() =>
        setMessage(
          "Clipboard access was blocked. Use Open in new tab to get the link.",
        ),
      );
  };
  const update = (changes: Parameters<typeof tasksAPI.update>[1]) =>
    void run(() => tasksAPI.update(record.id, changes), "Task updated.");
  const selectedIds =
    record.assignee_user_ids ??
    (record.assignee_user_id ? [record.assignee_user_id] : []);
  const actions: Action[] = [
    { label: `Open ${kind}`, icon: <ArrowUpRight size={15} />, run: open },
    {
      label: "Open in new tab",
      run: () => {
        window.open(href, "_blank", "noopener,noreferrer");
      },
    },
    {
      label: "Copy link",
      icon: <Copy size={15} />,
      run: () =>
        copy(new URL(href, window.location.origin).href, "Link copied."),
    },
    {
      label: `Copy ${kind} ID`,
      run: () => copy(record.key || String(record.id), "ID copied."),
    },
  ];
  if (kind === "project")
    actions.push(
      ...[
        ["Open board", "board"],
        ["Open timeline", "timeline"],
        ["Project analytics", "analytics"],
      ].map(([label, route]) => ({
        label,
        run: () => navigate(`${href}/${route}`),
      })),
    );
  if (kind === "project" && canEdit) actions.push({label:"Edit project", run:()=>navigate(`${href}/edit`)});
  if (kind === "task" && record.project_id)
    actions.push({
      label: "Go to project",
      run: () => navigate(`/pms/projects/${record.project_id}`),
    });
  if (kind === "task" && canEdit) {
    actions.push(
      {
        label: done(record.status) ? "Reopen task" : "Mark complete",
        icon: <Check size={15} />,
        run: () => update({ status: done(record.status) ? "To Do" : "Done" }),
      },
      {
        label: "Change status",
        children: ["To Do", "In Progress", "In Review", "Blocked", "Done"].map(
          (status) => ({
            label: status,
            selected: record.status === status,
            run: () => update({ status: status as TaskStatus }),
          }),
        ),
      },
      {
        label: "Change priority",
        children: ["Low", "Medium", "High", "Urgent", "Critical"].map(
          (priority) => ({
            label: priority,
            selected: record.priority === priority,
            run: () => update({ priority: priority as TaskPriority }),
          }),
        ),
      },
    );
    if (people)
      actions.push({
        label: "Assign people",
        children: [
          {
            label: "Unassign everyone",
            selected: !selectedIds.length,
            run: () => update({ assignee_user_ids: [] }),
          },
          ...people.map((person) => ({
            label: person.name,
            selected: selectedIds.includes(person.id),
            run: () =>
              update({
                assignee_user_ids: selectedIds.includes(person.id)
                  ? selectedIds.filter((id) => id !== person.id)
                  : [...selectedIds, person.id],
              }),
          })),
        ],
      });
    actions.push({
      label: "Duplicate task",
      icon: <Copy size={15} />,
      run: () =>
        void run(async () => {
          const original = await tasksAPI.get(record.id);
          await tasksAPI.create(original.project_id, {
            title: `Copy of ${original.title}`.slice(0, 220),
            task_key: `T-${crypto.randomUUID().slice(0, 8).toUpperCase()}`,
            description: original.description,
            priority: original.priority,
            status: "To Do",
            work_type:
              original.work_type === "Sub-task" ? "Task" : original.work_type,
            start_date: original.start_date,
            due_date: original.due_date,
            estimated_hours: original.estimated_hours,
            assignee_user_ids: original.assignee_user_ids,
          });
        }, "Task duplicated in the same project. Attachments and comments stay with the original."),
    });
  }
  if (canEdit) {
    actions.push({
      label: "Move to trash…",
      icon: <Trash2 size={15} />,
      danger: true,
      run: () => {
        setHoverOpen(false);
        setConfirmTrash(true);
      },
    });
  }
  function items(mode: "context" | "dropdown", list = actions): ReactNode {
    const M = mode === "context" ? Context : Dropdown;
    return list.map((action, index) =>
      action.children ? (
        <M.Sub key={action.label}>
          <M.SubTrigger className="pms-record-item" disabled={busy}>
            {action.label}
            <ChevronRight size={14} />
          </M.SubTrigger>
          <M.Portal>
            <M.SubContent className="pms-record-menu">
              {items(mode, action.children)}
            </M.SubContent>
          </M.Portal>
        </M.Sub>
      ) : (
        <M.Item
          key={action.label}
          disabled={busy}
          className={`pms-record-item ${action.danger ? "danger" : ""}`}
          onSelect={() => {
            action.run?.();
          }}
        >
          <span className="pms-record-item-icon">
            {action.selected ? <Check size={15} /> : action.icon}
          </span>
          <span>{action.label}</span>
          {index === 0 && mode === "context" && <kbd aria-hidden="true">↵</kbd>}
        </M.Item>
      ),
    );
  }
  const menuButton = (
    <Dropdown.Root
      open={menuOpen}
      onOpenChange={(value) => {
        setMenuOpen(value);
        if (value) {
          hidePreview();
          window.dispatchEvent(new Event("pms:record-overlay"));
        }
      }}
    >
      <Dropdown.Trigger asChild>
        <button
          type="button"
          className="pms-record-more"
          aria-label={`${kind === "task" ? "Task" : "Project"} actions for ${record.title}`}
          disabled={busy}
          onClick={(e) => e.stopPropagation()}
          onDoubleClick={(e) => e.stopPropagation()}
          onPointerDown={(e) => e.stopPropagation()}
        >
          <MoreHorizontal size={18} />
        </button>
      </Dropdown.Trigger>
      <Dropdown.Portal>
        <Dropdown.Content
          onEscapeKeyDown={(event) => {
            event.preventDefault();
            event.stopPropagation();
            setMenuOpen(false);
          }}
          className="pms-record-menu"
          align="end"
          sideOffset={6}
          collisionPadding={12}
          onClick={(e) => e.stopPropagation()}
        >
          {items("dropdown")}
        </Dropdown.Content>
      </Dropdown.Portal>
    </Dropdown.Root>
  );
  return (
    <>
      <Context.Root
        key={contextGeneration}
        modal={false}
        onOpenChange={(value) => {
          setContextOpen(value);
          if (value) {
            hidePreview();
            window.dispatchEvent(new Event("pms:record-overlay"));
          }
        }}
      >
        <Context.Trigger
          ref={contextTrigger}
          asChild
          aria-describedby={hoverOpen ? previewId : undefined}
          onPointerDown={hidePreview}
          onDragStart={hidePreview}
          onPointerLeave={hidePreview}
          onPointerEnter={(e) => {
            if (e.pointerType !== "mouse" || !preview || busy) return;
            const target = e.currentTarget;
            clearTimeout(hoverTimer.current);
            hoverTimer.current = setTimeout(() => {
              if (!target.isConnected) return;
              const rect = target.getBoundingClientRect();
              if (
                Array.from(
                  document.querySelectorAll('[role="menu"], [role="dialog"]'),
                ).some(
                  (element) =>
                    element.getClientRects().length > 0 &&
                    getComputedStyle(element).visibility !== "hidden" &&
                    !element.closest('[aria-hidden="true"]'),
                )
              )
                return;
              const width = Math.min(340, window.innerWidth - 28);
              setPreviewPosition({
                left: Math.max(
                  14,
                  Math.min(
                    rect.right + 12 + width < window.innerWidth
                      ? rect.right + 12
                      : rect.left - width - 12,
                    window.innerWidth - width - 14,
                  ),
                ),
                top: Math.max(14, Math.min(rect.top, window.innerHeight - 360)),
              });
              setHoverOpen(true);
            }, 550);
          }}
          onDoubleClick={(e) => {
            const control = (e.target as HTMLElement).closest(
              "button,a,input,textarea,select,[contenteditable=true]",
            );
            if (control && control !== e.currentTarget) return;
            e.stopPropagation();
            open();
          }}
          onContextMenuCapture={(e) => {
            if (
              (e.target as HTMLElement).closest(
                "input,textarea,[contenteditable=true]",
              )
            )
              e.stopPropagation();
          }}
          onKeyDown={(e) => {
            if (e.target !== e.currentTarget) return;
            if (!e.defaultPrevented && (e.key === "Enter" || e.key === " ")) {
              e.preventDefault();
              open();
              return;
            }
            if (e.key === "ContextMenu" || (e.shiftKey && e.key === "F10")) {
              e.preventDefault();
              const rect = e.currentTarget.getBoundingClientRect();
              e.currentTarget.dispatchEvent(
                new MouseEvent("contextmenu", {
                  bubbles: true,
                  clientX: rect.left + 24,
                  clientY: rect.top + 24,
                  button: 2,
                }),
              );
            }
          }}
        >
          {children(menuButton)}
        </Context.Trigger>
        <Context.Portal>
          <Context.Content
            className="pms-record-menu"
            collisionPadding={12}
            onClick={(e) => e.stopPropagation()}
          >
            {items("context")}
          </Context.Content>
        </Context.Portal>
      </Context.Root>
      {preview &&
        hoverOpen &&
        !menuOpen &&
        !contextOpen &&
        !confirmTrash &&
        !busy &&
        createPortal(
          <div
            id={previewId}
            role="tooltip"
            className="pms-record-preview"
            style={{
              position: "fixed",
              left: previewPosition.left,
              top: previewPosition.top,
              pointerEvents: "none",
            }}
          >
            <RecordSummary record={record} kind={kind} people={people} />
            <p className="pms-record-preview-hint">
              Double-click to open · Right-click for actions
            </p>
          </div>,
          document.body,
        )}
      <Dialog.Root
        open={confirmTrash}
        onOpenChange={(value) => {
          if (!busy) setConfirmTrash(value);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="pms-record-overlay" />
          <Dialog.Content
            className="pms-record-confirm"
            onClick={(e) => e.stopPropagation()}
          >
            <Dialog.Title>Move {kind} to trash?</Dialog.Title>
            <Dialog.Description>
              “{record.title}” will be removed from active views. You can
              restore it from Trash. {kind === "project" && "Its tasks and files remain attached and become accessible again when the project is restored."}
            </Dialog.Description>
            <div>
              <button disabled={busy} onClick={() => setConfirmTrash(false)}>
                Cancel
              </button>
              <button
                className="danger"
                disabled={busy}
                onClick={() =>
                  void run(
                    () => kind === "project" ? projectsAPI.delete(record.id) : tasksAPI.delete(record.id),
                    `${kind === "project" ? "Project" : "Task"} moved to trash.`,
                    true,
                  )
                }
              >
                {busy ? "Moving…" : "Move to trash"}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      {message &&
        createPortal(
          <div className="pms-record-feedback" role="status">
            {message}
            <button
              aria-label="Dismiss action message"
              onClick={() => setMessage("")}
            >
              <X size={14} />
            </button>
          </div>,
          document.body,
        )}
    </>
  );
}
