import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarDays, ChevronRight, Layers, RefreshCw } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import BranchSwitcher from "@/components/suite/BranchSwitcher";
import { normalizePriority } from "@/shared/priority/priority";
import "@/shared/priority/priority.css";
import { emptyWorkflowFilters, filterWorkflowRecords, formatWorkflowMoney, sortWorkflowRecords, workflowBadges, workflowFacets, workflowTotal, type WorkflowData, type WorkflowFilters, type WorkflowRecord } from "./model";
import "./workflow-board.css";

type Props = {
  data?: WorkflowData;
  title: string;
  loading?: boolean;
  error?: string;
  onRefresh: () => void;
  onChangeStage?: (record: WorkflowRecord) => void;
};

/** Compact dashboard presentation. Domain adapters own all reads and mutations. */
export function WorkflowBoard({ data, title, loading, error, onRefresh, onChangeStage }: Props) {
  const [filters, setFilters] = useState<WorkflowFilters>(emptyWorkflowFilters);
  const [listStage, setListStage] = useState<string | null>(null);
  const [now, setNow] = useState(() => new Date());
  useEffect(() => { const timer = window.setInterval(() => setNow(new Date()), 60_000); return () => window.clearInterval(timer); }, []);
  const records = data?.records || [];
  const filtered = sortWorkflowRecords(filterWorkflowRecords(records, filters), now);
  const owners = workflowFacets(records, "owners"), teams = workflowFacets(records, "teams");
  const invalid = !!filters.from && !!filters.to && filters.from > filters.to;
  const update = (key: keyof WorkflowFilters, value: string) => setFilters(f => ({ ...f, [key]: value }));
  const selectedStage = data?.stages.find(s => s.id === listStage);
  const list = listStage === "all" ? filtered : filtered.filter(r => r.stageId === listStage);
  const unavailable = loading || !!error;
  return <section className="workflow-board" aria-label={data?.title || title} aria-busy={loading}>
    <header className="workflow-board-heading">
      <h2><Layers size={18} />{data?.title || title}</h2>
      <div><button type="button" disabled={loading} aria-label={`Refresh ${title}`} onClick={onRefresh}><RefreshCw size={14} /></button>
        <button type="button" disabled={!data || unavailable} onClick={() => setListStage("all")}>View all <ChevronRight size={14} /></button></div>
    </header>
    <div className="workflow-board-filters">
      <BranchSwitcher />
      <label>Team<select aria-label="Team" value={filters.team} disabled={!data || unavailable} onChange={e => update("team", e.target.value)}><option value="">All teams</option>{teams.map(f => <option key={f.id} value={f.id}>{f.label}</option>)}<option value="__unassigned">No team assigned</option></select></label>
      <label>Owner<select aria-label="Owner" value={filters.owner} disabled={!data || unavailable} onChange={e => update("owner", e.target.value)}><option value="">All owners</option>{owners.map(f => <option key={f.id} value={f.id}>{f.label}</option>)}<option value="__unassigned">Unassigned</option></select></label>
      <label>{data?.dateLabel || "Date"} from<input aria-label={`${data?.dateLabel || "Date"} from`} type="date" value={filters.from} max={filters.to || undefined} onChange={e => update("from", e.target.value)} /></label>
      <label>To<input aria-label="To" type="date" value={filters.to} min={filters.from || undefined} onChange={e => update("to", e.target.value)} /></label>
      <button type="button" onClick={() => setFilters(emptyWorkflowFilters)} disabled={!Object.values(filters).some(Boolean)}>Clear filters</button>
    </div>
    {invalid && <p className="workflow-board-error" role="alert">From date must be on or before To date.</p>}
    {error ? <p className="workflow-board-error" role="alert">{error} <button type="button" onClick={onRefresh}>Retry</button></p> : loading ? <p className="workflow-board-state" role="status">Loading workflow…</p> : data && <>
      <p className="workflow-board-caption">{filtered.length} of {records.length} loaded records · Urgent items first. {data.note}{data.truncated && <> Showing a limited set; counts and totals cover loaded records. <Link to={data.workspaceHref}>Open full workspace</Link>.</>}</p>
      <div className="workflow-board-lanes" tabIndex={0} role="region" aria-label={`${data.title} stages`}>
        {data.stages.map((stage, index) => {
          const rows = filtered.filter(r => r.stageId === stage.id);
          return <section className={`workflow-board-lane workflow-tone-${index % 6}`} key={stage.id} aria-label={`${stage.name} stage`}>
            <button type="button" className="workflow-board-stage" onClick={() => setListStage(stage.id)} aria-label={`View ${stage.name}: ${rows.length} records`}><span><strong>{stage.name}</strong><b>{rows.length}</b></span><small>{workflowTotal(rows, data.totalLabel)}</small></button>
            <div className="workflow-board-cards">{rows.slice(0, 3).map(record => <WorkflowCard key={record.id} record={record} now={now} onChangeStage={onChangeStage} />)}{!rows.length && <p className="workflow-board-empty">No matching records</p>}</div>
            <button type="button" className="workflow-board-view" aria-label={`View all ${stage.name} records`} onClick={() => setListStage(stage.id)}>View all{rows.length ? ` (${rows.length})` : ""} <ChevronRight size={13} /></button>
          </section>;
        })}
      </div>
      <p className="workflow-board-caption">Branch uses your suite access scope. Team and owner filters use recorded assignments; records without assignments remain unassigned. Date filters exclude undated records. Open a record to review its workflow rules.</p>
    </>}
    <Dialog open={listStage !== null && !!data && !unavailable} onOpenChange={open => { if (!open) setListStage(null); }}><DialogContent className="workflow-board-dialog max-w-3xl"><DialogTitle>{selectedStage?.name || data?.title} — filtered records</DialogTitle><DialogDescription>Current branch, team, owner and date filters apply. {list.length} loaded records. {data?.truncated ? "This is a limited set; open the full workspace for all records." : ""}</DialogDescription>
      <div className="workflow-board-list">{list.map(r => <WorkflowCard key={r.id} record={r} now={now} onChangeStage={onChangeStage} />)}{!list.length && <p>No matching records. Adjust the board filters.</p>}</div>
      {data && <Link className="workflow-board-workspace" to={data.workspaceHref}>Open full workspace <ChevronRight size={14} /></Link>}
    </DialogContent></Dialog>
  </section>;
}

