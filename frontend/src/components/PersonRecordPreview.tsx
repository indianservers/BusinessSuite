import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Layers, Users, Mail, BriefcaseBusiness, ExternalLink, Flag, Bell, Search, MessageSquare } from "lucide-react";
import PersonPreviewDialog from "./PersonPreviewDialog";
import { Fields, label, privateField } from "./RecordPreviewFields";
export function isPersonRecord(record: Record<string, unknown>, path: string) {
  const personShape = !!((record.first_name || record.full_name || record.name || record.display_name) && (record.email || record.personal_email || record.work_email) && (record.role || record.classification || record.employment_type));
  if (!personShape && /\/(companies|accounts|deals|quotations|tasks|projects|parties|sales-orders|invoices)(?:\/|$)/.test(path)) return false;
  if (record.task_key || record.project_key || record.assignment_id || record.employee_count != null || record.entity_type === "company" || record.type === "Company") return false;
  if (/^\/crm\/(contacts|leads)(?:\/|$)/.test(path)) return !!(record.name || record.full_name || record.first_name || record.email);
  if ((record.employee_id || record.employee_code) && (record.name || record.first_name || record.full_name) && (record.employment_type || record.classification)) return true;
  if (/\/(people|users|user-accounts|recruitment)(?:\/|$)/.test(path)) return !!(record.name || record.full_name || record.first_name || record.email);
  return !!((record.first_name || record.full_name || record.display_name || record.name) && (record.email || record.personal_email || record.work_email) && !record.title && !record.subject && !record.company_name && !record.invoice_number);
}
export default function PersonRecordPreview({ record: input, related, onClose, fullProfileHref, actions, overview, work, followUp, activity, financial, sidebar, loading, error, photoUrl, onCloseAutoFocus }: { record: object; related?: unknown; onClose: () => void; fullProfileHref?: string; actions?: ReactNode; overview?: ReactNode; work?: ReactNode; followUp?: ReactNode; activity?: ReactNode; financial?: ReactNode; sidebar?: ReactNode; loading?: boolean; error?: string; photoUrl?: string | null; onCloseAutoFocus?: (event: Event) => void }) {
  const record = input as Record<string, unknown>;
  const [query, setQuery] = useState("");
  const text = (value: unknown) => typeof value === "string" || typeof value === "number" ? String(value) : undefined;
  const name = text(record.name || record.full_name || record.display_name) || [text(record.first_name), text(record.last_name)].filter(Boolean).join(" ") || text(record.email) || "Person profile";
  const entries = Object.entries(record).filter(([key]) => !privateField.test(key));
  const notes = /note|activity|timeline|history|interaction/i;
  const follow = /follow|next_action|reminder/i;
  const relationships = /workspace|project|team|batch|assignment|task|skill|membership|related/i;
  const group = (pattern: RegExp) => Object.fromEntries(entries.filter(([key]) => pattern.test(key)));
  const section = (value: unknown, empty: string) => value && typeof value === "object" && Object.keys(value).length ? <Fields value={value}/> : <p className="wf-muted">{empty}</p>;
  const status = text(record.status) || (typeof record.is_active === "boolean" ? record.is_active ? "Active" : "Inactive" : undefined);
  const nextFollowUp = text(record.nextFollowUp || record.next_follow_up_at || record.next_follow_up);
  const facts = [[Layers, "Department / Organization", text(record.department || record.department_name || record.organization || record.company_name)], [Users, "Supervisor / Owner", text(record.manager || record.reporting_manager_name || record.owner_name) || (record.ownerId ? `User #${record.ownerId}` : undefined)], [Mail, "Email", text(record.email || record.work_email || record.personal_email)], [BriefcaseBusiness, "Role / Classification", text(record.employment_type || record.classification || record.role)]] as const;
  const shared = <><dl className="wfp-facts">{facts.map(([Icon, title, value]) => <div key={title}><Icon size={21}/><div><dt>{title}</dt><dd>{value || "Not recorded"}</dd></div></div>)}</dl><div className="wf-actions wfp-actions">{fullProfileHref && <Link className="wf-button wfp-primary" to={fullProfileHref}><ExternalLink size={18}/>Full profile</Link>}{text(record.email || record.work_email || record.personal_email) && <a className="wf-button" href={`mailto:${text(record.email || record.work_email || record.personal_email)}`}><Mail size={18}/>Email</a>}{actions}</div>{loading && <p role="status">Loading complete profile…</p>}{error && <p role="alert" className="wf-error">{error}</p>}<label className="wfp-search"><Search size={17}/><input aria-label="Search profile fields" placeholder="Find a field or value…" value={query} onChange={e => setQuery(e.target.value)}/></label></>;
  const summary = sidebar || <><section className="wfp-card"><h2><Flag/>Follow-up Summary</h2><p className="text-sm">{nextFollowUp || "No follow-up date recorded."}</p></section><section className="wfp-card"><h2><Bell/>Profile status</h2><p className="text-sm">{status || "No status recorded."}</p></section></>;
  const panel = (title: string, content: ReactNode) => <>{shared}<div className="wfp-columns"><section className="wfp-card"><h2><Layers/>{query ? "Search results" : title}</h2>{query ? <Fields value={Object.fromEntries(entries.filter(([key, value]) => label(key).toLowerCase().includes(query.toLowerCase()) || JSON.stringify(value)?.toLowerCase().includes(query.toLowerCase())))}/> : content}</section><aside className="wfp-sidebar">{summary}</aside></div></>;
  return <PersonPreviewDialog name={name} identifier={text(record.employee_id || record.employee_code) || (record.id != null ? `#${record.id}` : undefined)} status={[status, text(record.employment_type || record.classification)].filter(Boolean).join(" · ")} photoUrl={photoUrl || text(record.profile_photo_url || record.photo_url)} onClose={onClose} onCloseAutoFocus={onCloseAutoFocus} tabs={[
    {id:"overview",label:"Overview",content:panel("Profile overview",overview || <Fields value={Object.fromEntries(entries)}/>)},
    {id:"work",label:"Work & Relationships",content:panel("Work & Relationships",work || section(related || group(relationships), "No work or relationship information is available in this preview."))},
    {id:"follow",label:"Follow-up",content:panel("Follow-up",followUp || section(group(follow), "No follow-up information is recorded."))},
    ...(financial ? [{id:"financial",label:"Financial data",content:panel("Financial data",financial)}] : []),
    {id:"notes",label:"Notes & Activity",icon:MessageSquare,content:panel("Notes & Activity",activity || section(group(notes), "No notes or activity are recorded."))},
  ]}/>;
}
