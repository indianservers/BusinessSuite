import { useModuleAction } from "@/hooks/use-module-action";
import {useAuthStore} from "@/store/authStore";
import { NativeSelect } from "@/components/ui/native-select";
import CompactForm from "@/components/forms/CompactForm";
import { useCallback, useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import {
  Search,
  Inbox,
  X,
  Clock3,
  ShieldCheck,
  FileText,
  ChevronRight,
  Check,
} from "lucide-react";
import {
  approvalApi as api,
  errorMessage,
  formatDate,
  download,
  upload,
  type RequestRow,
  type Detail,
  type Person,
  type Policy,
} from "./api";
export function ApprovalSLAIndicator({
  due,
  status,
}: {
  due: string | null;
  status: string;
}) {
  return (
    <span
      className={
        due && new Date(due) < new Date() && status === "Pending"
          ? "ap-overdue"
          : "ap-muted"
      }
    >
      <Clock3 size={12} />
      {due ? formatDate(due) : "No active deadline"}
    </span>
  );
}
export function ApproverPicker({
  people,
  value,
  onChange,
  label = "Approvers",
}: {
  people: Person[];
  label?: string;
  value: number[];
  onChange: (ids: number[]) => void;
}) {
  return (
    <label>
      {label}
      <NativeSelect
        multiple
        value={value.map(String)}
        onChange={(e) =>
          onChange(
            Array.from(e.target.selectedOptions).map((o) => Number(o.value)),
          )
        }
      >
        {people.map((p) => (
          <option value={p.id} key={p.id}>
            {p.label}
          </option>
        ))}
      </NativeSelect>
      <small>Choose independent eligible company identities.</small>
    </label>
  );
}
export function ApprovalRequestCard({
  row,
  onOpen,
}: {
  row: RequestRow;
  onOpen: () => void;
}) {
  return (
    <button data-priority-row data-priority={row.priority} className="ap-request-row" onClick={onOpen}>
      <span className="ap-avatar">
        {(row.requester_name || `User ${row.requester_user_id}`)
          .split(" ")
          .map((s) => s[0])
          .slice(0, 2)
          .join("")}
      </span>
      <span>
        <strong>{row.title}</strong>
        <small>
          {row.requester_name || `User #${row.requester_user_id}`} ·{" "}
          {row.request_type || `Request #${row.id}`}
        </small>
        {row.current_stage && (
          <small>
            {row.current_stage} · Approvers{" "}
            {row.assigned_user_ids?.map((id) => `#${id}`).join(", ")}
          </small>
        )}
      </span>
      <span
        className={`ap-badge ${row.status === "Approved" ? "success" : ""}`}
      >
        {row.status}
      </span>
      <span data-priority-badge data-priority={row.priority} className="ap-priority">{row.priority}</span>
      <span className="ap-row-date">{formatDate(row.created_at)}</span>
      <ChevronRight size={16} />
    </button>
  );
}
function QuickApprovalReview({ row, environment, onChanged, onOpen }: { row: RequestRow; environment: string; onChanged: () => void; onOpen: () => void }) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<Detail>();
  const [error, setError] = useState("");
  useEffect(() => {
    if (!open) return;
    let active = true;
    setDetail(undefined); setError("");
    api.get<Detail>(`/requests/${row.id}`, environment).then(data => { if (active) setDetail(data); }).catch(e => { if (active) setError(errorMessage(e)); });
    return () => { active = false; };
  }, [open, row.id, environment]);
  return <div className="ap-actions" style={{padding: 12, flexDirection: "column", alignItems: "stretch"}}>
    <button aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Close quick review" : "Review & decide"}</button>
    {open && <section aria-label={`Quick approval review: ${row.title}`}>
      {error && <p role="alert" className="ap-error">{error}</p>}
      {!detail && !error && <p role="status">Loading request…</p>}
      {detail && <><p>{detail.description || "No description provided."}</p>
        {Object.entries(detail.state.fields).map(([key, value]) => <p key={key}><strong>{key.replace(/_/g, " ")}: </strong>{typeof value === "object" ? JSON.stringify(value) : String(value ?? "—")}</p>)}
        <button onClick={onOpen}>Full details & documents</button>
        <ApprovalDecisionPanel request={detail} environment={environment} onError={setError} onChanged={() => { setOpen(false); onChanged(); }} />
      </>}
    </section>}
  </div>;
}

