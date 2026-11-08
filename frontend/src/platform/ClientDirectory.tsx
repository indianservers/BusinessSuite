import { useState } from "react";
import { platformApi as api } from "@/services/platform-api";
import { Alert, Badge, Bars, Loading, Table, allowed, date, download, message, money, useData, useOwner, type Data } from "./shared";

export const flagLabel = (value: string) => value === "activation_pending" ? "activation not confirmed" : value.replace(/_/g, " ");
export default function ClientDirectory({ onOpen, revision }: { onOpen: (id: number) => void; revision: number }) {
  const { me } = useOwner();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [attention, setAttention] = useState("");
  const [module, setModule] = useState("");
  const [priority, setPriority] = useState("");
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const filters = new URLSearchParams({ search, status, attention, module, priority });
  const rows = useData<Data>(`/platform/client-directory?${filters}&sort=${sort}&page=${page}&revision=${revision}`);
  const summary = rows.data?.summary;
  function filter(set: (value: string) => void, value: string) { set(value); setPage(1); setSelected([]); }
  async function sync() {
    setBusy(true); setError(""); setNotice("");
    try {
      const { data } = await api.post("/platform/client-usage-refresh", { ids: selected });
      const failed = data.items.filter((r: Data) => !r.ok);
      setNotice(`${data.items.length - failed.length} client usage snapshots refreshed.${failed.length ? ` Could not refresh client IDs: ${failed.map((r: Data) => r.id).join(", ")}. Check their databases and retry.` : ""}`);
      rows.refresh(); setSelected([]);
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  if (!allowed(me, "tenant.read")) return <Alert error="Your platform role cannot view client accounts." />;
  return <>
    <header className="po-heading"><div><h1>Clients</h1><p>Manage your businesses, monitor adoption and plan the next account action.</p></div><div className="po-actions"><button onClick={rows.refresh}>Refresh clients</button><button onClick={() => download(`/platform/client-directory/export?${filters}`, "clients.csv").catch(e => setError(message(e)))}>Export filtered clients</button></div></header>
    <Alert error={error} />{notice && <div className="po-notice" role="status">{notice}</div>}
    {summary && <><div className="po-stats">{[["Matching clients", summary.total], ["Need attention", summary.attention], ["Used seats", summary.seats], ["Users active in 30 days", summary.active_30d]].map(([title, value]) => <div className="po-stat" key={title}><span>{title}</span><strong>{value}</strong></div>)}</div><div className="po-client-summary"><section className="po-panel"><h2>Client lifecycle</h2><Bars values={summary.statuses} /></section><section className="po-panel"><h2>Monthly contracted revenue</h2>{Object.entries(summary.mrr_by_currency).length ? Object.entries(summary.mrr_by_currency).map(([currency, value]) => <p key={currency}><strong>{money(Number(value), currency)}</strong> / month</p>) : <p>No active paid contracts in this selection.</p>}<p className="po-muted">Active contracts only; currencies stay separate. This is contracted revenue, not received payments.</p><p>{summary.unsynced} clients have no usage snapshot.</p></section></div></>}
    <section className="po-panel"><div className="po-filters">
      <label>Search clients<input value={search} onChange={e => filter(setSearch, e.target.value)} placeholder="Business, admin, workspace, tag or ID" /></label>
      <label>Lifecycle<select value={status} onChange={e => filter(setStatus, e.target.value)}><option value="">All clients</option>{["trial", "active", "suspended", "cancelled", "offboarded"].map(x => <option key={x}>{x}</option>)}</select></label>
      <label>Attention<select value={attention} onChange={e => filter(setAttention, e.target.value)}><option value="">All accounts</option>{["any", "activation_pending", "trial_ending", "trial_expired", "renewal_due", "review_due", "usage_stale", "inactive", "seat_capacity", "storage_capacity"].map(x => <option value={x} key={x}>{x === "any" ? "Any attention flag" : flagLabel(x)}</option>)}</select></label>
      <label>Application<select value={module} onChange={e => filter(setModule, e.target.value)}><option value="">All applications</option>{me.modules?.map((m: Data) => <option value={m.key} key={m.key}>{m.label}</option>)}</select></label>
      <label>Priority<select data-priority-badge data-priority={priority} value={priority} onChange={e => filter(setPriority, e.target.value)}><option value="">All priorities</option>{["normal", "high", "critical"].map(x => <option key={x}>{x}</option>)}</select></label>
      <label>Sort clients<select value={sort} onChange={e => filter(setSort, e.target.value)}>{[["newest", "Newest first"], ["name", "Business name"], ["attention", "Most attention flags"], ["seats", "Most used seats"], ["last_login", "Most recent login"]].map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select></label>
    </div>
    <p className="po-muted">Usage and attention flags reflect saved snapshots. Refresh selected clients for current aggregates. File storage allowance and physical database size are different measures.</p>
    {allowed(me, "tenant.manage") && <div className="po-actions"><button disabled={busy || !selected.length || rows.busy} onClick={() => void sync()}>{busy ? "Refreshing usage…" : `Refresh selected usage (${selected.length}/10)`}</button><button disabled={!selected.length || busy} onClick={() => setSelected([])}>Clear selection</button></div>}
    <Loading busy={rows.busy} error={rows.error} />
    {!rows.error && <Table rows={rows.data?.items || []} empty="No clients match these filters." columns={[
      ...(allowed(me, "tenant.manage") ? [{ label: "Select", render: (r: Data) => <input type="checkbox" aria-label={`Select ${r.name}`} checked={selected.includes(r.id)} disabled={busy || (!selected.includes(r.id) && selected.length >= 10)} onChange={e => setSelected(e.target.checked ? [...selected, r.id] : selected.filter(id => id !== r.id))} /> }] : []),
      { label: "Client", render: r => <><button className="po-link" onClick={() => onOpen(r.id)}>{r.name}</button><small>{r.admin_email}</small><small>{r.database?.workspace || "Existing shared workspace"} · #{r.id}</small>{r.profile.tags?.map((tag: string) => <Badge key={tag}>{tag}</Badge>)}</> },
      { label: "Account", render: r => <><Badge>{r.status}</Badge><small>{r.profile.priority || "normal"} priority · {flagLabel(r.profile.stage || "onboarding")}</small></> },
      { label: "Contract", render: r => <>{money(r.config.monthly_price_minor, r.config.currency)} / month<small>{r.config.modules?.map((key: string) => me.modules?.find((m: Data) => m.key === key)?.label || key).join(", ")}</small></> },
      { label: "Seats / files", render: r => <>{r.usage.seats ?? "—"} / {r.config.seats} seats<small>{r.seat_percent == null ? "" : `${r.seat_percent}% seat capacity`}</small><small>{r.usage.storage_bytes == null ? "Not synced" : `${(r.usage.storage_bytes / 1048576).toFixed(1)} / ${r.config.storage_mib} MiB files`}</small></> },
      { label: "Engagement", render: r => <>{r.usage.active_30d ?? "—"} active users / 30 days<small>Last login: {date(r.usage.last_login_at)}</small><small>Synced: {date(r.usage.recorded_at)}</small></> },
      { label: "Next dates", render: r => <>Trial: {date(r.config.trial_ends_at)}<small>Renewal: {date(r.profile.renewal_at)}</small><small>Review: {date(r.profile.next_review_at)}</small></> },
      { label: "Attention", render: r => r.flags.length ? r.flags.map((f: string) => <div key={f}><Badge>{flagLabel(f)}</Badge></div>) : <span>Up to date</span> },
    ]} />}
    <div className="po-pagination"><span>{rows.data?.total ?? 0} matching clients · page {page}</span><div className="po-actions"><button disabled={page <= 1 || rows.busy} onClick={() => { setPage(page - 1); setSelected([]); }}>Previous</button><button disabled={rows.busy || page * 25 >= (rows.data?.total || 0)} onClick={() => { setPage(page + 1); setSelected([]); }}>Next</button></div></div></section>
  </>;
}

export function ClientStatistics({ ident }: { ident: number }) {
  const stats = useData<Data>(`/platform/clients/${ident}/statistics`);
  const usage = stats.data?.usage || {};
  return <><Loading busy={stats.busy} error={stats.error} /><p>Last usage snapshot: {date(usage.recorded_at)}</p><div className="po-stats">{[["Requests in 30 days", usage.requests_30d], ["Server errors in 30 days", usage.server_errors_30d], ["Database size (MiB)", usage.database_bytes == null ? "Not available" : (usage.database_bytes / 1048576).toFixed(1)], ["Active user accounts", usage.active_seats]].map(([title, value]) => <div className="po-stat" key={String(title)}><span>{title}</span><strong>{value ?? "Not synced"}</strong></div>)}</div><p>Last company activity: {date(usage.last_activity_at)}</p><h3>Database placement</h3>{stats.data?.database ? <div className="po-note"><strong>{stats.data.database.workspace}</strong><p>{stats.data.database.database_name}</p><p>{stats.data.database.server} · {stats.data.database.state} · routing version {stats.data.database.routing_version}</p></div> : <p>Existing shared workspace; no dedicated database is registered.</p>}<h3>Business record counts</h3><Bars values={usage.record_counts || {}} /><h3>API requests by day · last 30 days</h3><Bars values={usage.requests_by_day || {}} /><p className="po-muted">Aggregate counts only. API requests include background polling; they are not business transactions. Physical database size includes indexes and system overhead. Historical samples start when usage is refreshed.</p><h3>Recent usage snapshots</h3><Table rows={stats.data?.snapshots || []} columns={[{ label: "Sample", render: r => date(r.recorded_at) }, { label: "Seats", render: r => r.usage.seats }, { label: "Active in 30 days", render: r => r.usage.active_30d }, { label: "Requests in 30 days", render: r => r.usage.requests_30d ?? "—" }]} /></>;
}

export function AccountProfile({ r, onSave }: { r: Data; onSave: (profile: Data) => Promise<void> }) {
  const { me } = useOwner();
  const p = r.config.account_profile || {};
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const local = (value?: string) => { if (!value) return ""; const d = new Date(value); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16); };
  return <form className="po-form" key={p.version || 0} onSubmit={async e => { e.preventDefault(); setBusy(true); setError(""); const data = Object.fromEntries(new FormData(e.currentTarget)); try { await onSave({ ...data, version: p.version || 0, tags: String(data.tags).split(",").map(t => t.trim()).filter(Boolean), next_review_at: data.next_review_at ? new Date(String(data.next_review_at)).toISOString() : null, renewal_at: data.renewal_at ? new Date(String(data.renewal_at)).toISOString() : null }); } catch (err) { setError(message(err)); } finally { setBusy(false); } }}><Alert error={error} /><fieldset disabled={busy || !allowed(me, "tenant.manage")} className="po-form"><div className="po-form-grid"><label>Account priority<select name="priority" defaultValue={p.priority || "normal"}>{["normal", "high", "critical"].map(x => <option key={x}>{x}</option>)}</select></label><label>Success stage<select name="stage" defaultValue={p.stage || "onboarding"}>{["onboarding", "adopting", "established", "at_risk"].map(x => <option key={x} value={x}>{flagLabel(x)}</option>)}</select></label><label>Business contact<input name="contact_name" maxLength={120} defaultValue={p.contact_name} /></label><label>Business contact phone<input name="contact_phone" maxLength={40} defaultValue={p.contact_phone} /></label><label>Industry<input name="industry" maxLength={100} defaultValue={p.industry} /></label><label>Tags (comma separated)<input name="tags" defaultValue={p.tags?.join(", ")} /></label><label>Next account review<input type="datetime-local" name="next_review_at" defaultValue={local(p.next_review_at)} /></label><label>Contract renewal date<input type="datetime-local" name="renewal_at" defaultValue={local(p.renewal_at)} /></label></div><p className="po-muted">Dates are shown in your device timezone. Renewal tracking is an account reminder; it does not change subscription access or charge the customer.</p><label>Reason for account update<textarea name="reason" minLength={3} maxLength={1000} required /></label>{allowed(me, "tenant.manage") && <button disabled={busy}>{busy ? "Saving account…" : "Save account profile"}</button>}</fieldset></form>;
}
