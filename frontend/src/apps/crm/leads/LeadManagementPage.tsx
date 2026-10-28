import { useRefreshableEffect } from "@/lib/page-refresh";
import { RichTextField, RichTextContent, richTextPlainText } from "@/components/rich-text/LazyRichText";
import React, { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  Check,
  Download,
  FileSpreadsheet,
  LayoutGrid,
  List,
  Loader2,
  Mail,
  Phone,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  Users,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { useAuthStore } from "@/store/authStore";
import { PhoneInput } from "@/lib/validation/PhoneInput";
import {
  Bootstrap,
  ConversionPreview,
  ImportPreview,
  Lead,
  LeadDetails,
  LeadPatch,
  ListResult,
  Settings,
  download,
  errorMessage,
  leadsApi,
  publicUrl,
  captureEmbed,
} from "./api";
import "./leads.css";
import { LeadAnalyticsPanel } from "./LeadAnalyticsPanel";
import {
  FollowUpDialog,
  LeadTeamPanel,
  LeadWorkflowBoard,
} from "./LeadWorkflow";

const formatDate = (date?: string) =>
  date
    ? new Date(date).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "Not scheduled";
const dateInput = (date?: string | null) => {
  if (!date) return "";
  const d = new Date(date);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
};
const iso = (value: string) => (value ? new Date(value).toISOString() : null);
const emptyQualification = {
  need: "",
  budget: "",
  decisionMaker: "",
  timeline: "",
};
const queues = [
  ["all", "All leads"],
  ["my_day", "My day"],
  ["active", "Active"],
  ["sla", "SLA missed"],
  ["untouched", "Untouched"],
  ["overdue", "Overdue"],
  ["stale", "Inactive"],
  ["unassigned", "Enquiry inbox"],
  ["reactivation", "Review due"],
  ["archived", "Archived"],
];
type SavedView = {
  name: string;
  search: string;
  stage: string;
  owner: string;
  queue: string;
  view: string;
};

function ErrorNotice({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div className="lm-error" role="alert">
      {message}
      {retry && (
        <Button size="sm" variant="outline" onClick={retry}>
          Try again
        </Button>
      )}
    </div>
  );
}
function StageBadge({ stage }: { stage: string }) {
  return (
    <span
      className={`lm-stage lm-stage-${stage.toLowerCase().replace(/[^a-z]/g, "")}`}
    >
      {stage}
    </span>
  );
}
function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  const controlId = React.useId();
  return (
    <div className="lm-field">
      <label htmlFor={controlId}>{label}</label>
      {React.isValidElement(children)
        ? React.cloneElement(children as React.ReactElement<{ id?: string }>, {
            id: controlId,
          })
        : children}
    </div>
  );
}

