import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArchiveRestore, Plus, RefreshCw, Settings2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { recordPreviewProps } from "@/components/RecordQuickPreview";
import { crmApi, type CRMApiRecord } from "./api";
import { dealError } from "./deals/deal-utils";

const entities = [
  { key: "contacts", label: "Contacts", singular: "contact", description: "People, contact details, company relationships and customer preferences." },
  { key: "leads", label: "Leads", singular: "lead", description: "Prospects, sources, qualification, ownership and next follow-ups." },
  { key: "deals", label: "Deals", singular: "deal", description: "Opportunities, products and services, pipeline stages and sales values." },
  { key: "companies", label: "Companies", singular: "company", description: "Company metadata, industry, addresses, account type and linked contacts." },
] as const;
const name = (record: CRMApiRecord) => String(record.full_name || record.name || record.email || `Record #${record.id}`);
const displayDate = (value: unknown) => value ? new Date(String(value)).toLocaleString() : "—";

/** A common directory; specialized capture/detail screens retain their workflow validation. */
export default function CRMRecordsPage() {
  const [params, setParams] = useSearchParams();
  const entity = entities.find(item => item.key === params.get("entity")) || entities[0];
  const archived = params.get("view") === "deleted";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const search = params.get("search") || "";
  const [draftSearch, setDraftSearch] = useState(search);
  const [rows, setRows] = useState<CRMApiRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [revision, setRevision] = useState(0);
  const [pending, setPending] = useState<{ record: CRMApiRecord; entity: string; archived: boolean }>();
  const [busy, setBusy] = useState(false);
  const change = (patch: Record<string, string>, replace = false) => setParams(current => {
    const next = new URLSearchParams(current);
    Object.entries(patch).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key));
    return next;
  }, { replace });
  useEffect(() => setDraftSearch(search), [search]);
  useEffect(() => {
    if (draftSearch.trim() === search) return;
    const timer = window.setTimeout(() => change({ search: draftSearch.trim(), page: "" }, true), 300);
    return () => window.clearTimeout(timer);
  }, [draftSearch, search]);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(""); setRows([]);
    crmApi.list(entity.key, { page, per_page: 25, search, deleted_only: archived, sort_by: archived ? "deleted_at" : "updated_at", sort_order: "desc" })
      .then(({ data }) => {
        if (!active) return;
        if (!data.items.length && page > 1) {
          change({ page: String(Math.max(1, Math.ceil(data.total / 25))) }, true);
          return;
        }
        setRows(data.items); setTotal(data.total);
      })
      .catch(err => { if (active) { setError(dealError(err)); setTotal(0); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [entity.key, archived, search, page, revision]);
  const mutate = async () => {
    if (!pending || busy) return;
    setBusy(true); setError("");
    try {
      const id = Number(pending.record.id);
      if (pending.archived) await crmApi.restore(pending.entity, id);
      else await crmApi.delete(pending.entity, id);
      setNotice(`${name(pending.record)} ${pending.archived ? "restored" : "moved to recycle bin"}.`);
      setPending(undefined); setRevision(value => value + 1);
    } catch (err) { setError(dealError(err)); }
    finally { setBusy(false); }
  };
  return <main className="space-y-5 p-4 md:p-6">
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div><p className="text-xs uppercase tracking-wide text-muted-foreground">CRM</p><h1 className="text-2xl font-bold">Records management</h1><p className="mt-1 text-sm text-muted-foreground">Create, find, update and recover your business relationships.</p></div>
      <div className="flex flex-wrap gap-2"><Button asChild variant="outline"><Link to={`/crm/record-metadata?entity=${entity.key}`}><Settings2 className="mr-2 h-4 w-4" />Manage metadata</Link></Button><Button asChild><Link to={`/crm/${entity.key}?new=${entity.key}`}><Plus className="mr-2 h-4 w-4" />Create {entity.singular}</Link></Button></div>
    </header>
    <nav aria-label="Record types" className="flex flex-wrap gap-2">{entities.map(item => <Button key={item.key} variant={entity.key === item.key ? "default" : "outline"} aria-current={entity.key === item.key ? "page" : undefined} onClick={() => { setNotice(""); change({ entity: item.key, page: "" }); }}>{item.label}</Button>)}</nav>
    <p className="text-sm text-muted-foreground">{entity.description}</p>
    <section className="space-y-3 rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2"><Input aria-label="Search records" placeholder={`Search ${entity.label.toLowerCase()}…`} value={draftSearch} onChange={event => setDraftSearch(event.target.value)} className="max-w-sm" /><Button variant={archived ? "outline" : "default"} onClick={() => change({ view: "", page: "" })}>Active records</Button><Button variant={archived ? "default" : "outline"} onClick={() => change({ view: "deleted", page: "" })}>Recycle bin</Button><Button variant="ghost" aria-label="Refresh records" disabled={loading} onClick={() => setRevision(value => value + 1)}><RefreshCw className="h-4 w-4" /></Button><Link className="text-sm underline" to={`/crm/${entity.key}`}>Full {entity.label.toLowerCase()} workspace</Link></div>
      {notice && <p role="status" className="text-sm text-green-700">{notice}</p>}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {archived && <p className="text-sm text-muted-foreground">Deleted records keep their history and relationships. Merged records stay with the surviving record and cannot be restored.</p>}
      {loading ? <p role="status" className="p-6">Loading records…</p> : !error && <>
        <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="border-b text-muted-foreground"><tr><th className="p-3">Name</th><th className="p-3">Contact / Company</th><th className="p-3">Status</th><th className="p-3">{archived ? "Deleted" : "Updated"}</th><th className="p-3">Actions</th></tr></thead><tbody>{rows.map(record => <tr key={String(record.id)} className="border-b" {...(!archived ? recordPreviewProps(record, `/crm/${entity.key}`) : {})}><td className="p-3 font-medium">{archived ? name(record) : <Link className="underline" to={`/crm/${entity.key}/${record.id}`}>{name(record)}</Link>}<p className="text-xs text-muted-foreground">#{String(record.id)}</p></td><td className="p-3">{String(record.email || record.company_name || record.phone || "—")}</td><td className="p-3">{String(record.status || record.lifecycle_stage || "—")}</td><td className="whitespace-nowrap p-3">{displayDate(archived ? record.deleted_at : record.updated_at)}</td><td className="p-3"><div className="flex gap-2">{!archived && <Button asChild variant="outline" size="sm"><Link to={`/crm/${entity.key}/${record.id}`}>View / Edit</Link></Button>}<Button variant="outline" size="sm" aria-label={`${archived ? "Restore" : "Delete"} ${name(record)}`} onClick={() => {setError(""); setPending({ record, entity: entity.key, archived });}}>{archived ? <ArchiveRestore className="mr-1 h-4 w-4" /> : <Trash2 className="mr-1 h-4 w-4" />}{archived ? "Restore" : "Delete"}</Button></div></td></tr>)}</tbody></table></div>
        {!rows.length && <p className="p-6 text-center text-sm text-muted-foreground">{search ? "No records match this search." : archived ? "Recycle bin is empty." : `No ${entity.label.toLowerCase()} yet. Create your first ${entity.singular} above.`}</p>}
        <div className="flex items-center justify-between gap-2 text-sm"><span>{total} records · Page {page} of {Math.max(1, Math.ceil(total / 25))}</span><div className="flex gap-2"><Button variant="outline" size="sm" disabled={page <= 1} onClick={() => change({ page: String(page - 1) })}>Previous</Button><Button variant="outline" size="sm" disabled={page * 25 >= total} onClick={() => change({ page: String(page + 1) })}>Next</Button></div></div>
      </>}
    </section>
    <Dialog open={Boolean(pending)} onOpenChange={open => { if (!open && !busy) setPending(undefined); }}><DialogContent><DialogHeader><DialogTitle>{pending?.archived ? "Restore record" : "Delete record"}</DialogTitle><p className="text-sm font-normal text-muted-foreground">{pending?.archived ? "Return this record to the active workspace, preserving its saved details." : "Move this record to the recycle bin. You can restore it later."} {pending && name(pending.record)}</p></DialogHeader>{error && <p role="alert" className="text-sm text-destructive">{error}</p>}<div className="flex justify-end gap-2"><Button variant="outline" disabled={busy} onClick={() => setPending(undefined)}>Cancel</Button><Button variant={pending?.archived ? "default" : "destructive"} disabled={busy} onClick={mutate}>{busy ? "Saving…" : pending?.archived ? "Restore record" : "Delete record"}</Button></div></DialogContent></Dialog>
  </main>;
}
