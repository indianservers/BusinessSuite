import PersonRecordPreview, { isPersonRecord } from "./PersonRecordPreview";
import EmployeeQuickPreview from "@/apps/hrms/pages/employees/EmployeeQuickPreview";
import { Fields, label, privateField } from "./RecordPreviewFields";
import { useEffect, useRef, useState, type MouseEvent } from "react";
import { useLocation } from "react-router-dom";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import * as Tabs from "@radix-ui/react-tabs";
import { FileText, Search, Maximize2, Minimize2, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/services/api";
const eventName = "suite:record-preview";
type Preview = { record: unknown; path: string };
export function recordPreviewProps(record: unknown, path?: string) {
  return {
    onDoubleClickCapture: (event: MouseEvent<HTMLElement>) => {
      if ((event.target as HTMLElement).closest('input, textarea, select, [contenteditable="true"], [role="checkbox"], [role="switch"], [data-cell-editable="true"]')) return;
      const action = (event.target as HTMLElement).closest('button, a, [role="button"], [role="menuitem"]');
      if (action && action !== event.currentTarget) return;
      event.stopPropagation();
      event.preventDefault();
      window.dispatchEvent(new CustomEvent<Preview>(eventName, { detail: { record: record && typeof record === "object" && "original" in record ? (record as { original: unknown }).original : record, path: path || window.location.pathname } }));
    },
  };
}
export default function RecordQuickPreview() {
  const opener = useRef<HTMLElement | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [details, setDetails] = useState<unknown>(null);
  const [related, setRelated] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("overview");
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState(false);
  const location = useLocation();
  useEffect(() => {
    const open = (event: Event) => {
      opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      setDetails(null); setRelated(null); setError("");
      setPreview((event as CustomEvent<Preview>).detail);
    };
    window.addEventListener(eventName, open);
    const close = () => setPreview(null);
    window.addEventListener("suite:organization-changed", close);
    return () => { window.removeEventListener(eventName, open); window.removeEventListener("suite:organization-changed", close); };
  }, []);
  useEffect(() => setPreview(null), [location.pathname, location.search]);
  useEffect(() => {
    setDetails(null); setRelated(null); setError(""); setLoading(false);
    setTab("overview"); setQuery(""); setExpanded(false);
    if (!preview) return;
    const match = preview.path.match(/^\/crm\/(contacts|companies|accounts|leads|deals|quotations|tasks)(?:\/|$)/);
    const record = preview.record as Record<string, unknown> | null;
    if (!record?.id) return;
    const controller = new AbortController();
    const id = encodeURIComponent(String(record.id));
    const entity = match?.[1] === "accounts" ? "companies" : match?.[1];
    let base = entity ? `/crm/${entity}/${id}` : "";
    if (preview.path.startsWith("/pms/")) {
      if (record.task_key || record.project_id) base = `/project-management/tasks/${id}`;
      else if (record.project_key) base = `/project-management/projects/${id}`;
    }
    if (/^\/hrms\/employees\/?$/.test(preview.path)) base = `/employees/${id}`;
    const srm = preview.path.match(/^\/srm\/(sales-orders|contracts|engagements|billing-plans|invoices)\/?$/);
    if (srm) base = `/srm/${srm[1]}/${id}`;
    const fam = preview.path.match(/^\/fam\/(vouchers|parties)\/?$/);
    if (fam) base = `/fam/${fam[1]}/${id}`;
    if (!base) return;
    setLoading(true);
    void Promise.allSettled([api.get(base, { signal: controller.signal }), entity ? api.get(`${base}/related`, { signal: controller.signal }) : Promise.resolve({ data: null })]).then(([detail, relations]) => {
      if (controller.signal.aborted) return;
      if (detail.status === "fulfilled") setDetails(detail.value.data);
      if (relations.status === "fulfilled") setRelated(relations.value.data);
      if (detail.status === "rejected" || relations.status === "rejected") setError("Some additional details could not be loaded. The available record information is shown below.");
      setLoading(false);
    });
    return () => controller.abort();
  }, [preview]);
  const record = preview?.record as Record<string, unknown> | null;
  const title = record && typeof record === "object" ? record.name || record.title || record.full_name || record.display_name || record.email : null;
  const merged = details && typeof details === "object" && !Array.isArray(details) ? { ...record, ...details } : preview?.record;
  const entries = merged && typeof merged === "object" && !Array.isArray(merged)
    ? Object.entries(merged).filter(([key]) => !privateField.test(key)) : [];
  const contactField = /email|phone|mobile|address|city|state|country|postal|zip|website|linkedin/i;
  const systemField = /(^id$|_id$|Id$|created|updated|deleted|validation|metadata|settings|permissions)/;
  const hasValue = (value: unknown) => value != null && value !== "" && (!Array.isArray(value) || value.length > 0);
  const groups = {
    overview: entries.filter(([key, value]) => !contactField.test(key) && !systemField.test(key) && hasValue(value)),
    contact: entries.filter(([key]) => contactField.test(key)),
    details: entries.filter(([key, value]) => systemField.test(key) || (!contactField.test(key) && !hasValue(value))),
  };
  const tabs = [
    { id: "overview", name: "Overview", count: groups.overview.length },
    { id: "contact", name: "Contact", count: groups.contact.length },
    { id: "details", name: "Details", count: groups.details.length },
    { id: "related", name: "Related", count: related == null ? 0 : undefined },
  ];
  const matches = (key: string, value: unknown): boolean => {
    const needle = query.trim().toLowerCase();
    if (!needle || label(key).toLowerCase().includes(needle)) return true;
    if (value && typeof value === "object") return Object.entries(value).some(([k, v]) => !privateField.test(k) && matches(k, v));
    return String(value ?? "").toLowerCase().includes(needle);
  };
  const selected = tab === "related" ? related : Object.fromEntries(groups[tab as keyof typeof groups] || []);
  const visible = query.trim()
    ? Object.fromEntries([...entries, ...(related != null ? [["related", related] as [string, unknown]] : [])].filter(([key, value]) => matches(key, value)))
    : selected;
  const empty = visible == null || (typeof visible === "object" && Object.keys(visible).length === 0);
  const displayTitle = typeof title === "string" ? title : "Record details";
  if (preview && record && isPersonRecord(record, preview.path)) {
    if (/^\/hrms\/employees\/?$/.test(preview.path) && record.id && record.first_name) return <EmployeeQuickPreview key={String(record.id)} employee={record as never} onClose={() => setPreview(null)}/>;
    const crm = preview.path.match(/^\/crm\/(contacts|leads)(?:\/|$)/);
    const href = crm && record.id ? `/crm/${crm[1]}/${record.id}` : /^\/pms\/people(?:\/|$)/.test(preview.path) && record.id ? `/pms/people/${record.id}` : undefined;
    return <PersonRecordPreview key={`${preview.path}:${record.id}`} record={(merged || record) as object} related={related} loading={loading} error={error} fullProfileHref={href} onClose={() => setPreview(null)} onCloseAutoFocus={event => { event.preventDefault(); if (opener.current?.isConnected) opener.current.focus({ preventScroll: true }); }}/>;
  }
  return <Dialog open={!!preview} onOpenChange={open => { if (!open) setPreview(null); }}>
    <DialogContent onCloseAutoFocus={event => { event.preventDefault(); if (opener.current?.isConnected) opener.current.focus({ preventScroll: true }); }} className={`flex flex-col gap-0 overflow-hidden p-0 sm:p-0 rounded-2xl ${expanded ? "max-w-[96vw] h-[94dvh]" : "max-w-4xl h-[min(80dvh,740px)]"}`}>
      <header className="shrink-0 border-b bg-gradient-to-br from-primary/10 via-primary/5 to-background px-5 pb-5 pt-6 sm:px-7">
        <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-primary"><Sparkles className="h-3.5 w-3.5" />Quick preview</div>
        <div className="flex items-center gap-3 pr-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-primary/15 bg-background text-primary shadow-sm"><FileText className="h-6 w-6" /></div>
          <div className="min-w-0 flex-1"><DialogTitle className="break-words text-xl font-semibold tracking-tight line-clamp-2">{displayTitle}</DialogTitle><p className="mt-1 text-xs text-muted-foreground">Your record, at a glance</p></div>
          <Button variant="ghost" size="icon" className="h-11 w-11 shrink-0" aria-label={expanded ? "Restore preview size" : "Expand preview"} onClick={() => setExpanded(value => !value)}>{expanded ? <Minimize2 /> : <Maximize2 />}</Button>
        </div>
      </header>
      <Tabs.Root value={tab} onValueChange={setTab} className="flex min-h-0 flex-1 flex-col">
        <Tabs.List aria-label="Record information" className="grid shrink-0 grid-cols-2 border-b px-3 sm:flex sm:px-5">
          {tabs.map(item => <Tabs.Trigger key={item.id} value={item.id} className="flex min-h-11 min-w-0 items-center justify-center gap-2 border-b-2 border-transparent px-3 py-3.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary data-[state=active]:border-primary data-[state=active]:text-primary">{item.name}{item.count !== undefined && <span className="rounded-md bg-muted px-1.5 py-0.5 text-[10px] tabular-nums">{item.count}</span>}</Tabs.Trigger>)}
        </Tabs.List>
        <div className="shrink-0 px-5 pt-4 sm:px-7">
          <div className="flex items-center gap-2 rounded-lg border bg-muted/30 px-3 focus-within:ring-2 focus-within:ring-primary/30"><Search className="h-4 w-4 shrink-0 text-muted-foreground" /><input aria-label="Search record fields" placeholder="Find a field or value across all tabs…" value={query} onChange={event => setQuery(event.target.value)} className="h-11 min-w-0 flex-1 bg-transparent text-sm outline-none" />{query && <button type="button" aria-label="Clear search" onClick={() => setQuery("")} className="flex h-11 w-11 shrink-0 items-center justify-center rounded hover:bg-muted"><X className="h-4 w-4" /></button>}</div>
          {loading && <p role="status" className="pt-3 text-xs text-muted-foreground animate-pulse">Loading complete details…</p>}
          {error && <p role="status" className="mt-3 rounded-lg bg-muted p-3 text-xs text-muted-foreground">{error}</p>}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-5 py-4 sm:px-7">
          {tabs.map(item => <Tabs.Content key={item.id} value={item.id} className="outline-none focus-visible:ring-2 focus-visible:ring-primary">
            {query && <p className="mb-3 text-xs font-medium text-muted-foreground">Search results · All tabs</p>}
            {empty ? <div className="flex flex-col items-center justify-center gap-2 py-12 text-center"><Search className="mb-2 h-7 w-7 text-muted-foreground/50" /><p className="text-sm font-medium">{query ? "No matching fields" : tab === "related" ? "No related information yet" : "No information here yet"}</p><p className="text-xs text-muted-foreground">{query ? "Try another field name or value." : "Available record information appears in the other tabs."}</p></div> : <Fields value={visible} />}
          </Tabs.Content>)}
        </div>
      </Tabs.Root>
      <footer className="flex shrink-0 items-center justify-between gap-3 border-t bg-muted/20 px-5 py-3 sm:px-7"><p className="text-xs text-muted-foreground">Press <kbd className="rounded border bg-background px-1.5 py-0.5 font-sans">Esc</kbd> to close</p><Button variant="outline" size="sm" className="min-h-11" onClick={() => setPreview(null)}>Close preview</Button></footer>
    </DialogContent>
  </Dialog>;
}
