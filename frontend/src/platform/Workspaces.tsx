import { useState } from "react";
import { platformApi as api } from "@/services/platform-api";
import { useData, useOwner, allowed, message, Loading, Alert, Badge, Dialog, Table, ModulePicker, date, money, type Data } from "./shared";
export function Team() {
    const { me } = useOwner();
    const team = useData<Data[]>("/platform/staff");
    const [edit, setEdit] = useState<Data>();
    const [invite, setInvite] = useState(false);
    const [role, setRole] = useState("reviewer");
    const [error, setError] = useState("");
    const [notice, setNotice] = useState("");
    if (!allowed(me, "staff.manage"))
        return <Alert error="Platform team management is restricted to owners."/>;
    return <><header className="po-heading"><div><h1>Owner team</h1><p>Named Indian Servers staff accounts and access reviews. No client administrator accounts are managed here.</p></div><button className="po-primary" onClick={() => setInvite(true)}>Invite staff</button></header><Alert error={error}/>{notice && <div className="po-notice">{notice}</div>}<section className="po-panel"><Loading busy={team.busy} error={team.error}/><Table rows={team.data || []} columns={[{ label: "Staff member", render: r => <>{r.name}<small>{r.email}</small></> }, { label: "Role", render: r => <Badge>{r.role}</Badge> }, { label: "Access", render: r => <>{r.is_active ? "Active" : "Disabled"}<small>{r.assigned_only ? "Assigned accounts only" : "Role-wide access"}</small></> }, { label: "Last access review", render: r => date(r.reviewed_at) }, { label: "Manage", render: r => <div className="po-actions"><button onClick={() => setEdit({ ...r })}>Edit access</button><button onClick={async () => { try {
                await api.patch(`/platform/staff/${r.id}`, { action: "review", reason: "Periodic staff access review completed" });
                team.refresh();
            }
            catch (err) {
                setError(message(err));
            } }}>Mark reviewed</button></div> }]}/></section>
  {invite && <Dialog title="Invite Indian Servers staff" onClose={() => setInvite(false)}><form className="po-form" onSubmit={async (e) => { e.preventDefault(); const f = new FormData(e.currentTarget); try {
        const { data } = await api.post("/platform/staff/invite", { name: f.get("name"), email: f.get("email"), role, assigned_only: f.get("assigned_only") === "on", permissions: [] });
        setNotice(`Staff invitation prepared: ${data.url}`);
        setInvite(false);
    }
    catch (err) {
        setError(message(err));
    } }}><label>Full name<input name="name" required minLength={2}/></label><label>Staff email<input name="email" type="email" required/></label><label>Platform role<select value={role} onChange={e => setRole(e.target.value)}>{me.roles.map((r: string) => <option key={r}>{r}</option>)}</select></label><label className="po-check"><input type="checkbox" name="assigned_only"/>Restrict to assigned signup and customer records</label><p>Activation is completed using a private link in the local outbox.</p><button className="po-primary">Prepare invitation</button></form></Dialog>}
  {edit && <Dialog title={`Edit access · ${edit.name}`} onClose={() => setEdit(undefined)}><form className="po-form" onSubmit={async (e) => { e.preventDefault(); const f = new FormData(e.currentTarget); try {
        await api.patch(`/platform/staff/${edit.id}`, { action: "access", reason: f.get("reason"), values: { role: edit.role, is_active: edit.is_active, assigned_only: edit.assigned_only, permissions: edit.permissions } });
        team.refresh();
        setEdit(undefined);
    }
    catch (err) {
        setError(message(err));
    } }}><label>Role<select value={edit.role} onChange={e => setEdit({ ...edit, role: e.target.value, permissions: [] })}>{me.roles.map((r: string) => <option key={r}>{r}</option>)}</select></label><label className="po-check"><input type="checkbox" checked={edit.is_active} onChange={e => setEdit({ ...edit, is_active: e.target.checked })}/>Active staff account</label><label className="po-check"><input type="checkbox" checked={edit.assigned_only} onChange={e => setEdit({ ...edit, assigned_only: e.target.checked })}/>Assigned records only</label><details><summary>Restrict individual actions within this role</summary><small>No selections use the role defaults. Restrictions cannot grant more than the selected role allows.</small><div className="po-form-grid">{(me.role_permissions?.[edit.role] || []).map((p: string) => <label className="po-check" key={p}><input type="checkbox" checked={edit.permissions.includes(p)} onChange={e => setEdit({ ...edit, permissions: e.target.checked ? [...edit.permissions, p] : edit.permissions.filter((x: string) => x !== p) })}/>{p.split(".").join(" · ")}</label>)}</div></details><label>Reason<textarea name="reason" required minLength={3}/></label><Alert error={error}/><button className="po-primary">Save staff access</button></form></Dialog>}
  </>;
}
export function Records({ workspace }: {
    workspace: "tasks" | "communications";
}) {
    const { me } = useOwner();
    const [kind, setKind] = useState(workspace === "tasks" ? "task" : "outbox");
    const rows = useData<Data[]>(`/platform/records/${kind}`);
    const directory = useData<Data[]>("/platform/staff-directory");
    const [edit, setEdit] = useState<Data>();
    const [preview, setPreview] = useState<Data>();
    const [calendar, setCalendar] = useState(false);
    const [error, setError] = useState("");
    const [filter, setFilter] = useState("all");
    const canCreate = ["task", "template", "scheduled_report"].includes(kind);
    const tabs = workspace === "tasks" ? [["task", "Tasks"], ["view", "Saved views"], ["scheduled_report", "Report schedules"]] : [["outbox", "Local outbox"], ["template", "Reason templates"], ["customer_invitation", "Company invitations"], ["staff_invitation", "Staff invitations"]];
    const filtered = (rows.data || []).filter(r => filter === "all" || r.state === filter);
    async function action(row: Data, command: string) { try {
        await api.post(`/platform/record/${row.id}/action`, { action: command, reason: "Updated in the owner workspace" });
        rows.refresh();
    }
    catch (err) {
        setError(message(err));
    } }
    return <><header className="po-heading"><div><h1>{workspace === "tasks" ? "Tasks & follow-ups" : "Communications"}</h1><p>{workspace === "tasks" ? "Keep owner-team work, saved views and scheduled reports organized." : "Prepare customer and staff communications locally. No external messages are sent."}</p></div>{canCreate && <button className="po-primary" onClick={() => setEdit({ title: "", data: {}, owner_id: me.id })}>New {kind.split("_").join(" ")}</button>}</header><div className="po-tabs">{tabs.filter(([k]) => k !== "staff_invitation" || allowed(me, "staff.manage")).map(([k, title]) => <button key={k} className={kind === k ? "active" : ""} onClick={() => { setKind(k); setFilter("all"); }}>{title}</button>)}</div><Alert error={error}/><section className="po-panel"><div className="po-filters"><label>State<select value={filter} onChange={e => setFilter(e.target.value)}><option value="all">All states</option>{[...new Set((rows.data || []).map(r => r.state))].map(x => <option key={x}>{x}</option>)}</select></label>{kind === "task" && <button onClick={() => setCalendar(!calendar)}>{calendar ? "List view" : "Due-date view"}</button>}<button onClick={rows.refresh}>Refresh</button></div><Loading busy={rows.busy} error={rows.error}/>{calendar && kind === "task" ? <div className="po-timeline">{[...filtered].sort((a, b) => String(a.data.due_at || "9999").localeCompare(String(b.data.due_at || "9999"))).map(r => <article key={r.id}><strong>{date(r.data.due_at)}</strong><p>{r.title} · {r.state}</p><small>{r.data.body}</small><button onClick={() => action(r, r.state === "completed" ? "reopen" : "complete")}>{r.state === "completed" ? "Reopen" : "Complete"}</button></article>)}</div> : <Table rows={filtered} columns={[{ label: kind === "outbox" ? "Message" : "Item", render: r => <><button className="po-link" onClick={() => setPreview(r)}>{r.title}</button><small>{r.data.recipient || r.data.body?.slice(0, 80) || r.data.frequency || ""}</small></> }, { label: "State", render: r => <Badge>{r.state}</Badge> }, { label: "Owner / date", render: r => <>{directory.data?.find(u => u.id === r.owner_id)?.name || "Team"}<small>{date(r.data.due_at || r.expires_at || r.created_at)}</small></> }, { label: "Actions", render: r => <div className="po-actions">{["task", "template", "scheduled_report"].includes(kind) && <><button onClick={() => setEdit(r)}>Edit</button><button onClick={() => action(r, r.state === "completed" ? "reopen" : "complete")}>{r.state === "completed" ? "Reopen" : "Complete"}</button></>}{kind === "view" && <button onClick={() => action(r, "archive")}>Archive</button>}{kind === "outbox" && <><button onClick={() => setPreview(r)}>Preview</button><button onClick={() => action(r, "preview_delivered")}>Mark preview checked</button><button onClick={() => action(r, "retry")}>Requeue locally</button></>}{kind === "staff_invitation" && r.state === "pending" && <button onClick={() => action(r, "revoke")}>Revoke</button>}</div> }]}/>}</section>
  {preview && <Dialog title={preview.title} onClose={() => setPreview(undefined)}><p><Badge>{preview.state}</Badge></p>{preview.data.recipient && <p>To: {preview.data.recipient}</p>}<div className="po-note">{preview.data.body || preview.data.reason || "Use the associated customer or staff workflow to manage this invitation."}</div>{preview.kind === "outbox" && <small>Local preview only. Checking a preview does not indicate external email delivery.</small>}</Dialog>}
  {edit && <Dialog title={edit.id ? "Edit owner record" : "Create owner record"} onClose={() => setEdit(undefined)}><form className="po-form" onSubmit={async (e) => { e.preventDefault(); const f = new FormData(e.currentTarget); const data = { ...edit.data, body: String(f.get("body") || ""), priority: f.get("priority") || "normal", due_at: f.get("due_at") ? new Date(String(f.get("due_at"))).toISOString() : null, frequency: f.get("frequency") || edit.data.frequency }; try {
        if (edit.id)
            await api.post(`/platform/record/${edit.id}/action`, { action: "edit", reason: "Owner record edited", values: { title: f.get("title"), data, owner_id: Number(f.get("owner_id") || edit.owner_id) } });
        else
            await api.post(`/platform/records/${kind}`, { title: f.get("title"), owner_id: Number(f.get("owner_id") || me.id), data });
        setEdit(undefined);
        rows.refresh();
    }
    catch (err) {
        setError(message(err));
    } }}><label>Title<input name="title" defaultValue={edit.title} minLength={2} maxLength={180} required/></label><label>{kind === "template" ? "Template wording" : "Details"}<textarea name="body" defaultValue={edit.data.body}/></label>{kind === "task" && <><label>Assign to<select name="owner_id" defaultValue={edit.owner_id}>{directory.data?.map(u => <option key={u.id} value={u.id}>{u.name}</option>)}</select></label><label>Due date<input type="datetime-local" name="due_at" defaultValue={edit.data.due_at ? new Date(new Date(edit.data.due_at).getTime() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16) : ""}/></label><label>Priority<select name="priority" defaultValue={edit.data.priority || "normal"}><option>normal</option><option>high</option><option>low</option></select></label></>}{kind === "scheduled_report" && <label>Frequency<select name="frequency" defaultValue={edit.data.frequency || "daily"}><option>daily</option><option>weekly</option></select></label>}<Alert error={error}/><button className="po-primary">Save {kind.split("_").join(" ")}</button></form></Dialog>}
  </>;
}
export function Plans() {
    const { me } = useOwner();
    const rows = useData<Data[]>("/platform/plans");
    const payments = useData<Data[]>("/platform/records/billing_entry");
    const scheduled = useData<Data[]>("/platform/records/scheduled_change");
    const [edit, setEdit] = useState<Data>();
    const [modules, setModules] = useState<string[]>([]);
    const [error, setError] = useState("");
    return <><header className="po-heading"><div><h1>Plans & billing</h1><p>Maintain the ERP offer catalogue and view recorded offline customer payments.</p></div>{allowed(me, "billing.manage") && <button className="po-primary" onClick={() => { setEdit({ config: {}, active: true }); setModules([]); }}>New plan</button>}</header><Alert error={error}/><section className="po-panel"><h2>Plan catalogue</h2><Loading busy={rows.busy} error={rows.error}/><Table rows={rows.data || []} columns={[{ label: "Plan", render: r => <>{r.name}<small>{r.code}</small></> }, { label: "Price / month", render: r => money(r.config.monthly_price_minor, r.config.currency) }, { label: "Allowance", render: r => <>{r.config.seats} seats<small>{r.config.storage_mib} MiB storage</small></> }, { label: "Applications", render: r => r.config.modules.join(", ") }, { label: "State", render: r => <Badge>{r.active ? "available" : "retired"}</Badge> }, { label: "Manage", render: r => allowed(me, "billing.manage") && <button onClick={() => { setEdit(r); setModules(r.config.modules); }}>Edit plan</button> }]}/><small>Editing a catalogue plan does not silently change an existing customer's contract. Apply or schedule it from that customer's subscription workspace.</small></section><section className="po-panel"><h2>Offline payment ledger</h2><Table rows={payments.data || []} columns={[{ label: "Reference", render: r => r.title }, { label: "Customer", render: r => `#${r.tenant_id}` }, { label: "Amount", render: r => money(r.data.amount_minor, r.data.currency) }, { label: "Recorded", render: r => date(r.created_at) }]}/></section><section className="po-panel"><h2>Scheduled subscription changes</h2><Table rows={scheduled.data || []} columns={[{ label: "Change", render: r => r.title }, { label: "Effective", render: r => date(r.data.effective_at) }, { label: "State", render: r => <Badge>{r.state}</Badge> }]}/></section>
  {edit && <Dialog title={edit.id ? "Edit plan" : "New subscription plan"} onClose={() => setEdit(undefined)}><form className="po-form" onSubmit={async (e) => { e.preventDefault(); const f = new FormData(e.currentTarget); const data = { code: f.get("code"), name: f.get("name"), modules, seats: Number(f.get("seats")), storage_mib: Number(f.get("storage_mib")), monthly_price_minor: Math.round(Number(f.get("price")) * 100), currency: f.get("currency"), active: f.get("active") === "on" }; try {
        if (edit.id)
            await api.put(`/platform/plans/${edit.id}`, data);
        else
            await api.post("/platform/plans", data);
        setEdit(undefined);
        rows.refresh();
    }
    catch (err) {
        setError(message(err));
    } }}><div className="po-form-grid"><label>Plan code<input name="code" defaultValue={edit.code} pattern="[a-z0-9_-]+" minLength={2} required/></label><label>Plan name<input name="name" defaultValue={edit.name} minLength={2} required/></label><label>Monthly price<input name="price" type="number" step="0.01" min={0} defaultValue={(edit.config.monthly_price_minor || 0) / 100} required/></label><label>Currency<select name="currency" defaultValue={edit.config.currency || "INR"}><option>INR</option><option>USD</option><option>AED</option></select></label><label>Seats<input name="seats" type="number" min={1} max={10000} defaultValue={edit.config.seats || 5} required/></label><label>Storage allowance (MiB)<input name="storage_mib" type="number" min={100} max={1048576} defaultValue={edit.config.storage_mib || 1024} required/></label></div><ModulePicker value={modules} onChange={setModules}/><label className="po-check"><input type="checkbox" name="active" defaultChecked={edit.active}/>Available for new contracts</label><Alert error={error}/><button className="po-primary" disabled={!modules.length}>Save plan</button></form></Dialog>}
  </>;
}
export function Operations() { const {me}=useOwner(); const [kind, setKind] = useState(allowed(me,"signup.review")?"provisioning":"support"); const jobs = useData<Data[]>(`/platform/records/${kind}`); const [notice, setNotice] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false); return <><header className="po-heading"><div><h1>Operations</h1><p>Provisioning recovery, overdue reviews, local reports and customer support requests.</p></div>{me.role === "owner" && <button className="po-primary" disabled={busy} onClick={async () => { setBusy(true); try {
    const { data } = await api.post("/platform/operations/run-checks");
    setNotice(`Checks completed: ${Object.entries(data.processed).map(([k, v]) => `${k.split("_").join(" ")}: ${v}`).join(", ") || "Everything is up to date."}`);
    jobs.refresh();
}
catch (err) {
    setError(message(err));
}
finally {
    setBusy(false);
} }}>Run due checks now</button>}</header><div className="po-notice">The local due-work runner checks every five minutes. All communications stay in the local preview outbox.</div>{notice && <div className="po-notice">{notice}</div>}<Alert error={error}/><div className="po-tabs">{[["provisioning", "Provisioning"], ["escalation", "Overdue reviews"], ["support", "Support"], ["admin_transfer", "Admin transfers"], ["customer_invitation", "Invitations"]].filter(([k]) => k === "support" ? allowed(me,"tools.manage") : k === "admin_transfer" ? allowed(me,"tenant.manage") : allowed(me,"signup.review")).map(([k, title]) => <button className={k === kind ? "active" : ""} key={k} onClick={() => setKind(k)}>{title}</button>)}</div><section className="po-panel"><Loading busy={jobs.busy} error={jobs.error}/><Table rows={jobs.data || []} columns={[{ label: "Operation", render: r => <>{r.title}<small>{r.data.error || r.data.body || r.data.scope}</small></> }, { label: "State", render: r => <Badge>{r.state}</Badge> }, { label: "Created / expires", render: r => <>{date(r.created_at)}<small>{r.expires_at && date(r.expires_at)}</small></> }, { label: "Progress / action", render: r => <>{r.data.steps?.map((x: string) => <small key={x}>{x}</small>)}{r.kind === "provisioning" && r.state === "failed" && r.data.retryable && <button onClick={async () => { try {
            await api.post(`/platform/signups/${r.signup_id}/review`, r.data.review);
            setNotice("Provisioning reconciled. The customer workspace was not duplicated.");
            jobs.refresh();
        }
        catch (err) {
            setError(message(err));
        } }}>Retry review</button>}{r.signup_id && <a href={`/platform/signups?selected=${r.signup_id}`}>Open signup</a>}</> }]}/></section></>; }
