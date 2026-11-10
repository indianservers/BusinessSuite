import {
  Asset360Panel,
  AssetIntelligence,
  downloadAssetFile,
} from "./AssetWorkflows";

import { useEffect, useState } from "react";

import { useQuery } from "@tanstack/react-query";

import {
  Box,
  Laptop,
  Bike,
  Package,
  Search,
  Download,
  LayoutGrid,
  List,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
} from "lucide-react";

import { useAuthStore } from "@/store/authStore";

import { api, assetApi } from "@/services/api";

import { Button } from "@/components/ui/button";

import { Input } from "@/components/ui/input";

import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";

import GroupedRecords from "@/shared/data-grid/GroupedRecords";

import RecordMaintenance from "@/components/RecordMaintenance";

import { formatDate } from "@/lib/utils";

import "./assets-workspace.css";

type Asset = {
  id: number;

  name: string;

  asset_tag: string;

  assigned_employee?: string;

  serial_number?: string;

  category_id?: number;

  brand?: string;

  model?: string;

  status: string;

  condition?: string;

  location?: string;

  purchase_date?: string;

  purchase_cost?: number;

  warranty_expiry?: string;

  description?: string;
};

type Category = { id: number; name: string };

export type AssetSummary = {
  total: number;

  returned?: number;

  statuses: Record<string, number>;

  categories: { category_id: number | null; count: number }[];
};

export function AssetMetrics({
  summary,

  onFilter,
}: {
  summary?: AssetSummary;

  onFilter: (status: string) => void;
}) {
  return (
    <div className="asset-metrics">
      {[
        ["Total assets", "", summary?.total],

        ["Available", "Available", summary?.statuses.Available],

        ["Assigned", "Assigned", summary?.statuses.Assigned],

        ["Under repair", "Under Repair", summary?.statuses["Under Repair"]],

        ["Returned", "Returned", summary?.returned],

        [
          "Lost / damaged",

          "Lost / Damaged",

          summary
            ? (summary.statuses.Lost || 0) + (summary.statuses.Damaged || 0)
            : 0,
        ],

        [
          "Retired / disposed",

          "Retired / Disposed",

          summary
            ? (summary.statuses.Retired || 0) + (summary.statuses.Disposed || 0)
            : 0,
        ],
      ].map(([label, status, count], i) => (
        <button
          key={String(label)}
          onClick={() => onFilter(String(status))}
          className="asset-metric"
        >
          <span className={`asset-symbol tone-${i}`}>
            <Box size={21} />
          </span>

          <span>
            <small>{label}</small>

            <strong>{summary ? count || 0 : "—"}</strong>

            <em>
              {i === 0
                ? "Across your organization"
                : i === 1
                  ? "Ready for handover"
                  : i === 2
                    ? "In employee custody"
                    : i === 3
                      ? "Service & maintenance"
                      : "Lifecycle complete"}
            </em>
          </span>
        </button>
      ))}
    </div>
  );
}

