import { useCallback, useMemo, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  Archive,
  BadgeDollarSign,
  BriefcaseBusiness,
  CalendarDays,
  Flag,
  FolderKanban,
  Gauge,
  Mail,
  Pencil,
  SquareArrowOutUpRight,
  Users,
  Workflow,
} from "lucide-react";
import { api } from "@/services/api";
import SharedDataGrid from "@/shared/data-grid/SharedDataGrid";
import type {
  GridColumn,
  GridDataSource,
  GridQuery,
  GridResult,
} from "@/shared/data-grid/types";
import { emptyQuery } from "@/shared/data-grid/types";
import { dealMoney, label } from "./deal-utils";

type Deal = Record<string, any>;
export function dealGridSource(
  base: Record<string, unknown>,
): GridDataSource<Deal> {
  const baseJson = JSON.stringify(base);
  return {
    key: `crm-deals:${baseJson}`,
    personalIdentity: "id",
    load: async (query, signal) =>
      (
        await api.get<GridResult<Deal>>("/crm/deal-workspace/grid/query", {
          params: { state: JSON.stringify(query), base: baseJson },
          signal,
          progress: false,
        })
      ).data,
    facets: async (field, search, query, signal) =>
      (
        await api.get("/crm/deal-workspace/grid/facets", {
          params: {
            field,
            search,
            state: JSON.stringify(query),
            base: baseJson,
          },
          signal,
          progress: false,
        })
      ).data,
    export: async (request) =>
      (
        await api.get("/crm/deal-workspace/grid/export", {
          params: {
            format: request.format,
            scope: request.scope,
            ids: JSON.stringify(request.ids.map(Number)),
            columns: JSON.stringify(request.columns),
            include_groups: request.includeGroups,
            include_summaries: request.includeSummaries,
            state: JSON.stringify(request.query),
            base: baseJson,
          },
          responseType: request.format === "clipboard" ? "text" : "blob",
        })
      ).data,
  };
}
export default function DealsDataGrid({
  base,
  refreshKey,
  initialQuery,
  queryState,
  selected,
  onSelection,
  onResult,
  onQueryChange,
  edit,
  move,
  canManage,
  canArchive,
  owners,
  clearFilters,
  removeFilter,
  loadFilters,
  savedViewsHost,
  savedViewsExtra,
  active = true,
}: {
  base: Record<string, unknown>;
  refreshKey: number;
  initialQuery?: Partial<GridQuery>;
  queryState?: GridQuery;
  selected: number[];
  onSelection: (rows: Deal[], ids: number[]) => void;
  onResult: (result: GridResult<Deal>) => void;
  onQueryChange: (query: GridQuery) => void;
  edit: (id: number) => void;
  move: (id: number) => void;
  canManage?: boolean;
  canArchive?: boolean;
  owners: Deal[];
  clearFilters?: () => void;
  removeFilter?: (id: string) => void;
  loadFilters?: (context: Record<string, unknown>) => void;
  savedViewsHost?: HTMLElement | null;
  savedViewsExtra?: ReactNode;
  active?: boolean;
}) {
  const navigate = useNavigate(),
    [searchParams] = useSearchParams();
  const source = useMemo(() => dealGridSource(base), [JSON.stringify(base)]);
  const columns = useMemo<GridColumn<Deal>[]>(
    () => [
      {
        id: "name",
        title: "Deal name",
        icon: BriefcaseBusiness,
        width: 260,
        minWidth: 150,
        groupable: false,
        editable: true,
        validate: (value) =>
          !value.trim()
            ? "Enter a deal name."
            : value.length > 180
              ? "Use at most 180 characters."
              : undefined,
        render: (row) => (
          <Link to={`/crm/deals/${row.id}`} title={row.name}>
            {row.name}
          </Link>
        ),
      },
      {
        id: "company_id",
        title: "Company",
        icon: BriefcaseBusiness,
        width: 185,
        type: "category",
        accessor: (r) => r.company_name || r.company_id || "—",
        render: (r) => (
          <span title={r.company_name}>{r.company_name || "Not linked"}</span>
        ),
      },
      {
        id: "amount",
        title: "Deal value",
        icon: BadgeDollarSign,
        type: "currency",
        width: 155,
        groupable: false,
        editable: (r) => !r.has_catalog_items && !r.catalog_items?.length,
        editor: "number",
        validate: (v) =>
          !Number.isFinite(Number(v)) || Number(v) < 0
            ? "Enter a nonnegative amount."
            : undefined,
        render: (r) => dealMoney(r.amount, r.currency),
        exportValue: (r) => `${r.currency} ${Number(r.amount || 0).toFixed(2)}`,
      },
      { id: "currency", title: "Currency", type: "category", width: 100 },
      {
        id: "pipeline_id",
        title: "Pipeline",
        icon: FolderKanban,
        type: "category",
        width: 170,
        accessor: (r) => r.pipeline_name || r.pipeline_id || "—",
      },
      {
        id: "stage_id",
        title: "Stage",
        icon: Workflow,
        type: "status",
        width: 175,
        accessor: (r) => r.stage_name || r.stage_id,
        render: (r) => (
          <span
            className="udg-badge"
            style={{
              color: r.stage_color || "#6366f1",
              background: `${r.stage_color || "#6366f1"}12`,
            }}
          >
            <i />
            {r.stage_name || "Not set"}
          </span>
        ),
      },
      {
        id: "probability",
        title: "Probability",
        icon: Gauge,
        type: "number",
        width: 155,
        groupable: false,
        render: (r) => (
          <span className="udg-probability">
            <span>
              <i
                style={{
                  width: `${Math.min(100, Math.max(0, Number(r.probability) || 0))}%`,
                }}
              />
            </span>
            <b>{r.probability || 0}%</b>
          </span>
        ),
      },
      {
        id: "weighted",
        title: "Weighted value",
        type: "currency",
        width: 155,
        groupable: false,
        render: (r) => dealMoney(r.weighted, r.currency),
      },
      {
        id: "owner_user_id",
        title: "Owner",
        icon: Users,
        type: "owner",
        width: 210,
        accessor: (r) => r.owner_name || r.owner_user_id || "Unassigned",
        render: (r) => (
          <span className="udg-owner">
            <span className="udg-avatar">
              {String(r.owner_name || "?")
                .split(/[\s@.]/)
                .slice(0, 2)
                .map((p: string) => p[0])
                .join("")
                .toUpperCase()}
            </span>
            <span title={r.owner_name}>{r.owner_name || "Unassigned"}</span>
          </span>
        ),
      },
      {
        id: "expected_close_date",
        title: "Expected close",
        icon: CalendarDays,
        type: "date",
        width: 150,
        editable: true,
        editor: "date",
        render: (r) =>
          r.expected_close_date
            ? new Date(
                `${String(r.expected_close_date).slice(0, 10)}T12:00:00`,
              ).toLocaleDateString()
            : "Unscheduled",
      },
      {
        id: "priority",
        title: "Priority",
        icon: Flag,
        type: "status",
        width: 125,
        editable: true,
        editor: "select",
        options: ["Low", "Medium", "High", "Critical"].map((value) => ({
          value,
          label: value,
        })),
        render: (r) => (
          <span data-priority-badge data-priority={r.priority || "Medium"}
            className={`udg-priority ${String(r.priority || "Medium").toLowerCase()}`}
          >
            <i />
            {r.priority || "Medium"}
          </span>
        ),
      },
      {
        id: "status",
        title: "Status",
        type: "status",
        width: 110,
        render: (r) => (
          <span
            className="udg-badge"
            style={{
              color:
                r.status === "Won"
                  ? "#059669"
                  : r.status === "Lost"
                    ? "#dc2626"
                    : "#6366f1",
            }}
          >
            <i />
            {r.status}
          </span>
        ),
      },
      {
        id: "next_follow_up_at",
        title: "Next action",
        icon: CalendarDays,
        type: "datetime",
        width: 175,
        groupable: false,
        editable: true,
        editor: "datetime-local",
        render: (r) =>
          r.next_follow_up_at
            ? new Date(r.next_follow_up_at).toLocaleString(undefined, {
                dateStyle: "medium",
                timeStyle: "short",
              })
            : "Not scheduled",
      },
      {
        id: "created_at",
        title: "Created",
        type: "datetime",
        width: 160,
        groupable: false,
        render: (r) =>
          r.created_at ? new Date(r.created_at).toLocaleDateString() : "—",
      },
      {
        id: "updated_at",
        title: "Updated",
        type: "datetime",
        width: 160,
        groupable: false,
        render: (r) =>
          r.updated_at ? new Date(r.updated_at).toLocaleDateString() : "—",
      },
      { id: "deal_type", title: "Deal type", type: "category", width: 155 },
      { id: "source", title: "Source", type: "category", width: 140 },
    ],
    [],
  );
  const getId = useCallback((row: Deal) => String(row.id), []);
  const selectedIds = useMemo(() => selected.map(String), [selected]);
  return (
    <SharedDataGrid<Deal>
      compactControls
      savedViewsHost={savedViewsHost}
      savedViewsExtra={savedViewsExtra}
      savedViewsLabel="Saved views"
      savedViewsTitle="Personal table views"
      hideViewControls={!active}
      workspaceId={
        searchParams.get("workspaceId") ||
        searchParams.get("workspace_id") ||
        undefined
      }
      gridId="crm-deals"
      title="Deals data grid"
      columns={columns}
      dataSource={source}
      getRowId={getId}
      queryState={queryState}
      initialQuery={{
        ...emptyQuery(),
        sorting: [{ id: "updated_at", desc: true }],
        ...initialQuery,
      }}
      initialLayout={{
        pinning: { left: ["name"], right: [] },
        visibility: {
          created_at: false,
          updated_at: false,
          deal_type: false,
          source: false,
        },
        rowHeight: 42,
      }}
      refreshKey={refreshKey}
      viewContext={base}
      onViewContextChange={loadFilters}
      onClearFilters={clearFilters}
      externalFilters={Object.entries(base)
        .filter(([key]) => key !== "search")
        .map(([id, value]) => ({
          id,
          label: `${label(id)}: ${String(value)}`,
          clear: () => removeFilter?.(id),
        }))}
      selectedIds={selectedIds}
      onSelectionChange={(rows, ids) => onSelection(rows, ids.map(Number))}
      onQueryChange={onQueryChange}
      onResult={onResult}
      onOpen={(row) => navigate(`/crm/deals/${row.id}`)}
      onEdit={async (row, column, value) => {
        let typed: string | number | null = value;
        if (column === "amount") typed = Number(value);
        if (column === "expected_close_date") typed = value || null;
        if (column === "next_follow_up_at")
          typed = value ? new Date(value).toISOString() : null;
        await api.patch(`/crm/deals/${row.id}`, {
          [column]: typed,
          expected_version: row.version,
        });
        window.dispatchEvent(new Event("crm:records-changed"));
      }}
      rowActions={[
        {
          id: "open",
          label: "Open deal",
          icon: SquareArrowOutUpRight,
          run: (row) => navigate(`/crm/deals/${row.id}`),
        },
        {
          id: "edit",
          label: "Edit deal",
          icon: Pencil,
          quick: true,
          visible: () => !!canManage,
          run: (row) => edit(row.id),
        },
        {
          id: "move",
          label: "Move stage",
          icon: Workflow,
          quick: true,
          visible: () => !!canManage,
          run: (row) => move(row.id),
        },
        {
          id: "archive",
          label: "Archive deal",
          icon: Archive,
          danger: true,
          visible: () => !!canArchive,
          run: async (row) => {
            if (!window.confirm(`Archive “${row.name}”?`)) return;
            await api.delete(`/crm/deals/${row.id}`);
            window.dispatchEvent(new Event("crm:records-changed"));
          },
        },
      ]}
      defaultExportColumns={[
        "name",
        "company_id",
        "amount",
        "currency",
        "pipeline_id",
        "stage_id",
        "probability",
        "weighted",
        "owner_user_id",
        "expected_close_date",
        "priority",
        "status",
      ]}
    />
  );
}
