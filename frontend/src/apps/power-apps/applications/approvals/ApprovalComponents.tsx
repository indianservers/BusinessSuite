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
      <select
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
      </select>
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
    <button className="ap-request-row" onClick={onOpen}>
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
      <span className="ap-priority">{row.priority}</span>
      <span className="ap-row-date">{formatDate(row.created_at)}</span>
      <ChevronRight size={16} />
    </button>
  );
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
  }, [environment, tab, searchQuery, offset, sort, priority]);
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
          <select
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
          </select>
        </label>
        <label>
          Priority
          <select
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
          </select>
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
            <ApprovalRequestCard
              key={row.id}
              row={row}
              onOpen={() => onOpen(row.id)}
            />
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
  const task = request.assignments.find((a) => a.can_decide);
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
        <button disabled={busy} onClick={() => void decide("changes")}>
          Request changes
        </button>
        <button
          className="ap-danger"
          disabled={busy}
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
  const load = useCallback(() => {
    api
      .get<Detail>(`/requests/${id}`, environment)
      .then((r) => {
        setRequest(r);
        if (!dirtyFields.current)
          setFields(JSON.stringify(r.state.fields, null, 2));
      })
      .catch((e) => setError(errorMessage(e)));
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
    try {
      await api.post(`/requests/${id}/${action}`, environment, data);
      if (action === "resubmit") dirtyFields.current = false;
      changed();
    } catch (e) {
      setError(errorMessage(e));
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
          <>
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
            {r.can_resubmit && (
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
            {r.can_reassign && (
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
                disabled={!comment.trim()}
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
            {r.can_cancel &&
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
          </>
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
    <form
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
        <select
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
        </select>
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
            <select
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
            </select>
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
    </form>
  );
}
export const ApprovalRequestForm = ApprovalForm;
