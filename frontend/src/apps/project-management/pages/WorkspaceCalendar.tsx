import { useState } from "react";
import {
  taskAssignees,
  taskBucket,
  personName,
  type WorkTask,
  type WorkspaceMember,
  type WorkspaceProject,
} from "./workspaceTypes";
import "./WorkspaceCalendar.css";

export const dateKey = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const date = (s: string) => new Date(`${s}T12:00:00`);
const shift = (s: string, days: number) => {
  const d = date(s);
  d.setDate(d.getDate() + days);
  return dateKey(d);
};
const colors = ["#2563eb", "#7c3aed", "#047857", "#be185d", "#b45309"];
type Props = {
  tasks: WorkTask[];
  members: WorkspaceMember[];
  projects: WorkspaceProject[];
  canEdit: boolean;
  onOpen: (id: number) => void;
  onCreate: (day: string, project: string) => void;
  onUpdate: (task: WorkTask, changes: Partial<WorkTask>) => Promise<boolean>;
};
export default function WorkspaceCalendar({
  tasks,
  members,
  projects,
  canEdit,
  onOpen,
  onCreate,
  onUpdate,
}: Props) {
  const [anchor, setAnchor] = useState(dateKey(new Date()));
  const [mode, setMode] = useState("month");
  const [project, setProject] = useState("");
  const [search, setSearch] = useState("");
  const [assignee, setAssignee] = useState("");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [settings, setSettings] = useState(false);
  const [sidebar, setSidebar] = useState(true);
  const [prefs, setPrefs] = useState(() => {
    try {
      return {
        weekends: true,
        monday: true,
        completed: true,
        compact: false,
        color: "project",
        ...JSON.parse(localStorage.getItem("pms-workspace-calendar") || "{}"),
      };
    } catch {
      return {
        weekends: true,
        monday: true,
        completed: true,
        compact: false,
        color: "project",
      };
    }
  });
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [undo, setUndo] = useState<{
    task: WorkTask;
    changes: Partial<WorkTask>;
  } | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const today = dateKey(new Date()),
    current = date(anchor),
    weekOffset = (current.getDay() + (prefs.monday ? 6 : 0)) % 7;
  const first = new Date(current.getFullYear(), current.getMonth(), 1);
  const gridStart =
    mode === "month"
      ? shift(dateKey(first), -(first.getDay() + (prefs.monday ? 6 : 0)) % 7)
      : mode === "week"
        ? shift(anchor, -weekOffset)
        : anchor;
  const days = Array.from(
    { length: mode === "month" ? 42 : mode === "week" ? 7 : 1 },
    (_, i) => shift(gridStart, i),
  ).filter(
    (s) =>
      mode === "day" || prefs.weekends || ![0, 6].includes(date(s).getDay()),
  );
  const filtered = tasks.filter(
    (t) =>
      (!project || t.project_id === Number(project)) &&
      (!assignee ||
        (assignee === "none"
          ? !taskAssignees(t).length
          : taskAssignees(t).includes(Number(assignee)))) &&
      (!status || t.status === status) &&
      (!priority || t.priority === priority) &&
      (prefs.completed || taskBucket(t.status) !== "Done") &&
      `${t.title} ${t.task_key} ${t.description || ""}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  const scheduled = filtered.filter((t) => t.due_date || t.start_date),
    unscheduled = filtered.filter((t) => !t.due_date && !t.start_date);
  const displayed =
    mode === "agenda"
      ? scheduled
          .filter((t) => (t.due_date || t.start_date || "") >= anchor)
          .sort((a, b) =>
            (a.due_date || a.start_date || "").localeCompare(
              b.due_date || b.start_date || "",
            ),
          )
      : scheduled.filter((t) =>
          days.some(
            (d) =>
              d >= (t.start_date || t.due_date || "") &&
              d <= (t.due_date || t.start_date || ""),
          ),
        );
  function preference(key: string, value: unknown) {
    const next = { ...prefs, [key]: value };
    setPrefs(next);
    try {
      localStorage.setItem("pms-workspace-calendar", JSON.stringify(next));
    } catch {
      setMessage(
        "Display changed for this session; browser storage is unavailable.",
      );
    }
  }
  function navigate(direction: number) {
    const d = date(anchor);
    if (mode === "month") {
      d.setDate(1);
      d.setMonth(d.getMonth() + direction);
    } else d.setDate(d.getDate() + direction * (mode === "week" ? 7 : 1));
    setAnchor(dateKey(d));
  }
  async function save(t: WorkTask, changes: Partial<WorkTask>) {
    if (busy || !canEdit) return;
    setBusy(true);
    try {
      if (await onUpdate(t, changes)) {
        setUndo({
          task: { ...t, ...changes },
          changes: {
            start_date: t.start_date ?? null,
            due_date: t.due_date ?? null,
            status: t.status,
          } as Partial<WorkTask>,
        });
        setMessage("Task saved. Other workspace views use the same task.");
      } else
        setMessage(
          "Task could not be saved. Review the workspace error and retry.",
        );
    } catch {
      setMessage("Task could not be saved.");
    } finally {
      setBusy(false);
    }
  }
  function color(t: WorkTask) {
    return prefs.color === "status"
      ? taskBucket(t.status) === "Done"
        ? "#047857"
        : t.status === "Blocked"
          ? "#be123c"
          : "#6d28d9"
      : prefs.color === "priority"
        ? ["Urgent", "High", "Critical"].includes(t.priority)
          ? "#be123c"
          : t.priority === "Low"
            ? "#047857"
            : "#b45309"
        : colors[
            Math.max(
              0,
              projects.findIndex((p) => p.id === t.project_id),
            ) % colors.length
          ];
  }
  function exportFile(kind: "csv" | "ics") {
    const esc = (s: string) =>
      s
        .replace(/\\/g, "\\\\")
        .replace(/\n/g, "\\n")
        .replace(/[,;]/g, (m) => `\\${m}`);
    const csv = (s: string) =>
      `"${(/^[=+@\-\t\r]/.test(s) ? "'" : "") + s.replace(/"/g, '""')}"`;
    const content =
      kind === "csv"
        ? [
            "Key,Title,Status,Priority,Start,Due",
            ...filtered.map((t) =>
              [
                t.task_key,
                t.title,
                t.status,
                t.priority,
                t.start_date || "",
                t.due_date || "",
              ]
                .map(csv)
                .join(","),
            ),
          ].join("\r\n")
        : [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//KaryaFlow//Workspace Calendar//EN",
            ...scheduled.flatMap((t) => [
              "BEGIN:VEVENT",
              `UID:task-${t.id}@karyaflow`,
              `DTSTAMP:${new Date()
                .toISOString()
                .replace(/[-:]/g, "")
                .replace(/\.\d{3}/, "")}`,
              `DTSTART;VALUE=DATE:${(t.start_date || t.due_date || "").replace(/-/g, "")}`,
              `DTEND;VALUE=DATE:${shift(t.due_date || t.start_date || "", 1).replace(/-/g, "")}`,
              `SUMMARY:${esc(t.title)}`,
              "END:VEVENT",
            ]),
            "END:VCALENDAR",
          ].join("\r\n");
    const url = URL.createObjectURL(
      new Blob(
        [
          kind === "ics"
            ? content
                .split("\r\n")
                .map((line) => {
                  let result = "",
                    bytes = 0;
                  for (const char of line) {
                    const size = new TextEncoder().encode(char).length;
                    if (bytes + size > 73) {
                      result += "\r\n ";
                      bytes = 1;
                    }
                    result += char;
                    bytes += size;
                  }
                  return result;
                })
                .join("\r\n") + "\r\n"
            : content,
        ],
        {
          type:
            kind === "csv"
              ? "text/csv;charset=utf-8"
              : "text/calendar;charset=utf-8",
        },
      ),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `workspace-tasks.${kind}`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function chip(t: WorkTask, sourceDay?: string) {
    return (
      <button
        key={t.id}
        className={`wc-task ${taskBucket(t.status) === "Done" ? "done" : ""}`}
        style={{ borderLeftColor: color(t) }}
        draggable={canEdit && !busy}
        onDragStart={(e) => {
          e.dataTransfer.setData("text/plain", String(t.id));
          if (sourceDay)
            e.dataTransfer.setData("application/x-karyaflow-day", sourceDay);
          e.dataTransfer.effectAllowed = "move";
        }}
        onClick={(e) => {
          e.stopPropagation();
          onOpen(t.id);
        }}
        onDoubleClick={(e) => e.stopPropagation()}
        title={`${t.task_key}: ${t.title} · ${t.status} · ${t.priority}`}
      >
        <span>
          {taskBucket(t.status) === "Done" ? "✓ " : ""}
          {t.title}
        </span>
      </button>
    );
  }
  return (
    <section
      className={`wc-calendar ${prefs.compact ? "compact" : ""}`}
      aria-label="Workspace calendar"
    >
      <header>
        <div>
          <h2>Calendar</h2>
          <p>Plan work. Find time. Keep everyone aligned.</p>
        </div>
        {canEdit && (
          <button
            className="ws-button ws-primary"
            disabled={!projects.length}
            onClick={() => onCreate(anchor, project)}
          >
            + Create task
          </button>
        )}
      </header>
      <div className="wc-toolbar">
        <button aria-label="Previous period" onClick={() => navigate(-1)}>
          ‹
        </button>
        <button aria-label="Next period" onClick={() => navigate(1)}>
          ›
        </button>
        <strong>
          {current.toLocaleDateString(undefined, {
            month: "long",
            year: "numeric",
            ...(mode === "day" ? { day: "numeric" } : {}),
          })}
        </strong>
        <button onClick={() => setAnchor(today)}>Today</button>
        <input
          aria-label="Go to date"
          type="date"
          value={anchor}
          onChange={(e) => e.target.value && setAnchor(e.target.value)}
        />
        <select
          aria-label="Calendar view"
          value={mode}
          onChange={(e) => setMode(e.target.value)}
        >
          {["month", "week", "day", "agenda"].map((v) => (
            <option key={v} value={v}>
              {v[0].toUpperCase() + v.slice(1)}
            </option>
          ))}
        </select>
        <button aria-expanded={sidebar} onClick={() => setSidebar(!sidebar)}>
          Task list
        </button>
        <button aria-expanded={settings} onClick={() => setSettings(!settings)}>
          Display options
        </button>
      </div>
      <div className="wc-filters">
        <input
          aria-label="Search calendar tasks"
          placeholder="Search titles or task keys…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          aria-label="Calendar project"
          value={project}
          onChange={(e) => setProject(e.target.value)}
        >
          <option value="">All projects</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <select
          aria-label="Calendar assignee"
          value={assignee}
          onChange={(e) => setAssignee(e.target.value)}
        >
          <option value="">All assignees</option>
          <option value="none">Unassigned</option>
          {members.map((m) => (
            <option key={m.id} value={m.user_id}>
              {personName(m.email)}
            </option>
          ))}
        </select>
        <select
          aria-label="Calendar status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">All statuses</option>
          {Array.from(new Set(tasks.map((t) => t.status)))
            .sort()
            .map((s) => (
              <option key={s}>{s}</option>
            ))}
        </select>
        <select
          aria-label="Calendar priority"
          value={priority}
          onChange={(e) => setPriority(e.target.value)}
        >
          <option value="">All priorities</option>
          {Array.from(new Set(tasks.map((t) => t.priority)))
            .sort()
            .map((s) => (
              <option key={s}>{s}</option>
            ))}
        </select>
        <button
          onClick={() => {
            setProject("");
            setSearch("");
            setAssignee("");
            setStatus("");
            setPriority("");
          }}
        >
          Clear filters
        </button>
      </div>
      {settings && (
        <fieldset className="wc-settings">
          <legend>Saved display preferences</legend>
          {(
            [
              ["weekends", "Show weekends"],
              ["monday", "Start week Monday"],
              ["completed", "Show completed tasks"],
              ["compact", "Compact density"],
            ] as const
          ).map(([key, label]) => (
            <label key={key}>
              <input
                type="checkbox"
                checked={prefs[key]}
                onChange={(e) => preference(key, e.target.checked)}
              />
              {label}
            </label>
          ))}
          <label>
            Color by
            <select
              aria-label="Color tasks by"
              value={prefs.color}
              onChange={(e) => preference("color", e.target.value)}
            >
              <option value="project">Project</option>
              <option value="status">Status</option>
              <option value="priority">Priority</option>
            </select>
          </label>
          <button onClick={() => exportFile("csv")}>Export CSV</button>
          <button onClick={() => exportFile("ics")}>Export iCalendar</button>
          <button onClick={() => window.print()}>Print</button>
        </fieldset>
      )}
      <div className="wc-summary">
        <span>
          {filtered.length} tasks · {unscheduled.length} unscheduled ·{" "}
          {
            filtered.filter(
              (t) =>
                !!t.due_date &&
                t.due_date < today &&
                taskBucket(t.status) !== "Done",
            ).length
          }{" "}
          overdue
        </span>
        <span>
          Double-click a date to create · Enter opens day view · + adds a task
        </span>
      </div>
      <div role="status" className="wc-feedback">
        {message}
        {undo && (
          <button
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                const t = tasks.find((t) => t.id === undo.task.id);
                if (t && (await onUpdate(t, undo.changes))) {
                  setUndo(null);
                  setMessage("Last calendar change undone.");
                } else setMessage("Undo could not be saved.");
              } finally {
                setBusy(false);
              }
            }}
          >
            Undo last change
          </button>
        )}
      </div>
      <div className={`wc-body ${sidebar ? "with-list" : ""}`}>
        <main>
          {mode === "agenda" ? (
            <div className="wc-agenda">
              {!displayed.length && (
                <p>
                  No scheduled tasks from this date. Clear filters or choose an
                  earlier date.
                </p>
              )}
              {displayed.map((t) => (
                <article key={t.id}>
                  <time>{t.due_date || t.start_date}</time>
                  {chip(t)}
                  <span>
                    {t.status} · {t.priority}
                  </span>
                </article>
              ))}
            </div>
          ) : (
            <div
              className="wc-grid"
              style={{
                gridTemplateColumns: `repeat(${mode === "day" ? 1 : prefs.weekends ? 7 : 5},minmax(0,1fr))`,
              }}
            >
              {days
                .slice(0, mode === "day" ? 1 : prefs.weekends ? 7 : 5)
                .map((d) => (
                  <strong key={d}>
                    {date(d).toLocaleDateString(undefined, {
                      weekday: "short",
                    })}
                  </strong>
                ))}
              {days.map((d) => {
                const items = scheduled.filter(
                  (t) =>
                    d >= (t.start_date || t.due_date || "") &&
                    d <= (t.due_date || t.start_date || ""),
                );
                return (
                  <div
                    key={d}
                    tabIndex={0}
                    role="group"
                    aria-label={`Calendar date ${d}`}
                    className={`wc-day ${d === today ? "today" : ""} ${date(d).getMonth() !== current.getMonth() ? "outside" : ""}`}
                    onDoubleClick={(e) => {
                      if (
                        e.target === e.currentTarget &&
                        canEdit &&
                        projects.length
                      )
                        onCreate(d, project);
                    }}
                    onKeyDown={(e) => {
                      if (e.target !== e.currentTarget) return;
                      if (e.key === "Enter") {
                        setAnchor(d);
                        setMode("day");
                      }
                      if (e.key === "+" && canEdit && projects.length) {
                        e.preventDefault();
                        onCreate(d, project);
                      }
                    }}
                    onDragOver={(e) => {
                      if (canEdit && !busy) e.preventDefault();
                    }}
                    onDrop={(e) => {
                      e.preventDefault();
                      const t = tasks.find(
                        (t) =>
                          String(t.id) === e.dataTransfer.getData("text/plain"),
                      );
                      if (!t || !canEdit) return;
                      const end =
                        e.dataTransfer.getData("application/x-karyaflow-day") ||
                        t.due_date ||
                        t.start_date;
                      const delta = end
                        ? Math.round(
                            (date(d).getTime() - date(end).getTime()) /
                              86400000,
                          )
                        : 0;
                      void save(t, {
                        due_date: t.due_date ? shift(t.due_date, delta) : d,
                        ...(t.start_date
                          ? { start_date: shift(t.start_date, delta) }
                          : {}),
                      });
                    }}
                  >
                    <header>
                      <button
                        onClick={() => {
                          setAnchor(d);
                          setMode("day");
                        }}
                        aria-label={`Show ${d}`}
                      >
                        {date(d).getDate()}
                      </button>
                      {canEdit && (
                        <button
                          aria-label={`Add task on ${d}`}
                          disabled={!projects.length}
                          onClick={() => onCreate(d, project)}
                        >
                          +
                        </button>
                      )}
                    </header>
                    {items
                      .slice(0, mode === "month" ? 4 : items.length)
                      .map((t) => chip(t, d))}
                    {mode === "month" && items.length > 4 && (
                      <button
                        className="wc-more"
                        onClick={() => {
                          setAnchor(d);
                          setMode("day");
                        }}
                      >
                        + {items.length - 4} more
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </main>
        {sidebar && (
          <aside aria-label="Calendar task list">
            <h3>Tasks · {filtered.length}</h3>
            <p>Select tasks, then choose a date to schedule them.</p>
            <label>
              Schedule selected on
              <input
                aria-label="Schedule selected date"
                type="date"
                value={anchor}
                onChange={(e) => e.target.value && setAnchor(e.target.value)}
              />
            </label>
            {canEdit && (
              <button
                disabled={busy || !selected.length}
                onClick={async () => {
                  setBusy(true);
                  let saved = 0;
                  try {
                    for (const id of selected) {
                      const t = filtered.find((t) => t.id === id);
                      if (
                        t &&
                        (await onUpdate(t, {
                          due_date: anchor,
                          ...(t.start_date && t.start_date > anchor
                            ? { start_date: anchor }
                            : {}),
                        }))
                      )
                        saved++;
                    }
                    setMessage(
                      `${saved} of ${selected.length} tasks scheduled.`,
                    );
                    setSelected([]);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Schedule {selected.length} selected
              </button>
            )}
            <h4>Unscheduled · {unscheduled.length}</h4>
            {unscheduled.map((t) => (
              <div key={t.id} className="wc-list-row">
                {canEdit && (
                  <input
                    type="checkbox"
                    aria-label={`Select ${t.title}`}
                    checked={selected.includes(t.id)}
                    onChange={(e) =>
                      setSelected(
                        e.target.checked
                          ? [...selected, t.id]
                          : selected.filter((id) => id !== t.id),
                      )
                    }
                  />
                )}{" "}
                {chip(t)}
              </div>
            ))}
            <h4>Scheduled · {scheduled.length}</h4>
            {scheduled
              .sort((a, b) =>
                (a.due_date || a.start_date || "").localeCompare(
                  b.due_date || b.start_date || "",
                ),
              )
              .map((t) => (
                <div key={t.id} className="wc-list-row">
                  {canEdit && (
                    <input
                      type="checkbox"
                      aria-label={`Select ${t.title}`}
                      checked={selected.includes(t.id)}
                      onChange={(e) =>
                        setSelected(
                          e.target.checked
                            ? [...selected, t.id]
                            : selected.filter((id) => id !== t.id),
                        )
                      }
                    />
                  )}
                  <div>
                    {chip(t)}
                    <small>
                      {t.due_date || t.start_date} · {t.status}
                    </small>
                  </div>
                  {canEdit && (
                    <button
                      aria-label={`Complete ${t.title}`}
                      disabled={busy}
                      onClick={() =>
                        void save(t, {
                          status:
                            taskBucket(t.status) === "Done" ? "To Do" : "Done",
                        })
                      }
                    >
                      {taskBucket(t.status) === "Done" ? "↶" : "✓"}
                    </button>
                  )}
                </div>
              ))}
          </aside>
        )}
      </div>
    </section>
  );
}
