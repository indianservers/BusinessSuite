import { RichTextContent } from "@/components/rich-text/RichTextContent";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Plus,
  Search,
  SlidersHorizontal,
  Settings2,
  Target,
  X,
  CheckCircle2,
  Circle,
  Flag,
  Folder,
  Inbox,
  GripVertical,
  RefreshCw,
  ArrowUpRight,
  Pin,
} from "lucide-react";
import {
  addDays,
  addMonths,
  format,
  startOfMonth,
  startOfWeek,
  endOfMonth,
  endOfWeek,
  isSameMonth,
  parseISO,
  differenceInCalendarDays,
} from "date-fns";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { tasksAPI } from "../services/api";
import CreateTaskModal from "../components/CreateTaskModal";
import "./PlannerPage.css";
import CalendarSettings from "../components/CalendarSettings";
import CalendarEventEditor from "../components/CalendarEventEditor";
import {
  calendarDefaults,
  calendarICS,
  saveCalendarFile,
  zonedDay,
  zonedInput,
  localToUTC,
  type CalendarPrefs,
  type CalendarEvent,
} from "./calendarTypes";

type Task = {
  id: number;
  project_id: number;
  title: string;
  description?: string;
  task_key: string;
  start_date: string | null;
  due_date: string | null;
  status: string;
  priority: string;
  assignee_user_ids: number[];
  can_schedule: boolean;
  recurrence_rule?: string;
  recurrence_interval?: number;
  recurrence_until?: string | null;
};
type Data = {
  projects: {
    id: number;
    name: string;
    workspace_id: number | null;
    due_date: string | null;
    status: string;
    can_schedule: boolean;
  }[];
  tasks: Task[];
  milestones: {
    id: number;
    project_id: number;
    title: string;
    due_date: string | null;
    status: string;
  }[];
  people: { id: number; name: string }[];
};
type Item = {
  key: string;
  id: number;
  project_id: number;
  title: string;
  date: string;
  type: "task" | "milestone" | "project" | "event";
  event?: CalendarEvent;
  projected?: boolean;
  status: string;
  task?: Task;
};
type View = "Month" | "Week" | "Day" | "List";
const done = (status: string) =>
  ["Done", "Completed", "Closed", "Resolved"].includes(status);
const dateKey = (date: Date) => format(date, "yyyy-MM-dd");
function validDate(value: string | null) {
  return (
    !!value &&
    /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    !isNaN(parseISO(value).getTime())
  );
}
function saved<T>(key: string, fallback: T): T {
  try {
    const value = localStorage.getItem(key);
    return value ? JSON.parse(value) : fallback;
  } catch {
    return fallback;
  }
}

