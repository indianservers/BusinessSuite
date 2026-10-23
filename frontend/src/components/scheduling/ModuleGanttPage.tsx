import { useId, useMemo, useRef, useState, type PointerEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { Link } from "react-router-dom";
import { api, leaveApi } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { getRoleKey } from "@/lib/roles";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

type Module = "crm" | "srm" | "hrms" | "fam" | "inventory";
type RecordData = Record<string, unknown>;
type Source = { label: string; key: string; endpoint: string; start: string; end: string; titles: string[]; path: string; listOnly?: boolean };
type Dependency = { id: string; source_id: string; target_id: string; type: "FS" | "SS" | "FF" | "SF"; lag: number };
type ScheduleRecord = { can_edit: boolean; start: string | null; end: string | null };
type ScheduleState = { revision: number; records: Record<string, ScheduleRecord>; dependencies: Dependency[] };
type Row = { id: string; title: string; from: number | null; to: number | null; canEdit: boolean; status: string; owner: string; href: string };
type Drag = { id: string; mode: "move" | "start" | "end"; x: number; from: number; to: number; delta: number; revision: number; expected: ScheduleRecord; scroll: number };
type Editor = { row: Row; from: string; to: string; revision: number; expected: ScheduleRecord };
const sources: Record<Module, Source[]> = {
  crm: [{ label: "CRM calendar", key: "calendar", endpoint: "/crm/calendar", start: "start", end: "end", titles: ["title"], path: "/crm/calendar", listOnly: true }],
  srm: [
    { label: "Sales orders", key: "sales-orders", endpoint: "/srm/sales-orders", start: "expected_start_date", end: "expected_end_date", titles: ["title", "order_number"], path: "/srm/sales-orders" },
    { label: "Contracts", key: "contracts", endpoint: "/srm/contracts", start: "effective_date", end: "expiry_date", titles: ["title", "contract_number"], path: "/srm/contracts" },
    { label: "Engagements", key: "engagements", endpoint: "/srm/engagements", start: "planned_start_date", end: "planned_end_date", titles: ["name", "engagement_number"], path: "/srm/engagements" },
  ],
  inventory: [{ label: "Purchase orders", key: "purchase-orders", endpoint: "/srm/procurement/purchase-orders", start: "order_date", end: "expected_date", titles: ["po_number", "vendor_name"], path: "/srm/inventory/purchase-orders", listOnly: true }],
  hrms: [{ label: "Leave requests", key: "leave", endpoint: "/leave/my-requests", start: "from_date", end: "to_date", titles: ["reason"], path: "/hrms/leave", listOnly: true }],
  fam: [{ label: "Financial years", key: "financial-years", endpoint: "/fam/financial-years", start: "start_date", end: "end_date", titles: ["name"], path: "/fam/financial-years", listOnly: true }],
};
const names: Record<Module, string> = { crm: "CRM", srm: "SRM", hrms: "HR", fam: "Finance", inventory: "Inventory" };
const dayMs = 86400000;
export function calendarDay(value: unknown): number | null {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}/.test(value)) return null;
  const date = value.slice(0, 10); const millis = Date.parse(`${date}T00:00:00Z`);
  return Number.isFinite(millis) && new Date(millis).toISOString().slice(0, 10) === date ? millis / dayMs : null;
}
const iso = (day: number) => new Date(day * dayMs).toISOString().slice(0, 10);
const todayDay = () => { const now = new Date(); return calendarDay(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`)!; };
const displayDay = (day: number) => new Date(day * dayMs).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
const valid = (row: Row) => row.from !== null && row.to !== null && row.to >= row.from;
const errorMessage = (error: unknown) => { const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail; return typeof detail === "string" ? detail : "Unable to save. Refresh and try again."; };

export default function ModuleGanttPage({ module }: { module: Module }) {
  const user = useAuthStore(state => state.user);
  const queryClient = useQueryClient();
  const arrowId = `arrow-${useId().replace(/:/g, "")}`;
  const [sourceIndex, setSourceIndex] = useState(0);
  const source = sources[module][sourceIndex] || sources[module][0];
  const url = `/scheduling/${module}/${source.key}`;
  const [search, setSearch] = useState(""); const [status, setStatus] = useState(""); const [zoom, setZoom] = useState("week");
  const [range, setRange] = useState(() => ({ from: iso(todayDay() - 30), to: iso(todayDay() + 90) }));
  const [editor, setEditor] = useState<Editor | null>(null);
  const [saving, setSaving] = useState(false); const saveLock = useRef(false);
  const [error, setError] = useState(""); const [notice, setNotice] = useState("");
  const [drag, setDrag] = useState<Drag | null>(null); const dragRef = useRef<Drag | null>(null);
  const [linkSource, setLinkSource] = useState(""); const [linkTarget, setLinkTarget] = useState("");
  const [linkType, setLinkType] = useState<Dependency["type"]>("FS"); const [lag, setLag] = useState("0");
  const scroll = useRef<HTMLDivElement>(null);
  const start = calendarDay(range.from); const end = calendarDay(range.to);
  const validRange = start !== null && end !== null && end >= start && end - start <= 3660;
  const role = getRoleKey(user?.role, user?.is_superuser);
  const teamLeave = ["admin", "hr", "manager"].includes(role);
  const query = useQuery<RecordData[]>({
    queryKey: ["module-gantt", module, source.key, user?.id, teamLeave, range.from, range.to], enabled: validRange,
    queryFn: async () => {
      const response = module === "hrms" ? await (teamLeave ? leaveApi.allRequests({ per_page: 500 }) : leaveApi.myRequests({ per_page: 500 }))
        : await api.get(source.endpoint, { params: module === "crm" ? { startDate: range.from, endDate: `${range.to}T23:59:59Z` } : undefined });
      const records: unknown = Array.isArray(response.data) ? response.data : response.data?.items;
      if (!Array.isArray(records)) throw new Error("Unexpected schedule response");
      return records as RecordData[];
    },
  });
  const ids = (query.data || []).map(record => String(record.id)).sort().join(",");
  const schedule = useQuery<ScheduleState>({
    queryKey: ["schedule-state", module, source.key, user?.id, ids], enabled: query.isSuccess && validRange, retry: false,
    queryFn: async () => (await api.get(url, { params: { ids } })).data,
  });
  const normalized = useMemo<Row[]>(() => (query.data || []).flatMap(record => {
    const id = String(record.id); const access = schedule.data?.records[id];
    if (schedule.data && !access) return [];
    const from = calendarDay(access ? access.start : record[source.start]); const to = calendarDay(access ? access.end : record[source.end]);
    const employee = record.employee as RecordData | undefined; const leaveType = record.leave_type as RecordData | undefined;
    const owner = employee ? [employee.first_name, employee.last_name].filter(Boolean).join(" ") : String(record.assigned_user_id ?? record.ownerId ?? "");
    const title = source.titles.map(key => record[key]).find(value => typeof value === "string" && value.trim()) as string | undefined;
    return [{ id, title: module === "hrms" ? `${owner || "Leave"} - ${String(leaveType?.name || title || "Leave request")}` : title || `Record ${id}`,
      from: from ?? to, to: to ?? from, canEdit: !!access?.can_edit && !saving && !schedule.isError,
      owner, status: String(record.status ?? "Unspecified"), href: source.listOnly ? source.path : `${source.path}/${id}` }];
  }), [query.data, schedule.data, schedule.isError, source, module, saving]);
  const rows = normalized.filter(row => valid(row) && row.from! <= (end ?? 0) && row.to! >= (start ?? 0) && (!status || row.status === status) && `${row.title} ${row.owner}`.toLowerCase().includes(search.toLowerCase()));
  const unscheduled = normalized.filter(row => !valid(row));
  const dayWidth = zoom === "day" ? 44 : zoom === "week" ? 16 : 5;
  const chartStart = start ?? 0; const width = validRange ? (end! - chartStart + 1) * dayWidth : 0;
  const tickDays = zoom === "day" ? 1 : zoom === "week" ? 7 : 30;
  const ticks = validRange ? Array.from({ length: Math.ceil((end! - chartStart + 1) / tickDays) }, (_, i) => chartStart + i * tickDays) : [];
  const busy = saving || !!drag;
  const refresh = async () => { await Promise.all([queryClient.invalidateQueries({ queryKey: ["module-gantt", module] }), queryClient.invalidateQueries({ queryKey: ["schedule-state", module] })]); };
  const persist = async (id: string, from: string, to: string, revision: number, expected: ScheduleRecord) => {
    if (!expected.can_edit || saveLock.current) return false;
    if (calendarDay(from) === null || calendarDay(to) === null || from > to) { setError("End date must be on or after the start date."); return false; }
    saveLock.current = true; setSaving(true); setError(""); setNotice("");
    try {
      await api.patch(`${url}/records/${encodeURIComponent(id)}`, { start: from, end: to, revision, expected_start: expected.start, expected_end: expected.end });
      await refresh(); setNotice("Schedule saved."); return true;
    } catch (cause) { setError(errorMessage(cause)); await refresh(); return false; }
    finally { saveLock.current = false; setSaving(false); }
  };
  const openEditor = (row: Row) => {
    if (!row.canEdit || !schedule.data) return;
    setError(""); setNotice(""); setEditor({ row, from: row.from === null ? "" : iso(row.from), to: row.to === null ? "" : iso(row.to), revision: schedule.data.revision, expected: schedule.data.records[row.id] });
  };
  const saveEditor = async () => { if (editor && await persist(editor.row.id, editor.from, editor.to, editor.revision, editor.expected)) setEditor(null); };
  const beginDrag = (event: PointerEvent<HTMLButtonElement>, row: Row, mode: Drag["mode"]) => {
    if (!row.canEdit || !valid(row) || busy || !schedule.data || (event.pointerType === "mouse" && event.button !== 0)) return;
    event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId);
    const value: Drag = { id: row.id, mode, x: event.clientX, from: row.from!, to: row.to!, delta: 0, revision: schedule.data.revision, expected: schedule.data.records[row.id], scroll: scroll.current?.scrollLeft || 0 };
    dragRef.current = value; setDrag(value); setError("");
  };
  const moveDrag = (event: PointerEvent<HTMLButtonElement>) => {
    const current = dragRef.current; if (!current) return;
    let delta = Math.round((event.clientX - current.x + (scroll.current?.scrollLeft || 0) - current.scroll) / dayWidth);
    if (current.mode === "start") delta = Math.min(delta, current.to - current.from);
    if (current.mode === "end") delta = Math.max(delta, current.from - current.to);
    const next = { ...current, delta }; dragRef.current = next; setDrag(next);
  };
  const cancelDrag = () => { dragRef.current = null; setDrag(null); };
  const endDrag = async () => {
    const current = dragRef.current; cancelDrag(); if (!current?.delta) return;
    await persist(current.id, iso(current.from + (current.mode !== "end" ? current.delta : 0)), iso(current.to + (current.mode !== "start" ? current.delta : 0)), current.revision, current.expected);
  };
  const preview = (row: Row): Row => drag?.id === row.id ? { ...row, from: drag.from + (drag.mode !== "end" ? drag.delta : 0), to: drag.to + (drag.mode !== "start" ? drag.delta : 0) } : row;
  const mutateLink = async (id?: string) => {
    if (!schedule.data || busy || saveLock.current) return;
    if (!id && (!linkSource || !linkTarget || !Number.isInteger(Number(lag)))) { setError("Choose two records and a whole number of lag days."); return; }
    saveLock.current = true; setSaving(true); setError("");
    try {
      if (id) await api.delete(`${url}/dependencies/${id}`, { params: { revision: schedule.data.revision } });
      else await api.post(`${url}/dependencies`, { source_id: linkSource, target_id: linkTarget, type: linkType, lag: Number(lag), revision: schedule.data.revision });
      await refresh(); setNotice(id ? "Dependency removed." : "Dependency saved.");
    } catch (cause) { setError(errorMessage(cause)); await refresh(); }
    finally { saveLock.current = false; setSaving(false); }
  };
  const visibleLinks = (schedule.data?.dependencies || []).flatMap(link => {
    const si = rows.findIndex(row => row.id === link.source_id); const ti = rows.findIndex(row => row.id === link.target_id);
    if (si < 0 || ti < 0) return [];
    const a = preview(rows[si]); const b = preview(rows[ti]);
    const sourceDay = link.type[0] === "F" ? a.to! : a.from!; const targetDay = link.type[1] === "F" ? b.to! : b.from!;
    const sx = 260 + (sourceDay + (link.type[0] === "F" ? 1 : 0) - chartStart) * dayWidth;
    const tx = 260 + (targetDay + (link.type[1] === "F" ? 1 : 0) - chartStart) * dayWidth;
    return [{ ...link, path: `M ${sx} ${si * 56 + 28} H ${sx + 14} V ${ti * 56 + 28} H ${tx}`, warning: targetDay < sourceDay + link.lag }];
  });
  const dragProps = (row: Row, mode: Drag["mode"]) => ({ onPointerDown: (event: PointerEvent<HTMLButtonElement>) => beginDrag(event, row, mode), onPointerMove: moveDrag, onPointerUp: () => void endDrag(), onPointerCancel: cancelDrag, onLostPointerCapture: cancelDrag });

  return <div className="space-y-4">
    <div><h1 className="page-title">{names[module]} Gantt</h1><p className="page-description">Drag bars to move dates; drag edges to resize. Use Edit dates for keyboard scheduling. Locked records are read-only.</p>{module === "crm" && <p className="text-sm text-muted-foreground">Planning starts are saved with the chart; due dates and meeting times update the CRM records.</p>}</div>
    <Card className="flex flex-wrap items-end gap-3 p-4">
      <label className="grid gap-1 text-sm">Schedule<select aria-label="Schedule" className="rounded border bg-background p-2" value={sourceIndex} disabled={busy} onChange={event => { setSourceIndex(Number(event.target.value)); setStatus(""); setLinkSource(""); setLinkTarget(""); setNotice(""); setError(""); }}>{sources[module].map((item, i) => <option key={item.key} value={i}>{item.label}</option>)}</select></label>
      <label className="grid gap-1 text-sm">From<Input disabled={busy} type="date" value={range.from} onChange={event => setRange({ ...range, from: event.target.value })} /></label>
      <label className="grid gap-1 text-sm">To<Input disabled={busy} type="date" value={range.to} onChange={event => setRange({ ...range, to: event.target.value })} /></label>
      <label className="grid gap-1 text-sm">Zoom<select aria-label="Zoom" disabled={busy} className="rounded border bg-background p-2" value={zoom} onChange={event => setZoom(event.target.value)}>{["day", "week", "month"].map(value => <option key={value}>{value}</option>)}</select></label>
      <label className="grid gap-1 text-sm">Status<select aria-label="Status" disabled={busy} className="rounded border bg-background p-2" value={status} onChange={event => setStatus(event.target.value)}><option value="">All statuses</option>{Array.from(new Set(normalized.map(row => row.status))).sort().map(value => <option key={value}>{value}</option>)}</select></label>
      <label className="grid gap-1 text-sm">Search<Input disabled={busy} placeholder="Search schedules" value={search} onChange={event => setSearch(event.target.value)} /></label>
      <Button variant="outline" disabled={!validRange || busy || query.isFetching || schedule.isFetching} onClick={() => void refresh()}>Refresh</Button>
      <Button variant="outline" disabled={busy || !normalized.some(valid)} onClick={() => { const dated = normalized.filter(valid); setRange({ from: iso(Math.min(...dated.map(row => row.from!)) - 3), to: iso(Math.max(...dated.map(row => row.to!)) + 3) }); }}>Fit dates</Button>
      <Button variant="outline" disabled={busy || !validRange} onClick={() => { const today = todayDay(); if (today < chartStart || today > end!) setRange({ from: iso(today - 7), to: iso(today + 90) }); else scroll.current?.scrollTo({ left: Math.max(0, (today - chartStart) * dayWidth - 80), behavior: "smooth" }); }}>Today</Button>
    </Card>
    {!validRange && <p role="alert">Choose a valid date range of up to ten years.</p>}
    {(query.isLoading || schedule.isLoading) && <p role="status">Loading schedules...</p>}
    {query.isError && <p role="alert">Unable to load schedules. Check your permission and use Refresh to retry.</p>}
    {schedule.isError && <p role="alert">Unable to load scheduling permissions and dependencies. Refresh to retry.</p>}
    {error && !editor && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {validRange && query.isSuccess && <>
      <p className="text-sm text-muted-foreground">{rows.length} schedules in range - {unscheduled.length} without valid dates. Dates are inclusive.</p>
      {!rows.length ? <Card className="p-8 text-center">No schedules match this range and filters. Adjust dates or use Fit dates.</Card> :
        <Card ref={scroll} className="max-h-[640px] overflow-auto" aria-label={`${names[module]} schedule chart`}>
          <div style={{ width: width + 260, minWidth: "100%" }}>
            <div className="sticky top-0 z-30 flex h-12 border-b bg-background"><div className="sticky left-0 z-40 w-[260px] shrink-0 border-r bg-background p-3 font-medium">{source.label}</div><div className="relative" style={{ width }}>{ticks.map(day => <span key={day} className="absolute h-full whitespace-nowrap border-l p-2 text-xs" style={{ left: (day - chartStart) * dayWidth }}>{displayDay(day)}</span>)}</div></div>
            <div className="relative">
              {rows.map((original, index) => { const row = preview(original); const left = Math.max(row.from!, chartStart); const right = Math.min(row.to!, end!); const color = /done|completed|approved|closed|active/i.test(row.status) ? "bg-emerald-500" : /blocked|rejected|cancel/i.test(row.status) ? "bg-rose-500" : index % 2 ? "bg-violet-500" : "bg-blue-500";
                return <div key={row.id} className="flex h-14 border-b" data-testid="schedule-row"><div className="sticky left-0 z-20 flex w-[260px] shrink-0 items-center gap-2 border-r bg-background px-3 py-1 text-sm"><Link to={row.href} className="min-w-0 flex-1 truncate hover:underline" title={row.title}><span className="block truncate font-medium">{row.title}</span><span className="text-xs text-muted-foreground">{row.status}{row.owner ? ` - ${row.owner}` : ""}</span></Link>{row.canEdit && <button disabled={busy} className="shrink-0 text-xs text-primary underline" aria-label={`Edit dates for ${row.title}`} onClick={() => openEditor(row)}>Edit dates</button>}</div><div className="relative" style={{ width }}>
                  {ticks.map(day => <span key={day} aria-hidden="true" className="absolute inset-y-0 border-l border-border/50" style={{ left: (day - chartStart) * dayWidth }} />)}
                  <div className={`absolute top-3 h-8 rounded-full text-xs font-medium text-white shadow ${color}`} style={{ left: (left - chartStart) * dayWidth, width: Math.max(18, (right - left + 1) * dayWidth) }}>
                    <button type="button" aria-label={`Resize start for ${row.title}`} disabled={!row.canEdit} {...dragProps(original, "start")} className="absolute left-0 top-0 z-10 h-full w-2 touch-none cursor-ew-resize rounded-l-full bg-black/20 disabled:cursor-default" />
                    <button type="button" aria-label={`Move ${row.title}: ${iso(row.from!)} to ${iso(row.to!)}`} title={`${row.title}: ${iso(row.from!)} to ${iso(row.to!)}`} disabled={!row.canEdit} {...dragProps(original, "move")} className="h-full w-full touch-none cursor-grab truncate px-3 text-left disabled:cursor-default">{row.title}</button>
                    <button type="button" aria-label={`Resize end for ${row.title}`} disabled={!row.canEdit} {...dragProps(original, "end")} className="absolute right-0 top-0 z-10 h-full w-2 touch-none cursor-ew-resize rounded-r-full bg-black/20 disabled:cursor-default" />
                  </div>
                </div></div>;
              })}
              <svg aria-label="Schedule dependencies" className="pointer-events-none absolute inset-0 z-10 h-full w-full overflow-hidden"><defs><marker id={arrowId} markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#64748b" /></marker></defs>{visibleLinks.map(link => <path key={link.id} data-testid="dependency-arrow" d={link.path} fill="none" stroke={link.warning ? "#f59e0b" : "#64748b"} strokeWidth="2" markerEnd={`url(#${arrowId})`}><title>{link.type} dependency{link.warning ? " - schedule constraint not met" : ""}</title></path>)}</svg>
              {todayDay() >= chartStart && todayDay() <= end! && <div aria-label="Today marker" className="pointer-events-none absolute inset-y-0 z-10 border-l-2 border-violet-500" style={{ left: 260 + (todayDay() - chartStart) * dayWidth }} />}
            </div>
          </div>
        </Card>}
      {!!unscheduled.length && <details className="rounded border p-3"><summary>Records needing dates ({unscheduled.length})</summary><ul className="mt-2 space-y-2">{unscheduled.map(row => <li key={row.id}><Link className="text-primary underline" to={row.href}>{row.title}</Link>{row.canEdit && <button disabled={busy} className="ml-3 text-primary underline" onClick={() => openEditor(row)}>Edit dates</button>}</li>)}</ul></details>}
    </>}
    {schedule.data && !schedule.isError && <Card className="space-y-3 p-4">
      <h2 className="text-lg font-semibold">Dependencies</h2><p className="text-sm text-muted-foreground">Saved links between these records. Amber arrows flag unmet constraints. Linked records are not automatically rescheduled.</p>
      {normalized.some(row => row.canEdit) && <form onSubmit={event => { event.preventDefault(); void mutateLink(); }}><fieldset disabled={busy} className="flex flex-wrap items-end gap-3">
        <label>Predecessor<select aria-label="Predecessor" className="block max-w-[250px] rounded border bg-background p-2" value={linkSource} onChange={event => setLinkSource(event.target.value)}><option value="">Choose a record</option>{normalized.filter(row => row.canEdit).map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select></label>
        <label>Successor<select aria-label="Successor" className="block max-w-[250px] rounded border bg-background p-2" value={linkTarget} onChange={event => setLinkTarget(event.target.value)}><option value="">Choose a record</option>{normalized.filter(row => row.canEdit && row.id !== linkSource).map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select></label>
        <label>Type<select aria-label="Dependency type" className="block rounded border bg-background p-2" value={linkType} onChange={event => setLinkType(event.target.value as Dependency["type"])}>{["FS", "SS", "FF", "SF"].map(type => <option key={type}>{type}</option>)}</select></label>
        <label>Lag days<Input aria-label="Lag days" type="number" step="1" min="-3650" max="3650" value={lag} onChange={event => setLag(event.target.value)} className="w-24" /></label><Button disabled={!linkSource || !linkTarget}>Add dependency</Button>
      </fieldset></form>}
      <ul className="space-y-2">{schedule.data.dependencies.map(link => <li key={link.id} className="flex flex-wrap items-center justify-between gap-2 rounded border p-2 text-sm"><span>{normalized.find(row => row.id === link.source_id)?.title} &rarr; {normalized.find(row => row.id === link.target_id)?.title} - {link.type} - {link.lag}d</span>{normalized.find(row => row.id === link.source_id)?.canEdit && normalized.find(row => row.id === link.target_id)?.canEdit && <Button variant="outline" size="sm" disabled={busy} onClick={() => void mutateLink(link.id)}>Remove dependency</Button>}</li>)}</ul>
      {!schedule.data.dependencies.length && <p className="text-sm text-muted-foreground">No dependencies yet.</p>}
    </Card>}
    <Dialog.Root open={!!editor} onOpenChange={open => { if (!open && !saving) setEditor(null); }}><Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-50 bg-black/50" /><Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(90vw,420px)] -translate-x-1/2 -translate-y-1/2 space-y-4 rounded-xl border bg-background p-6">
      <Dialog.Title className="text-lg font-semibold">Edit schedule</Dialog.Title><Dialog.Description>{editor?.row.title}</Dialog.Description>
      <form className="space-y-4" onSubmit={event => { event.preventDefault(); void saveEditor(); }}>
        <label className="grid gap-1">Start date<Input required type="date" value={editor?.from || ""} disabled={saving} onChange={event => setEditor(current => current && { ...current, from: event.target.value })} /></label>
        <label className="grid gap-1">End date<Input required type="date" value={editor?.to || ""} disabled={saving} onChange={event => setEditor(current => current && { ...current, to: event.target.value })} /></label>
        {error && <p role="alert">{error}</p>}<div className="flex gap-2"><Button type="submit" disabled={saving}>{saving ? "Saving..." : "Save schedule"}</Button><Button type="button" variant="outline" disabled={saving} onClick={() => { setEditor(null); setError(""); }}>Cancel</Button></div>
      </form>
    </Dialog.Content></Dialog.Portal></Dialog.Root>
  </div>;
}