export default function AssetWorkspace({
  categories,

  status,

  setStatus,

  canEdit,

  canDelete,

  summary,
}: {
  categories: Category[];

  status: string;

  setStatus: (v: string) => void;

  canEdit: boolean;

  canDelete: boolean;

  summary?: AssetSummary;
}) {
  const userId = useAuthStore((s) => s.user?.id);

  const [sort, setSort] = useState("created_at");

  const [search, setSearch] = useState(""),
    [category, setCategory] = useState(""),
    [page, setPage] = useState(0),
    [view, setView] = useState("table"),
    [selected, setSelected] = useState<Asset | null>(null);

  useEffect(() => setPage(0), [status, sort]);

  const rows = useQuery({
    queryKey: [
      "assets",

      "register",

      userId,

      search,

      status,

      category,

      page,

      sort,
    ],

    queryFn: () =>
      assetApi

        .list({
          search: search || undefined,

          status: status || undefined,

          category_id: category || undefined,

          offset: page * 25,

          limit: 25,

          sort,

          descending: sort === "created_at",
        })

        .then((r) => r.data as Asset[]),
  });

  const icon = (a: Asset) => {
    const name = categories.find((c) => c.id === a.category_id)?.name || "";

    const Icon = /bike|vehicle|car/i.test(name)
      ? Bike
      : /laptop|computer/i.test(name)
        ? Laptop
        : Package;

    return (
      <span className="asset-symbol">
        <Icon size={23} />
      </span>
    );
  };

  const exportRows = async () => {
    const all: Asset[] = [];

    for (let offset = 0; ; offset += 200) {
      const { data } = await assetApi.list({
        search: search || undefined,

        status: status || undefined,

        category_id: category || undefined,

        offset,

        limit: 200,
      });

      all.push(...data);

      if (data.length < 200) break;
    }

    const keys: (keyof Asset)[] = [
      "asset_tag",

      "name",

      "serial_number",

      "brand",

      "model",

      "status",

      "condition",

      "location",

      "purchase_date",

      "purchase_cost",

      "warranty_expiry",
    ];

    const escape = (v: unknown) =>
      '"' +
      String(v ?? "")
        .replace(/^[=+@-]/, "'$&")

        .replace(/"/g, '""') +
      '"';

    const url = URL.createObjectURL(
      new Blob(
        [
          "\uFEFF" +
            [
              keys.join(","),

              ...all.map((a) => keys.map((k) => escape(a[k])).join(",")),
            ].join("\r\n"),
        ],

        { type: "text/csv;charset=utf-8" },
      ),
    );

    const a = document.createElement("a");

    a.href = url;

    a.download = "company-assets.csv";

    a.click();

    URL.revokeObjectURL(url);
  };

  return (
    <div className="asset-register-layout">
      <section className="asset-panel">
        <div className="asset-panel-heading">
          <div className="flex items-center gap-3">
            <span className="asset-symbol">
              <Box />
            </span>

            <div>
              <h2>Inventory management</h2>

              <p>Your complete company asset register</p>
            </div>
          </div>

          <Button
            variant="outline"
            onClick={() =>
              void exportRows().catch(() =>
                window.alert("Export failed. Please retry."),
              )
            }
          >
            <Download size={15} /> Export CSV
          </Button>

          <Button
            variant="outline"
            onClick={() =>
              downloadAssetFile(
                "/assets/export?format=xlsx&register=inventory&search=" +
                  encodeURIComponent(search) +
                  "&status=" +
                  encodeURIComponent(status) +
                  (category ? "&category_id=" + category : ""),

                "company-assets.xlsx",
              ).catch(() => window.alert("Export failed. Please retry."))
            }
          >
            Excel
          </Button>
        </div>

        <div className="asset-toolbar">
          <div className="asset-search">
            <Search size={17} />

            <Input
              aria-label="Search asset register"
              placeholder="Search name, asset tag or serial number…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);

                setPage(0);
              }}
            />
          </div>

          <select
            aria-label="Filter category"
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);

              setPage(0);
            }}
          >
            <option value="">All categories</option>

            {categories.map((c) => (
              <option value={c.id} key={c.id}>
                {c.name}
              </option>
            ))}
          </select>

          <select
            aria-label="Filter status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);

              setPage(0);
            }}
          >
            <option value="">All statuses</option>

            {[
              "Available",

              "Assigned",

              "Pending Inspection",

              "Under Repair",

              "Lost",

              "Damaged",

              "Retired",

              "Disposed",

              "Returned",

              "Lost / Damaged",

              "Retired / Disposed",
            ].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>

          <select
            aria-label="Sort inventory"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            <option value="created_at">Newest first</option>

            <option value="name">Asset name</option>

            <option value="asset_tag">Asset tag</option>

            <option value="status">Status</option>

            <option value="purchase_cost">Purchase cost</option>

            <option value="warranty_expiry">Warranty expiry</option>
          </select>

          <Button
            aria-label="Table view"
            variant={view === "table" ? "default" : "outline"}
            onClick={() => setView("table")}
          >
            <List size={17} />
          </Button>

          <Button
            variant={view === "compact" ? "default" : "outline"}
            aria-label="Compact list view"
            onClick={() => setView("compact")}
          >
            <List size={14} />
          </Button>

          <Button
            aria-label="Card view"
            variant={view === "cards" ? "default" : "outline"}
            onClick={() => setView("cards")}
          >
            <LayoutGrid size={17} />
          </Button>
        </div>

        {rows.isPending ? (
          <div className="asset-loading" role="status">
            Loading your asset register…
          </div>
        ) : rows.isError ? (
          <div role="alert" className="asset-empty">
            Unable to load assets.{" "}
            <Button onClick={() => rows.refetch()}>Retry</Button>
          </div>
        ) : !rows.data?.length ? (
          <div className="asset-empty">
            <Package size={36} />

            <h3>No assets found</h3>

            <p>Register your first asset or adjust the filters.</p>
          </div>
        ) : view !== "cards" ? (
          <div className="asset-table-scroll">
            <table
              className={`asset-table ${view === "compact" ? "asset-table-compact" : ""}`}
            >
              <thead>
                <tr>
                  {[
                    "Asset / tag",

                    "Category",

                    "Brand / model",

                    "Serial / registration",

                    "Location",

                    "Condition",

                    "Status",

                    "Assigned employee",

                    "Purchase",

                    "Warranty",

                    "Actions",
                  ].map((s) => (
                    <th key={s}>{s}</th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {rows.data.map((a) => (
                  <tr key={a.id}>
                    <td>
                      <button
                        className="asset-name"
                        onClick={() => setSelected(a)}
                      >
                        {icon(a)}

                        <span>
                          <b>{a.name}</b>

                          <small>{a.asset_tag}</small>
                        </span>
                      </button>
                    </td>

                    <td>
                      {categories.find((c) => c.id === a.category_id)?.name ||
                        "Uncategorized"}
                    </td>

                    <td>
                      {[a.brand, a.model].filter(Boolean).join(" · ") || "—"}
                    </td>

                    <td>{a.serial_number || "—"}</td>

                    <td>{a.location || "—"}</td>

                    <td>{a.condition || "—"}</td>

                    <td>
                      <span
                        className={`asset-status ${a.status === "Available" ? "good" : a.status === "Under Repair" ? "warn" : ""}`}
                      >
                        {a.status}
                      </span>
                    </td>

                    <td>{a.assigned_employee || "Not assigned"}</td>

                    <td>
                      {a.purchase_cost == null
                        ? "—"
                        : Number(a.purchase_cost).toLocaleString()}

                      <small>{formatDate(a.purchase_date ?? null)}</small>
                    </td>

                    <td>{formatDate(a.warranty_expiry ?? null)}</td>

                    <td>
                      <RecordMaintenance
                        record={a as unknown as Record<string, unknown>}
                        name={a.name}
                        endpoint={`/assets/${a.id}`}
                        fields={[
                          { key: "name", label: "Asset name", required: true },

                          { key: "serial_number", label: "Serial number" },
                        ]}
                        queryKeys={[
                          "assets",

                          "assets-available",

                          "asset-summary",
                        ]}
                        canEdit={canEdit}
                        canDelete={canDelete}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <GroupedRecords
            scope="hrms-assets"
            items={rows.data}
            fields={[
              { id: "status", label: "Status", value: (a) => a.status },

              {
                id: "category",

                label: "Category",

                value: (a) =>
                  categories.find((c) => c.id === a.category_id)?.name ||
                  "Uncategorized",
              },
            ]}
            gridClassName="asset-card-grid"
            renderItem={(a) => (
              <button
                className="asset-item-card"
                key={a.id}
                onClick={() => setSelected(a)}
              >
                {icon(a)}

                <b>{a.name}</b>

                <small>{a.asset_tag}</small>

                <span className="asset-status">{a.status}</span>
              </button>
            )}
          />
        )}

        <footer className="asset-pagination">
          <span>
            Page {page + 1} · {rows.data?.length || 0} records
          </span>

          <div>
            <Button
              aria-label="Previous page"
              variant="outline"
              disabled={!page}
              onClick={() => setPage(page - 1)}
            >
              <ChevronLeft size={16} />
            </Button>

            <Button
              aria-label="Next page"
              variant="outline"
              disabled={(rows.data?.length || 0) < 25}
              onClick={() => setPage(page + 1)}
            >
              <ChevronRight size={16} />
            </Button>
          </div>
        </footer>
      </section>

      <aside className="asset-insights">
        <section className="asset-panel">
          <h2>Inventory insights</h2>

          <p>Category distribution · all assets</p>

          <div className="asset-total">
            <Box size={25} />

            <strong>{summary?.total ?? "—"}</strong>

            <small>Company assets</small>
          </div>

          {summary?.categories.map((c, i) => (
            <div className="asset-distribution" key={c.category_id ?? "none"}>
              <div>
                <span>
                  {categories.find((k) => k.id === c.category_id)?.name ||
                    "Uncategorized"}
                </span>

                <b>{c.count}</b>
              </div>

              <div className="asset-bar">
                <span
                  style={{
                    width: `${summary.total ? (100 * c.count) / summary.total : 0}%`,

                    background: ["#7c3aed", "#6366f1", "#38bdf8", "#34d399"][
                      i % 4
                    ],
                  }}
                />
              </div>
            </div>
          ))}
        </section>

        <section className="asset-panel">
          <AssetIntelligence />
        </section>

        <section className="asset-panel">
          <ShieldCheck className="text-violet-600" />

          <h2>Connected lifecycle</h2>

          <p>Register → assign → acknowledge → return → repair or release.</p>

          <p>
            Employee exit approval remains governed by your existing offboarding
            process.
          </p>
        </section>
      </aside>

      <Dialog
        open={!!selected}
        onOpenChange={(v) => {
          if (!v) setSelected(null);
        }}
      >
        <DialogContent className="asset-360">
          <DialogTitle>Asset 360°</DialogTitle>

          {selected && (
            <Asset360Panel assetId={selected.id} canManage={canEdit} />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
