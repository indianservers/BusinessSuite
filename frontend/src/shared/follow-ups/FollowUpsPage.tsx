import { NativeSelect } from "@/components/ui/native-select";
import MobileFollowUpQueue from "@/components/mobile/MobileFollowUpQueue";
import { useMobileSessionState } from "@/components/mobile/useMobileSessionState";
import { MobileFilters } from "@/components/mobile/MobilePrimitives";
import CompactForm from "@/components/forms/CompactForm";
import FollowUpGrid from "./FollowUpGrid";
import { useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays,
  CheckCircle2,
  Clock,
  Plus,
  Download,
  Phone,
  MessageCircle,
} from "lucide-react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  ScheduleFields,
  defaultSchedule,
  type Schedule,
} from "./ScheduleFields";
import { toast } from "@/hooks/use-toast";
type Row = {
  id: number;
  title: string;
  customer_id: number;
  customer_name: string;
  phone?: string;
  product_id?: number;
  order_id?: number;
  due_at: string;
  timezone: string;
  status: string;
  priority: string;
  assigned_to: string;
  assigned_user_id: number;
  configuration: Schedule;
  links?: Record<string, number>;
  activities?: {
    id: number;
    action: string;
    actor_id: number;
    actor_name?: string;
    created_at: string;
    details: Record<string, unknown>;
  }[];
};
const load = (url: string, params = {}) =>
  api.get(url, { params }).then((r) => r.data);
