import { useEffect, useState, type MouseEvent, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/services/api";

const eventName = "suite:record-preview";
type Preview = { record: unknown; path: string };
const label = (key: string) => key.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/[_-]/g, " ").replace(/^./, c => c.toUpperCase());
const privateField = /password|secret|token|credential|authorization|api[_-]?key/i;

export function recordPreviewProps(record: unknown) {
  return {
    onDoubleClickCapture: (event: MouseEvent<HTMLElement>) => {
      if ((event.target as HTMLElement).closest('input, textarea, select, [contenteditable="true"], [role="checkbox"], [role="switch"]')) return;
      event.stopPropagation();
      event.preventDefault();
      window.dispatchEvent(new CustomEvent<Preview>(eventName, { detail: { record, path: window.location.pathname } }));
    },
  };
}

function Fields({ value }: { value: unknown }): ReactNode {
  if (value == null || value === "") return <span className="text-muted-foreground">—</span>;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value !== "object") return <span className="whitespace-pre-wrap break-words">{String(value)}</span>;
  if (Array.isArray(value)) return value.length ? <div className="space-y-3">{value.map((item, i) => <div key={i} className="rounded-md border p-3"><Fields value={item} /></div>)}</div> : <span className="text-muted-foreground">None</span>;
  return <dl className="divide-y">{Object.entries(value).filter(([key]) => !privateField.test(key)).map(([key, item]) => <div key={key} className="grid gap-1 py-3 sm:grid-cols-[minmax(120px,1fr)_minmax(0,2fr)] sm:gap-4"><dt className="text-sm font-medium text-muted-foreground">{label(key)}</dt><dd className="min-w-0 text-sm"><Fields value={item} /></dd></div>)}</dl>;
}

export default function RecordQuickPreview() {
  const [preview, setPreview] = useState<Preview | null>(null);
  const [details, setDetails] = useState<unknown>(null);
  const [related, setRelated] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const location = useLocation();
  useEffect(() => {
    const open = (event: Event) => setPreview((event as CustomEvent<Preview>).detail);
    window.addEventListener(eventName, open);
    const close = () => setPreview(null);
    window.addEventListener("suite:organization-changed", close);
    return () => { window.removeEventListener(eventName, open); window.removeEventListener("suite:organization-changed", close); };
  }, []);
  useEffect(() => setPreview(null), [location.pathname, location.search]);
  useEffect(() => {
    setDetails(null); setRelated(null); setError(""); setLoading(false);
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
  return <Dialog open={!!preview} onOpenChange={open => { if (!open) setPreview(null); }}><DialogContent className="max-w-3xl max-h-[85dvh] flex flex-col overflow-hidden"><div className="pr-8"><p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Quick preview</p><DialogTitle className="text-lg font-semibold break-words">{typeof title === "string" ? title : "Record details"}</DialogTitle></div><div className="min-h-0 overflow-y-auto pr-2">{loading && <p role="status" className="py-2 text-sm text-muted-foreground">Loading complete details…</p>}{error && <p role="status" className="py-2 text-sm text-muted-foreground">{error}</p>}<Fields value={details && typeof details === "object" && !Array.isArray(details) ? { ...record, ...details } : preview?.record} />{related != null && <section className="mt-4 border-t pt-4"><h3 className="font-semibold">Related information</h3><Fields value={related} /></section>}</div></DialogContent></Dialog>;
}

