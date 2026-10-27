import { useDeferredValue, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import "./workforce.css";

type Row = Record<string, any>;
const errorMessage = (error: any) => typeof error?.response?.data?.detail === "string" ? error.response.data.detail : error.message || "The operation failed. Please retry.";
const emptyFilters = { search: "", kind: "all", department_id: "", batch_id: "", manager_id: "", status: "", account_status: "" };
type Filters = typeof emptyFilters;
const modes = [["", "All people"], ["overdue", "Overdue work"], ["review", "Awaiting review"], ["unassigned", "No supervisor"], ["warnings", "Open warnings"]];

export default function WorkforceOperationsPage({ context = "pms" }: { context?: "pms" | "interns" }) {
  const user = useAuthStore(s => s.user);
  const qc = useQueryClient();
  const root = context === "pms" ? "/project-management/operations" : "/interns-hub/operations";
  const [filters, setFilters] = useState<Filters>({ ...emptyFilters, kind: context === "interns" ? "intern" : "all" });
  const search = useDeferredValue(filters.search);
  const [exception, setException] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number[]>([]);
  const [allFiltered, setAllFiltered] = useState(false);
  const [modal, setModal] = useState<"notice" | "warning" | "reassign" | null>(null);
  const [form, setForm] = useState({ title: "", message: "", severity: "normal", reporting_manager_id: "" });
  const [preview, setPreview] = useState<Row>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState("");
  const [profile, setProfile] = useState<Row>();
  const [profilePage, setProfilePage] = useState(1);
  const [historyPage, setHistoryPage] = useState(1);
  const [resolution, setResolution] = useState({ id: 0, note: "" });
  const [jobPage, setJobPage] = useState(1);
  const requestKey = useRef(crypto.randomUUID());
  const [views, setViews] = useState<Array<{ name: string; filters: Filters }>>([]);
  const [viewName, setViewName] = useState("");
  const viewKey = `workforce.views.${user?.id}.${context}`;
  useEffect(() => { try { setViews(JSON.parse(localStorage.getItem(viewKey) || "[]")); } catch { setViews([]); } }, [viewKey]);
  const params = Object.fromEntries(Object.entries({ ...filters, search }).filter(([, value]) => value !== ""));
  const selection = { ...params, all_filtered: allFiltered, employee_ids: selected };
  const { data, isLoading, error: loadError } = useQuery<Row>({ queryKey: ["workforce", root, "people", params, exception, page],
    queryFn: () => api.get(root + "/people", { params: { ...params, exception, page, per_page: 50 } }).then(r => r.data) });
  const { data: summary } = useQuery<Row>({ queryKey: ["workforce", root, "summary", filters.kind],
    queryFn: () => api.get(root + "/summary", { params: { kind: filters.kind } }).then(r => r.data) });
  const { data: options } = useQuery<Row>({ queryKey: ["workforce", "options"], queryFn: () => api.get("/interns-hub/management/options").then(r => r.data) });
  const { data: managers = [] } = useQuery<Row[]>({ queryKey: ["workforce", "managers"],
    queryFn: () => api.get(root + "/managers").then(r => r.data) });
  const { data: jobs } = useQuery<Row>({ queryKey: ["workforce", root, "jobs", jobPage],
    queryFn: () => api.get(root + "/jobs", { params: { page: jobPage } }).then(r => r.data), refetchInterval: 10000 });
  const { data: history, error: historyError } = useQuery<Row>({ queryKey: ["workforce", root, "history", profile?.id, historyPage],
    queryFn: () => api.get(`${root}/people/${profile!.id}/history`, { params: { page: historyPage } }).then(r => r.data), enabled: !!profile });
  const { data: personWork, error: workError } = useQuery<Row>({ queryKey: ["workforce", root, "work", profile?.id, profilePage],
    queryFn: () => api.get(`${root}/people/${profile!.id}/work`, { params: { page: profilePage } }).then(r => r.data), enabled: !!profile });
  function update(next: Partial<Filters>) { setFilters(f => ({ ...f, ...next })); setPage(1); setSelected([]); setAllFiltered(false); setPreview(undefined); }
  function refresh() { void qc.invalidateQueries({ queryKey: ["workforce"] }); void qc.invalidateQueries({ queryKey: ["intern-management"] }); }
  const count = allFiltered ? data?.total || 0 : selected.length;
  const rows: Row[] = data?.items || [];
  const taskPath = context === "pms" ? "/pms/batch-tasks" : "/hrms/interns/tasks";
  const batchPath = context === "pms" ? "/pms/batches" : "/hrms/interns/batches";
  async function openOperation(operation: typeof modal) {
    setError(""); setResult(""); setPreview(undefined); setBusy(true);
    try { const response = await api.post(root + "/preview", selection); setPreview(response.data); setModal(operation); setForm({ title: "", message: "", severity: operation === "warning" ? "important" : "normal", reporting_manager_id: "" }); requestKey.current = crypto.randomUUID(); }
    catch (error) { setError(errorMessage(error)); }
    finally { setBusy(false); }
  }
  return <div className="wf-space">
    <header className="wf-row wf-between"><div><p className="wf-eyebrow">PEOPLE · PROGRAMS · DELIVERY</p>
      <h1>{context === "interns" ? "Intern profiles & work" : "People & work management"}</h1>
      <p>Find people, study their workload, assign work and follow up from one place.</p></div>
      <div className="wf-actions"><Link className="wf-button" to={batchPath}>Groups & programs</Link><Link className="wf-button" to={taskPath}>Assign work</Link>
        <Link className="wf-button" to={context === "pms" ? "/pms/reviews" : "/hrms/interns/reviews"}>Review work</Link>
        <Link className="wf-button" to="/pms/my-notices">My notices</Link></div></header>
    <section aria-label="Workforce overview" className="wf-metrics">
      {[["", "People", summary?.people], ["overdue", "Overdue assignments", summary?.overdue], ["review", "Awaiting review", summary?.review], ["unassigned", "No supervisor", summary?.unassigned], ["warnings", "Open warnings", summary?.warnings]].map(([key, label, value]) =>
        <button key={String(key)} className="wf-card wf-metric" aria-pressed={exception === key} onClick={() => { setException(String(key)); setPage(1); setSelected([]); setAllFiltered(false); }}><span>{label}</span><strong>{typeof value === "number" ? value.toLocaleString() : "—"}</strong></button>)}
    </section>
    <section className="wf-card wf-dialog" aria-label="Find people">
      <div className="wf-filters">
        <label>Search people<input value={filters.search} placeholder="Name, employee ID or email" onChange={e => update({ search: e.target.value })} /></label>
        <label>People<select value={filters.kind} onChange={e => update({ kind: e.target.value })}><option value="all">All employees & interns</option><option value="intern">Interns</option><option value="employee">Other employees</option></select></label>
        <label>Department<select value={filters.department_id} onChange={e => update({ department_id: e.target.value })}><option value="">All departments</option>{options?.departments.map((d: Row) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
        <label>Batch or group<select value={filters.batch_id} onChange={e => update({ batch_id: e.target.value })}><option value="">All groups</option>{options?.batches.map((b: Row) => <option key={b.id} value={b.id}>{b.name}</option>)}</select></label>
        <label>Supervisor<select value={filters.manager_id} onChange={e => update({ manager_id: e.target.value })}><option value="">All supervisors</option>{managers.filter(m => m.id > 0).map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
        <label>Status<select value={filters.status} onChange={e => update({ status: e.target.value })}><option value="">All statuses</option>{["Active", "Probation", "Inactive", "Suspended", "Completed", "Resigned"].map(s => <option key={s}>{s}</option>)}</select></label>
        <label>Account<select value={filters.account_status} onChange={e => update({ account_status: e.target.value })}><option value="">All accounts</option><option value="active">Active accounts only</option><option value="missing">Missing or inactive accounts</option></select></label>
        <label>Action queue<select value={exception} onChange={e => { setException(e.target.value); setPage(1); setSelected([]); setAllFiltered(false); }}>{modes.map(([v, label]) => <option key={v} value={v}>{label}</option>)}</select></label>
        <label>Saved views<select value="" onChange={e => { const view = views[Number(e.target.value)]; if (view) { update(view.filters); setException(""); } }}><option value="">Choose a saved view</option>{views.map((v, i) => <option key={i} value={i}>{v.name}</option>)}</select></label>
      </div>
      <div className="wf-row"><input aria-label="Saved view name" placeholder="Name this view" maxLength={60} value={viewName} onChange={e => setViewName(e.target.value)} />
        <button disabled={!viewName.trim()} onClick={() => { const next = [...views.filter(v => v.name !== viewName.trim()), { name: viewName.trim(), filters }].slice(-20); setViews(next); localStorage.setItem(viewKey, JSON.stringify(next)); setViewName(""); }}>Save view on this device</button>
        <button onClick={() => { update({ ...emptyFilters, kind: context === "interns" ? "intern" : "all" }); setException(""); }}>Reset filters</button></div>
      <p className="wf-muted">Overview counts cover your authorized {filters.kind === "all" ? "people" : filters.kind === "intern" ? "interns" : "employees"}. The directory uses the filters above.</p>
    </section>
    {(error || loadError) && <p role="alert" className="wf-error">{error || errorMessage(loadError)}</p>}
    {result && <p role="status" className="wf-success">{result}</p>}
    <section className="wf-card">
      <div className="wf-row wf-between"><h2>{modes.find(m => m[0] === exception)?.[1]} <span className="wf-pill">{data?.total?.toLocaleString() || 0}</span></h2>
        <button onClick={refresh}>Refresh</button></div>
      <div className="wf-table wf-people"><table><thead><tr><th><input aria-label="Select this page" type="checkbox" checked={rows.length > 0 && rows.every(e => selected.includes(e.id))} disabled={allFiltered} onChange={e => setSelected(prev => e.target.checked ? Array.from(new Set([...prev, ...rows.map(r => r.id)])) : prev.filter(id => !rows.some(r => r.id === id)))} /></th>
        {["Person", "Department / Supervisor", "Status", "Work", "Follow up", "Profile"].map(h => <th key={h}>{h}</th>)}</tr></thead>
        <tbody>{rows.map(person => <tr key={person.id}><td><input type="checkbox" aria-label={`Select ${person.name}`} checked={allFiltered || selected.includes(person.id)} disabled={allFiltered} onChange={e => setSelected(prev => e.target.checked ? [...prev, person.id] : prev.filter(id => id !== person.id))} /></td>
          <td><strong>{person.name}</strong><small>{person.employee_id} · {person.employment_type}</small><small>{person.email || "No email"}</small></td>
          <td>{person.department || "No department"}<small>{person.manager || "No supervisor assigned"}</small></td>
          <td><span className="wf-pill">{person.status}</span><small>{person.account_active ? "Account active" : "No active account"}</small></td>
          <td>{person.done}/{person.assigned} completed<small>{person.overdue} overdue · {person.review} awaiting review</small></td>
          <td>{person.warnings ? `${person.warnings} open warnings` : "No open warnings"}</td>
          <td><button onClick={() => { setProfile(person); setProfilePage(1); setHistoryPage(1); setResolution({ id: 0, note: "" }); }}>Study profile</button></td></tr>)}</tbody></table></div>
      {isLoading && <p role="status">Loading people…</p>}
      {!isLoading && !rows.length && <p className="wf-muted">No people match this view. Adjust the filters or add people through HRMS.</p>}
      <footer className="wf-row wf-between"><span>Page {page} · 50 people per page</span><div className="wf-actions"><button disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</button><button disabled={!data || page * 50 >= data.total} onClick={() => setPage(p => p + 1)}>Next</button></div></footer>
    </section>
    {count > 0 && <section className="wf-card wf-toolbar wf-row" aria-label="Selected people actions"><strong>{count.toLocaleString()} selected</strong>
      {!exception && !allFiltered && <button onClick={() => { setAllFiltered(true); setSelected([]); }}>Select all {data?.total?.toLocaleString()} matching people</button>}
      <button disabled={busy} onClick={() => openOperation("reassign")}>Change supervisor</button><button disabled={busy} onClick={() => openOperation("notice")}>Send notice</button><button disabled={busy} onClick={() => openOperation("warning")}>Send warning</button>
      {!allFiltered && <Link className="wf-button" to={taskPath} state={{ employee_ids: selected }}>Assign work to selected</Link>}
      <button onClick={() => { setSelected([]); setAllFiltered(false); }}>Clear</button></section>}
    <section className="wf-card wf-dialog"><h2>Bulk operations</h2><p className="wf-muted">Large operations run in resumable chunks. Your selection is fixed when the operation starts.</p>
      {jobs?.items.map((job: Row) => <div key={job.id} className="wf-row wf-between"><span>#{job.id} · {job.operation} · <strong>{job.status}</strong> · {job.cursor}/{job.total}</span>
        {job.error && <span className="wf-error">{job.error}</span>}
        {job.status !== "Completed" && <button disabled={busy} onClick={async () => { setBusy(true); setError(""); try { await api.post(`${root}/jobs/${job.id}/continue`); refresh(); } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); } }}> {job.status === "Failed" ? "Retry next chunk" : "Process next chunk"}</button>}</div>)}
      {!jobs?.items.length && <p>No bulk operations yet.</p>}
      <div className="wf-actions"><button disabled={jobPage === 1} onClick={() => setJobPage(p => p - 1)}>Previous operations</button><button disabled={!jobs || jobPage * 25 >= jobs.total} onClick={() => setJobPage(p => p + 1)}>More operations</button></div>
    </section>
    <Dialog open={!!modal} onOpenChange={open => { if (!open && !busy) setModal(null); }}><DialogContent><DialogHeader><DialogTitle>{modal === "reassign" ? "Change reporting supervisor" : modal === "warning" ? "Send a warning" : "Send a notice"}</DialogTitle></DialogHeader>
      <form className="wf-space wf-dialog" onSubmit={async e => {
        e.preventDefault(); setBusy(true); setError("");
        try { const response = await api.post(root + "/jobs", { ...selection, operation: modal, ...form, reporting_manager_id: Number(form.reporting_manager_id) || null, request_key: requestKey.current, expected_total: preview?.total });
          setResult(`Operation #${response.data.id}: ${response.data.status} (${response.data.cursor}/${response.data.total}).`); setModal(null); setSelected([]); setAllFiltered(false); refresh(); }
        catch (error) { setError(errorMessage(error)); }
        finally { setBusy(false); }
      }}>
        <p><strong>{preview?.total} people</strong> will receive this change. {preview?.sample?.map((p: Row) => p.name).join(", ")}{(preview?.total || 0) > 10 ? ", …" : ""}</p>
        {modal === "reassign" ? <label>New reporting supervisor<select required value={form.reporting_manager_id} onChange={e => setForm(f => ({ ...f, reporting_manager_id: e.target.value }))}><option value="">Choose a supervisor</option>{managers.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label> : <>
          <label>Title<input required maxLength={200} value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} /></label>
          <label>Message<textarea required maxLength={3000} placeholder="Explain the issue, expected action and deadline." value={form.message} onChange={e => setForm(f => ({ ...f, message: e.target.value }))} /></label>
          <label>Priority<select value={form.severity} onChange={e => setForm(f => ({ ...f, severity: e.target.value }))}>{["normal", "important", "urgent"].map(s => <option key={s}>{s}</option>)}</select></label>
          <p>Delivered in the app. Recipients can acknowledge receipt; managers can record a resolution.</p>
        </>}
        {error && <p role="alert" className="wf-error">{error}</p>}
        <div className="wf-row"><button type="button" disabled={busy} onClick={() => setModal(null)}>Cancel</button><button className="wf-primary" disabled={busy || !preview?.total}>{busy ? "Starting…" : `Confirm for ${preview?.total || 0} people`}</button></div>
      </form>
    </DialogContent></Dialog>
    <Dialog open={!!profile} onOpenChange={open => { if (!open) setProfile(undefined); }}><DialogContent className="max-w-3xl"><DialogHeader><DialogTitle>{profile?.name}</DialogTitle></DialogHeader>
      {profile && <div className="wf-space max-h-[78vh] overflow-y-auto"><dl className="wf-profile">{[["Employee ID", profile.employee_id], ["Email", profile.email], ["Department", profile.department], ["Supervisor", profile.manager], ["Employment", profile.employment_type], ["Status", profile.status]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value || "Not assigned"}</dd></div>)}</dl>
        <div className="wf-actions"><Link className="wf-button" to={`/hrms/employees/${profile.id}`}>Full HRMS profile</Link><Link className="wf-button" to={taskPath} state={{ employee_ids: [profile.id] }}>Assign work</Link>
          <button onClick={() => { setSelected([profile.id]); setAllFiltered(false); setProfile(undefined); }}>Select for follow-up</button></div>
        <h2>Work & progress</h2>{workError && <p role="alert" className="wf-error">{errorMessage(workError)}</p>}
        <div className="wf-table"><table><thead><tr><th>Assignment</th><th>Status</th><th>Due</th></tr></thead><tbody>{personWork?.items.map((task: Row) => <tr key={task.id}><td><Link to={`/pms/projects/${task.project_id}/tasks/${task.id}`}>{task.title}</Link><small>{task.progress}% progress</small></td><td>{task.status}</td><td>{task.due_date || "No deadline"}{task.overdue && <small className="wf-error">Overdue</small>}</td></tr>)}</tbody></table>{personWork?.total === 0 && <p>No assignments in projects you can access.</p>}</div>
        <div className="wf-actions"><button disabled={profilePage === 1} onClick={() => setProfilePage(p => p - 1)}>Previous work</button><button disabled={!personWork || profilePage * 20 >= personWork.total} onClick={() => setProfilePage(p => p + 1)}>More work</button></div>
        <h2>Notices & warning history</h2>{historyError && <p role="alert" className="wf-error">{errorMessage(historyError)}</p>}<div className="wf-history">{history?.items.map((message: Row) => <article key={message.id} className={`wf-card ${message.kind === "warning" ? "wf-warning" : ""}`}>
          <strong>{message.title}</strong><small className="wf-muted"> · {message.kind} · {new Date(message.created_at).toLocaleString()}</small><p className="wf-message">{message.message}</p>
          <p>{message.acknowledged_at ? "Acknowledged" : "Awaiting acknowledgement"} · {message.resolved_at ? `Resolved: ${message.resolution}` : "Open"}</p>
          {!message.resolved_at && <div className="wf-row"><input aria-label={`Resolution for ${message.title}`} placeholder="Resolution note" value={resolution.id === message.id ? resolution.note : ""} onChange={e => setResolution({ id: message.id, note: e.target.value })} />
            <button disabled={busy || resolution.id !== message.id || resolution.note.trim().length < 3} onClick={async () => { setBusy(true); try { await api.post(`${root}/messages/${message.id}/resolve`, { note: resolution.note }); setResolution({ id: 0, note: "" }); refresh(); } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); } }}>Resolve</button></div>}
        </article>)}{history?.total === 0 && <p>No notices or warnings for this person.</p>}</div>
        <div className="wf-actions"><button disabled={historyPage === 1} onClick={() => setHistoryPage(p => p - 1)}>Previous messages</button><button disabled={!history || historyPage * 25 >= history.total} onClick={() => setHistoryPage(p => p + 1)}>More messages</button></div>
        {error && <p role="alert" className="wf-error">{error}</p>}
      </div>}
    </DialogContent></Dialog>
  </div>;
}
