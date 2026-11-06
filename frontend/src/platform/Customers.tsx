import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { platformApi as api } from "@/services/platform-api";
import { useData, useOwner, allowed, message, Loading, Alert, Badge, Dialog, Table, ModulePicker, date, money, download, type Data } from "./shared";
export default function Customers() { const { me } = useOwner(); const [params, setParams] = useSearchParams(); const [search, setSearch] = useState(""); const [status, setStatus] = useState(""); const [error, setError] = useState(""); const rows = useData<Data[]>(`/platform/customers?search=${encodeURIComponent(search)}&status=${status}`); const selected = Number(params.get("selected")); if (!allowed(me, "tenant.read"))
    return <Alert error="Your platform role cannot view customer accounts."/>; return <><header className="po-heading"><div><h1>Customers</h1><p>Subscriptions and onboarding for approved businesses. Client ERP records stay in their own application.</p></div><button onClick={rows.refresh}>Refresh customers</button></header><Alert error={error}/><section className="po-panel"><div className="po-filters"><label>Search<input value={search} onChange={e => setSearch(e.target.value)} placeholder="Business name or admin email"/></label><label>Lifecycle<select value={status} onChange={e => setStatus(e.target.value)}><option value="">All customers</option>{["trial", "active", "suspended", "cancelled", "offboarded"].map(x => <option key={x}>{x}</option>)}</select></label></div><Loading busy={rows.busy} error={rows.error}/><Table rows={rows.data || []} empty="Approved workspaces will appear here after the first trial approval." columns={[{ label: "Business", render: r => <><button className="po-link" onClick={() => setParams({ selected: String(r.id) })}>{r.name}</button><small>{r.admin_email}</small></> }, { label: "Status", render: r => <Badge>{r.status}</Badge> }, { label: "Applications", render: r => r.config.modules?.map((key: string) => me.modules.find((m: Data) => m.key === key)?.label || key).join(", ") }, { label: "Usage / limits", render: r => <>{r.usage.seats ?? "—"} / {r.config.seats} seats<small>{r.usage.storage_bytes != null ? `${(r.usage.storage_bytes / 1048576).toFixed(1)} / ${r.config.storage_mib} MiB` : `${r.config.storage_mib} MiB allowance`}</small></> }, { label: "Trial ends", render: r => date(r.config.trial_ends_at) }, { label: "Monthly contract", render: r => money(r.config.monthly_price_minor, r.config.currency) }]}/></section>{!!selected && <CustomerDetail ident={selected} onClose={() => setParams({})} refreshList={rows.refresh}/>}</>; }
