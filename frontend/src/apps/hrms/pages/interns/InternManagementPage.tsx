import { RichTextField, RichTextContent, richTextPlainText } from "@/components/rich-text/LazyRichText";
import {
  useDeferredValue,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Users,
  Layers,
  ClipboardList,
  CheckCircle2,
  Clock,
  Star,
  GraduationCap,
  Plus,
  Search,
  Download,
  ArrowRight,
  BarChart3,
  Target,
  Send,
  FileText,
  RefreshCw,
  ExternalLink,
  ShieldCheck,
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "@/hooks/use-toast";
import WorkReviewPanel from "@/apps/project-management/components/WorkReviewPanel";
import InternApplicationsPage from "./InternApplicationsPage";
import InternsHubAdminPage from "./InternsHubAdminPage";
import "./intern-management.css";
type Row = Record<string, any>;
type Page = "dashboard" | "batches" | "tasks" | "reviews" | "performance";
const root = "/interns-hub/management";
const pages = [
  ["dashboard", "Dashboard", BarChart3],
  ["batches", "Batches & Interns", Users],
  ["tasks", "Task Assignment", ClipboardList],
  ["reviews", "Daily Reports & Reviews", FileText],
  ["performance", "Performance & Completion", GraduationCap],
] as const;
const titles: Record<Page, [string, string]> = {
  dashboard: [
    "Intern Management Dashboard",
    "Overview of intern programs, batches, PMS assignments, reviews and performance.",
  ],
  batches: [
    "Batch & Intern Management",
    "Organize interns into cohorts, allocate mentors, and manage enrollment at scale.",
  ],
  tasks: [
    "Task Assignment Center",
    "Create PMS assignments for individual interns, selected groups, batches or eligible participants.",
  ],
  reviews: [
    "Daily Reports & Submission Review",
    "One operational queue for intern reports, PMS evidence, revisions and mentor reviews.",
  ],
  performance: [
    "Performance & Completion",
    "Compare batch outcomes, identify support needs and approve internship completion.",
  ],
};
const clean = (value: Row) =>
  Object.fromEntries(
    Object.entries(value).filter(
      ([, v]) => v !== "" && v !== undefined && v !== null,
    ),
  );
const date = (v?: string) =>
  v ? new Date(v + "T12:00:00").toLocaleDateString("en-IN") : "—";
const day = () => new Date().toLocaleDateString("en-CA");
function Panel({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className="im-panel">
      <div className="im-panel-head">
        <h2>{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}
function Metric({
  label,
  value,
  icon: Icon,
  note,
}: {
  label: string;
  value: any;
  icon: any;
  note?: string;
}) {
  return (
    <div className="im-metric">
      <span>
        <Icon size={23} />
      </span>
      <small>{label}</small>
      <strong>{value ?? "—"}</strong>
      <p>{note || "Live authoritative records"}</p>
    </div>
  );
}
function Status({ value }: { value: any }) {
  return (
    <span
      className={`im-status ${/Active|Approved|Completed|Done|Eligible/.test(String(value)) ? "good" : /Failed|Rejected|Missing|Overdue|Incomplete/.test(String(value)) ? "bad" : /Pending|Upcoming|Revision|Correction/.test(String(value)) ? "warn" : ""}`}
    >
      {value || "—"}
    </span>
  );
}
function Table({
  columns,
  rows,
  empty = "No matching records yet.",
}: {
  columns: Array<[string, (row: Row) => ReactNode]>;
  rows: Row[];
  empty?: string;
}) {
  return (
    <div className="im-table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map(([title]) => (
              <th key={title}>{title}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.id ?? i}>
              {columns.map(([title, render]) => (
                <td key={title}>{render(r)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <p className="im-empty">{empty}</p>}
    </div>
  );
}
function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="im-field">
      <span>{label}</span>
      {children}
    </label>
  );
}
function Select({
  value,
  onChange,
  options,
  placeholder = "Select…",
  required = false,
}: {
  value: any;
  onChange: (v: string) => void;
  options: Row[];
  placeholder?: string;
  required?: boolean;
}) {
  return (
    <select
      required={required}
      value={value || ""}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">{placeholder}</option>
      {options.map((o) => (
        <option key={o.id} value={o.id}>
          {o.name || o.code || o.title}
        </option>
      ))}
    </select>
  );
}
function Pagination({
  page,
  setPage,
  total,
  size = 50,
}: {
  page: number;
  setPage: (v: number) => void;
  total: number;
  size?: number;
}) {
  return (
    <div className="im-pagination">
      <span>
        {total.toLocaleString()} authorized records · Page {page}
      </span>
      <Button
        size="sm"
        variant="outline"
        disabled={page <= 1}
        onClick={() => setPage(page - 1)}
      >
        Previous
      </Button>
      <Button
        size="sm"
        variant="outline"
        disabled={page * size >= total}
        onClick={() => setPage(page + 1)}
      >
        Next
      </Button>
    </div>
  );
}
export default function InternManagementPage({ page }: { page: Page }) {
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [filter, setFilter] = useState<Row>({
    department_id: "",
    batch_id: "",
    reporting_manager_id: "",
    mentor_id: "",
    program: "",
    internship_status: "",
    date_from: "",
    date_to: "",
  });
  const [current, setCurrent] = useState(1);
  const [tab, setTab] = useState(
    new URLSearchParams(location.search).get("tab") || "",
  );
  const [selected, setSelected] = useState<number[]>([]);
  const [allFiltered, setAllFiltered] = useState(false);
  const [batchDialog, setBatchDialog] = useState<Row | null>(null);
  const [membershipDialog, setMembershipDialog] = useState<Row | null>(null);
  const [history, setHistory] = useState<Row[] | null>(null);
  const [activeReview, setActiveReview] = useState<Row | null>(null);
  const [activeReport, setActiveReport] = useState<Row | null>(null);
  const [reportNote, setReportNote] = useState("");
  const [noticeDialog, setNoticeDialog] = useState(false);
  const [notice, setNotice] = useState({ title: "", message: "" });
  const [completion, setCompletion] = useState<Row | null>(null);
  const [completionNote, setCompletionNote] = useState("");
  const [assignment, setAssignment] = useState<Row>({
    project_id: "",
    task_id: "",
    title: "",
    description: "",
    category: "Project",
    priority: "Medium",
    target_type: "batches",
    batch_ids: [],
    employee_ids: [],
    exclude_ids: [],
    department_id: "",
    program: "",
    reviewer_user_id: "",
    maximum_score: 100,
    start_date: "",
    due_date: day(),
    estimated_hours: "",
    instructions: "",
    deliverables: "",
    review_instructions: "",
    recurrence: "",
    recurrence_until: "",
  });
  const key = useRef(crypto.randomUUID());
  const [preview, setPreview] = useState<Row | null>(null);
  const { data: access, isError: denied } = useQuery({
    queryKey: ["intern-management", "access"],
    queryFn: () => api.get(root + "/access").then((r) => r.data),
    retry: false,
  });
  const allowed = !!access?.allowed;
  const params = clean({ ...filter, include_employees:true, search: deferredSearch });
  const { data: options } = useQuery<Row>({
    queryKey: ["intern-management", "options"],
    queryFn: () => api.get(root + "/options").then((r) => r.data),
    enabled: allowed,
  });
  const { data: dashboard, error: dashboardError } = useQuery<Row>({
    queryKey: ["intern-management", "dashboard", params],
    queryFn: () => api.get(root + "/dashboard", { params }).then((r) => r.data),
    enabled: allowed && ["dashboard", "batches", "performance"].includes(page),
  });
  const { data: batches, error: batchesError } = useQuery<Row>({
    queryKey: ["intern-management", "batches", params, current],
    queryFn: () =>
      api
        .get(root + "/batches", {
          params: {
            search: page === "batches" ? deferredSearch : undefined,
            department_id: filter.department_id || undefined,
            mentor_id:filter.mentor_id||undefined,date_from:filter.date_from||undefined,date_to:filter.date_to||undefined,
            page: current,
            per_page: 50,
          },
        })
        .then((r) => r.data),
    enabled: allowed,
  });
  const { data: interns, error: internsError } = useQuery<Row>({
    queryKey: ["intern-management", "interns", params, current],
    queryFn: () =>
      api
        .get(root + "/interns", {
          params: { ...params, page: current, per_page: 50 },
        })
        .then((r) => r.data),
    enabled: allowed && ["batches", "tasks", "performance"].includes(page),
  });
  const { data: jobs, error: jobsError } = useQuery<Row>({
    queryKey: ["intern-management", "jobs", current],
    queryFn: () =>
      api
        .get(root + "/distributions", { params: { page: current } })
        .then((r) => r.data),
    enabled: allowed && page === "tasks",
    refetchInterval: page === "tasks" ? 10000 : false,
  });
  const { data: schedules } = useQuery<Row[]>({
    queryKey: ["intern-management", "schedules"],
    queryFn: () => api.get(root + "/schedules").then((r) => r.data),
    enabled: allowed && page === "tasks",
  });
  const { data: legacy } = useQuery<Row>({
    queryKey: ["intern-management", "legacy"],
    queryFn: () => api.get(root + "/legacy").then((r) => r.data),
    enabled: allowed && page === "tasks",
  });
  const { data: templates } = useQuery<Row>({
    queryKey: ["intern-management", "templates", assignment.project_id],
    queryFn: () =>
      api
        .get(root + `/projects/${assignment.project_id}/tasks`)
        .then((r) => r.data),
    enabled: allowed && page === "tasks" && !!assignment.project_id,
  });
  const { data: reports, error: reportsError } = useQuery<Row>({
    queryKey: ["intern-management", "reports", params, current, tab],
    queryFn: () =>
      api
        .get(root + "/reports", {
          params: {
            ...params,
            page: current,
            missing: tab === "Exceptions" || undefined,
          },
        })
        .then((r) => r.data),
    enabled:
      allowed &&
      page === "reviews" &&
      (!tab || ["Daily Reports", "Exceptions"].includes(tab)),
  });
  const { data: reviews, error: reviewsError } = useQuery<Row>({
    queryKey: ["intern-management", "reviews", params, current, tab],
    queryFn: () =>
      api
        .get(root + "/reviews", {
          params: {
            ...params,
            page: current,
            status:
              tab === "Pending Reviews"
                ? "Pending Review"
                : tab === "Revision Requests"
                  ? "Needs Revision"
                  : undefined,
          },
        })
        .then((r) => r.data),
    enabled:
      allowed &&
      page === "reviews" &&
      ["Task Submissions", "Pending Reviews", "Revision Requests"].includes(
        tab,
      ),
  });
  const { data: completions } = useQuery<Row>({
    queryKey: ["intern-management", "completions", current],
    queryFn: () =>
      api
        .get(root + "/completions", { params: { page: current } })
        .then((r) => r.data),
    enabled: allowed && page === "performance",
  });
  const { data: batchAnalytics, error: batchAnalyticsError } = useQuery<Row[]>({
    queryKey: ["intern-management", "batch-analytics", params],
    queryFn: () =>
      api.get(root + "/batch-analytics", { params }).then((r) => r.data),
    enabled: allowed && ["dashboard", "performance"].includes(page),
  });
  const mutation = useMutation({
    mutationFn: ({
      path,
      body,
      method = "post",
    }: {
      path: string;
      body?: any;
      method?: string;
    }) => api.request({ url: root + path, method, data: body }),
    onSuccess: (response) => {
      qc.invalidateQueries({ queryKey: ["intern-management"] });
      qc.invalidateQueries({ queryKey: ["pms-work"] });
      if (response.data?.errors?.length) {
        toast({title:'Some histories need attention',description:response.data.errors.slice(0,5).map((item:Row)=>`Task ${item.legacy_task_id}: ${item.reason}`).join('; '),variant:'destructive'});
      } else {
        toast({ title: "Intern Management updated" });
      }
    },
    onError: (e: any) =>
      toast({
        title: "Action not completed",
        description:
          typeof e.response?.data?.detail === "string"
            ? e.response.data.detail
            : "Check the fields and your HRMS/PMS permissions.",
        variant: "destructive",
      }),
  });
  const save = (
    path: string,
    body?: any,
    method = "post",
    success?: () => void,
  ) => mutation.mutate({ path, body, method }, { onSuccess: success });
  useEffect(() => {
    setCurrent(1);
    setTab(new URLSearchParams(location.search).get("tab") || "");
    setSelected([]);
    setAllFiltered(false);
  }, [page, location.search]);
  useEffect(() => {
    setCurrent(1);
    setSelected([]);
    setAllFiltered(false);
  }, [deferredSearch, JSON.stringify(filter)]);
  function updateAssignment(name: string, value: any) {
    setAssignment((a) => ({
      ...a,
      [name]: value,
      ...(name === "project_id" ? { task_id: "", reviewer_user_id: "" } : {}),
    }));
    setPreview(null);
    key.current = crypto.randomUUID();
  }
  function assignmentPayload() {
    return {
      ...assignment,
      program: assignment.program || filter.program,
      search: deferredSearch,
      project_id: Number(assignment.project_id),
      task_id: Number(assignment.task_id) || null,
      department_id: Number(assignment.department_id) || null,
      reviewer_user_id: Number(assignment.reviewer_user_id),
      maximum_score: Number(assignment.maximum_score),
      employee_ids: assignment.target_type === "interns" ? selected : [],
      start_date: assignment.start_date || null,
      estimated_hours:
        assignment.estimated_hours === ""
          ? null
          : Number(assignment.estimated_hours),
      recurrence: assignment.recurrence || null,
      recurrence_until: assignment.recurrence_until || null,
      idempotency_key: key.current,
    };
  }
  async function exportPage() {
    try {
      const r = await api.get(root + "/export", {
        params: { ...params, page: current },
        responseType: "blob",
      });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = "intern-performance.csv";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      toast({ title: "Export failed", variant: "destructive" });
    }
  }
  function newBatch() {
    setBatchDialog({
      name: "",
      code: "",
      department_id: "",
      manager_user_id: "",
      mentor_user_id: "",
      additional_mentors: [],
      project_id: "",
      program: "Internship",
      specialization: "",
      description: "",
      start_date: day(),
      end_date: new Date(Date.now() + 90 * 86400000).toLocaleDateString(
        "en-CA",
      ),
      capacity: 400,
      expected_hours: 8,
      reporting_frequency: "Daily",
      policy: {
        weights: {
          quality: 40,
          timeliness: 20,
          reports: 15,
          completion: 15,
          communication: 10,
        },
        completion: {
          minimum_days: 90,
          minimum_tasks: 1,
          minimum_reports_percent: 80,
          minimum_attendance_percent: 0,
        },
      },
    });
  }
  const choose = (id: number) =>
    setSelected((v) =>
      v.includes(id) ? v.filter((x) => x !== id) : [...v, id],
    );
  if (denied)
    return (
      <div role="alert" className="im-denied">
        <ShieldCheck />
        <h1>Manager/Admin access required</h1>
        <p>Your account does not have scoped Intern Management permission.</p>
      </div>
    );
  if (!allowed) return <p>Checking HRMS permissions…</p>;
  const d = dashboard || {};
  const batchRows = batches?.items || [];
  const people = interns?.items || [];
  const staff = options?.staff || [];
  const busy = mutation.isPending;
  const memberForm = membershipDialog || {};
  const loadError = [
    dashboardError,
    batchesError,
    internsError,
    jobsError,
    reportsError,
    reviewsError,
    batchAnalyticsError,
  ].find(Boolean);
  return (
    <div className="intern-management">
      {loadError && (
        <div role="alert" className="im-callout im-error">
          Some records could not load. Check your access or try again.
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              qc.invalidateQueries({ queryKey: ["intern-management"] })
            }
          >
            Retry
          </Button>
        </div>
      )}
      <div className="im-heading">
        <div>
          <h1>{titles[page][0]}</h1>
          <p>{titles[page][1]}</p>
        </div>
        <div className="im-actions">
          {page === "dashboard" && (
            <Button onClick={() => navigate("/hrms/interns/tasks")}>
              <Plus size={15} />
              Assign PMS Task
            </Button>
          )}
          {page === "batches" && (
            <Button onClick={newBatch}>
              <Plus size={15} />
              Create Batch
            </Button>
          )}
          {page === "reviews" || page === "performance" ? (
            <Button onClick={exportPage} variant="outline">
              <Download size={15} />
              Export Authorized Page
            </Button>
          ) : null}
        </div>
      </div>
      <nav className="im-page-nav" aria-label="Intern Management pages">
        {pages.map(([path, label, Icon]) => (
          <NavLink key={path} to={`/hrms/interns/${path}`}>
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="im-filters">
        <label>
          <Search size={16} />
          <Input
            aria-label="Search interns or batches"
            placeholder="Search interns, batches, reports…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <Select
          placeholder="All Departments"
          value={filter.department_id}
          options={options?.departments || []}
          onChange={(v) => setFilter({ ...filter, department_id: v })}
        />
        <Select
          placeholder="All Batches"
          value={filter.batch_id}
          options={options?.batches || []}
          onChange={(v) => setFilter({ ...filter, batch_id: v })}
        />
        <Input
          aria-label="Program filter"
          placeholder="Program"
          value={filter.program}
          onChange={(e) => setFilter({ ...filter, program: e.target.value })}
        />
        <details>
          <summary>More Filters</summary>
          <div className="im-more-filters">
            <Field label="Task / report date from">
              <Input
                type="date"
                value={filter.date_from}
                onChange={(e) =>
                  setFilter({ ...filter, date_from: e.target.value })
                }
              />
            </Field>
            <Field label="Date to">
              <Input
                type="date"
                value={filter.date_to}
                onChange={(e) =>
                  setFilter({ ...filter, date_to: e.target.value })
                }
              />
            </Field>
            <Field label="Reporting Manager (employee ID)">
              <Input
                type="number"
                value={filter.reporting_manager_id}
                onChange={(e) =>
                  setFilter({ ...filter, reporting_manager_id: e.target.value })
                }
              />
            </Field>
            <Field label="Mentor">
              <Select
                value={filter.mentor_id}
                options={staff}
                onChange={(v) => setFilter({ ...filter, mentor_id: v })}
              />
            </Field>
            <Field label="College">
              <Input
                value={filter.college || ""}
                onChange={(e) =>
                  setFilter({ ...filter, college: e.target.value })
                }
              />
            </Field>
            <Field label="Skill">
              <Input
                value={filter.skill || ""}
                onChange={(e) =>
                  setFilter({ ...filter, skill: e.target.value })
                }
              />
            </Field>
            <Field label="Internship status">
              <select
                value={filter.internship_status}
                onChange={(e) =>
                  setFilter({ ...filter, internship_status: e.target.value })
                }
              >
                <option value="">All Statuses</option>
                {[
                  "Active",
                  "Probation",
                  "On Leave",
                  "Resigned",
                  "Terminated",
                ].map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </Field>
          </div>
        </details>
      </div>
      {page === "dashboard" && (
        <>
          <div className="im-metrics">
            <Metric
              label="Total Participants"
              value={d.total_interns}
              icon={Users}
            />
            <Metric
              label="Active Batches"
              value={d.active_batches}
              icon={Layers}
              note={`${d.upcoming_batches || 0} upcoming`}
            />
            <Metric
              label="Assigned PMS Tasks"
              value={d.assigned_tasks}
              icon={ClipboardList}
            />
            <Metric
              label="Submissions Today"
              value={d.submissions_today}
              icon={CheckCircle2}
            />
            <Metric
              label="Average PMS Review"
              value={d.average_score == null ? "—" : `${d.average_score}/100`}
              icon={Star}
            />
            <Metric
              label="Pending Reviews"
              value={d.pending_reviews}
              icon={Clock}
            />
          </div>
          <div className="im-dashboard-charts">
            <Panel title="Intern Growth">
              <div className="im-chart">
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={d.growth || []}>
                    <CartesianGrid vertical={false} stroke="#eef0f9" />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} width={35} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#8266ff" radius={[5, 5, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
            <Panel title="Task Completion Status">
              <div
                className="im-ring"
                style={
                  {
                    "--pct": `${d.assigned_tasks ? (d.completed_tasks * 100) / d.assigned_tasks : 0}%`,
                  } as any
                }
              >
                <div>
                  <b>
                    {d.assigned_tasks
                      ? Math.round((d.completed_tasks * 100) / d.assigned_tasks)
                      : 0}
                    %
                  </b>
                  <small>Approved in PMS</small>
                </div>
              </div>
              <div className="im-mini-stats">
                <Status value={`${d.completed_tasks || 0} Done`} />
                <Status value={`${d.overdue || 0} Overdue`} />
              </div>
            </Panel>
            <Panel title="Interns by Department">
              <div className="im-bars">
                {(d.distribution || []).map((r: Row) => (
                  <div key={r.name}>
                    <span>{r.name}</span>
                    <progress
                      max={Math.max(d.total_interns || 1, 1)}
                      value={r.count}
                    />
                    <b>{r.count}</b>
                  </div>
                ))}
              </div>
            </Panel>
            <Panel title="Top Performing Batches">
              <Table
                rows={(batchAnalytics || [])
                  .slice()
                  .sort((a, b) => (b.score || 0) - (a.score || 0))
                  .slice(0, 6)}
                columns={[
                  ["Batch", (r) => r.name],
                  [
                    "PMS Review",
                    (r) => (r.score == null ? "—" : `${r.score}/100`),
                  ],
                ]}
              />
            </Panel>
          </div>
          <div className="im-three">
            <Panel title="Recent PMS Activity">
              {(d.activity || []).map((r: Row) => (
                <div className="im-activity" key={r.id}>
                  <span>
                    <CheckCircle2 size={18} />
                  </span>
                  <div>
                    {r.summary}
                    <small>{new Date(r.created_at).toLocaleString()}</small>
                  </div>
                </div>
              ))}
              {!d.activity?.length && (
                <p className="im-empty">No task activity yet.</p>
              )}
            </Panel>
            <Panel title="Upcoming Deadlines">
              <Table
                rows={d.deadlines || []}
                columns={[
                  [
                    "Task",
                    (r) => (
                      <Link to={`/pms/tasks/${r.task_id}`}>{r.title}</Link>
                    ),
                  ],
                  ["Due Date", (r) => date(r.due_date)],
                ]}
              />
            </Panel>
            <Panel title="Operational Queue">
              <div className="im-callout">
                <b>
                  {d.pending_applications || 0} pending onboarding applications
                </b>
                <Link to="/hrms/interns/batches?tab=Onboarding">
                  Review registrations <ArrowRight size={14} />
                </Link>
              </div>
              <p>{d.reports_today || 0} daily reports received today</p>
              <p>{d.completions || 0} manager-approved completions</p>
              <Button
                variant="outline"
                onClick={() => {
                  setNoticeDialog(true);
                  if (!selected.length)
                    toast({
                      title:
                        "Select recipients in Batches & Interns before sending an announcement",
                    });
                }}
              >
                Send Announcement
              </Button>
              <Link className="im-text-link" to="/hrms/interns/reviews">
                Open Review Queue →
              </Link>
            </Panel>
          </div>
          <Panel
            title="Batch Overview"
            action={
              <Button onClick={newBatch} size="sm">
                <Plus size={14} />
                Create Batch
              </Button>
            }
          >
            <BatchTable
              rows={batchRows}
              edit={setBatchDialog}
              membership={setMembershipDialog}
              save={save}
            />
          </Panel>
        </>
      )}
      {page === "batches" && (
        <>
          <div className="im-metrics five">
            <Metric
              label="Total Participants"
              value={d.total_interns}
              icon={Users}
            />
            <Metric
              label="Active Batches"
              value={d.active_batches}
              icon={Layers}
            />
            <Metric
              label="Approved Completions"
              value={d.completions}
              icon={GraduationCap}
            />
            <Metric
              label="Upcoming Batches"
              value={d.upcoming_batches}
              icon={Clock}
            />
            <Metric
              label="Assigned PMS Tasks"
              value={d.assigned_tasks}
              icon={ClipboardList}
            />
          </div>
          <Tabs
            values={[
              "Batches",
              "Participant Directory",
              "Onboarding",
              "Learning & Support",
            ]}
            current={tab || "Batches"}
            onChange={setTab}
          />
          {tab === "Onboarding" ? (
            <InternApplicationsPage />
          ) : tab === "Learning & Support" ? (
            <InternsHubAdminPage resourceOnly />
          ) : tab === "Participant Directory" ? (
            <Panel
              title="Participant Directory"
              action={
                <div className="im-actions">
                  <Button
                    size="sm"
                    disabled={!selected.length && !allFiltered}
                    onClick={() => setMembershipDialog({ action: "add" })}
                  >
                    Add to Batch
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setNoticeDialog(true)}
                  >
                    Send Announcement
                  </Button>
                </div>
              }
            >
              <label className="im-check">
                <input
                  type="checkbox"
                  checked={allFiltered}
                  onChange={(e) => {
                    setAllFiltered(e.target.checked);
                    setSelected([]);
                  }}
                />
                Select the entire authorized filtered group (
                {interns?.total || 0})
              </label>
              <Table
                rows={people}
                columns={[
                  [
                    "Select",
                    (r) => (
                      <input
                        aria-label={`Select ${r.name}`}
                        type="checkbox"
                        checked={allFiltered || selected.includes(r.id)}
                        onChange={() => {
                          setAllFiltered(false);
                          choose(r.id);
                        }}
                      />
                    ),
                  ],
                  [
                    "Intern",
                    (r) => (
                      <div>
                        <b>{r.name}</b>
                        <small>
                          {r.intern_id} · {r.email}
                        </small>
                      </div>
                    ),
                  ],
                  ["Department", (r) => r.department || "—"],
                  [
                    "College / Degree",
                    (r) => (
                      <div>
                        {r.college || "—"}
                        <small>{r.degree}</small>
                      </div>
                    ),
                  ],
                  ["Skills", (r) => r.skills.join(", ")],
                  [
                    "Batches",
                    (r) =>
                      r.batches.map((b: Row) => b.code).join(", ") ||
                      "Unallocated",
                  ],
                  ["Status", (r) => <Status value={r.status} />],
                  ["Score", (r) => r.score ?? "—"],
                  [
                    "Actions",
                    (r) => (
                      <div className="im-actions">
                        <Link to={`/hrms/employees/${r.id}`}>HRMS Profile</Link>
                        <button
                          onClick={async () => {
                            try {
                              setHistory(
                                (await api.get(root + `/memberships/${r.id}`))
                                  .data,
                              );
                            } catch {
                              toast({ title: "History unavailable" });
                            }
                          }}
                        >
                          History
                        </button>
                      </div>
                    ),
                  ],
                ]}
              />
              <Pagination
                total={interns?.total || 0}
                page={current}
                setPage={setCurrent}
              />
            </Panel>
          ) : (
            <div className="im-main-aside">
              <Panel
                title="Manage Batches"
                action={
                  <Button onClick={newBatch} size="sm">
                    Create Batch
                  </Button>
                }
              >
                <BatchTable
                  rows={batchRows}
                  edit={setBatchDialog}
                  membership={setMembershipDialog}
                  save={save}
                />
                <Pagination
                  total={batches?.total || 0}
                  page={current}
                  setPage={setCurrent}
                />
              </Panel>
              <Panel title="Quick Batch Actions">
                {[
                  [
                    "Create a new batch",
                    "Set specialization, capacity, dates and mentor",
                    newBatch,
                  ],
                  [
                    "Bulk allocate interns",
                    "Filter existing HRMS identities and add memberships",
                    () => setTab("Participant Directory"),
                  ],
                  [
                    "Transfer & rebalance",
                    "Move members without losing PMS records",
                    () => setMembershipDialog({ action: "transfer" }),
                  ],
                  [
                    "Review registrations",
                    "Approve applicants in the existing HRMS workflow",
                    () => setTab("Onboarding"),
                  ],
                ].map(([title, note, action], i) => (
                  <button
                    className="im-quick"
                    key={String(title)}
                    onClick={action as () => void}
                  >
                    <span>{i + 1}</span>
                    <div>
                      <b>{String(title)}</b>
                      <small>{String(note)}</small>
                    </div>
                  </button>
                ))}
              </Panel>
            </div>
          )}
        </>
      )}
      {page === "tasks" && (
        <>
          <div className="im-metrics five">
            <Metric
              label="PMS Tasks in Selected Project"
              value={templates?.total || 0}
              icon={ClipboardList}
            />
            <Metric
              label="Distribution Jobs"
              value={jobs?.total || 0}
              icon={Layers}
            />
            <Metric
              label="PMS-owned Execution"
              value="One History"
              icon={ShieldCheck}
            />
            <Metric
              label="Displayed Recipients"
              value={(jobs?.items || []).reduce(
                (n: number, j: Row) => n + j.recipients,
                0,
              )}
              icon={Users}
            />
            <Metric
              label="Legacy Histories to Import"
              value={legacy?.pending || 0}
              icon={RefreshCw}
            />
          </div>
          <div className="im-assignment-layout">
            <Panel title="Create & Distribute PMS Task">
              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  try {
                    const result = await api.post(
                      root + "/distributions/preview",
                      assignmentPayload(),
                    );
                    setPreview(result.data);
                  } catch (e: any) {
                    toast({
                      title: "Preview unavailable",
                      description:
                        e.response?.data?.detail ||
                        "Check project, recipients and reviewer permissions.",
                      variant: "destructive",
                    });
                  }
                }}
              >
                <Field label="1. PMS project">
                  <Select
                    required
                    value={assignment.project_id}
                    options={(options?.projects || []).filter(
                      (p: Row) => p.can_assign,
                    )}
                    onChange={(v) => updateAssignment("project_id", v)}
                    placeholder="Choose an authorized PMS project"
                  />
                </Field>
                <Field label="2. Existing PMS task or template">
                  <Select
                    value={assignment.task_id}
                    options={templates?.items || []}
                    onChange={(v) => updateAssignment("task_id", v)}
                    placeholder="Create a new PMS task"
                  />
                </Field>
                {!assignment.task_id && (
                  <>
                    <Field label="Task Title">
                      <Input
                        required
                        maxLength={220}
                        value={assignment.title}
                        onChange={(e) =>
                          updateAssignment("title", e.target.value)
                        }
                      />
                    </Field>
                    <Field label="Description">
                      <RichTextField
                        required
                        rows={3}
                        value={assignment.description}
                        onChange={(e) =>
                          updateAssignment("description", e.target.value)
                        }
                      />
                    </Field>
                    <div className="im-form-grid">
                      <Field label="Category">
                        <Input
                          value={assignment.category}
                          onChange={(e) =>
                            updateAssignment("category", e.target.value)
                          }
                        />
                      </Field>
                      <Field label="Instructions">
                        <Input
                          value={assignment.instructions}
                          onChange={(e) =>
                            updateAssignment("instructions", e.target.value)
                          }
                        />
                      </Field>
                      <Field label="Expected Deliverables">
                        <Input
                          value={assignment.deliverables}
                          onChange={(e) =>
                            updateAssignment("deliverables", e.target.value)
                          }
                        />
                      </Field>
                      <Field label="Review Instructions">
                        <Input
                          value={assignment.review_instructions}
                          onChange={(e) =>
                            updateAssignment(
                              "review_instructions",
                              e.target.value,
                            )
                          }
                        />
                      </Field>
                    </div>
                  </>
                )}
                <Field label="3. Assignment Scope">
                  <div className="im-scope-options">
                    {[
                      ["interns", "Individual / Selected Interns"],
                      ["batches", "One / Multiple Batches"],
                      ["department", "Department"],
                      ["all", "All Eligible in Authorized Program"],
                    ].map(([value, label]) => (
                      <label
                        key={value}
                        className={
                          assignment.target_type === value ? "selected" : ""
                        }
                      >
                        <input
                          type="radio"
                          name="target"
                          value={value}
                          checked={assignment.target_type === value}
                          onChange={() =>
                            updateAssignment("target_type", value)
                          }
                        />
                        {label}
                      </label>
                    ))}
                  </div>
                </Field>
                {assignment.target_type === "batches" ? (
                  <div className="im-recipient-list">
                    {batchRows.map((b: Row) => (
                      <label key={b.id}>
                        <input
                          type="checkbox"
                          checked={assignment.batch_ids.includes(b.id)}
                          onChange={() =>
                            updateAssignment(
                              "batch_ids",
                              assignment.batch_ids.includes(b.id)
                                ? assignment.batch_ids.filter(
                                    (id: number) => id !== b.id,
                                  )
                                : [...assignment.batch_ids, b.id],
                            )
                          }
                        />
                        <div>
                          <b>
                            {b.code} · {b.name}
                          </b>
                          <small>
                            {b.members} interns · {b.status}
                          </small>
                        </div>
                        <Status value={b.status} />
                      </label>
                    ))}
                  </div>
                ) : assignment.target_type === "interns" ? (
                  <div className="im-recipient-list">
                    {people.map((p: Row) => (
                      <label key={p.id}>
                        <input
                          type="checkbox"
                          checked={selected.includes(p.id)}
                          onChange={() => {
                            choose(p.id);
                            setPreview(null);
                            key.current = crypto.randomUUID();
                          }}
                        />
                        <div>
                          <b>{p.name}</b>
                          <small>
                            {p.intern_id} · {p.department}
                          </small>
                        </div>
                      </label>
                    ))}
                    <Pagination
                      total={interns?.total || 0}
                      page={current}
                      setPage={setCurrent}
                    />
                  </div>
                ) : (
                  <div className="im-form-grid">
                    <Field label="Department">
                      <Select
                        value={assignment.department_id}
                        options={options?.departments || []}
                        onChange={(v) => updateAssignment("department_id", v)}
                      />
                    </Field>
                    <Field label="Program (optional)">
                      <Input
                        value={assignment.program}
                        onChange={(e) =>
                          updateAssignment("program", e.target.value)
                        }
                      />
                    </Field>
                  </div>
                )}
                <div className="im-form-grid">
                  <Field label="Deadline">
                    <Input
                      type="date"
                      required
                      value={assignment.due_date}
                      onChange={(e) =>
                        updateAssignment("due_date", e.target.value)
                      }
                    />
                  </Field>
                  <Field label="Start Date">
                    <Input
                      type="date"
                      value={assignment.start_date}
                      onChange={(e) =>
                        updateAssignment("start_date", e.target.value)
                      }
                    />
                  </Field>
                  <Field label="Priority">
                    <select
                      value={assignment.priority}
                      onChange={(e) =>
                        updateAssignment("priority", e.target.value)
                      }
                    >
                      {["Low", "Medium", "High", "Critical"].map((v) => (
                        <option key={v}>{v}</option>
                      ))}
                    </select>
                  </Field>
                  <Field label="PMS-authorized Reviewer">
                    <Select
                      required
                      value={assignment.reviewer_user_id}
                      options={staff}
                      onChange={(v) => updateAssignment("reviewer_user_id", v)}
                    />
                  </Field>
                  <Field label="Maximum Score">
                    <Input
                      type="number"
                      required
                      min={1}
                      max={1000}
                      value={assignment.maximum_score}
                      onChange={(e) =>
                        updateAssignment("maximum_score", e.target.value)
                      }
                    />
                  </Field>
                  <Field label="Estimated Effort (hours)">
                    <Input
                      type="number"
                      min={0}
                      step="0.5"
                      value={assignment.estimated_hours}
                      onChange={(e) =>
                        updateAssignment("estimated_hours", e.target.value)
                      }
                    />
                  </Field>
                  <Field label="Repeat Schedule">
                    <select
                      value={assignment.recurrence}
                      onChange={(e) =>
                        updateAssignment("recurrence", e.target.value)
                      }
                    >
                      <option value="">One assignment</option>
                      <option value="daily">Daily</option>
                      <option value="weekly">Weekly</option><option value="custom">Custom interval</option>
                    </select>
                  </Field>
                  {assignment.recurrence==="custom"&&<Field label="Repeat every (days)"><Input type="number" min={1} max={365} value={assignment.recurrence_interval||1} onChange={e=>updateAssignment("recurrence_interval",Number(e.target.value))}/></Field>}
                  {assignment.recurrence && (
                    <Field label="Repeat Until">
                      <Input
                        required
                        type="date"
                        value={assignment.recurrence_until}
                        onChange={(e) =>
                          updateAssignment("recurrence_until", e.target.value)
                        }
                      />
                    </Field>
                  )}
                </div>
                <Button type="submit" variant="outline">
                  <Search size={15} />
                  Preview Assignment
                </Button>
              </form>
            </Panel>
            <div className="im-stack">
              <Panel title="Assignment Preview">
                <div className="im-preview">
                  <small>Eligible, deduplicated recipients</small>
                  <strong>
                    {preview?.total ?? "—"} <span>interns</span>
                  </strong>
                  <p>
                    Each recipient has independent execution, evidence versions
                    and PMS reviewer decisions under one shared task.
                  </p>
                </div>
                {preview && (
                  <>
                    <div className="im-recipient-list">
                      {preview.sample.map((p: Row) => (
                        <div className="im-exclude" key={p.id}>
                          <span>
                            {p.name}
                            <small>{p.intern_id}</small>
                          </span>
                          <button
                            onClick={() =>
                              updateAssignment("exclude_ids", [
                                ...assignment.exclude_ids,
                                p.id,
                              ])
                            }
                          >
                            Exclude
                          </button>
                        </div>
                      ))}
                    </div>
                    {preview.total > 20 && (
                      <p className="im-muted">
                        Showing the first 20 of {preview.total} recipients.
                      </p>
                    )}
                    <Button
                      disabled={busy}
                      className="w-full"
                      onClick={() =>
                        save(
                          "/distributions",
                          assignmentPayload(),
                          "post",
                          () => {
                            setPreview(null);
                            key.current = crypto.randomUUID();
                          },
                        )
                      }
                    >
                      <Send size={15} />
                      Publish PMS Assignment
                    </Button>
                  </>
                )}
                <div className="im-callout">
                  <b>PMS permissions stay authoritative</b>
                  <p>
                    Creating assignments requires PMS task-management access.
                    Reviewers must already have PMS approval permission. Interns
                    receive access only to their own work.
                  </p>
                </div>
                {assignment.task_id && (
                  <Link
                    className="im-text-link"
                    to={`/pms/tasks/${assignment.task_id}`}
                  >
                    Manage supporting files and dependencies in PMS{" "}
                    <ExternalLink size={14} />
                  </Link>
                )}
              </Panel>
              {!!legacy?.pending && (
                <Panel title="Preserve Existing Hub History">
                  <p>
                    {legacy.pending} historical tasks await conversion. Their
                    old records remain intact and read-only.
                  </p>
                  <p className="im-muted">
                    Choose a PMS project and reviewer above, then import up to
                    100 histories at a time.
                  </p>
                  <Button
                    disabled={
                      busy ||
                      !assignment.project_id ||
                      !assignment.reviewer_user_id
                    }
                    variant="outline"
                    onClick={() =>
                      save(
                        "/legacy/import",
                        {
                          project_id: Number(assignment.project_id),
                          reviewer_user_id: Number(assignment.reviewer_user_id),
                        },
                        "post",
                        () =>
                          toast({
                            title: "Legacy import processed",
                            description:
                              "Check remaining histories and any evidence reconciliation errors.",
                          }),
                      )
                    }
                  >
                    Import History into PMS
                  </Button>
                </Panel>
              )}
            </div>
          </div>
          <Panel title="PMS Task Distribution Jobs">
              <p className="im-callout">Execution totals belong to the shared PMS task across all its assignees. Recipient and published counts belong to each distribution request.</p>
            <Table
              rows={jobs?.items || []}
              columns={[
                [
                  "Task",
                  (r) => (
                    <Link to={`/pms/tasks/${r.task_id}`}>
                      {r.title}
                      <small>PMS task #{r.task_id}</small>
                    </Link>
                  ),
                ],
                ["Recipients", (r) => r.recipients],
                ["Published", (r) => r.cursor],
                ["Task Started", (r) => r.started],
                ["Task Submitted", (r) => r.submitted],
                ["Task Approved", (r) => r.approved],
                ["Deadline", (r) => date(r.due_date)],
                ["Delivery", (r) => <Status value={r.status} />],
                [
                  "Actions",
                  (r) => (
                    <div>
                      {r.error && <small className="im-error">{r.error}</small>}
                      {r.status !== "Completed" && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busy}
                          onClick={() => save(`/distributions/${r.id}/retry`)}
                        >
                          Resume / Retry
                        </Button>
                      )}
                      <Link
                        className="im-text-link"
                        to={`/pms/tasks/${r.task_id}`}
                      >
                        Open in PMS
                      </Link>
                    </div>
                  ),
                ],
              ]}
            />
            <Pagination
              total={jobs?.total || 0}
              page={current}
              size={30}
              setPage={setCurrent}
            />
          </Panel>
        </>
      )}
      {page === "tasks" && !!schedules?.length && (
        <Panel title="Recurring PMS Assignment Schedules">
          <Table
            rows={schedules}
            columns={[
              ["Schedule", (r) => `PMS task #${r.task_id}`],
              ["Frequency", (r) => r.frequency],
              ["Recipients", (r) => r.recipients],
              ["Next Due", (r) => date(r.next_run)],
              ["End", (r) => date(r.until)],
              [
                "State",
                (r) => (
                  <Status
                    value={
                      r.last_error
                        ? "Retry Required"
                        : r.active
                          ? "Active"
                          : "Paused"
                    }
                  />
                ),
              ],
              ["Last Issue", (r) => r.last_error || "—"],
              [
                "Action",
                (r) => (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      save(`/schedules/${r.id}/state`, { active: !r.active })
                    }
                  >
                    {r.active ? "Pause" : "Resume"}
                  </Button>
                ),
              ],
            ]}
          />
        </Panel>
      )}
      {page === "reviews" && (
        <>
          <div className="im-metrics five">
            <Metric
              label="Reports on This Page"
              value={reports?.items?.length || 0}
              icon={FileText}
            />
            <Metric
              label="Matching Reports / Exceptions"
              value={reports?.total || 0}
              icon={Clock}
            />
            <Metric
              label="Matching PMS Submissions"
              value={reviews?.total ?? "—"}
              icon={ClipboardList}
            />
            <Metric label="Evidence Source" value="PMS" icon={ShieldCheck} />
            <Metric label="Review Source" value="PMS" icon={CheckCircle2} />
          </div>
          <Tabs
            values={[
              "Daily Reports",
              "Task Submissions",
              "Pending Reviews",
              "Revision Requests",
              "Exceptions",
            ]}
            current={tab || "Daily Reports"}
            onChange={(v) => {
              setTab(v);
              setCurrent(1);
            }}
          />
          <Panel
            title="Review Queue"
            action={<Link to="/pms/reviews">Open PMS Review Queue →</Link>}
          >
            {[
              "Task Submissions",
              "Pending Reviews",
              "Revision Requests",
            ].includes(tab) ? (
              <>
                <Table
                  rows={reviews?.items || []}
                  columns={[
                    ["Intern", (r) => r.intern],
                    [
                      "PMS Task",
                      (r) => (
                        <Link to={`/pms/tasks/${r.task_id}`}>
                          {r.task}
                          <small>Version {r.version}</small>
                        </Link>
                      ),
                    ],
                    [
                      "Submitted",
                      (r) => new Date(r.created_at).toLocaleString(),
                    ],
                    [
                      "Evidence",
                      (r) =>
                        `${r.files.length} files · ${r.links.length} links`,
                    ],
                    ["Score", (r) => r.score ?? "—"],
                    ["Status", (r) => <Status value={r.status} />],
                    [
                      "Review",
                      (r) => (
                        <button onClick={() => setActiveReview(r)}>
                          Inspect →
                        </button>
                      ),
                    ],
                  ]}
                />
                <Pagination
                  total={reviews?.total || 0}
                  page={current}
                  setPage={setCurrent}
                />
              </>
            ) : (
              <>
                <Table
                  rows={reports?.items || []}
                  columns={[
                    ["Intern", (r) => r.intern],
                    ["Date", (r) => date(r.report_date)],
                    [
                      "Reported Time",
                      (r) =>
                        r.minutes != null
                          ? `${r.minutes} min (self-reported)`
                          : "—",
                    ],
                    [
                      "Work / Blocker",
                      (r) => (
                        <div>
                          {r.work || "No report submitted"}
                          <small>{r.blockers}</small>
                        </div>
                      ),
                    ],
                    [
                      "Review",
                      (r) => <Status value={r.review?.decision || r.status} />,
                    ],
                    [
                      "Action",
                      (r) =>
                        r.id ? (
                          <button
                            onClick={() => {
                              setActiveReport(r);
                              setReportNote("");
                            }}
                          >
                            Open →
                          </button>
                        ) : (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              save("/announcements", {
                                employee_ids: [r.employee_id],
                                title: "Daily report reminder",
                                message:
                                  "Please submit your daily report or contact your manager if you need support.",
                              })
                            }
                          >
                            Send Reminder
                          </Button>
                        ),
                    ],
                  ]}
                />
                <Pagination
                  total={reports?.total || 0}
                  page={current}
                  setPage={setCurrent}
                />
              </>
            )}
          </Panel>
          <div className="im-callout">
            <b>Reporting exceptions respect approved leave</b>
            <p>
              Missing-report checks exclude weekends and approved leave.
              Reported hours are self-declared; browser activity is never
              treated as verified work.
            </p>
          </div>
        </>
      )}
      {page === "performance" && (
        <>
          <div className="im-metrics five">
            <Metric
              label="Average PMS Review"
              value={d.average_score == null ? "—" : `${d.average_score}/100`}
              icon={Star}
            />
            <Metric
              label="Task Completion"
              value={
                d.assigned_tasks
                  ? `${Math.round((d.completed_tasks * 100) / d.assigned_tasks)}%`
                  : "0%"
              }
              icon={CheckCircle2}
            />
            <Metric
              label="Reports Today"
              value={d.reports_today}
              icon={FileText}
            />
            <Metric
              label="Eligible on This Page"
              value={people.filter((p: Row) => p.eligible).length}
              icon={Target}
            />
            <Metric
              label="Approved Completions"
              value={d.completions}
              icon={GraduationCap}
            />
          </div>
          <Tabs
            values={[
              "Overview",
              "Individual Performance",
              "Batch Analytics",
              "Completion",
              "Certificates",
            ]}
            current={tab || "Overview"}
            onChange={(v) => {
              setTab(v);
              setCurrent(1);
            }}
          />
          {(!tab || tab === "Overview" || tab === "Batch Analytics") && (
            <div className="im-main-aside">
              <Panel title="Batch Performance Comparison">
                <div className="im-bars big">
                  {(batchAnalytics || []).map((b: Row) => (
                    <div key={b.id}>
                      <span>{b.name}</span>
                      <progress max={100} value={b.score || 0} />
                      <b>{b.score ?? "—"}</b>
                    </div>
                  ))}
                </div>
                <p className="im-muted">
                  Average scores come from the latest PMS work evaluations.
                  Completion rates use per-assignee PMS status.
                </p>
              </Panel>
              <Panel title="Completion Requirements">
                <p>
                  Requirements and score weights are configured per batch.
                  Manager approval is always required.
                </p>
                <div className="im-callout">
                  {people.filter((p: Row) => p.eligible).length} of the{" "}
                  {people.length} displayed interns currently satisfy their
                  server-side eligibility checks.
                </div>
                <Button onClick={() => setTab("Completion")}>
                  Review Completion Queue
                </Button>
              </Panel>
            </div>
          )}
          {tab === "Certificates" ? (
            <Panel title="Manager-approved Certificates">
              <Table
                rows={completions?.items || []}
                columns={[
                  ["Employee", (r) => r.snapshot.name],
                  ["Batch", (r) => r.batch_id],
                  ["Decision", (r) => <Status value={r.decision} />],
                  ["Verification ID", (r) => r.verification_id || "—"],
                  [
                    "Action",
                    (r) =>
                      r.certificate_id ? (
                        <Status value="Issued" />
                      ) : (
                        <Button
                          size="sm"
                          disabled={busy || r.decision !== "Approved"}
                          onClick={() =>
                            save(`/completions/${r.id}/certificate`)
                          }
                        >
                          Issue HRMS Certificate
                        </Button>
                      ),
                  ],
                ]}
              />
              <Pagination
                total={completions?.total || 0}
                page={current}
                setPage={setCurrent}
              />
            </Panel>
          ) : (
            <Panel
              title={
                tab === "Completion"
                  ? "Intern Evaluation & Completion Queue"
                  : "Individual Performance"
              }
            >
              <Table
                rows={people}
                columns={[
                  [
                    "Intern / Batch",
                    (r) => (
                      <div>
                        <b>{r.name}</b>
                        <small>
                          {r.batches.map((b: Row) => b.code).join(", ") ||
                            "Unallocated"}
                        </small>
                      </div>
                    ),
                  ],
                  [
                    "PMS Quality",
                    (r) =>
                      r.parts.quality == null
                        ? "—"
                        : `${Math.round(r.parts.quality)}/100`,
                  ],
                  [
                    "On-time",
                    (r) =>
                      r.parts.timeliness == null
                        ? "—"
                        : `${r.parts.timeliness}%`,
                  ],
                  [
                    "Reporting",
                    (r) =>
                      r.parts.reports == null ? "—" : `${r.parts.reports}%`,
                  ],
                  ["Tasks", (r) => `${r.accepted}/${r.assigned}`],
                  ["Overall", (r) => <b>{r.score ?? "—"}</b>],
                  [
                    "Risk / Eligibility",
                    (r) => (
                      <div>
                        <Status
                          value={r.eligible ? "Eligible" : "Needs Review"}
                        />
                        <small>{r.risks.join("; ")}</small>
                      </div>
                    ),
                  ],
                  [
                    "Decision",
                    (r) => (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={!r.batches.length}
                        onClick={() => {
                          setCompletion({ ...r, batch_id: Number(filter.batch_id) || r.batches[0]?.id });
                          setCompletionNote("");
                        }}
                      >
                        Review →
                      </Button>
                    ),
                  ],
                ]}
              />
              <Pagination
                total={interns?.total || 0}
                page={current}
                setPage={setCurrent}
              />
            </Panel>
          )}
        </>
      )}
      <Dialog
        open={!!batchDialog}
        onOpenChange={(v) => !v && setBatchDialog(null)}
      >
        <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {batchDialog?.id ? "Manage Batch" : "Create Batch"}
            </DialogTitle>
          </DialogHeader>
          {batchDialog && (
            <form
              className="im-form-grid"
              onSubmit={(e) => {
                e.preventDefault();
                const {
                  id,
                  status,
                  organization_id,
                  members,
                  mentor,
                  manager,
                  created_at,
                  ...body
                } = batchDialog;
                save(
                  id ? `/batches/${id}` : "/batches",
                  body,
                  id ? "put" : "post",
                  () => setBatchDialog(null),
                );
              }}
            >
              <Field label="Batch Type"><select value={batchDialog.batch_type||"Intern"} onChange={e=>setBatchDialog({...batchDialog,batch_type:e.target.value})}>{["Intern","Employee","Training","Mixed"].map(t=><option key={t}>{t}</option>)}</select></Field>
              {[
                ["name", "Batch Name"],
                ["code", "Unique Batch Code"],
                ["program", "Program"],
                ["specialization", "Specialization"],
                ["description", "Description"],
              ].map(([k, label]) => (
                <Field key={k} label={label}>
                  <Input
                    required={k === "name" || k === "code"}
                    value={batchDialog[k]}
                    onChange={(e) =>
                      setBatchDialog({ ...batchDialog, [k]: e.target.value })
                    }
                  />
                </Field>
              ))}
              {[
                ["department_id", "Department", options?.departments],
                ["manager_user_id", "Manager", staff],
                ["mentor_user_id", "Primary Mentor", staff],
                [
                  "project_id",
                  "PMS Project",
                  (options?.projects || []).filter((p: Row) => p.can_assign),
                ],
              ].map(([k, label, choices]) => (
                <Field key={String(k)} label={String(label)}>
                  <Select
                    required
                    value={batchDialog[String(k)]}
                    options={(choices || []) as Row[]}
                    onChange={(v) =>
                      setBatchDialog({ ...batchDialog, [String(k)]: Number(v) })
                    }
                  />
                </Field>
              ))}
              <Field label="Additional Mentors">
                <select
                  multiple
                  value={(batchDialog.additional_mentors || []).map(String)}
                  onChange={(e) =>
                    setBatchDialog({
                      ...batchDialog,
                      additional_mentors: Array.from(
                        e.target.selectedOptions,
                      ).map((o) => Number(o.value)),
                    })
                  }
                >
                  {staff.map((u: Row) => (
                    <option key={u.id} value={u.id}>
                      {u.name}
                    </option>
                  ))}
                </select>
              </Field>
              {[
                ["start_date", "Start Date", "date"],
                ["end_date", "End Date", "date"],
                ["capacity", "Capacity", "number"],
                ["expected_hours", "Expected Hours / Day", "number"],
              ].map(([k, label, type]) => (
                <Field key={k} label={label}>
                  <Input
                    type={type}
                    required
                    value={batchDialog[k]}
                    onChange={(e) =>
                      setBatchDialog({
                        ...batchDialog,
                        [k]:
                          type === "number"
                            ? Number(e.target.value)
                            : e.target.value,
                      })
                    }
                  />
                </Field>
              ))}
              <Field label="Reporting Frequency">
                <select
                  value={batchDialog.reporting_frequency}
                  onChange={(e) =>
                    setBatchDialog({
                      ...batchDialog,
                      reporting_frequency: e.target.value,
                    })
                  }
                >
                  <option>Daily</option>
                  <option>Weekly</option>
                </select>
              </Field>
              <div className="im-span-two">
                <h3>Performance Weights (must sum to 100)</h3>
                <div className="im-form-grid">
                  {Object.entries(batchDialog.policy?.weights || {}).map(
                    ([k, v]) => (
                      <Field label={k} key={k}>
                        <Input
                          type="number"
                          min={0}
                          max={100}
                          value={String(v)}
                          onChange={(e) =>
                            setBatchDialog({
                              ...batchDialog,
                              policy: {
                                ...batchDialog.policy,
                                weights: {
                                  ...batchDialog.policy.weights,
                                  [k]: Number(e.target.value),
                                },
                              },
                            })
                          }
                        />
                      </Field>
                    ),
                  )}
                </div>
                <h3>Completion Requirements</h3>
                <div className="im-form-grid">
                  {[
                    ["minimum_days", "Minimum Days"],
                    ["minimum_tasks", "Minimum Tasks"],
                    ["minimum_reports_percent", "Required Report %"],
                    ["minimum_attendance_percent", "Required Attendance %"],
                  ].map(([k, label]) => (
                    <Field label={label} key={k}>
                      <Input
                        type="number"
                        min={0}
                        value={batchDialog.policy?.completion?.[k] ?? 0}
                        onChange={(e) =>
                          setBatchDialog({
                            ...batchDialog,
                            policy: {
                              ...batchDialog.policy,
                              completion: {
                                ...batchDialog.policy.completion,
                                [k]: Number(e.target.value),
                              },
                            },
                          })
                        }
                      />
                    </Field>
                  ))}
                </div>
              </div>
              <label className="im-check im-span-two">
                <input
                  type="checkbox"
                  checked={!!batchDialog?.policy.completion.training_required}
                  onChange={(e) =>
                    setBatchDialog({
                      ...batchDialog,
                      policy: {
                        ...batchDialog!.policy,
                        completion: {
                          ...batchDialog!.policy.completion,
                          training_required: e.target.checked,
                        },
                      },
                    })
                  }
                />
                Require passing enrolled learning assessments (70% minimum)
              </label>
              <label className="im-check im-span-two">
                <input
                  type="checkbox"
                  checked={
                    !!batchDialog?.policy.completion.final_project_required
                  }
                  onChange={(e) =>
                    setBatchDialog({
                      ...batchDialog,
                      policy: {
                        ...batchDialog!.policy,
                        completion: {
                          ...batchDialog!.policy.completion,
                          final_project_required: e.target.checked,
                        },
                      },
                    })
                  }
                />
                Require PMS-approved task in the “Final Project” category
              </label>
              <Button disabled={busy}>Save Batch</Button>
            </form>
          )}
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!membershipDialog}
        onOpenChange={(v) => !v && setMembershipDialog(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Batch Membership</DialogTitle>
          </DialogHeader>
          <form
            className="im-stack"
            onSubmit={(e) => {
              e.preventDefault();
              save(
                `/batches/${memberForm.batch_id || memberForm.id}/members`,
                {
                  action: memberForm.action || "add",
                  employee_ids: selected,
                  select_filter: allFiltered ? params : null,
                  target_batch_id: memberForm.target_batch_id || null,
                  reason: memberForm.reason || "",
                },
                "post",
                () => setMembershipDialog(null),
              );
            }}
          >
            <p>
              {allFiltered
                ? `All ${interns?.total || 0} authorized filtered interns`
                : `${selected.length} selected interns`}
              . Select recipients in the Participant Directory tab.
            </p>
            <Field label="Source / Target Batch">
              <Select
                required
                value={memberForm?.batch_id || memberForm?.id}
                options={options?.batches || []}
                onChange={(v) =>
                  setMembershipDialog({ ...memberForm, batch_id: Number(v) })
                }
              />
            </Field>
            <Field label="Action">
              <select
                value={memberForm?.action || "add"}
                onChange={(e) =>
                  setMembershipDialog({ ...memberForm, action: e.target.value })
                }
              >
                {["add", "remove", "transfer", "deactivate", "reactivate"].map(
                  (v) => (
                    <option key={v}>{v}</option>
                  ),
                )}
              </select>
            </Field>
            {memberForm?.action === "transfer" && (
              <Field label="Transfer To">
                <Select
                  required
                  value={memberForm?.target_batch_id}
                  options={options?.batches || []}
                  onChange={(v) =>
                    setMembershipDialog({
                      ...memberForm,
                      target_batch_id: Number(v),
                    })
                  }
                />
              </Field>
            )}
            <Field label="Reason / Transfer Note">
              <Input
                required={memberForm?.action === "transfer"}
                value={memberForm?.reason || ""}
                onChange={(e) =>
                  setMembershipDialog({ ...memberForm, reason: e.target.value })
                }
              />
            </Field>
            <Button disabled={busy || (!selected.length && !allFiltered)}>
              Apply Membership Change
            </Button>
          </form>
        </DialogContent>
      </Dialog>
      <Dialog
        open={history !== null}
        onOpenChange={(v) => !v && setHistory(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Membership History</DialogTitle>
          </DialogHeader>
          <Table
            rows={history || []}
            columns={[
              ["Batch", (r) => r.batch_id],
              ["Status", (r) => r.status],
              ["Joined", (r) => new Date(r.joined_at).toLocaleString()],
              [
                "Left",
                (r) => (r.left_at ? new Date(r.left_at).toLocaleString() : "—"),
              ],
              ["Reason", (r) => r.reason || "—"],
            ]}
          />
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!activeReview}
        onOpenChange={(v) => !v && setActiveReview(null)}
      >
        <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>PMS Submission Evidence & Review</DialogTitle>
          </DialogHeader>
          {activeReview && (
            <WorkReviewPanel
              taskId={activeReview.task_id}
              submissionId={activeReview.id}
            />
          )}
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!activeReport}
        onOpenChange={(v) => !v && setActiveReport(null)}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Daily Report · {activeReport?.intern}</DialogTitle>
          </DialogHeader>
          {activeReport && (
            <>
              <p className="text-sm">
                {date(activeReport.report_date)} · {activeReport.minutes}{" "}
                self-reported minutes
              </p>
              {[
                ["work", "Work Completed"],
                ["learning", "Learning"],
                ["blockers", "Blockers"],
                ["tomorrow", "Plan for Tomorrow"],
              ].map(([k, label]) => (
                <div key={k}>
                  <b className="text-sm">{label}</b>
                  <p className="whitespace-pre-wrap text-sm text-muted-foreground">
                    {activeReport[k] || "—"}
                  </p>
                </div>
              ))}
              <Field label="Review / Correction Note">
                <Input
                  value={reportNote}
                  onChange={(e) => setReportNote(e.target.value)}
                />
              </Field>
              <div className="im-actions">
                {["Reviewed", "Correction Requested"].map((v) => (
                  <Button
                    key={v}
                    variant={v === "Reviewed" ? "default" : "outline"}
                    disabled={busy || !reportNote.trim()}
                    onClick={() =>
                      save(
                        `/reports/${activeReport.id}/review`,
                        { decision: v, note: reportNote },
                        "post",
                        () => setActiveReport(null),
                      )
                    }
                  >
                    {v}
                  </Button>
                ))}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
      <Dialog open={noticeDialog} onOpenChange={setNoticeDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Send Program Announcement</DialogTitle>
          </DialogHeader>
          <p>
            {selected.length} explicitly selected intern recipients. Choose them
            in Batches & Interns.
          </p>
          <form
            className="im-stack"
            onSubmit={(e) => {
              e.preventDefault();
              save(
                "/announcements",
                { ...notice, employee_ids: selected },
                "post",
                () => setNoticeDialog(false),
              );
            }}
          >
            <Field label="Title">
              <Input
                required
                value={notice.title}
                onChange={(e) =>
                  setNotice({ ...notice, title: e.target.value })
                }
              />
            </Field>
            <Field label="Message">
              <RichTextField
                required
                value={notice.message}
                onChange={(e) =>
                  setNotice({ ...notice, message: e.target.value })
                }
              />
            </Field>
            <Button disabled={busy || !selected.length}>
              Send In-app Announcement
            </Button>
          </form>
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!completion}
        onOpenChange={(v) => !v && setCompletion(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Internship Completion · {completion?.name}
            </DialogTitle>
          </DialogHeader>
          {completion && (
            <>
              <Field label="Batch">
                <Select
                  required
                  value={completion.batch_id}
                  options={completion.batches}
                  onChange={async (v) => {
                    setCompletion({
                      ...completion,
                      batch_id: Number(v),
                      eligible: false,
                      eligibility_reasons: [
                        "Checking selected batch requirements…",
                      ],
                    });
                    try {
                      const r = await api.get(
                        root + `/interns/${completion.id}/performance`,
                        { params: { batch_id: Number(v) } },
                      );
                      setCompletion({ ...r.data, batch_id: Number(v) });
                    } catch {
                      setCompletion((c) => ({
                        ...c,
                        eligible: false,
                        eligibility_reasons: [
                          "Could not verify selected batch requirements.",
                        ],
                      }));
                    }
                  }}
                />
              </Field>
              <Status
                value={
                  completion.eligible ? "Eligible" : "Requirements Outstanding"
                }
              />
              {completion.eligibility_reasons.map((reason: string) => (
                <p className="im-error" key={reason}>
                  {reason}
                </p>
              ))}
              <p>
                Final eligibility is recomputed on the server. PMS work
                approvals cannot be overridden here.
              </p>
              <Field label="Manager Review Note">
                <Input
                  value={completionNote}
                  onChange={(e) => setCompletionNote(e.target.value)}
                />
              </Field>
              <div className="im-actions">
                {["Approved", "Improvements Requested", "Incomplete"].map(
                  (v) => (
                    <Button
                      key={v}
                      variant={v === "Approved" ? "default" : "outline"}
                      disabled={
                        busy ||
                        !completionNote.trim() ||
                        (v === "Approved" && !completion.eligible)
                      }
                      onClick={() =>
                        save(
                          "/completions",
                          {
                            batch_id: completion.batch_id,
                            employee_id: completion.id,
                            decision: v,
                            note: completionNote,
                          },
                          "post",
                          () => setCompletion(null),
                        )
                      }
                    >
                      {v}
                    </Button>
                  ),
                )}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
function Tabs({
  values,
  current,
  onChange,
}: {
  values: string[];
  current: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="im-tabs">
      {values.map((v) => (
        <button
          key={v}
          className={current === v ? "active" : ""}
          onClick={() => onChange(v)}
        >
          {v}
        </button>
      ))}
    </div>
  );
}
function BatchTable({
  rows,
  edit,
  membership,
  save,
}: {
  rows: Row[];
  edit: (r: Row) => void;
  membership: (r: Row) => void;
  save: (
    path: string,
    body?: any,
    method?: string,
    success?: () => void,
  ) => void;
}) {
  const next: Row = {
    Draft: ["Upcoming", "Archived"],
    Upcoming: ["Active", "Archived"],
    Active: ["Evaluation", "Archived"],
    Evaluation: ["Active", "Completed", "Archived"],
    Completed: ["Archived"],
    Archived: [],
  };
  return (
    <Table
      rows={rows}
      columns={[
        [
          "Batch / Track",
          (r) => (
            <div>
              <b>{r.code}</b>
              <small>
                {r.name} · {r.specialization}
              </small>
            </div>
          ),
        ],
        ["Intern Count", (r) => `${r.members} / ${r.capacity}`],
        ["Mentor", (r) => r.mentor || "Unassigned"],
        [
          "Duration",
          (r) => (
            <div>
              {date(r.start_date)}
              <small>to {date(r.end_date)}</small>
            </div>
          ),
        ],
        ["Status", (r) => <Status value={r.status} />],
        [
          "Actions",
          (r) => (
            <div className="im-actions">
              <button onClick={() => edit(r)}>Manage →</button>
              <button onClick={() => membership({ ...r, action: "add" })}>
                Members
              </button>
              <select
                aria-label={`Transition ${r.code}`}
                value=""
                onChange={(e) => {
                  if (e.target.value)
                    save(`/batches/${r.id}/transition`, {
                      status: e.target.value,
                    });
                }}
              >
                <option value="">Change Status</option>
                {(next[r.status] || []).map((v: string) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </div>
          ),
        ],
      ]}
    />
  );
}
