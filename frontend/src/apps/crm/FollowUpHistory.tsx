import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { History, RefreshCw, Clock3, CheckCircle2, UserRound } from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useDebounced } from "@/shared/catalog/api";
import "./follow-up-history.css";

type Person = { id: number; name: string; email: string };
type State = { id: number; title: string; status: string; owner_id?: number; due_at?: string; reminder_at?: string; priority?: string };
type Item = { id: number; entity: string; record_id: number; record_name: string; title: string; status: string; occurred_at?: string; due_at?: string; completed_at?: string; pending_since?: string; pending_seconds?: number; overdue_since?: string; actor?: Person; completed_by?: Person; assignee?: Person; last_updated_by?: Person; notes?: string; metadata: { before?: State; after?: State; next_follow_up?: State; changes?: {before: State; after: State}[]; owner_id?: number; nextFollowUp?: string; outcome?: string } };
type Result = { items: Item[]; total: number; page: number; pages: number; employees: Person[]; people?: Person[]; as_of: string };
type RecordScope = { entity: string; id: number; name: string };
const stamp = (value?: string) => value ? new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "Not recorded";
const personName = (person?: Person) => person?.name || "Not recorded";
function elapsed(seconds = 0) { const minutes = Math.floor(seconds / 60), hours = Math.floor(minutes / 60), days = Math.floor(hours / 24); return days ? `${days}d ${hours % 24}h` : hours ? `${hours}h ${minutes % 60}m` : minutes ? `${minutes}m` : "Just created"; }

export function FollowUpHistoryButton({ entity }: { entity: string }) {
  const [open, setOpen] = useState(false);
  return <><Button size="sm" variant="outline" onClick={() => setOpen(true)}><History size={15}/>Follow-up history</Button>{open && <Dialog open onOpenChange={setOpen}><DialogContent className="fu-history-dialog"><DialogTitle>Follow-up history</DialogTitle><p className="text-sm text-muted-foreground">Track waiting time, assignments and the work recorded by each employee.</p><FollowUpHistory entity={entity}/></DialogContent></Dialog>}</>;
}

