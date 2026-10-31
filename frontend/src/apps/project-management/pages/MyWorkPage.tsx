import MoveBoard from "@/components/interaction/MoveBoard";
import { arrangeTask } from "../components/SprintMoveBoard";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import * as Menu from "@radix-ui/react-dropdown-menu";
import {
  Activity,
  ArrowDownUp,
  CalendarDays,
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  Clock3,
  Columns3,
  Download,
  Filter,
  LayoutList,
  ListChecks,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Search,
  Users,
  X,
} from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { tasksAPI } from "../services/api";
import type { PMSTaskListItem, PMSTaskListResponse } from "../types";
import TaskAssignmentPanel, {
  AssignmentAvatar,
  type AssignmentPerson,
  type AssignmentGroup,
} from "../components/TaskAssignmentPanel";
import { usePMSRealtime } from "../realtime";
import { workspaceError } from "./workspaceTypes";
import "./MyWorkPage.css";

type WorkTask = PMSTaskListItem & {
  assignees: AssignmentPerson[];
  group_targets: AssignmentGroup[];
  workspace_name?: string;
  progress: number;
};
type WorkData = Omit<PMSTaskListResponse, "items" | "summary" | "filters"> & {
  items: WorkTask[];
  group_summaries: (AssignmentGroup & { total: number; completed: number })[];
  summary: {
    total: number;
    todo: number;
    in_progress: number;
    in_review: number;
    overdue: number;
    completed: number;
  };
  filters: PMSTaskListResponse["filters"] & {
    workspaces: { id: number; name: string }[];
    groups: AssignmentGroup[];
  };
};
const statuses = [
  "Backlog",
  "To Do",
  "In Progress",
  "In Review",
  "Blocked",
  "Done",
  "Cancelled",
];
const priorities = ["Low", "Medium", "High", "Urgent"];
const tabs = [
  ["mine", "My Tasks"],
  ["all", "All Tasks"],
  ["teams", "Team Tasks"],
  ["batches", "Intern Batches"],
  ["unassigned", "Unassigned"],
  ["approvals", "Approvals"],
  ["completed", "Completed"],
];
const columns = [
  "Task",
  "Project / Workspace",
  "Assignees",
  "Status",
  "Priority",
  "Due date",
  "Progress",
  "Actions",
];
const closed = (status: string) =>
  ["Done", "Completed", "Closed", "Cancelled"].includes(status);
