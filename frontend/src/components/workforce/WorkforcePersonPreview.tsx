import { PersonPreviewHeader } from "@/components/PersonPreviewDialog";
import { Home, Layers, CalendarDays, MessageSquare, ExternalLink, Plus, CircleDot, Users, Mail, BriefcaseBusiness, Flag, Bell, Check, ChevronRight, FileText } from "lucide-react";
import { recordPreviewProps } from "@/components/RecordQuickPreview";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import "./workforce.css";

type Row = Record<string, any>;
const errorMessage = (error: any) => typeof error?.response?.data?.detail === "string" ? error.response.data.detail : error.message || "The operation failed. Please retry.";
export default function WorkforcePersonPreview({ profile, root, taskPath, onClose, onFollowUp }: { profile: Row; root: string; taskPath: string; onClose: () => void; onFollowUp: () => void }) {
  const user = useAuthStore(s => s.user);
  const qc = useQueryClient();
  const [profileTab, setProfileTab] = useState("work");
  const [profilePage, setProfilePage] = useState(1);
  const [historyPage, setHistoryPage] = useState(1);
  const [resolution, setResolution] = useState({ id: 0, note: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  function refresh() { void qc.invalidateQueries({ queryKey: ["workforce"] }); }
  const { data: history, error: historyError } = useQuery<Row>({ queryKey: ["workforce", root, user?.id, "history", profile?.id, historyPage],
    queryFn: () => api.get(`${root}/people/${profile!.id}/history`, { params: { page: historyPage } }).then(r => r.data), enabled: !!profile });
  const { data: personWork, error: workError } = useQuery<Row>({ queryKey: ["workforce", root, user?.id, "work", profile?.id, profilePage],
    queryFn: () => api.get(`${root}/people/${profile!.id}/work`, { params: { page: profilePage } }).then(r => r.data), enabled: !!profile });
  return <Dialog open={!!profile} onOpenChange={open => { if (!open) onClose(); }}><DialogContent className="wf-preview">
      {profile && <>
        <PersonPreviewHeader name={String(profile.name)} identifier={profile.employee_id} status={`${profile.status || ""} ${profile.employment_type || ""}`} photoUrl={profile.profile_photo_url || profile.photo_url}/>
        <div className="wfp-tabs" role="tablist" aria-label="Profile sections" onKeyDown={event => { const ids = ["overview", "work", "follow", "notes"]; const index = ids.indexOf(profileTab); const next = event.key === "ArrowRight" ? ids[(index + 1) % 4] : event.key === "ArrowLeft" ? ids[(index + 3) % 4] : event.key === "Home" ? ids[0] : event.key === "End" ? ids[3] : null; if (next) { event.preventDefault(); setProfileTab(next); document.getElementById(`wfp-tab-${next}`)?.focus(); } }}>{[["overview", "Overview", Home], ["work", "Work & Progress", Layers], ["follow", "Follow-up", CalendarDays], ["notes", "Notes & Activity", MessageSquare]].map(([id, title, Icon]) => <button key={String(id)} id={`wfp-tab-${id}`} role="tab" tabIndex={profileTab === id ? 0 : -1} aria-selected={profileTab === id} aria-controls="wfp-panel" onClick={() => setProfileTab(String(id))}><Icon size={23}/>{String(title)}</button>)}</div>
        <div className="wfp-body wf-space">
          <dl className="wfp-facts">{[[Layers, "Department", profile.department], [Users, "Supervisor", profile.manager], [Mail, "Email", profile.email], [BriefcaseBusiness, "Employment", profile.employment_type]].map(([Icon, label, value]) => <div key={String(label)}><Icon size={21}/><div><dt>{String(label)}</dt><dd>{value || "Not assigned"}</dd></div></div>)}</dl>
          <div className="wf-actions wfp-actions"><Link className="wf-button wfp-primary" to={`/hrms/employees/${profile.id}`}><ExternalLink size={18}/>Full HRMS Profile</Link><Link className="wf-button" to={taskPath} state={{ employee_ids: [profile.id] }}><Plus size={21}/>Assign Work</Link><button onClick={() => { onFollowUp(); }}><CircleDot size={20}/>Select for Follow-up</button></div>
          <div id="wfp-panel" role="tabpanel" aria-labelledby={`wfp-tab-${profileTab}`} className="wfp-columns">
            <section className="wfp-card">
              {(profileTab === "work" || profileTab === "overview") && <><h2><Layers/>Work & Progress</h2>{workError && <p role="alert" className="wf-error">{errorMessage(workError)}</p>}
                {!personWork && !workError && <p role="status" className="wf-muted">Loading assignments…</p>}
                <div className="wf-table wfp-work"><table><thead><tr><th aria-label="Assignment icon"/><th>Assignment</th><th>Progress</th><th>Status</th><th>Due date</th></tr></thead><tbody>{personWork?.items.map((task: Row) => <tr {...recordPreviewProps(task)} key={task.id}><td><FileText size={16}/></td><td><Link to={`/pms/projects/${task.project_id}/tasks/${task.id}`}>{task.title}</Link></td><td><div className="wfp-progress"><progress aria-label={`Progress for ${task.title}`} max="100" value={task.progress || 0}/><span>{task.progress || 0}%</span></div></td><td><span className={`wfp-status wfp-status-${String(task.status).toLowerCase().replace(/\s+/g, "-")}`}>{task.status === "Done" && <Check size={13}/>} {task.status}</span></td><td><span className="wfp-date"><CalendarDays size={15}/>{task.due_date || "No deadline"}</span>{task.overdue && <small className="wf-error">Overdue</small>}</td></tr>)}</tbody></table>{personWork?.total === 0 && <p className="wf-muted">No assignments in projects you can access.</p>}</div>
                {(personWork?.total > 20 || profilePage > 1) && <div className="wf-actions"><button disabled={profilePage === 1} onClick={() => setProfilePage(p => p - 1)}>Previous work</button><button disabled={!personWork || profilePage * 20 >= personWork.total} onClick={() => setProfilePage(p => p + 1)}>More work</button></div>}
              </>}
              {profileTab === "follow" && <><h2><Flag/>Follow-up</h2><p className="wf-muted">{profile.overdue ?? "—"} overdue assignments · {profile.review ?? "—"} awaiting review</p><Link className="wf-button" to={taskPath} state={{ employee_ids: [profile.id] }}>Review assigned work</Link></>}
              {profileTab === "notes" && <>
        <h2>Notices & warning history</h2>{historyError && <p role="alert" className="wf-error">{errorMessage(historyError)}</p>}<div className="wf-history">{history?.items.map((message: Row) => <article key={message.id} className={`wf-card ${message.kind === "warning" ? "wf-warning" : ""}`}>
          <strong>{message.title}</strong><small className="wf-muted"> · {message.kind} · {new Date(message.created_at).toLocaleString()}</small><p className="wf-message">{message.message}</p>
          <p>{message.acknowledged_at ? "Acknowledged" : "Awaiting acknowledgement"} · {message.resolved_at ? `Resolved: ${message.resolution}` : "Open"}</p>
          {!message.resolved_at && <div className="wf-row"><input aria-label={`Resolution for ${message.title}`} placeholder="Resolution note" value={resolution.id === message.id ? resolution.note : ""} onChange={e => setResolution({ id: message.id, note: e.target.value })} />
            <button disabled={busy || resolution.id !== message.id || resolution.note.trim().length < 3} onClick={async () => { setBusy(true); try { await api.post(`${root}/messages/${message.id}/resolve`, { note: resolution.note }); setResolution({ id: 0, note: "" }); refresh(); } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); } }}>Resolve</button></div>}
        </article>)}{history?.total === 0 && <p>No notices or warnings for this person.</p>}</div>
        <div className="wf-actions"><button disabled={historyPage === 1} onClick={() => setHistoryPage(p => p - 1)}>Previous messages</button><button disabled={!history || historyPage * 25 >= history.total} onClick={() => setHistoryPage(p => p + 1)}>More messages</button></div>
              </>}
            </section>
            <aside className="wfp-sidebar"><section className="wfp-card"><button className="wfp-summary-title" onClick={() => setProfileTab("follow")}><Flag size={22}/><strong>Follow-up Summary</strong><ChevronRight size={18}/></button><div className="wfp-summary-row"><CircleDot size={17}/>Overdue work<span>{profile.overdue ?? "—"}</span></div><div className="wfp-summary-row"><Check size={17}/>Awaiting review<span>{profile.review ?? "—"}</span></div></section>
              <section className="wfp-card"><h2><Bell/>Notices & Warnings</h2>{historyError ? <p role="alert" className="wf-error">{errorMessage(historyError)}</p> : !history ? <p role="status">Loading notices…</p> : history.total === 0 ? <div className="wfp-clear"><span><Check size={23}/></span><p>No notices or warnings<br/>for this person.</p></div> : <button className="wfp-notice-link" onClick={() => setProfileTab("notes")}>View notices & warning history <span className="wf-pill">{history.total}</span><ChevronRight size={16}/></button>}</section>
            </aside>
          </div>
          {error && <p role="alert" className="wf-error">{error}</p>}
        </div>
      </>}
    </DialogContent></Dialog>;
}