function WorkflowCard({ record, now, onChangeStage }: { record: WorkflowRecord; now: Date; onChangeStage?: Props["onChangeStage"] }) {
  const badges = workflowBadges(record, now);
  const priority = normalizePriority(record.priority);
  return <article className="workflow-board-card" data-priority-row data-priority={priority}>
    <Link to={record.href} className="workflow-board-record">
      <strong title={record.title}>{record.title}</strong>{record.subtitle && <span title={record.subtitle}>{record.subtitle}</span>}
      {record.amount != null && <span>{formatWorkflowMoney(record.amount, record.currency)}</span>}
      {record.effort != null && <span>{record.effort} h estimated</span>}
      {priority && <span><span data-priority-badge data-priority={priority}>{record.priority}</span></span>}
      {badges.length > 0 && <span className="workflow-board-badges">{badges.map(b => <em key={b} className={b === "Overdue" ? "workflow-badge-overdue" : b === "Blocked" ? "workflow-badge-blocked" : "workflow-badge-approval"}>{b}</em>)}</span>}
      <small><CalendarDays size={12} />{record.date ? new Date(/^\d{4}-\d{2}-\d{2}$/.test(record.date) ? `${record.date}T12:00:00` : record.date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "No date"}</small>
      <small title={record.owners.map(o => o.label).join(", ")}>{record.owners.map(o => o.label).join(", ") || "Unassigned"}</small>
    </Link>
    {record.canChangeStage && onChangeStage && <button type="button" className="workflow-board-change" onClick={() => onChangeStage(record)}>Change stage</button>}
  </article>;
}
