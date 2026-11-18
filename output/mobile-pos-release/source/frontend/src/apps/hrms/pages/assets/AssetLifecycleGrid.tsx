import { useQuery } from "@tanstack/react-query";

import { api } from "@/services/api";

import { useAuthStore } from "@/store/authStore";

import { Fragment, useState, type ReactNode } from "react";

import {
  Search,
  Users,
  History,
  LogOut,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

import { Button } from "@/components/ui/button";

import { Input } from "@/components/ui/input";

import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";

import { Asset360Button, downloadAssetFile } from "./AssetWorkflows";

import { formatDate } from "@/lib/utils";

type Row = {
  id?: number;

  exit_id?: number;
  exit_status?: string;
  issues?: { kind: string }[];

  employee_name?: string;

  employee_id?: number;

  asset_id?: number;

  inspection_status?: string;

  recovery_status?: string;

  recovery_amount?: string;

  expected_return_date?: string | null;

  department?: string;

  return_details?: {
    received_by?: number;
    inspection?: { inspected_by?: number };
    missing_accessories?: string[];
    damage_description?: string;
  };

  asset_name?: string;

  asset_tag?: string;

  assigned_date?: string;

  returned_date?: string | null;

  condition_at_return?: string | null;

  acknowledged?: boolean;

  cleared?: boolean;

  last_working_date?: string | null;

  outstanding_assets?: {
    assignment_id: number;

    name: string;

    asset_tag: string;
  }[];
};

export default function AssetLifecycleGrid<T extends Row>({
  items,

  renderItem,

  scope,

  fields = [],

  source,
}: {
  items: T[];

  renderItem: (row: T) => ReactNode;

  scope: string;

  fields?: { id: string; label: string; value: (row: T) => string }[];

  gridClassName?: string;

  source?: "custody" | "history";
}) {
  const [group, setGroup] = useState("");

  const [search, setSearch] = useState(""),
    [status, setStatus] = useState(""),
    [page, setPage] = useState(0),
    [selected, setSelected] = useState<T | null>(null);

  const [descending, setDescending] = useState(true);
  const [fromDate, setFromDate] = useState(""),
    [toDate, setToDate] = useState(""),
    [department, setDepartment] = useState("");

  const uid = useAuthStore((s) => s.user?.id);

  const remote = useQuery({
    queryKey: [
      "asset-assignments",

      "paged",

      uid,

      source,

      search,

      status,

      page,

      group,

      fromDate,

      toDate,

      department,
      descending,
    ],

    enabled: !!source,

    queryFn: () =>
      api

        .get<{
          items: T[];

          total: number;

          summary: { label: string; value: number }[];
        }>("/assets/assignments", {
          params: {
            active: source === "custody",

            paged: true,

            search: search || undefined,

            status: status || undefined,

            group,

            from_date: fromDate || undefined,
            to_date: toDate || undefined,
            department: department || undefined,

            offset: page * 15,

            limit: 15,
          },
        })

        .then((r) => r.data),
  });

  const records = source ? remote.data?.items || [] : items;

  const exits = scope.includes("clearance"),
    returns = scope.includes("history") || records.some((r) => r.returned_date),
    label = exits ? "Exit case" : returns ? "Return record" : "Custody record";

  const state = (r: T) =>
    exits
      ? r.cleared
        ? "Assets cleared"
        : "Awaiting return"
      : r.returned_date &&
          r.inspection_status &&
          r.inspection_status !== "Not Required"
        ? r.inspection_status
        : r.returned_date
          ? r.condition_at_return === "Damaged" ||
            r.condition_at_return === "Poor"
            ? "Damaged return"
            : "Returned"
          : r.acknowledged
            ? "Acknowledged"
            : "Acknowledgment pending";

  const filtered = records.filter(
    (r) =>
      source ||
      ((!search ||
        [r.employee_name, r.employee_id, r.asset_name, r.asset_tag, r.exit_id]

          .join(" ")

          .toLowerCase()

          .includes(search.toLowerCase())) &&
        (!status || state(r) === status)),
  );

  const grouping = fields.find((f) => f.id === group);

  if (grouping)
    filtered.sort((a, b) => grouping.value(a).localeCompare(grouping.value(b)));

  const visible = source ? filtered : filtered.slice(page * 15, page * 15 + 15);

  const total = source ? remote.data?.total || 0 : filtered.length;

  const localStats = exits
    ? [
        ["Total exit requests", records.length],
        ["Pending clearance", records.filter((r) => !r.cleared).length],
        [
          "In progress",
          records.filter((r) => r.exit_status === "In Progress").length,
        ],
        [
          "Awaiting asset return",
          records.filter((r) => !!r.outstanding_assets?.length).length,
        ],
        [
          "Awaiting approval",
          records.filter((r) =>
            r.issues?.some(
              (i) =>
                i.kind === "Under Inspection" ||
                i.kind === "Outstanding Recovery",
            ),
          ).length,
        ],
        ["Assets cleared", records.filter((r) => r.cleared).length],
        [
          "Blocked / overdue",
          records.filter(
            (r) =>
              !r.cleared &&
              !!r.last_working_date &&
              r.last_working_date < new Date().toLocaleDateString("en-CA"),
          ).length,
        ],
      ]
    : returns
      ? [
          ["Total returns", records.length],

          [
            "Returned this month",

            records.filter(
              (r) =>
                r.returned_date?.slice(0, 7) ===
                new Date().toLocaleDateString("en-CA").slice(0, 7),
            ).length,
          ],

          [
            "Good condition",

            records.filter((r) =>
              ["Good", "New"].includes(r.condition_at_return || ""),
            ).length,
          ],

          [
            "Damaged / poor",

            records.filter((r) =>
              ["Damaged", "Poor"].includes(r.condition_at_return || ""),
            ).length,
          ],
        ]
      : [
          ["Assigned assets", records.length],

          [
            "Employees with assets",

            new Set(records.map((r) => r.employee_id)).size,
          ],

          ["Acknowledged", records.filter((r) => r.acknowledged).length],

          ["Pending handover", records.filter((r) => !r.acknowledged).length],
        ];

  const stats =
    source && remote.data
      ? remote.data.summary.map((s) => [s.label, s.value])
      : localStats;

  const Icon = exits ? LogOut : returns ? History : Users;

  return (
    <>
      <div className="asset-lifecycle-metrics">
        {stats.map(([name, count]) => (
          <div className="asset-metric" key={String(name)}>
            <span className="asset-symbol">
              <Icon size={20} />
            </span>

            <span>
              <small>{name}</small>

              <strong>{count}</strong>
            </span>
          </div>
        ))}
      </div>

      {exits && (
        <div className="asset-clearance-steps">
          {[
            "Existing employee exit",

            "Asset reconciliation",

            "Returns & condition",

            "Department approvals",

            "Offboarding completion",
          ].map((s, i) => (
            <span key={s}>
              <b>{i + 1}</b>

              {s}
            </span>
          ))}
        </div>
      )}

      <div className="asset-toolbar">
        <div className="asset-search">
          <Search size={17} />

          <Input
            aria-label={`Search ${label.toLowerCase()}s`}
            placeholder="Search employee, asset or reference…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);

              setPage(0);
            }}
          />
        </div>

        <select
          aria-label="Filter lifecycle status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);

            setPage(0);
          }}
        >
          <option value="">All statuses</option>

          {(source
            ? source === "custody"
              ? ["Acknowledged", "Acknowledgment pending", "Overdue"]
              : [
                  "Pending",

                  "Awaiting Approval",

                  "Approved",

                  "Rejected",

                  "Outstanding Recovery",
                ]
            : [...new Set(records.map(state))]
          ).map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>

        <select
          aria-label="Group lifecycle records"
          value={group}
          onChange={(e) => {
            setGroup(e.target.value);

            setPage(0);
          }}
        >
          <option value="">No grouping</option>

          {fields.map((f) => (
            <option key={f.id} value={f.id}>
              {f.label}
            </option>
          ))}
        </select>

        {source && (
          <>
            <select
              aria-label="Sort lifecycle records"
              value={descending ? "newest" : "oldest"}
              onChange={(e) => {
                setDescending(e.target.value === "newest");
                setPage(0);
              }}
            >
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
            </select>
            <Input
              aria-label="Filter department"
              placeholder="Department"
              value={department}
              onChange={(e) => {
                setDepartment(e.target.value);

                setPage(0);
              }}
            />

            <label className="asset-date-filter">
              From
              <Input
                aria-label="Register from date"
                type="date"
                value={fromDate}
                onChange={(e) => {
                  setFromDate(e.target.value);

                  setPage(0);
                }}
              />
            </label>

            <label className="asset-date-filter">
              To
              <Input
                aria-label="Register to date"
                type="date"
                value={toDate}
                onChange={(e) => {
                  setToDate(e.target.value);

                  setPage(0);
                }}
              />
            </label>
          </>
        )}

        {source && (
          <>
            <Button
              variant="outline"
              onClick={() =>
                downloadAssetFile(
                  "/assets/export?register=" +
                    source +
                    "&format=csv&search=" +
                    encodeURIComponent(search) +
                    "&status=" +
                    encodeURIComponent(status) +
                    "&department=" +
                    encodeURIComponent(department) +
                    "&from_date=" +
                    fromDate +
                    "&to_date=" +
                    toDate,

                  "asset-" + source + ".csv",
                ).catch(() => window.alert("Export failed"))
              }
            >
              Export CSV
            </Button>

            <Button
              variant="outline"
              onClick={() =>
                downloadAssetFile(
                  "/assets/export?register=" +
                    source +
                    "&format=xlsx&search=" +
                    encodeURIComponent(search) +
                    "&status=" +
                    encodeURIComponent(status) +
                    "&department=" +
                    encodeURIComponent(department) +
                    "&from_date=" +
                    fromDate +
                    "&to_date=" +
                    toDate,

                  "asset-" + source + ".xlsx",
                ).catch(() => window.alert("Export failed"))
              }
            >
              Excel
            </Button>
          </>
        )}
      </div>

      {source && remote.isError && (
        <p role="alert">
          Records could not load.{" "}
          <Button onClick={() => remote.refetch()}>Retry</Button>
        </p>
      )}

      {source && remote.isFetching && <p role="status">Loading records...</p>}

      <div className="asset-table-scroll">
        <table className="asset-table">
          <thead>
            <tr>
              {[
                label,

                "Employee",

                ...(exits
                  ? ["Last working day", "Outstanding assets"]
                  : [
                      "Asset",

                      "Assigned",

                      ...(returns
                        ? [
                            "Returned",
                            "Expected return",
                            "Condition",
                            "Received by",
                            "Inspected by",
                            "Missing accessories",
                            "Recovery",
                            "Damage remarks",
                          ]
                        : ["Expected return", "Handover"]),
                    ]),

                "Status",

                "Actions",
              ].map((s) => (
                <th key={s}>{s}</th>
              ))}
            </tr>
          </thead>

          <tbody>
            {visible.map((r, index) => (
              <Fragment key={r.id ?? r.exit_id}>
                {grouping &&
                  (index === 0 ||
                    grouping.value(r) !==
                      grouping.value(visible[index - 1])) && (
                    <tr>
                      <td colSpan={10} className="font-semibold bg-violet-50">
                        {grouping.label}: {grouping.value(r)}
                      </td>
                    </tr>
                  )}

                <tr>
                  <td>
                    {exits ? "EXIT" : returns ? "RET" : "HND"}-
                    {r.id ?? r.exit_id}
                  </td>

                  <td>
                    <button
                      className="asset-name"
                      onClick={() => setSelected(r)}
                    >
                      <span className="asset-employee-avatar">
                        {r.employee_name

                          ?.split(" ")

                          .map((s) => s[0])

                          .slice(0, 2)

                          .join("")}
                      </span>

                      <span>
                        <b>{r.employee_name}</b>
                        <small>{r.department}</small>

                        {r.employee_id && (
                          <small>Employee reference {r.employee_id}</small>
                        )}
                      </span>
                    </button>
                  </td>

                  {exits ? (
                    <>
                      <td>{formatDate(r.last_working_date ?? null)}</td>

                      <td>
                        {r.outstanding_assets?.length || 0} awaiting return
                      </td>
                    </>
                  ) : (
                    <>
                      <td>
                        {r.asset_id ? (
                          <Asset360Button
                            assetId={r.asset_id}
                            label={r.asset_name || r.asset_tag || "View asset"}
                          />
                        ) : (
                          <b>{r.asset_name}</b>
                        )}

                        <small>{r.asset_tag}</small>
                      </td>

                      <td>{formatDate(r.assigned_date ?? null)}</td>

                      {returns ? (
                        <>
                          <td>{formatDate(r.returned_date ?? null)}</td>

                          <td>{formatDate(r.expected_return_date ?? null)}</td>
                          <td>{r.condition_at_return || "Not recorded"}</td>
                          <td>
                            {r.return_details?.received_by || "Not recorded"}
                          </td>
                          <td>
                            {r.return_details?.inspection?.inspected_by ||
                              "Not recorded"}
                          </td>
                          <td>
                            {r.return_details?.missing_accessories?.join(
                              ", ",
                            ) || "None recorded"}
                          </td>
                          <td>
                            {r.recovery_amount || 0} ·{" "}
                            {r.recovery_status || "None"}
                          </td>
                          <td>
                            {r.return_details?.damage_description || "None"}
                          </td>
                        </>
                      ) : (
                        <>
                          <td>{formatDate(r.expected_return_date ?? null)}</td>

                          <td>
                            {r.acknowledged
                              ? "Signed & acknowledged"
                              : "Awaiting employee"}
                          </td>
                        </>
                      )}
                    </>
                  )}

                  <td>
                    <span
                      className={`asset-status ${r.cleared || r.acknowledged ? "good" : "warn"}`}
                    >
                      {state(r)}
                    </span>
                  </td>

                  <td>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setSelected(r)}
                    >
                      View details
                    </Button>
                  </td>
                </tr>
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {!filtered.length && (
        <div className="asset-empty">No records match these filters.</div>
      )}

      <footer className="asset-pagination">
        <span>
          {total} records · Page {page + 1}
        </span>

        <div>
          <Button
            aria-label="Previous records"
            variant="outline"
            disabled={!page}
            onClick={() => setPage(page - 1)}
          >
            <ChevronLeft size={16} />
          </Button>

          <Button
            aria-label="Next records"
            variant="outline"
            disabled={(page + 1) * 15 >= total}
            onClick={() => setPage(page + 1)}
          >
            <ChevronRight size={16} />
          </Button>
        </div>
      </footer>

      <Dialog
        open={!!selected}
        onOpenChange={(v) => {
          if (!v) setSelected(null);
        }}
      >
        <DialogContent className="asset-360">
          <DialogTitle>{label} details</DialogTitle>

          {selected &&
            renderItem(
              records.find(
                (r) =>
                  (r.id ?? r.exit_id) === (selected.id ?? selected.exit_id),
              ) || selected,
            )}

          {exits && (
            <p className="text-sm text-muted-foreground">
              Asset clearance covers company assets only. Department approvals
              and final exit completion are managed in the existing employee
              offboarding workflow.
            </p>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
