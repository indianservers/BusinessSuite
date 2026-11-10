import "./assets-mobile.css";
import "./assets-workspace.css";
import { useEffect, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Box, Plus, RefreshCw, Zap } from "lucide-react";
import { api, assetApi } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { useDefinitionPermission } from "@/components/RecordDefinitionActions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/hooks/use-toast";
import { formatDate } from "@/lib/utils";
import { usePageTitle } from "@/hooks/use-page-title";
import EmployeeSearchSelect from "../../components/EmployeeSearchSelect";
import AssetWorkspace, {
  AssetMetrics,
  type AssetSummary,
} from "./AssetWorkspace";
import AssetLifecycleGrid from "./AssetLifecycleGrid";
import {
  EmployeeAssetProfileButton,
  Asset360Button,
  AssetHandoverButton,
  AssetRegistrationButton,
  AssetPolicyButton,
  AssetRecordWorkflow,
  AssetExitActions,
  useAssetRefresh,
  type CustodyRow,
} from "./AssetWorkflows";

type Category = { id: number; name: string };
type Assignment = CustodyRow & {
  employee_code?: string;
  department?: string;
  asset_category?: string;
  branch?: string;
  acknowledged_at?: string | null;
  remarks?: string | null;
};
type Clearance = {
  exit_id: number;
  employee_id: number;
  employee_name: string;
  last_working_date: string | null;
  cleared: boolean;
  department?: string;
  exit_type?: string;
  exit_status?: string;
  assets_assigned?: number;
  assets_returned?: number;
  issues?: { kind: string; asset_tag: string }[];
  checklist?: {
    id: number;
    task_name: string;
    department: string;
    completed: boolean;
  }[];
  outstanding_assets: {
    assignment_id: number;
    asset_id?: number;
    name: string;
    asset_tag: string;
  }[];
};
const errorText = (e: unknown) => {
  const value = (e as { response?: { data?: { detail?: unknown } } }).response
    ?.data?.detail;
  return typeof value === "string"
    ? value
    : "Please check the details and try again.";
};
export default function AssetsPage() {
  usePageTitle("Company assets");
  const user = useAuthStore((s) => s.user),
    [params, setParams] = useSearchParams(),
    location = useLocation();
  const views = ["inventory", "custody", "history", "clearance"];
  const [tab, setTab] = useState(
    views.includes(params.get("view") || "")
      ? params.get("view")!
      : "inventory",
  );
  const [statusFilter, setStatusFilter] = useState(""),
    [employeeId, setEmployeeId] = useState(""),
    [assetId, setAssetId] = useState(""),
    [categoryName, setCategoryName] = useState("");
  const refresh = useAssetRefresh();
  const permissions = useQuery({
    queryKey: ["asset-permissions", user?.id],
    queryFn: () =>
      api
        .get<{ can_manage: boolean }>("/assets/capabilities")
        .then((r) => r.data),
  });
  const canManage = !!permissions.data?.can_manage,
    canCreate = useDefinitionPermission(["asset_manage"], "create"),
    canAssign = useDefinitionPermission(["asset_manage"], "assign"),
    canEdit = useDefinitionPermission(["asset_manage"], "edit"),
    canDelete = useDefinitionPermission(["asset_manage"], "delete");
  const moduleGrant = user?.access?.grants.hrms,
    canAcknowledge =
      !!user?.is_superuser ||
      !user?.access?.managed ||
      (!!moduleGrant?.enabled && moduleGrant.actions.includes("edit"));
  useEffect(() => {
    if (location.hash === "#new-record") setTab("inventory");
  }, [location.hash, location.key]);
  const changeTab = (value: string) => {
    setTab(value);
    setParams(
      (current) => {
        current.set("view", value);
        return current;
      },
      { replace: true },
    );
  };
  const summary = useQuery({
    queryKey: ["asset-summary", user?.id],
    queryFn: () => api.get<AssetSummary>("/assets/summary").then((r) => r.data),
  });
  const categories = useQuery({
    queryKey: ["asset-categories"],
    queryFn: () => assetApi.categories().then((r) => r.data as Category[]),
  });
  const available = useQuery({
    queryKey: ["assets-available", user?.id],
    enabled: canManage,
    queryFn: () =>
      assetApi
        .list({ status: "Available" })
        .then(
          (r) => r.data as { id: number; name: string; asset_tag: string }[],
        ),
  });

  const clearance = useQuery({
    queryKey: ["asset-clearance", user?.id],
    enabled: tab === "clearance",
    queryFn: () =>
      api.get<Clearance[]>("/assets/exit-clearance").then((r) => r.data),
  });
  const assign = useMutation({
    mutationFn: () =>
      assetApi.assign({
        asset_id: Number(assetId),
        employee_id: Number(employeeId),
        assigned_date: new Date().toLocaleDateString("en-CA"),
        condition_at_assignment: "Good",
      }),
    onSuccess: async () => {
      setAssetId("");
      setEmployeeId("");
      await refresh();
      toast({ title: "Asset assigned; employee acknowledgment pending" });
    },
    onError: (e) =>
      toast({
        title: "Assignment failed",
        description: errorText(e),
        variant: "destructive",
      }),
  });
  const acknowledge = useMutation({
    mutationFn: (id: number) =>
      api.put(`/assets/assignments/${id}/acknowledge`),
    onSuccess: refresh,
    onError: (e) =>
      toast({
        title: "Acknowledgment failed",
        description: errorText(e),
        variant: "destructive",
      }),
  });
  const addCategory = useMutation({
    mutationFn: () => assetApi.createCategory({ name: categoryName.trim() }),
    onSuccess: async () => {
      setCategoryName("");
      await refresh();
      await categories.refetch();
    },
    onError: (e) =>
      toast({
        title: "Could not add category",
        description: errorText(e),
        variant: "destructive",
      }),
  });
  return (
    <div className="hrms-assets-page space-y-5">
      <header className="asset-page-heading">
        <div className="flex gap-3 items-center">
          <span className="asset-symbol">
            <Box size={26} />
          </span>
          <div>
            <h1>Company Assets</h1>
            <p>
              Bikes, laptops, phones and equipment: handovers, custody, returns
              and exit clearance.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {canManage && <AssetPolicyButton />}
          <Button variant="outline" onClick={() => void refresh()}>
            <RefreshCw size={15} />
            Refresh
          </Button>
        </div>
      </header>
      <nav aria-label="Asset views" className="flex flex-wrap gap-2">
        {[
          ["inventory", "Inventory"],
          ["custody", "Employee custody"],
          ["history", "Return history"],
          ["clearance", "Exit clearance"],
        ].map(([id, label]) => (
          <Button
            key={id}
            variant={tab === id ? "default" : "outline"}
            aria-pressed={tab === id}
            onClick={() => changeTab(id)}
          >
            {label}
          </Button>
        ))}
      </nav>
      {canManage && (canCreate || canAssign) && (
        <div className="asset-quick-actions">
          <span>
            <Zap size={17} />
            Quick actions
          </span>
          {canCreate && (
            <AssetRegistrationButton
              openRequest={
                location.hash === "#new-record" ? location.key : undefined
              }
              categories={categories.data || []}
              onSaved={() => void refresh()}
            />
          )}{" "}
          {canAssign && <AssetHandoverButton />}
          <Button variant="outline" onClick={() => changeTab("custody")}>
            Record return
          </Button>
          <Button variant="outline" onClick={() => changeTab("history")}>
            Inspect return
          </Button>
          <Button variant="outline" onClick={() => changeTab("clearance")}>
            Process exit clearance
          </Button>
        </div>
      )}
      {tab === "inventory" && (
        <>
          <AssetMetrics summary={summary.data} onFilter={setStatusFilter} />
          <div
            className={`grid items-start gap-4 ${canManage ? "xl:grid-cols-[15rem_minmax(0,1fr)]" : ""}`}
          >
            {canManage && (
              <aside className="asset-panel space-y-4">
                <h2>Custody actions</h2>
                {canAssign && (
                  <>
                    <label className="asset-form-field">
                      Available asset
                      <select
                        aria-label="Available asset"
                        value={assetId}
                        onChange={(e) => setAssetId(e.target.value)}
                      >
                        <option value="">Select available asset</option>
                        {available.data?.map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.name} ({a.asset_tag})
                          </option>
                        ))}
                      </select>
                    </label>
                    {available.isError && (
                      <p role="alert">
                        Available assets could not load. Use Refresh to retry.
                      </p>
                    )}
                    <EmployeeSearchSelect
                      endpoint="/assets/employees"
                      value={employeeId}
                      onChange={setEmployeeId}
                    />
                    <p className="text-xs text-muted-foreground">
                      Assign one asset here or use Assign multiple assets for
                      dates, accessories and a complete handover.
                    </p>
                    <Button
                      disabled={!assetId || !employeeId || assign.isPending}
                      onClick={() => assign.mutate()}
                    >
                      Assign asset
                    </Button>
                  </>
                )}
                {canCreate && (
                  <details>
                    <summary>Add asset category</summary>
                    <form
                      className="asset-form-grid mt-3"
                      onSubmit={(e) => {
                        e.preventDefault();
                        addCategory.mutate();
                      }}
                    >
                      <Input
                        aria-label="New asset category"
                        required
                        maxLength={100}
                        value={categoryName}
                        onChange={(e) => setCategoryName(e.target.value)}
                      />
                      <Button
                        disabled={!categoryName.trim() || addCategory.isPending}
                      >
                        <Plus size={14} />
                        Add category
                      </Button>
                    </form>
                  </details>
                )}
              </aside>
            )}
            <AssetWorkspace
              categories={categories.data || []}
              summary={summary.data}
              status={statusFilter}
              setStatus={setStatusFilter}
              canEdit={canManage && canEdit}
              canDelete={canManage && canDelete}
            />
          </div>
        </>
      )}
      {(tab === "custody" || tab === "history") && (
        <section className="asset-panel">
          <div className="asset-panel-heading">
            <div>
              <h2>
                {tab === "history"
                  ? "Returned assets"
                  : "Assigned equipment & handover"}
              </h2>
              <p>
                {tab === "history"
                  ? "Physical returns, inspection approvals and recovery proposals."
                  : "Employee custody, acknowledgments, due dates and transfers."}
              </p>
            </div>
            {canManage && canAssign && <AssetHandoverButton />}
          </div>
          <AssetLifecycleGrid
            scope={`hrms-asset-${tab}`}
            source={tab as "custody" | "history"}
            items={[] as Assignment[]}
            fields={[
              {
                id: "employee",
                label: "Employee",
                value: (r) => r.employee_name,
              },
              {
                id: "department",
                label: "Department",
                value: (r) => r.department || "Unassigned",
              },
              {
                id: "category",
                label: "Asset type",
                value: (r) => r.asset_category || "Uncategorized",
              },
              {
                id: "branch",
                label: "Branch / location",
                value: (r) => r.branch || "Unspecified",
              },
              {
                id: "status",
                label: "Status",
                value: (r) =>
                  r.returned_date
                    ? r.inspection_status || "Returned"
                    : r.acknowledged
                      ? "Acknowledged"
                      : "Pending acknowledgment",
              },
            ]}
            renderItem={(r) => (
              <div className="asset-form-grid">
                <h3>
                  {r.asset_id ? (
                    <Asset360Button
                      assetId={r.asset_id}
                      label={`${r.asset_name} · ${r.asset_tag}`}
                      canManage={canManage && canEdit}
                    />
                  ) : (
                    r.asset_name
                  )}
                </h3>
                <Link
                  className="text-violet-700 underline"
                  to={`/hrms/employees/${r.employee_id}`}
                >
                  {r.employee_name} · {r.employee_code || r.employee_id}
                </Link>
                <EmployeeAssetProfileButton
                  employeeId={r.employee_id}
                  label="Employee asset profile"
                  canManage={canManage && canAssign}
                />
                <p>
                  {r.department} · Assigned {formatDate(r.assigned_date)}
                </p>
                <p>
                  Expected return: {formatDate(r.expected_return_date ?? null)}
                </p>
                <Badge variant="outline">
                  {r.acknowledged
                    ? "Acknowledged"
                    : "Awaiting employee acknowledgement"}
                </Badge>
                {r.acknowledged_at && (
                  <p>Acknowledged {formatDate(r.acknowledged_at)}</p>
                )}
                {r.remarks && <p>Handover notes: {r.remarks}</p>}
                {r.returned_date && (
                  <p>
                    Returned {formatDate(r.returned_date)} ·{" "}
                    {r.condition_at_return} · Inspection {r.inspection_status}
                  </p>
                )}
                {!r.returned_date &&
                  !r.acknowledged &&
                  user?.employee_id === r.employee_id && (
                    <Button
                      disabled={!canAcknowledge || acknowledge.isPending}
                      onClick={() => acknowledge.mutate(r.id)}
                    >
                      Acknowledge receipt
                    </Button>
                  )}
                <AssetRecordWorkflow
                  row={r}
                  canManage={canManage && canAssign}
                />
              </div>
            )}
          />
        </section>
      )}
      {tab === "clearance" && (
        <section className="asset-panel">
          <div className="asset-panel-heading">
            <div>
              <h2>Exit asset clearance</h2>
              <p>
                Linked to existing employee exit cases. Asset sign-off never
                completes company-wide offboarding.
              </p>
            </div>
            <Link className="text-sm text-violet-700 underline" to="/hrms/exit">
              Initiate or open existing exit
            </Link>
          </div>
          {clearance.isPending ? (
            <p role="status">Loading exits…</p>
          ) : clearance.isError ? (
            <p role="alert">
              Exit clearance could not load. Use Refresh to retry.
            </p>
          ) : (
            <AssetLifecycleGrid
              scope="hrms-asset-clearance"
              items={clearance.data || []}
              fields={[
                {
                  id: "status",
                  label: "Status",
                  value: (r) =>
                    r.cleared ? "Assets cleared" : "Awaiting action",
                },
              ]}
              renderItem={(r) => (
                <div className="asset-form-grid">
                  <h3>{r.employee_name}</h3>
                  <p>
                    {r.department} · {r.exit_type} · Last working day{" "}
                    {formatDate(r.last_working_date)}
                  </p>
                  <p>
                    {r.assets_returned || 0} returned / {r.assets_assigned || 0}{" "}
                    assignments
                  </p>
                  <Badge variant={r.cleared ? "success" : "warning"}>
                    {r.cleared
                      ? "Assets cleared"
                      : `${r.outstanding_assets.length} awaiting return`}
                  </Badge>
                  {r.outstanding_assets.map((a) => (
                    <div key={a.assignment_id}>
                      {a.asset_id ? (
                        <Asset360Button
                          assetId={a.asset_id}
                          label={`${a.name} · ${a.asset_tag}`}
                          canManage={canManage && canEdit}
                        />
                      ) : (
                        a.name
                      )}
                    </div>
                  ))}
                  <div className="asset-department-approvals">
                    <h3>Existing department approvals</h3>
                    {r.checklist?.map((t) => (
                      <p key={t.id}>
                        <span>{t.completed ? "✓" : "○"}</span> {t.department} ·{" "}
                        {t.task_name}
                      </p>
                    ))}
                  </div>
                  <AssetExitActions
                    exitId={r.exit_id}
                    canManage={canManage && canAssign}
                    issues={r.issues}
                  />
                  {!r.cleared && (
                    <Button
                      variant="outline"
                      onClick={() => changeTab("custody")}
                    >
                      Open custody & returns
                    </Button>
                  )}
                </div>
              )}
            />
          )}
        </section>
      )}
    </div>
  );
}