export default function PlannerPage() {
  const userId = useAuthStore((s) => s.user?.id || 0);
  const [params, setParams] = useSearchParams();
  const client = useQueryClient();
  const preferencesQuery = useQuery({
    queryKey: ["pms-calendar-preferences", userId],
    queryFn: () =>
      api
        .get<{
          revision: number;
          preferences: CalendarPrefs;
        }>("/project-management/planner/preferences")
        .then((r) => r.data),
    retry: false,
  });
  const prefs = useMemo(
    () =>
      preferencesQuery.data
        ? {
            ...preferencesQuery.data.preferences,
            timezone: preferencesQuery.data.revision
              ? preferencesQuery.data.preferences.timezone
              : calendarDefaults.timezone,
          }
        : calendarDefaults,
    [preferencesQuery.data],
  );
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(timer);
  }, []);
  const today = zonedDay(new Date(now).toISOString(), prefs.timezone);
  const anchor = validDate(params.get("date"))
    ? parseISO(params.get("date")!)
    : parseISO(today);
  const initialView = window.matchMedia("(max-width: 767px)").matches
    ? "List"
    : "Month";
  const view: View = ["Month", "Week", "Day", "List"].includes(
    params.get("view") || "",
  )
    ? (params.get("view") as View)
    : initialView;
  const query = params.get("q") || "";
  const project = params.get("project") || "";
  const assignee = params.get("person") || "";
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [includeDone, setIncludeDone] = useState(true);
  useEffect(() => setIncludeDone(prefs.closed_tasks), [prefs.closed_tasks]);
  const [itemType, setItemType] = useState("all");
  const weekends = prefs.weekends;
  const compact = false;
  const [pins, setPins] = useState<number[]>(() => {
    const value = saved<unknown>(`planner-pins-${userId}`, []);
    return Array.isArray(value)
      ? value.filter((v) => typeof v === "number")
      : [];
  });
  const [pinOpen, setPinOpen] = useState(false);
  const [peopleSearch, setPeopleSearch] = useState("");
  const [pinSearch, setPinSearch] = useState("");
  const [selected, setSelected] = useState<Item | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [saveError, setSaveError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [createDate, setCreateDate] = useState(today);
  const [createProject, setCreateProject] = useState(0);
  const searchRef = useRef<HTMLInputElement>(null);
  const dragTask = useRef<number | null>(null);
  const dragEvent = useRef<{ id: number; day: string } | null>(null);
  const [dragOver, setDragOver] = useState("");
  const result = useQuery({
    queryKey: ["pms-planner", userId],
    queryFn: ({ signal }) =>
      api
        .get<Data>("/project-management/planner", { signal })
        .then((r) => r.data),
    retry: 1,
    refetchOnWindowFocus: true,
  });
  const data = result.data;
  const [eventOpen, setEventOpen] = useState(false);
  const [editingEvent, setEditingEvent] = useState<CalendarEvent | null>(null);
  const [eventDay, setEventDay] = useState(today);
  const [eventTask, setEventTask] = useState<number | undefined>();
  const eventRange = {
    start: dateKey(startOfMonth(addMonths(anchor, -1))) + "T00:00:00Z",
    end: dateKey(addDays(endOfMonth(addMonths(anchor, 1)), 2)) + "T00:00:00Z",
  };
  const eventQuery = useQuery({
    queryKey: ["pms-calendar-events", userId, eventRange.start, eventRange.end],
    queryFn: () =>
      api
        .get<
          CalendarEvent[]
        >("/project-management/planner/events", { params: eventRange })
        .then((r) => r.data),
    retry: false,
  });
  const upcomingQuery = useQuery({
    queryKey: ["pms-calendar-upcoming", userId, today],
    queryFn: () =>
      api
        .get<
          CalendarEvent[]
        >("/project-management/planner/events", { params: { start: new Date().toISOString(), end: new Date(Date.now() + 7 * 86400000).toISOString() } })
        .then((r) => r.data),
    refetchInterval: 60000,
    retry: false,
  });
  const upcoming = (upcomingQuery.data || [])
    .filter((e) => e.kind === "meeting" && Date.parse(e.end_at) > now)
    .sort((a, b) => a.start_at.localeCompare(b.start_at))[0];
  const reminded = useRef(new Set<number>());
  useEffect(() => {
    if (
      prefs.browser_reminders &&
      upcoming &&
      "Notification" in window &&
      Notification.permission === "granted" &&
      Date.parse(upcoming.start_at) - now <= prefs.quick_join * 60000 &&
      !reminded.current.has(upcoming.id)
    ) {
      try {
        new Notification(upcoming.title, {
          body:
            Date.parse(upcoming.start_at) <= now
              ? "Your meeting is in progress."
              : "Your meeting starts soon.",
        });
      } catch {
        setNotice(
          "This browser cannot show meeting reminders. Use the upcoming meeting button instead.",
        );
      }
      reminded.current.add(upcoming.id);
    }
  }, [upcoming, now, prefs.browser_reminders, prefs.quick_join]);
  function openEvent(
    event: CalendarEvent | null = null,
    day = today,
    taskId?: number,
  ) {
    setEditingEvent(event);
    setEventDay(day);
    setEventTask(taskId);
    setEventOpen(true);
  }
  function refreshEvents() {
    void client.invalidateQueries({ queryKey: ["pms-calendar-events"] });
    void client.invalidateQueries({ queryKey: ["pms-calendar-upcoming"] });
  }

  const canCreate = !!data?.projects.some(
    (p) => p.can_schedule && (!project || p.id === Number(project)),
  );
  useEffect(() => {
    localStorage.setItem(`planner-pins-${userId}`, JSON.stringify(pins));
  }, [pins, userId]);

  function changeMany(values: Record<string, string>) {
    setParams((old) => {
      const next = new URLSearchParams(old);
      Object.entries(values).forEach(([key, value]) =>
        value ? next.set(key, value) : next.delete(key),
      );
      return next;
    });
  }
  function change(key: string, value: string) {
    changeMany({ [key]: value });
  }
  function setView(next: View) {
    change("view", next);
  }
  function step(direction: number) {
    change(
      "date",
      dateKey(
        view === "Month" || view === "List"
          ? addMonths(anchor, direction)
          : addDays(anchor, direction * (view === "Week" ? 7 : 1)),
      ),
    );
  }
  const filteredTasks = (data?.tasks || []).filter(
    (t) =>
      (prefs.task_scope !== "mine" || t.assignee_user_ids.includes(userId)) &&
      (!project || t.project_id === Number(project)) &&
      (!assignee || t.assignee_user_ids.includes(Number(assignee))) &&
      (includeDone || !done(t.status)) &&
      `${t.title} ${t.task_key} ${data?.projects.find((p) => p.id === t.project_id)?.name}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const items = useMemo<Item[]>(() => {
    const tasks: Item[] = filteredTasks
      .filter((t) => t.due_date && prefs.show_task_dates)
      .map((t) => ({
        key: `task-${t.id}`,
        id: t.id,
        project_id: t.project_id,
        title: t.title,
        date: t.due_date!,
        type: "task",
        status: t.status,
        task: t,
      }));
    const milestones: Item[] = assignee
      ? []
      : (data?.milestones || [])
          .filter(
            (m) =>
              m.due_date &&
              (!project || m.project_id === Number(project)) &&
              (includeDone || !done(m.status)) &&
              m.title.toLowerCase().includes(query.toLowerCase()),
          )
          .map((m) => ({
            key: `milestone-${m.id}`,
            id: m.id,
            project_id: m.project_id,
            title: m.title,
            date: m.due_date!,
            type: "milestone",
            status: m.status,
          }));
    const projects: Item[] = assignee
      ? []
      : (data?.projects || [])
          .filter(
            (p) =>
              p.due_date &&
              (!project || p.id === Number(project)) &&
              p.name.toLowerCase().includes(query.toLowerCase()) &&
              (includeDone || !done(p.status)),
          )
          .map((p) => ({
            key: `project-${p.id}`,
            id: p.id,
            project_id: p.id,
            title: p.name,
            date: p.due_date!,
            type: "project",
            status: p.status,
          }));
    const events: Item[] = (eventQuery.data || [])
      .filter(
        (e) =>
          (!assignee || e.owner_id === Number(assignee)) &&
          e.title.toLowerCase().includes(query.toLowerCase()),
      )
      .flatMap((e): Item[] => {
        const first = zonedDay(e.start_at, prefs.timezone);
        const last = zonedDay(
          new Date(Date.parse(e.end_at) - 1).toISOString(),
          prefs.timezone,
        );
        return Array.from(
          {
            length: Math.max(
              1,
              Math.min(
                9,
                differenceInCalendarDays(parseISO(last), parseISO(first)) + 1,
              ),
            ),
          },
          (_, index) => ({
            key: `event-${e.id}-${index}`,
            id: e.id,
            project_id: 0,
            title: `${index ? "↳" : new Date(e.start_at).toLocaleTimeString([], { timeZone: prefs.timezone, hour: "2-digit", minute: "2-digit" })} ${e.title}`,
            date: dateKey(addDays(parseISO(first), index)),
            type: "event",
            status: e.kind,
            event: e,
          }),
        );
      });
    const projections: Item[] = [];
    if (prefs.recurring && prefs.show_task_dates)
      for (const task of filteredTasks.filter(
        (t) => t.recurrence_rule && t.due_date && !done(t.status),
      )) {
        let day = parseISO(task.due_date!);
        for (let i = 1; i <= 12; i++) {
          day =
            task.recurrence_rule === "monthly"
              ? addMonths(
                  parseISO(task.due_date!),
                  i * (task.recurrence_interval || 1),
                )
              : addDays(
                  day,
                  (task.recurrence_interval || 1) *
                    (task.recurrence_rule === "weekly" ? 7 : 1),
                );
          const key = dateKey(day);
          if (task.recurrence_until && key > task.recurrence_until) break;
          projections.push({
            key: `projected-${task.id}-${i}`,
            id: task.id,
            project_id: task.project_id,
            title: `↻ ${task.title}`,
            date: key,
            type: "task",
            status: "Projected",
            projected: true,
          });
        }
      }
    return [...tasks, ...milestones, ...projects, ...events, ...projections]
      .filter((i) => itemType === "all" || i.type === itemType)
      .sort(
        (a, b) =>
          a.date.localeCompare(b.date) || a.title.localeCompare(b.title),
      );
  }, [
    data,
    project,
    assignee,
    query,
    includeDone,
    itemType,
    filteredTasks,
    eventQuery.data,
    prefs,
  ]);
  const weekStartsOn = prefs.week_start as 0 | 1 | 2 | 3 | 4 | 5 | 6;
  const monthStart = startOfWeek(startOfMonth(anchor), { weekStartsOn });
  const monthEnd = endOfWeek(endOfMonth(anchor), { weekStartsOn });
  const rangeStart =
    view === "Month"
      ? monthStart
      : view === "Week"
        ? startOfWeek(anchor, { weekStartsOn })
        : view === "Day"
          ? anchor
          : startOfMonth(anchor);
  const rangeEnd =
    view === "Month"
      ? monthEnd
      : view === "Week"
        ? endOfWeek(anchor, { weekStartsOn })
        : view === "Day"
          ? anchor
          : endOfMonth(anchor);
  const days = Array.from(
    { length: differenceInCalendarDays(rangeEnd, rangeStart) + 1 },
    (_, i) => addDays(rangeStart, i),
  ).filter((d) => weekends || ![0, 6].includes(d.getDay()));
  const rangeItems = items.filter(
    (i) => i.date >= dateKey(rangeStart) && i.date <= dateKey(rangeEnd),
  );
  const mine = filteredTasks.filter(
    (t) => t.assignee_user_ids.includes(userId) && !done(t.status),
  );
  const overdue = mine
    .filter((t) => t.due_date && t.due_date <= today)
    .sort((a, b) => (a.due_date || "").localeCompare(b.due_date || ""));
  const backlog = mine.filter((t) => !t.due_date);
  const pinned = (data?.tasks || []).filter((t) => pins.includes(t.id));
  async function refresh() {
    await client.invalidateQueries({ queryKey: ["pms-planner"] });
  }
  function openCreate(day = today) {
    setCreateDate(day);
    setCreateProject(
      Number(project) ||
        (data?.projects.some(
          (p) => p.id === prefs.default_project && p.can_schedule,
        )
          ? prefs.default_project
          : 0) ||
        data?.projects.find((p) => p.can_schedule)?.id ||
        0,
    );
    setCreateOpen(true);
  }
  async function schedule(task: Task, date: string) {
    if (!task.can_schedule || busy) return;
    setBusy(true);
    setSaveError("");
    setNotice("");
    const previous = { due_date: task.due_date, start_date: task.start_date };
    const startDate =
      task.start_date && task.due_date
        ? dateKey(
            addDays(
              parseISO(task.start_date),
              differenceInCalendarDays(parseISO(date), parseISO(task.due_date)),
            ),
          )
        : task.start_date && task.start_date > date
          ? date
          : task.start_date;
    try {
      await tasksAPI.update(task.id, {
        due_date: date,
        start_date: startDate || undefined,
      });
      await refresh();
      setNotice(
        `Scheduled “${task.title}” for ${format(parseISO(date), "MMM d")}.`,
      );
      setUndo({ task, previous });
      setSelected(null);
    } catch (e: any) {
      setSaveError(
        typeof e?.response?.data?.detail === "string"
          ? e.response.data.detail
          : "Could not reschedule. Your original dates have been kept.",
      );
    } finally {
      setBusy(false);
    }
  }
  const [undo, setUndo] = useState<{
    task: Task;
    previous: { due_date: string | null; start_date: string | null };
  } | null>(null);
  async function undoSchedule() {
    if (!undo || busy) return;
    setBusy(true);
    try {
      await api.patch(
        `/project-management/tasks/${undo.task.id}`,
        undo.previous,
      );
      await refresh();
      setNotice("Original dates restored.");
      setUndo(null);
    } catch {
      setSaveError("Could not restore the dates. Try again.");
    } finally {
      setBusy(false);
    }
  }
  async function toggleDone(task: Task) {
    if (busy || !task.can_schedule) return;
    setBusy(true);
    setSaveError("");
    try {
      await tasksAPI.update(task.id, {
        status: done(task.status) ? "To Do" : "Done",
      });
      await refresh();
      setSelected(null);
      setUndo(null);
      setNotice(done(task.status) ? "Task reopened." : "Task completed.");
    } catch {
      setSaveError("Could not update task status. Please try again.");
    } finally {
      setBusy(false);
    }
  }
  function taskItem(task: Task): Item {
    return {
      key: `task-${task.id}`,
      id: task.id,
      project_id: task.project_id,
      title: task.title,
      date: task.due_date || today,
      type: "task",
      status: task.status,
      task,
    };
  }
  function togglePin(id: number) {
    setPins((current) =>
      current.includes(id)
        ? current.filter((x) => x !== id)
        : [...current, id].slice(-5),
    );
  }
  async function moveEvent(
    event: CalendarEvent,
    day: string,
    sourceDay: string,
  ) {
    if (!event.can_edit || busy) return;
    setBusy(true);
    setSaveError("");
    try {
      const delta = differenceInCalendarDays(
        parseISO(day),
        parseISO(sourceDay),
      );
      const original = zonedInput(event.start_at, prefs.timezone);
      const next =
        dateKey(addDays(parseISO(original.slice(0, 10)), delta)) +
        original.slice(10);
      const start = localToUTC(next, prefs.timezone);
      const end = new Date(
        Date.parse(start) +
          Date.parse(event.end_at) -
          Date.parse(event.start_at),
      ).toISOString();
      await api.put(`/project-management/planner/events/${event.id}`, {
        title: event.title,
        description: event.description,
        start_at: start,
        end_at: end,
        timezone: prefs.timezone,
        kind: event.kind,
        visibility: event.visibility,
        workspace_id: event.workspace_id,
        task_id: event.task_id,
        meeting_url: event.meeting_url,
        revision: event.revision,
      });
      refreshEvents();
      setNotice(`Moved “${event.title}” to ${day}.`);
    } catch (e) {
      setSaveError(
        e instanceof Error && !("response" in e)
          ? e.message
          : "Could not move event. Reload and try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  function chip(item: Item) {
    return (
      <button
        key={item.key}
        type="button"
        className={`planner-chip ${item.type} ${done(item.status) ? "complete" : ""} ${item.task?.priority === "Urgent" ? "urgent" : ""}`}
        style={
          {
            "--calendar-color":
              prefs.color_by === "priority"
                ? (
                    {
                      Urgent: "#e11d48",
                      High: "#d97706",
                      Low: "#059669",
                    } as Record<string, string>
                  )[item.task?.priority || ""] || "#7c3aed"
                : prefs.color_by === "status"
                  ? done(item.status)
                    ? "#059669"
                    : item.status === "In Progress"
                      ? "#2563eb"
                      : "#7c3aed"
                  : ["#7c3aed", "#0891b2", "#db2777", "#059669", "#d97706"][
                      item.project_id % 5
                    ],
          } as React.CSSProperties
        }
        title={`${item.title} · ${item.status}`}
        draggable={!!(item.task?.can_schedule || item.event?.can_edit) && !busy}
        onDragStart={(e) => {
          if (item.event) {
            dragEvent.current = { id: item.event.id, day: item.date };
            e.dataTransfer.setData("text/plain", `event:${item.event.id}`);
            e.dataTransfer.effectAllowed = "move";
          } else if (item.task) {
            dragTask.current = item.task.id;
            e.dataTransfer.setData("text/plain", String(item.task.id));
            e.dataTransfer.effectAllowed = "move";
          }
        }}
        onDragEnd={() => {
          dragTask.current = null;
          dragEvent.current = null;
          setDragOver("");
        }}
        onClick={() => {
          setSaveError("");
          if (item.event) openEvent(item.event);
          else setSelected(item);
        }}
      >
        {item.type === "task" ? (
          done(item.status) ? (
            <CheckCircle2 />
          ) : (
            <Circle />
          )
        ) : item.type === "milestone" ? (
          <Flag />
        ) : item.event ? (
          <CalendarDays />
        ) : (
          <Folder />
        )}
        <span>{item.title}</span>
      </button>
    );
  }
  function sideTasks(title: string, tasks: Task[], empty: string) {
    return (
      <section className="planner-side-section">
        <div className="planner-section-title">
          <h2>{title}</h2>
          <span>{tasks.length}</span>
        </div>
        {tasks.length ? (
          tasks.slice(0, 6).map((task) => (
            <button
              type="button"
              className="planner-side-task"
              key={task.id}
              onClick={() => setSelected(taskItem(task))}
              draggable={task.can_schedule && !busy}
              onDragStart={(e) => {
                dragTask.current = task.id;
                e.dataTransfer.setData("text/plain", String(task.id));
              }}
              onDragEnd={() => {
                dragTask.current = null;
                setDragOver("");
              }}
            >
              <Circle
                className={
                  task.priority === "Urgent"
                    ? "text-rose-500"
                    : "text-violet-500"
                }
              />
              <span>{task.title}</span>
              {task.due_date && (
                <small className={task.due_date < today ? "late" : ""}>
                  {format(parseISO(task.due_date), "MMM d")}
                </small>
              )}
            </button>
          ))
        ) : (
          <div className="planner-mini-empty">
            <Inbox />
            <span>{empty}</span>
          </div>
        )}
        {tasks.length > 6 && (
          <button
            type="button"
            className="planner-see-all"
            onClick={() => {
              changeMany({ person: String(userId), view: "List" });
              setSidebarOpen(false);
            }}
          >
            See scheduled tasks in list →
          </button>
        )}
      </section>
    );
  }
  return (
    <div
      className={`planner-shell ${compact ? "compact" : ""} grid-${prefs.grid_size} event-${prefs.event_style}`}
    >
      <aside className={`planner-sidebar ${sidebarOpen ? "mobile-open" : ""}`}>
        <div className="planner-brand">
          <span>
            <CalendarDays />
          </span>
          <div>
            <h1>Planner</h1>
            <p>Make space for your best work.</p>
          </div>
          <button
            type="button"
            className="planner-add"
            aria-label="Create planner task"
            onClick={() => openCreate()}
            disabled={!canCreate}
          >
            <Plus />
          </button>
        </div>
        <button
          className="planner-close-sidebar"
          type="button"
          onClick={() => setSidebarOpen(false)}
        >
          <X />
          Close task panel
        </button>
        {prefs.sections
          .filter((s) => s.enabled)
          .map((section) => (
            <div key={section.id}>
              {section.filter === "priorities" ? (
                <section className="planner-side-section">
                  <div className="planner-section-title">
                    <h2>{section.title}</h2>
                    <span>{pinned.length}</span>
                  </div>
                  <div className="planner-priorities">
                    {pinned.length ? (
                      pinned.map((t) => (
                        <div className="planner-pin" key={t.id}>
                          <button
                            type="button"
                            onClick={() => setSelected(taskItem(t))}
                          >
                            <Target />
                            <span>{t.title}</span>
                          </button>
                          <button
                            type="button"
                            aria-label={`Unpin ${t.title}`}
                            onClick={() => togglePin(t.id)}
                          >
                            <X />
                          </button>
                        </div>
                      ))
                    ) : (
                      <div className="planner-priority-empty">
                        <Target />
                        <p>
                          Keep your most important tasks
                          <br />
                          in focus, every day.
                        </p>
                      </div>
                    )}
                    <button
                      type="button"
                      className="planner-pin-add"
                      onClick={() => setPinOpen(!pinOpen)}
                    >
                      <Plus />
                      Add priority
                    </button>
                    {pinOpen && (
                      <div className="planner-pin-picker">
                        <input
                          aria-label="Search priorities"
                          placeholder="Find a task to pin…"
                          value={pinSearch}
                          onChange={(e) => setPinSearch(e.target.value)}
                        />
                        {(data?.tasks || [])
                          .filter(
                            (t) =>
                              !pins.includes(t.id) &&
                              t.title
                                .toLowerCase()
                                .includes(pinSearch.toLowerCase()),
                          )
                          .slice(0, 12)
                          .map((t) => (
                            <button
                              type="button"
                              key={t.id}
                              onClick={() => {
                                togglePin(t.id);
                                setPinOpen(false);
                              }}
                            >
                              {t.title}
                            </button>
                          ))}
                        <small>Up to 5 priorities, saved on this device.</small>
                      </div>
                    )}
                  </div>
                </section>
              ) : section.filter === "people" ? (
                <section className="planner-side-section">
                  <div className="planner-section-title">
                    <h2>{section.title}</h2>
                    <button
                      type="button"
                      onClick={() => {
                        change("person", "");
                        setPeopleSearch("");
                      }}
                    >
                      See all
                    </button>
                  </div>
                  <div className="planner-people-search">
                    <Search />
                    <input
                      aria-label="Search planner people"
                      placeholder="Search for people…"
                      value={peopleSearch}
                      onChange={(e) => setPeopleSearch(e.target.value)}
                    />
                  </div>
                  {peopleSearch &&
                    (data?.people || [])
                      .filter((p) =>
                        p.name
                          .toLowerCase()
                          .includes(peopleSearch.toLowerCase()),
                      )
                      .slice(0, 5)
                      .map((p) => (
                        <button
                          type="button"
                          className="planner-person"
                          key={p.id}
                          onClick={() => {
                            change("person", String(p.id));
                            setPeopleSearch("");
                            setSidebarOpen(false);
                          }}
                        >
                          {p.name}
                        </button>
                      ))}
                </section>
              ) : (
                sideTasks(
                  section.title,
                  section.filter === "assigned"
                    ? mine
                    : section.filter === "overdue"
                      ? overdue
                      : section.filter === "backlog"
                        ? backlog
                        : mine.filter((t) =>
                            ["High", "Urgent", "Critical"].includes(t.priority),
                          ),
                  "No tasks match this section.",
                )
              )}
            </div>
          ))}
        <p className="planner-drag-tip">
          <GripVertical />
          Drag editable tasks onto a date, or open one to schedule it.
        </p>
      </aside>
      <section className="planner-main" aria-label="Planner calendar">
        <div className="planner-toolbar">
          <div className="planner-period">
            <button
              type="button"
              aria-label="Previous period"
              onClick={() => step(-1)}
            >
              <ChevronLeft />
            </button>
            <button
              type="button"
              aria-label="Next period"
              onClick={() => step(1)}
            >
              <ChevronRight />
            </button>
            <h2>
              {view === "Day"
                ? format(anchor, "EEEE, MMM d")
                : view === "Week"
                  ? `${format(rangeStart, "MMM d")} – ${format(rangeEnd, "MMM d, yyyy")}`
                  : format(anchor, "MMMM yyyy")}
            </h2>
            <button
              type="button"
              className="planner-today"
              onClick={() => change("date", today)}
            >
              Today
            </button>
          </div>
          <div className="planner-toolbar-actions">
            <button
              type="button"
              className="planner-filter-button"
              onClick={() => openEvent(null, dateKey(anchor))}
            >
              <Plus />
              Event / focus
            </button>
            <div
              className="planner-view-tabs"
              role="group"
              aria-label="Calendar view"
            >
              {(["Month", "Week", "Day", "List"] as View[]).map((v) => (
                <button
                  type="button"
                  key={v}
                  aria-pressed={view === v}
                  className={view === v ? "active" : ""}
                  onClick={() => setView(v)}
                >
                  {v}
                </button>
              ))}
            </div>
            <button
              type="button"
              className="planner-icon-button"
              aria-label="Refresh planner"
              disabled={result.isFetching}
              onClick={() => void refresh()}
            >
              <RefreshCw className={result.isFetching ? "animate-spin" : ""} />
            </button>
            <button
              type="button"
              className={`planner-filter-button ${filtersOpen ? "active" : ""}`}
              aria-expanded={filtersOpen}
              onClick={() => setFiltersOpen(!filtersOpen)}
            >
              <SlidersHorizontal />
              Filters
            </button>
            <button
              type="button"
              className="planner-icon-button"
              aria-label="Planner settings"
              aria-expanded={settingsOpen}
              onClick={() => setSettingsOpen(!settingsOpen)}
            >
              <Settings2 />
            </button>
          </div>
        </div>
        {upcoming && (
          <div className="planner-upcoming">
            <button onClick={() => openEvent(upcoming)}>
              {prefs.show_event_details ? upcoming.title : "Upcoming meeting"} ·{" "}
              {prefs.show_time_left && Date.parse(upcoming.start_at) <= now
                ? `${Math.max(0, Math.ceil((Date.parse(upcoming.end_at) - now) / 60000))} min left`
                : new Date(upcoming.start_at).toLocaleString([], {
                    timeZone: prefs.timezone,
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
            </button>
            {upcoming.meeting_url.startsWith("https://") &&
              Date.parse(upcoming.start_at) - now <=
                prefs.quick_join * 60000 && (
                <a href={upcoming.meeting_url} target="_blank" rel="noreferrer">
                  Join ↗
                </a>
              )}
          </div>
        )}
        <div className="planner-search-row">
          <button
            type="button"
            className="planner-mobile-tasks"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            <Target />
            My tasks
          </button>
          <div className="planner-search">
            <Search />
            <input
              ref={searchRef}
              aria-label="Search planner"
              placeholder="Search tasks, milestones, projects…"
              value={query}
              onChange={(e) => change("q", e.target.value)}
            />
            {query && (
              <button
                type="button"
                aria-label="Clear search"
                onClick={() => change("q", "")}
              >
                <X />
              </button>
            )}
          </div>
          <label className="planner-jump">
            <CalendarDays />
            <input
              aria-label="Jump to date"
              type="date"
              value={dateKey(anchor)}
              onChange={(e) => {
                if (validDate(e.target.value)) change("date", e.target.value);
              }}
            />
          </label>
        </div>
        {filtersOpen && (
          <div className="planner-filters">
            <label>
              Project
              <select
                aria-label="Planner project"
                value={project}
                onChange={(e) => change("project", e.target.value)}
              >
                <option value="">All projects</option>
                {data?.projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Assignee
              <select
                aria-label="Planner assignee"
                value={assignee}
                onChange={(e) => change("person", e.target.value)}
              >
                <option value="">Everyone</option>
                {data?.people.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Item type
              <select
                aria-label="Planner item type"
                value={itemType}
                onChange={(e) => setItemType(e.target.value)}
              >
                <option value="all">All items</option>
                <option value="task">Tasks</option>
                <option value="milestone">Milestones</option>
                <option value="project">Project deadlines</option>
                <option value="event">Events / focus</option>
              </select>
            </label>
            <label className="planner-checkbox">
              <input
                type="checkbox"
                checked={includeDone}
                onChange={(e) => setIncludeDone(e.target.checked)}
              />
              Show completed
            </label>
            <button
              type="button"
              onClick={() => {
                setParams({ date: dateKey(anchor), view });
                setItemType("all");
                setIncludeDone(true);
              }}
            >
              Reset filters
            </button>
          </div>
        )}

        {saveError && (
          <div role="alert" className="planner-error">
            {saveError}
          </div>
        )}
        {notice && (
          <div role="status" className="planner-notice">
            {notice}
            {undo && (
              <button
                type="button"
                disabled={busy}
                onClick={() => void undoSchedule()}
              >
                Undo date change
              </button>
            )}
          </div>
        )}
        {result.isPending && (
          <div className="planner-loading" role="status">
            Loading your planner…
          </div>
        )}
        {result.error && (
          <div className="planner-error" role="alert">
            Your schedule could not load. Please try again.
            <button type="button" onClick={() => void refresh()}>
              Retry
            </button>
          </div>
        )}
        {preferencesQuery.error && (
          <p role="alert" className="planner-error">
            Calendar settings could not load.{" "}
            <button onClick={() => void preferencesQuery.refetch()}>
              Retry settings
            </button>
          </p>
        )}
        {eventQuery.error && (
          <p role="alert" className="planner-error">
            Calendar events could not load.{" "}
            <button onClick={() => void eventQuery.refetch()}>
              Retry events
            </button>
          </p>
        )}
        {view === "Week" && prefs.week_numbers && (
          <p className="planner-week-number">ISO week {format(anchor, "II")}</p>
        )}
        {data && !result.error && (
          <>
            {view === "Month" || view === "Week" ? (
              <div className="planner-calendar-scroll">
                <div
                  className={`planner-calendar ${view === "Week" ? "week" : ""}`}
                  style={
                    {
                      "--planner-columns": weekends ? 7 : 5,
                    } as React.CSSProperties
                  }
                >
                  <div className="planner-weekdays">
                    {days.slice(0, weekends ? 7 : 5).map((d) => (
                      <span key={dateKey(d)}>{format(d, "EEE")}</span>
                    ))}
                  </div>
                  <div className="planner-date-grid">
                    {days.map((day) => {
                      const key = dateKey(day);
                      const entries = items.filter((i) => i.date === key);
                      return (
                        <div
                          key={key}
                          className={`planner-day ${!isSameMonth(day, anchor) && view === "Month" ? "outside" : ""} ${key === today ? "today" : ""} ${dragOver === key ? "drag-over" : ""}`}
                          onDragOver={(e) => {
                            if (dragTask.current || dragEvent.current) {
                              e.preventDefault();
                              e.dataTransfer.dropEffect = "move";
                              setDragOver(key);
                            }
                          }}
                          onDragLeave={() => setDragOver("")}
                          onDrop={(e) => {
                            e.preventDefault();
                            setDragOver("");
                            if (dragEvent.current) {
                              const moving = dragEvent.current;
                              dragEvent.current = null;
                              const event = eventQuery.data?.find(
                                (e) => e.id === moving.id,
                              );
                              if (event) void moveEvent(event, key, moving.day);
                              return;
                            }
                            const task = data.tasks.find(
                              (t) => t.id === dragTask.current,
                            );
                            dragTask.current = null;
                            if (task) void schedule(task, key);
                          }}
                        >
                          <div className="planner-day-heading">
                            <button
                              type="button"
                              aria-label={`View ${format(day, "EEEE, MMMM d, yyyy")}`}
                              onClick={() => {
                                changeMany({ date: key, view: "Day" });
                              }}
                            >
                              {format(day, "d")}
                            </button>
                            <button
                              type="button"
                              aria-label={`Add task on ${key}`}
                              className="planner-day-add"
                              disabled={!canCreate}
                              onClick={() => openCreate(key)}
                            >
                              <Plus />
                            </button>
                          </div>
                          {entries.slice(0, compact ? 2 : 4).map(chip)}
                          {entries.length > (compact ? 2 : 4) && (
                            <button
                              type="button"
                              className="planner-more"
                              onClick={() => {
                                changeMany({ date: key, view: "Day" });
                              }}
                            >
                              + {entries.length - (compact ? 2 : 4)} more
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            ) : (
              <div className="planner-agenda">
                {(view === "Day"
                  ? [anchor]
                  : days.filter((d) =>
                      rangeItems.some((i) => i.date === dateKey(d)),
                    )
                ).map((day) => (
                  <section key={dateKey(day)}>
                    <div className="planner-agenda-heading">
                      <h3>{format(day, "EEEE, MMMM d")}</h3>
                      <button
                        type="button"
                        onClick={() => openCreate(dateKey(day))}
                        disabled={!canCreate}
                      >
                        <Plus />
                        Add task
                      </button>
                    </div>
                    {items
                      .filter((i) => i.date === dateKey(day))
                      .map((item) => (
                        <div className="planner-agenda-item" key={item.key}>
                          {chip(item)}
                          <span>
                            {
                              data.projects.find(
                                (p) => p.id === item.project_id,
                              )?.name
                            }
                          </span>
                          <small>{item.status}</small>
                        </div>
                      ))}
                    {!items.some((i) => i.date === dateKey(day)) && (
                      <p className="planner-agenda-empty">
                        A little breathing room. Nothing scheduled for this day.
                      </p>
                    )}
                  </section>
                ))}
                {view === "List" && !rangeItems.length && (
                  <div className="planner-large-empty">
                    <CalendarDays />
                    <h3>A clear calendar</h3>
                    <p>
                      No scheduled items match this month and these filters.
                    </p>
                    <button
                      type="button"
                      onClick={() => openCreate(dateKey(anchor))}
                      disabled={!canCreate}
                    >
                      <Plus />
                      Plan a task
                    </button>
                  </div>
                )}
              </div>
            )}
            <footer className="planner-legend">
              <span>
                <i className="task" />
                Task
              </span>
              <span>
                <i className="milestone" />
                Milestone
              </span>
              <span>
                <i className="project" />
                Project deadline
              </span>
              <small>
                {rangeItems.length} scheduled items · {prefs.timezone} · Task
                deadlines are date-only
              </small>
            </footer>
          </>
        )}
      </section>
      <Dialog.Root
        open={!!selected}
        onOpenChange={(open) => {
          if (!open && !busy) setSelected(null);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="planner-dialog-overlay" />
          <Dialog.Content
            className="planner-detail"
            onEscapeKeyDown={(e) => {
              if (busy) e.preventDefault();
            }}
          >
            <div className="planner-detail-top">
              <span>{selected?.type}</span>
              <Dialog.Close disabled={busy} aria-label="Close planner item">
                <X />
              </Dialog.Close>
            </div>
            <Dialog.Title>{selected?.title}</Dialog.Title>
            <Dialog.Description>
              {data?.projects.find((p) => p.id === selected?.project_id)?.name}{" "}
              · {selected?.status}
            </Dialog.Description>
            {selected?.task && (
              <>
                <div className="planner-detail-description"><RichTextContent value={selected.task.description || "No description yet."}/></div>
                <p className="planner-detail-meta">
                  {selected.task.priority} priority · {selected.task.task_key}
                </p>
                <label>
                  Due date
                  <input
                    aria-label="Schedule task date"
                    type="date"
                    defaultValue={selected.task.due_date || ""}
                    key={selected.key}
                    disabled={busy || !selected.task.can_schedule}
                    onChange={(e) => {
                      if (validDate(e.target.value) && selected.task)
                        void schedule(selected.task, e.target.value);
                    }}
                  />
                </label>
                {!selected.task.can_schedule && (
                  <p className="planner-detail-meta">
                    You have read-only access to this project.
                  </p>
                )}
                <div className="planner-detail-actions">
                  <button
                    type="button"
                    disabled={busy || !selected.task.can_schedule}
                    onClick={() =>
                      selected.task && void toggleDone(selected.task)
                    }
                  >
                    <CheckCircle2 />
                    {done(selected.task.status)
                      ? "Reopen task"
                      : "Mark complete"}
                  </button>
                  <button type="button" onClick={() => togglePin(selected.id)}>
                    <Pin />
                    {pins.includes(selected.id) ? "Unpin" : "Pin priority"}
                  </button>
                </div>
                <Link to={`/pms/tasks/${selected.id}`}>
                  Open full task <ArrowUpRight />
                </Link>
              </>
            )}
            {selected?.projected && (
              <p className="planner-detail-meta">
                Projected occurrence. It becomes a real task when the previous
                occurrence is completed.{" "}
                <Link to={`/pms/tasks/${selected.id}`}>
                  Open recurring task
                </Link>
              </p>
            )}
            {selected?.task && (
              <button
                className="planner-filter-button"
                onClick={() => {
                  setSelected(null);
                  openEvent(null, selected.date, selected.id);
                }}
              >
                Block focus time
              </button>
            )}
            {selected && selected.type !== "task" && (
              <Link
                to={`/pms/projects/${selected.project_id}${selected.type === "milestone" ? "/milestones" : ""}`}
              >
                Open project <ArrowUpRight />
              </Link>
            )}
            {saveError && (
              <p role="alert" className="planner-error">
                {saveError}
              </p>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <CalendarSettings
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        value={prefs}
        revision={preferencesQuery.data?.revision || 0}
        onSaved={(saved) => {
          client.setQueryData(["pms-calendar-preferences", userId], saved);
          setNotice("Calendar settings saved.");
        }}
        projects={data?.projects || []}
        onExport={() =>
          saveCalendarFile(
            calendarICS(
              rangeItems.flatMap((i) => (i.event ? [i.event] : [])),
              rangeItems
                .filter((i) => !i.event)
                .map((i) => ({ id: i.key, title: i.title, due_date: i.date })),
            ),
            "karyaflow-calendar.ics",
            "text/calendar",
          )
        }
      />
      <CalendarEventEditor
        open={eventOpen}
        event={editingEvent}
        day={eventDay}
        taskId={eventTask}
        tasks={data?.tasks || []}
        prefs={prefs}
        onClose={() => setEventOpen(false)}
        onSaved={() => {
          refreshEvents();
          setNotice("Calendar updated.");
        }}
      />
      <CreateTaskModal
        isOpen={createOpen}
        onClose={() => setCreateOpen(false)}
        projectId={createProject}
        initialDueDate={createDate}
        projects={data?.projects.filter((p) => p.can_schedule)}
        onTaskCreated={(_task, another) => {
          if (!another) setCreateOpen(false);
          setUndo(null);
          void refresh();
          setNotice("Task created and added to your planner.");
        }}
      />
    </div>
  );
}
