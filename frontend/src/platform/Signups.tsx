import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { platformApi as api } from "@/services/platform-api";
import { useOwner, useData, allowed, message, Loading, Alert, Badge, Dialog, Table, ModulePicker, date, download, type Data } from "./shared";
const states = ["active", "pending", "under_review", "awaiting_applicant", "approved", "rejected", "withdrawn", "archived", "all"];
const fresh = { status: "active", search: "", applicant_type: "", source: "", module: "", assignee: "", start: "", end: "", priority: "" };
export default function Signups() {
    const { me } = useOwner();
    const [params, setParams] = useSearchParams();
    const [filters, setFilters] = useState(fresh);
    const [page, setPage] = useState(1);
    const [create, setCreate] = useState(false);
    const [selected, setSelected] = useState<number[]>([]);
    const [error, setError] = useState("");
    const [notice, setNotice] = useState("");
    const [bulk, setBulk] = useState<Data>();
    const views = useData<Data[]>("/platform/records/view");
    const staff = useData<Data[]>("/platform/staff-directory");
    const query = new URLSearchParams({ page: String(page), page_size: String(me.preferences?.page_size || 25) });
    Object.entries(filters).forEach(([k, v]) => { if (v)
        query.set(k, k === "start" || k === "end" ? new Date(v + (k === "end" ? "T23:59:59" : "T00:00:00")).toISOString() : v); });
    const rows = useData<Data>("/platform/signups?" + query.toString());
    const chosen = Number(params.get("selected")) || 0;
    function filter(k: string, v: string) { setFilters(f => ({ ...f, [k]: v })); setPage(1); setSelected([]); }
    async function saveView(e: React.FormEvent<HTMLFormElement>) { e.preventDefault(); const f = new FormData(e.currentTarget); try {
        await api.post("/platform/records/view", { title: f.get("title"), data: { filters, shared: f.get("shared") === "on" } });
        views.refresh();
        setNotice("View saved.");
    }
    catch (err) {
        setError(message(err));
    } }
    if (!allowed(me, "signup.read"))
        return <Alert error="Your platform role cannot view signup records."/>;
    return <><header className="po-heading"><div><h1>Signups</h1><p>Review company and individual ERP enquiries in one place.</p></div><div className="po-actions">{allowed(me, "signup.export") && <button onClick={() => download("/platform/signup-export", "platform-signups.csv").catch(e => setError(message(e)))}>Export permitted requests</button>}{allowed(me, "signup.create") && <button className="po-primary" onClick={() => setCreate(true)}>New signup</button>}</div></header><Alert error={error}/>{notice && <div className="po-notice" role="status">{notice}</div>}
    <section className="po-panel"><div className="po-filters"><label>Search<input value={filters.search} onChange={e => filter("search", e.target.value)} placeholder="Name, email, phone or company"/></label><label>Status<select value={filters.status} onChange={e => filter("status", e.target.value)}>{states.map(s => <option key={s}>{s}</option>)}</select></label><label>Type<select value={filters.applicant_type} onChange={e => filter("applicant_type", e.target.value)}><option value="">All applicants</option><option>company</option><option>individual</option></select></label><label>Assigned to<select value={filters.assignee} onChange={e => filter("assignee", e.target.value)}><option value="">Everyone</option><option value="0">Unassigned</option>{staff.data?.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</select></label></div>
    <details><summary>More filters and saved views</summary><div className="po-filters"><label>Source<input value={filters.source} onChange={e => filter("source", e.target.value)}/></label><label>Application<select value={filters.module} onChange={e => filter("module", e.target.value)}><option value="">All applications</option>{me.modules.map((m: Data) => <option key={m.key} value={m.key}>{m.label}</option>)}</select></label><label>Priority<select value={filters.priority} onChange={e => filter("priority", e.target.value)}><option value="">All</option>{["low", "normal", "high"].map(x => <option key={x}>{x}</option>)}</select></label><label>From<input type="date" value={filters.start} onChange={e => filter("start", e.target.value)}/></label><label>Through<input type="date" value={filters.end} onChange={e => filter("end", e.target.value)}/></label></div><div className="po-filters"><label>Saved view<select defaultValue="" onChange={e => { const view = views.data?.find(r => r.id === Number(e.target.value)); if (view) {
        setFilters({ ...fresh, ...view.data.filters });
        setPage(1);
    } }}><option value="">Choose a saved view</option>{views.data?.filter(v => v.state !== "archived").map(v => <option key={v.id} value={v.id}>{v.title}{v.data.shared ? " · shared" : ""}</option>)}</select></label><form className="po-actions" onSubmit={saveView}><input name="title" required minLength={2} placeholder="Name this view"/>{me.role === "owner" && <label className="po-check"><input type="checkbox" name="shared"/>Share with team</label>}<button>Save view</button></form><button onClick={() => { setFilters(fresh); setPage(1); }}>Reset filters</button></div></details></section>
    {!!selected.length && <div className="po-panel po-actions"><strong>{selected.length} selected</strong>{["assign", "under_review", "archive", "restore"].map(action => <button key={action} onClick={() => setBulk({ action, ids: selected, reason: "", assigned_to: null })}>{action.split("_").join(" ")}</button>)}<button onClick={() => setSelected([])}>Clear selection</button></div>}
    <section className="po-panel"><Loading busy={rows.busy} error={rows.error}/>{rows.data && <><Table rows={rows.data.items} columns={[{ label: "Select", render: r => <input type="checkbox" aria-label={`Select ${r.company_name || r.name}`} checked={selected.includes(r.id)} onChange={e => setSelected(ids => e.target.checked ? [...ids, r.id] : ids.filter(i => i !== r.id))}/> }, { label: "Applicant", render: r => <><button className="po-link" onClick={() => setParams({ selected: String(r.id) })}>{r.company_name || r.name}</button><small>{r.name} · {r.applicant_type}</small><small>{r.email}</small></> }, { label: "Review", render: r => <><Badge>{r.status}</Badge>{r.overdue && <small>Over SLA · {r.age_hours} business hours</small>}{!!r.duplicates.length && <small>{r.duplicates.length} possible matches</small>}</> }, { label: "Apps", render: r => <small>{r.requested_modules.map((k: string) => me.modules.find((m: Data) => m.key === k)?.label || k).join(", ")}</small> }, { label: "Owner / source", render: r => <>{staff.data?.find(a => a.id === r.assigned_to)?.name || "Unassigned"}<small>{r.source}{r.campaign && ` · ${r.campaign}`}</small></> }, { label: "Submitted", render: r => date(r.created_at) }]}/><footer className="po-pagination"><button disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</button><span>Page {page} · {rows.data.total} requests</span><button disabled={page * rows.data.page_size >= rows.data.total} onClick={() => setPage(p => p + 1)}>Next</button></footer></>}</section>
    {create && <CreateSignup onClose={() => setCreate(false)} onSaved={() => { setCreate(false); rows.refresh(); }}/>}{chosen > 0 && <SignupDetail ident={chosen} staff={staff.data || []} onClose={() => setParams({})} onSaved={rows.refresh}/>}
    {bulk && <Dialog title="Bulk action preview" onClose={() => setBulk(undefined)}><form className="po-form" onSubmit={async (e) => { e.preventDefault(); setError(""); try {
        const response = await api.post("/platform/signup-bulk", { ...bulk, preview: !bulk.preview, versions: bulk.preview ? Object.fromEntries(bulk.preview.items.map((r: Data) => [String(r.id), r.version])) : {}, assigned_to: bulk.assigned_to ? Number(bulk.assigned_to) : null });
        if (bulk.preview) {
            setNotice(`${response.data.changed} requests changed.`);
            setBulk(undefined);
            setSelected([]);
            rows.refresh();
        }
        else
            setBulk({ ...bulk, preview: response.data });
    }
    catch (err) {
        setError(message(err));
    } }}><p>{bulk.action.split("_").join(" ")} · {selected.length} selected records</p>{bulk.action === "assign" && <label>Assign to<select onChange={e => setBulk({ ...bulk, assigned_to: e.target.value, preview: undefined })}><option value="">Unassigned</option>{staff.data?.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</select></label>}<label>Reason<textarea value={bulk.reason} required minLength={3} onChange={e => setBulk({ ...bulk, reason: e.target.value, preview: undefined })}/></label>{bulk.preview && <><Table rows={bulk.preview.items} columns={[{ label: "Applicant", render: r => r.name }, { label: "Current status", render: r => r.status }]}/>{bulk.preview.errors.map((r: Data) => <Alert key={r.id} error={`#${r.id}: ${r.error}`}/>)}</>}<button className="po-primary" disabled={!!bulk.preview?.errors.length}>{bulk.preview ? "Confirm changes" : "Preview changes"}</button></form></Dialog>}
  </>;
}
function CreateSignup({ onClose, onSaved }: {
    onClose: () => void;
    onSaved: () => void;
}) { const [kind, setKind] = useState("company"); const [modules, setModules] = useState<string[]>([]); const [error, setError] = useState(""); const [busy, setBusy] = useState(false); return <Dialog title="New signup" onClose={onClose}><form className="po-form" onSubmit={async (e) => { e.preventDefault(); setBusy(true); const f = new FormData(e.currentTarget); try {
    await api.post("/platform/signups", { applicant_type: kind, name: f.get("name"), company_name: kind === "company" ? f.get("company_name") : null, email: f.get("email"), phone: f.get("phone"), phone_country_code: f.get("phone_country_code"), requested_modules: modules, notes: f.get("notes"), source: f.get("source"), campaign: f.get("campaign"), consent: true, consent_evidence: f.get("consent_evidence"), tags: String(f.get("tags") || "").split(",").map(t => t.trim()).filter(Boolean) });
    onSaved();
}
catch (err) {
    setError(message(err));
}
finally {
    setBusy(false);
} }}><div className="po-form-grid"><label>Applicant type<select value={kind} onChange={e => setKind(e.target.value)}><option>company</option><option>individual</option></select></label><label>Contact name<input name="name" required minLength={2}/></label>{kind === "company" && <label>Company name<input name="company_name" required/></label>}<label>Email<input name="email" type="email" required/></label><label>Calling code<input name="phone_country_code" defaultValue="+91" required/></label><label>Phone<input name="phone" required minLength={5}/></label><label>Lead source<input name="source" defaultValue="phone" required/></label><label>Campaign<input name="campaign"/></label><label>Tags, separated by commas<input name="tags"/></label></div><ModulePicker value={modules} onChange={setModules}/><label>Notes<textarea name="notes"/></label><label>Consent evidence<textarea name="consent_evidence" required minLength={5} placeholder="How and when did the applicant agree to be contacted?"/></label><Alert error={error}/><button className="po-primary" disabled={busy || !modules.length}>{busy ? "Creating…" : "Create signup"}</button></form></Dialog>; }
function SignupDetail({ ident, staff, onClose, onSaved }: {
    ident: number;
    staff: Data[];
    onClose: () => void;
    onSaved: () => void;
}) { const result = useData<Data>(`/platform/signups/${ident}`); return <Dialog title="Signup workspace" onClose={onClose}><Loading busy={result.busy} error={result.error}/>{result.data && <DetailForm key={result.data.id} row={result.data} staff={staff} onPurged={onClose} refresh={() => { result.refresh(); onSaved(); }}/>}</Dialog>; }
function DetailForm({ row, staff, refresh, onPurged }: {
    row: Data;
    staff: Data[];
    refresh: () => void;
    onPurged: () => void;
}) {
    const { me } = useOwner();
    const [tab, setTab] = useState("details");
    const [draft, setDraft] = useState<Data>({ ...row, priority: row.workflow.priority || "normal", checklist: row.workflow.checklist || {} });
    const [modules, setModules] = useState<string[]>(row.requested_modules);
    const [error, setError] = useState("");
    const [notice, setNotice] = useState("");
    const [busy, setBusy] = useState(false);
    const [reason, setReason] = useState("");
    const [decision, setDecision] = useState("approve");
    const [purgeConfirm, setPurgeConfirm] = useState(false);
    const templates = useData<Data[]>("/platform/records/template");
    const editable = ["pending", "under_review", "awaiting_applicant"].includes(row.status) && allowed(me, "signup.edit");
    async function operation(action: string, values: Data = {}) { setBusy(true); setError(""); try {
        const { data } = await api.post(`/platform/signups/${row.id}/action`, { action, reason: reason || "Updated from signup workspace", values });
        refresh();
        if (action === "delete") onPurged();
        return data;
    }
    catch (err) {
        setError(message(err));
    }
    finally {
        setBusy(false);
    } }
    const field = (key: string, label: string, type = "text") => <label>{label}<input type={type} value={draft[key] ?? ""} disabled={!editable} onChange={e => setDraft({ ...draft, [key]: e.target.value })}/></label>;
    return <><div className="po-heading"><div><h2>{row.company_name || row.name}</h2><p>{row.email} · {row.phone_country_code} {row.phone}</p></div><Badge>{row.status}</Badge></div><div className="po-status-line"><span>Submitted {date(row.created_at)}</span><span>{row.age_hours} business hours</span>{row.overdue && <strong>Overdue review</strong>}</div><div className="po-tabs">{["details", "review", "notes", "activity"].map(t => <button key={t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>{t}</button>)}</div><Alert error={error}/>{notice && <div role="status" className="po-notice">{notice}</div>}
    {row.workflow?.sample_data_requested && <div role="status" className="po-notice">Company requested sample data. After approval, their administrator can choose Import sample data.</div>}
    {tab === "details" && <form className="po-form" onSubmit={async (e) => { e.preventDefault(); setBusy(true); setError(""); try {
            await api.patch(`/platform/signups/${row.id}`, { version: row.version, reason: reason || "Applicant details corrected", name: draft.name, company_name: draft.company_name, email: draft.email, phone: draft.phone, notes: draft.notes || "", source: draft.source, campaign: draft.campaign, assigned_to: draft.assigned_to ? Number(draft.assigned_to) : null, priority: draft.priority, requested_modules: modules, tags: typeof draft.tags === "string" ? draft.tags.split(",").map((t: string) => t.trim()).filter(Boolean) : draft.tags });
            refresh();
        }
        catch (err) {
            setError(message(err));
        }
        finally {
            setBusy(false);
        } }}><div className="po-form-grid">{field("name", "Contact name")}{row.applicant_type === "company" && field("company_name", "Company")}{field("email", "Email", "email")}{field("phone", "Phone")}{field("source", "Source")}{field("campaign", "Campaign")}<label>Assigned to<select value={draft.assigned_to || ""} disabled={!editable} onChange={e => setDraft({ ...draft, assigned_to: e.target.value })}><option value="">Unassigned</option>{staff.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</select></label><label>Priority<select value={draft.priority} disabled={!editable} onChange={e => setDraft({ ...draft, priority: e.target.value })}>{["low", "normal", "high"].map(t => <option key={t}>{t}</option>)}</select></label><label>Tags<input value={Array.isArray(draft.tags) ? draft.tags.join(", ") : draft.tags} disabled={!editable} onChange={e => setDraft({ ...draft, tags: e.target.value })}/></label></div><ModulePicker value={modules} onChange={setModules} disabled={!editable}/><label>Notes<textarea value={draft.notes || ""} disabled={!editable} onChange={e => setDraft({ ...draft, notes: e.target.value })}/></label><small>Consent: {row.consent_evidence}</small>{editable && <><label>Change reason<input value={reason} onChange={e => setReason(e.target.value)} required minLength={3}/></label><button className="po-primary" disabled={busy}>Save applicant changes</button></>}
      <div className="po-actions">{editable && <button type="button" onClick={() => operation("under_review")}>Start review</button>}{allowed(me, "signup.archive") && <button type="button" onClick={() => operation(row.archived_at ? "restore" : "archive")}>{row.archived_at ? "Restore request" : "Archive request"}</button>}{allowed(me, "signup.delete") && <><button type="button" onClick={() => operation("legal_hold", { enabled: !row.legal_hold })}>{row.legal_hold ? "Release legal hold" : "Set legal hold"}</button>{row.archived_at && !row.company_id && <button type="button" className="po-danger" onClick={() => setPurgeConfirm(true)}>Purge after retention</button>}</>}<button type="button" onClick={async () => { try {
            const { data } = await api.post(`/platform/signups/${row.id}/tracking-link`);
            setNotice(`Private status link: ${data.url}`);
        }
        catch (err) {
            setError(message(err));
        } }}>Prepare status link</button></div>{purgeConfirm && <section className="po-note" role="alert"><strong>Permanently purge applicant personal data?</strong><p>This cannot be undone. Retention and legal hold checks still apply to request #{row.id}.</p><button type="button" className="po-danger" disabled={busy} onClick={async () => { setPurgeConfirm(false); await operation("delete"); }}>Confirm permanent purge</button><button type="button" onClick={() => setPurgeConfirm(false)}>Cancel purge</button></section>}</form>}
    {tab === "review" && <div className="po-form">{!!row.duplicates.length && <section className="po-note"><h3>Possible duplicates</h3>{row.duplicates.map((r: Data) => <p key={r.id}>#{r.id} · {r.name} · {r.match} · {r.status}</p>)}</section>}{["pending", "under_review", "awaiting_applicant"].includes(row.status) && allowed(me, "signup.review") ? <>
      <fieldset><legend>Review checklist</legend>{[["identity", "Business / applicant identity reviewed"], ["duplicates", "Possible duplicate records checked"], ["modules", "Requested applications checked"]].map(([key, label]) => <label className="po-check" key={key}><input type="checkbox" checked={!!draft.checklist[key]} onChange={e => setDraft({ ...draft, checklist: { ...draft.checklist, [key]: e.target.checked } })}/>{label}</label>)}<button disabled={busy} onClick={async () => { try {
                await api.patch(`/platform/signups/${row.id}`, { version: row.version, reason: "Review checklist completed", checklist: draft.checklist });
                refresh();
            }
            catch (err) {
                setError(message(err));
            } }}>Save checklist</button></fieldset>
      <label>Reason template<select defaultValue="" onChange={e => { const t = templates.data?.find(t => t.id === Number(e.target.value)); if (t)
                setReason(t.data.body || t.title); }}><option value="">Choose a template</option>{templates.data?.filter(t => t.state !== "archived").map(t => <option key={t.id} value={t.id}>{t.title}</option>)}</select></label><form className="po-form" onSubmit={async (e) => { e.preventDefault(); setBusy(true); setError(""); const f = new FormData(e.currentTarget); try {
                const { data } = await api.post(`/platform/signups/${row.id}/review`, { decision, reason, modules, trial_days: Number(f.get("trial_days") || 14), seats: Number(f.get("seats") || 5), storage_mib: Number(f.get("storage_mib") || 1024) });
                setNotice(data.invitation_url ? `Approved. Local invitation: ${data.invitation_url}` : "Review saved.");
                refresh();
            }
            catch (err) {
                setError(message(err));
            }
            finally {
                setBusy(false);
            } }}><label>Decision<select value={decision} onChange={e => setDecision(e.target.value)}><option value="approve">Approve trial</option><option value="reject">Reject application</option></select></label>{decision === "approve" && <><ModulePicker value={modules} onChange={setModules}/><div className="po-form-grid"><label>Trial days<input name="trial_days" type="number" min={1} max={90} defaultValue={me.settings.trial_days} required/></label><label>Seats<input name="seats" type="number" min={1} max={10000} defaultValue={me.settings.seats} required/></label><label>Storage allowance (MiB)<input name="storage_mib" type="number" min={100} max={1048576} defaultValue={me.settings.storage_mib} required/></label></div></>}<label>Review reason<textarea value={reason} onChange={e => setReason(e.target.value)} required minLength={3}/></label><div className="po-actions"><button className="po-primary" disabled={busy}>Confirm {decision === "approve" ? "approval" : "rejection"}</button><button type="button" disabled={busy || reason.length < 3} onClick={async () => { try {
                const { data } = await api.post(`/platform/signups/${row.id}/request-info`, { action: "request_info", reason });
                setNotice(`Correction link prepared: ${data.url}`);
                refresh();
            }
            catch (err) {
                setError(message(err));
            } }}>Request more information</button></div></form></> : <p>This application has no pending review action.</p>}{row.records?.filter((r: Data) => r.kind === "provisioning").map((r: Data) => <section key={r.id} className="po-note"><h3>{r.title} · {r.state}</h3>{r.data.steps && <div className="po-progress">{r.data.steps.map((x: string) => <span key={x}>{x}</span>)}</div>}{r.data.error && <p>{r.data.error}</p>}</section>)}</div>}
    {tab === "notes" && <><form className="po-form" onSubmit={async (e) => { e.preventDefault(); const f = new FormData(e.currentTarget); try {
        await api.post("/platform/records/note", { title: f.get("title"), signup_id: row.id, data: { body: f.get("body") } });
        refresh();
    }
    catch (err) {
        setError(message(err));
    } }}><label>Note title<input name="title" required minLength={2}/></label><label>Note<textarea name="body" required/></label><button>Add internal note</button></form><div className="po-timeline">{row.records?.filter((r: Data) => r.kind === "note").map((r: Data) => <article key={r.id}><strong>{r.title}</strong><p>{r.data.body}</p><small>{date(r.created_at)}</small></article>)}</div></>}
    {tab === "activity" && <div className="po-timeline">{row.history?.map((r: Data) => <article key={r.id}><strong>{r.action.split(".").join(" · ")}</strong><small> · {date(r.created_at)}</small><p>{r.reason}</p>{Object.keys(r.after || {}).filter(k => JSON.stringify(r.after[k]) !== JSON.stringify(r.before?.[k])).map(key => <small key={key}>{key.split("_").join(" ")}: {typeof r.after[key] === "object" ? JSON.stringify(r.after[key]) : String(r.after[key] ?? "—")}<br /></small>)}</article>)}</div>}
  </>;
}