export default function LeadManagementPage() {
  const { toast } = useToast();
  const userId = useAuthStore((s) => s.user?.id);
  const [params, setParams] = useSearchParams();
  const [bootstrap, setBootstrap] = useState<Bootstrap>();
  const [result, setResult] = useState<ListResult>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [selected, setSelected] = useState<number[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [insights, setInsights] = useState(false);
  const [busy, setBusy] = useState(false);
  const [followUp, setFollowUp] = useState<{ lead: Lead; date?: string }>();
  const [bulk, setBulk] = useState<{
    patch: LeadPatch;
    items: { id: number; name: string; stage: string }[];
  }>();
  const [bulkAction, setBulkAction] = useState("");
  const [savedViews, setSavedViews] = useState<SavedView[]>(() => {
    try {
      return JSON.parse(sessionStorage.getItem(`lead-views-${userId}`) || "[]");
    } catch {
      return [];
    }
  });
  const [viewName, setViewName] = useState("");
  const [showViewSave, setShowViewSave] = useState(false);
  const [columns, setColumns] = useState(() => {
    try {
      return JSON.parse(
        sessionStorage.getItem(`lead-columns-${userId}`) ||
          '["company","owner","score","follow","action"]',
      ) as string[];
    } catch {
      return ["company", "owner", "score", "follow", "action"];
    }
  });
  const search = params.get("search") || "",
    stage = params.get("stage") || "",
    owner = params.get("owner") || "",
    queue = params.get("queue") || "all",
    view = params.get("view") || "table";
  const page = Number(params.get("page") || 1),
    opened = Number(params.get("lead") || 0);
  const [searchDraft, setSearchDraft] = useState(search);
  const updateParams = (values: Record<string, string>) =>
    setParams((current) => {
      const next = new URLSearchParams(current);
      Object.entries(values).forEach(([key, value]) =>
        value ? next.set(key, value) : next.delete(key),
      );
      return next;
    });
  const refresh = () => setRevision((v) => v + 1);
  const report = (err: unknown) =>
    toast({
      title: "Action could not be completed",
      description: errorMessage(err),
      variant: "destructive",
    });

  useRefreshableEffect(() => {
    let active = true;
    leadsApi
      .bootstrap()
      .then((r) => {
        if (active) setBootstrap(r.data);
      })
      .catch((err) => {
        if (active) setError(errorMessage(err));
      });
    return () => {
      active = false;
    };
  }, [revision]);
  useEffect(() => {
    setSearchDraft(search);
  }, [search]);
  useEffect(() => {
    if (searchDraft === search) return;
    const timer = setTimeout(
      () => updateParams({ search: searchDraft, page: "1" }),
      300,
    );
    return () => clearTimeout(timer);
  }, [searchDraft, search]);
  useRefreshableEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    leadsApi
      .list(
        {
          search,
          stage,
          ...(owner ? { owner } : {}),
          queue,
          page,
          per_page: 40,
        },
        controller.signal,
      )
      .then((r) => setResult(r.data))
      .catch((err) => {
        if (!controller.signal.aborted) setError(errorMessage(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [search, stage, owner, queue, page, revision]);
  useEffect(() => {
    setSelected([]);
  }, [search, stage, owner, queue, page]);
  useEffect(() => {
    sessionStorage.setItem(`lead-columns-${userId}`, JSON.stringify(columns));
  }, [columns, userId]);
  const ownerName = (id?: number) =>
    bootstrap?.owners.find((o) => o.id === id)?.name ||
    (id ? `User ${id}` : "Unassigned");
  const openLead = (id: number) => {
    sessionStorage.setItem(`lead-scroll-${userId}`, String(window.scrollY));
    updateParams({ lead: String(id) });
  };
  const closeLead = () => {
    updateParams({ lead: "", transition: "" });
    requestAnimationFrame(() =>
      window.scrollTo(
        0,
        Number(sessionStorage.getItem(`lead-scroll-${userId}`) || 0),
      ),
    );
  };
  const mutate = async (lead: Lead, patch: LeadPatch) => {
    setBusy(true);
    try {
      await leadsApi.update(lead.id, { ...patch, version: lead.version });
      toast({ title: "Lead saved" });
      refresh();
    } catch (err) {
      report(err);
      updateParams({
        lead: String(lead.id),
        transition: String(patch.values?.status || ""),
      });
    } finally {
      setBusy(false);
    }
  };
  const exportExcel = async () => {
    setBusy(true);
    try {
      const response = await leadsApi.export(
        selected.length
          ? { ids: selected.join(",") }
          : { search, stage, ...(owner ? { owner } : {}) },
      );
      download(response.data, "leads.xlsx");
      toast({
        title: "Excel export ready",
        description: selected.length
          ? `${selected.length} selected leads`
          : "All permitted leads matching search, stage and owner filters. Includes archived leads.",
      });
    } catch (err) {
      report(err);
    } finally {
      setBusy(false);
    }
  };
  const previewBulk = async () => {
    let patch: LeadPatch;
    if (bulkAction.startsWith("owner:"))
      patch = { values: { owner_user_id: Number(bulkAction.slice(6)) } };
    else if (bulkAction.startsWith("stage:"))
      patch = { values: { status: bulkAction.slice(6) } };
    else if (bulkAction === "archive") {
      const reason = window.prompt("Reason for archiving these leads");
      if (!reason) return;
      patch = { details: { archived: true, archiveReason: reason } };
    } else if (bulkAction === "restore")
      patch = { details: { archived: false } };
    else return;
    setBusy(true);
    try {
      const response = await leadsApi.bulkPreview(selected, patch);
      setBulk({ patch, items: response.data.items });
    } catch (err) {
      report(err);
    } finally {
      setBusy(false);
    }
  };
  const saveView = () => {
    if (!viewName.trim()) return;
    const next = [
      ...savedViews.filter((v) => v.name !== viewName.trim()),
      { name: viewName.trim(), search, stage, owner, queue, view },
    ].slice(-20);
    setSavedViews(next);
    sessionStorage.setItem(`lead-views-${userId}`, JSON.stringify(next));
    setShowViewSave(false);
    setViewName("");
  };

  return (
    <div className="lm-root" aria-label="Lead workbench">
      {followUp && bootstrap && (
        <FollowUpDialog
          lead={followUp.lead}
          bootstrap={bootstrap}
          initialDate={followUp.date}
          close={() => setFollowUp(undefined)}
          saved={() => {
            refresh();
            toast({ title: "Follow-up saved" });
          }}
        />
      )}
      <header className="lm-header">
        <div>
          <div className="lm-eyebrow">CUSTOMER RELATIONSHIPS</div>
          <h1>
            Lead workbench{" "}
            <span className="lm-count">{result?.total ?? "—"}</span>
          </h1>
          <p>Know where every enquiry stands. Make the next move.</p>
        </div>
        <div className="lm-actions">
          <Button variant="outline" onClick={exportExcel} disabled={busy}>
            <Download size={16} />
            Export Excel
          </Button>
          {bootstrap?.canManage && (
            <>
              <Button variant="outline" onClick={() => setImportOpen(true)}>
                <FileSpreadsheet size={16} />
                Import Excel
              </Button>
              <Button onClick={() => setCreateOpen(true)}>
                <Plus size={16} />
                Add lead
              </Button>
            </>
          )}
          {bootstrap?.canAdmin && (
            <Button
              variant="outline"
              aria-label="Lead workflow settings"
              onClick={() => setSettingsOpen(true)}
            >
              <Settings2 size={17} />
            </Button>
          )}
        </div>
      </header>
      <nav className="lm-links" aria-label="Related CRM tools">
        <Link to="/crm/leads/classic">Classic workspace</Link>
        <Link to="/crm/webforms">Website forms</Link>
        <Link to="/crm/communication-hub">Communications</Link>
        <Link to="/crm/calendar">Calendar & scheduling</Link>
        <Link to="/crm/duplicates">Duplicate review & merge</Link>
      </nav>
      <section className="lm-metrics" aria-label="Lead health">
        {[
          ["active", "Active leads"],
          ["overdue", "Overdue follow-ups"],
          ["slaBreached", "Response SLA missed"],
          ["stale", "Inactive leads"],
        ].map(([key, label]) => (
          <button
            key={key}
            onClick={() =>
              updateParams({
                queue:
                  key === "overdue"
                    ? "overdue"
                    : key === "stale"
                      ? "stale"
                      : key === "slaBreached"
                        ? "sla"
                        : "active",
                page: "1",
              })
            }
          >
            <span>{label}</span>
            <strong>{result?.summary[key] ?? "—"}</strong>
            <span className="lm-metric-caption">
              {search || stage || owner
                ? "Within current filters"
                : "Visible CRM records"}
            </span>
          </button>
        ))}
      </section>
      <div className="lm-tabs" role="group" aria-label="Lead queues">
        {queues.map(([key, label]) => (
          <button
            key={key}
            aria-pressed={queue === key}
            className={queue === key ? "active" : ""}
            onClick={() => updateParams({ queue: key, page: "1" })}
          >
            {label}
          </button>
        ))}
        <button
          className={insights ? "active" : ""}
          aria-pressed={insights}
          onClick={() => setInsights((v) => !v)}
        >
          Insights
        </button>
      </div>
      {insights && result && (
        <section className="lm-insights">
          <div>
            <h2>Current lead stages</h2>
            <p>Snapshot counts, not historical stage conversion.</p>
            {Object.entries(result.byStage).map(([name, count]) => (
              <div className="lm-bar-row" key={name}>
                <span>{name}</span>
                <meter
                  min="0"
                  max={Math.max(result.summary.total, 1)}
                  value={count}
                />
                <strong>{count}</strong>
              </div>
            ))}
          </div>
          <div>
            <h2>Source quality</h2>
            <p>Converted leads / total leads from each source.</p>
            {Object.entries(result.bySource).map(([name, count]) => (
              <div className="lm-bar-row" key={name}>
                <span>{name}</span>
                <span>
                  {result.convertedBySource[name] || 0} / {count} converted
                </span>
                <strong>
                  {Math.round(
                    ((result.convertedBySource[name] || 0) / count) * 100,
                  )}
                  %
                </strong>
              </div>
            ))}
          </div>
          <div>
            <h2>Why leads were lost</h2>
            {Object.entries(result.lostReasons).length ? (
              Object.entries(result.lostReasons).map(([reason, count]) => (
                <p key={reason}>
                  {reason} <strong>{count}</strong>
                </p>
              ))
            ) : (
              <p>No lost leads in the current filters.</p>
            )}
            <Link to="/crm/reports">
              Open CRM funnel report <ArrowRight size={14} />
            </Link>
          </div>
        </section>
      )}
      {insights && bootstrap && (
        <LeadAnalyticsPanel owners={bootstrap.owners} revision={revision} />
      )}
      <section className="lm-workspace" aria-label="Lead records">
        <div className="lm-toolbar">
          <label className="lm-search">
            <Search size={17} />
            <input
              aria-label="Search leads"
              placeholder="Search name, company, email or phone"
              value={searchDraft}
              onChange={(e) => setSearchDraft(e.target.value)}
            />
          </label>
          <select
            aria-label="Filter stage"
            value={stage}
            onChange={(e) => updateParams({ stage: e.target.value, page: "1" })}
          >
            <option value="">All stages</option>
            {bootstrap?.settings.stages.map((s) => (
              <option key={s.name}>{s.name}</option>
            ))}
          </select>
          <select
            aria-label="Filter owner"
            value={owner}
            onChange={(e) => updateParams({ owner: e.target.value, page: "1" })}
          >
            <option value="">All visible owners</option>
            {bootstrap?.owners.map((o) => (
              <option value={o.id} key={o.id}>
                {o.name}
              </option>
            ))}
          </select>
          <div className="lm-view-toggle">
            {[
              ["table", List],
              ["board", LayoutGrid],
              ["compact", Users],
            ].map(([key, Icon]) => {
              const Component = Icon as typeof List;
              return (
                <button
                  key={String(key)}
                  aria-label={`${key} view`}
                  aria-pressed={view === key}
                  onClick={() => updateParams({ view: String(key) })}
                >
                  <Component size={17} />
                </button>
              );
            })}
          </div>
          <Button
            size="sm"
            variant="ghost"
            onClick={refresh}
            aria-label="Refresh leads"
          >
            <RefreshCw size={16} />
          </Button>
        </div>
        <div className="lm-view-tools">
          <select
            aria-label="Saved views"
            value=""
            onChange={(e) => {
              const saved = savedViews.find((v) => v.name === e.target.value);
              if (saved) {
                const { name: _, ...values } = saved;
                updateParams({ ...values, page: "1" });
              }
            }}
          >
            <option value="">Saved views</option>
            {savedViews.map((v) => (
              <option key={v.name}>{v.name}</option>
            ))}
          </select>
          <button onClick={() => setShowViewSave((v) => !v)}>
            Save current view
          </button>
          {showViewSave && (
            <>
              <input
                aria-label="View name"
                maxLength={80}
                placeholder="Name this view"
                value={viewName}
                onChange={(e) => setViewName(e.target.value)}
              />
              <button onClick={saveView}>Save view</button>
            </>
          )}
          <details>
            <summary>Columns</summary>
            <div className="lm-column-options">
              {["company", "owner", "score", "follow", "action"].map(
                (column) => (
                  <label key={column}>
                    <input
                      type="checkbox"
                      checked={columns.includes(column)}
                      onChange={(e) =>
                        setColumns((current) =>
                          e.target.checked
                            ? [...current, column]
                            : current.filter((c) => c !== column),
                        )
                      }
                    />
                    {column}
                  </label>
                ),
              )}
            </div>
          </details>
          {bootstrap?.canManage && (
            <button
              onClick={async () => {
                try {
                  const r = await leadsApi.alerts();
                  toast({
                    title: `${r.data.notificationsCreated} response alerts created`,
                  });
                } catch (err) {
                  report(err);
                }
              }}
            >
              Escalate missed response deadlines
            </button>
          )}
        </div>
        {!!selected.length && bootstrap?.canManage && (
          <div className="lm-bulk">
            <strong>{selected.length} selected</strong>
            <select
              aria-label="Bulk action"
              value={bulkAction}
              onChange={(e) => setBulkAction(e.target.value)}
            >
              <option value="">Choose action</option>
              <optgroup label="Change stage">
                {bootstrap.settings.stages
                  .filter((s) => !["Converted", "Lost"].includes(s.name))
                  .map((s) => (
                    <option value={`stage:${s.name}`} key={s.name}>
                      {s.name}
                    </option>
                  ))}
              </optgroup>
              <optgroup label="Assign owner">
                {bootstrap.owners.map((o) => (
                  <option value={`owner:${o.id}`} key={o.id}>
                    {o.name}
                  </option>
                ))}
              </optgroup>
              <option value="archive">Archive with reason</option>
              <option value="restore">Restore from archive</option>
            </select>
            <Button
              size="sm"
              variant="outline"
              onClick={previewBulk}
              disabled={!bulkAction || busy}
            >
              Preview changes
            </Button>
            <button onClick={() => setSelected([])}>Clear selection</button>
          </div>
        )}
        {error && <ErrorNotice message={error} retry={refresh} />}
        {result?.truncated && (
          <div className="lm-warning">
            Showing the newest {result.limit.toLocaleString()} permitted leads.
            Narrow search, stage or owner filters to review older records.
          </div>
        )}
        {loading ? (
          <div className="lm-loading" role="status">
            <Loader2 className="animate-spin" />
            Loading lead records…
          </div>
        ) : !result?.items.length ? (
          <div className="lm-empty">
            <Users size={30} />
            <h2>
              {queue === "my_day" ? "Your queue is clear" : "No matching leads"}
            </h2>
            <p>
              {queue === "my_day"
                ? "New assignments and due follow-ups will appear here."
                : "Adjust your filters, add a lead or import an Excel workbook."}
            </p>
            <Button
              variant="outline"
              onClick={() => {
                setSearchDraft("");
                updateParams({
                  search: "",
                  stage: "",
                  owner: "",
                  queue: "all",
                  page: "1",
                });
              }}
            >
              Reset filters
            </Button>
          </div>
        ) : view === "board" ? (
          bootstrap && (
            <LeadWorkflowBoard
              group={params.get("group") || "stage"}
              groupChanged={(group) => updateParams({ group })}
              leads={result.items}
              bootstrap={bootstrap}
              busy={busy}
              open={openLead}
              move={(lead, values) => void mutate(lead, { values })}
              schedule={(lead, date) => setFollowUp({ lead, date })}
            />
          )
        ) : view === "compact" ? (
          <div className="lm-compact">
            {result.items.map((lead) => (
              <button key={lead.id} onClick={() => openLead(lead.id)}>
                <div>
                  <strong>{lead.full_name}</strong>
                  <span>{lead.company_name || lead.email}</span>
                </div>
                <StageBadge stage={lead.status} />
                <span className={lead.signals.overdue ? "lm-danger-text" : ""}>
                  {lead.signals.followUpLabel}
                </span>
                <ArrowRight size={17} />
              </button>
            ))}
          </div>
        ) : (
          <div className="lm-table-scroll">
            <table className="lm-table">
              <thead>
                <tr>
                  <th>
                    {bootstrap?.canManage && (
                      <input
                        type="checkbox"
                        aria-label="Select all leads on this page"
                        checked={
                          result.items.length > 0 &&
                          result.items.every((l) => selected.includes(l.id))
                        }
                        onChange={(e) =>
                          setSelected(
                            e.target.checked
                              ? result.items.map((l) => l.id)
                              : [],
                          )
                        }
                      />
                    )}
                  </th>
                  <th>Lead</th>
                  <th>Stage</th>
                  {columns.includes("company") && <th>Company</th>}
                  {columns.includes("owner") && <th>Assigned employee</th>}
                  {columns.includes("score") && <th>Score</th>}
                  {columns.includes("follow") && <th>Follow-up</th>}
                  {columns.includes("action") && <th>Next action</th>}
                </tr>
              </thead>
              <tbody>
                {result.items.map((lead) => (
                  <tr key={lead.id}>
                    <td>
                      {bootstrap?.canManage && (
                        <input
                          type="checkbox"
                          aria-label={`Select ${lead.full_name}`}
                          checked={selected.includes(lead.id)}
                          onChange={(e) =>
                            setSelected((current) =>
                              e.target.checked
                                ? [...current, lead.id]
                                : current.filter((id) => id !== lead.id),
                            )
                          }
                        />
                      )}
                    </td>
                    <td>
                      <button
                        className="lm-name"
                        onClick={() => openLead(lead.id)}
                      >
                        {lead.full_name}
                      </button>
                      <span className="lm-secondary">
                        {lead.email || lead.phone || "No contact details"}
                      </span>
                    </td>
                    <td>
                      {bootstrap?.canManage && !lead.is_converted ? (
                        <select
                          className="lm-inline"
                          aria-label={`Stage for ${lead.full_name}`}
                          disabled={busy}
                          value={lead.status}
                          onChange={(e) => {
                            if (e.target.value === "Lost") {
                              updateParams({
                                lead: String(lead.id),
                                transition: "Lost",
                              });
                            } else
                              void mutate(lead, {
                                values: { status: e.target.value },
                              });
                          }}
                        >
                          <option>{lead.status}</option>
                          {bootstrap.settings.stages
                            .find((s) => s.name === lead.status)
                            ?.allowedNext.filter((name) => name !== "Converted")
                            .map((name) => (
                              <option key={name}>{name}</option>
                            ))}
                        </select>
                      ) : (
                        <StageBadge stage={lead.status} />
                      )}
                    </td>
                    {columns.includes("company") && (
                      <td>{lead.company_name || "—"}</td>
                    )}
                    {columns.includes("owner") && (
                      <td>
                        {bootstrap?.canManage && bootstrap.owners.length > 1 ? (
                          <select
                            className="lm-inline"
                            aria-label={`Owner for ${lead.full_name}`}
                            value={lead.owner_user_id || ""}
                            disabled={busy}
                            onChange={(e) =>
                              void mutate(lead, {
                                values: {
                                  owner_user_id: Number(e.target.value),
                                },
                              })
                            }
                          >
                            <option value="" disabled>
                              Unassigned
                            </option>
                            {!!lead.owner_user_id &&
                              !bootstrap.owners.some(
                                (o) => o.id === lead.owner_user_id,
                              ) && (
                                <option value={lead.owner_user_id} disabled>
                                  Current assignee (unavailable)
                                </option>
                              )}
                            {bootstrap.owners.map((o) => (
                              <option value={o.id} key={o.id}>
                                {o.name}
                              </option>
                            ))}
                          </select>
                        ) : (
                          ownerName(lead.owner_user_id)
                        )}
                      </td>
                    )}
                    {columns.includes("score") && (
                      <td>
                        <span className="lm-score">{lead.lead_score || 0}</span>
                        <span className="lm-secondary">
                          {lead.lead_score_mode}
                        </span>
                      </td>
                    )}
                    {columns.includes("follow") && (
                      <td>
                        <span
                          className={
                            lead.signals.overdue ? "lm-danger-text" : ""
                          }
                        >
                          {lead.signals.followUpLabel}
                        </span>
                        <span className="lm-secondary">
                          {lead.next_follow_up_at
                            ? formatDate(lead.next_follow_up_at)
                            : "Choose a next step"}
                        </span>
                      </td>
                    )}
                    {columns.includes("action") && (
                      <td className="lm-next-action">
                        {lead.signals.slaBreached && (
                          <span className="lm-alert-dot" />
                        )}
                        {lead.signals.nextAction}
                        {bootstrap?.canManage && lead.signals.active && (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={busy}
                            onClick={() => setFollowUp({ lead })}
                          >
                            Follow up
                          </Button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <footer className="lm-pagination">
          <span>
            {result?.total || 0} matching leads ·{" "}
            {view === "board" ? "Board shows current page" : "40 per page"}
          </span>
          <div>
            <Button
              size="sm"
              variant="outline"
              disabled={page <= 1 || loading}
              onClick={() => updateParams({ page: String(page - 1) })}
            >
              Previous
            </Button>
            <span>
              Page {page} of {Math.max(1, Math.ceil((result?.total || 0) / 40))}
            </span>
            <Button
              size="sm"
              variant="outline"
              disabled={page * 40 >= (result?.total || 0) || loading}
              onClick={() => updateParams({ page: String(page + 1) })}
            >
              Next
            </Button>
          </div>
        </footer>
      </section>
      {bootstrap && createOpen && (
        <CaptureDialog
          bootstrap={bootstrap}
          close={() => setCreateOpen(false)}
          saved={(id) => {
            setCreateOpen(false);
            refresh();
            openLead(id);
          }}
        />
      )}
      {bootstrap && opened > 0 && (
        <LeadDrawer
          id={opened}
          targetStage={params.get("transition") || ""}
          bootstrap={bootstrap}
          close={closeLead}
          changed={refresh}
        />
      )}
      {importOpen && (
        <ExcelDialog
          close={() => setImportOpen(false)}
          imported={() => {
            setImportOpen(false);
            refresh();
          }}
        />
      )}
      {bootstrap && settingsOpen && (
        <WorkflowSettings
          bootstrap={bootstrap}
          close={() => setSettingsOpen(false)}
          saved={() => {
            setSettingsOpen(false);
            refresh();
          }}
        />
      )}
      <Dialog
        open={!!bulk}
        onOpenChange={(open) => {
          if (!open && !busy) setBulk(undefined);
        }}
      >
        <DialogContent className="lm-dialog">
          <DialogTitle>Review bulk changes</DialogTitle>
          <p>
            {bulk?.items.length} leads will be updated. Changes are applied
            together; a validation failure keeps all records unchanged.
          </p>
          <pre className="lm-change-preview">
            {bulk?.patch.values?.status
              ? `Stage → ${bulk.patch.values.status}`
              : bulk?.patch.values?.owner_user_id
                ? `Owner → ${ownerName(Number(bulk.patch.values.owner_user_id))}`
                : bulk?.patch.details?.archived
                  ? `Archive: ${bulk.patch.details.archiveReason}`
                  : "Restore archived leads"}
          </pre>
          <ul className="lm-preview-list">
            {bulk?.items.map((item) => (
              <li key={item.id}>
                {item.name}
                <StageBadge stage={item.stage} />
              </li>
            ))}
          </ul>
          <Button
            disabled={busy}
            onClick={async () => {
              if (!bulk) return;
              setBusy(true);
              try {
                const response = await leadsApi.bulkApply(
                  bulk.items.map((i) => i.id),
                  bulk.patch,
                );
                toast({ title: `${response.data.updated} leads updated` });
                setBulk(undefined);
                setSelected([]);
                refresh();
              } catch (err) {
                report(err);
              } finally {
                setBusy(false);
              }
            }}
          >
            Apply to {bulk?.items.length} leads
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function CaptureDialog({
  bootstrap,
  close,
  saved,
}: {
  bootstrap: Bootstrap;
  close: () => void;
  saved: (id: number) => void;
}) {
  const key = `lead-capture-draft-${bootstrap.userId}`;
  const automaticRouting =
    bootstrap.settings.assignment.mode !== "manual" ||
    bootstrap.settings.assignment.rules.length > 0;
  const defaultOwner = automaticRouting
    ? ""
    : String(bootstrap.owners.find((o) => o.id === bootstrap.userId)?.id || "");
  const [values, setValues] = useState<Record<string, string>>(() => {
    try {
      return JSON.parse(
        sessionStorage.getItem(key) ||
          '{"full_name":"","email":"","phone":"","company_name":"","source":"Manual"}',
      );
    } catch {
      return { full_name: "", source: "Manual" };
    }
  });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    sessionStorage.setItem(key, JSON.stringify(values));
  }, [values, key]);
  const dismiss = () => {
    if (
      !saving &&
      (!values.full_name ||
        window.confirm(
          "Keep this draft and close? It will be available when you add a lead again.",
        ))
    )
      close();
  };
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) dismiss();
      }}
    >
      <DialogContent className="lm-dialog">
        <DialogTitle>Capture a new lead</DialogTitle>
        <p>
          Start with a name. Add qualification details as the conversation
          develops.
        </p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setSaving(true);
            setError("");
            try {
              const response = await leadsApi.create({
                values: Object.fromEntries(
                  Object.entries({
                    ...values,
                    owner_user_id: values.owner_user_id ?? defaultOwner,
                  }).filter(([, value]) => value !== ""),
                ),
              });
              sessionStorage.removeItem(key);
              saved(response.data.id);
            } catch (err) {
              setError(errorMessage(err));
            } finally {
              setSaving(false);
            }
          }}
        >
          <div className="lm-form-grid">
            <Field label="Assign to employee">
              <select
                value={values.owner_user_id ?? defaultOwner}
                onChange={(e) =>
                  setValues((v) => ({ ...v, owner_user_id: e.target.value }))
                }
              >
                <option value="">
                  {automaticRouting
                    ? "Use automatic assignment rules"
                    : "Assign to me"}
                </option>
                {bootstrap.owners.map((owner) => (
                  <option key={owner.id} value={owner.id}>
                    {owner.name}
                  </option>
                ))}
              </select>
            </Field>
            {[
              ["full_name", "Full name *"],
              ["company_name", "Company"],
              ["email", "Email"],
              ["source", "Lead source"],
            ].map(([name, label]) => (
              <Field key={name} label={label}>
                <input
                  autoFocus={name === "full_name"}
                  required={name === "full_name"}
                  type={
                    name === "email"
                      ? "email"
                      : name === "phone"
                        ? "tel"
                        : "text"
                  }
                  value={values[name] || ""}
                  maxLength={
                    name === "full_name"
                      ? 220
                      : name === "email"
                        ? 150
                        : name === "phone"
                          ? 40
                          : 180
                  }
                  onChange={(e) =>
                    setValues((current) => ({
                      ...current,
                      [name]: e.target.value,
                    }))
                  }
                />
              </Field>
            ))}
            <Field label="Phone">
              <PhoneInput
                value={values.phone || ""}
                countryCode={values.phone_country_code || ""}
                onChange={(phone) => setValues((v) => ({ ...v, phone }))}
                onCountryCodeChange={(phone_country_code) =>
                  setValues((v) => ({ ...v, phone_country_code }))
                }
              />
            </Field>
          </div>
          {!!bootstrap.unavailableEmployees?.length && (
            <details className="lm-help">
              <summary>
                Employees missing CRM access (
                {bootstrap.unavailableEmployees.length})
              </summary>
              <ul>
                {bootstrap.unavailableEmployees.map((employee) => (
                  <li key={employee.employeeId}>
                    {employee.name} ({employee.employeeCode}): {employee.reason}
                  </li>
                ))}
              </ul>
              <p>
                Link an active login and grant CRM lead access before assigning
                these employees.
              </p>
            </details>
          )}
          {error && <ErrorNotice message={error} />}
          <div className="lm-dialog-actions">
            <span>
              {saving ? "Saving…" : "Draft saved in this browser session"}
            </span>
            <Button type="submit" disabled={saving}>
              {saving ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Check size={16} />
              )}
              Create lead
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function LeadDrawer({
  id,
  targetStage,
  bootstrap,
  close,
  changed,
}: {
  id: number;
  targetStage: string;
  bootstrap: Bootstrap;
  close: () => void;
  changed: () => void;
}) {
  const { toast } = useToast();
  const [lead, setLead] = useState<Lead>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  const [tab, setTab] = useState("overview");
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [details, setDetails] = useState<LeadDetails>({});
  const [dirty, setDirty] = useState(false);
  const [teamDirty, setTeamDirty] = useState(false);
  const [activity, setActivity] = useState({
    type: "call",
    outcome: "",
    nextFollowUp: "",
    responded: false,
    startAt: "",
  });
  const [sequence, setSequence] = useState(
    bootstrap.settings.sequences[0]?.name || "",
  );
  const [conversion, setConversion] = useState<ConversionPreview>();
  const [conversionIds, setConversionIds] = useState({
    existingContactId: "",
    existingCompanyId: "",
  });
  const [booking, setBooking] = useState("");
  const [scheduling, setScheduling] = useState(false);
  useRefreshableEffect(() => {
    const controller = new AbortController();
    setError("");
    leadsApi
      .detail(id, controller.signal)
      .then((r) => {
        setLead(r.data);
        const pendingTransition = targetStage && targetStage !== r.data.status;
        setValues(pendingTransition ? { status: targetStage } : {});
        setDetails(r.data.details);
        setDirty(Boolean(pendingTransition));
        if (pendingTransition) setTab("qualification");
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(errorMessage(err));
      });
    return () => controller.abort();
  }, [id, reload, targetStage]);
  const dismiss = () => {
    if (
      !busy &&
      (!(dirty || teamDirty) ||
        window.confirm("Discard unsaved changes to this lead?"))
    )
      close();
  };
  const setValue = (key: string, value: unknown) => {
    setValues((current) => ({ ...current, [key]: value }));
    setDirty(true);
  };
  const setDetail = (patch: Partial<LeadDetails>) => {
    setDetails((current) => ({ ...current, ...patch }));
    setDirty(true);
  };
  const value = (key: keyof Lead) => String(values[key] ?? lead?.[key] ?? "");
  const act = async (operation: () => Promise<unknown>, message: string) => {
    setBusy(true);
    setError("");
    try {
      await operation();
      toast({ title: message });
      changed();
      setReload((v) => v + 1);
      return true;
    } catch (err) {
      setError(errorMessage(err));
      return false;
    } finally {
      setBusy(false);
    }
  };
  const save = () => {
    if (!lead) return;
    const writable = [
      "qualification",
      "interests",
      "lossReason",
      "competitor",
      "scoreOverrideReason",
      "archived",
      "archiveReason",
      "reviewAt",
    ];
    const patch = Object.fromEntries(
      Object.entries(details).filter(([key]) => writable.includes(key)),
    );
    return act(
      () =>
        leadsApi.update(id, { values, details: patch, version: lead.version }),
      "Lead saved",
    );
  };
  const qualification = { ...emptyQualification, ...details.qualification };
  const allowed =
    bootstrap.settings.stages.find((s) => s.name === lead?.status)
      ?.allowedNext || [];
  const stageConfig = bootstrap.settings.stages.find(
    (s) => s.name === (values.status || lead?.status),
  );
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) dismiss();
      }}
    >
      <DialogContent className="lm-drawer">
        {scheduling && lead && (
          <FollowUpDialog
            lead={lead}
            bootstrap={bootstrap}
            close={() => setScheduling(false)}
            saved={() => {
              changed();
              setReload((v) => v + 1);
            }}
          />
        )}
        <DialogTitle className="lm-drawer-title">
          {lead?.full_name || "Lead details"}
        </DialogTitle>
        {!lead ? (
          error ? (
            <ErrorNotice
              message={error}
              retry={() => setReload((v) => v + 1)}
            />
          ) : (
            <div className="lm-loading" role="status">
              Loading lead…
            </div>
          )
        ) : (
          <>
            <header className="lm-record-header">
              <div>
                <StageBadge stage={lead.status} />
                <span>{lead.company_name || "Individual enquiry"}</span>
              </div>
              <p>{lead.signals.nextAction}</p>
              <div className="lm-contact-actions">
                {lead.phone && (
                  <a href={`tel:${lead.phone_country_code || ""}${lead.phone}`}>
                    <Phone size={15} />
                    Call
                  </a>
                )}
                {lead.email && (
                  <a href={`mailto:${lead.email}`}>
                    <Mail size={15} />
                    Email
                  </a>
                )}
                <Link to={`/crm/leads/${id}`}>
                  Full record <ArrowRight size={14} />
                </Link>
              </div>
            </header>
            <nav className="lm-tabs" aria-label="Lead detail sections">
              {[
                "overview",
                "qualification",
                "activities",
                "team",
                "score",
                "history",
              ].map((name) => (
                <button
                  key={name}
                  className={tab === name ? "active" : ""}
                  aria-pressed={tab === name}
                  onClick={() => {
                    if (
                      name !== tab &&
                      teamDirty &&
                      !window.confirm("Discard your unsaved team update?")
                    )
                      return;
                    if (name !== tab) setTeamDirty(false);
                    setTab(name);
                  }}
                >
                  {name}
                </button>
              ))}
            </nav>
            {error && <ErrorNotice message={error} />}
            <fieldset
              className="lm-fieldset"
              disabled={!bootstrap.canManage || busy}
            >
              {tab === "overview" && (
                <>
                  <div className="lm-form-grid">
                    <Field label="Current stage">
                      <select
                        value={value("status")}
                        onChange={(e) => setValue("status", e.target.value)}
                        disabled={lead.is_converted}
                      >
                        <option>{lead.status}</option>
                        {allowed
                          .filter((s) => s !== "Converted")
                          .map((s) => (
                            <option key={s}>{s}</option>
                          ))}
                      </select>
                    </Field>
                    <Field label="Assigned employee">
                      <select
                        value={value("owner_user_id")}
                        onChange={(e) =>
                          setValue("owner_user_id", Number(e.target.value))
                        }
                      >
                        <option value="" disabled>
                          Unassigned
                        </option>
                        {!!lead.owner_user_id &&
                          !bootstrap.owners.some(
                            (o) => o.id === lead.owner_user_id,
                          ) && (
                            <option value={lead.owner_user_id} disabled>
                              Current assignee (unavailable)
                            </option>
                          )}
                        {bootstrap.owners.map((o) => (
                          <option key={o.id} value={o.id}>
                            {o.name}
                          </option>
                        ))}
                      </select>
                    </Field>
                    {[
                      ["full_name", "Name"],
                      ["company_name", "Company"],
                      ["email", "Email"],
                      ["source", "Source"],
                      ["estimated_value", "Estimated value"],
                    ].map(([key, label]) => (
                      <Field label={label} key={key}>
                        <input
                          type={
                            key === "email"
                              ? "email"
                              : key === "estimated_value"
                                ? "number"
                                : "text"
                          }
                          min={key === "estimated_value" ? 0 : undefined}
                          step={key === "estimated_value" ? "0.01" : undefined}
                          value={value(key as keyof Lead)}
                          onChange={(e) =>
                            setValue(
                              key,
                              key === "estimated_value"
                                ? e.target.value === ""
                                  ? null
                                  : Number(e.target.value)
                                : e.target.value,
                            )
                          }
                        />
                      </Field>
                    ))}
                    <Field label="Phone">
                      <PhoneInput
                        value={value("phone")}
                        countryCode={value("phone_country_code")}
                        onChange={(number) => setValue("phone", number)}
                        onCountryCodeChange={(code) =>
                          setValue("phone_country_code", code)
                        }
                      />
                    </Field>
                    <Field label="Next follow-up">
                      <input
                        type="datetime-local"
                        value={dateInput(value("next_follow_up_at"))}
                        onChange={(e) =>
                          setValue("next_follow_up_at", iso(e.target.value))
                        }
                      />
                    </Field>
                  </div>
                  <Field label="Notes">
                    <RichTextField
                      rows={3}
                      value={value("notes")}
                      onChange={(e) => setValue("notes", e.target.value)}
                    />
                  </Field>
                  <section className="lm-section">
                    <h3>Follow-up sequence</h3>
                    <p>
                      Schedules tasks for your team. Record a response to stop
                      pending steps.
                    </p>
                    {details.sequence && (
                      <p>
                        {details.sequence.name} ·{" "}
                        {details.sequence.active
                          ? "Active"
                          : `Stopped: ${details.sequence.stopReason}`}
                      </p>
                    )}
                    <div className="lm-actions">
                      <select
                        aria-label="Follow-up sequence"
                        value={sequence}
                        onChange={(e) => setSequence(e.target.value)}
                      >
                        {bootstrap.settings.sequences.map((s) => (
                          <option key={s.name}>{s.name}</option>
                        ))}
                      </select>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={!sequence || busy}
                        onClick={() =>
                          void act(
                            () => leadsApi.sequence(id, sequence),
                            "Sequence scheduled",
                          )
                        }
                      >
                        Start sequence
                      </Button>
                      {details.sequence?.active && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            void act(
                              () => leadsApi.sequence(id, sequence, true),
                              "Sequence stopped",
                            )
                          }
                        >
                          Stop
                        </Button>
                      )}
                    </div>
                  </section>
                  <section className="lm-section">
                    <h3>Nurture & review</h3>
                    <Field label="Review on">
                      <input
                        type="datetime-local"
                        value={dateInput(details.reviewAt)}
                        onChange={(e) =>
                          setDetail({
                            reviewAt: iso(e.target.value),
                          })
                        }
                      />
                    </Field>
                    <label className="lm-check">
                      <input
                        type="checkbox"
                        checked={!!details.archived}
                        onChange={(e) =>
                          setDetail({ archived: e.target.checked })
                        }
                      />
                      Archive from the active queue
                    </label>
                    {details.archived && (
                      <Field label="Archive reason">
                        <input
                          value={details.archiveReason || ""}
                          onChange={(e) =>
                            setDetail({ archiveReason: e.target.value })
                          }
                        />
                      </Field>
                    )}
                    {lead.status === "Lost" && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setValue("status", "New");
                          setDetail({ archived: false });
                        }}
                      >
                        Reactivate as New — save to apply
                      </Button>
                    )}
                  </section>
                </>
              )}
              {tab === "qualification" && (
                <>
                  <p className="lm-help">
                    Required for {stageConfig?.name}:{" "}
                    {stageConfig?.required.join(", ") || "No additional fields"}
                    . Complete these before saving a stage change.
                  </p>
                  <div className="lm-form-grid">
                    {Object.entries(qualification).map(([key, val]) => (
                      <Field
                        label={
                          {
                            need: "Business need",
                            budget: "Budget",
                            decisionMaker: "Decision-maker",
                            timeline: "Purchase timeline",
                          }[key] || key
                        }
                        key={key}
                      >
                        <RichTextField
                          rows={2}
                          value={val}
                          onChange={(e) =>
                            setDetail({
                              qualification: {
                                ...qualification,
                                [key]: e.target.value,
                              },
                            })
                          }
                        />
                      </Field>
                    ))}
                  </div>
                  <h3>Product & service interests</h3>
                  {(details.interests || []).map((interest, index) => (
                    <div className="lm-interest" key={index}>
                      <Field label="Product or service">
                        <input
                          value={interest.name}
                          onChange={(e) =>
                            setDetail({
                              interests: details.interests?.map((v, i) =>
                                i === index
                                  ? { ...v, name: e.target.value }
                                  : v,
                              ),
                            })
                          }
                        />
                      </Field>
                      <Field label="Estimated value">
                        <input
                          type="number"
                          min="0"
                          value={interest.value}
                          onChange={(e) =>
                            setDetail({
                              interests: details.interests?.map((v, i) =>
                                i === index
                                  ? { ...v, value: Number(e.target.value) }
                                  : v,
                              ),
                            })
                          }
                        />
                      </Field>
                      <Field label="Requirements">
                        <RichTextField
                          value={interest.requirements}
                          onChange={(e) =>
                            setDetail({
                              interests: details.interests?.map((v, i) =>
                                i === index
                                  ? { ...v, requirements: e.target.value }
                                  : v,
                              ),
                            })
                          }
                        />
                      </Field>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          setDetail({
                            interests: details.interests?.filter(
                              (_, i) => i !== index,
                            ),
                          })
                        }
                      >
                        Remove interest
                      </Button>
                    </div>
                  ))}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      setDetail({
                        interests: [
                          ...(details.interests || []),
                          { name: "", value: 0, requirements: "" },
                        ],
                      })
                    }
                  >
                    Add interest
                  </Button>
                  <section className="lm-section">
                    <h3>Loss details</h3>
                    <Field label="Loss reason (required when Lost)">
                      <select
                        value={details.lossReason || ""}
                        onChange={(e) =>
                          setDetail({ lossReason: e.target.value })
                        }
                      >
                        <option value="">Choose a reason</option>
                        {[
                          "Budget",
                          "Timing",
                          "No response",
                          "Competitor",
                          "Poor fit",
                          "Other",
                        ].map((reason) => (
                          <option key={reason}>{reason}</option>
                        ))}
                        {details.lossReason &&
                          ![
                            "Budget",
                            "Timing",
                            "No response",
                            "Competitor",
                            "Poor fit",
                            "Other",
                          ].includes(details.lossReason) && (
                            <option>{details.lossReason}</option>
                          )}
                      </select>
                    </Field>
                    <Field label="Competitor">
                      <input
                        value={details.competitor || ""}
                        onChange={(e) =>
                          setDetail({ competitor: e.target.value })
                        }
                      />
                    </Field>
                  </section>
                </>
              )}
              {tab === "team" && (
                <LeadTeamPanel
                  draftChanged={setTeamDirty}
                  lead={lead}
                  canManage={bootstrap.canManage}
                  disabled={busy || dirty}
                  changed={() => {
                    changed();
                    setReload((v) => v + 1);
                  }}
                />
              )}
              {tab === "activities" && (
                <>
                  <h3>Log an outcome & next step</h3>
                  {bootstrap.canManage && lead.signals.active && (
                    <Button
                      variant="outline"
                      disabled={busy || dirty}
                      onClick={() => setScheduling(true)}
                    >
                      Schedule or reschedule follow-up
                    </Button>
                  )}
                  <p className="lm-help">
                    Record completed interactions here. Use Communications to
                    send through connected providers.
                  </p>
                  <div className="lm-form-grid">
                    <Field label="Activity type">
                      <select
                        value={activity.type}
                        onChange={(e) =>
                          setActivity((v) => ({ ...v, type: e.target.value }))
                        }
                      >
                        {["call", "email", "meeting", "note", "task"].map(
                          (type) => (
                            <option key={type}>{type}</option>
                          ),
                        )}
                      </select>
                    </Field>
                    <Field label="Next follow-up">
                      <input
                        type="datetime-local"
                        value={activity.nextFollowUp}
                        onChange={(e) =>
                          setActivity((v) => ({
                            ...v,
                            nextFollowUp: e.target.value,
                          }))
                        }
                      />
                    </Field>
                    {activity.type === "meeting" && (
                      <Field label="Schedule meeting for (optional)">
                        <input
                          type="datetime-local"
                          value={activity.startAt}
                          onChange={(e) =>
                            setActivity((v) => ({
                              ...v,
                              startAt: e.target.value,
                            }))
                          }
                        />
                      </Field>
                    )}
                  </div>
                  <Field label="Outcome or meeting purpose">
                    <RichTextField
                      rows={3}
                      value={activity.outcome}
                      onChange={(e) =>
                        setActivity((v) => ({ ...v, outcome: e.target.value }))
                      }
                    />
                  </Field>
                  <label className="lm-check">
                    <input
                      type="checkbox"
                      checked={activity.responded}
                      onChange={(e) =>
                        setActivity((v) => ({
                          ...v,
                          responded: e.target.checked,
                        }))
                      }
                    />
                    Lead responded — stop pending sequence tasks
                  </label>
                  <Button
                    disabled={!activity.outcome.trim() || busy}
                    onClick={async () => {
                      const ok = await act(
                        () =>
                          leadsApi.activity(id, {
                            ...activity,
                            nextFollowUp: iso(activity.nextFollowUp),
                            startAt: iso(activity.startAt),
                          }),
                        "Activity and follow-up saved",
                      );
                      if (ok)
                        setActivity((v) => ({
                          ...v,
                          outcome: "",
                          responded: false,
                        }));
                    }}
                  >
                    Save activity & next step
                  </Button>
                  <section className="lm-section">
                    <h3>Let the lead book a meeting</h3>
                    <p>
                      Create a private, single-use booking link, valid for 30
                      days. Availability checks use the assigned BusinessSuite
                      calendar.
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busy || dirty}
                      onClick={async () => {
                        try {
                          const response = await leadsApi.bookingLink(id);
                          setBooking(publicUrl(response.data.path));
                          setReload((v) => v + 1);
                          changed();
                        } catch (err) {
                          setError(errorMessage(err));
                        }
                      }}
                    >
                      Create booking link
                    </Button>
                    {booking && (
                      <Field label="Share this booking link">
                        <input
                          readOnly
                          value={booking}
                          onFocus={(e) => e.target.select()}
                        />
                      </Field>
                    )}
                  </section>
                  <section className="lm-section">
                    <h3>Scheduled & completed activities</h3>
                    {lead.activities?.map((item) => (
                      <div className="lm-activity-row" key={item.id}>
                        <strong>{item.subject}</strong>
                        <span>
                          {item.activity_type} · {item.status}
                          {item.due_date
                            ? ` · ${formatDate(item.due_date)}`
                            : ""}
                        </span>
                        {item.status === "Pending" && bootstrap.canManage && (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={busy || dirty}
                            onClick={() =>
                              void act(
                                () => leadsApi.completeTask(id, item.id),
                                "Activity completed; next follow-up updated",
                              )
                            }
                          >
                            Complete task
                          </Button>
                        )}
                      </div>
                    ))}
                  </section>
                </>
              )}
              {tab === "score" && (
                <>
                  <div className="lm-score-heading">
                    <strong>
                      {lead.lead_score || 0}
                      <small>/100</small>
                    </strong>
                    <span>
                      {lead.lead_score_mode === "manual"
                        ? "Manual override"
                        : "Calculated from active scoring rules"}
                    </span>
                  </div>
                  <p>
                    Rule contributions below show the current automatic
                    calculation. A manual score can differ.
                  </p>
                  {lead.scoreReasons?.map((reason, index) => (
                    <div className="lm-rule-row" key={index}>
                      <span>
                        {reason.matched ? "Matched" : "Not matched"} ·{" "}
                        {reason.name}
                      </span>
                      <strong>
                        {reason.points > 0 ? "+" : ""}
                        {reason.points}
                      </strong>
                    </div>
                  ))}
                  <div className="lm-form-grid">
                    <Field label="Manual score (0–100)">
                      <input
                        type="number"
                        min="0"
                        max="100"
                        value={value("lead_score")}
                        onChange={(e) =>
                          setValue("lead_score", Number(e.target.value))
                        }
                      />
                    </Field>
                    <Field label="Reason for score override">
                      <input
                        value={details.scoreOverrideReason || ""}
                        onChange={(e) =>
                          setDetail({ scoreOverrideReason: e.target.value })
                        }
                      />
                    </Field>
                  </div>
                  <Link to="/crm/lead-scoring">Manage scoring rules</Link>
                </>
              )}
            </fieldset>
            {tab === "history" && (
              <section className="lm-timeline">
                <p className="lm-help">
                  Status changes include actor, timestamp and time in the
                  previous stage where recorded.
                </p>
                {lead.timeline?.length ? (
                  lead.timeline.map((item) => (
                    <article key={item.id}>
                      <span className="lm-timeline-kind">
                        {item.event_type.replace(/_/g, " ")}
                      </span>
                      <h3>{item.title}</h3>
                      {item.description && <div><RichTextContent legacyFormat="plain" value={item.description}/></div>}
                      <small>
                        {formatDate(item.occurred_at)} ·{" "}
                        {bootstrap.owners.find(
                          (o) => o.id === item.actor_user_id,
                        )?.name || `User ${item.actor_user_id || "system"}`}
                        {item.metadata_json?.durationHours !== undefined &&
                          ` · ${item.metadata_json.durationHours} hours in previous stage`}
                      </small>
                    </article>
                  ))
                ) : (
                  <p>No recorded events yet.</p>
                )}
              </section>
            )}
            {bootstrap.canManage && (
              <footer className="lm-drawer-footer">
                <span role="status">
                  {busy
                    ? "Saving…"
                    : dirty
                      ? "Unsaved changes"
                      : "All changes saved"}
                </span>
                <Button
                  variant="outline"
                  disabled={
                    busy ||
                    dirty ||
                    lead.status !== "Qualified" ||
                    lead.is_converted
                  }
                  onClick={async () => {
                    try {
                      const response = await leadsApi.previewConversion(id);
                      setConversion(response.data);
                      setConversionIds({
                        existingContactId: String(
                          response.data.matches.contacts[0]?.id || "",
                        ),
                        existingCompanyId: String(
                          response.data.matches.companies[0]?.id || "",
                        ),
                      });
                    } catch (err) {
                      setError(errorMessage(err));
                    }
                  }}
                >
                  Convert lead
                </Button>
                <Button disabled={!dirty || busy} onClick={() => void save()}>
                  Save changes
                </Button>
              </footer>
            )}
            {lead.is_converted && (
              <div className="lm-converted">
                Converted successfully.{" "}
                {lead.converted_contact_id && (
                  <Link to={`/crm/contacts/${lead.converted_contact_id}`}>
                    Contact
                  </Link>
                )}
                {lead.converted_company_id && (
                  <Link to={`/crm/accounts/${lead.converted_company_id}`}>
                    Company
                  </Link>
                )}
                {lead.converted_deal_id && (
                  <Link to={`/crm/deals/${lead.converted_deal_id}`}>Deal</Link>
                )}
              </div>
            )}
            <Dialog
              open={!!conversion}
              onOpenChange={(open) => {
                if (!open) setConversion(undefined);
              }}
            >
              <DialogContent className="lm-dialog">
                <DialogTitle>Review lead conversion</DialogTitle>
                <p>
                  Create or reuse a contact and company, and create a deal for
                  this qualified lead. Existing lead history is retained.
                </p>
                <Field label="Contact">
                  <select
                    value={conversionIds.existingContactId}
                    onChange={(e) =>
                      setConversionIds((v) => ({
                        ...v,
                        existingContactId: e.target.value,
                      }))
                    }
                  >
                    <option value="">Create a new contact</option>
                    {conversion?.matches.contacts.map((c) => (
                      <option value={c.id} key={c.id}>
                        Reuse {c.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Company">
                  <select
                    value={conversionIds.existingCompanyId}
                    onChange={(e) =>
                      setConversionIds((v) => ({
                        ...v,
                        existingCompanyId: e.target.value,
                      }))
                    }
                  >
                    <option value="">
                      {lead.company_name
                        ? "Create or match company by name"
                        : "No company will be created"}
                    </option>
                    {conversion?.matches.companies.map((c) => (
                      <option value={c.id} key={c.id}>
                        Reuse {c.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Button
                  disabled={busy || !conversion?.ready}
                  onClick={async () => {
                    if (
                      await act(
                        () =>
                          leadsApi.convert(id, {
                            existingContactId: conversionIds.existingContactId
                              ? Number(conversionIds.existingContactId)
                              : null,
                            existingCompanyId: conversionIds.existingCompanyId
                              ? Number(conversionIds.existingCompanyId)
                              : null,
                          }),
                        "Lead converted; customer records are linked below",
                      )
                    )
                      setConversion(undefined);
                  }}
                >
                  Convert & open linked records
                </Button>
              </DialogContent>
            </Dialog>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function ExcelDialog({
  close,
  imported,
}: {
  close: () => void;
  imported: () => void;
}) {
  const { toast } = useToast();
  const [preview, setPreview] = useState<ImportPreview>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !busy) close();
      }}
    >
      <DialogContent className="lm-dialog lm-excel-dialog">
        <DialogTitle>Import leads from Excel</DialogTitle>
        <p>
          Upload .xlsx or UTF-8 .csv, up to 3 MB / 5,000 rows. Duplicate emails
          and phone numbers are skipped. No leads are saved until you review and
          import.
        </p>
        <Button
          variant="outline"
          disabled={busy}
          onClick={async () => {
            try {
              download(
                (await leadsApi.template()).data,
                "lead-import-template.xlsx",
              );
            } catch (err) {
              setError(errorMessage(err));
            }
          }}
        >
          <Download size={16} />
          Download Excel template
        </Button>
        <label className="lm-upload">
          Choose an Excel workbook
          <input
            ref={input}
            type="file"
            accept=".xlsx,.csv"
            disabled={busy}
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              setPreview(undefined);
              setError("");
              if (file.size > 3 * 1024 * 1024) {
                setError("Choose a file smaller than 3 MB");
                return;
              }
              setBusy(true);
              try {
                setPreview((await leadsApi.previewImport(file)).data);
              } catch (err) {
                setError(errorMessage(err));
              } finally {
                setBusy(false);
              }
            }}
          />
        </label>
        {busy && <p role="status">Processing workbook…</p>}
        {error && <ErrorNotice message={error} />}
        {preview && (
          <>
            <div className="lm-import-summary">
              <strong>{preview.ready} ready</strong>
              <span>{preview.skipped.length} duplicates skipped</span>
              <span>{preview.errors.length} errors</span>
            </div>
            {preview.errors.length > 0 && (
              <div className="lm-error">
                Correct the listed rows and upload the workbook again. No
                records have been imported.
                <ul>
                  {preview.errors.map((e) => (
                    <li key={e.row}>
                      Row {e.row}:{" "}
                      {typeof e.error === "string"
                        ? e.error
                        : JSON.stringify(e.error)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {preview.skipped.length > 0 && (
              <details>
                <summary>Review skipped duplicate rows</summary>
                <ul>
                  {preview.skipped.map((s) => (
                    <li key={s.row}>
                      Row {s.row}: {s.reason}
                    </li>
                  ))}
                </ul>
              </details>
            )}
            <div className="lm-table-scroll">
              <table className="lm-table">
                <caption>Preview of the first 10 valid leads</caption>
                <thead>
                  <tr>
                    <th>Row</th>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Company</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.validRows.slice(0, 10).map((row) => (
                    <tr key={row.row}>
                      <td>{row.row}</td>
                      <td>{String(row.values.full_name || "")}</td>
                      <td>{String(row.values.email || "")}</td>
                      <td>{String(row.values.company_name || "")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Button
              disabled={busy || !preview.ready || preview.errors.length > 0}
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  const response = await leadsApi.import(preview.rows);
                  toast({
                    title: `${response.data.created} leads imported`,
                    description: `${response.data.skipped.length} duplicates skipped.`,
                  });
                  imported();
                } catch (err) {
                  setError(errorMessage(err));
                } finally {
                  setBusy(false);
                }
              }}
            >
              Import {preview.ready} leads
            </Button>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function WorkflowSettings({
  bootstrap,
  close,
  saved,
}: {
  bootstrap: Bootstrap;
  close: () => void;
  saved: () => void;
}) {
  const [settings, setSettings] = useState<Settings>(() =>
    JSON.parse(JSON.stringify(bootstrap.settings)),
  );
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState("stages");
  const [stageName, setStageName] = useState("");
  const [capture, setCapture] = useState<{
    enabled: boolean;
    path?: string;
    ownerId?: number;
  }>();
  const [captureOwner, setCaptureOwner] = useState(
    bootstrap.owners[0]?.id || bootstrap.userId,
  );
  useRefreshableEffect(() => {
    leadsApi
      .captureSettings()
      .then((r) => {
        setCapture(r.data);
        if (r.data.ownerId) setCaptureOwner(r.data.ownerId);
      })
      .catch((err) => setError(errorMessage(err)));
  }, []);
  const updateStage = (
    index: number,
    patch: Partial<Settings["stages"][number]>,
  ) =>
    setSettings((s) => ({
      ...s,
      stages: s.stages.map((v, i) => (i === index ? { ...v, ...patch } : v)),
    }));
  const required = [
    "email",
    "phone",
    "company_name",
    "need",
    "budget",
    "decisionMaker",
    "timeline",
    "lossReason",
    "competitor",
    "next_follow_up_at",
  ];
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !busy) close();
      }}
    >
      <DialogContent className="lm-dialog lm-settings-dialog">
        <DialogTitle>Lead workflow settings</DialogTitle>
        <p>
          Organization-wide rules apply to lead workbench operations and Excel
          imports.
        </p>
        <nav className="lm-tabs">
          {["stages", "assignment", "sequences", "automation", "website"].map(
            (name) => (
              <button
                key={name}
                aria-pressed={tab === name}
                className={tab === name ? "active" : ""}
                onClick={() => setTab(name)}
              >
                {name}
              </button>
            ),
          )}
        </nav>
        <fieldset disabled={busy} className="lm-fieldset">
          {tab === "stages" && (
            <>
              <div className="lm-form-grid">
                <Field label="First-response deadline (hours)">
                  <input
                    type="number"
                    min="1"
                    max="8760"
                    value={settings.slaHours}
                    onChange={(e) =>
                      setSettings((s) => ({
                        ...s,
                        slaHours: Number(e.target.value),
                      }))
                    }
                  />
                </Field>
                <Field label="Flag inactive after (days)">
                  <input
                    type="number"
                    min="1"
                    max="365"
                    value={settings.staleDays}
                    onChange={(e) =>
                      setSettings((s) => ({
                        ...s,
                        staleDays: Number(e.target.value),
                      }))
                    }
                  />
                </Field>
              </div>
              <label className="lm-check">
                <input
                  type="checkbox"
                  checked={settings.preventDuplicates}
                  onChange={(e) =>
                    setSettings((s) => ({
                      ...s,
                      preventDuplicates: e.target.checked,
                    }))
                  }
                />
                Prevent matching email / phone duplicates
              </label>
              {settings.stages.map((stage, index) => (
                <section className="lm-section" key={index}>
                  <h3>{stage.name}</h3>
                  <div className="lm-form-grid">
                    <div>
                      <p>Allowed next stages</p>
                      {settings.stages
                        .filter(
                          (s) =>
                            s.name !== stage.name && s.name !== "Converted",
                        )
                        .map((next) => (
                          <label className="lm-check" key={next.name}>
                            <input
                              type="checkbox"
                              checked={stage.allowedNext.includes(next.name)}
                              disabled={stage.name === "Converted"}
                              onChange={(e) =>
                                updateStage(index, {
                                  allowedNext: e.target.checked
                                    ? [...stage.allowedNext, next.name]
                                    : stage.allowedNext.filter(
                                        (n) => n !== next.name,
                                      ),
                                })
                              }
                            />
                            {next.name}
                          </label>
                        ))}
                    </div>
                    <div>
                      <p>Required before entering</p>
                      {required.map((field) => (
                        <label className="lm-check" key={field}>
                          <input
                            type="checkbox"
                            checked={stage.required.includes(field)}
                            onChange={(e) =>
                              updateStage(index, {
                                required: e.target.checked
                                  ? [...stage.required, field]
                                  : stage.required.filter((n) => n !== field),
                              })
                            }
                          />
                          {field.replace(/_/g, " ")}
                        </label>
                      ))}
                    </div>
                  </div>
                </section>
              ))}
              <div className="lm-actions">
                <input
                  aria-label="New stage name"
                  maxLength={40}
                  value={stageName}
                  onChange={(e) => setStageName(e.target.value)}
                  placeholder="Add a custom stage"
                />
                <Button
                  variant="outline"
                  size="sm"
                  disabled={
                    !stageName.trim() ||
                    settings.stages.some((s) => s.name === stageName.trim())
                  }
                  onClick={() => {
                    setSettings((s) => ({
                      ...s,
                      stages: [
                        ...s.stages,
                        {
                          name: stageName.trim(),
                          required: [],
                          allowedNext: ["Qualified", "Lost"],
                        },
                      ],
                    }));
                    setStageName("");
                  }}
                >
                  Add stage
                </Button>
              </div>
            </>
          )}
          {tab === "assignment" && (
            <>
              <Field label="Distribution method">
                <select
                  value={settings.assignment.mode}
                  onChange={(e) =>
                    setSettings((s) => ({
                      ...s,
                      assignment: { ...s.assignment, mode: e.target.value },
                    }))
                  }
                >
                  <option value="manual">
                    Manual / existing territory rules
                  </option>
                  <option value="round_robin">Round-robin</option>
                  <option value="workload">Fewest active leads</option>
                </select>
              </Field>
              <h3>Eligible owners</h3>
              {bootstrap.owners.map((owner) => (
                <label className="lm-check" key={owner.id}>
                  <input
                    type="checkbox"
                    checked={settings.assignment.ownerIds.includes(owner.id)}
                    onChange={(e) =>
                      setSettings((s) => ({
                        ...s,
                        assignment: {
                          ...s.assignment,
                          ownerIds: e.target.checked
                            ? [...s.assignment.ownerIds, owner.id]
                            : s.assignment.ownerIds.filter(
                                (id) => id !== owner.id,
                              ),
                        },
                      }))
                    }
                  />
                  {owner.name}
                </label>
              ))}
              <section className="lm-section">
                <h3>Assignment rules</h3>
                <p>
                  First matching rule wins; otherwise use the distribution
                  method.
                </p>
                {settings.assignment.rules.map((rule, index) => (
                  <div className="lm-rule-editor" key={index}>
                    <select
                      aria-label="Assignment condition field"
                      value={rule.field}
                      onChange={(e) =>
                        setSettings((s) => ({
                          ...s,
                          assignment: {
                            ...s.assignment,
                            rules: s.assignment.rules.map((r, i) =>
                              i === index ? { ...r, field: e.target.value } : r,
                            ),
                          },
                        }))
                      }
                    >
                      {[
                        "source",
                        "city",
                        "state",
                        "country",
                        "industry",
                        "territory_id",
                        "product",
                      ].map((name) => (
                        <option key={name}>{name}</option>
                      ))}
                    </select>
                    <input
                      aria-label="Assignment match value"
                      placeholder="Equals"
                      value={rule.equals}
                      onChange={(e) =>
                        setSettings((s) => ({
                          ...s,
                          assignment: {
                            ...s.assignment,
                            rules: s.assignment.rules.map((r, i) =>
                              i === index
                                ? { ...r, equals: e.target.value }
                                : r,
                            ),
                          },
                        }))
                      }
                    />
                    <select
                      aria-label="Rule owner"
                      value={rule.ownerId}
                      onChange={(e) =>
                        setSettings((s) => ({
                          ...s,
                          assignment: {
                            ...s.assignment,
                            rules: s.assignment.rules.map((r, i) =>
                              i === index
                                ? { ...r, ownerId: Number(e.target.value) }
                                : r,
                            ),
                          },
                        }))
                      }
                    >
                      {bootstrap.owners.map((o) => (
                        <option key={o.id} value={o.id}>
                          {o.name}
                        </option>
                      ))}
                    </select>
                    <button
                      aria-label="Remove assignment rule"
                      onClick={() =>
                        setSettings((s) => ({
                          ...s,
                          assignment: {
                            ...s.assignment,
                            rules: s.assignment.rules.filter(
                              (_, i) => i !== index,
                            ),
                          },
                        }))
                      }
                    >
                      <X size={16} />
                    </button>
                  </div>
                ))}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    setSettings((s) => ({
                      ...s,
                      assignment: {
                        ...s.assignment,
                        rules: [
                          ...s.assignment.rules,
                          {
                            field: "source",
                            equals: "Website",
                            ownerId:
                              bootstrap.owners[0]?.id || bootstrap.userId,
                          },
                        ],
                      },
                    }))
                  }
                >
                  Add assignment rule
                </Button>
              </section>
            </>
          )}
          {tab === "sequences" && (
            <>
              <p>
                Sequence steps become scheduled call, email, meeting or
                follow-up tasks. They stop when a response is logged.
              </p>
              {settings.sequences.map((sequence, index) => (
                <section className="lm-section" key={index}>
                  <Field label="Sequence name">
                    <input
                      value={sequence.name}
                      onChange={(e) =>
                        setSettings((s) => ({
                          ...s,
                          sequences: s.sequences.map((v, i) =>
                            i === index ? { ...v, name: e.target.value } : v,
                          ),
                        }))
                      }
                    />
                  </Field>
                  {sequence.steps.map((step, stepIndex) => (
                    <div className="lm-rule-editor" key={stepIndex}>
                      <Field label="Days after start">
                        <input
                          type="number"
                          min="0"
                          max="365"
                          value={step.day}
                          onChange={(e) =>
                            setSettings((s) => ({
                              ...s,
                              sequences: s.sequences.map((v, i) =>
                                i === index
                                  ? {
                                      ...v,
                                      steps: v.steps.map((st, j) =>
                                        j === stepIndex
                                          ? {
                                              ...st,
                                              day: Number(e.target.value),
                                            }
                                          : st,
                                      ),
                                    }
                                  : v,
                              ),
                            }))
                          }
                        />
                      </Field>
                      <Field label="Task type">
                        <select
                          value={step.type}
                          onChange={(e) =>
                            setSettings((s) => ({
                              ...s,
                              sequences: s.sequences.map((v, i) =>
                                i === index
                                  ? {
                                      ...v,
                                      steps: v.steps.map((st, j) =>
                                        j === stepIndex
                                          ? { ...st, type: e.target.value }
                                          : st,
                                      ),
                                    }
                                  : v,
                              ),
                            }))
                          }
                        >
                          {["call", "email", "task", "meeting"].map((name) => (
                            <option key={name}>{name}</option>
                          ))}
                        </select>
                      </Field>
                      <Field label="Task title">
                        <input
                          value={step.title}
                          onChange={(e) =>
                            setSettings((s) => ({
                              ...s,
                              sequences: s.sequences.map((v, i) =>
                                i === index
                                  ? {
                                      ...v,
                                      steps: v.steps.map((st, j) =>
                                        j === stepIndex
                                          ? { ...st, title: e.target.value }
                                          : st,
                                      ),
                                    }
                                  : v,
                              ),
                            }))
                          }
                        />
                      </Field>
                      <button
                        aria-label="Remove sequence step"
                        onClick={() =>
                          setSettings((s) => ({
                            ...s,
                            sequences: s.sequences.map((v, i) =>
                              i === index
                                ? {
                                    ...v,
                                    steps: v.steps.filter(
                                      (_, j) => j !== stepIndex,
                                    ),
                                  }
                                : v,
                            ),
                          }))
                        }
                      >
                        <X size={16} />
                      </button>
                    </div>
                  ))}
                  <div className="lm-actions">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setSettings((s) => ({
                          ...s,
                          sequences: s.sequences.map((v, i) =>
                            i === index
                              ? {
                                  ...v,
                                  steps: [
                                    ...v.steps,
                                    {
                                      day: 1,
                                      type: "task",
                                      title: "Follow up",
                                    },
                                  ],
                                }
                              : v,
                          ),
                        }))
                      }
                    >
                      Add step
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        setSettings((s) => ({
                          ...s,
                          sequences: s.sequences.filter((_, i) => i !== index),
                        }))
                      }
                    >
                      Remove sequence
                    </Button>
                  </div>
                </section>
              ))}
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  setSettings((s) => ({
                    ...s,
                    sequences: [
                      ...s.sequences,
                      {
                        name: `Follow-up ${s.sequences.length + 1}`,
                        steps: [
                          { day: 0, type: "call", title: "Make first contact" },
                        ],
                      },
                    ],
                  }))
                }
              >
                New sequence
              </Button>
            </>
          )}
          {tab === "automation" && (
            <>
              <p>
                Create tasks, notify owners or assign leads when a lead is
                created, changes stage or responds.
              </p>
              {settings.workflows.map((rule, index) => {
                const update = (patch: Partial<typeof rule>) =>
                  setSettings((s) => ({
                    ...s,
                    workflows: s.workflows.map((r, i) =>
                      i === index ? { ...r, ...patch } : r,
                    ),
                  }));
                return (
                  <section className="lm-section" key={index}>
                    <div className="lm-form-grid">
                      <Field label="Rule name">
                        <input
                          value={rule.name}
                          onChange={(e) => update({ name: e.target.value })}
                        />
                      </Field>
                      <Field label="When">
                        <select
                          value={rule.trigger}
                          onChange={(e) => update({ trigger: e.target.value })}
                        >
                          <option value="created">Lead created</option>
                          <option value="stage_changed">Stage changed</option>
                          <option value="responded">Lead responded</option>
                        </select>
                      </Field>
                      <Field label="Only in stage">
                        <select
                          value={rule.stage}
                          onChange={(e) => update({ stage: e.target.value })}
                        >
                          <option value="">Any stage</option>
                          {settings.stages.map((s) => (
                            <option key={s.name}>{s.name}</option>
                          ))}
                        </select>
                      </Field>
                      <Field label="Then">
                        <select
                          value={rule.action}
                          onChange={(e) => update({ action: e.target.value })}
                        >
                          <option value="task">Create task</option>
                          <option value="notify">Notify owner</option>
                          <option value="assign">Assign owner</option>
                        </select>
                      </Field>
                      <Field label="Task or notification title">
                        <input
                          value={rule.title}
                          onChange={(e) => update({ title: e.target.value })}
                        />
                      </Field>
                      {rule.action === "assign" ? (
                        <Field label="Assign to">
                          <select
                            value={rule.ownerId || ""}
                            onChange={(e) =>
                              update({ ownerId: Number(e.target.value) })
                            }
                          >
                            <option value="">Choose owner</option>
                            {bootstrap.owners.map((o) => (
                              <option value={o.id} key={o.id}>
                                {o.name}
                              </option>
                            ))}
                          </select>
                        </Field>
                      ) : (
                        <Field label="Task due after (hours)">
                          <input
                            type="number"
                            min="0"
                            value={rule.delayHours}
                            onChange={(e) =>
                              update({ delayHours: Number(e.target.value) })
                            }
                          />
                        </Field>
                      )}
                    </div>
                    <label className="lm-check">
                      <input
                        type="checkbox"
                        checked={rule.enabled}
                        onChange={(e) => update({ enabled: e.target.checked })}
                      />
                      Enabled
                    </label>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        setSettings((s) => ({
                          ...s,
                          workflows: s.workflows.filter((_, i) => i !== index),
                        }))
                      }
                    >
                      Remove rule
                    </Button>
                  </section>
                );
              })}
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  setSettings((s) => ({
                    ...s,
                    workflows: [
                      ...s.workflows,
                      {
                        name: `Workflow ${s.workflows.length + 1}`,
                        enabled: true,
                        trigger: "created",
                        stage: "",
                        action: "task",
                        title: "Review new enquiry",
                        delayHours: 1,
                      },
                    ],
                  }))
                }
              >
                Add automation
              </Button>
            </>
          )}
          {tab === "website" && (
            <>
              <h3>Website enquiry form</h3>
              <p>
                Publish a dedicated enquiry link. Submissions enter the enquiry
                inbox with an accountable owner, source, consent timestamp and
                duplicate prevention.
              </p>
              <Field label="Responsible intake owner">
                <select
                  value={captureOwner}
                  onChange={(e) => setCaptureOwner(Number(e.target.value))}
                >
                  {bootstrap.owners.map((o) => (
                    <option value={o.id} key={o.id}>
                      {o.name}
                    </option>
                  ))}
                </select>
              </Field>
              <p>Form status: {capture?.enabled ? "Active" : "Disabled"}</p>
              <div className="lm-actions">
                <Button
                  variant="outline"
                  onClick={async () => {
                    setBusy(true);
                    try {
                      setCapture(
                        (await leadsApi.enableCapture(true, captureOwner)).data,
                      );
                    } catch (err) {
                      setError(errorMessage(err));
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  {capture?.enabled
                    ? "Rotate link & update owner"
                    : "Enable enquiry form"}
                </Button>
                {capture?.enabled && (
                  <Button
                    variant="outline"
                    onClick={async () => {
                      try {
                        setCapture(
                          (await leadsApi.enableCapture(false, captureOwner))
                            .data,
                        );
                      } catch (err) {
                        setError(errorMessage(err));
                      }
                    }}
                  >
                    Disable form
                  </Button>
                )}
              </div>
              {capture?.enabled && capture.path && (
                <Field label="Share or link from your website">
                  <input
                    readOnly
                    value={publicUrl(capture.path)}
                    onFocus={(e) => e.target.select()}
                  />
                </Field>
              )}
              {capture?.enabled && capture.path && (
                <Field label="Embed this HTML form on your website">
                  <textarea
                    readOnly
                    rows={6}
                    value={captureEmbed(capture.path)}
                    onFocus={(e) => e.target.select()}
                  />
                </Field>
              )}
              <p>
                Rotating the link revokes the old form. The form accepts up to
                100 enquiries per hour for this organization, including repeat
                submissions.
              </p>
            </>
          )}{" "}
        </fieldset>
        {error && <ErrorNotice message={error} />}
        <div className="lm-dialog-actions">
          <span>Changes apply after saving</span>
          <Button
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                await leadsApi.settings(settings);
                saved();
              } catch (err) {
                setError(errorMessage(err));
              } finally {
                setBusy(false);
              }
            }}
          >
            Save workflow settings
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