export default function FollowUpHistory({ entity, record, revision = 0 }: { entity: string; record?: RecordScope; revision?: number }) {
  const user = useAuthStore(state => state.user);
  const [view, setView] = useState(record ? "history" : "pending"), [employee, setEmployee] = useState(""), [search, setSearch] = useState(""), [page, setPage] = useState(1);
  const term = useDebounced(search);
  const scope = `${user?.id}:${user?.access?.companyId}:${sessionStorage.getItem("suite-branch")}`;
  const query = useQuery({ queryKey: ["followup-history", scope, entity, record?.id, view, employee, term, page, revision], queryFn: async () => (await api.get<Result>("/crm/growth/history", {params: {entity: record?.entity || entity, record_id: record?.id, view, employee_id: employee || undefined, search: term || undefined, page, per_page: 20}})).data, staleTime: 0 });
  const people = new Map((query.data?.people || query.data?.employees)?.map(person => [person.id, person.name]) || []);
  const ownerName = (id?: number) => id ? people.get(id) || `Employee #${id}` : "Unassigned";
  const changes = (before?: State, after?: State) => {
    if (!after) return null;
    const values = [
      ["Due", before?.due_at, after.due_at, stamp(before?.due_at), stamp(after.due_at)],
      ["Assigned to", before?.owner_id, after.owner_id, ownerName(before?.owner_id), ownerName(after.owner_id)],
      ["Reminder", before?.reminder_at, after.reminder_at, stamp(before?.reminder_at), stamp(after.reminder_at)],
      ["Status", before?.status, after.status, before?.status, after.status],
      ["Priority", before?.priority, after.priority, before?.priority, after.priority],
    ].filter(([, oldValue, newValue]) => oldValue !== newValue && (before || newValue != null));
    return <dl className="fuh-changes">{values.map(([label, , , oldValue, newValue]) => <div key={String(label)}><dt>{label}</dt><dd>{before && <><span className="fuh-previous">{oldValue || "None"}</span><span aria-label="changed to"> → </span></>}<strong>{newValue || "None"}</strong></dd></div>)}</dl>;
  };
  return <section className={`fu-history ${record ? "embedded" : ""}`} aria-label={record ? `Follow-up history: ${record.name}` : "Follow-up history workspace"}>
    <div className="fuh-tabs" role="tablist" aria-label="Follow-up history view">{[["pending", "Pending"], ["completed", "Completed"], ["history", "Employee activity"]].map(([key, title]) => <button role="tab" aria-selected={view === key} key={key} onClick={() => {setView(key); setPage(1); setEmployee("");}}>{title}</button>)}</div>
    <div className="fuh-filters">{!record && <Input aria-label="Search follow-up history" placeholder="Search relationship name…" value={search} onChange={event => {setSearch(event.target.value); setPage(1);}}/>}<NativeSelect aria-label={view === "history" ? "Performed by employee" : "Assigned employee filter"} value={employee} onChange={event => {setEmployee(event.target.value); setPage(1);}}><option value="">{view === "history" ? "Performed by any employee" : "Assigned to any employee"}</option>{query.data?.employees.map(person => <option key={person.id} value={person.id}>{person.name}</option>)}</NativeSelect><Button variant="outline" size="icon" aria-label="Refresh follow-up history" onClick={() => void query.refetch()}><RefreshCw size={15}/></Button></div>
    {query.isPending && <p role="status" className="fuh-empty">Loading follow-up history…</p>}
    {query.error && <p role="alert" className="text-destructive">Could not load history. Refresh to try again.</p>}
    {query.data && <><p className="fuh-count">{query.data.total} {view === "history" ? "recorded actions" : `${view} follow-up${query.data.total === 1 ? "" : "s"}`} · updated {stamp(query.data.as_of)}</p><div className={view === "history" ? "fuh-timeline" : "fuh-cards"}>
      {query.data.items.map(item => view === "history" ? <article className="fuh-event" key={item.id}><span className="fuh-event-icon"><History size={15}/></span><div><header><strong>{item.title}</strong><time>{stamp(item.occurred_at)}</time></header><p className="fuh-actor"><UserRound size={13}/><strong>{personName(item.actor)}</strong></p>{!record && <p className="fuh-record">{item.record_name} · {item.entity}</p>}{item.metadata.after?.title && <p className="fuh-purpose">{item.metadata.after.title}</p>}{changes(item.metadata.before, item.metadata.after)}{item.metadata.changes?.map(change => <div key={change.after.id}><small>Follow-up #{change.after.id} · {change.after.title}</small>{changes(change.before, change.after)}</div>)}{!item.metadata.after && !item.metadata.changes && <div className="fuh-legacy">{item.metadata.nextFollowUp && <p>Next conversation: {stamp(item.metadata.nextFollowUp)}</p>}{item.metadata.owner_id && <p>Assigned to {ownerName(item.metadata.owner_id)}</p>}<small>Earlier values were not recorded for this action.</small></div>}{item.metadata.outcome && <p>Outcome: {item.metadata.outcome}</p>}{item.notes && <p className="fuh-notes">{item.notes}</p>}{item.metadata.next_follow_up && <p className="fuh-next">Next follow-up: {stamp(item.metadata.next_follow_up.due_at)} · {ownerName(item.metadata.next_follow_up.owner_id)}</p>}</div></article> : <article className="fuh-card" key={item.id}><header><div>{!record && <p className="fuh-record">{item.record_name}</p>}<h3>{item.title}</h3></div><span className={item.overdue_since ? "fuh-status overdue" : "fuh-status"}>{item.overdue_since ? "Overdue" : view === "completed" ? "Completed" : "Pending"}</span></header>{view === "pending" ? <div className="fuh-age"><Clock3 size={17}/><strong>Waiting {elapsed(item.pending_seconds)}</strong><span>Pending since {stamp(item.pending_since)}</span></div> : <div className="fuh-age"><CheckCircle2 size={17}/><strong>Completed {stamp(item.completed_at)}</strong></div>}<dl><div><dt>Assigned employee</dt><dd>{item.assignee ? personName(item.assignee) : "Unassigned"}</dd></div><div><dt>Scheduled by</dt><dd>{personName(item.actor)}</dd></div><div><dt>Due</dt><dd>{stamp(item.due_at)}</dd></div>{item.overdue_since && <div><dt>Overdue since</dt><dd className="fuh-overdue">{stamp(item.overdue_since)}</dd></div>}{item.completed_by && <div><dt>Completed by</dt><dd>{personName(item.completed_by)}</dd></div>}{item.last_updated_by && !item.completed_by && <div><dt>Last updated by</dt><dd>{personName(item.last_updated_by)}</dd></div>}</dl>{item.notes && <p className="fuh-notes">{item.notes}</p>}</article>)}
    </div>{!query.data.items.length && <p className="fuh-empty">No {view === "history" ? "recorded employee actions" : `${view} follow-ups`} match these filters.</p>}<footer className="fuh-pagination"><Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(value => value-1)}>Previous</Button><span>Page {page} of {Math.max(1, query.data.pages)}</span><Button size="sm" variant="outline" disabled={page >= query.data.pages} onClick={() => setPage(value => value+1)}>Next</Button></footer></>}
  </section>;
}
