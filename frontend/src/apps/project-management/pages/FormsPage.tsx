import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "@/services/api";
import { workspaceError } from "./workspaceTypes";
import FormBuilder from "./FormBuilder";
import FormResponse from "./FormResponse";
import {
  download,
  fresh,
  type Definition,
  type Saved,
  type Reply,
  type Answer,
} from "./formsTypes";
import "./FormsPage.css";
export default function FormsPage() {
  const [params, setParams] = useSearchParams();
  const [workspaces, setWorkspaces] = useState<
    { id: number; name: string; role: string }[]
  >([]);
  const [wid, setWid] = useState(0);
  const [forms, setForms] = useState<Saved[]>([]);
  const [current, setCurrent] = useState<Saved | null>(null);
  const [draft, setDraft] = useState<Definition>(fresh);
  const [selected, setSelected] = useState("");
  const [tab, setTab] = useState("build");
  const [mobile, setMobile] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [dirty, setDirty] = useState(false);
  const [projects, setProjects] = useState<{ id: number; name: string }[]>([]);
  const [members, setMembers] = useState<
    { user_id: number; email: string; role: string }[]
  >([]);
  const [replies, setReplies] = useState<Reply[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const requestId = useRef(crypto.randomUUID());
  const role = workspaces.find((w) => w.id === wid)?.role;
  const admin = role === "Owner" || role === "Admin";
  const base = `/project-management/workspaces/${wid}/forms`;
  useEffect(() => {
    let active = true;
    void api
      .get("/project-management/workspaces")
      .then((r) => {
        if (!active) return;
        setWorkspaces(r.data);
        setWid(
          r.data.some(
            (w: { id: number }) => w.id === Number(params.get("workspace")),
          )
            ? Number(params.get("workspace"))
            : r.data[0]?.id || 0,
        );
      })
      .catch((e) => setError(workspaceError(e)))
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    if (!wid) return;
    let active = true;
    setLoading(true);
    setCurrent(null);
    setForms([]);
    setReplies([]);
    setError("");
    setNotice("");
    setDirty(false);
    void Promise.all([
      api.get(base),
      api.get(`/project-management/workspaces/${wid}/overview`),
      api.get(`/project-management/workspaces/${wid}/members`),
    ])
      .then(([f, p, m]) => {
        if (!active) return;
        setForms(f.data);
        setProjects(p.data.projects);
        setMembers(m.data.filter((x: { role: string }) => x.role !== "Guest"));
        const chosen =
          f.data.find((v: Saved) => v.id === Number(params.get("form"))) ||
          f.data[0];
        if (chosen) {
          setCurrent(chosen);
          setDraft(chosen.draft || chosen.definition);
          setSelected((chosen.draft || chosen.definition).fields[0]?.id || "");
        } else setDraft(fresh());
        setTab(
          params.get("view") === "fill" ||
            !["Owner", "Admin"].includes(
              workspaces.find((w) => w.id === wid)?.role || "",
            )
            ? "fill"
            : "build",
        );
      })
      .catch((e) => {
        if (active) setError(workspaceError(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [wid]);
  useEffect(() => {
    const h = (e: BeforeUnloadEvent) => {
      if (dirty) e.preventDefault();
    };
    window.addEventListener("beforeunload", h);
    return () => window.removeEventListener("beforeunload", h);
  }, [dirty]);
  useEffect(() => {
    if (tab !== "responses" || !current || !admin) return;
    let active = true;
    setReplies([]);
    setLoading(true);
    void api
      .get(`${base}/${current.id}/responses`, { params: { offset, limit: 25 } })
      .then((r) => {
        if (active) {
          setReplies(r.data.items);
          setTotal(r.data.total);
        }
      })
      .catch((e) => {
        if (active) setError(workspaceError(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [tab, current?.id, offset, wid]);
  function edit(d: Definition) {
    setDraft(d);
    setDirty(true);
    setNotice("");
  }
  function choose(f: Saved) {
    if (dirty && !window.confirm("Discard unsaved form changes?")) return;
    setCurrent(f);
    setDraft(f.draft || f.definition!);
    setSelected((f.draft || f.definition!).fields[0]?.id || "");
    setDirty(false);
    setError("");
    setNotice("");
    setOffset(0);
    requestId.current = crypto.randomUUID();
    setParams({ workspace: String(wid), form: String(f.id) });
  }
  async function run(fn: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError(workspaceError(e));
    } finally {
      setBusy(false);
    }
  }
  async function save(publish = false, close = false) {
    await run(async () => {
      let saved = current;
      if (!saved) {
        saved = (await api.post(base, draft)).data;
        setCurrent(saved);
        setForms((prev) => [saved!, ...prev]);
      }
      if (current || publish || close)
        saved = (
          await api.put(`${base}/${saved!.id}`, {
            revision: saved!.revision,
            definition: draft,
            publish,
            close,
          })
        ).data;
      setCurrent(saved);
      setForms((prev) => [saved!, ...prev.filter((f) => f.id !== saved!.id)]);
      setDirty(false);
      setNotice(
        close
          ? "Form closed. Existing responses are retained."
          : publish
            ? "Published. Workspace members can now respond."
            : "Draft saved. Published questions remain unchanged.",
      );
    });
  }
  async function submit(answers: Record<string, Answer>) {
    if (tab === "preview") {
      setNotice("Preview validated. No response or task was created.");
      return;
    }
    await run(async () => {
      const r = await api.post(`${base}/${current!.id}/submit`, {
        request_id: requestId.current,
        version: current!.version,
        answers,
      });
      requestId.current = crypto.randomUUID();
      setNotice(r.data.message || "Your response was already saved.");
      setCurrent((c) =>
        c
          ? { ...c, responses: (c.responses || 0) + (r.data.replayed ? 0 : 1) }
          : c,
      );
    });
  }
  const live = current?.published || current?.definition;
  return (
    <div
      className="forms-studio"
      style={{ "--form-accent": draft.accent } as CSSProperties}
    >
      <header className="forms-heading">
        <div>
          <span className="forms-eyebrow">KARYAFLOW / FORMS</span>
          <h1>Good questions. Great workflows.</h1>
          <p>Build a beautiful intake. Turn every response into action.</p>
        </div>
        <label>
          Workspace
          <select
            aria-label="Forms workspace"
            disabled={busy}
            value={wid}
            onChange={(e) => {
              if (!dirty || window.confirm("Discard unsaved changes?"))
                setWid(Number(e.target.value));
            }}
          >
            {workspaces.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        </label>
      </header>
      {error && (
        <div role="alert" className="forms-alert">
          {error}
          <button onClick={() => window.location.reload()}>Reload</button>
        </div>
      )}
      {notice && (
        <div role="status" className="forms-notice">
          {notice}
        </div>
      )}
      {!wid && !loading ? (
        <p>Create or join a workspace to start building forms.</p>
      ) : (
        <>
          <div className="forms-library">
            <input
              aria-label="Search forms"
              placeholder="Search your forms…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <div>
              {forms
                .filter((f) =>
                  (f.draft || f.definition)?.name
                    .toLowerCase()
                    .includes(search.toLowerCase()),
                )
                .map((f) => (
                  <button
                    disabled={busy}
                    key={f.id}
                    className={current?.id === f.id ? "active" : ""}
                    onClick={() => choose(f)}
                  >
                    {(f.draft || f.definition)?.name}
                    <small>
                      {f.open ? "Live" : f.version ? "Closed" : "Draft"}
                    </small>
                  </button>
                ))}
            </div>
            {admin && (
              <button
                className="form-primary"
                disabled={busy}
                onClick={() => {
                  if (dirty && !window.confirm("Discard unsaved changes?"))
                    return;
                  setCurrent(null);
                  const d = fresh();
                  setDraft(d);
                  setSelected(d.fields[0].id);
                  setDirty(true);
                  setTab("build");
                  setNotice("");
                  setError("");
                }}
              >
                ＋ New form
              </button>
            )}
          </div>
          <div className="forms-topbar">
            <nav aria-label="Form sections">
              {(admin
                ? [
                    ["build", "Build"],
                    ["preview", "Preview"],
                    ["workflow", "Workflow"],
                    ["responses", "Responses"],
                    ["fill", "Open form"],
                  ]
                : [["fill", "Open form"]]
              ).map(([id, label]) => (
                <button
                  disabled={
                    busy || (!current && ["responses", "fill"].includes(id))
                  }
                  className={tab === id ? "active" : ""}
                  key={id}
                  onClick={() => setTab(id)}
                >
                  {label}
                </button>
              ))}
            </nav>
            {admin && (
              <div>
                <span>
                  {dirty
                    ? "Unsaved changes"
                    : current
                      ? `v${current.version} · ${current.open ? "Live" : "Draft / closed"}`
                      : "New form"}
                </span>
                <button disabled={busy || loading} onClick={() => void save()}>
                  Save draft
                </button>
                <button
                  className="form-primary"
                  disabled={busy || loading}
                  onClick={() => void save(true)}
                >
                  Publish →
                </button>
              </div>
            )}
          </div>
          {loading ? (
            <p role="status">Loading forms…</p>
          ) : (
            <fieldset className="forms-workspace" disabled={busy}>
              {tab === "build" && admin && (
                <FormBuilder
                  draft={draft}
                  selected={selected}
                  setSelected={setSelected}
                  edit={edit}
                  error={setError}
                  open={!!current?.open}
                  close={() => void save(false, true)}
                  share={() =>
                    void run(async () => {
                      await navigator.clipboard.writeText(
                        `${location.origin}/pms/forms?workspace=${wid}&form=${current!.id}&view=fill`,
                      );
                      setNotice(
                        "Workspace form link copied. Recipients must sign in.",
                      );
                    })
                  }
                  importForm={async (d) => {
                    if (
                      dirty &&
                      !window.confirm(
                        "Import as a new form and discard unsaved changes?",
                      )
                    )
                      return;
                    await run(async () => {
                      const r = await api.post(base, d);
                      setForms((f) => [r.data, ...f]);
                      setCurrent(r.data);
                      setDraft(r.data.draft);
                      setDirty(false);
                      setSelected(r.data.draft.fields[0].id);
                      setNotice("Imported as a new draft.");
                    });
                  }}
                />
              )}
              {tab === "workflow" && admin && (
                <div className="forms-workflow">
                  <div className="forms-panel">
                    <span className="forms-eyebrow">
                      RESPONSE → TASK → AUTOMATION
                    </span>
                    <h2>Put responses to work</h2>
                    <p>
                      Create a task from each response, then run your project’s
                      existing task-created automation rules in the same
                      transaction.
                    </p>
                    <label className="form-choice">
                      <input
                        type="checkbox"
                        checked={draft.workflow.enabled}
                        onChange={(e) =>
                          edit({
                            ...draft,
                            workflow: {
                              ...draft.workflow,
                              enabled: e.target.checked,
                            },
                          })
                        }
                      />
                      Create a task on submission
                    </label>
                    <div className="form-grid-two">
                      <label>
                        Destination project
                        <select
                          value={draft.workflow.project_id || ""}
                          onChange={(e) =>
                            edit({
                              ...draft,
                              workflow: {
                                ...draft.workflow,
                                project_id: Number(e.target.value) || null,
                              },
                            })
                          }
                        >
                          <option value="">Choose a project</option>
                          {projects.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Task title question
                        <select
                          value={draft.workflow.title_field}
                          onChange={(e) =>
                            edit({
                              ...draft,
                              workflow: {
                                ...draft.workflow,
                                title_field: e.target.value,
                              },
                            })
                          }
                        >
                          <option value="">
                            Choose a required text question
                          </option>
                          {draft.fields
                            .filter(
                              (f) =>
                                f.type === "text" && f.required && !f.condition,
                            )
                            .map((f) => (
                              <option key={f.id} value={f.id}>
                                {f.label}
                              </option>
                            ))}
                        </select>
                      </label>
                      <label>
                        Default priority
                        <select
                          value={draft.workflow.priority}
                          onChange={(e) =>
                            edit({
                              ...draft,
                              workflow: {
                                ...draft.workflow,
                                priority: e.target.value,
                              },
                            })
                          }
                        >
                          {["Low", "Medium", "High", "Urgent"].map((p) => (
                            <option key={p}>{p}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Assign to
                        <select
                          value={draft.workflow.assignee_id || ""}
                          onChange={(e) =>
                            edit({
                              ...draft,
                              workflow: {
                                ...draft.workflow,
                                assignee_id: Number(e.target.value) || null,
                              },
                            })
                          }
                        >
                          <option value="">Unassigned</option>
                          {members.map((m) => (
                            <option key={m.user_id} value={m.user_id}>
                              {m.email}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Due in days
                        <input
                          type="number"
                          min={0}
                          max={365}
                          value={draft.workflow.due_days ?? ""}
                          onChange={(e) =>
                            edit({
                              ...draft,
                              workflow: {
                                ...draft.workflow,
                                due_days:
                                  e.target.value === ""
                                    ? null
                                    : Number(e.target.value),
                              },
                            })
                          }
                        />
                      </label>
                    </div>
                    <p>
                      Answers become the task description. Publish to activate
                      workflow changes. Retried submissions create one response
                      and one task.
                    </p>
                    <Link to={`/pms/automation?workspace=${wid}`}>
                      Manage project automation →
                    </Link>
                  </div>
                  <div className="forms-flow-diagram">
                    {[
                      "① Form submitted",
                      "② Validate visible answers",
                      draft.workflow.enabled
                        ? "③ Create task + apply project rules"
                        : "③ Save response",
                      "④ Response receipt + export",
                    ].map((s) => (
                      <div key={s}>{s}</div>
                    ))}
                  </div>
                </div>
              )}
              {(tab === "preview" || tab === "fill") && (
                <div className="forms-preview">
                  {tab === "preview" && (
                    <div className="forms-preview-tools">
                      <button
                        onClick={() => setMobile(false)}
                        aria-pressed={!mobile}
                      >
                        Desktop
                      </button>
                      <button
                        onClick={() => setMobile(true)}
                        aria-pressed={mobile}
                      >
                        Mobile
                      </button>
                      <button onClick={() => window.print()}>
                        Print / Save PDF
                      </button>
                      <p>Interactive preview · responses are not saved</p>
                    </div>
                  )}
                  {tab === "fill" && (!live || !current?.open) ? (
                    <p>This form is not accepting responses.</p>
                  ) : (
                    <FormResponse
                      key={`${current?.id}-${current?.version}-${tab}`}
                      definition={tab === "preview" ? draft : live!}
                      disabled={busy || role === "Guest"}
                      mobile={mobile && tab === "preview"}
                      submit={submit}
                    />
                  )}
                </div>
              )}
              {tab === "responses" && admin && current && (
                <section className="forms-response-section">
                  <header>
                    <div>
                      <h2>{total} responses</h2>
                      <p>Answers retain their labels and published version.</p>
                    </div>
                    <div>
                      {["csv", "json"].map((format) => (
                        <button
                          key={format}
                          onClick={() =>
                            void run(async () => {
                              const r = await api.get(
                                `${base}/${current.id}/export`,
                                { params: { format }, responseType: "blob" },
                              );
                              download(
                                r.data,
                                `form-${current.id}.${format}`,
                                format === "csv"
                                  ? "text/csv"
                                  : "application/json",
                              );
                            })
                          }
                        >
                          Export {format.toUpperCase()} ↓
                        </button>
                      ))}
                    </div>
                  </header>
                  <div className="forms-response-table">
                    <table>
                      <thead>
                        <tr>
                          <th>Response</th>
                          <th>Submitted (UTC)</th>
                          <th>User / version</th>
                          <th>Answers</th>
                          <th>Task</th>
                        </tr>
                      </thead>
                      <tbody>
                        {replies.map((r) => (
                          <tr key={r.id}>
                            <td>#{r.id}</td>
                            <td>
                              {new Date(r.submitted_at)
                                .toISOString()
                                .replace("T", " ")
                                .slice(0, 19)}
                            </td>
                            <td>
                              #{r.user_id} · v{r.version}
                            </td>
                            <td>
                              <details>
                                <summary>
                                  {Object.keys(r.answers).length} answers
                                </summary>
                                {Object.entries(r.answers).map(([k, v]) => (
                                  <p key={k}>
                                    <strong>{r.labels[k]}</strong>
                                    <br />
                                    {Array.isArray(v)
                                      ? v.join(", ")
                                      : String(v)}
                                  </p>
                                ))}
                              </details>
                            </td>
                            <td>
                              {r.task_id ? (
                                <Link
                                  to={`/pms/workspaces?workspace=${wid}&task=${r.task_id}`}
                                >
                                  Open #{r.task_id} ↗
                                </Link>
                              ) : (
                                "Response only"
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {!replies.length && (
                      <p>
                        No responses yet. Publish your form and share its
                        workspace link.
                      </p>
                    )}
                  </div>
                  <footer>
                    <button
                      disabled={offset === 0}
                      onClick={() => setOffset((v) => Math.max(0, v - 25))}
                    >
                      ← Previous
                    </button>
                    <span>
                      {total ? offset + 1 : 0}–{Math.min(offset + 25, total)} of{" "}
                      {total}
                    </span>
                    <button
                      disabled={offset + 25 >= total}
                      onClick={() => setOffset((v) => v + 25)}
                    >
                      Next →
                    </button>
                  </footer>
                </section>
              )}
            </fieldset>
          )}
        </>
      )}
    </div>
  );
}
