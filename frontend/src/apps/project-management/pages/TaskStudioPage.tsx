import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Link,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  ArrowLeft,
  Sparkles,
  Save,
  FileText,
  Folder,
  Type,
  Users,
  UserRound,
  GraduationCap,
  Check,
  Plus,
  X,
  Search,
  CalendarDays,
  Flag,
  Circle,
  Bug,
  Lightbulb,
  BarChart3,
  MoreHorizontal,
  Copy,
  ListChecks,
  Trash2,
  Upload,
  ArrowRight,
  ChevronRight,
} from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import RichTextEditor from "@/components/rich-text/LazyRichText";
import AskAiButton from "@/components/ai-agents/AskAiButton";
import { projectsAPI, tasksAPI, filesAPI } from "../services/api";
import {
  CustomFieldsForm,
  fieldPath,
  type FieldRecord,
  type FieldDraft,
} from "../components/CustomFields";
import TaskExecutionPanel from "../components/TaskExecutionPanel";
import AddExistingPeopleDialog from "../components/people/AddExistingPeopleDialog";
import { ManagePersonButton } from "../components/people/PersonIdentity";
import type {
  PMSProject,
  PMSTask,
  PMSChecklistItem,
  PMSFileAsset,
} from "../types";
import { workspaceError } from "./workspaceTypes";
import "./TaskStudioPage.css";

type StudioProject = Pick<
  PMSProject,
  "id" | "name" | "project_key" | "workspace_id"
> & { can_manage_tasks: boolean };
type Person = {
  id: number;
  name: string;
  email: string;
  photo_url?: string | null;
  role?: string;
  availability?: string;
};
type Group = {
  id: number;
  name: string;
  member_ids: number[];
  excluded_count: number;
  member_count?: number;
  population_count?: number;
};
type Selection = {
  people: number[];
  teams: number[];
  batches: number[];
  reviewer: number | null;
  owner: number | null;
  allow_partial_groups: boolean;
};
type Options = {
  people: Person[];
  teams: Group[];
  batches: Group[];
  reviewers: number[];
  workspace_id?: number;
  can_edit: boolean;
  can_add_existing: boolean;
  batch_reason: string;
};
type Draft = {
  projectId: number;
  title: string;
  description: string;
  work_type: string;
  priority: string;
  status: string;
  start_date: string;
  due_date: string;
  story_points: string;
  assignment: Selection;
  task_key: string;
  custom_fields: FieldDraft;
  execution_mode?: "shared" | "individual";
};
type Detail = {
  task: PMSTask;
  assignment: Selection;
  version: string;
  can_edit: boolean;
  protected_ids: number[];
  protected_count?: number;
  retained_people?: Person[];
};
const base = "/project-management/task-studio";
const emptySelection = (): Selection => ({
  people: [],
  teams: [],
  batches: [],
  reviewer: null,
  owner: null,
  allow_partial_groups: false,
});
const dateLabel = (value: string) =>
  value
    ? new Date(value + "T00:00:00").toLocaleDateString("en-US", {
        month: "short",
        day: "2-digit",
        year: "numeric",
      })
    : "Not set";