function CustomerDetail({ ident, onClose, refreshList }: {
    ident: number;
    onClose: () => void;
    refreshList: () => void;
}) {
    const { me } = useOwner();
    const row = useData<Data>(`/platform/customers/${ident}`);
    const plans = useData<Data[]>("/platform/plans");
    const backups = useData<Data[]>(`/platform/records/backup?tenant_id=${ident}`);
    const notes = useData<Data[]>(`/platform/records/note?tenant_id=${ident}`);
    const [tab, setTab] = useState("overview");
    const [action, setAction] = useState("");
    const [error, setError] = useState("");
    const [notice, setNotice] = useState("");
    const [busy, setBusy] = useState(false);
    const [modules, setModules] = useState<string[]>();
    const r = row.data;
    const canManage = allowed(me, "tenant.manage"), canBill = allowed(me, "billing.manage");
    async function execute(command: string, reason: string, values: Data = {}) { setBusy(true); setError(""); try {
        const { data } = await api.post(`/platform/customers/${ident}/action`, { action: command, reason, values });
        setNotice(data.url ? `Local private link: ${data.url}` : data.message || (data.scheduled ? "Change scheduled." : "Customer updated."));
        setAction("");
        row.refresh();
        backups.refresh();
        refreshList();
    }
    catch (err) {
        setError(message(err));
    }
    finally {
        setBusy(false);
    } }
    return <Dialog title={r?.name || "Customer workspace"} onClose={onClose}><Loading busy={row.busy} error={row.error}/><Alert error={error}/>{notice && <div className="po-notice" role="status">{notice}</div>}{r && <><div className="po-status-line"><Badge>{r.status}</Badge><span>{r.admin_email}</span><span>Customer #{r.id}</span></div><div className="po-tabs">{["overview", "subscription", "people", "notes", "history", "snapshots"].map(t => <button className={tab === t ? "active" : ""} onClick={() => setTab(t)} key={t}>{t}</button>)}</div>
    {tab === "overview" && <><div className="po-stats">{[["Licensed seats", r.config.seats], ["Used seats", r.usage.seats ?? "Not synced"], ["Active in 30 days", r.usage.active_30d ?? "Not synced"], ["Storage (MiB)", r.usage.storage_bytes != null ? (r.usage.storage_bytes / 1048576).toFixed(1) : "Not synced"]].map(([title, value]) => <div className="po-stat" key={String(title)}><span>{title}</span><strong>{value}</strong></div>)}</div><p>Usage last synced: {date(r.usage.recorded_at)}</p><p>Trial ends: {date(r.config.trial_ends_at)}</p><p>Account activated: {date(r.config.activated_at)}</p>{canManage && <div className="po-actions"><button onClick={() => execute("sync_usage", "Refresh aggregate customer usage")}>Sync aggregate usage</button><button onClick={() => setAction("support_request")}>Request customer-approved support</button><button onClick={() => download(`/platform/customers/${ident}/export`, `customer-${ident}-configuration.json`).catch(e => setError(message(e)))}>Export customer configuration</button></div>}<p className="po-muted">Only account configuration and aggregate usage are shown here. Customer business records and App Super Admin pages are not part of this portal.</p></>}
    {tab === "subscription" && <><div className="po-note"><strong>{plans.data?.find(p => p.id === r.plan_id)?.name || "Public trial"}</strong><p>{money(r.config.monthly_price_minor, r.config.currency)} / month · {r.config.seats} seats · {r.config.storage_mib} MiB</p><p>{r.config.modules?.join(", ")}</p></div><div className="po-actions">{canBill && <><button onClick={() => setAction(r.status === "trial" ? "convert_paid" : "plan")}>{r.status === "trial" ? "Convert trial to paid" : "Change plan"}</button><button onClick={() => setAction("payment")}>Record offline payment</button></>}{canManage && <><button onClick={() => setAction("extend_trial")} disabled={r.status !== "trial"}>Extend trial</button><button onClick={() => { setModules(r.config.modules); setAction("entitlements"); }}>Adjust allowances</button><button onClick={() => setAction(r.status === "suspended" || r.status === "cancelled" ? "resume" : "suspend")}>{r.status === "suspended" || r.status === "cancelled" ? "Reactivate" : "Suspend"}</button><button onClick={() => setAction("cancel")}>Cancel subscription</button><button onClick={() => setAction("offboard")} disabled={r.status !== "cancelled"}>Start offboarding</button></>}</div>{r.config.retention_until && <div className="po-notice">Offboarding retention review: {date(r.config.retention_until)}. ERP records are preserved until a separate reviewed deletion process.</div>}</>}
    {tab === "people" && <><h3>Primary company administrator</h3><p>{r.admin_email}</p><p>Activation status: {r.config.activated_at ? "Activated" : "Invitation pending"}</p>{canManage && <div className="po-actions"><button onClick={() => execute("resend_invitation", "Company admin requested another activation link")}>Prepare new invitation</button><button onClick={() => execute("revoke_invitation", "Company admin invitation revoked by platform owner")}>Revoke invitation</button><button onClick={() => setAction("admin_transfer")}>Transfer primary admin</button></div>}<p className="po-muted">A transfer requires confirmation from both current and new email holders. It does not give platform staff a company login.</p></>}
    {tab === "notes" && <><form className="po-form" onSubmit={async (e) => { e.preventDefault(); const form = e.currentTarget; const f = new FormData(form); try {
            await api.post("/platform/records/note", { title: f.get("title"), tenant_id: ident, data: { body: f.get("body") } });
            form.reset();
            notes.refresh();
        }
        catch (err) {
            setError(message(err));
        } }}><label>Note title<input name="title" required minLength={2}/></label><label>Internal account note<textarea name="body" required/></label><button>Add customer note</button></form>{notes.data?.map(n => <article className="po-note" key={n.id}><strong>{n.title}</strong><p>{n.data.body}</p><small>{date(n.created_at)}</small></article>)}</>}
    {tab === "history" && <div className="po-timeline">{r.history.map((h: Data) => <article key={h.id}><strong>{h.action.split(".").join(" · ")}</strong><small> · {date(h.created_at)}</small><p>{h.reason}</p>{h.before?.status !== h.after?.status && <p>{h.before?.status || "—"} → {h.after?.status || "—"}</p>}</article>)}</div>}
    {tab === "snapshots" && <><p>Snapshots preserve customer subscription configuration, allowances and plan settings. They exclude ERP data and passwords.</p>{canManage && <button onClick={() => execute("snapshot", "Customer configuration snapshot requested")}>Create configuration snapshot</button>}<Loading busy={backups.busy} error={backups.error}/><Table rows={backups.data || []} columns={[{ label: "Snapshot", render: b => <>{b.title}<small>{date(b.created_at)}</small></> }, { label: "State", render: b => <Badge>{b.state}</Badge> }, { label: "Restore", render: b => canManage && <button onClick={() => { if (window.confirm("Restore this customer's subscription configuration from the snapshot?"))
                    void execute("restore_snapshot", "Customer configuration restored from snapshot", { snapshot_id: b.id }); }}>Restore configuration</button> }]}/></>}
    {action && <section className="po-panel" style={{ marginTop: 20 }}><h3>{action.split("_").join(" ")}</h3><form className="po-form" onSubmit={e => { e.preventDefault(); const f = new FormData(e.currentTarget); const values: Data = {}; for (const [key, value] of f.entries()) {
                if (key !== "reason")
                    values[key] = ["days", "seats", "storage_mib", "plan_id", "amount_minor", "hours"].includes(key) ? Number(value) : value;
            } if (action === "entitlements")
                values.modules = modules; if (action === "payment") {
                values.amount_minor = Math.round(Number(values.amount) * 100);
                delete values.amount;
            } if (values.effective_at)
                values.effective_at = new Date(values.effective_at).toISOString(); void execute(action, String(f.get("reason")), values); }}>
      {["plan", "convert_paid"].includes(action) && <><label>Plan<select name="plan_id" required><option value="">Choose an active plan</option>{plans.data?.filter(p => p.active).map(p => <option key={p.id} value={p.id}>{p.name} · {money(p.config.monthly_price_minor, p.config.currency)} / month</option>)}</select></label><label>Effective date (leave empty for now)<input name="effective_at" type="datetime-local"/></label></>}
      {action === "extend_trial" && <label>Extra days<input type="number" name="days" min={1} max={90} defaultValue={7} required/></label>}
      {action === "entitlements" && <><div className="po-form-grid"><label>Seats<input type="number" name="seats" min={1} max={10000} defaultValue={r.config.seats} required/></label><label>Storage (MiB)<input type="number" name="storage_mib" min={100} max={1048576} defaultValue={r.config.storage_mib} required/></label></div><ModulePicker value={modules || []} onChange={setModules}/></>}
      {action === "payment" && <><p>Record a payment already received outside this local app. This does not charge the customer.</p><label>Payment reference<input name="reference" required minLength={3}/></label><label>Amount<input type="number" name="amount" min={0.01} step="0.01" required/></label><label>Currency<select name="currency">{["INR", "USD", "AED"].map(c => <option key={c}>{c}</option>)}</select></label></>}
      {action === "admin_transfer" && <label>New company admin email<input type="email" name="email" required/></label>}{action === "support_request" && <label>Support window (hours)<input type="number" name="hours" min={1} max={24} defaultValue={4} required/></label>}
      <label>Reason<textarea name="reason" required minLength={3}/></label><div className="po-actions"><button className="po-primary" disabled={busy}>Confirm action</button><button type="button" onClick={() => setAction("")}>Cancel</button></div></form></section>}
  </>}</Dialog>;
}