export function ApprovalInbox({
  environment,
  scope = "assigned",
  onOpen,
}: {
  environment: string;
  scope?: string;
  onOpen: (id: number) => void;
}) {
  const [tab, setTab] = useState(scope),
    [refresh, setRefresh] = useState(0),
    [search, setSearch] = useState(""),
    [rows, setRows] = useState<RequestRow[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [offset, setOffset] = useState(0),
    [total, setTotal] = useState(0),
    [sort, setSort] = useState("created"),
    [priority, setPriority] = useState(""),
    [searchQuery, setSearchQuery] = useState("");
  useEffect(() => {
    const timer = window.setTimeout(() => setSearchQuery(search), 250);
    return () => window.clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    let live = true;
    setLoading(true);
    const status = ["Pending", "Approved", "Rejected"].includes(tab)
      ? tab
      : undefined;
    api
      .get<{ items: RequestRow[]; total: number }>("/requests", environment, {
        scope: status ? "all" : tab,
        status,
        search: searchQuery,
        offset,
        sort,
        priority: priority || undefined,
      })
      .then((r) => {
        if (live) {
          setRows(r.items);
          setTotal(r.total);
        }
      })
      .catch((e) => {
        if (live) setError(errorMessage(e));
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [environment, tab, searchQuery, offset, sort, priority, refresh]);
  return (
    <>
      <div className="ap-tabs">
        {[
          ["assigned", "Assigned to me"],
          ["team", "Team queue"],
          ["submitted", "Requested by me"],
          ["delegated", "Delegated to me"],
          ["Pending", "Pending"],
          ["Approved", "Completed"],
          ["Rejected", "Rejected"],
          ["overdue", "Overdue"],
        ].map(([key, label]) => (
          <button
            key={key}
            className={tab === key ? "active" : ""}
            onClick={() => {
              setTab(key);
              setOffset(0);
            }}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="ap-actions" style={{ marginBottom: 12 }}>
        <label>
          Sort requests
          <NativeSelect
            aria-label="Sort requests"
            value={sort}
            onChange={(e) => {
              setSort(e.target.value);
              setOffset(0);
            }}
          >
            <option value="created">Newest first</option>
            <option value="due">Due date</option>
            <option value="priority">Priority</option>
          </NativeSelect>
        </label>
        <label>
          Priority
          <NativeSelect
            aria-label="Filter priority"
            value={priority}
            onChange={(e) => {
              setPriority(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">All priorities</option>
            {["Low", "Normal", "High", "Urgent"].map((p) => (
              <option key={p}>{p}</option>
            ))}
          </NativeSelect>
        </label>
      </div>
      <div className="ap-search">
        <Search size={17} />
        <input
          aria-label="Search approval requests"
          placeholder="Search requests by title…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setOffset(0);
          }}
        />
        <small>{total} requests</small>
      </div>
      {error && (
        <p className="ap-error" role="alert">
          {error}
        </p>
      )}
      <div className="ap-panel">
        {loading ? (
          <p className="ap-empty">Loading approvals…</p>
        ) : rows.length ? (
          rows.map((row) => (
            <div key={row.id}>
            <ApprovalRequestCard
              row={row}
              onOpen={() => onOpen(row.id)}
            />
            {row.status === "Pending" && ["assigned", "delegated"].includes(tab) && <QuickApprovalReview row={row} environment={environment} onOpen={() => onOpen(row.id)} onChanged={() => setRefresh(value => value + 1)} />}
            </div>
          ))
        ) : (
          <div className="ap-empty">
            <Inbox size={33} />
            <h3>Your queue is clear</h3>
            <p>No approval requests match this view.</p>
          </div>
        )}
      </div>
      <div className="ap-actions">
        <button
          disabled={!offset}
          onClick={() => setOffset(Math.max(0, offset - 40))}
        >
          Previous
        </button>
        <button
          disabled={offset + 40 >= total}
          onClick={() => setOffset(offset + 40)}
        >
          Next
        </button>
      </div>
    </>
  );
}
export function ApprovalTimeline({ request }: { request: Detail }) {
  return (
    <ol className="ap-timeline">
      {request.history.map((h) => (
        <li key={h.id}>
          <span className="ap-timeline-dot" />
          <div>
            <strong>{h.event_type.replace(/_/g, " ")}</strong>
            <small>
              {formatDate(h.created_at)} ·{" "}
              {h.actor_user_id ? `User #${h.actor_user_id}` : "Workflow worker"}
            </small>
            {h.reason && <p>{h.reason}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}
export const ApprovalHistory = ApprovalTimeline;
export function ApprovalDecisionPanel({
  request,
  environment,
  onChanged,
  onError,
}: {
  request: Detail;
  environment: string;
  onChanged: () => void;
  onError: (s: string) => void;
}) {
  const [reason, setReason] = useState(""),
    [busy, setBusy] = useState(false);
  const actor=useAuthStore(s=>s.user),grant=actor?.access?.grants.power_apps;
  const canApprove=!!actor?.is_superuser||!actor?.access?.managed||!!grant?.enabled&&grant.actions.includes("approve");
  const task = canApprove?request.assignments.find((a) => a.can_decide):undefined;
  if (!task)
    return <p className="ap-muted">You have no active decision assignment.</p>;
  const decide = async (decision: string) => {
    setBusy(true);
    try {
      await api.post(`/requests/${request.id}/decisions`, environment, {
        assignment_id: task.id,
        expected_revision: request.state.revision,
        decision,
        reason,
        request_key: crypto.randomUUID(),
      });
      onChanged();
      setReason("");
    } catch (e) {
      onError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="ap-decision">
      <label>
        Decision reason
        <textarea
          value={reason}
          maxLength={4000}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Explain your decision or the changes needed"
        />
      </label>
      <div className="ap-actions">
        <button
          className="ap-primary"
          disabled={busy}
          onClick={() => void decide("approve")}
        >
          <Check size={14} />
          Approve
        </button>
        <button disabled={busy || !reason.trim()} onClick={() => void decide("changes")}>
          Request changes
        </button>
        <button
          className="ap-danger"
          disabled={busy || !reason.trim()}
          onClick={() => void decide("reject")}
        >
          Reject
        </button>
      </div>
      <small>
        Recorded against your authenticated identity and current policy version.
      </small>
    </div>
  );
}
export function ApprovalDetailsDrawer({
  id,
  environment,
  onClose,
  onChanged,
}: {
  id: number;
  environment: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const canCreate=useModuleAction("create"),canAssign=useModuleAction("assign");
  const [r, setRequest] = useState<Detail | null>(null),
    [error, setError] = useState(""),
    [comment, setComment] = useState(""),
    [fields, setFields] = useState(""),
    [alternate, setAlternate] = useState("");
  const dialogRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const focusable = () =>
      Array.from(
        dialogRef.current?.querySelectorAll<HTMLElement>(
          'button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]',
        ) || [],
      ).filter((element) => element.getClientRects().length > 0);
    focusable()[0]?.focus();
    const trap = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;
      const items = focusable(),
        first = items[0],
        last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", trap);
    return () => {
      document.removeEventListener("keydown", trap);
      if (previous?.isConnected) previous.focus();
    };
  }, []);
  const dirtyFields = useRef(false);
  const pendingReads=useRef(new Set<string>());
  const mutationPending=useRef(false), readGeneration=useRef(0);
  const [mutating,setMutating]=useState(false);
  const currentRequest=useRef("");currentRequest.current=`${environment}:${id}`;
  const load = useCallback(() => {
    const key=`${environment}:${id}`;
    if(mutationPending.current||pendingReads.current.has(key))return;
    const generation=readGeneration.current;
    pendingReads.current.add(key);
    api
      .get<Detail>(`/requests/${id}`, environment, {}, true)
      .then((r) => {
        if(currentRequest.current!==key||generation!==readGeneration.current)return;
        setRequest(previous=>previous?.id===r.id&&previous.state.revision>r.state.revision?previous:r);
        if (!dirtyFields.current)
          setFields(JSON.stringify(r.state.fields, null, 2));
      })
      .catch((e) => {if(currentRequest.current===key)setError(errorMessage(e));})
      .finally(()=>pendingReads.current.delete(key));
  }, [id, environment]);
  useEffect(load, [load]);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);
  useEffect(() => {
    if (r?.status !== "Pending" && r?.status !== "Resolution Required") return;
    const timer = window.setInterval(load, 3000);
    return () => window.clearInterval(timer);
  }, [r?.status, load]);
  const changed = () => {
    load();
    onChanged();
  };
  const post = async (action: string, data: unknown) => {
    if(mutationPending.current)return;
    mutationPending.current=true;readGeneration.current+=1;setMutating(true);setError("");
    const key=`${environment}:${id}`;
    try {
      const updated=await api.post<Detail>(`/requests/${id}/${action}`, environment, data);
      if(currentRequest.current!==key)return;
      if (action === "resubmit") dirtyFields.current = false;
      setRequest(updated);
      if(!dirtyFields.current)setFields(JSON.stringify(updated.state.fields,null,2));
      onChanged();
    } catch (e) {
      if(currentRequest.current===key)setError(errorMessage(e));
    } finally {
      mutationPending.current=false;setMutating(false);
    }
  };
  return (
    <div className="ap-drawer-backdrop">
      <aside
        ref={dialogRef}
        className="ap-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Approval request details"
      >
        <button
          className="ap-close"
          aria-label="Close request details"
          onClick={onClose}
        >
          <X size={20} />
        </button>
        {error && (
          <p className="ap-error" role="alert">
            {error}
          </p>
        )}
        {r ? (
          <fieldset className="contents" disabled={mutating} aria-busy={mutating}>
            <small className="ap-eyebrow">
              REQUEST #{id} · POLICY VERSION #{r.state.version_id}
            </small>
            <h2>{r.title}</h2>
            <span className="ap-badge">{r.status}</span>
            <p>{r.description || "No description supplied."}</p>
            <ApprovalSLAIndicator due={r.sla_due_at} status={r.status} />
            <section>
              <h3>Request information</h3>
              <dl className="ap-fields">
                {Object.entries(r.state.fields).map(([k, v]) => (
                  <div key={k}>
                    <dt>{k}</dt>
                    <dd>
                      {typeof v === "object" ? JSON.stringify(v) : String(v)}
                    </dd>
                  </div>
                ))}
              </dl>
              <Link
                to={`/power-apps/automations/executions/${r.state.run_id}?environment=${environment}`}
              >
                Linked workflow execution ↗
              </Link>
            </section>
            <section>
              <h3>Approval assignments</h3>
              {r.assignments.map((a) => (
                <div className="ap-assignment" key={a.id}>
                  <span>
                    {a.stage_name}
                    <small>
                      Approver #{a.user_id}
                      {a.original_user_id !== a.user_id
                        ? ` · delegated from #${a.original_user_id}`
                        : ""}{" "}
                      · cycle {a.cycle}
                    </small>
                  </span>
                  <span className="ap-badge">{a.status}</span>
                </div>
              ))}
            </section>
            <ApprovalDecisionPanel
              request={r}
              environment={environment}
              onChanged={changed}
              onError={setError}
            />
            <section>
              <h3>Supporting documents</h3>
              {r.can_upload && (
                <label>
                  Add supporting document
                  <input
                    type="file"
                    accept=".pdf,.png,.jpg,.txt"
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (file)
                        try {
                          await upload(id, environment, file);
                          changed();
                        } catch (error) {
                          setError(errorMessage(error));
                        }
                    }}
                  />
                </label>
              )}
              {r.attachments.length ? (
                r.attachments.map((f) => (
                  <button
                    className="ap-file"
                    key={f.id}
                    onClick={() =>
                      void download(id, environment, f).catch((e) =>
                        setError(errorMessage(e)),
                      )
                    }
                  >
                    <FileText size={15} />
                    {f.name} · download verified version
                  </button>
                ))
              ) : (
                <p className="ap-muted">No supporting documents.</p>
              )}
            </section>
            {r.can_resubmit && canCreate && (
              <section>
                <h3>Revise and resubmit</h3>
                <label>
                  Revised fields (JSON)
                  <textarea
                    rows={6}
                    value={fields}
                    onChange={(e) => {
                      dirtyFields.current = true;
                      setFields(e.target.value);
                    }}
                  />
                </label>
                <button
                  className="ap-primary"
                  onClick={() => {
                    try {
                      void post("resubmit", {
                        expected_revision: r.state.revision,
                        fields: JSON.parse(fields),
                        reason: comment,
                      });
                    } catch {
                      setError("Enter valid JSON fields");
                    }
                  }}
                >
                  Resubmit request
                </button>
              </section>
            )}
            {r.can_reassign && canAssign && (
              <section>
                <h3>Administrative resolution</h3>
                {r.status === "Resolution Required" && (
                  <button
                    onClick={() =>
                      void post("resolve", {
                        expected_revision: r.state.revision,
                        reason: comment,
                      })
                    }
                  >
                    Retry configured approver resolution
                  </button>
                )}
                <label>
                  Alternate user ID
                  <input
                    type="number"
                    min={1}
                    value={alternate}
                    onChange={(e) => setAlternate(e.target.value)}
                  />
                </label>
                <button
                  onClick={() =>
                    void post("reassign", {
                      assignment_id: r.assignments.find(
                        (a) => a.status === "pending",
                      )?.id,
                      user_id: Number(alternate),
                      expected_revision: r.state.revision,
                      reason: comment,
                    })
                  }
                >
                  Reassign with reason below
                </button>
              </section>
            )}
            <section>
              <h3>Discussion</h3>
              {r.comments.map((c) => (
                <p className="ap-comment" key={c.id}>
                  <small>User #{c.author_user_id}</small>
                  {c.comment}
                </p>
              ))}
              <label>
                Comment / administrative reason
                <textarea
                  value={comment}
                  maxLength={4000}
                  onChange={(e) => setComment(e.target.value)}
                />
              </label>
              <button
                disabled={!canCreate||!comment.trim()}
                onClick={() => void post("comments", { text: comment })}
              >
                Add comment
              </button>
            </section>
            <section>
              <h3>Decision history</h3>
              <p className={r.evidence_valid ? "ap-verified" : "ap-error"}>
                <ShieldCheck size={15} />
                {r.evidence_valid
                  ? "Audit evidence verified"
                  : "Audit evidence verification failed"}
              </p>
              <ApprovalTimeline request={r} />
            </section>
            {r.can_cancel && canCreate &&
              ![
                "Approved",
                "Rejected",
                "Cancelled",
                "Expired",
                "Failed",
              ].includes(r.status) && (
                <button
                  className="ap-danger"
                  onClick={() =>
                    void post("cancel", {
                      expected_revision: r.state.revision,
                      reason: comment,
                    })
                  }
                >
                  Cancel request
                </button>
              )}
          </fieldset>
        ) : (
          <p>Loading approval details…</p>
        )}
      </aside>
    </div>
  );
}
export function ApprovalForm({
  environment,
  policies,
  onSubmitted,
}: {
  environment: string;
  policies: Policy[];
  onSubmitted: (id: number) => void;
}) {
  const [policyId, setPolicyId] = useState(""),
    [title, setTitle] = useState(""),
    [description, setDescription] = useState(""),
    [fields, setFields] = useState<Record<string, unknown>>({}),
    [files, setFiles] = useState<File[]>([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const p = policies.find((p) => p.id === Number(policyId));
  const form = p?.published_definition || p?.definition;
  const [requestKey] = useState(() => crypto.randomUUID());
  return (
    <CompactForm
      className="ap-panel ap-form"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        try {
          const r = await api.post<Detail>("/requests", environment, {
            policy_id: Number(policyId),
            title,
            description,
            fields,
            request_key: requestKey,
          });
          for (const file of files) await upload(r.id, environment, file);
          onSubmitted(r.id);
        } catch (e) {
          setError(errorMessage(e));
        } finally {
          setBusy(false);
        }
      }}
    >
      <h2>New approval request</h2>
      <p className="ap-muted">
        Approvers, voting rules and deadlines come from the activated policy.
      </p>
      {error && (
        <p className="ap-error" role="alert">
          {error}
        </p>
      )}
      <label>
        Approval process
        <NativeSelect
          required
          value={policyId}
          onChange={(e) => {
            setPolicyId(e.target.value);
            setFields({});
          }}
        >
          <option value="">Choose an activated process</option>
          {policies
            .filter((p) => p.enabled)
            .map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
        </NativeSelect>
      </label>
      <label>
        Title
        <input
          required
          value={title}
          maxLength={220}
          onChange={(e) => setTitle(e.target.value)}
        />
      </label>
      <label>
        Description
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </label>
      {form?.fields.map((f) => (
        <label key={f.key}>
          {f.label}
          {f.required ? " *" : ""}
          {f.kind === "select" ? (
            <NativeSelect
              required={f.required}
              value={String(fields[f.key] ?? "")}
              onChange={(e) =>
                setFields({ ...fields, [f.key]: e.target.value })
              }
            >
              <option value="">Choose</option>
              {f.options?.map((o) => (
                <option key={o}>{o}</option>
              ))}
            </NativeSelect>
          ) : (
            <input
              required={f.required}
              type={
                f.kind === "number"
                  ? "number"
                  : f.kind === "date"
                    ? "date"
                    : "text"
              }
              value={String(fields[f.key] ?? "")}
              onChange={(e) =>
                setFields({
                  ...fields,
                  [f.key]:
                    f.kind === "number"
                      ? Number(e.target.value)
                      : e.target.value,
                })
              }
            />
          )}
        </label>
      ))}
      <label>
        Supporting documents
        <input
          type="file"
          accept=".pdf,.png,.jpg,.txt"
          multiple
          required={form?.documents_required}
          onChange={(e) => setFiles(Array.from(e.target.files || []))}
        />
        <small>
          Private storage · 2 MB per document · PDF, PNG, JPG or text
        </small>
      </label>
      <button className="ap-primary" disabled={!p || busy}>
        {busy ? "Submitting…" : "Submit for approval"}
      </button>
    </CompactForm>
  );
}
export const ApprovalRequestForm = ApprovalForm;
