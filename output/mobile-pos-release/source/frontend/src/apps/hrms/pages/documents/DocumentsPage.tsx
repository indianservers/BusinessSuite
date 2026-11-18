import { useMobile } from "@/components/mobile/useMobile";
import { lazy, Suspense, useMemo, useState, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Users,
  Files,
  ShieldCheck,
  CalendarClock,
  CircleAlert,
  FileWarning,
  FolderOpen,
  Upload,
  Filter,
  X,
  Download,
  Eye,
  Send,
  Check,
  FileSpreadsheet,
  BookOpen,
  Layers,
  Search,
} from "lucide-react";
import { api, companyApi } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import SharedDataGrid from "@/shared/data-grid/SharedDataGrid";
import type { GridColumn, GridDataSource } from "@/shared/data-grid/types";
import { formatDate, assetUrl } from "@/lib/utils";
import DocumentUploadTools from "./DocumentUploadTools";
import "./document-management.css";
const PdfPreview = lazy(() => import("@/components/PdfPreview"));
const base = "/documents/certificates";
type Employee = {
  id: number;
  name: string;
  code: string;
  department: string;
  designation: string;
  email?: string;
  photo?: string;
};
type Certificate = {
  id: number;
  employee_id: number;
  employee: Employee;
  title: string;
  category: string;
  certificate_type: string;
  verification_status: string;
  certificate_number?: string;
  issue_date?: string;
  expiry_date?: string;
  uploaded_at?: string;
  verified_at?: string;
  verifier_name?: string;
  verification_notes?: string;
  original_filename?: string;
  remarks?: string;
  reminder_date?: string;
};
type Requirement = {
  id?: number;
  version?: number;
  title: string;
  certificate_type: string;
  department_id?: number | null;
  designation_id?: number | null;
  branch_id?: number | null;
  employment_type: string;
  employee_category: string;
  mandatory: boolean;
  verification_required: boolean;
  expiry_required: boolean;
  reminder_days: number;
  reminders_enabled: boolean;
  active: boolean;
};
type Insights = {
  employees: number;
  documents: number;
  verified: number;
  pending: number;
  expired: number;
  expiring: number;
  missing: number;
  missing_documents: number;
  required_documents: number;
  missing_employees: (Employee & { requirements: Requirement[] })[];
};
const blankRequirement: Requirement = {
  title: "",
  certificate_type: "",
  employment_type: "",
  employee_category: "",
  mandatory: true,
  verification_required: true,
  expiry_required: false,
  reminder_days: 30,
  reminders_enabled: false,
  active: true,
};
const statuses = [
  "Pending",
  "Verified",
  "Rejected",
  "Correction Required",
  "Expiring Soon",
  "Expired",
];
function status(c: Certificate) {
  return c.expiry_date && c.expiry_date < new Date().toLocaleDateString("en-CA")
    ? "Expired"
    : c.verification_status;
}
function Avatar({ employee }: { employee: Employee }) {
  return (
    <span className="dv-avatar">
      {employee.photo ? (
        <img src={assetUrl(employee.photo)} alt="" />
      ) : (
        employee.name
          .split(" ")
          .map((n) => n[0])
          .slice(0, 2)
          .join("")
      )}
    </span>
  );
}
export default function DocumentsPage() {
  const phone = useMobile(800);
  const qc = useQueryClient();
  const { user } = useAuthStore();
  const [params, setParams] = useSearchParams();
  const grant = user?.access?.grants.hrms;
  const canVerify =
    !!user?.is_superuser || !!grant?.permissions.includes("employee_update");
  const canExport =
    !!user?.is_superuser || !!grant?.permissions.includes("reports_view");
  const canConfigure =
    !!user?.is_superuser || !!grant?.permissions.includes("company_manage");
  const [tab, setTab] = useState(params.get("tab") || "Documents");
  const [filters, setFilters] = useState<Record<string, string>>({
    employee_id: params.get("employee_id") || "",
  });
  const [selected, setSelected] = useState<Employee | null>(null);
  const [missing, setMissing] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const [revision, setRevision] = useState(0);
  const [review, setReview] = useState<Certificate | null>(null);
  const [reviewStatus, setReviewStatus] = useState("Verified");
  const [reason, setReason] = useState("");
  const [verifier, setVerifier] = useState("");
  const [verifierCompany, setVerifierCompany] = useState("");
  const [verifierDesignation, setVerifierDesignation] = useState("");
  const [verifierContact, setVerifierContact] = useState("");
  const [file, setFile] = useState<Blob | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [edit, setEdit] = useState<Requirement | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const scope = JSON.stringify([
    user?.id,
    user?.access?.companyId,
    sessionStorage.getItem("suite-branch"),
  ]);
  const insights = useQuery<Insights>({
    queryKey: ["vault-insights", scope, revision],
    queryFn: async () =>
      (await api.get(base + "/insights", { recordCache: false })).data,
  });
  const activity = useQuery<{ items: Certificate[] }>({
    queryKey: ["vault-activity", scope, selected?.id, revision],
    enabled: !!selected,
    queryFn: async () =>
      (
        await api.get(base + "/library", {
          recordCache: false,
          params: { employee_id: selected?.id, per_page: 5 },
        })
      ).data,
  });
  const employeeInsights = useQuery<Insights>({
    queryKey: ["vault-employee", scope, selected?.id, revision],
    enabled: !!selected,
    queryFn: async () =>
      (
        await api.get(base + "/insights", {
          params: { employee_id: selected?.id },
          recordCache: false,
        })
      ).data,
  });
  const requirements = useQuery<Requirement[]>({
    queryKey: ["vault-requirements", scope, revision],
    queryFn: async () =>
      (await api.get(base + "/requirements", { recordCache: false })).data,
  });
  const departments = useQuery<{ id: number; name: string }[]>({
    queryKey: ["vault-departments", scope],
    queryFn: async () => (await companyApi.listDepartments()).data,
  });
  const branches = useQuery<{ id: number; name: string }[]>({
    queryKey: ["vault-branches", scope],
    queryFn: async () => (await companyApi.listBranches()).data,
  });
  const designations = useQuery<{ id: number; name: string }[]>({
    queryKey: ["vault-designations", scope],
    queryFn: async () => (await companyApi.listDesignations()).data,
  });
  const history = useQuery<
    {
      id: number;
      operation_type: string;
      original_filename: string;
      status: string;
      total_records: number;
      failure_count: number;
      requested_at: string;
    }[]
  >({
    queryKey: ["vault-imports", scope, revision],
    enabled: tab === "Bulk Import / Export",
    queryFn: async () =>
      (await api.get(base + "/import-export", { recordCache: false })).data,
  });
  const refresh = () => {
    setRevision((v) => v + 1);
    void qc.invalidateQueries({ queryKey: ["certificates"] });
  };
  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setNotice("");
    try {
      await action();
      refresh();
    } catch (e) {
      setNotice(
        (e as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail || "Unable to complete this action. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  const change = (key: string, value: string) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setMissing(false);
  };
  useEffect(
    () => () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    },
    [previewUrl],
  );
  const revisions = useQuery<
    {
      id: number;
      saved_at: string;
      title: string;
      verification_status: string;
      original_filename: string;
    }[]
  >({
    queryKey: ["vault-revisions", scope, review?.id, revision],
    enabled: !!review,
    queryFn: async () =>
      (await api.get(`${base}/${review?.id}/revisions`, { recordCache: false }))
        .data,
  });
  const source = useMemo<GridDataSource<Certificate>>(
    () => ({
      key: "vault:" + scope + JSON.stringify(filters) + tab + revision,
      load: async (query, signal) => {
        const { data } = await api.get(base + "/library", {
          signal,
          recordCache: false,
          params: {
            ...Object.fromEntries(
              Object.entries(filters).filter(([, v]) => v !== ""),
            ),
            verification_status:
              tab === "Verification Queue"
                ? "Pending"
                : filters.verification_status || undefined,
            q: query.search || filters.q,
            page: query.page,
            per_page: Math.min(query.pageSize || 100, 100),
            sort: query.sorting[0]?.id || "uploaded_at",
            descending: query.sorting[0]?.desc ?? true,
          },
        });
        return {
          rows: data.items,
          total: data.total,
          pageTotal: data.total,
          page: query.page,
          pageSize: Math.min(query.pageSize || 100, 100),
          permissions: { edit: canVerify, export: canExport },
        };
      },
      export: canExport
        ? async (request) => {
            const rows: Certificate[] = [];
            let page = 1,
              total = 0;
            do {
              const { data } = await api.get(base + "/metadata-export", {
                recordCache: false,
                params: {
                  ...Object.fromEntries(
                    Object.entries(filters).filter(([, v]) => v !== ""),
                  ),
                  q: request.query.search || filters.q,
                  verification_status:
                    tab === "Verification Queue"
                      ? "Pending"
                      : filters.verification_status || undefined,
                  per_page: 100,
                  page,
                },
              });
              total = data.total;
              rows.push(...data.items);
              page++;
            } while (rows.length < total);
            const exported =
              request.scope === "selected"
                ? rows.filter((r) => request.ids.includes(String(r.id)))
                : request.scope === "visible"
                  ? rows.slice(
                      (request.query.page - 1) * request.query.pageSize,
                      request.query.page * request.query.pageSize,
                    )
                  : rows;
            const cell = (value: unknown) => {
              let text = String(value ?? "");
              if (/^[=+@\-\t\r]/.test(text)) text = "'" + text;
              return '"' + text.replace(/"/g, '""') + '"';
            };
            const result = [
              [
                "Record ID",
                "Employee",
                "Employee code",
                "Title",
                "Category",
                "Certificate type",
                "Certificate number",
                "Issue date",
                "Expiry date",
                "Verification status",
              ],
              ...exported.map((r) => [
                r.id,
                r.employee.name,
                r.employee.code,
                r.title,
                r.category,
                r.certificate_type,
                r.certificate_number,
                r.issue_date,
                r.expiry_date,
                r.verification_status,
              ]),
            ]
              .map((row) => row.map(cell).join(","))
              .join("\r\n");
            await api.post(base + "/exports", null, {
              params: {
                total_records: exported.length,
                remarks: "Authorized vault metadata export",
              },
            });
            return new Blob([result], { type: "text/csv;charset=utf-8" });
          }
        : undefined,
    }),
    [filters, tab, revision, scope, canVerify, canExport],
  );
  async function open(row: Certificate) {
    setReview(row);
    setReviewStatus("Verified");
    setReason("");
    setFile(null);
    setVerifier("");
    setVerifierCompany("");
    setVerifierDesignation("");
    setVerifierContact("");
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl("");
    await run(async () => {
      const r = await api.get(`${base}/${row.id}/file`, {
        responseType: "blob",
        recordCache: false,
      });
      setFile(r.data);
      setPreviewUrl(URL.createObjectURL(r.data));
    });
  }
  async function download(row: Certificate) {
    await run(async () => {
      const r = await api.get(`${base}/${row.id}/file`, {
        responseType: "blob",
        recordCache: false,
      });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = row.original_filename || row.title;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  }
  async function remind(id: number) {
    await run(async () => {
      const { data } = await api.post(base + "/reminders", { employee_id: id });
      setNotice(
        data.duplicate
          ? "A reminder was already sent today."
          : "Document reminder sent.",
      );
    });
  }
  const columns = useMemo<GridColumn<Certificate>[]>(
    () =>
      (
        [
          {
            id: "employee",
            title: "Employee",
            width: 190,
            sortable: false,
            render: (r) => (
              <button
                className="dv-person"
                onClick={(e) => {
                  e.stopPropagation();
                  setSelected(r.employee);
                }}
              >
                <Avatar employee={r.employee} />
                <span>
                  <strong>{r.employee.name}</strong>
                  <small>
                    {r.employee.code} · {r.employee.department}
                  </small>
                </span>
              </button>
            ),
          },
          {
            id: "title",
            title: "Document / Certificate",
            width: 230,
            render: (r) => (
              <span className="dv-document-cell">
                <Files size={21} />
                <span>
                  <strong>{r.title}</strong>
                  <small>{r.original_filename || r.certificate_type}</small>
                </span>
              </span>
            ),
          },
          {
            id: "category",
            title: "Category",
            width: 125,
            render: (r) => <span className="dv-tag">{r.category}</span>,
          },
          {
            id: "uploaded_at",
            title: "Uploaded",
            type: "date",
            width: 115,
            render: (r) => formatDate(r.uploaded_at || null),
          },
          {
            id: "issue_date",
            title: "Issue date",
            type: "date",
            width: 110,
            render: (r) => formatDate(r.issue_date || null),
          },
          {
            id: "expiry_date",
            title: "Expiry date",
            type: "date",
            width: 110,
            render: (r) => formatDate(r.expiry_date || null),
          },
          {
            id: "verification_status",
            title: "Verification",
            width: 150,
            render: (r) => (
              <span
                className={
                  "dv-status dv-status-" +
                  status(r).toLowerCase().replace(/ /g, "-")
                }
              >
                {status(r)}
              </span>
            ),
          },
        ] satisfies GridColumn<Certificate>[]
      ).map((c) => ({ ...c, filterable: false, groupable: false })),
    [],
  );
  const filterPanel = (
    <aside className="dv-panel dv-filters">
      <header>
        <h2>
          <Filter size={17} />
          Filters
        </h2>
        <button
          onClick={() => {
            setFilters({});
            setMissing(false);
          }}
        >
          Clear all
        </button>
      </header>
      <label>
        Employee name / ID
        <Input
          value={filters.q || ""}
          onChange={(e) => change("q", e.target.value)}
          placeholder="Search name or employee ID"
        />
      </label>
      <label>
        Department
        <NativeSelect
          value={filters.department_id || ""}
          onChange={(e) => change("department_id", e.target.value)}
        >
          <option value="">All departments</option>
          {departments.data?.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </NativeSelect>
      </label>
      <label>
        Designation
        <NativeSelect
          value={filters.designation_id || ""}
          onChange={(e) => change("designation_id", e.target.value)}
        >
          <option value="">All designations</option>
          {designations.data?.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </NativeSelect>
      </label>
      <label>
        Branch
        <NativeSelect
          value={filters.branch_id || ""}
          onChange={(e) => change("branch_id", e.target.value)}
        >
          <option value="">All branches</option>
          {branches.data?.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </NativeSelect>
      </label>
      <label>
        Document category
        <NativeSelect
          value={filters.category || ""}
          onChange={(e) => change("category", e.target.value)}
        >
          <option value="">All categories</option>
          {[
            "Study",
            "Class Certificate",
            "Old Company",
            "Identity",
            "Training",
            "Professional",
            "Employment",
            "Contracts",
            "Compliance",
            "Other",
          ].map((c) => (
            <option key={c}>{c}</option>
          ))}
        </NativeSelect>
      </label>
      <label>
        Verification status
        <NativeSelect
          value={filters.verification_status || ""}
          onChange={(e) => change("verification_status", e.target.value)}
        >
          <option value="">All statuses</option>
          {statuses.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </NativeSelect>
      </label>
      {[
        ["upload_from", "Uploaded from"],
        ["upload_to", "Uploaded until"],
        ["expiry_from", "Expiring from"],
        ["expiry_to", "Expiring until"],
      ].map(([key, label]) => (
        <label key={key}>
          {label}
          <Input
            type="date"
            value={filters[key] || ""}
            onChange={(e) => change(key, e.target.value)}
          />
        </label>
      ))}
      <label>
        Requirement
        <NativeSelect
          value={filters.mandatory || ""}
          onChange={(e) => change("mandatory", e.target.value)}
        >
          <option value="">All documents</option>
          <option value="true">Mandatory</option>
          <option value="false">Optional</option>
        </NativeSelect>
      </label>
      <Button variant="outline" onClick={() => setMissing((v) => !v)}>
        Show missing certificates
      </Button>
    </aside>
  );
  const stats = insights.data;
  return (
    <div className="document-management dv-workspace">
      <header className="dm-hero">
        <span className="dm-hero-icon">
          <FolderOpen size={30} />
        </span>
        <div>
          <p className="dm-eyebrow">DOCUMENTS / EMPLOYEE DOCUMENT VAULT</p>
          <h1>Employee Document Vault</h1>
          <p>
            Collect, verify and track employee documents in one secure
            workspace.
          </p>
        </div>
        <Link className="dm-hero-link" to="/hrms/letters-certificates">
          Letters & Certificates Studio →
        </Link>
      </header>
      <div className="dv-kpis">
        {[
          { key: "employees", label: "Total Employees", icon: Users },
          { key: "documents", label: "Total Documents", icon: Files },
          {
            key: "verified",
            label: "Verified Documents",
            icon: ShieldCheck,
            status: "Verified",
          },
          {
            key: "expiring",
            label: "Expiring Soon",
            icon: CalendarClock,
            status: "Expiring Soon",
          },
          {
            key: "expired",
            label: "Expired Documents",
            icon: CircleAlert,
            status: "Expired",
          },
          { key: "missing", label: "Missing Mandatory", icon: FileWarning },
        ].map((k, i) => (
          <button
            key={k.key}
            className={"dv-kpi dv-kpi-" + i}
            onClick={() => {
              setTab("Documents");
              setFilters({ verification_status: k.status || "" });
              setMissing(k.key === "missing");
            }}
          >
            <span>
              <k.icon size={23} />
            </span>
            <div>
              <strong>
                {stats
                  ? (stats[k.key as keyof Insights] as number).toLocaleString()
                  : "—"}
              </strong>
              <p>{k.label}</p>
              <small>
                {i === 3
                  ? "Next 30 days"
                  : i === 5
                    ? "Employees with incomplete requirements"
                    : i === 2
                      ? "HR verification completed"
                      : "Current authorized scope"}
              </small>
            </div>
          </button>
        ))}
      </div>
      <nav className="dm-tabs" aria-label="Document vault sections">
        {[
          { label: "Documents", icon: Files },
          { label: "Upload Documents", icon: Upload },
          { label: "Verification Queue", icon: ShieldCheck },
          { label: "Bulk Import / Export", icon: FileSpreadsheet },
          { label: "Policies & Requirements", icon: BookOpen },
        ].map((t) => (
          <button
            key={t.label}
            aria-current={tab === t.label ? "page" : undefined}
            onClick={() => {
              setTab(t.label);
              setParams(
                (p) => {
                  p.set("tab", t.label);
                  return p;
                },
                { replace: true },
              );
            }}
          >
            <t.icon size={17} />
            {t.label}
            {t.label === "Verification Queue" && !!stats?.pending && (
              <span>{stats.pending}</span>
            )}
          </button>
        ))}
      </nav>
      {notice && (
        <p role="status" className="dm-notice">
          {notice}
        </p>
      )}
      {insights.isError && (
        <p role="alert" className="dm-notice">
          Document insights could not load.{" "}
          <Button onClick={() => void insights.refetch()}>Retry</Button>
        </p>
      )}
      {(tab === "Documents" || tab === "Verification Queue") && (
        <>
          <Button
            className="dv-mobile-filter"
            variant="outline"
            onClick={() => setFilterOpen(true)}
          >
            <Filter size={16} />
            Filters
          </Button>
          <div className="dv-layout">
            {filterPanel}
            <section className="dv-panel dv-library">
              <header>
                <div>
                  <h2>
                    <Layers size={20} />
                    {tab === "Verification Queue"
                      ? "Verification Queue"
                      : "Document Library"}
                  </h2>
                  <p>Private files · Live employee records</p>
                </div>
                <Button onClick={() => setTab("Upload Documents")}>
                  <Upload size={15} />
                  Upload document
                </Button>
              </header>
              {missing ? (
                <div className="dv-missing-list">
                  <h3>Employees missing mandatory documents</h3>
                  <p>
                    Requirements respect department, designation, branch and
                    employment conditions.
                  </p>
                  {stats?.missing_employees.map((e) => (
                    <article key={e.id}>
                      <button
                        className="dv-person"
                        onClick={() => setSelected(e)}
                      >
                        <Avatar employee={e} />
                        <span>
                          <strong>{e.name}</strong>
                          <small>
                            {e.code} · {e.department}
                          </small>
                        </span>
                      </button>
                      <p>{e.requirements.map((r) => r.title).join(", ")}</p>
                      {canVerify && (
                        <Button
                          variant="outline"
                          onClick={() => void remind(e.id)}
                          disabled={busy}
                        >
                          Send reminder
                        </Button>
                      )}
                    </article>
                  ))}
                  {stats && !stats.missing && (
                    <p>
                      No missing mandatory documents in your authorized scope.
                    </p>
                  )}
                </div>
              ) : (
                <SharedDataGrid<Certificate>
                  gridId="hrms-document-vault"
                  overview={false}
                  personalViews={false}
                  viewMode={phone ? "cards" : undefined}
                  title="Documents"
                  dataSource={source}
                  columns={columns}
                  getRowId={(r) => String(r.id)}
                  userId={user?.id}
                  organizationId={user?.access?.companyId}
                  initialQuery={{ pageSize: 25 }}
                  initialLayout={{
                    density: "compact",
                    visibility: { issue_date: false },
                    view: "list",
                  }}
                  exportFormats={["csv"]}
                  views={["list", "cards"]}
                  bulkActions={
                    canVerify
                      ? [
                          {
                            id: "verify",
                            label: "Verify selected",
                            confirm: (rows) =>
                              `Verify ${rows.length} selected documents?`,
                            run: async (rows) => {
                              await run(async () => {
                                for (const row of rows)
                                  await api.put(`${base}/${row.id}/verify`, {
                                    verification_status: "Verified",
                                    verifier_name: user?.email || "HR",
                                    verification_notes: "Bulk HR verification",
                                  });
                                setNotice(`${rows.length} documents verified.`);
                              });
                            },
                          },
                          {
                            id: "download",
                            label: "Download selected files",
                            run: async (rows) => {
                              await run(async () => {
                                const response = await api.post(
                                  base + "/download-bulk",
                                  { ids: rows.map((r) => r.id) },
                                  { responseType: "blob" },
                                );
                                const url = URL.createObjectURL(response.data);
                                const a = document.createElement("a");
                                a.href = url;
                                a.download = "employee-documents.zip";
                                a.click();
                                setTimeout(
                                  () => URL.revokeObjectURL(url),
                                  1000,
                                );
                              });
                            },
                          },
                        ]
                      : []
                  }
                  onSelectRecord={(r) => setSelected(r.employee)}
                  onOpen={(r) => void open(r)}
                  rowActions={[
                    {
                      id: "preview",
                      label: "Preview document",
                      icon: Eye,
                      quick: true,
                      run: (r) => open(r),
                    },
                    {
                      id: "download",
                      label: "Download document",
                      icon: Download,
                      quick: true,
                      run: (r) => download(r),
                    },
                  ]}
                  renderCard={(r) => (
                    <div className="dv-document-card">
                      <span className="dv-tag">{r.category}</span>
                      <h3>{r.title}</h3>
                      <p>
                        {r.employee.name} · {r.employee.code}
                      </p>
                      <span className="dv-status">{status(r)}</span>
                      <Button variant="outline" onClick={() => void open(r)}>
                        Preview & review
                      </Button>
                    </div>
                  )}
                  emptyContent={
                    <div className="dm-empty">
                      <FolderOpen size={38} />
                      <h3>No documents found</h3>
                      <p>Upload a document or adjust your filters.</p>
                    </div>
                  }
                />
              )}
            </section>
            <aside className="dv-panel dv-intelligence">
              <header>
                <h2>
                  <Users size={18} />
                  {selected ? "Employee details" : "Document intelligence"}
                </h2>
                {selected && (
                  <button
                    aria-label="Clear selected employee"
                    onClick={() => setSelected(null)}
                  >
                    <X size={17} />
                  </button>
                )}
              </header>
              {selected ? (
                <>
                  <div className="dv-profile">
                    <Avatar employee={selected} />
                    <div>
                      <h3>{selected.name}</h3>
                      <p>{selected.code}</p>
                      <span className="dv-tag">{selected.department}</span>
                    </div>
                  </div>
                  <p>{selected.designation}</p>
                  <p>{selected.email}</p>
                  <hr />
                  <h3>Document completion</h3>
                  <strong className="dv-completion">
                    {employeeInsights.data?.required_documents
                      ? `${Math.round((100 * (employeeInsights.data.required_documents - employeeInsights.data.missing_documents)) / employeeInsights.data.required_documents)}%`
                      : "—"}
                  </strong>
                  <p>
                    {employeeInsights.data?.documents || 0} submitted ·{" "}
                    {employeeInsights.data?.verified || 0} verified
                  </p>
                  {employeeInsights.data?.required_documents ? (
                    <progress
                      max={employeeInsights.data.required_documents}
                      value={
                        employeeInsights.data.required_documents -
                        employeeInsights.data.missing_documents
                      }
                    />
                  ) : (
                    <p>No mandatory checklist applies to this employee.</p>
                  )}
                  <h3>Missing mandatory documents</h3>
                  {employeeInsights.data?.missing_employees
                    .flatMap((e) => e.requirements)
                    .map((r, i) => (
                      <p className="dv-missing" key={i}>
                        {r.title}
                      </p>
                    ))}
                  {!employeeInsights.data?.missing_documents && (
                    <p>No missing requirements.</p>
                  )}
                  <p>
                    {employeeInsights.data?.expiring || 0} expiring soon ·{" "}
                    {employeeInsights.data?.expired || 0} expired
                  </p>
                  <h3>Recent activity</h3>
                  {activity.data?.items.map((c) => (
                    <div className="dv-activity" key={c.id}>
                      <strong>{c.title}</strong>
                      <p>
                        {c.verification_status} ·{" "}
                        {formatDate(c.verified_at || c.uploaded_at || null)}
                      </p>
                    </div>
                  ))}
                  {canVerify && (
                    <Button
                      disabled={busy}
                      onClick={() => void remind(selected.id)}
                    >
                      <Send size={15} />
                      Request documents / remind
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    onClick={() => {
                      change("employee_id", String(selected.id));
                      setTab("Documents");
                    }}
                  >
                    View all employee documents
                  </Button>
                </>
              ) : (
                <>
                  <div className="dv-insight-art">
                    <ShieldCheck size={55} />
                  </div>
                  <h3>A clearer view of compliance</h3>
                  <p>
                    Select an employee to see their documentation and missing
                    requirements.
                  </p>
                  <hr />
                  <h3>Needs your attention</h3>
                  <button
                    className="dv-insight-row"
                    onClick={() => setTab("Verification Queue")}
                  >
                    <span>Pending verification</span>
                    <strong>{stats?.pending ?? "—"}</strong>
                  </button>
                  <button
                    className="dv-insight-row"
                    onClick={() => {
                      setFilters({ verification_status: "Expiring Soon" });
                      setTab("Documents");
                    }}
                  >
                    <span>Renewals in 30 days</span>
                    <strong>{stats?.expiring ?? "—"}</strong>
                  </button>
                  <button
                    className="dv-insight-row"
                    onClick={() => setMissing(true)}
                  >
                    <span>Missing requirements</span>
                    <strong>{stats?.missing_documents ?? "—"}</strong>
                  </button>
                  <hr />
                  <p>
                    Document requirements are configurable. No checklist is
                    assumed for employees.
                  </p>
                </>
              )}
            </aside>
          </div>
        </>
      )}
      {tab === "Upload Documents" && (
        <section className="dv-panel dv-upload-panel">
          <DocumentUploadTools />
        </section>
      )}
      {tab === "Bulk Import / Export" && (
        <section className="dv-panel dv-import">
          <DocumentUploadTools mode="import" />
          <h3>Import & export history</h3>
          <p>
            Metadata imports are recorded by the existing import service; they
            do not upload employee binary files.
          </p>
          {history.isPending ? (
            <p role="status">Loading import history…</p>
          ) : history.isError ? (
            <p role="alert">Import history unavailable.</p>
          ) : (
            history.data?.map((h) => (
              <article key={h.id}>
                <FileSpreadsheet size={20} />
                <div>
                  <strong>{h.original_filename || h.operation_type}</strong>
                  <p>
                    {formatDate(h.requested_at)} · {h.status} ·{" "}
                    {h.total_records} records · {h.failure_count} errors
                  </p>
                </div>
                {h.failure_count > 0 && canVerify && (
                  <Button
                    variant="outline"
                    onClick={() =>
                      void run(async () => {
                        const response = await api.get(
                          `${base}/imports/${h.id}/report`,
                          { recordCache: false },
                        );
                        const report = response.data.errors
                          .map(
                            (e: { row: number; error: string }) =>
                              `Row ${e.row}: ${e.error}`,
                          )
                          .join("\n");
                        const url = URL.createObjectURL(
                          new Blob([report], {
                            type: "text/plain;charset=utf-8",
                          }),
                        );
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = `import-${h.id}-errors.txt`;
                        a.click();
                        setTimeout(() => URL.revokeObjectURL(url), 1000);
                      })
                    }
                  >
                    Download errors
                  </Button>
                )}
              </article>
            ))
          )}
          {!history.isPending && !history.data?.length && (
            <p>No import or export batches yet.</p>
          )}
        </section>
      )}
      {tab === "Policies & Requirements" && (
        <section className="dv-panel dv-requirements">
          <header>
            <div>
              <h2>Document policies & requirements</h2>
              <p>Apply a checklist only to the employees who need it.</p>
            </div>
            {canConfigure && (
              <Button onClick={() => setEdit({ ...blankRequirement })}>
                Add requirement
              </Button>
            )}
          </header>
          <div className="dv-policy-grid">
            {requirements.data?.map((r) => (
              <article key={r.id}>
                <span className="dv-tag">
                  {r.mandatory ? "Mandatory" : "Optional"} ·{" "}
                  {r.active ? "Active" : "Inactive"}
                </span>
                <h3>{r.title}</h3>
                <p>{r.certificate_type}</p>
                <p>
                  {r.employment_type || "All employment types"} ·{" "}
                  {r.employee_category || "All categories"}
                </p>
                <p>
                  {r.verification_required
                    ? "Verification required"
                    : "Submission only"}{" "}
                  · Remind {r.reminder_days} days before expiry
                </p>
                {canConfigure && (
                  <Button variant="outline" onClick={() => setEdit(r)}>
                    Edit requirement
                  </Button>
                )}
              </article>
            ))}
          </div>
          {!requirements.data?.length && (
            <div className="dm-empty">
              <BookOpen size={34} />
              <h3>Your requirements, your rules</h3>
              <p>
                Add the first requirement to start tracking missing
                documentation.
              </p>
            </div>
          )}
        </section>
      )}
      <Dialog open={filterOpen} onOpenChange={setFilterOpen}>
        <DialogContent className="dv-filter-dialog">
          <DialogTitle>Filter documents</DialogTitle>
          {filterPanel}
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!review}
        onOpenChange={(v) => {
          if (!v) {
            setReview(null);
            setFile(null);
            if (previewUrl) URL.revokeObjectURL(previewUrl);
            setPreviewUrl("");
          }
        }}
      >
        <DialogContent className="dv-review-dialog">
          <DialogTitle>{review?.title}</DialogTitle>
          <div className="dv-review-layout">
            <div className="dv-private-preview">
              {file ? (
                file.type.includes("pdf") ? (
                  <Suspense fallback={<p>Loading private PDF…</p>}>
                    <PdfPreview file={file} />
                  </Suspense>
                ) : file.type.startsWith("image/") ? (
                  <img src={previewUrl} alt={review?.title} />
                ) : (
                  <p>This file format can be downloaded for viewing.</p>
                )
              ) : (
                <p role="status">Loading private file…</p>
              )}
            </div>
            <div>
              <h3>{review?.employee.name}</h3>
              <p>
                {review?.certificate_type} · {review?.category}
              </p>
              <p>Reference: {review?.certificate_number || "Not supplied"}</p>
              <p>Issued: {formatDate(review?.issue_date || null)}</p>
              <p>Expires: {formatDate(review?.expiry_date || null)}</p>
              <p>
                Verified by {review?.verifier_name || "—"} ·{" "}
                {formatDate(review?.verified_at || null)}
              </p>
              <p>{review?.verification_notes}</p>
              <Button
                variant="outline"
                disabled={busy}
                onClick={() => review && void download(review)}
              >
                <Download size={15} />
                Download
              </Button>
              {canVerify && (
                <form
                  className="dv-review-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (review)
                      void run(async () => {
                        await api.put(`${base}/${review.id}/verify`, {
                          verification_status: reviewStatus,
                          verification_notes: reason,
                          verifier_name: verifier || user?.email || "HR",
                          verifier_company: verifierCompany,
                          verifier_designation: verifierDesignation,
                          verifier_contact: verifierContact,
                        });
                        setReview(null);
                        setNotice("Verification decision saved.");
                      });
                  }}
                >
                  <h3>Verification decision</h3>
                  <label>
                    Status
                    <NativeSelect
                      value={reviewStatus}
                      onChange={(e) => setReviewStatus(e.target.value)}
                    >
                      {[
                        "Verified",
                        "Rejected",
                        "Correction Required",
                        "Pending",
                      ].map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </NativeSelect>
                  </label>
                  <label>
                    Reason / notes
                    <textarea
                      required={["Rejected", "Correction Required"].includes(
                        reviewStatus,
                      )}
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                  </label>
                  {[
                    ["Verifier name", verifier, setVerifier],
                    ["Verifier company", verifierCompany, setVerifierCompany],
                    [
                      "Verifier designation",
                      verifierDesignation,
                      setVerifierDesignation,
                    ],
                    ["Verifier contact", verifierContact, setVerifierContact],
                  ].map(([label, value, set]) => (
                    <label key={label as string}>
                      {label as string}
                      <Input
                        value={value as string}
                        onChange={(e) =>
                          (set as (v: string) => void)(e.target.value)
                        }
                      />
                    </label>
                  ))}
                  <Button disabled={busy} type="submit">
                    <Check size={15} />
                    Save decision
                  </Button>
                </form>
              )}
              {notice && <p role="alert">{notice}</p>}
            </div>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={!!edit} onOpenChange={(v) => !v && setEdit(null)}>
        <DialogContent className="dv-policy-dialog">
          <DialogTitle>
            {edit?.id ? "Edit requirement" : "New document requirement"}
          </DialogTitle>
          {edit && (
            <form
              className="dv-policy-form"
              onSubmit={(e) => {
                e.preventDefault();
                void run(async () => {
                  await api.post(base + "/requirements", edit, {
                    params: { identity: edit.id },
                  });
                  setEdit(null);
                  setNotice("Document requirement saved.");
                });
              }}
            >
              {[
                ["title", "Requirement title"],
                ["certificate_type", "Certificate type"],
                ["employment_type", "Employment type (optional)"],
                ["employee_category", "Employee category (optional)"],
              ].map(([key, label]) => (
                <label key={key}>
                  {label}
                  <Input
                    required={key === "title" || key === "certificate_type"}
                    value={String(edit[key as keyof Requirement] || "")}
                    onChange={(e) =>
                      setEdit({ ...edit, [key]: e.target.value })
                    }
                  />
                </label>
              ))}
              {[
                ["department_id", "Department", departments.data],
                ["branch_id", "Branch", branches.data],
              ].map(([key, label, options]) => (
                <label key={key as string}>
                  {label as string}
                  <NativeSelect
                    value={String(edit[key as keyof Requirement] || "")}
                    onChange={(e) =>
                      setEdit({
                        ...edit,
                        [key as string]: Number(e.target.value) || null,
                      })
                    }
                  >
                    <option value="">All</option>
                    {(
                      options as { id: number; name: string }[] | undefined
                    )?.map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.name}
                      </option>
                    ))}
                  </NativeSelect>
                </label>
              ))}
              <label>
                Designation
                <NativeSelect
                  value={String(edit.designation_id || "")}
                  onChange={(e) =>
                    setEdit({
                      ...edit,
                      designation_id: Number(e.target.value) || null,
                    })
                  }
                >
                  <option value="">All designations</option>
                  {designations.data?.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </NativeSelect>
              </label>
              <label>
                Reminder days before expiry
                <Input
                  type="number"
                  min="0"
                  max="365"
                  value={edit.reminder_days}
                  onChange={(e) =>
                    setEdit({ ...edit, reminder_days: Number(e.target.value) })
                  }
                />
              </label>
              {[
                ["mandatory", "Mandatory"],
                ["reminders_enabled", "Automatic in-app reminders"],
                ["verification_required", "Verification required"],
                ["expiry_required", "Expiry date required"],
                ["active", "Active"],
              ].map(([key, label]) => (
                <label className="dv-checkbox" key={key}>
                  <input
                    type="checkbox"
                    checked={!!edit[key as keyof Requirement]}
                    onChange={(e) =>
                      setEdit({ ...edit, [key]: e.target.checked })
                    }
                  />
                  {label}
                </label>
              ))}
              {notice && <p role="alert">{notice}</p>}
              <Button disabled={busy}>Save requirement</Button>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
