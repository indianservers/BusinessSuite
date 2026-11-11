import {useRouteViewState} from "@/hooks/use-route-view-state";
import { LoadingState } from "@/components/ui/state";
import { useDefinitionPermission } from "@/components/RecordDefinitionActions";
import { withRecordViewHost } from "@/shared/data-grid/RecordViewHost";
import WorkspaceViewBar, { type WorkspaceView } from "@/shared/workspace/WorkspaceViewBar";
import RecordLensViews from "@/shared/workspace/RecordLensViews";
import { PipelineDrawer } from "@/shared/pipeline/PipelineExperience";
import PipelineDomainDetails from "@/shared/pipeline/PipelineDomainDetails";
import PipelineBoard, { PipelineSearch } from "@/shared/pipeline/PipelineBoard";
import CompactActions from "@/components/actions/CompactActions";
import { useRecordView } from "@/lib/smart-cache/use-record-view";
import { NativeSelect } from "@/components/ui/native-select";
import CRMDataTransfer from "../CRMDataTransfer";
import { useCreateIntent } from "@/hooks/use-create-intent";
import DealsDataGrid, { dealGridSource } from "./DealsDataGrid";
import {
  emptyQuery,
  type GridQuery,
  type GridResult,
} from "@/shared/data-grid/types";
import DealAnalytics from "./DealAnalytics";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Archive,
  Plus,
  Search,
  RefreshCw,
  Download,
  LayoutGrid,
  List,
  Table2,
  Calendar,
  TrendingUp,
  Settings2,
} from "lucide-react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuthStore } from "@/store/authStore";
import { useQueryClient } from "@tanstack/react-query";
import { affectsResource, publishGridRecord, removeGridRecords, removedRecordIds, recordSavedEvent, type RecordSaved } from "@/lib/record-changes";
import { crmApi } from "../api";
import CRMStageDialog from "../CRMStageDialog";
import { dealError, dealMoney, dealOptions, label } from "./deal-utils";
import "./deals.css";

const Capture = lazy(() =>
  import("../CRMWorkspacePage").then((module) => ({
    default: module.QuickDealDialog,
  })),
);
type Row = Record<string, any>;
type Filters = {
  search: string;
  pipeline_id: string;
  stage_id: string;
  owner_id: string;
  currency: string;
  status: string;
  priority: string;
  deal_type: string;
  start: string;
  end: string;
  industry: string;
  source: string;
  team_id: string;
  entered_stage_id: string;
  lost_reason: string;
  no_next: boolean;
};
const empty: Filters = {
  search: "",
  pipeline_id: "",
  stage_id: "",
  owner_id: "",
  currency: "",
  status: "",
  priority: "",
  deal_type: "",
  start: "",
  end: "",
  industry: "",
  source: "",
  team_id: "",
  entered_stage_id: "",
  lost_reason: "",
  no_next: false,
};
const columns = [
  "name",
  "company_id",
  "amount",
  "currency",
  "stage_id",
  "probability",
  "owner_user_id",
  "expected_close_date",
  "priority",
  "status",
  "next_follow_up_at",
];
const columnLabel = (column: string) =>
  (
    ({
      company_id: "Company",
      owner_user_id: "Owner",
      stage_id: "Stage",
      expected_close_date: "Expected close",
      next_follow_up_at: "Next action",
      name: "Deal",
      amount: "Value",
    }) as Record<string, string>
  )[column] || label(column);
const dealLensModes = ["calendar","gantt","timeline","team","activity","mindmap","whiteboard"];
const dealViews: WorkspaceView[] = [
 {id:"grid",label:"Table",icon:"table",description:"A precise, customisable data grid",color:"#16a596"},
 {id:"kanban",label:"Board",icon:"board",description:"Opportunities moving through sales stages",color:"#6b8be8"},
 {id:"cards",label:"Gallery",icon:"gallery",description:"Rich cards for every opportunity",color:"#d97aa5"},
 {id:"list",label:"List",description:"An expandable view of your deals",color:"#9370d9"},
 {id:"gantt",label:"Gantt",description:"Opportunity schedules and closing windows",category:"Plan",color:"#ec8276"},
 {id:"timeline",label:"Timeline",description:"Upcoming close dates and milestones",category:"Plan",color:"#d7a14d"},
 {id:"calendar",label:"Calendar",description:"Closing dates on your calendar",category:"Plan",color:"#e29c58"},
 {id:"forecast",label:"Forecast",icon:"dashboard",description:"Revenue, probabilities and performance",category:"Explore",color:"#9b70d0"},
 {id:"team",label:"Team",description:"Ownership and opportunity distribution",category:"Explore",color:"#46a79a"},
 {id:"mindmap",label:"Mind map",description:"Explore deals by owner or sales stage",category:"Explore",color:"#d776a7"},
 {id:"whiteboard",label:"Whiteboard",description:"Arrange your opportunity strategy",category:"Explore",color:"#c1a04b"},
 {id:"activity",label:"Activity",description:"Recently updated opportunities",category:"Collaborate",color:"#509edb"},
 {id:"channel",label:"Channel",description:"Team conversations in your CRM",category:"Collaborate",href:"/crm/messages",color:"#8b5cf6"},
 {id:"files",label:"Files",description:"Sales collateral and shared documents",category:"Collaborate",href:"/crm/files",color:"#7999be"},
 {id:"form",label:"Forms",description:"Capture enquiries and lead requests",category:"Collaborate",href:"/crm/webforms",color:"#9672d7"},
];