const localDate = (d = new Date()) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
function MultiFilter({
  label,
  values,
  value,
  onChange,
}: {
  label: string;
  values: { id: string | number; name: string }[];
  value: string;
  onChange: (v: string) => void;
}) {
  const selected = value.split(",").filter(Boolean);
  return (
    <Menu.Root>
      <Menu.Trigger className="mw-multi-filter">
        {selected.length
          ? `${label.replace("All ", "")}: ${selected.length}`
          : label}
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Content className="mw-menu mw-filter-menu" sideOffset={6}>
          {values.map((v) => (
            <Menu.CheckboxItem
              key={v.id}
              checked={selected.includes(String(v.id))}
              onSelect={(e) => e.preventDefault()}
              onCheckedChange={(checked) =>
                onChange(
                  checked
                    ? [...selected, String(v.id)].join(",")
                    : selected.filter((id) => id !== String(v.id)).join(","),
                )
              }
            >
              {selected.includes(String(v.id)) ? "✓ " : "　"}
              {v.name}
            </Menu.CheckboxItem>
          ))}
        </Menu.Content>
      </Menu.Portal>
    </Menu.Root>
  );
}
function readStorage<T>(key: string, fallback: T): T {
  try {
    return JSON.parse(localStorage.getItem(key) || "null") ?? fallback;
  } catch {
    return fallback;
  }
}
function badgeClass(value: string) {
  return value === "In Progress"
    ? "blue"
    : value === "In Review"
      ? "purple"
      : ["High", "Urgent", "Blocked"].includes(value)
        ? "red"
        : value === "Medium"
          ? "amber"
          : closed(value) || value === "Low"
            ? "green"
            : "gray";
}
function Badge({ value }: { value: string }) {
  return (
    <span className={`mw-badge ${badgeClass(value)}`}>
      <i />
      {value}
    </span>
  );
}
function TaskMenu({
  label,
  value,
  values,
  disabled,
  onChange,
}: {
  label: string;
  value: string;
  values: string[];
  disabled: boolean;
  onChange: (v: string) => void;
}) {
  return (
    <Menu.Root>
      <Menu.Trigger disabled={disabled} aria-label={label}>
        <Badge value={value} />
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Content className="mw-menu" sideOffset={6}>
          {values.map((v) => (
            <Menu.Item key={v} onSelect={() => onChange(v)}>
              <Badge value={v} />
            </Menu.Item>
          ))}
        </Menu.Content>
      </Menu.Portal>
    </Menu.Root>
  );
}
function exportTasks(tasks: WorkTask[]) {
  const escape = (value: unknown) => {
    const s = String(value ?? "");
    return (
      '"' + (/^[=+@\-\t\r]/.test(s) ? "'" : "") + s.replace(/"/g, '""') + '"'
    );
  };
  const rows = [
    [
      "Task",
      "Title",
      "Project",
      "Assignees",
      "Groups",
      "Status",
      "Priority",
      "Due",
    ],
    ...tasks.map((t) => [
      t.task_key,
      t.title,
      t.project_name,
      t.assignees.map((p) => p.name).join("; "),
      t.group_targets.map((g) => g.name).join("; "),
      t.status,
      t.priority,
      t.due_date,
    ]),
  ];
  const url = URL.createObjectURL(
    new Blob(
      ["\uFEFF" + rows.map((row) => row.map(escape).join(",")).join("\r\n")],
      { type: "text/csv;charset=utf-8" },
    ),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = "my-work.csv";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export default function MyWorkPage() {
  const identity = useAuthStore((s) => s.user);
  const uid = identity?.id;
  const contextKey = JSON.stringify([
    uid,
    identity?.access?.companyId,
    identity?.role,
    identity?.access?.grants,
  ]);
  const lastContext = useRef(contextKey);
  const prefKey = `pms-my-work:${uid}:${identity?.access?.companyId || "default"}`;
  const [loadedPrefs, setLoadedPrefs] = useState(prefKey);
  const [params, setParams] = useSearchParams();
  const paramsRef = useRef(params);
  paramsRef.current = params;
  const view = params.get("workView") || "mine";
  const layout = params.get("layout") || "list";
  const [data, setData] = useState<WorkData>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [revision, setRevision] = useState(0);
  const [search, setSearch] = useState(params.get("search") || "");
  const [more, setMore] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const [assign, setAssign] = useState<WorkTask[]>([]);
  const [busy, setBusy] = useState(false);
  const [hidden, setHidden] = useState<string[]>(() =>
    readStorage(prefKey + ":columns", []),
  );
  const [widths, setWidths] = useState<Record<string, number>>(() =>
    readStorage(prefKey + ":widths", {}),
  );
  const [saved, setSaved] = useState<{ name: string; query: string }[]>(() =>
    readStorage(prefKey + ":views", []),
  );
  const [savingView, setSavingView] = useState(false);
  const [viewName, setViewName] = useState("");
  const [bulkField, setBulkField] = useState("status");
  const [bulkValue, setBulkValue] = useState("");
  const page = Math.max(1, Number(params.get("page")) || 1);
  const pageSize = Number(params.get("pageSize")) || 10;
  const change = (key: string, value: string) => {
    const next = new URLSearchParams(paramsRef.current);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.delete("page");
    paramsRef.current = next;
    setParams(next);
    setSelected([]);
  };
  const refresh = () => setRevision((r) => r + 1);
  usePMSRealtime({
    onEvent: (event) => {
      if (event.type.startsWith("task.") || event.type === "project.updated")
        refresh();
    },
    onFallbackPoll: refresh,
    showToast: false,
  });
  useEffect(() => {
    setSearch(params.get("search") || "");
  }, [params.get("search")]);
  useEffect(() => {
    const timer = setTimeout(() => {
      if (search !== (params.get("search") || "")) change("search", search);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    let active = true;
    if (lastContext.current !== contextKey) {
      setData(undefined);
      setAssign([]);
      setSelected([]);
      setNotice("");
      lastContext.current = contextKey;
    }
    setLoading(true);
    setError("");
    const query = Object.fromEntries(params);
    if (query.workspace && !query.workspaceId)
      query.workspaceId = query.workspace;
    if (query.owner && !query.assigneeIds) query.assigneeIds = query.owner;
    api
      .get<WorkData>("/project-management/tasks", {
        params: {
          ...query,
          workView: view,
          page,
          pageSize,
          referenceDate: localDate(),
        },
      })
      .then((r) => {
        if (active) setData(r.data);
      })
      .catch((e) => {
        if (active) {
          setError(workspaceError(e));
          setData(undefined);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [params.toString(), revision, contextKey]);
  useEffect(() => {
    if (loadedPrefs === prefKey) return;
    setHidden(readStorage(prefKey + ":columns", []));
    setWidths(readStorage(prefKey + ":widths", {}));
    setSaved(readStorage(prefKey + ":views", []));
    setLoadedPrefs(prefKey);
  }, [prefKey, loadedPrefs]);
  useEffect(() => {
    if (loadedPrefs !== prefKey) return;
    try {
      localStorage.setItem(prefKey + ":columns", JSON.stringify(hidden));
      localStorage.setItem(prefKey + ":widths", JSON.stringify(widths));
      localStorage.setItem(prefKey + ":views", JSON.stringify(saved));
    } catch {
      /* Browser storage may be unavailable. */
    }
  }, [hidden, widths, saved, prefKey, loadedPrefs]);
  const editable = (t: WorkTask) =>
    !!data?.filters.projects.find((p) => p.id === t.project_id)
      ?.can_manage_tasks;
  async function update(tasks: WorkTask[], payload: Record<string, unknown>) {
    setBusy(true);
    setError("");
    let successes = 0;
    const failed: string[] = [];
    for (const task of tasks) {
      try {
        await api.patch(
          `/project-management/management/tasks/${task.id}`,
          payload,
        );
        successes++;
      } catch (e) {
        failed.push(`${task.title}: ${workspaceError(e)}`);
      }
    }
    setNotice(
      `${successes} task${successes === 1 ? "" : "s"} updated${failed.length ? ` · ${failed.length} failed` : ""}`,
    );
    if (failed.length) setError(failed.join("\n"));
    setBusy(false);
    setSelected([]);
    refresh();
  }
  const items = data?.items || [];
  const chosen = items.filter((t) => selected.includes(t.id));
  function openAssignment(tasks: WorkTask[]) {
    setAssign(tasks);
  }
  const options = (
    key: string,
    label: string,
    values: { id: string | number; name: string }[],
  ) =>
    ["projectIds", "assigneeIds", "status", "priority"].includes(key) ? (
      <MultiFilter
        label={label}
        values={values}
        value={params.get(key) || ""}
        onChange={(v) => change(key, v)}
      />
    ) : (
      <select
        aria-label={label}
        value={params.get(key) || ""}
        onChange={(e) => change(key, e.target.value)}
      >
        <option value="">{label}</option>
        {values.map((v) => (
          <option key={v.id} value={v.id}>
            {v.name}
          </option>
        ))}
      </select>
    );
  const avatars = (task: WorkTask) => (
    <button
      className="mw-avatars"
      aria-label={`Assign ${task.title}`}
      disabled={!editable(task) || busy}
      onClick={() => openAssignment([task])}
    >
      {task.assignees.slice(0, 3).map((p) => (
        <AssignmentAvatar key={p.id} person={p} />
      ))}
      {task.assignees.length > 3 && (
        <span className="mw-avatar">+{task.assignees.length - 3}</span>
      )}
      {!task.assignees.length && (
        <span className="mw-unassigned">
          <Users size={15} />
          {task.group_targets.length ? "Group" : "Assign"}
        </span>
      )}
      {!!task.group_targets.length && (
        <span
          className="mw-group-count"
          title={task.group_targets.map((g) => g.name).join(", ")}
        >
          +{task.group_targets.length} group
          {task.group_targets.length > 1 ? "s" : ""}
        </span>
      )}
    </button>
  );
  const progress = (task: WorkTask) => (
    <div className="mw-progress">
      <progress
        aria-label={`Progress of ${task.title}`}
        max={100}
        value={task.progress}
      />
      <small>{task.progress}%</small>
    </div>
  );
  const card = (t: WorkTask) => (
    <article className="mw-task-card" key={t.id}>
      <div className="mw-card-top">
        <span>{t.task_key}</span>
        <Badge value={t.priority} />
      </div>
      <Link to={`/pms/tasks/${t.id}`}>{t.title}</Link>
      <small>
        {t.project_name} · {t.workspace_name}
      </small>
      {!!t.group_targets.length && (
        <small>{t.group_targets.map((g) => g.name).join(" · ")}</small>
      )}
      <div className="mw-card-bottom">
        {avatars(t)}
        <TaskMenu
          label={`Status of ${t.title}`}
          value={t.status}
          values={statuses}
          disabled={!editable(t) || busy}
          onChange={(v) => void update([t], { status: v })}
        />
      </div>
      {progress(t)}
      <small>
        {t.due_date ? `Due ${t.due_date}` : "No due date"}
        {t.completed_at ? ` · Completed ${t.completed_at.slice(0, 10)}` : ""}
      </small>
    </article>
  );
  const activeFilters = [...params.entries()].filter(
    ([k]) =>
      ![
        "layout",
        "workView",
        "page",
        "pageSize",
        "sortBy",
        "sortOrder",
        "workspace",
        "owner",
      ].includes(k),
  );
  const calendarDays = useMemo(() => {
    const month = params.get("month") || localDate().slice(0, 7);
    const first = new Date(month + "-01T12:00:00");
    first.setDate(first.getDate() - first.getDay());
    return Array.from({ length: 42 }, (_, index) => {
      const d = new Date(first);
      d.setDate(first.getDate() + index);
      return localDate(d);
    });
  }, [params.get("month")]);
  const visibleColumns = columns.filter((c) => !hidden.includes(c));
  return (
    <main className="mw-page">
      <header className="mw-heading">
        <div>
          <h1>My Work</h1>
          <p>
            Manage your tasks, approvals and deadlines across all projects and
            workspaces.
          </p>
        </div>
        <div className="mw-actions">
          <button
            aria-label="Refresh tasks"
            onClick={refresh}
            disabled={loading}
          >
            <RefreshCw size={16} />
          </button>
          <Link className="mw-primary" to="/pms/tasks/new">
            <Plus size={18} /> Add Task
          </Link>
        </div>
      </header>
      {error && (
        <div role="alert" className="mw-error">
          {error}
          <button
            onClick={() => {
              setError("");
              refresh();
            }}
          >
            Retry
          </button>
        </div>
      )}
      {notice && (
        <div role="status" className="mw-notice">
          {notice}
          <button
            aria-label="Dismiss notification"
            onClick={() => setNotice("")}
          >
            <X size={15} />
          </button>
        </div>
      )}
      <section className="mw-stats" aria-label="Task statistics">
        {[
          {
            label: "Total Tasks",
            key: "total",
            color: "purple",
            icon: ListChecks,
            filter: "",
            value: "",
          },
          {
            label: "To Do",
            key: "todo",
            color: "blue",
            icon: LayoutList,
            filter: "status",
            value: "To Do",
          },
          {
            label: "In Progress",
            key: "in_progress",
            color: "amber",
            icon: Clock3,
            filter: "status",
            value: "In Progress",
          },
          {
            label: "In Review",
            key: "in_review",
            color: "purple",
            icon: CheckCheck,
            filter: "status",
            value: "In Review",
          },
          {
            label: "Overdue",
            key: "overdue",
            color: "red",
            icon: Clock3,
            filter: "overdue",
            value: "true",
          },
          {
            label: "Completed",
            key: "completed",
            color: "green",
            icon: CircleCheck,
            filter: "workView",
            value: "completed",
          },
        ].map((s) => (
          <button
            className="mw-stat"
            key={s.key}
            onClick={() => {
              setParams((p) => {
                const n = new URLSearchParams(p);
                n.delete("status");
                n.delete("overdue");
                n.delete("page");
                if (s.filter) n.set(s.filter, s.value);
                return n;
              });
              setSelected([]);
            }}
          >
            <span className={`mw-stat-icon ${s.color}`}>
              <s.icon size={23} />
            </span>
            <span>
              <small>{s.label}</small>
              <strong>
                {loading
                  ? "…"
                  : (data?.summary[s.key as keyof WorkData["summary"]] ?? 0)}
              </strong>
            </span>
          </button>
        ))}
      </section>
      <nav className="mw-scope-tabs" aria-label="Task scope">
        {tabs.map(([key, name]) => (
          <button
            key={key}
            aria-current={view === key ? "page" : undefined}
            onClick={() => change("workView", key)}
          >
            {name}
          </button>
        ))}
      </nav>
      <div className="mw-view-toolbar">
        <nav className="mw-layout-tabs" aria-label="Task views">
          {[
            ["list", "Task List", LayoutList],
            ["board", "Board View", Columns3],
            ["calendar", "My Calendar", CalendarDays],
            ["activity", "Recent Activity", Activity],
          ].map(([key, label, Icon]) => {
            const ViewIcon = Icon as typeof LayoutList;
            return (
              <button
                key={String(key)}
                aria-pressed={layout === key}
                onClick={() => change("layout", String(key))}
              >
                <ViewIcon size={16} />
                {String(label)}
              </button>
            );
          })}
        </nav>
        <div className="mw-actions">
          <button onClick={() => setSavingView((v) => !v)}>Save view</button>
          <Menu.Root>
            <Menu.Trigger>
              <Columns3 size={15} /> Columns
            </Menu.Trigger>
            <Menu.Portal>
              <Menu.Content className="mw-menu" sideOffset={6}>
                {columns
                  .filter((c) => !["Task", "Actions"].includes(c))
                  .map((c) => (
                    <Menu.CheckboxItem
                      key={c}
                      checked={!hidden.includes(c)}
                      onSelect={(e) => e.preventDefault()}
                      onCheckedChange={(checked) =>
                        setHidden((v) =>
                          checked ? v.filter((x) => x !== c) : [...v, c],
                        )
                      }
                    >
                      {!hidden.includes(c) ? "✓ " : "　"}
                      {c}
                    </Menu.CheckboxItem>
                  ))}
              </Menu.Content>
            </Menu.Portal>
          </Menu.Root>
        </div>
      </div>
      {savingView && (
        <form
          className="mw-save-view"
          onSubmit={(e) => {
            e.preventDefault();
            setSaved((v) => [
              ...v.filter((s) => s.name !== viewName.trim()),
              { name: viewName.trim(), query: params.toString() },
            ]);
            setSavingView(false);
            setViewName("");
          }}
        >
          <input
            required
            maxLength={80}
            aria-label="Saved view name"
            placeholder="Name this view"
            value={viewName}
            onChange={(e) => setViewName(e.target.value)}
          />
          <button type="submit" className="mw-primary">
            Save on this browser
          </button>
        </form>
      )}
      {!!saved.length && (
        <div className="mw-chips">
          {saved.map((s) => (
            <span key={s.name}>
              <button
                onClick={() => {
                  setParams(new URLSearchParams(s.query));
                  setSelected([]);
                }}
              >
                {s.name}
              </button>
              <button
                aria-label={`Delete saved view ${s.name}`}
                onClick={() =>
                  setSaved((v) => v.filter((x) => x.name !== s.name))
                }
              >
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
      )}
      <section className="mw-filters" aria-label="Task filters">
        <label className="mw-search">
          <Search size={16} />
          <input
            aria-label="Search tasks"
            placeholder="Search tasks by title, key, description…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        {options(
          "workspaceId",
          "All workspaces",
          data?.filters.workspaces || [],
        )}
        {options("projectIds", "All projects", data?.filters.projects || [])}
        {options("assigneeIds", "All assignees", data?.filters.assignees || [])}
        {options(
          "status",
          "All statuses",
          statuses.map((s) => ({ id: s, name: s })),
        )}
        {options(
          "priority",
          "All priorities",
          priorities.map((s) => ({ id: s, name: s })),
        )}
        <label className="mw-date">
          <span>Due on / before</span>
          <input
            aria-label="Due on or before"
            type="date"
            value={params.get("dueTo") || ""}
            onChange={(e) => change("dueTo", e.target.value)}
          />
        </label>
        <button aria-expanded={more} onClick={() => setMore((v) => !v)}>
          <Filter size={15} /> More filters
        </button>
      </section>
      {more && (
        <section className="mw-more-filters">
          {options(
            "teamId",
            "All teams",
            data?.filters.groups.filter((g) => g.kind === "teams") || [],
          )}
          {options(
            "batchId",
            "All batches",
            data?.filters.groups.filter((g) => g.kind === "batches") || [],
          )}
          {options("reporterId", "Created by", data?.filters.reporters || [])}
          {options(
            "workType",
            "Task type",
            ["Task", "Story", "Bug", "Epic", "Sub-task"].map((s) => ({
              id: s,
              name: s,
            })),
          )}
          <label>
            <input
              type="checkbox"
              checked={params.get("overdue") === "true"}
              onChange={(e) =>
                change("overdue", e.target.checked ? "true" : "")
              }
            />{" "}
            Overdue only
          </label>
          <Link to="/pms/reviews">Open approval inbox</Link>
        </section>
      )}
      {!!activeFilters.length && (
        <div className="mw-chips">
          {activeFilters.map(([key, value]) => (
            <button key={key} onClick={() => change(key, "")}>
              {key}: {value}
              <X size={12} />
            </button>
          ))}
          <button
            onClick={() => {
              setParams({ workView: view, layout });
              setSearch("");
              setSelected([]);
            }}
          >
            Clear filters
          </button>
        </div>
      )}
      {!!chosen.length && (
        <section className="mw-bulk" aria-label="Bulk task actions">
          <strong>{chosen.length} selected</strong>
          <button onClick={() => openAssignment(chosen)}>
            <Users size={16} /> Assign people / groups
          </button>
          <select
            aria-label="Bulk field"
            value={bulkField}
            onChange={(e) => {
              setBulkField(e.target.value);
              setBulkValue("");
            }}
          >
            <option value="status">Status</option>
            <option value="priority">Priority</option>
            <option value="due_date">Due date</option>
            <option value="project_id">Move to project</option>
          </select>
          {bulkField === "due_date" ? (
            <input
              aria-label="Bulk due date"
              type="date"
              value={bulkValue}
              onChange={(e) => setBulkValue(e.target.value)}
            />
          ) : (
            <select
              aria-label="Bulk value"
              value={bulkValue}
              onChange={(e) => setBulkValue(e.target.value)}
            >
              <option value="">Choose value</option>
              {(bulkField === "project_id"
                ? data?.filters.projects
                    .filter((p) => p.can_manage_tasks)
                    .map((p) => ({ id: String(p.id), name: p.name })) || []
                : (bulkField === "status" ? statuses : priorities).map((s) => ({
                    id: s,
                    name: s,
                  }))
              ).map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          )}
          <button
            disabled={busy || !bulkValue}
            onClick={() =>
              void update(chosen, {
                [bulkField]:
                  bulkField === "project_id" ? Number(bulkValue) : bulkValue,
              })
            }
          >
            Apply
          </button>
          <button onClick={() => exportTasks(chosen)}>
            <Download size={15} /> Export
          </button>
          <button
            disabled={busy}
            onClick={() => {
              if (!window.confirm(`Delete ${chosen.length} selected tasks?`))
                return;
              setBusy(true);
              void (async () => {
                const failures: string[] = [];
                let successes = 0;
                for (const task of chosen) {
                  try {
                    await tasksAPI.delete(task.id);
                    successes++;
                  } catch (e) {
                    failures.push(`${task.title}: ${workspaceError(e)}`);
                  }
                }
                setNotice(`${successes} deleted · ${failures.length} failed`);
                if (failures.length) setError(failures.join("\n"));
                setBusy(false);
                setSelected([]);
                refresh();
              })();
            }}
          >
            Delete selected
          </button>
          <button aria-label="Clear selection" onClick={() => setSelected([])}>
            <X size={16} />
          </button>
        </section>
      )}
      {view === "approvals" && (
        <div className="mw-more-filters">
          <CheckCheck size={17} />
          <span>Tasks awaiting review are shown below.</span>
          <Link to="/pms/reviews">
            Open pending approvals and work submissions
          </Link>
        </div>
      )}
      {(view === "teams" || view === "batches") && (
        <section className="mw-group-summaries" aria-label="Group progress">
          {data?.group_summaries
            .filter((g) => g.kind === view)
            .map((g) => (
              <button
                key={(g.kind || "group") + g.id}
                onClick={() =>
                  change(view === "teams" ? "teamId" : "batchId", String(g.id))
                }
              >
                <strong>{g.name}</strong>
                <small>
                  {g.member_count} members · {g.completed} / {g.total} tasks
                  completed
                </small>
                <progress
                  aria-label={`Progress for ${g.name}`}
                  value={g.completed}
                  max={g.total || 1}
                />
              </button>
            ))}
        </section>
      )}
      <section className="mw-results" aria-busy={loading}>
        {loading ? (
          <div className="mw-skeleton" role="status" aria-label="Loading tasks">
            {Array.from({ length: 6 }, (_, i) => (
              <div key={i} />
            ))}
          </div>
        ) : layout === "activity" ? (
          <div className="mw-activity">
            {data?.activity?.map((a) => (
              <article key={a.id}>
                <span className="mw-stat-icon purple">
                  <Activity size={17} />
                </span>
                <div>
                  <Link to={`/pms/tasks/${a.task_id}`}>{a.summary}</Link>
                  <small>
                    {a.actor_name} ·{" "}
                    {new Date(
                      /(?:Z|[+-]\d{2}:\d{2})$/.test(a.created_at)
                        ? a.created_at
                        : a.created_at + "Z",
                    ).toLocaleString()}
                  </small>
                </div>
              </article>
            ))}
            {!data?.activity?.length && (
              <p className="mw-empty">No recent task activity in this view.</p>
            )}
          </div>
        ) : !items.length ? (
          <div className="mw-empty">
            <ListChecks size={32} />
            <h2>No tasks in this view</h2>
            <p>Adjust your filters or add a task to get started.</p>
            <Link to="/pms/tasks/new" className="mw-primary">
              <Plus size={16} /> Add Task
            </Link>
          </div>
        ) : layout === "board" ? (
          <MoveBoard label="My Work status board" groups={statuses.map(s => ({ id: s, label: s }))} disabled={busy} items={[...items].sort((a,b) => (a.position || 0) - (b.position || 0)).map(t => ({ id: t.id, label: t.title, group: t.status, disabled: !editable(t), content: <Link className="text-xs text-primary" to={`/pms/tasks/${t.id}`}>{t.task_key} · {t.project_name}</Link> }))} onMove={async ({ item, group, beforeId }) => { await arrangeTask(Number(item.id), { group_by: "status", status: group, before_id: items.find(t=>t.id===beforeId)?.project_id === items.find(t=>t.id===item.id)?.project_id ? beforeId : undefined }); refresh(); }} />
        ) : layout === "calendar" ? (
          <>
            <div className="mw-calendar-heading">
              <CalendarDays size={18} />
              <input
                aria-label="Calendar month"
                type="month"
                value={params.get("month") || localDate().slice(0, 7)}
                onChange={(e) => {
                  const month = e.target.value;
                  if (!month) return;
                  setParams((p) => {
                    const n = new URLSearchParams(p);
                    n.set("month", month);
                    n.set("dueFrom", month + "-01");
                    const end = new Date(month + "-01T12:00:00");
                    end.setMonth(end.getMonth() + 1);
                    end.setDate(0);
                    n.set("dueTo", localDate(end));
                    n.delete("page");
                    return n;
                  });
                  setSelected([]);
                }}
              />
              <span>Tasks with a due date · current result page</span>
            </div>
            <div className="mw-calendar">
              {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
                <strong key={d}>{d}</strong>
              ))}
              {calendarDays.map((day) => (
                <div key={day} className={day === localDate() ? "today" : ""}>
                  <time dateTime={day}>{Number(day.slice(-2))}</time>
                  {items
                    .filter((t) => t.due_date === day)
                    .map((t) => (
                      <Link
                        key={t.id}
                        to={`/pms/tasks/${t.id}`}
                        title={t.title}
                      >
                        {t.title}
                      </Link>
                    ))}
                </div>
              ))}
            </div>
          </>
        ) : (
          <>
            <div className="mw-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>
                      <input
                        aria-label="Select all editable tasks on this page"
                        type="checkbox"
                        checked={
                          !!items.filter(editable).length &&
                          items
                            .filter(editable)
                            .every((t) => selected.includes(t.id))
                        }
                        onChange={(e) =>
                          setSelected(
                            e.target.checked
                              ? items.filter(editable).map((t) => t.id)
                              : [],
                          )
                        }
                      />
                    </th>
                    {visibleColumns.map((c) => (
                      <th key={c} style={{ width: widths[c] }}>
                        <button
                          onClick={() => {
                            const key =
                              c === "Task"
                                ? "title"
                                : c === "Due date"
                                  ? "dueDate"
                                  : c.toLowerCase();
                            if (
                              ![
                                "title",
                                "dueDate",
                                "status",
                                "priority",
                              ].includes(key)
                            )
                              return;
                            setParams((p) => {
                              const n = new URLSearchParams(p);
                              n.set("sortBy", key);
                              n.set(
                                "sortOrder",
                                p.get("sortOrder") === "asc" ? "desc" : "asc",
                              );
                              return n;
                            });
                          }}
                        >
                          {c}
                          {["Task", "Status", "Priority", "Due date"].includes(
                            c,
                          ) && <ArrowDownUp size={11} />}
                        </button>
                        <span
                          className="mw-resize"
                          role="separator"
                          aria-label={`Resize ${c}`}
                          onPointerDown={(e) => {
                            e.preventDefault();
                            const start = e.clientX;
                            const initial =
                              e.currentTarget.parentElement!.getBoundingClientRect()
                                .width;
                            const move = (ev: PointerEvent) =>
                              setWidths((w) => ({
                                ...w,
                                [c]: Math.max(80, initial + ev.clientX - start),
                              }));
                            const stop = () => {
                              window.removeEventListener("pointermove", move);
                              window.removeEventListener("pointerup", stop);
                            };
                            window.addEventListener("pointermove", move);
                            window.addEventListener("pointerup", stop);
                          }}
                        />
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {items.map((t) => (
                    <tr key={t.id} data-selected={selected.includes(t.id)}>
                      <td>
                        <input
                          type="checkbox"
                          aria-label={`Select ${t.title}`}
                          disabled={!editable(t) || busy}
                          checked={selected.includes(t.id)}
                          onChange={(e) =>
                            setSelected((v) =>
                              e.target.checked
                                ? [...v, t.id]
                                : v.filter((id) => id !== t.id),
                            )
                          }
                        />
                      </td>
                      {visibleColumns.map((c) => (
                        <td key={c}>
                          {c === "Task" ? (
                            <div className="mw-task-title">
                              <Link title={t.title} to={`/pms/tasks/${t.id}`}>
                                {t.title}
                              </Link>
                              <small>
                                {t.task_key} · {t.work_type}
                              </small>
                              {!!t.group_targets.length && (
                                <small>
                                  {t.group_targets
                                    .map((g) => g.name)
                                    .join(" · ")}
                                </small>
                              )}
                            </div>
                          ) : c === "Project / Workspace" ? (
                            <div className="mw-project">
                              {t.is_general ? <span>General tasks</span> : <Link to={`/pms/projects/${t.project_id}`}>{t.project_name}</Link>}
                              <small>{t.workspace_name}</small>
                            </div>
                          ) : c === "Assignees" ? (
                            avatars(t)
                          ) : c === "Status" ? (
                            <TaskMenu
                              label={`Status of ${t.title}`}
                              value={t.status}
                              values={statuses}
                              disabled={!editable(t) || busy}
                              onChange={(v) => void update([t], { status: v })}
                            />
                          ) : c === "Priority" ? (
                            <TaskMenu
                              label={`Priority of ${t.title}`}
                              value={t.priority}
                              values={priorities}
                              disabled={!editable(t) || busy}
                              onChange={(v) =>
                                void update([t], { priority: v })
                              }
                            />
                          ) : c === "Due date" ? (
                            <span
                              className={`mw-due ${t.due_date && t.due_date < localDate() && !closed(t.status) ? "overdue" : ""}`}
                            >
                              <CalendarDays size={14} />
                              {t.due_date
                                ? new Date(
                                    t.due_date + "T12:00:00",
                                  ).toLocaleDateString("en-GB", {
                                    day: "2-digit",
                                    month: "short",
                                    year: "numeric",
                                  })
                                : "No date"}
                            </span>
                          ) : c === "Progress" ? (
                            progress(t)
                          ) : (
                            <Menu.Root>
                              <Menu.Trigger
                                aria-label={`Actions for ${t.title}`}
                              >
                                <MoreHorizontal size={19} />
                              </Menu.Trigger>
                              <Menu.Portal>
                                <Menu.Content className="mw-menu">
                                  <Menu.Item asChild>
                                    <Link to={`/pms/tasks/${t.id}`}>
                                      Open full task
                                    </Link>
                                  </Menu.Item>
                                  <Menu.Item
                                    disabled={!editable(t)}
                                    onSelect={() => openAssignment([t])}
                                  >
                                    Assign people / groups
                                  </Menu.Item>
                                  <Menu.Item onSelect={() => exportTasks([t])}>
                                    Export task
                                  </Menu.Item>
                                  <Menu.Item
                                    disabled={!editable(t)}
                                    onSelect={() => {
                                      if (
                                        window.confirm(`Delete “${t.title}”?`)
                                      ) {
                                        setBusy(true);
                                        void tasksAPI
                                          .delete(t.id)
                                          .then(() => {
                                            refresh();
                                            setNotice("Task deleted");
                                          })
                                          .catch((e) =>
                                            setError(workspaceError(e)),
                                          )
                                          .finally(() => setBusy(false));
                                      }
                                    }}
                                  >
                                    Delete task
                                  </Menu.Item>
                                </Menu.Content>
                              </Menu.Portal>
                            </Menu.Root>
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mw-mobile-cards">{items.map(card)}</div>
          </>
        )}
        <footer className="mw-pagination">
          <span>
            {data?.total
              ? `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, data.total)} of ${data.total} tasks`
              : "0 tasks"}
            {layout === "board" ? " · Board shows this page" : ""}
          </span>
          <div>
            <select
              aria-label="Tasks per page"
              value={pageSize}
              onChange={(e) => change("pageSize", e.target.value)}
            >
              {[10, 25, 50, 100].map((n) => (
                <option key={n} value={n}>
                  {n} per page
                </option>
              ))}
            </select>
            <button
              aria-label="Previous page"
              disabled={page <= 1 || loading}
              onClick={() => change("page", String(page - 1))}
            >
              <ChevronLeft size={18} />
            </button>
            <strong>{page}</strong>
            <button
              aria-label="Next page"
              disabled={!data || page >= data.pages || loading}
              onClick={() => change("page", String(page + 1))}
            >
              <ChevronRight size={18} />
            </button>
          </div>
        </footer>
      </section>
      {!!assign.length && (
        <TaskAssignmentPanel
          tasks={assign}
          onClose={() => setAssign([])}
          onSaved={() => {
            refresh();
            setNotice("Assignment changes processed");
            setSelected([]);
          }}
        />
      )}
    </main>
  );
}