export function Audit() { const [search, setSearch] = useState(""); const [page, setPage] = useState(1); const events = useData<Data>(`/platform/events?search=${encodeURIComponent(search)}&page=${page}`); const [selected, setSelected] = useState<Data>(); return <><header className="po-heading"><div><h1>Platform activity log</h1><p>Who changed what and why, across owner workflows. No client App Super Admin actions are mixed into this log.</p></div></header><section className="po-panel"><label>Filter action<input value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} placeholder="signup, tenant, staff, login…"/></label><Loading busy={events.busy} error={events.error}/><Table rows={events.data?.items || []} columns={[{ label: "Time", render: r => date(r.created_at) }, { label: "Actor", render: r => r.admin_id ? `Staff #${r.admin_id}` : "Applicant / system" }, { label: "Action", render: r => <button className="po-link" onClick={() => setSelected(r)}>{r.action}</button> }, { label: "Record", render: r => `${r.entity} ${r.entity_id || ""}` }, { label: "Reason", render: r => r.reason }]}/><div className="po-pagination"><button disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</button><span>{events.data?.total || 0} events</span><button disabled={page * 50 >= (events.data?.total || 0)} onClick={() => setPage(p => p + 1)}>Next</button></div></section>{selected && <Dialog title={selected.action} onClose={() => setSelected(undefined)}><p>{selected.reason}</p><Table rows={[...new Set([...Object.keys(selected.before || {}), ...Object.keys(selected.after || {})])].filter(key => JSON.stringify(selected.before?.[key]) !== JSON.stringify(selected.after?.[key])).map(key => ({ id: key, key, before: selected.before?.[key], after: selected.after?.[key] }))} columns={[{ label: "Field", render: r => r.key.split("_").join(" ") }, { label: "Before", render: r => typeof r.before === "object" ? JSON.stringify(r.before) : String(r.before ?? "—") }, { label: "After", render: r => typeof r.after === "object" ? JSON.stringify(r.after) : String(r.after ?? "—") }]}/></Dialog>}</>; }
export function SettingsPage() { const { me, refresh } = useOwner(); const settings = useData<Data>("/platform/settings"); const keys = useData<Data[]>("/platform/records/api_key"); const [error, setError] = useState(""); const [notice, setNotice] = useState(""); const [newKey, setNewKey] = useState(false); const [scopes, setScopes] = useState<string[]>(["reports.read"]); const numeric: [
    [
        string,
        string
    ],
    ...Array<[
        string,
        string
    ]>
] = [["trial_days", "Default trial days"], ["seats", "Default seats"], ["storage_mib", "Default storage (MiB)"], ["sla_hours", "Review SLA (business hours)"], ["retention_days", "Archived applicant retention (days)"], ["idle_minutes", "Idle session timeout (minutes)"], ["business_start", "Business start hour"], ["business_end", "Business end hour"], ["grace_days", "Trial grace days"]]; return <><header className="po-heading"><div><h1>Portal settings</h1><p>Practical defaults for the owner team and customer onboarding.</p></div></header><Alert error={error}/>{notice && <div role="status" className="po-notice">{notice}</div>}<section className="po-panel"><Loading busy={settings.busy} error={settings.error}/>{settings.data && <form className="po-form" onSubmit={async (e) => { e.preventDefault(); const f = new FormData(e.currentTarget); const values: Data = {}; numeric.forEach(([key]) => values[key] = Number(f.get(key))); values.timezone = f.get("timezone"); values.business_days = f.getAll("business_days").map(Number); values.require_checklist = f.get("require_checklist") === "on"; values.notify_new_signup = f.get("notify_new_signup") === "on"; try {
    await api.put("/platform/settings", { action: "update", reason: f.get("reason"), values });
    settings.refresh();
    refresh();
    setNotice("Owner portal settings saved.");
}
catch (err) {
    setError(message(err));
} }}><div className="po-form-grid">{numeric.map(([key, label]) => <label key={key}>{label}<input type="number" name={key} defaultValue={settings.data?.[key]} required/></label>)}<label>Business timezone<input name="timezone" defaultValue={settings.data.timezone} required/></label></div><fieldset><legend>Business weekdays for SLA</legend><div className="po-actions">{["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((label, i) => <label key={label} className="po-check"><input type="checkbox" name="business_days" value={i} defaultChecked={settings.data?.business_days.includes(i)}/>{label}</label>)}</div></fieldset><label className="po-check"><input type="checkbox" name="require_checklist" defaultChecked={settings.data.require_checklist}/>Require the practical review checklist before approval</label><label className="po-check"><input type="checkbox" name="notify_new_signup" defaultChecked={settings.data.notify_new_signup}/>Notify the owner team about new signup requests</label><label>Reason for changing settings<input name="reason" minLength={3} required/></label><button className="po-primary">Save settings</button></form>}</section><section className="po-panel"><header className="po-heading"><h2>Local integrations</h2><button onClick={() => setNewKey(true)}>Create scoped API key</button></header><Table rows={keys.data || []} columns={[{ label: "Key", render: r => <>{r.title}<small>{r.data.prefix}…</small></> }, { label: "Scopes", render: r => r.data.scopes.join(", ") }, { label: "Expires", render: r => date(r.expires_at) }, { label: "State", render: r => <Badge>{r.state}</Badge> }, { label: "Manage", render: r => r.state === "active" && <button onClick={async () => { try {
            await api.post(`/platform/record/${r.id}/action`, { action: "revoke", reason: "Integration key revoked" });
            keys.refresh();
        }
        catch (err) {
            setError(message(err));
        } }}>Revoke</button> }]}/><small>API credentials authenticate only to platform endpoints. They cannot log in to client applications.</small></section>{newKey && <Dialog title="Create local integration key" onClose={() => setNewKey(false)}><form className="po-form" onSubmit={async (e) => { e.preventDefault(); const f = new FormData(e.currentTarget); try {
    const { data } = await api.post("/platform/api-keys", { title: f.get("title"), days: Number(f.get("days")), scopes });
    setNotice(`Copy this key now; it is only shown once: ${data.key}`);
    setNewKey(false);
    keys.refresh();
}
catch (err) {
    setError(message(err));
} }}><label>Integration name<input name="title" required minLength={2}/></label><label>Valid days<input name="days" type="number" min={1} max={365} defaultValue={30} required/></label>{["reports.read", "signup.read", "signup.create", "tenant.read"].map(scope => <label className="po-check" key={scope}><input type="checkbox" checked={scopes.includes(scope)} onChange={e => setScopes(e.target.checked ? [...scopes, scope] : scopes.filter(s => s !== scope))}/>{scope}</label>)}<button className="po-primary" disabled={!scopes.length}>Create API key</button></form></Dialog>}</>; }
export function Profile() { const { me, refresh } = useOwner(); const sessions = useData<Data[]>("/platform/sessions"); const history = useData<Data[]>("/platform/login-history"); const notifications = useData<Data[]>("/platform/records/notification"); const [error, setError] = useState(""); const [notice, setNotice] = useState(""); return <><header className="po-heading"><div><h1>My platform account</h1><p>{me.email} · {me.role}</p></div></header><Alert error={error}/>{notice && <div className="po-notice">{notice}</div>}<div className="po-grid"><section className="po-panel"><h2>Profile</h2><form className="po-form" onSubmit={async (e) => { e.preventDefault(); const f = new FormData(e.currentTarget); try {
    await api.patch("/platform/profile", { action: "profile", reason: "Own profile updated", values: { name: f.get("name") } });
    refresh();
    setNotice("Profile saved.");
}
catch (err) {
    setError(message(err));
} }}><label>Display name<input name="name" defaultValue={me.name} minLength={2} required/></label><button>Save profile</button></form></section><section className="po-panel"><h2>Workspace preferences</h2><form className="po-form" onSubmit={async (e) => { e.preventDefault(); const f = new FormData(e.currentTarget); try {
    await api.patch("/platform/profile", { action: "preferences", reason: "Workspace preferences updated", values: { default_page: f.get("default_page"), page_size: Number(f.get("page_size")), compact_rows: f.get("compact_rows") === "on" } });
    refresh();
    setNotice("Preferences saved.");
}
catch (err) {
    setError(message(err));
} }}><label>Start page<select name="default_page" defaultValue={me.preferences.default_page || "overview"}>{["overview", "signups", "customers", "tasks", "reports", "profile"].map(p => <option key={p}>{p}</option>)}</select></label><label>Requests per page<select name="page_size" defaultValue={me.preferences.page_size || 25}><option>10</option><option>25</option><option>50</option><option>100</option></select></label><label className="po-check"><input type="checkbox" name="compact_rows" defaultChecked={me.preferences.compact_rows}/>Compact signup rows</label><button>Save preferences</button></form></section></div><section className="po-panel" style={{ marginTop: 18 }}><h2>Notifications</h2>{notifications.data?.filter(n => n.state !== "read").map(n => <article className="po-note" key={n.id}><strong>{n.title}</strong><p>{n.data.body}</p><button onClick={async () => { await api.post(`/platform/record/${n.id}/action`, { action: "read", reason: "Owner read notification" }); notifications.refresh(); }}>Mark read</button></article>)}{!notifications.data?.some(n => n.state !== "read") && <p>No unread notifications.</p>}</section><section className="po-panel"><h2>Sessions</h2><Table rows={sessions.data || []} columns={[{ label: "Device", render: r => <>{r.device}<small>{r.ip}{r.id === me.session_id ? " · this session" : ""}</small></> }, { label: "State", render: r => <Badge>{r.status}</Badge> }, { label: "Last active", render: r => date(r.last_seen_at) }, { label: "Action", render: r => r.status === "active" && <button onClick={async () => { try {
            await api.post("/platform/sessions/revoke", { action: "one", reason: "Session revoked by its owner", values: { id: r.id } });
            sessions.refresh();
        }
        catch (err) {
            setError(message(err));
        } }}>Revoke session</button> }]}/><button onClick={async () => { await api.post("/platform/sessions/revoke", { action: "others", reason: "Owner signed out other devices" }); sessions.refresh(); }}>Sign out other sessions</button></section><section className="po-panel"><h2>Login history</h2><Table rows={history.data || []} columns={[{ label: "When", render: r => date(r.created_at) }, { label: "Result", render: r => r.action }, { label: "IP / device", render: r => <>{r.reason}<small>{r.after?.device}</small></> }]}/></section></>; }
