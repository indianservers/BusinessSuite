import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { platformApi as api } from "@/services/platform-api";
import { useData, useOwner, allowed, message, Loading, Alert, Badge, Dialog, Table, ModulePicker, date, money, download, type Data } from "./shared";
import ClientDirectory, { AccountProfile, ClientStatistics } from "./ClientDirectory";
import CompanyRemoval from "./CompanyRemoval";
export default function Customers() {
    const [params, setParams] = useSearchParams();
    const selected = Number(params.get("selected"));
    const [revision, setRevision] = useState(0);
    const [removalNotice,setRemovalNotice]=useState("");
    return <>{removalNotice&&<div className="po-notice" role="status">{removalNotice}</div>}<ClientDirectory revision={revision} onOpen={id => setParams({ selected: String(id) })} />{selected > 0 && <CustomerDetail ident={selected} onClose={() => setParams({})} refreshList={() => setRevision(v => v + 1)} onRemoved={name=>{setRemovalNotice(`${name} was removed.`);setParams({});setRevision(v=>v+1);}} />}</>;
}

function CustomerDetail({ ident, onClose, refreshList, onRemoved }: {
    ident: number;
    onClose: () => void;
    refreshList: () => void;
    onRemoved: (name:string) => void;
}) {
    const { me } = useOwner();
    const canManage = allowed(me, "tenant.manage"), canBill = allowed(me, "billing.manage");
    const row = useData<Data>(`/platform/customers/${ident}`);
    const plans = useData<Data[]>("/platform/plans", allowed(me, "billing.read"));
    const backups = useData<Data[]>(`/platform/records/backup?tenant_id=${ident}`, canManage);
    const notes = useData<Data[]>(`/platform/records/note?tenant_id=${ident}`);
    const [tab, setTab] = useState("overview");
    const [action, setAction] = useState("");
    const [error, setError] = useState("");
    const [notice, setNotice] = useState("");
    const [busy, setBusy] = useState(false);
    const [modules, setModules] = useState<string[]>();
    const [snapshotId, setSnapshotId] = useState<number>();
    const r = row.data;
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
    return <Dialog title={r?.name || "Customer workspace"} onClose={onClose}><Loading busy={row.busy} error={row.error}/><Alert error={error}/>{notice && <div className="po-notice" role="status">{notice}</div>}{r && <><div className="po-status-line"><Badge>{r.status}</Badge><span>{r.admin_email}</span><span>Customer #{r.id}</span></div><div className="po-tabs">{["overview", "account", "statistics", "subscription", "people", "notes", "history", ...(canManage ? ["snapshots"] : [])].map(t => <button className={tab === t ? "active" : ""} onClick={() => setTab(t)} key={t}>{t}</button>)}</div>
    {tab === "overview" && <><div className="po-stats">{[["Licensed seats", r.config.seats], ["Used seats", r.usage.seats ?? "Not synced"], ["Active in 30 days", r.usage.active_30d ?? "Not synced"], ["Storage (MiB)", r.usage.storage_bytes != null ? (r.usage.storage_bytes / 1048576).toFixed(1) : "Not synced"]].map(([title, value]) => <div className="po-stat" key={String(title)}><span>{title}</span><strong>{value}</strong></div>)}</div><p>Usage last synced: {date(r.usage.recorded_at)}</p><p>Trial ends: {date(r.config.trial_ends_at)}</p><p>Account activated: {date(r.config.activated_at)}</p>{canManage && <div className="po-actions"><button disabled={busy} onClick={() => execute("sync_usage", "Refresh aggregate customer usage")}>Sync aggregate usage</button><button onClick={() => setAction("support_request")}>Request customer-approved support</button><button onClick={() => download(`/platform/customers/${ident}/export`, `customer-${ident}-configuration.json`).catch(e => setError(message(e)))}>Export customer configuration</button></div>}<p className="po-muted">Only account configuration and aggregate usage are shown here. Customer business records and App Super Admin pages are not part of this portal.</p></>}
    {tab === "account" && <AccountProfile key={r.config.account_profile?.version || 0} r={r} onSave={async values => { await api.patch(`/platform/clients/${ident}/profile`, values); row.refresh(); refreshList(); setNotice("Account profile saved."); }} />}
    {tab === "statistics" && <ClientStatistics ident={ident} />}
    {tab === "subscription" && <><div className="po-note"><strong>{r.plan_name || plans.data?.find(p => p.id === r.plan_id)?.name || "Public trial"}</strong><p>{money(r.config.monthly_price_minor, r.config.currency)} / month · {r.config.seats} seats · {r.config.storage_mib} MiB</p><p>{r.config.modules?.join(", ")}</p></div><div className="po-actions">{canBill && <><button disabled={r.status === "offboarded"} onClick={() => setAction(r.status === "trial" ? "convert_paid" : "plan")}>{r.status === "trial" ? "Convert trial to paid" : "Change plan"}</button><button onClick={() => setAction("payment")}>Record offline payment</button></>}{canManage && <><button onClick={() => setAction("extend_trial")} disabled={r.status !== "trial"}>Extend trial</button><button disabled={r.status === "offboarded"} onClick={() => { setModules(r.config.modules); setAction("entitlements"); }}>Adjust allowances</button><button disabled={r.status === "offboarded"} onClick={() => setAction(r.status === "suspended" || r.status === "cancelled" ? "resume" : "suspend")}>{r.status === "suspended" || r.status === "cancelled" ? "Reactivate" : "Suspend"}</button><button disabled={["cancelled", "offboarded"].includes(r.status)} onClick={() => setAction("cancel")}>Cancel subscription</button><button onClick={() => setAction("offboard")} disabled={r.status !== "cancelled"}>Start offboarding</button></>}</div>{r.config.retention_until && <div className="po-notice">Offboarding retention review: {date(r.config.retention_until)}. ERP records are preserved until a separate reviewed deletion process.</div>}</>}
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
    {tab === "snapshots" && <><p>Snapshots preserve customer subscription configuration, allowances and plan settings. They exclude ERP data and passwords.</p>{canManage && <button disabled={busy} onClick={() => execute("snapshot", "Customer configuration snapshot requested")}>Create configuration snapshot</button>}<Loading busy={backups.busy} error={backups.error}/><Table rows={backups.data || []} columns={[{ label: "Snapshot", render: b => <>{b.title}<small>{date(b.created_at)}</small></> }, { label: "State", render: b => <Badge>{b.state}</Badge> }, { label: "Restore", render: b => canManage && <button disabled={busy} onClick={() => { setSnapshotId(b.id); setAction("restore_snapshot"); }}>Restore configuration</button> }]}/></>}
    {tab === "overview" && me.role === "owner" && r.status !== "removed" && <CompanyRemoval ident={ident} onRemoved={onRemoved}/>}
    {action && <section className="po-panel" style={{ marginTop: 20 }}><h3>{action.split("_").join(" ")}</h3><form className="po-form" onSubmit={e => { e.preventDefault(); const f = new FormData(e.currentTarget); const values: Data = {}; for (const [key, value] of f.entries()) {
                if (key !== "reason")
                    values[key] = ["days", "seats", "storage_mib", "plan_id", "amount_minor", "hours"].includes(key) ? Number(value) : value;
            } if (action === "restore_snapshot") values.snapshot_id = snapshotId; if (action === "entitlements")
                values.modules = modules; if (action === "payment") {
                values.amount_minor = Math.round(Number(values.amount) * 100);
                delete values.amount;
            } if (values.effective_at)
                values.effective_at = new Date(values.effective_at).toISOString(); void execute(action, String(f.get("reason")), values); }}>
      {action === "restore_snapshot" && <p>Restore subscription configuration from snapshot #{snapshotId}. Check the plan, allowances and lifecycle before confirming. Company business records are preserved.</p>}
      {["plan", "convert_paid"].includes(action) && <><label>Plan<select name="plan_id" required><option value="">Choose an active plan</option>{plans.data?.filter(p => p.active).map(p => <option key={p.id} value={p.id}>{p.name} · {money(p.config.monthly_price_minor, p.config.currency)} / month</option>)}</select></label><label>Effective date (leave empty for now)<input name="effective_at" type="datetime-local"/></label></>}
      {action === "extend_trial" && <label>Extra days<input type="number" name="days" min={1} max={90} defaultValue={7} required/></label>}
      {action === "entitlements" && <><div className="po-form-grid"><label>Seats<input type="number" name="seats" min={1} max={10000} defaultValue={r.config.seats} required/></label><label>Storage (MiB)<input type="number" name="storage_mib" min={100} max={1048576} defaultValue={r.config.storage_mib} required/></label></div><ModulePicker value={modules || []} onChange={setModules}/></>}
      {action === "payment" && <><p>Record a payment already received outside this local app. This does not charge the customer.</p><label>Payment reference<input name="reference" required minLength={3}/></label><label>Amount<input type="number" name="amount" min={0.01} step="0.01" required/></label><label>Currency<select name="currency">{["INR", "USD", "AED"].map(c => <option key={c}>{c}</option>)}</select></label></>}
      {action === "admin_transfer" && <label>New company admin email<input type="email" name="email" required/></label>}{action === "support_request" && <label>Support window (hours)<input type="number" name="hours" min={1} max={24} defaultValue={4} required/></label>}
      <label>Reason<textarea name="reason" required minLength={3}/></label><div className="po-actions"><button className="po-primary" disabled={busy}>Confirm action</button><button type="button" onClick={() => setAction("")}>Cancel</button></div></form></section>}
  </>}</Dialog>;
}