function Photo({ person }: { person?: Person }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [person?.photo_url]);
  return person?.photo_url && !failed ? (
    <img
      src={person.photo_url}
      alt={person.name}
      className="ts-photo"
      onError={() => setFailed(true)}
    />
  ) : (
    <span className="ts-photo ts-initials">
      {(person?.name || person?.email || "?")
        .split(" ")
        .slice(0, 2)
        .map((n) => n[0])
        .join("")
        .toUpperCase()}
    </span>
  );
}
function Section({
  icon,
  title,
  sub,
  children,
}: {
  icon: ReactNode;
  title: string;
  sub?: string;
  children: ReactNode;
}) {
  return (
    <section className="ts-section">
      <header>
        <span className="ts-section-icon">{icon}</span>
        <div>
          <h2>{title}</h2>
          {sub && <p>{sub}</p>}
        </div>
      </header>
      {children}
    </section>
  );
}
function PeoplePicker({
  label,
  people,
  value,
  onChange,
  single = false,
  disabled = false,
  protectedIds = [],
  projectId,
  reviewers = false,
}: {
  label: string;
  people: Person[];
  value: number[];
  onChange: (ids: number[]) => void;
  single?: boolean;
  disabled?: boolean;
  protectedIds?: number[];
  projectId: number;
  reviewers?: boolean;
}) {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [remote, setRemote] = useState<{
    items: Person[];
    selected: Person[];
    pages: number;
  }>();
  const [pickerError, setPickerError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      if (projectId)
        api
          .get(`${base}/people`, {
            params: {
              project_id: projectId,
              q,
              page,
              selected: value.slice(0, 100).join(","),
              reviewers,
            },
          })
          .then((r) => {
            if (active) {
              setRemote(r.data);
              setPickerError("");
            }
          })
          .catch((e) => {
            if (active) setPickerError(workspaceError(e));
          });
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [projectId, q, page, value.join(","), reviewers, retry]);
  const known = [
    ...new Map(
      [...people, ...(remote?.items || []), ...(remote?.selected || [])].map(
        (p) => [p.id, p],
      ),
    ).values(),
  ];
  return (
    <div className="ts-picker">
      <details>
        <summary aria-label={label}>
          <Search size={15} />
          <span>
            {single && value.length
              ? known.find((p) => p.id === value[0])?.name ||
                `Person ${value[0]}`
              : label}
          </span>
          <ChevronRight size={14} />
        </summary>
        <div className="ts-picker-list">
          <input
            aria-label={`Search ${label}`}
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
            placeholder="Name, email or role…"
          />
          {(remote?.items || people)
            .filter((p) =>
              `${p.name} ${p.email} ${p.role}`
                .toLowerCase()
                .includes(q.toLowerCase()),
            )
            .map((p) => (
              <div className="ts-picker-row" key={p.id}>
                <label>
                  <input
                    type="checkbox"
                    disabled={disabled || protectedIds.includes(p.id)}
                    checked={value.includes(p.id)}
                    onChange={(e) =>
                      onChange(
                        e.target.checked
                          ? single
                            ? [p.id]
                            : [...value, p.id]
                          : value.filter((id) => id !== p.id),
                      )
                    }
                  />
                  <Photo person={p} />
                  <span>
                    <strong>{p.name}</strong>
                    <small>
                      {p.email} · {p.role} · {p.availability}
                    </small>
                    {protectedIds.includes(p.id) && (
                      <small>Managed by Batch controls</small>
                    )}
                  </span>
                </label>
                <ManagePersonButton userId={p.id} projectId={projectId} />
              </div>
            ))}
          {pickerError && (
            <p role="alert">
              {pickerError}
              <button type="button" onClick={() => setRetry((v) => v + 1)}>
                Retry
              </button>
            </p>
          )}
          {remote && remote.pages > 1 && (
            <div>
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((v) => v - 1)}
              >
                Previous
              </button>{" "}
              Page {page} of {remote.pages}{" "}
              <button
                type="button"
                disabled={page >= remote.pages}
                onClick={() => setPage((v) => v + 1)}
              >
                Next
              </button>
            </div>
          )}
          {remote?.items.length === 0 && <p>No eligible people match.</p>}
        </div>
      </details>
      <div className="ts-chips">
        {value.map((id) => (
          <span key={id}>
            <Photo person={known.find((p) => p.id === id)} />
            {known.find((p) => p.id === id)?.name || `Person ${id}`}
            <button
              type="button"
              disabled={disabled || protectedIds.includes(id)}
              aria-label={`Remove ${known.find((p) => p.id === id)?.name || id} from ${label}`}
              onClick={() => onChange(value.filter((v) => v !== id))}
            >
              <X size={11} />
            </button>
          </span>
        ))}
      </div>
    </div>
  );
}
export default function TaskStudioPage() {
  const { taskId } = useParams();
  const id = Number(taskId) || 0;
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const { user } = useAuthStore();
  const initial = (): Draft => ({
    projectId: Number(params.get("projectId")) || 0,
    title: params.get("title") || "",
    description: "",
    work_type: params.get("workType") || "Task",
    priority: "Medium",
    status: "To Do",
    start_date: "",
    due_date: params.get("dueDate") || "",
    story_points: "",
    assignment: {
      ...emptySelection(),
      ...Object.fromEntries(
        (["people", "teams", "batches"] as const).map((kind) => [
          kind,
          (params.get(kind) || "")
            .split(",")
            .map(Number)
            .filter((id) => Number.isInteger(id) && id > 0),
        ]),
      ),
    },
    task_key: `TSK-${crypto.randomUUID().slice(0, 12)}`,
    custom_fields: {},
  });
  const [draft, setDraft] = useState<Draft>(initial);
  const [saved, setSaved] = useState("");
  const [detail, setDetail] = useState<Detail>();
  const [job, setJob] = useState<{
    id: number;
    task_id: number;
    status: string;
    total: number;
    processed: number;
    error?: string;
  }>();
  const [projects, setProjects] = useState<StudioProject[]>([]);
  const [options, setOptions] = useState<Options>();
  const [mode, setMode] = useState<"people" | "teams" | "batches">(
    params.get("batches")
      ? "batches"
      : params.get("teams")
        ? "teams"
        : "people",
  );
  const [groupSearch, setGroupSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(location.state?.notice || "");
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [revision, setRevision] = useState(0);
  const [loadRevision, setLoadRevision] = useState(0);
  const [createAnother, setCreateAnother] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [copyOpen, setCopyOpen] = useState(false);
  const [copyTasks, setCopyTasks] = useState<PMSTask[]>([]);
  const [draftAvailable, setDraftAvailable] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [attachments, setAttachments] = useState<PMSFileAsset[]>([]);
  const [checklist, setChecklist] = useState<PMSChecklistItem[]>([]);
  const [checkTitle, setCheckTitle] = useState("");
  const [checkBusy, setCheckBusy] = useState<number[]>([]);
  const [types, setTypes] = useState([
    "Task",
    "Bug",
    "Feature",
    "Improvement",
    "Research",
    "Documentation",
  ]);
  const [extraDirty, setExtraDirty] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);
  const pickerRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const created = useRef<number>();
  const uploaded = useRef(new Set<string>());
  const allowNavigation = useRef(false);
  const draftKey = `pms-task-studio:${user?.id}:${id || "new"}`;
  const dirty =
    (!!saved && saved !== JSON.stringify(draft)) ||
    files.length > 0 ||
    extraDirty;
  const editable = id ? !!detail?.can_edit : options ? options.can_edit : true;
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((d) => ({ ...d, [key]: value }));
  const assign = (changes: Partial<Selection>) =>
    setDraft((d) => ({ ...d, assignment: { ...d.assignment, ...changes } }));
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    setDetail(undefined);
    created.current = undefined;
    uploaded.current.clear();
    setFiles([]);
    setExtraDirty(false);
    allowNavigation.current = false;
    Promise.all([
      api
        .get<StudioProject[]>(`${base}/projects`, {
          params: {
            people: params.get("people") || undefined,
            teams: params.get("teams") || undefined,
            batches: params.get("batches") || undefined,
          },
        })
        .then((r) => r.data),
      id
        ? api.get<Detail>(`${base}/tasks/${id}`).then((r) => r.data)
        : Promise.resolve(undefined),
      id
        ? api.get<FieldRecord>(fieldPath("task", id)).then((r) => r.data)
        : Promise.resolve(undefined),
    ])
      .then(([p, record, fieldRecord]) => {
        if (!active) return;
        setProjects(p);
        let d = initial();
        if (record) {
          setDetail(record);
          const t = record.task;
          d = {
            ...d,
            projectId: t.project_id,
            title: t.title,
            description: t.description || "",
            work_type: t.work_type || "Task",
            priority: t.priority,
            status: t.status,
            start_date: t.start_date || "",
            due_date: t.due_date || "",
            story_points: t.story_points == null ? "" : String(t.story_points),
            task_key: t.task_key,
            custom_fields: Object.fromEntries(
              (fieldRecord?.fields || []).map((field) => [
                String(field.id),
                {
                  value: field.value ?? null,
                  country_code: field.country_code || undefined,
                },
              ]),
            ),
            assignment: { ...emptySelection(), ...record.assignment },
          };
          setAttachments([]);
          void tasksAPI
            .listAttachments(id)
            .then(setAttachments)
            .catch((e) => setError(workspaceError(e)));
          void tasksAPI
            .listChecklists(id)
            .then(setChecklist)
            .catch((e) => setError(workspaceError(e)));
        } else if (!d.projectId)
          d.projectId = p.find((project) => project.can_manage_tasks)?.id || 0;
        setDraft(d);
        setSaved(JSON.stringify(d));
        setDraftAvailable(!!localStorage.getItem(draftKey));
      })
      .catch((e) => {
        if (active) setError(workspaceError(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [id, loadRevision]);
  useEffect(() => {
    if (!draft.projectId) return;
    let active = true;
    setOptions(undefined);
    api
      .get<Options>(`${base}/options`, {
        params: { project_id: draft.projectId, compact: true },
      })
      .then((r) => {
        if (active) setOptions(r.data);
      })
      .catch((e) => {
        if (active) setError(workspaceError(e));
      });
    return () => {
      active = false;
    };
  }, [draft.projectId, revision]);
  useEffect(() => {
    api
      .get("/project-management/task-types")
      .then(({ data }) =>
        setTypes((t) => [
          ...new Set([
            ...t,
            ...(data.types || [])
              .filter((x: { archived: boolean }) => !x.archived)
              .map((x: { name: string }) => x.name),
          ]),
        ]),
      )
      .catch(() => {});
  }, []);
  useEffect(() => {
    if (!dirty) return;
    const guard = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", guard);
    const click = (e: MouseEvent) => {
      try {
        localStorage.setItem(draftKey, JSON.stringify(draft));
      } catch {
        /* Explicit Save Draft reports storage errors. */
      }
      const link = (e.target as HTMLElement).closest?.(
        "a[href]",
      ) as HTMLAnchorElement | null;
      if (
        link &&
        link.origin === window.location.origin &&
        link.pathname !== window.location.pathname &&
        !allowNavigation.current &&
        !window.confirm(
          "Leave this task with unsaved changes? Save a draft first to keep your work.",
        )
      ) {
        e.preventDefault();
        e.stopPropagation();
      }
    };
    document.addEventListener("click", click, true);
    return () => {
      window.removeEventListener("beforeunload", guard);
      document.removeEventListener("click", click, true);
    };
  }, [dirty, draft, draftKey]);
  const selectedGroups = useMemo(
    () => [
      ...(options?.teams || []).filter((g) =>
        draft.assignment.teams.includes(g.id),
      ),
      ...(options?.batches || []).filter((g) =>
        draft.assignment.batches.includes(g.id),
      ),
    ],
    [options, draft.assignment],
  );
  const ids = [
    ...new Set([
      ...draft.assignment.people,
      ...selectedGroups.flatMap((g) => g.member_ids),
    ]),
  ];
  const excluded = selectedGroups.reduce((n, g) => n + g.excluded_count, 0);
  const people = [
    ...(options?.people || []),
    ...(detail?.retained_people || []).filter(
      (person) =>
        !options?.people.some((existing) => existing.id === person.id),
    ),
  ];
  const selectedPeople = ids
    .map((id) => people.find((p) => p.id === id))
    .filter((p): p is Person => !!p);
  const project = projects.find((p) => p.id === draft.projectId);
  function saveDraft() {
    try {
      localStorage.setItem(draftKey, JSON.stringify(draft));
      setDraftAvailable(true);
      setNotice(
        "Draft saved on this device. Attached files must be selected again after leaving.",
      );
    } catch {
      setError(
        "This browser could not save the draft. Keep this page open and retry.",
      );
    }
  }
  function restoreDraft() {
    try {
      const d = JSON.parse(localStorage.getItem(draftKey) || "null");
      if (d?.title !== undefined && d?.assignment) {
        setDraft({ ...initial(), ...d });
        setNotice(
          "Saved draft restored. Review the current project members before saving.",
        );
      }
    } catch {
      setError("The saved draft could not be restored.");
    }
  }
  async function save() {
    if (extraDirty) {
      setError(
        "Save or discard the execution-panel changes before saving task details.",
      );
      return;
    }
    if (!formRef.current?.reportValidity()) return;
    if (!options || !draft.projectId) {
      setError("Choose a project and wait for assignment options to load.");
      return;
    }
    if (
      draft.start_date &&
      draft.due_date &&
      draft.start_date > draft.due_date
    ) {
      setError("Start date cannot be after due date.");
      return;
    }
    if (
      draft.execution_mode !== "individual" &&
      excluded &&
      !draft.assignment.allow_partial_groups
    ) {
      setError(
        "Review excluded group members and acknowledge assigning eligible members only.",
      );
      return;
    }
    setBusy(true);
    setError("");
    try {
      const task = {
        title: draft.title.trim(),
        description: draft.description,
        work_type: draft.work_type,
        task_key: draft.task_key,
        priority: draft.priority,
        status: draft.status,
        start_date: draft.start_date || null,
        due_date: draft.due_date || null,
        story_points:
          draft.story_points === "" ? null : Number(draft.story_points),
        custom_fields: draft.custom_fields,
      };
      if (!id && draft.execution_mode === "individual") {
        if (!draft.assignment.reviewer || !draft.due_date)
          throw new Error(
            "Choose a reviewer and due date for individual assignments.",
          );
        if (
          draft.assignment.teams.length ||
          (draft.assignment.people.length && draft.assignment.batches.length)
        )
          throw new Error(
            "Choose batches or individual interns. Remove other selections first.",
          );
        if (files.length)
          throw new Error(
            "Save individual assignments first, then attach evidence to the parent task.",
          );
        const result = (
          await api.post(
            "/project-management/people-workspace/individual-tasks/" +
              draft.projectId,
            {
              task,
              people: draft.assignment.people,
              batches: draft.assignment.batches,
              reviewer_user_id: draft.assignment.reviewer,
              request_key: draft.task_key,
            },
          )
        ).data;
        setJob(result);
        setSaved(JSON.stringify(draft));
        localStorage.removeItem(draftKey);
        setNotice(
          "Individual assignments published. Each intern has an independent execution and review record.",
        );
        return;
      }
      let record: Detail;
      if (id || created.current) {
        record = (
          await api.put<Detail>(`${base}/tasks/${id || created.current}`, {
            task,
            assignment: draft.assignment,
            version: detail?.version,
          })
        ).data;
      } else {
        record = (
          await api.post<Detail>(`${base}/projects/${draft.projectId}/tasks`, {
            task,
            assignment: draft.assignment,
          })
        ).data;
        created.current = record.task.id;
      }
      setDetail(record);
      for (let i = 0; i < files.length; i++) {
        const key = `${files[i].name}-${files[i].size}-${files[i].lastModified}`;
        if (!uploaded.current.has(key)) {
          await filesAPI.uploadToTask(record.task.id, files[i]);
          uploaded.current.add(key);
          const completedFile = files[i];
          setFiles((current) =>
            current.filter((file) => file !== completedFile),
          );
        }
      }
      localStorage.removeItem(draftKey);
      setDraftAvailable(false);
      setFiles([]);
      setSaved(JSON.stringify(draft));
      setNotice(
        id ? "Task and assignments updated." : "Task created successfully.",
      );
      if (!id && createAnother) {
        const next = {
          ...initial(),
          projectId: draft.projectId,
          assignment: emptySelection(),
        };
        setDraft(next);
        setSaved(JSON.stringify(next));
        setDetail(undefined);
        created.current = undefined;
        uploaded.current.clear();
        window.scrollTo({ top: 0 });
      } else if (!id) {
        allowNavigation.current = true;
        navigate(`/pms/tasks/${record.task.id}`, {
          replace: true,
          state: { notice: "Task created successfully." },
        });
      } else {
        setAttachments(await tasksAPI.listAttachments(id));
      }
    } catch (e) {
      setError(
        `${created.current && !id ? "Task is saved. Retry to finish without creating a duplicate. " : ""}${workspaceError(e)}`,
      );
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    setBusy(true);
    try {
      await tasksAPI.delete(id);
      localStorage.removeItem(draftKey);
      allowNavigation.current = true;
      navigate("/pms/tasks");
    } catch (e) {
      setError(workspaceError(e));
    } finally {
      setBusy(false);
    }
  }
  async function loadCopy() {
    setCopyOpen(true);
    try {
      setCopyTasks(await tasksAPI.list(draft.projectId));
    } catch (e) {
      setError(workspaceError(e));
    }
  }
  function resetBlank() {
    if (
      dirty &&
      !window.confirm("Replace the current draft with a blank task?")
    )
      return;
    const d = { ...initial(), projectId: draft.projectId };
    setDraft(d);
    setFiles([]);
    setNotice("Blank task ready.");
  }
  async function addCheck() {
    if (!checkTitle.trim()) return;
    try {
      await tasksAPI.addChecklistItem(id, { title: checkTitle.trim() });
      setChecklist(await tasksAPI.listChecklists(id));
      setCheckTitle("");
    } catch (e) {
      setError(workspaceError(e));
    }
  }
  if (loading)
    return (
      <main className="task-studio ts-loading" role="status">
        Loading task workspace…
      </main>
    );
  return (
    <main className="task-studio" id="suite-main" tabIndex={-1}>
      <div className="ts-breadcrumb">
        <Link to="/dashboard">All applications</Link>
        <ChevronRight />
        <Link to="/pms">KaryaFlow PMS</Link>
        <ChevronRight />
        <Link to="/pms/tasks">Tasks</Link>
        <ChevronRight />
        <b>{id ? "Task Details" : "Create Task"}</b>
      </div>
      <div className="ts-title">
        <button
          className="tr-button ts-back"
          aria-label="Back to tasks"
          onClick={() => {
            if (
              !dirty ||
              window.confirm(
                "Leave with unsaved changes? Save a draft to keep your work.",
              )
            )
              navigate("/pms/tasks");
          }}
        >
          <ArrowLeft size={18} />
        </button>
        <div>
          <h1>{id ? "Task Details" : "Create Task"}</h1>
          <p>
            {id
              ? "Review, update, and manage this task and its members."
              : "Add a new task to keep your project on track and move work forward."}
          </p>
        </div>
        <div className="ts-title-actions">
          <button className="tr-button" disabled={busy} onClick={saveDraft}>
            <Save size={17} />
            Save Draft
          </button>
          <button
            className="tr-primary"
            disabled={busy || !!job || !editable || !options?.can_edit}
            onClick={() => void save()}
          >
            <Sparkles size={19} />
            {busy ? "Saving…" : id ? "Save Changes" : "Create Task"}
          </button>
        </div>
      </div>
      {(error || notice) && (
        <div
          className={`tr-feedback ${error ? "error" : ""}`}
          role={error ? "alert" : "status"}
        >
          {error || notice}
          {error && (
            <button onClick={() => setRevision((v) => v + 1)}>
              Reload options
            </button>
          )}
          <button
            aria-label="Dismiss message"
            onClick={() => {
              setError("");
              setNotice("");
            }}
          >
            <X size={16} />
          </button>
        </div>
      )}
      {!!id && error && (
        <button
          type="button"
          className="tr-button"
          onClick={() => {
            saveDraft();
            setLoadRevision((v) => v + 1);
          }}
        >
          Reload latest task; keep my draft
        </button>
      )}
      {draftAvailable && (
        <div className="ts-draft-banner">
          A saved draft is available for this {id ? "task" : "new task"}.{" "}
          <button onClick={restoreDraft}>Restore draft</button>
          <button
            onClick={() => {
              localStorage.removeItem(draftKey);
              setDraftAvailable(false);
            }}
          >
            Discard saved draft
          </button>
        </div>
      )}
      {!editable && (
        <p className="tr-feedback">
          Your project role allows viewing this task. Ask a project
          administrator for editing access.
        </p>
      )}
      <form
        ref={formRef}
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
        className="ts-layout"
      >
        <div className="ts-fields">
          <fieldset disabled={busy || (!!id && !editable)}>
            <Section
              icon={<FileText />}
              title="1. Basic Info"
              sub="Provide the essential details about the task."
            >
              <div className="ts-basic-pair">
                <label className="ts-field">
                  <Folder />
                  <span>
                    Project <b>*</b>
                    <select
                      required
                      aria-label="Project"
                      value={draft.projectId || ""}
                      disabled={!!id || !!created.current}
                      onChange={(e) => {
                        setDraft((d) => ({
                          ...d,
                          projectId: Number(e.target.value),
                          assignment: emptySelection(),
                          custom_fields: {},
                        }));
                        setNotice(
                          "Project changed. Assignment selections were cleared to protect access boundaries.",
                        );
                      }}
                    >
                      <option value="">Choose a project</option>
                      {projects.map((p) => (
                        <option
                          key={p.id}
                          value={p.id}
                          disabled={!id && !p.can_manage_tasks}
                        >
                          {p.name}　{p.project_key}
                        </option>
                      ))}
                    </select>
                  </span>
                </label>
                <label className="ts-field">
                  <Type />
                  <span>
                    Task Title <b>*</b>
                    <input
                      aria-label="Task Title"
                      required
                      maxLength={220}
                      placeholder="What needs to be done?"
                      value={draft.title}
                      onChange={(e) => set("title", e.target.value)}
                    />
                    <small>
                      Be clear and specific about what needs to be done.
                    </small>
                  </span>
                </label>
              </div>
              <div className="ts-field ts-worktype">
                <FileText />
                <div>
                  <label>
                    Work item type <b>*</b>
                  </label>
                  <div role="group" aria-label="Work item type">
                    {types
                      .filter((type) =>
                        [
                          "Task",
                          "Bug",
                          "Feature",
                          "Improvement",
                          "Research",
                          "Documentation",
                        ].includes(type),
                      )
                      .map((type) => {
                        const Icon =
                          type === "Bug"
                            ? Bug
                            : type === "Feature"
                              ? Lightbulb
                              : type === "Improvement"
                                ? BarChart3
                                : type === "Research"
                                  ? Search
                                  : FileText;
                        return (
                          <button
                            type="button"
                            key={type}
                            className={
                              draft.work_type === type ? "selected" : ""
                            }
                            aria-pressed={draft.work_type === type}
                            onClick={() => set("work_type", type)}
                          >
                            <Icon size={16} />
                            {type}
                            {draft.work_type === type && <Check size={13} />}
                          </button>
                        );
                      })}
                    <select
                      aria-label="Other work item types"
                      value={
                        [
                          "Task",
                          "Bug",
                          "Feature",
                          "Improvement",
                          "Research",
                          "Documentation",
                        ].includes(draft.work_type)
                          ? ""
                          : draft.work_type
                      }
                      onChange={(e) => {
                        if (e.target.value) set("work_type", e.target.value);
                      }}
                    >
                      <option value="">•••　Other</option>
                      {types
                        .filter(
                          (type) =>
                            ![
                              "Task",
                              "Bug",
                              "Feature",
                              "Improvement",
                              "Research",
                              "Documentation",
                              ...(!id ? ["Sub-task"] : []),
                            ].includes(type),
                        )
                        .map((type) => (
                          <option key={type}>{type}</option>
                        ))}
                    </select>{" "}
                  </div>
                </div>
              </div>
              <div className="ts-field ts-description">
                <FileText />
                <div>
                  <label>Description</label>
                  <RichTextEditor
                    label="Task description"
                    value={draft.description}
                    onChange={(v) => set("description", v)}
                    variant="compact"
                    placeholder="Add details, context, or acceptance criteria…"
                    onAttach={() => fileRef.current?.click()}
                  />
                </div>
              </div>
            </Section>
            <div ref={pickerRef}>
              <Section
                icon={<Users />}
                title="2. Assignment"
                sub="Assign this task to a person, team, or interns batch."
              >
                {!id && (
                  <div className="ts-execution-choice">
                    <label>
                      Execution mode
                      <select
                        aria-label="Execution mode"
                        value={draft.execution_mode || "shared"}
                        onChange={(e) =>
                          set(
                            "execution_mode",
                            e.target.value as "shared" | "individual",
                          )
                        }
                      >
                        <option value="shared">
                          Shared task � one task for selected collaborators
                        </option>
                        <option value="individual">
                          Individual intern assignments � separate progress,
                          submission and review
                        </option>
                      </select>
                    </label>
                    <p>
                      {draft.execution_mode === "individual"
                        ? "Choose linked intern batches or individual interns, a deadline and reviewer. Large batches are processed in resumable chunks of 500."
                        : "Share this task with up to 100 collaborators. Groups use a snapshot of their eligible members."}
                    </p>
                  </div>
                )}
                {job && (
                  <div className="ts-job" role="status">
                    <strong>
                      {job.status}: {job.processed} of {job.total} assignments
                    </strong>
                    <progress max={job.total} value={job.processed} />
                    {job.error && <p role="alert">{job.error}</p>}
                    {job.status !== "Completed" && (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={async () => {
                          setBusy(true);
                          try {
                            setJob(
                              (
                                await api.post(
                                  `/project-management/people-workspace/assignment-jobs/${job.id}/continue`,
                                )
                              ).data,
                            );
                          } catch (e) {
                            setError(workspaceError(e));
                          } finally {
                            setBusy(false);
                          }
                        }}
                      >
                        {job.status === "Failed"
                          ? "Retry failed chunk"
                          : "Continue next 500"}
                      </button>
                    )}
                    <Link
                      to={`/pms/tasks/${job.task_id}/classic`}
                      onClick={() => {
                        allowNavigation.current = true;
                      }}
                    >
                      Open task and individual progress
                    </Link>
                    <Link
                      to="/hrms/interns/tasks"
                      onClick={() => {
                        allowNavigation.current = true;
                      }}
                    >
                      Open Intern Hub tracking
                    </Link>
                    <small>
                      Committed chunks remain saved if you leave. Pending chunks
                      are handled by the existing distribution worker or the
                      Continue action.
                    </small>
                  </div>
                )}
                {(detail?.protected_count || 0) > 100 && (
                  <p role="status">
                    {detail?.protected_count} managed individual assignments.
                    Edit task details here; use the execution panel or Batch
                    controls for recipient progress and membership.
                  </p>
                )}
                <div className="ts-assignment-cards">
                  {[
                    {
                      key: "people" as const,
                      title: "Person",
                      sub: "Assign to individual team members",
                      icon: UserRound,
                    },
                    {
                      key: "teams" as const,
                      title: "Team",
                      sub: "Assign to an existing team",
                      icon: Users,
                    },
                    {
                      key: "batches" as const,
                      title: "Interns Batch",
                      sub: "Assign to a batch of interns",
                      icon: GraduationCap,
                    },
                  ].map((m) => (
                    <button
                      type="button"
                      key={m.key}
                      aria-pressed={mode === m.key}
                      className={mode === m.key ? "selected" : ""}
                      onClick={() => setMode(m.key)}
                    >
                      <span>
                        <m.icon />
                      </span>
                      <div>
                        <strong>{m.title}</strong>
                        <small>{m.sub}</small>
                      </div>
                      {mode === m.key && <Check size={15} />}
                    </button>
                  ))}
                </div>
                <div className="ts-assignment-body">
                  <div>
                    <label>
                      {mode === "people"
                        ? "Select assignees"
                        : "Select " +
                          (mode === "teams" ? "teams" : "intern batches")}{" "}
                      <b>*</b>
                    </label>
                    {!options ? (
                      <p role="status">Loading assignment options…</p>
                    ) : mode === "people" ? (
                      <PeoplePicker
                        label="Select assignees"
                        people={people}
                        value={draft.assignment.people}
                        protectedIds={detail?.protected_ids}
                        disabled={!editable}
                        projectId={draft.projectId}
                        onChange={(v) => assign({ people: v })}
                      />
                    ) : (
                      <div className="ts-group-picker">
                        <label className="ts-group-search">
                          <Search size={15} />
                          <input
                            aria-label="Search groups"
                            placeholder="Search and select multiple groups…"
                            value={groupSearch}
                            onChange={(e) => setGroupSearch(e.target.value)}
                          />
                        </label>
                        {options[mode]
                          .filter((g) =>
                            g.name
                              .toLowerCase()
                              .includes(groupSearch.toLowerCase()),
                          )
                          .map((g) => (
                            <label key={g.id} className="ts-group-row">
                              <input
                                type="checkbox"
                                checked={draft.assignment[mode].includes(g.id)}
                                disabled={
                                  draft.execution_mode === "individual" &&
                                  mode === "batches"
                                    ? !g.population_count
                                    : !g.member_ids.length
                                }
                                onChange={(e) =>
                                  assign({
                                    [mode]: e.target.checked
                                      ? [...draft.assignment[mode], g.id]
                                      : draft.assignment[mode].filter(
                                          (v) => v !== g.id,
                                        ),
                                  })
                                }
                              />
                              <span>
                                <strong>{g.name}</strong>
                                <small>
                                  {g.member_count ?? g.member_ids.length}{" "}
                                  eligible · {g.excluded_count} excluded
                                  (missing access, inactive account, or outside
                                  your scope)
                                </small>
                              </span>
                            </label>
                          ))}
                        {!options[mode].length && (
                          <p>
                            {mode === "batches"
                              ? options.batch_reason
                              : "No teams in this workspace. Create a team from workspace management."}
                          </p>
                        )}
                      </div>
                    )}
                    <div className="ts-group-chips">
                      {options &&
                        (["teams", "batches"] as const).flatMap((kind) =>
                          draft.assignment[kind]
                            .filter(
                              (id) => !options[kind].some((g) => g.id === id),
                            )
                            .map((id) => (
                              <span key={`missing-${kind}-${id}`}>
                                Unavailable{" "}
                                {kind === "teams" ? "team" : "batch"} #{id}
                                <button
                                  type="button"
                                  aria-label={`Remove unavailable ${kind} ${id}`}
                                  onClick={() =>
                                    assign({
                                      [kind]: draft.assignment[kind].filter(
                                        (v) => v !== id,
                                      ),
                                    })
                                  }
                                >
                                  <X size={11} />
                                </button>
                              </span>
                            )),
                        )}
                      {["teams", "batches"].map((kind) =>
                        (options?.[kind as "teams" | "batches"] || [])
                          .filter((g) =>
                            draft.assignment[
                              kind as "teams" | "batches"
                            ].includes(g.id),
                          )
                          .map((g) => (
                            <span key={`${kind}-${g.id}`}>
                              {g.name}
                              <button
                                type="button"
                                aria-label={`Remove group ${g.name}`}
                                onClick={() =>
                                  assign({
                                    [kind]: draft.assignment[
                                      kind as "teams" | "batches"
                                    ].filter((v) => v !== g.id),
                                  })
                                }
                              >
                                <X size={11} />
                              </button>
                            </span>
                          )),
                      )}
                    </div>
                    <button
                      type="button"
                      className="ts-add-person"
                      onClick={() => setAdding(true)}
                      disabled={!draft.projectId || !options?.can_add_existing}
                      title={
                        !options?.can_add_existing
                          ? "Only a workspace or project administrator can add existing people."
                          : "Add an existing person immediately"
                      }
                    >
                      <Plus size={13} />
                      Add existing person
                    </button>
                    {!!selectedGroups.length && (
                      <small className="ts-snapshot-note">
                        Groups assign a snapshot of their current eligible
                        members. Future membership changes do not silently
                        change this task.
                      </small>
                    )}
                    {excluded > 0 && (
                      <label className="ts-exclusion">
                        <input
                          type="checkbox"
                          checked={draft.assignment.allow_partial_groups}
                          onChange={(e) =>
                            assign({ allow_partial_groups: e.target.checked })
                          }
                        />
                        I reviewed {excluded} excluded group memberships. Assign
                        eligible members only.
                      </label>
                    )}
                  </div>
                  <div>
                    <label>
                      Reviewer <small>(optional)</small>
                    </label>
                    <PeoplePicker
                      label="Select reviewer"
                      reviewers
                      people={people.filter((p) =>
                        options?.reviewers.includes(p.id),
                      )}
                      value={
                        draft.assignment.reviewer
                          ? [draft.assignment.reviewer]
                          : []
                      }
                      single
                      projectId={draft.projectId}
                      onChange={(v) => assign({ reviewer: v[0] || null })}
                    />
                  </div>
                </div>
                <div className="ts-owner">
                  <label>
                    Owner <small>(optional)</small>
                  </label>
                  <PeoplePicker
                    label="Select owner"
                    people={options?.people || []}
                    value={
                      draft.assignment.owner ? [draft.assignment.owner] : []
                    }
                    single
                    projectId={draft.projectId}
                    onChange={(v) => assign({ owner: v[0] || null })}
                  />
                </div>
                {!!detail?.protected_ids.length && (
                  <p className="ts-snapshot-note">
                    Some assignments are managed by an intern program. Use Batch
                    controls to reassign or remove them while preserving work
                    history.
                  </p>
                )}
              </Section>
            </div>
            <Section
              icon={<CalendarDays />}
              title="3. Schedule"
              sub="Set timeline, priority, and status for this task."
            >
              <div className="ts-schedule">
                <label>
                  Start date
                  <input
                    type="date"
                    aria-label="Start date"
                    value={draft.start_date}
                    onChange={(e) => set("start_date", e.target.value)}
                  />
                </label>
                <label>
                  Due date
                  <input
                    type="date"
                    aria-label="Due date"
                    value={draft.due_date}
                    min={draft.start_date || undefined}
                    onChange={(e) => set("due_date", e.target.value)}
                  />
                </label>
                <label>
                  Priority
                  <select
                    aria-label="Priority"
                    value={draft.priority}
                    onChange={(e) => set("priority", e.target.value)}
                  >
                    {["Low", "Medium", "High", "Urgent"].map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Status
                  <select
                    aria-label="Status"
                    value={draft.status}
                    onChange={(e) => set("status", e.target.value)}
                  >
                    {[
                      "Backlog",
                      "To Do",
                      "In Progress",
                      "In Review",
                      ...(id ? ["Blocked"] : []),
                      "Done",
                      "Cancelled",
                    ].map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Story points
                  <input
                    type="number"
                    min={0}
                    step={1}
                    aria-label="Story points"
                    value={draft.story_points}
                    onChange={(e) => set("story_points", e.target.value)}
                  />
                </label>
              </div>
            </Section>
            <Section
              icon={<ListChecks />}
              title="4. Details & attachments"
              sub="Keep required project fields and supporting evidence together."
            >
              <CustomFieldsForm
                entity="task"
                projectId={draft.projectId}
                workType={draft.work_type}
                values={draft.custom_fields}
                onChange={(v) => set("custom_fields", v)}
              />
              <label
                className="ts-upload"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  if (!busy && editable)
                    setFiles((f) => [
                      ...f,
                      ...Array.from(e.dataTransfer.files),
                    ]);
                }}
              >
                <Upload size={23} />
                <span>
                  <strong>Add supporting files</strong>
                  <small>
                    Choose or drop evidence, screenshots, and documents. Files
                    upload when you save.
                  </small>
                </span>
                <input
                  ref={fileRef}
                  type="file"
                  multiple
                  aria-label="Upload task attachments"
                  onChange={(e) =>
                    setFiles((f) => [...f, ...Array.from(e.target.files || [])])
                  }
                />
              </label>
              {files.map((f, i) => (
                <div key={i} className="ts-file-row">
                  {f.name}
                  <button
                    type="button"
                    aria-label={`Remove pending file ${f.name}`}
                    onClick={() =>
                      setFiles((f) => f.filter((_, index) => index !== i))
                    }
                  >
                    <X size={14} />
                  </button>
                </div>
              ))}
              {attachments.map((f) => (
                <div key={f.id} className="ts-file-row">
                  {f.original_name || f.file_name}
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        const blob = await filesAPI.downloadBlob(f.id);
                        const url = URL.createObjectURL(blob);
                        const link = document.createElement("a");
                        link.href = url;
                        link.download = f.original_name || f.file_name;
                        link.click();
                        setTimeout(() => URL.revokeObjectURL(url), 5000);
                      } catch (e) {
                        setError(workspaceError(e));
                      }
                    }}
                  >
                    Download
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete attachment ${f.original_name || f.file_name}`}
                    onClick={async () => {
                      if (!window.confirm("Delete this attachment?")) return;
                      try {
                        await filesAPI.deleteAttachment(f.id);
                        setAttachments((v) => v.filter((x) => x.id !== f.id));
                      } catch (e) {
                        setError(workspaceError(e));
                      }
                    }}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </Section>
          </fieldset>
          {!!id && (
            <>
              <Section
                icon={<ListChecks />}
                title="5. Completion checklist"
                sub="Add, edit, and remove the checks required for delivery."
              >
                {checklist.map((item) => (
                  <div className="ts-check-row" key={item.id}>
                    <input
                      aria-label={`Complete ${item.title}`}
                      type="checkbox"
                      disabled={!editable || checkBusy.includes(item.id)}
                      checked={item.is_completed}
                      onChange={(e) => {
                        const checked = e.target.checked;
                        setChecklist((rows) =>
                          rows.map((row) =>
                            row.id === item.id
                              ? { ...row, is_completed: checked }
                              : row,
                          ),
                        );
                        setCheckBusy((ids) => [...ids, item.id]);
                        void tasksAPI
                          .updateChecklistItem(item.id, {
                            is_completed: checked,
                          })
                          .then(() => tasksAPI.listChecklists(id))
                          .then(setChecklist)
                          .catch((e) => {
                            setError(workspaceError(e));
                            void tasksAPI.listChecklists(id).then(setChecklist);
                          })
                          .finally(() =>
                            setCheckBusy((ids) =>
                              ids.filter((value) => value !== item.id),
                            ),
                          );
                      }}
                    />
                    <input
                      aria-label={`Checklist title ${item.id}`}
                      defaultValue={item.title}
                      disabled={!editable}
                      onBlur={async (e) => {
                        if (e.target.value === item.title) return;
                        try {
                          await tasksAPI.updateChecklistItem(item.id, {
                            title: e.target.value,
                          });
                          setChecklist(await tasksAPI.listChecklists(id));
                        } catch (e) {
                          setError(workspaceError(e));
                        }
                      }}
                    />
                    <button
                      type="button"
                      disabled={!editable}
                      aria-label={`Delete checklist ${item.title}`}
                      onClick={async () => {
                        try {
                          await tasksAPI.deleteChecklistItem(item.id);
                          setChecklist(await tasksAPI.listChecklists(id));
                        } catch (e) {
                          setError(workspaceError(e));
                        }
                      }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
                <div className="ts-check-row">
                  <input
                    aria-label="New checklist item"
                    disabled={!editable}
                    placeholder="Add a delivery check…"
                    value={checkTitle}
                    onChange={(e) => setCheckTitle(e.target.value)}
                  />
                  <button
                    type="button"
                    className="tr-button"
                    disabled={!editable || !checkTitle.trim()}
                    onClick={() => void addCheck()}
                  >
                    <Plus size={15} />
                    Add check
                  </button>
                </div>
              </Section>
              <TaskExecutionPanel
                taskId={id}
                refreshKey={checklist
                  .map(
                    (item) => `${item.id}:${item.title}:${item.is_completed}`,
                  )
                  .join("|")}
                onDirtyChange={setExtraDirty}
                onChanged={() => {
                  void api
                    .get<Detail>(`${base}/tasks/${id}`)
                    .then(({ data }) => {
                      setDetail(data);
                      setDraft((d) => ({ ...d, status: data.task.status }));
                      setSaved((previous) => {
                        const value = JSON.parse(previous);
                        return JSON.stringify({
                          ...value,
                          status: data.task.status,
                        });
                      });
                    })
                    .catch((e) => setError(workspaceError(e)));
                }}
              />
              <section className="ts-danger">
                <div>
                  <strong>Delete task</strong>
                  <p>
                    Move this task to Trash. Its saved history remains available
                    for authorized recovery.
                  </p>
                </div>
                <button
                  type="button"
                  className="tr-button"
                  disabled={!editable || busy}
                  onClick={() => setDeleteOpen(true)}
                >
                  <Trash2 size={16} />
                  Delete task
                </button>
              </section>
              <Link className="ts-classic-link" to={`/pms/tasks/${id}/classic`}>
                Open activity, conversations, subtasks, and advanced tools{" "}
                <ArrowRight size={15} />
              </Link>
            </>
          )}
          <div className="ts-bottom">
            <span role="status">
              {dirty ? "Unsaved changes" : "All task details saved"}
            </span>
            {!id && (
              <label>
                <input
                  type="checkbox"
                  checked={createAnother}
                  onChange={(e) => setCreateAnother(e.target.checked)}
                />
                Create another
              </label>
            )}
            <button
              className="tr-primary"
              type="submit"
              disabled={busy || !!job || !editable || !options?.can_edit}
            >
              {id ? "Save Changes" : "Create Task"}
            </button>
          </div>
        </div>
        <aside className="ts-right">
          <section className="ts-summary">
            <header>
              <span className="ts-section-icon">
                <Users />
              </span>
              <div>
                <h2>Assignment Summary</h2>
                <small>
                  {draft.execution_mode === "individual" &&
                  selectedGroups.length
                    ? "Whole batches selected; exact unique recipient count appears after publishing"
                    : selectedGroups.some(
                          (g) => (g.member_count || 0) > g.member_ids.length,
                        )
                      ? "Group preview (first 100); server validates all eligible members"
                      : `${detail?.protected_count && detail.protected_count > 100 ? detail.protected_count : ids.length} assignees selected`}
                </small>
                <div className="ts-summary-photos">
                  {selectedPeople.slice(0, 5).map((p) => (
                    <Photo key={p.id} person={p} />
                  ))}
                  <button
                    type="button"
                    onClick={() => {
                      pickerRef.current?.scrollIntoView({
                        behavior: "smooth",
                        block: "center",
                      });
                      setMode("people");
                      pickerRef.current?.querySelector("summary")?.focus();
                    }}
                  >
                    <Plus size={13} />
                    Add more
                  </button>
                </div>
              </div>
            </header>
            {[
              {
                icon: Users,
                label: "Assignees",
                value:
                  selectedPeople.map((p) => p.name).join(", ") ||
                  "No one assigned",
              },
              {
                icon: Folder,
                label: "Project",
                value: project?.name || "Choose a project",
              },
              { icon: Flag, label: "Work item type", value: draft.work_type },
              { icon: Search, label: "Priority", value: draft.priority },
              {
                icon: CalendarDays,
                label: "Start date",
                value: dateLabel(draft.start_date),
              },
              {
                icon: CalendarDays,
                label: "Due date",
                value: dateLabel(draft.due_date),
              },
              { icon: Circle, label: "Status", value: draft.status },
            ].map((row) => (
              <div className="ts-summary-row" key={row.label}>
                <row.icon size={15} />
                <span>{row.label}</span>
                <strong
                  className={row.label === "Priority" ? "ts-priority" : ""}
                >
                  {row.value}
                </strong>
              </div>
            ))}
          </section>
          <section className="ts-ai">
            <div>
              <Sparkles size={20} />
              <strong>AI Assist</strong>
              <small>Project context</small>
            </div>
            <h3>Suggest task details with AI</h3>
            <p>
              Get help with the title, description, subtasks, and acceptance
              criteria.
            </p>
            <div onClickCapture={saveDraft}>
              <AskAiButton
                module="PMS"
                relatedEntityType="task"
                relatedEntityId={id || undefined}
                defaultPrompt={`Help plan this task in ${project?.name || "my project"}: ${draft.title}`}
                buttonLabel="Generate with AI"
              />
            </div>
          </section>
          <section className="ts-quick">
            <header>
              <div>
                <h2>⚡ Quick Actions</h2>
                <small>Save time with templates and shortcuts.</small>
              </div>
              <button type="button" onClick={() => setCopyOpen(true)}>
                View all ›
              </button>
            </header>
            <div>
              <button type="button" onClick={resetBlank} disabled={!!id}>
                <Plus />
                Blank task<small>Start from scratch</small>
              </button>
              <button type="button" onClick={() => void loadCopy()}>
                <Copy />
                Copy from existing<small>Use a similar task</small>
              </button>
              <button
                type="button"
                onClick={() => {
                  if (draft.description) {
                    setNotice(
                      "The description already has content. Clear it before applying this template, or use Copy from existing.",
                    );
                    return;
                  }
                  set(
                    "description",
                    draft.description ||
                      "Objective:\n\nAcceptance criteria:\n- \n\nDelivery evidence:\n",
                  );
                  setNotice("Task structure inserted into the description.");
                }}
              >
                <FileText />
                Use template<small>Structured task brief</small>
              </button>
              <button
                type="button"
                onClick={() => {
                  if (!id) {
                    setNotice(
                      "Create the task first, then add completion checks and subtasks.",
                    );
                    return;
                  }
                  navigate(`/pms/tasks/${id}/classic`);
                }}
              >
                <ListChecks />
                Create subtasks<small>Break into smaller tasks</small>
              </button>
            </div>
          </section>
          <section className="ts-tips">
            <h2>💡 Tips for creating great tasks</h2>
            {[
              "Use a clear and descriptive title",
              "Add acceptance criteria in the description",
              "Assign the right person, team, or batch",
              "Set a realistic due date and priority",
              "Include evidence needed for completion",
            ].map((t) => (
              <p key={t}>
                <Check size={13} />
                {t}
              </p>
            ))}
          </section>
        </aside>
      </form>
      <AddExistingPeopleDialog
        open={adding}
        onClose={() => setAdding(false)}
        projectId={draft.projectId}
        personIds={draft.assignment.people}
        workspaceId={options?.workspace_id}
        onAdded={(ids) => {
          setRevision((v) => v + 1);
          assign({
            people: [...new Set([...draft.assignment.people, ...ids])],
          });
        }}
      />
      <Dialog.Root
        open={deleteOpen}
        onOpenChange={(v) => {
          if (!busy) setDeleteOpen(v);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="ts-modal-overlay" />
          <Dialog.Content
            className="ts-modal"
            aria-describedby="ts-delete-description"
          >
            <Dialog.Title>Delete this task?</Dialog.Title>
            <p>
              {draft.task_key} · {draft.title}
            </p>
            <Dialog.Description id="ts-delete-description">
              This removes the task from active views and moves its saved
              details to Trash.
            </Dialog.Description>
            <button
              className="tr-button"
              type="button"
              disabled={busy}
              onClick={() => setDeleteOpen(false)}
            >
              Keep task
            </button>
            <button
              className="tr-primary"
              type="button"
              disabled={busy}
              onClick={() => void remove()}
            >
              Move to Trash
            </button>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <Dialog.Root open={copyOpen} onOpenChange={setCopyOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="ts-modal-overlay" />
          <Dialog.Content className="ts-modal">
            <Dialog.Title>Copy task details</Dialog.Title>
            <Dialog.Description>
              Copy a title, work type, description, and priority. Members and
              dates stay under your control.
            </Dialog.Description>
            {copyTasks.map((t) => (
              <button
                type="button"
                key={t.id}
                onClick={() => {
                  setDraft((d) => ({
                    ...d,
                    title: `Copy of ${t.title}`,
                    description: t.description || "",
                    work_type: t.work_type || "Task",
                    priority: t.priority,
                  }));
                  setCopyOpen(false);
                }}
              >
                {t.task_key} · {t.title}
              </button>
            ))}
            {!copyTasks.length && (
              <button
                type="button"
                className="tr-button"
                onClick={() => void loadCopy()}
              >
                Load existing tasks
              </button>
            )}
            <button
              type="button"
              className="tr-button"
              onClick={() => setCopyOpen(false)}
            >
              Close
            </button>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </main>
  );
}