export default function FollowUpsPage() {
  const { id } = useParams();
  const location = useLocation();
  const base = location.pathname.startsWith("/srm")
    ? "/srm/follow-ups"
    : "/crm/follow-ups";
  const view = id
    ? "detail"
    : location.pathname.endsWith("calendar")
      ? "calendar"
      : location.pathname.endsWith("directory")
        ? "directory"
        : "dashboard";
  const cache = useQueryClient();
  const [search, setSearch] = useMobileSessionState(`${base}:search`, "");
  const [status, setStatus] = useMobileSessionState(`${base}:status`, "");
  const [assigned, setAssigned] = useMobileSessionState(`${base}:assigned`, "");
  const [page, setPage] = useMobileSessionState(`${base}:page`, 1);
  const [creating, setCreating] = useState(
    new URLSearchParams(location.search).has("new"),
  );
  const [schedule, setSchedule] = useState<Schedule>({
    ...defaultSchedule,
    required: true,
  });
  const [customer, setCustomer] = useState(
    new URLSearchParams(location.search).get("customer") || "",
  );
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [reschedule, setReschedule] = useState("");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const [calendarMode, setCalendarMode] = useState("Month");
  const [anchor, setAnchor] = useState(new Date().toISOString().slice(0, 10));
  const [sort, setSort] = useState("due_at");
  const [group, setGroup] = useState("");
  const [sourceType, setSourceType] = useState("deals");
  const [sourceId, setSourceId] = useState(
    new URLSearchParams(location.search).get("deal") || "",
  );
  const [sourceSearch, setSourceSearch] = useState("");
  const linkedOptions = useQuery({
    queryKey: ["follow-up-links", sourceType, sourceSearch],
    queryFn: () =>
      load(`/follow-ups/link-options/${sourceType}`, { search: sourceSearch }),
    enabled: creating,
  });
  const [productSearch, setProductSearch] = useState("");
  const [productId, setProductId] = useState("");
  const products = useQuery({
    queryKey: ["follow-up-catalogue", productSearch, base],
    queryFn: () =>
      load("/catalog/items", {
        source: base.startsWith("/srm") ? "srm" : "crm",
        search: productSearch,
        status: "Active",
        per_page: 100,
      }),
    enabled: creating,
  });
  const options = useQuery({
    queryKey: ["follow-up-options"],
    queryFn: () => load("/follow-ups/options"),
  });
  const query = useQuery({
    queryKey: ["follow-ups", search, status, assigned, page],
    queryFn: () =>
      load("/follow-ups", {
        search,
        status,
        assigned_user_id: assigned || undefined,
        customer_id:
          new URLSearchParams(location.search).get("customer") || undefined,
        page,
        per_page: 100,
      }),
    refetchInterval: 60000,
  });
  const stats = useQuery({
    queryKey: ["follow-ups", "statistics"],
    queryFn: () => load("/follow-ups/statistics"),
    refetchInterval: 60000,
  });
  const preferences = useQuery({
    queryKey: ["follow-up-preferences"],
    queryFn: () => load("/follow-ups/preferences/me"),
  });
  const attachments = useQuery({
    queryKey: ["follow-up-attachments", id],
    queryFn: () => load(`/follow-ups/${id}/attachments`),
    enabled: !!id,
  });
  const detail = useQuery<Row>({
    queryKey: ["follow-ups", id],
    queryFn: () => load(`/follow-ups/${id}`),
    enabled: !!id,
  });
  const refresh = () => cache.invalidateQueries({ queryKey: ["follow-ups"] });
  const run = async (work: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await work();
      await refresh();
      toast({ title: "Follow-up saved" });
    } catch (e: any) {
      toast({
        title: "Could not save follow-up",
        description:
          typeof e.response?.data?.detail === "string"
            ? e.response.data.detail
            : "Check required fields and permissions.",
        variant: "destructive",
      });
    } finally {
      setBusy(false);
    }
  };
  const action = (ident: number, action: string, extra = {}) =>
    api.post(`/follow-ups/${ident}/actions`, {
      action,
      notes: notes || `${action} from follow-up workspace`,
      ...extra,
    });
  const rows: Row[] = [...(query.data?.items || [])].sort((a, b) =>
    String(a[sort as keyof Row] || "").localeCompare(
      String(b[sort as keyof Row] || ""),
    ),
  );
  function exportRows() {
    const keys = [
      "id",
      "customer_name",
      "title",
      "due_at",
      "assigned_to",
      "priority",
      "status",
      "order_id",
    ];
    const csv = [
      keys.join(","),
      ...rows.map((r) =>
        keys
          .map(
            (k) =>
              '"' +
              String(r[k as keyof Row] ?? "")
                .replace(/"/g, '""')
                .replace(/^[=+@-]/, "'$&") +
              '"',
          )
          .join(","),
      ),
    ].join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "follow-ups-page.csv";
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <div className="min-w-0 space-y-4 p-2 md:p-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <CalendarDays className="h-5 w-5 text-primary" />
            Customer follow-ups
          </h1>
          <p className="text-sm text-muted-foreground">
            Service care, renewals and customer commitments · shared across CRM
            and Sales
          </p>
        </div>
        <Button onClick={() => setCreating((v) => !v)}>
          <Plus className="mr-2 h-4 w-4" />
          Schedule follow-up
        </Button>
      </header>
      <nav className="flex flex-wrap gap-2">
        {[
          ["Dashboard", base],
          ["Directory", base + "/directory"],
          ["Calendar", base + "/calendar"],
        ].map(([label, path]) => (
          <Button key={path} asChild variant="outline" size="sm">
            <Link to={path}>{label}</Link>
          </Button>
        ))}
      </nav>
      <details className="rounded border bg-card p-3 text-sm">
        <summary className="cursor-pointer">My reminder preferences</summary>
        {preferences.data &&
          ["in_app", "overdue"].map((key) => (
            <label
              key={key}
              className="mr-5 inline-flex items-center gap-2 py-2"
            >
              <input
                type="checkbox"
                checked={preferences.data[key]}
                onChange={(e) => {
                  void run(async () => {
                    await api.put("/follow-ups/preferences/me", {
                      ...preferences.data,
                      [key]: e.target.checked,
                    });
                    await cache.invalidateQueries({
                      queryKey: ["follow-up-preferences"],
                    });
                  });
                }}
              />
              {key === "in_app"
                ? "In-app reminders"
                : "Overdue escalation alerts"}
            </label>
          ))}
      </details>
      {creating && (
        <CompactForm
          className="space-y-3 rounded-xl border bg-card p-4"
          onSubmit={(e) => {
            e.preventDefault();
            void run(async () => {
              await api.post("/follow-ups", {
                ...schedule,
                customer_id: Number(customer),
                product_id: Number(productId) || undefined,
                title,
                ...(sourceId
                  ? {
                      [sourceType === "leads"
                        ? "lead_id"
                        : sourceType === "contacts"
                          ? "contact_id"
                          : sourceType === "quotations"
                            ? "quotation_id"
                            : "deal_id"]: Number(sourceId),
                    }
                  : {}),
              });
              setCreating(false);
            });
          }}
        >
          <h2 className="font-semibold">New customer commitment</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-xs">
              Customer
              <NativeSelect loading={options.isFetching} error={options.isError}
                required
                className="block w-full rounded border bg-background p-2"
                value={customer}
                onChange={(e) => setCustomer(e.target.value)}
              >
                <option value="">Choose customer</option>
                {options.data?.customers.map((c: any) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </NativeSelect>
            </label>
            <label className="text-xs">
              Purpose / next action
              <Input
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </label>
          </div>
          <details className="rounded border p-3">
            <summary className="cursor-pointer text-sm">
              Link a lead, contact, deal or quotation
            </summary>
            <div className="mt-2 grid gap-2 sm:grid-cols-3">
              <NativeSelect
                aria-label="Linked record type"
                className="rounded border bg-background p-2"
                value={sourceType}
                onChange={(e) => {
                  setSourceType(e.target.value);
                  setSourceId("");
                }}
              >
                {["leads", "contacts", "deals", "quotations"].map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </NativeSelect>
              <Input
                aria-label="Search linked record"
                placeholder="Search permitted records"
                value={sourceSearch}
                onChange={(e) => setSourceSearch(e.target.value)}
              />
              <NativeSelect loading={linkedOptions.isFetching} error={linkedOptions.isError}
                aria-label="Linked record"
                className="rounded border bg-background p-2"
                value={sourceId}
                onChange={(e) => setSourceId(e.target.value)}
              >
                <option value="">No linked record</option>
                {linkedOptions.data?.map((r: { id: number; name: string }) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </NativeSelect>
            </div>
          </details>
          <div className="grid gap-2 sm:grid-cols-2">
            <Input
              aria-label="Search linked catalogue"
              placeholder="Search products or services"
              value={productSearch}
              onChange={(e) => setProductSearch(e.target.value)}
            />
            <NativeSelect loading={products.isFetching} error={products.isError}
              aria-label="Linked product or service"
              className="rounded border bg-background p-2 text-sm"
              value={productId}
              onChange={(e) => {
                setProductId(e.target.value);
                const product = products.data?.items.find(
                  (p: { id: number }) => p.id === Number(e.target.value),
                );
                if (product) {
                  if (!title) setTitle(product.name);
                  if (product.follow_up)
                    setSchedule({ ...product.follow_up, required: true });
                }
              }}
            >
              <option value="">No linked catalogue item</option>
              {products.data?.items.map(
                (p: { id: number; name: string; kind: string }) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.kind})
                  </option>
                ),
              )}
            </NativeSelect>
          </div>
          <ScheduleFields
            value={schedule}
            onChange={setSchedule}
            employees={options.data?.employees}
            teams={options.data?.teams}
          />
          <Button disabled={busy || !schedule.required}>Save follow-up</Button>
        </CompactForm>
      )}
      {(query.isError || detail.isError || stats.isError) && (
        <p role="alert" className="rounded border border-red-300 p-3">
          Unable to load follow-ups. Check your connection or access
          permissions.{" "}
          <button className="underline" onClick={() => void refresh()}>
            Retry
          </button>
        </p>
      )}
      {view === "detail" && detail.data && (
        <section className="space-y-4 rounded-xl border bg-card p-4">
          <h2 className="text-lg font-semibold">{detail.data.title}</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            {Object.entries({
              Customer: detail.data.customer_name,
              Due: new Date(detail.data.due_at).toLocaleString(),
              "Time zone": detail.data.timezone,
              Status: detail.data.status,
              Priority: detail.data.priority,
              "Assigned to": detail.data.assigned_to,
            }).map(([k, v]) => (
              <div key={k} className="rounded border p-3">
                <p className="text-xs text-muted-foreground">{k}</p>
                <p className="text-sm font-medium">{v}</p>
              </div>
            ))}
          </div>
          <Link
            className="text-primary underline"
            to={`/crm/companies/${detail.data.customer_id}`}
          >
            Customer 360
          </Link>
          {detail.data.order_id && (
            <Link
              className="ml-4 text-primary underline"
              to={`/srm/sales-orders/${detail.data.order_id}`}
            >
              Transaction #{detail.data.order_id}
            </Link>
          )}
          <div className="flex flex-wrap gap-2">
            {Object.entries(detail.data.links || {})
              .filter(([, value]) => value)
              .map(([key, value]) => (
                <Link
                  className="text-sm text-primary underline"
                  key={key}
                  to={
                    key === "invoice_id"
                      ? `/srm/invoices/${value}`
                      : `/crm/${key === "lead_id" ? "leads" : key === "contact_id" ? "contacts" : key === "deal_id" ? "deals" : "quotations"}/${value}`
                  }
                >
                  {key.replace(/_id/, "")} #{value}
                </Link>
              ))}
          </div>
          <p className="text-sm">{detail.data.configuration.notes}</p>
          <Input
            aria-label="Internal comment or action reason"
            placeholder="Internal comment / reason for change"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={busy}
              onClick={() => void run(() => action(Number(id), "complete"))}
            >
              <CheckCircle2 className="mr-2 h-4 w-4" />
              Complete
            </Button>
            <Button
              disabled={busy || !notes.trim()}
              variant="outline"
              onClick={() => void run(() => action(Number(id), "comment"))}
            >
              Add comment
            </Button>
            <Button
              disabled={busy || !notes.trim()}
              variant="outline"
              onClick={() => void run(() => action(Number(id), "contact"))}
            >
              Log customer contact
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                setSchedule({ ...detail.data!.configuration, required: true });
                setCustomer(String(detail.data!.customer_id));
                setTitle(detail.data!.title);
                setCreating(true);
              }}
            >
              Create next follow-up
            </Button>
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => void run(() => action(Number(id), "cancel"))}
            >
              Cancel
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
            <Input
              className="max-w-xs"
              type="datetime-local"
              aria-label="New follow-up date"
              value={reschedule}
              onChange={(e) => setReschedule(e.target.value)}
            />
            <Button
              variant="outline"
              disabled={busy || !reschedule || !notes.trim()}
              onClick={() =>
                void run(() =>
                  action(Number(id), "reschedule", {
                    due_at: new Date(reschedule).toISOString(),
                  }),
                )
              }
            >
              Reschedule
            </Button>
          </div>
          <section className="space-y-2">
            <h3 className="font-semibold">Attachments</h3>
            <Input
              aria-label="Upload follow-up attachment"
              type="file"
              disabled={busy}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file)
                  void run(async () => {
                    const body = new FormData();
                    body.append("file", file);
                    await api.post(`/follow-ups/${id}/attachments`, body, {
                      headers: { "Content-Type": "multipart/form-data" },
                    });
                    await attachments.refetch();
                  });
                e.target.value = "";
              }}
            />
            {attachments.data?.map((file: { id: number; name: string }) => (
              <button
                className="block text-sm text-primary underline"
                key={file.id}
                onClick={() =>
                  void run(async () => {
                    const response = await api.get(
                      `/follow-ups/${id}/attachments/${file.id}`,
                      { responseType: "blob" },
                    );
                    const url = URL.createObjectURL(response.data);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = file.name;
                    a.click();
                    URL.revokeObjectURL(url);
                  })
                }
              >
                {file.name}
              </button>
            ))}
          </section>
          <h3 className="font-semibold">Activity timeline</h3>
          {detail.data.activities?.map((a) => (
            <article
              key={a.id}
              className="border-l-2 border-primary/30 py-2 pl-4 text-sm"
            >
              <strong>{a.action}</strong>
              <p className="text-xs text-muted-foreground">
                {a.actor_name || `Employee #${a.actor_id}`} ·{" "}
                {new Date(a.created_at).toLocaleString()}
              </p>
              {Object.entries(a.details).map(([k, v]) => (
                <p key={k}>
                  {k.replace(/_/g, " ")}: {String(v)}
                </p>
              ))}
            </article>
          ))}
        </section>
      )}
      {view === "dashboard" && <MobileFollowUpQueue base={base}/>}
      {view === "dashboard" && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {Object.entries(stats.data || {}).map(([label, value]) => (
              <button
                key={label}
                onClick={() => {
                  setStatus(label === "Total" ? "" : label);
                }}
                className="rounded-xl border bg-card p-4 text-left shadow-sm"
              >
                <Clock
                  className={`mb-2 h-4 w-4 ${label === "Overdue" ? "text-red-500" : "text-primary"}`}
                />
                <p className="text-xs text-muted-foreground">
                  {label === "Due" ? "Due today" : label}
                </p>
                <p className="text-2xl font-semibold">
                  {String(value)}
                  {label === "Conversion Rate" ? "%" : ""}
                </p>
              </button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            Conversion rate measures completed follow-ups as a share of all
            follow-ups. Upcoming and due counts can overlap.
          </p>
        </>
      )}
      {view === "directory" && (
        <FollowUpGrid
          base={base}
          refreshKey={query.dataUpdatedAt}
          onSelectionChange={setSelected}
        />
      )}
      {view !== "detail" && (
        <>
          {view !== "directory" && (
            <MobileFilters chips={[search,status,assigned&&`Employee ${assigned}`].filter(Boolean)} onClear={()=>{setSearch("");setStatus("");setAssigned("");setPage(1);}}>
            <div className="flex flex-wrap gap-2 rounded-xl border bg-card p-3">
              <Input
                className="max-w-xs"
                aria-label="Search follow-ups"
                placeholder="Search next action…"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
              />
              <NativeSelect
                className="rounded border bg-background px-2 text-sm"
                aria-label="Follow-up status"
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">All statuses</option>
                {[
                  "Scheduled",
                  "Due",
                  "Overdue",
                  "Completed",
                  "Rescheduled",
                  "Missed",
                  "Cancelled",
                ].map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </NativeSelect>
              <NativeSelect loading={options.isFetching} error={options.isError}
                className="rounded border bg-background px-2 text-sm"
                aria-label="Employee filter"
                value={assigned}
                onChange={(e) => {
                  setAssigned(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">All permitted employees</option>
                {options.data?.employees.map((u: any) => (
                  <option key={u.id} value={u.id}>
                    {u.name}
                  </option>
                ))}
              </NativeSelect>
              <NativeSelect
                aria-label="Sort by"
                className="rounded border bg-background px-2 text-sm"
                value={sort}
                onChange={(e) => setSort(e.target.value)}
              >
                {[
                  "due_at",
                  "customer_name",
                  "priority",
                  "status",
                  "assigned_to",
                ].map((s) => (
                  <option key={s} value={s}>
                    {s.replace(/_/g, " ")}
                  </option>
                ))}
              </NativeSelect>
              <NativeSelect
                aria-label="Group by"
                className="rounded border bg-background px-2 text-sm"
                value={group}
                onChange={(e) => setGroup(e.target.value)}
              >
                <option value="">No grouping</option>
                <option value="status">Group by status</option>
                <option value="assigned_to">Group by employee</option>
              </NativeSelect>
              <Button variant="outline" onClick={exportRows}>
                <Download className="mr-2 h-4 w-4" />
                Export page
              </Button>
              <Button
                variant="outline"
                onClick={() =>
                  localStorage.setItem(
                    "follow-up-view",
                    JSON.stringify({ search, status, assigned, sort, group }),
                  )
                }
              >
                Save view
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  try {
                    const v = JSON.parse(
                      localStorage.getItem("follow-up-view") || "{}",
                    );
                    setSearch(v.search || "");
                    setStatus(v.status || "");
                    setAssigned(v.assigned || "");
                    setSort(v.sort || "due_at");
                    setGroup(v.group || "");
                  } catch {}
                }}
              >
                Restore view
              </Button>
            </div>
            </MobileFilters>
          )}
          {selected.length > 0 && (
            <div className="flex gap-2">
              <span>{selected.length} selected</span>
              <NativeSelect loading={options.isFetching} error={options.isError}
                aria-label="Bulk assign employee"
                className="rounded border bg-background"
                defaultValue=""
                onChange={(e) => {
                  const employee = Number(e.target.value);
                  if (employee)
                    void run(async () => {
                      for (const ident of selected)
                        await action(ident, "assign", {
                          assigned_user_id: employee,
                        });
                      setSelected([]);
                    });
                }}
              >
                <option value="">Assign selected to…</option>
                {options.data?.employees.map((u: any) => (
                  <option key={u.id} value={u.id}>
                    {u.name}
                  </option>
                ))}
              </NativeSelect>
            </div>
          )}
          {view === "calendar" && (
            <>
              <div className="flex flex-wrap gap-2">
                <Input
                  className="max-w-xs"
                  aria-label="Calendar date"
                  type="date"
                  value={anchor}
                  onChange={(e) => setAnchor(e.target.value)}
                />
                {["Day", "Week", "Month", "Agenda"].map((m) => (
                  <Button
                    variant={m === calendarMode ? "default" : "outline"}
                    key={m}
                    onClick={() => setCalendarMode(m)}
                  >
                    {m}
                  </Button>
                ))}
              </div>
              <div
                className={`grid gap-2 ${calendarMode === "Day" || calendarMode === "Agenda" ? "grid-cols-1" : "grid-cols-1 sm:grid-cols-7"}`}
              >
                {Array.from(
                  {
                    length:
                      calendarMode === "Month"
                        ? new Date(
                            new Date(anchor).getFullYear(),
                            new Date(anchor).getMonth() + 1,
                            0,
                          ).getDate()
                        : calendarMode === "Week"
                          ? 7
                          : 1,
                  },
                  (_, i) => {
                    const day = new Date(anchor + "T00:00:00");
                    if (calendarMode === "Month") day.setDate(i + 1);
                    else day.setDate(day.getDate() + i);
                    const key = day.toLocaleDateString();
                    return (
                      <div
                        key={i}
                        className="min-h-28 rounded border bg-card p-2"
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={(e) => {
                          e.preventDefault();
                          const ident = Number(
                            e.dataTransfer.getData("text/plain"),
                          );
                          if (ident)
                            void run(() =>
                              action(ident, "reschedule", {
                                due_at: new Date(
                                  day.getFullYear(),
                                  day.getMonth(),
                                  day.getDate(),
                                  9,
                                ).toISOString(),
                              }),
                            );
                        }}
                      >
                        <button
                          className="text-xs font-semibold"
                          onClick={() => {
                            setSchedule({
                              ...defaultSchedule,
                              required: true,
                              type: "date",
                              due_at: new Date(
                                day.getFullYear(),
                                day.getMonth(),
                                day.getDate(),
                                9,
                              ).toISOString(),
                            });
                            setCreating(true);
                          }}
                        >
                          {key} +
                        </button>
                        {rows
                          .filter(
                            (r) =>
                              calendarMode === "Agenda" ||
                              new Date(r.due_at).toLocaleDateString() === key,
                          )
                          .map((r) => (
                            <Link
                              draggable
                              onDragStart={(e) =>
                                e.dataTransfer.setData(
                                  "text/plain",
                                  String(r.id),
                                )
                              }
                              to={`${base}/${r.id}`}
                              key={r.id}
                              className={`mt-2 block rounded border-l-4 p-2 text-xs ${r.status === "Overdue" || r.priority === "Urgent" ? "border-red-500 bg-red-50 text-red-900" : "border-indigo-500 bg-indigo-50 text-indigo-900"}`}
                            >
                              {r.title}
                              <br />
                              {r.customer_name} · {r.status}
                            </Link>
                          ))}
                      </div>
                    );
                  },
                )}
              </div>
              <p className="text-xs text-muted-foreground">
                Calendar uses your device time zone (
                {Intl.DateTimeFormat().resolvedOptions().timeZone}). Drag to
                move a commitment to 09:00 on the selected day. Showing the
                current result page.
              </p>
            </>
          )}
          {view !== "calendar" && view !== "directory" && (
            <div className="max-h-[65vh] overflow-auto rounded-xl border bg-card">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-muted">
                  <tr>
                    {[
                      "Select",
                      "Customer",
                      "Product / service & next action",
                      "Transaction",
                      "Follow-up date",
                      "Assigned to",
                      "Priority",
                      "Status",
                      "Actions",
                    ].map((h) => (
                      <th
                        key={h}
                        className="resize-x overflow-auto whitespace-nowrap p-3"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id} className="border-t">
                      <td className="p-3">
                        <input
                          type="checkbox"
                          aria-label={`Select ${r.title}`}
                          checked={selected.includes(r.id)}
                          onChange={(e) =>
                            setSelected((v) =>
                              e.target.checked
                                ? [...v, r.id]
                                : v.filter((i) => i !== r.id),
                            )
                          }
                        />
                      </td>
                      <td className="p-3">
                        {r.customer_name}
                        <small className="block text-muted-foreground">
                          {r.phone}
                        </small>
                      </td>
                      <td className="p-3">
                        <Link
                          className="font-medium text-primary"
                          to={`${base}/${r.id}`}
                        >
                          {r.title}
                        </Link>
                        {group && (
                          <small className="block">
                            {String(r[group as keyof Row])}
                          </small>
                        )}
                      </td>
                      <td className="p-3">
                        {r.order_id ? `Order #${r.order_id}` : "Manual"}
                      </td>
                      <td className="whitespace-nowrap p-3">
                        {new Date(r.due_at).toLocaleString()}
                        <small className="block text-muted-foreground">
                          {r.timezone}
                        </small>
                      </td>
                      <td className="p-3">{r.assigned_to}</td>
                      <td className="p-3">{r.priority}</td>
                      <td className="p-3">
                        <span
                          className={`rounded-full px-2 py-1 text-xs ${r.status === "Overdue" ? "bg-red-100 text-red-800" : r.status === "Completed" ? "bg-emerald-100 text-emerald-800" : "bg-indigo-100 text-indigo-800"}`}
                        >
                          {r.status}
                        </span>
                      </td>
                      <td className="p-3">
                        <div className="flex gap-2">
                          {r.phone && (
                            <>
                              <a
                                aria-label="Call customer"
                                href={`tel:${r.phone.replace(/[^\d+]/g, "")}`}
                              >
                                <Phone className="h-4 w-4" />
                              </a>
                              <a
                                aria-label="Contact on WhatsApp"
                                href={`https://wa.me/${r.phone.replace(/\D/g, "")}`}
                                target="_blank"
                                rel="noreferrer"
                              >
                                <MessageCircle className="h-4 w-4" />
                              </a>
                            </>
                          )}
                          <Link className="underline" to={`${base}/${r.id}`}>
                            Open
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {view !== "directory" && query.isLoading && (
            <div role="status" className="animate-pulse rounded border p-6">
              Loading follow-ups…
            </div>
          )}
          {view !== "directory" && !query.isLoading && !rows.length && (
            <div className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
              No follow-ups match these filters. Schedule a customer commitment
              to get started.
            </div>
          )}
          {view !== "directory" && (
            <footer className="flex items-center gap-3 text-sm">
              <Button
                variant="outline"
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <span>
                {query.data?.total || 0} records · Page {page}
              </span>
              <Button
                variant="outline"
                disabled={page * 100 >= (query.data?.total || 0)}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </footer>
          )}
        </>
      )}
    </div>
  );
}