function EnterpriseDealsPage({ initialView = "grid" }: { initialView?: "grid" | "kanban" }) {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const canCreate=useDefinitionPermission(["crm_deals_manage","crm_manage","crm_admin"],"create");
  const queryClient = useQueryClient();
  const key = `crm-deal-workspace:${user?.access?.companyId}:${user?.id}`;
  const [gridQuery, setGridQuery] = useState<GridQuery>(() => ({
    ...emptyQuery(),
    sorting: [{ id: "updated_at", desc: true }],
  }));
  const [gridReady, setGridReady] = useState(false);
  const [selectedRecords, setSelectedRecords] = useState<Row[]>([]);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filters, setFilters] = useRouteViewState<Filters>("filters",empty),
    [search, setSearch] = useRouteViewState("search","");
  const [lensPreview,setLensPreview] = useState<string>();
  const [forecastGroup, setForecastGroup] = useState("month");
  const [mode, setMode] = useRouteViewState<string>("mode",initialView),
    [page, setPage] = useRouteViewState("page",1),
    [reload, setReload] = useState(0);
  const [data, setData] = useState<Row>(),
    [summary, setSummary] = useState<Row>(),
    [options, setOptions] = useState<Record<string, Row[]>>({});
  const [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [lookupsError, setLookupsError] = useState("");
  const [lookupsLoading, setLookupsLoading] = useState(true);
  const [captureStage,setCaptureStage]=useState<number>();
  const [create, setCreate] = useState(false),
    [editing, setEditing] = useState<number>(),
    [transition, setTransition] = useState<{ id: number; stage?: number }>();
  useCreateIntent(kind => { if (kind === "deals" && canCreate) setCreate(true); });
  const [selected, setSelected] = useState<number[]>([]),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  const [columnOrder, setColumnOrder] = useState(columns),
    [hidden, setHidden] = useState<string[]>([]),
    [pinned, setPinned] = useState("name"),
    [widths, setWidths] = useState<Record<string, number>>({});
  const [group, setGroup] = useState(""),
    [sort, setSort] = useState("updated_at"),
    [direction, setDirection] = useState("desc");
  const [loadedKey, setLoadedKey] = useState("");
  const [views, setViews] = useState<Row[]>([]),
    [viewName, setViewName] = useState("");
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(key) || "{}");
      setColumnOrder(saved.columnOrder || columns);
      setHidden(saved.hidden || []);
      setWidths(saved.widths || {});
      setPinned(saved.pinned || "name");
      setViews(saved.views || []);
      setLoadedKey(key);
    } catch {
      setLoadedKey(key); /* Invalid preferences do not block real data. */
    }
  }, [key]);
  useEffect(() => {
    if (loadedKey !== key) return;
    localStorage.setItem(
      key,
      JSON.stringify({ columnOrder, hidden, widths, pinned, views }),
    );
  }, [key, loadedKey, columnOrder, hidden, widths, pinned, views]);
  useEffect(() => {
    const timer = setTimeout(
      () => setFilters((current) => current.search===search?current:({ ...current, search })),
      300,
    );
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    setSelected([]);
  }, [page]);
  const filterResetReady=useRef(false);
  useEffect(() => {
    if(!filterResetReady.current){filterResetReady.current=true;return;}
    setPage(1);
    setSelected([]);
  }, [filters, mode]);
  useEffect(() => {
    const handler = () => setReload((value) => value + 1);
    window.addEventListener("crm:records-changed", handler);
    return () => window.removeEventListener("crm:records-changed", handler);
  }, []);
  useEffect(() => {
    let active = true;
    setLookupsLoading(true);
    void Promise.all(
      [
        "deal-workspace/pipelines",
        "deal-workspace/pipeline-stages",
        "deal-workspace/teams",
        "deal-workspace/assignees",
      ].map(
        async (resource) =>
          [
            resource,
            await dealOptions(resource).catch((error) => {
              if (resource === "teams" && error?.response?.status === 403)
                return [];
              throw error;
            }),
          ] as const,
      ),
    )
      .then((entries) => {
        if (active) {
          const values = Object.fromEntries(entries);
          values.teams = values["deal-workspace/teams"] || [];
          values.pipelines = values["deal-workspace/pipelines"] || [];
          values["pipeline-stages"] =
            values["deal-workspace/pipeline-stages"] || [];
          setOptions(values);
          setLookupsError("");
        }
      })
      .catch((e) => {
        if (active) setLookupsError(dealError(e));
      }).finally(() => { if (active) setLookupsLoading(false); });
    return () => {
      active = false;
    };
  }, [reload]);
  const params = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(filters).filter(
          ([, value]) => value !== "" && value !== false,
        ),
      ),
    [filters],
  );
  useEffect(() => {
    const changed = (event: Event) => {
      const change=(event as CustomEvent<RecordSaved>).detail;
      const {url,method,record} = change;
      if (!affectsResource("/crm/deals",url)&&change.resource!=="/crm/deals") return;
      const removed=new Set(removedRecordIds(change,"/crm/deals").map(String));
      if(removed.size){removeGridRecords(queryClient,dealGridSource(params).key,[...removed]);setData(current=>{if(!current)return current;const items=current.items.filter((row:Row)=>!removed.has(String(row.id)));return {...current,items,total:Math.max(0,current.total-(current.items.length-items.length))};});setSelected(current=>current.filter(id=>!removed.has(String(id))));}
      else if (method !== "delete" && record?.id) {
        publishGridRecord(queryClient,dealGridSource(params).key,record as Row & {id:number});
        setData(current => {
          if (!current) return current;
          const exists=current.items.some((row:Row)=>row.id===record.id);
          if(!exists&&(page!==1||Object.values(params).some(Boolean)))return current;
          return {...current,items:exists?current.items.map((row:Row)=>row.id===record.id?{...row,...record}:row):[record,...current.items],total:current.total+(exists?0:1)};
        });
      }
      setReload(value=>value+1);
    };
    window.addEventListener(recordSavedEvent,changed);
    return () => window.removeEventListener(recordSavedEvent,changed);
  },[params,page,queryClient]);
  useEffect(() => {
    if (mode === "grid") return;
    const controller = new AbortController();
    setLoading(true);
    void dealGridSource(params)
      .load(
        {
          ...gridQuery,
          search: filters.search,
          grouping: [],
          path: [],
          page,
          pageSize: mode === "kanban" ? 100 : 25,
        },
        controller.signal,
      )
      .then((result) => {
        setData({
          items: result.rows,
          total: result.total,
          page: result.page,
          pages: Math.ceil(result.pageTotal / result.pageSize),
          can_manage: result.permissions?.edit,
          can_export: result.permissions?.export,
          can_archive: result.permissions?.archive,
          can_assign: result.permissions?.assign,
        });
        setSummary(result.context?.summary as Row);
        setError("");
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(dealError(e));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [
    params,
    page,
    mode,
    sort,
    direction,
    reload,
    JSON.stringify(gridQuery.filters),
    JSON.stringify(gridQuery.sorting),
  ]);
  useRecordView<GridResult<Row>>("/crm/deal-workspace/grid/query", { state: JSON.stringify({ ...gridQuery, search: filters.search, grouping: [], path: [], page, pageSize: mode === "kanban" ? 100 : 25 }), base: JSON.stringify(params) }, result => {
    if (mode !== "grid") {
      setData({ items: result.rows, total: result.total, page: result.page, pages: Math.ceil(result.pageTotal / result.pageSize), can_manage: result.permissions?.edit, can_export: result.permissions?.export, can_archive: result.permissions?.archive, can_assign: result.permissions?.assign });
      setSummary(result.context?.summary as Row);
    }
  }, () => { setData(undefined); setSummary(undefined); setSelected([]); });
  const rows: Row[] = data?.items || [];
  const lookup = (resource: string, id: unknown) => {
    const found = options[resource]?.find(
      (item) => Number(item.id) === Number(id),
    );
    return String(
      found?.name ||
        found?.full_name ||
        found?.email ||
        (id ? `#${id}` : "Unassigned"),
    );
  };
  const change = (name: keyof Filters, value: string | boolean) =>
    setFilters((current) => ({ ...current, [name]: value }));
  const clearDealFilters = () => {
    setFilters(empty);
    setSearch("");
    setGridQuery(current => ({ ...current, search: "", filters: { logic: "and", rules: [] }, page: 1 }));
  };
  const activeFilterCount = Object.entries(filters).filter(([key, value]) => key !== "search" && value !== "" && value !== false).length;
  const advancedFilterCount = Object.entries(filters).filter(([key, value]) => !["search", "pipeline_id", "stage_id", "owner_id"].includes(key) && value !== "" && value !== false).length;
  async function exportDeals(format: string) {
    try {
      const response = await dealGridSource(params).export!({
        format: format as "csv" | "xlsx",
        scope: "filtered",
        ids: [],
        columns,
        includeGroups: false,
        includeSummaries: true,
        query: { ...gridQuery, search: filters.search },
      });
      const url = URL.createObjectURL(response as Blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `deals.${format}`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError(dealError(e));
    }
  }
  async function bulk(value: string, field = "owner_user_id") {
    if (!value || !selected.length) return;
    const stage = options["pipeline-stages"]?.find(
      (item) => item.id === Number(value),
    );
    const reason =
      field === "stage_id" && (stage?.is_lost || stage?.stage_type === "lost")
        ? window.prompt(
            "Lost reason for the selected deals (at least five characters)",
          )
        : "";
    if (
      reason === null ||
      (field === "stage_id" &&
        !window.confirm(
          `Apply the selected stage to ${selected.length} deals? Each deal's entry requirements and permissions will be checked.`,
        ))
    )
      return;
    setBusy(true);
    try {
      const response = await api.post("/crm/deal-workspace/bulk", {
        records: selected.map((id) => ({
          id,
          version:
            selectedRecords.find((item) => item.id === id)?.version ||
            rows.find((item) => item.id === id)?.version ||
            1,
        })),
        [field]: Number(value),
        lost_reason: reason || "",
      });
      const failed = response.data.items.filter((item: Row) => !item.saved);
      setSelected(failed.map((item: Row) => item.id));
      setNotice(
        `${selected.length - failed.length} of ${selected.length} deals updated. ${failed.map((item: Row) => `#${item.id}: ${item.message}`).join(". ")}`,
      );
    } catch (e) {
      setError(dealError(e));
    } finally {
      setBusy(false);
      setReload((v) => v + 1);
    }
  }
  async function archiveSelected() {
    if (!selected.length || busy) return;
    if (selected.length > 200) {
      setError("Choose at most 200 deals to archive at a time.");
      return;
    }
    if (
      !window.confirm(
        `Archive ${selected.length} selected deals? Historical records will be preserved.`,
      )
    )
      return;
    setBusy(true);
    try {
      const response = await api.post("/crm/deal-workspace/grid/archive", {
        records: selected.map((id) => ({
          id,
          version:
            selectedRecords.find((r) => r.id === id)?.version ||
            rows.find((r) => r.id === id)?.version ||
            1,
        })),
      });
      const failed = response.data.items.filter((r: Row) => !r.saved);
      setSelected(failed.map((r: Row) => r.id));
      setNotice(
        `${selected.length - failed.length} deals archived. ${failed.map((r: Row) => `#${r.id}: ${r.message}`).join(". ")}`,
      );
    } catch (e) {
      setError(dealError(e));
    } finally {
      setBusy(false);
      setReload((v) => v + 1);
    }
  }
  const value = (row: Row, column: string) =>
    column === "name" ? (
      <Link className="ed-deal-name" to={`/crm/deals/${row.id}`}>
        {row.name}
      </Link>
    ) : column === "company_id" ? (
      row.company_name || lookup("companies", row.company_id)
    ) : column === "stage_id" ? (
      row.stage_name || lookup("pipeline-stages", row.stage_id)
    ) : column === "owner_user_id" ? (
      row.owner_name || lookup("deal-workspace/assignees", row.owner_user_id)
    ) : column === "amount" ? (
      dealMoney(row.amount, row.currency)
    ) : column === "probability" ? (
      `${row.probability}%`
    ) : column === "priority" ? (
      <span data-priority-badge data-priority={row.priority}
        className={`ed-priority ${String(row.priority || "Medium").toLowerCase()}`}
      >
        {row.priority || "Medium"}
      </span>
    ) : (
      String(row[column] ?? "—")
    );
  const visible = columnOrder.filter((column) => !hidden.includes(column));
  const grouped = group
    ? [
        ...new Set(rows.map((row) => String(row[group] || "Unassigned"))),
      ].flatMap((groupValue) => [
        { group: groupValue },
        ...rows.filter(
          (row) => String(row[group] || "Unassigned") === groupValue,
        ),
      ])
    : rows;
  const counts = summary?.counts || {};
  const stageOptions = (options["pipeline-stages"] || []).filter(
    (stage) =>
      !filters.pipeline_id ||
      String(stage.pipeline_id || stage.pipelineId) === filters.pipeline_id,
  );
  const forecastRows: Row[] =
    forecastGroup === "quarter"
      ? Object.values(
          (summary?.forecast || []).reduce(
            (groups: Record<string, Row>, row: Row) => {
              const [year, month] = String(row.month).split("-").map(Number);
              const period =
                row.month === "Unscheduled"
                  ? "Unscheduled"
                  : `${year}-Q${Math.ceil(month / 3)}`;
              const key = `${period}:${row.currency}`;
              const current = groups[key] || {
                month: period,
                currency: row.currency,
                count: 0,
                amount: 0,
                weighted: 0,
              };
              groups[key] = {
                ...current,
                count: current.count + row.count,
                amount: current.amount + row.amount,
                weighted: current.weighted + row.weighted,
              };
              return groups;
            },
            {},
          ),
        )
      : forecastGroup === "month"
        ? summary?.forecast || []
        : (summary?.breakdowns?.[forecastGroup] || []).map((row: Row) => ({
            ...row,
            month: lookup(
              forecastGroup === "owner"
                ? "deal-workspace/assignees"
                : forecastGroup === "stage"
                  ? "pipeline-stages"
                  : "pipelines",
              row.id,
            ),
          }));
  function card(row: Row) {
    return (
      <article data-priority-row data-priority={row.priority}
        className="ed-card"
        key={row.id}
        draggable={Boolean(data?.can_manage)}
        onDragStart={(event) =>
          event.dataTransfer.setData("application/x-crm-deal", String(row.id))
        }
      >
        <Link className="ed-deal-name" to={`/crm/deals/${row.id}`}>
          {row.name}
        </Link>
        <p className="ed-muted">
          {row.company_name || lookup("companies", row.company_id)}
        </p>
        <div className="ed-card-line">
          <strong>{dealMoney(row.amount, row.currency)}</strong>
          <span>{row.probability}%</span>
        </div>
        <div className="ed-card-line">
          <span>
            {row.owner_name ||
              lookup("deal-workspace/assignees", row.owner_user_id)}
          </span>
          <span data-priority-badge data-priority={row.priority}
            className={`ed-priority ${String(row.priority || "Medium").toLowerCase()}`}
          >
            {row.priority || "Medium"}
          </span>
        </div>
        <p className="ed-muted">
          Close: {row.expected_close_date || "Unscheduled"}
        </p>
        {row.next_follow_up_at && (
          <p className="ed-muted">
            Next: {new Date(row.next_follow_up_at).toLocaleString()}
          </p>
        )}
        {row.health?.reasons?.slice(0, 2).map((reason: string) => (
          <p className="ed-risk" key={reason}>
            {reason}
          </p>
        ))}
        <div className="ed-card-actions">
          <CompactActions><Link to={`/crm/deals/${row.id}?tab=Activities`}>Next action</Link>
<Link to={`/crm/deals/${row.id}?tab=Notes+%26+Files`}>Note</Link>
{data?.can_manage && (
            <>
              <Button type="submit" variant="outline" onClick={() => setEditing(row.id)}>Edit</Button>
              <button onClick={() => setTransition({ id: row.id })}>
                Move
              </button>
            </>
          )}</CompactActions>


        </div>
      </article>
    );
  }
  return (
    <main className={`ed-workspace ed-collection ${mode === "kanban" ? "ed-pipeline-workspace" : ""}`} aria-busy={loading}>
      <header className="ed-header">
        <div className="ed-collection-heading">
          <h1>Deals</h1>
          <p className="ed-muted">
            Permitted opportunities
          </p>
        </div>
        <div className="ed-actions">
          <Link className="ed-link-button" to="/crm/pipeline-settings">
            <Settings2 size={16} />
            Pipelines
          </Link>
          <Button
            variant="outline"
            onClick={() => setReload((v) => v + 1)}
            aria-label="Refresh deals"
          >
            <RefreshCw size={16} />
          </Button>
          {canCreate && <CRMDataTransfer entity="deals" importOnly onImported={()=>setReload(v=>v+1)}/>}
          {canCreate && (
            <Button onClick={() => setCreate(true)}>
              <Plus size={16} />
              Create deal
            </Button>
          )}
        </div>
      </header>
      {error && (
        <div role="alert" className="ed-error">
          {error}
          <Button variant="outline" onClick={() => setReload((v) => v + 1)}>
            Retry
          </Button>
        </div>
      )}
      {lookupsError && (
        <p role="alert" className="ed-error">
          Choices could not load: {lookupsError}
          <button onClick={() => setReload((v) => v + 1)}>Retry choices</button>
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {mode !== "kanban" && <details className="ed-summary ed-sales-overview">
      <summary>Sales overview · {counts.open ?? "—"} open · {counts.overdue ?? "—"} overdue follow-ups</summary>
      <section className="ed-stats ed-stats-primary" aria-label="Deal statistics">
        {[
          ["Open deals", counts.open],
          ["Closing this month", counts.closing_month],
          ["Overdue follow-ups", counts.overdue],
        ].map(([name, number]) => (
          <div key={String(name)}>
            <span>{name}</span>
            <strong>{loading && !data ? "…" : (number ?? "—")}</strong>
          </div>
        ))}
      </section>
      <details className="ed-summary-details">
        <summary>More sales metrics</summary>
        <section className="ed-stats" aria-label="Additional deal statistics">
          {[["Won this month", counts.won_month], ["Lost this month", counts.lost_month], ["Without activity", counts.without_activity]].map(([name, number]) => <div key={String(name)}><span>{name}</span><strong>{loading && !data ? "…" : (number ?? "—")}</strong></div>)}
        {["pipeline", "weighted"].map((metric) => (
          <div key={metric}>
            <span>
              {metric === "pipeline" ? "Pipeline value" : "Weighted pipeline"}
            </span>
            {summary?.currencies?.length ? (
              summary.currencies.map((row: Row) => (
                <strong className="ed-money-stat" key={row.currency}>
                  {dealMoney(row[metric], row.currency)}
                </strong>
              ))
            ) : (
              <strong>—</strong>
            )}
          </div>
        ))}
        </section>
      </details>
      </details>}
      <WorkspaceViewBar scope="crm-deals" label="Deal views" active={mode} views={dealViews} onChange={setMode} primary={["grid","kanban","forecast"]}/>
      <section className="ed-controls">
        <div className="ed-toolbar">
          {mode !== "grid" && (
            <div className="ed-search">
              <Search size={16} />
              <Input
                aria-label="Search deals"
                placeholder="Search deals..."
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>
          )}
          {mode !== "grid" && data?.can_export && (
            <details>
              <summary className="ed-link-button">
                <Download size={15} />
                Export
              </summary>
              <div className="ed-popover">
                <Button variant="ghost" onClick={() => void exportDeals("csv")}>
                  CSV
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => void exportDeals("xlsx")}
                >
                  Excel
                </Button>
              </div>
            </details>
          )}
        </div>
        <div className="ed-filters ed-quick-filters" role="group" aria-label="Quick deal filters">
            {[
              ["pipeline_id", "Pipeline", options.pipelines || []],
              ["stage_id", "Stage", stageOptions],
              ["owner_id", "Owner", options["deal-workspace/assignees"] || []],
            ].map(([key, title, choices]) => (
              <label key={String(key)}>
                {String(title)}
                <NativeSelect
                  aria-label={String(title)}
                  loading={lookupsLoading}
                  error={!!lookupsError}
                  value={String(filters[key as keyof Filters])}
                  onChange={(event) => {
                    change(key as keyof Filters, event.target.value);
                    if (key === "pipeline_id") change("stage_id", "");
                  }}
                >
                  <option value="">All</option>
                  {(choices as Row[]).map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name || item.full_name || item.email}
                    </option>
                  ))}
                </NativeSelect>
              </label>
            ))}
            {activeFilterCount > 0 && <button type="button" className="ed-text-button" onClick={clearDealFilters}>Clear filters ({activeFilterCount})</button>}
        </div>
        <details
          className="ed-filter-details"
          open={filtersOpen}
          onToggle={(event) => setFiltersOpen(event.currentTarget.open)}
        >
          <summary>Advanced filters{advancedFilterCount > 0 ? ` (${advancedFilterCount} active)` : ""}</summary>
          <div className="ed-filters">
            {[
              [
                "currency",
                [
                  ...new Set(
                    [
                      "INR",
                      "USD",
                      "EUR",
                      "GBP",
                      "AED",
                      filters.currency,
                      ...(summary?.currencies || []).map(
                        (row: Row) => row.currency,
                      ),
                    ].filter(Boolean),
                  ),
                ],
              ],
              ["status", ["Open", "Won", "Lost"]],
              ["priority", ["Low", "Medium", "High", "Critical"]],
              [
                "deal_type",
                [
                  "New Business",
                  "Existing Business",
                  "Renewal",
                  "Upsell",
                  "Cross-sell",
                ],
              ],
            ].map(([key, choices]) => (
              <label key={String(key)}>
                {label(String(key))}
                <NativeSelect
                  aria-label={label(String(key))}
                  value={String(filters[key as keyof Filters])}
                  onChange={(e) => change(key as keyof Filters, e.target.value)}
                >
                  <option value="">All</option>
                  {(choices as string[]).map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </NativeSelect>
              </label>
            ))}
            {["industry", "source"].map((key) => (
              <label key={key}>
                {label(key)}
                <input
                  aria-label={label(key)}
                  value={String(filters[key as keyof Filters])}
                  onChange={(e) => change(key as keyof Filters, e.target.value)}
                  type={key === "team_id" ? "number" : "text"}
                />
              </label>
            ))}
            <label>
              Sales team
              <NativeSelect
                aria-label="Sales team"
                loading={lookupsLoading}
                error={!!lookupsError}
                value={filters.team_id}
                onChange={(e) => change("team_id", e.target.value)}
              >
                <option value="">All permitted teams</option>
                {(options.teams || []).map((team) => (
                  <option key={team.id} value={team.id}>
                    {team.name}
                  </option>
                ))}
              </NativeSelect>
            </label>
            <label>
              Closing from
              <input
                aria-label="Closing from"
                type="date"
                value={filters.start}
                onChange={(e) => change("start", e.target.value)}
              />
            </label>
            <label>
              Closing through
              <input
                aria-label="Closing through"
                type="date"
                value={filters.end}
                onChange={(e) => change("end", e.target.value)}
              />
            </label>
            <label className="ed-checkbox">
              <input
                type="checkbox"
                checked={filters.no_next}
                onChange={(e) => change("no_next", e.target.checked)}
              />
              No next action
            </label>
            <button
              className="ed-text-button"
              onClick={clearDealFilters}
            >
              Clear
            </button>
          </div>
        </details>
        {filters.entered_stage_id && (
          <p className="ed-muted py-2">
            Recorded entry cohort:{" "}
            {lookup("pipeline-stages", filters.entered_stage_id)}
            <button
              className="ed-text-button"
              onClick={() => change("entered_stage_id", "")}
            >
              Clear cohort
            </button>
          </p>
        )}
        {filters.lost_reason && (
          <p className="ed-muted py-2">
            Loss reason: {filters.lost_reason}
            <button
              className="ed-text-button"
              onClick={() => change("lost_reason", "")}
            >
              Clear reason
            </button>
          </p>
        )}
        {mode !== "grid" && (
          <div className="ed-view-tools">
            <NativeSelect
              aria-label="Saved deal views"
              onChange={(e) => {
                const view = views[Number(e.target.value)];
                if (view) {
                  setFilters(view.filters);
                  setSearch(view.filters.search);
                  setMode(view.mode);
                }
              }}
              defaultValue=""
            >
              <option value="">My saved views</option>
              {views.map((view, index) => (
                <option key={index} value={index}>
                  {view.name}
                </option>
              ))}
            </NativeSelect>
            <Input
              aria-label="View name"
              placeholder="Name this view"
              value={viewName}
              onChange={(e) => setViewName(e.target.value)}
            />
            <Button
              variant="outline"
              size="sm"
              disabled={!viewName.trim()}
              onClick={() => {
                setViews((current) =>
                  [
                    ...current.filter((view) => view.name !== viewName.trim()),
                    { name: viewName.trim(), filters, mode },
                  ].slice(-50),
                );
                setViewName("");
              }}
            >
              Save view
            </Button>
          </div>
        )}
      </section>
      {selected.length > 0 && (
        <div className="ed-bulk">
          <strong>{selected.length} selected</strong>
          {data?.can_assign && (
            <NativeSelect
              aria-label="Bulk reassign deals"
              disabled={busy}
              defaultValue=""
              onChange={(e) => void bulk(e.target.value)}
            >
              <option value="">Reassign to...</option>
              {options["deal-workspace/assignees"]?.map((item) => (
                <option value={item.id} key={item.id}>
                  {item.name}
                </option>
              ))}
            </NativeSelect>
          )}
          <Button size="sm" variant="outline" onClick={() => setSelected([])}>
            Clear selection
          </Button>
          {data?.can_manage && (
            <NativeSelect
              aria-label="Bulk update deal stage"
              disabled={busy}
              value=""
              onChange={(e) => void bulk(e.target.value, "stage_id")}
            >
              <option value="">Move to stage...</option>
              {stageOptions.map((item) => (
                <option value={item.id} key={item.id}>
                  {item.name}
                </option>
              ))}
            </NativeSelect>
          )}
          {data?.can_archive && (
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => void archiveSelected()}
            >
              <Archive size={14} />
              {busy ? "Working…" : "Archive selected"}
            </Button>
          )}
          <span className="ed-muted">
            Each selected deal is validated separately. Failed updates remain
            selected.
          </span>
        </div>
      )}
      {loading && !data ? (
        <LoadingState label="Loading Deals" variant="table"/>
      ) : (
        <>
          {mode === "grid" && (
            <DealsDataGrid
              base={params}
              refreshKey={reload}
              initialQuery={gridQuery}
              queryState={gridReady ? gridQuery : undefined}
              selected={selected}
              onSelection={(records, ids) => {
                setSelectedRecords(records);
                setSelected(ids);
              }}
              onResult={(result) => {
                setData({
                  items: result.rows,
                  total: result.total,
                  page: result.page,
                  pages: Math.ceil(result.pageTotal / result.pageSize),
                  can_manage: result.permissions?.edit,
                  can_export: result.permissions?.export,
                  can_archive: result.permissions?.archive,
                  can_assign: result.permissions?.assign,
                });
                setSummary(result.context?.summary as Row);
                setLoading(false);
                setError("");
              }}
              onQueryChange={(value) => {
                setGridReady(true);
                setGridQuery(value);
                if (value.search !== filters.search) {
                  setSearch(value.search);
                  setFilters((current) => ({
                    ...current,
                    search: value.search,
                  }));
                }
              }}
              edit={(id) => setEditing(id)}
              move={(id) => setTransition({ id })}
              canManage={data?.can_manage}
              canArchive={data?.can_archive}
              owners={options["deal-workspace/assignees"] || []}
              clearFilters={clearDealFilters}
              removeFilter={(key) =>
                setFilters((current) => ({
                  ...current,
                  [key]: key === "no_next" ? false : "",
                }))
              }
              loadFilters={(context) => {
                const restored = Object.fromEntries(
                  Object.keys(empty).map((key) => [
                    key,
                    key === "no_next"
                      ? !!context[key]
                      : context[key] == null
                        ? ""
                        : String(context[key]),
                  ]),
                ) as Filters;
                setFilters(restored);
                setSearch(restored.search);
              }}
            />
          )}
          {dealLensModes.includes(mode) && <RecordLensViews scope={`crm-deals:${filters.pipeline_id || "all"}`} view={mode} records={rows.map(row => ({id:String(row.id),title:String(row.name || "Untitled deal"),subtitle:row.company_name || lookup("companies",row.company_id),status:row.stage_name || lookup("pipeline-stages",row.stage_id) || row.status,owner:row.owner_name || lookup("deal-workspace/assignees",row.owner_user_id),value:dealMoney(row.amount,row.currency),start:row.planning?.start_date || row.start_date,due:row.expected_close_date,updated:row.updated_at,color:stageOptions.find(stage => stage.id === row.stage_id)?.color,tags:[row.priority || "Medium",row.currency || ""]}))} onOpen={record => setLensPreview(record.id)}/>}
          {mode === "cards" && (
            <div className="ed-shared-cards">{rows.map(card)}</div>
          )}
          {mode === "kanban" && <PipelineBoard
            title={String(options.pipelines?.find(p=>String(p.id)===filters.pipeline_id)?.name||"Sales pipeline")} description="Build relationships, track every opportunity and keep the next conversation moving." label="Sales pipeline" viewState={filters} onApplyView={saved=>{const restored=Object.fromEntries(Object.keys(empty).map(key=>[key,key==="no_next"?!!saved[key]:String(saved[key]||"")])) as Filters;setFilters(restored);setSearch(restored.search);}} context={{module:"crm",scope:`pipeline:${filters.pipeline_id||"all"}`,kind:"deal"}} renderDetails={record=><PipelineDomainDetails module="crm" id={record.id}/>} onAdd={canCreate?stageId=>{setCaptureStage(Number(stageId));setCreate(true);}:undefined} reorder={false} disabled={loading}
            loading={loading && !data}
            notice={`Showing ${rows.length} of ${data?.total ?? rows.length} deals · page ${page}. Stage totals cover all matching deals.`}
            toolbar={<>{canCreate && <button type="button" className="pipeline-primary" onClick={() => {setCaptureStage(undefined);setCreate(true);}}><Plus size={14}/> Deal</button>}<PipelineSearch value={search} onChange={setSearch} placeholder="Search deals"/><div className="pipeline-toolbar-end"><select aria-label="Sort deals" value={`${gridQuery.sorting[0]?.id||"updated_at"}:${gridQuery.sorting[0]?.desc?"desc":"asc"}`} onChange={e=>{const [field,order]=e.target.value.split(":");setGridQuery(q=>({...q,sorting:[{id:field,desc:order==="desc"}]}));}}><option value="updated_at:desc">Sort: Recently updated</option><option value="next_follow_up_at:asc">Sort: Next activity</option><option value="amount:desc">Sort: Highest value</option><option value="name:asc">Sort: Name</option></select><button type="button" className="ed-link-button" aria-expanded={filtersOpen} onClick={()=>setFiltersOpen(v=>!v)}>Filter</button><select aria-label="Board pipeline" value={filters.pipeline_id} onChange={e=>setFilters(f=>({...f,pipeline_id:e.target.value,stage_id:""}))}><option value="">All pipelines</option>{(options.pipelines || []).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select><Link to="/crm/pipeline-settings" className="ed-link-button" aria-label="Customize pipeline"><Settings2 size={15}/></Link></div></>}
            stages={stageOptions.map(stage=>({id:String(stage.id),name:filters.pipeline_id?String(stage.name):`${options.pipelines?.find(p=>String(p.id)===String(stage.pipeline_id || stage.pipelineId))?.name || "Pipeline"} · ${stage.name}`,canAdd:!stage.is_won&&!stage.is_lost,color:stage.color,probability:stage.probability,wipLimit:stage.wip_limit,agingDays:stage.stagnation_days||14,count:(summary?.stages||[]).filter((t:Row)=>t.stage_id===stage.id).reduce((sum:number,t:Row)=>sum+t.count,0),summary:<>{(summary?.stages || []).filter((total:Row)=>total.stage_id===stage.id).map((total:Row)=><span key={total.currency}>{total.count} deals · {dealMoney(total.amount,total.currency)}</span>)}{!(summary?.stages || []).some((total:Row)=>total.stage_id===stage.id)&&<span>0 deals</span>}</>}))}
            records={rows.map(row=>({id:String(row.id),stageId:String(row.stage_id),title:String(row.name),priority:row.priority,description:row.description,subtitle:row.company_name||lookup("companies",row.company_id),value:dealMoney(row.amount,row.currency),owner:row.owner_name||lookup("deal-workspace/assignees",row.owner_user_id),ownerId:Number(row.owner_user_id)||undefined,nextActionAt:row.next_follow_up_at||undefined,isClosed:row.status==="Won"||row.status==="Lost",labelColor:stageOptions.find(s=>s.id===row.stage_id)?.color,activity:!row.next_follow_up_at?"missing":new Date(row.next_follow_up_at)<new Date()?"overdue":"scheduled",activityLabel:row.next_follow_up_at?`Next activity: ${new Date(row.next_follow_up_at).toLocaleString()}`:"No next activity"}))}
            onOpen={record=>navigate(`/crm/deals/${record.id}`)}
            onMove={data?.can_manage?({record,stageId})=>setTransition({id:Number(record.id),stage:Number(stageId)}):undefined}
            actions={data?.can_manage ? stageOptions.filter(s=>s.is_won||s.is_lost).map(s=>({id:String(s.id),label:s.is_won?"Won":"Lost",tone:s.is_won?"success" as const:"danger" as const,onAction:(record:{id:string})=>setTransition({id:Number(record.id),stage:Number(s.id)})})):[]}
          />}
          {mode === "list" && (
            <div className="ed-list">
              {rows.map((row) => (
                <details key={row.id}>
                  <summary>
                    <Link className="ed-deal-name" to={`/crm/deals/${row.id}`}>
                      {row.name}
                    </Link>
                    <strong>{dealMoney(row.amount, row.currency)}</strong>
                    <span>
                      {row.stage_name ||
                        lookup("pipeline-stages", row.stage_id)}
                    </span>
                    <span data-priority-badge data-priority={row.priority}>{row.priority || "Medium"}</span>
                  </summary>
                  {card(row)}
                </details>
              ))}
            </div>
          )}
          {mode === "forecast" && (
            <section className="ed-forecast">
              <h2>Revenue forecast</h2>
              <NativeSelect
                className="my-3 rounded border bg-background p-2 text-sm"
                aria-label="Forecast grouping"
                value={forecastGroup}
                onChange={(e) => setForecastGroup(e.target.value)}
              >
                {["month", "quarter", "owner", "stage", "pipeline"].map(
                  (group) => (
                    <option key={group} value={group}>
                      {label(group)}
                    </option>
                  ),
                )}
              </NativeSelect>
              <p className="ed-muted">
                All filtered open deals, grouped by the selected period or sales
                dimension, with currencies kept separate. Select a group to
                inspect its deals.
              </p>
              {forecastRows.map((row: Row) => (
                <button
                  disabled={row.month === "Unscheduled"}
                  title={
                    row.month === "Unscheduled"
                      ? "Set closing dates to drill into a forecast month"
                      : "View deals in this month"
                  }
                  key={`${row.month}-${row.currency}`}
                  onClick={() => {
                    if (
                      forecastGroup === "quarter" &&
                      row.month !== "Unscheduled"
                    ) {
                      const [year, quarter] = String(row.month)
                        .split("-Q")
                        .map(Number);
                      const first = (quarter - 1) * 3 + 1;
                      const last = quarter * 3;
                      setFilters((current) => ({
                        ...current,
                        currency: row.currency,
                        start: `${year}-${String(first).padStart(2, "0")}-01`,
                        end: `${year}-${String(last).padStart(2, "0")}-${new Date(year, last, 0).getDate()}`,
                      }));
                      setMode("grid");
                    } else if (forecastGroup !== "month") {
                      setFilters((current) => ({
                        ...current,
                        currency: row.currency,
                        [forecastGroup === "owner"
                          ? "owner_id"
                          : forecastGroup === "stage"
                            ? "stage_id"
                            : "pipeline_id"]: String(row.id || ""),
                      }));
                      setMode("grid");
                    } else if (row.month !== "Unscheduled") {
                      const [year, month] = row.month.split("-").map(Number);
                      setFilters((current) => ({
                        ...current,
                        currency: row.currency,
                        start: `${row.month}-01`,
                        end: `${row.month}-${new Date(year, month, 0).getDate()}`,
                      }));
                      setMode("grid");
                    }
                  }}
                >
                  <strong>
                    {row.month} · {row.currency}
                  </strong>
                  <span>{row.count} deals</span>
                  <span>{dealMoney(row.amount, row.currency)} pipeline</span>
                  <b>{dealMoney(row.weighted, row.currency)} weighted</b>
                  <meter
                    min={0}
                    max={Math.max(row.amount, 1)}
                    value={row.weighted}
                  />
                </button>
              ))}
            </section>
          )}
          {mode === "forecast" && summary?.analytics?.length > 0 && (
            <section className="ed-forecast mt-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2>Outcome & velocity analysis</h2>
              </div>
              {(summary?.analytics || []).map((row: Row) => (
                <div className="mt-4 rounded-xl border p-4" key={row.currency}>
                  <h3 className="mb-3 font-semibold">{row.currency}</h3>
                  <dl className="grid grid-cols-2 gap-4 text-sm lg:grid-cols-3">
                    {Object.entries({
                      "Won revenue": dealMoney(row.won_revenue, row.currency),
                      "Lost opportunity value": dealMoney(
                        row.lost_value,
                        row.currency,
                      ),
                      "Average deal size": dealMoney(
                        row.average_deal_size,
                        row.currency,
                      ),
                      "Win rate":
                        row.win_rate == null
                          ? "No closed outcomes"
                          : `${row.win_rate}%`,
                      "Average sales cycle":
                        row.sales_cycle_days == null
                          ? "No recorded closing dates"
                          : `${row.sales_cycle_days} days`,
                      "Estimated velocity / day":
                        row.velocity_per_day == null
                          ? "Insufficient closed history"
                          : dealMoney(row.velocity_per_day, row.currency),
                    }).map(([key, value]) => (
                      <div key={key}>
                        <dt className="ed-muted">{key}</dt>
                        <dd className="font-semibold">{value}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              ))}
            </section>
          )}
          {mode === "forecast" && (
            <DealAnalytics
              params={{ ...params, grid_state: JSON.stringify(gridQuery) }}
              drill={(values) => {
                setFilters((current) => ({ ...current, ...values }));
                setMode("grid");
              }}
            />
          )}
          {!rows.length && mode !== "forecast" && mode !== "grid" && mode !== "kanban" && (
            <div className="ed-empty">
              <h2>No deals match this view</h2>
              <p>Adjust the filters or capture a new opportunity.</p>
              {canCreate && (
                <Button onClick={() => setCreate(true)}>Create deal</Button>
              )}
            </div>
          )}
        </>
      )}
      {mode !== "grid" && (
        <footer className="ed-footer">
          <span>
            {data?.total || 0} matching deals · Page {page} of{" "}
            {data?.pages || 1}. Cards and groups show this page; statistics
            cover all filtered deals.
          </span>
          <div>
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1 || loading}
              onClick={() => setPage((v) => v - 1)}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= (data?.pages || 1) || loading}
              onClick={() => setPage((v) => v + 1)}
            >
              Next
            </Button>
          </div>
        </footer>
      )}
      <PipelineDrawer open={!!lensPreview} onClose={() => setLensPreview(undefined)} title={rows.find(row => String(row.id) === lensPreview)?.name || "Deal workspace"}>{lensPreview && <><Button asChild variant="outline"><Link className="ed-link-button" to={`/crm/deals/${lensPreview}`}>Open complete deal</Link></Button><PipelineDomainDetails module="crm" id={lensPreview} canEdit={!!data?.can_manage}/></>}</PipelineDrawer>
      <details className="ed-definitions">
        <summary>Calculation definitions</summary>
        {Object.entries(summary?.definitions || {}).map(([key, text]) => (
          <p key={key}>
            <strong>{label(key)}:</strong> {String(text)}
          </p>
        ))}
      </details>
      {(create || editing) && (
        <Suspense fallback={<LoadingState label="Preparing New Deal" variant="form"/>}>
          <Capture
            initialStageId={captureStage}
            initialPipelineId={Number(filters.pipeline_id)||undefined}
            dealId={editing}
            close={() => {
              setCreate(false);
              setEditing(undefined);
            }}
            saved={() => setReload((v) => v + 1)}
          />
        </Suspense>
      )}
      {transition && (
        <CRMStageDialog
          id={transition.id}
          targetStage={transition.stage}
          close={() => setTransition(undefined)}
          saved={() => setReload((v) => v + 1)}
        />
      )}
    </main>
  );
}

export default withRecordViewHost(EnterpriseDealsPage);
