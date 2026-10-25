import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  ClipboardList,
  Plus,
  Eye,
  Send,
  LayoutGrid,
  Palette,
  GitBranch,
  BarChart3,
  Check,
  Copy,
  ExternalLink,
} from "lucide-react";
import { api } from "@/services/api";
import FormBuilder from "./FormBuilder";
import FormResponse from "./FormResponse";
import {
  defaultSettings,
  fresh,
  question,
  download,
  type Definition,
  type Saved,
  type Question,
} from "./formsTypes";
import { message } from "./PublicFormPage";
import "./FormsPage.css";
type Form = Saved & {
  draft: Definition;
  slug: string;
  module_key: string;
  read_only?: boolean;
};
type Catalog = {
  id: number;
  module_name: string;
  api_name: string;
  label: string;
  type: Question["type"];
  required: boolean;
  help: string;
  options: string[];
};
type Reply = {
  task_id?: number;
  id: number;
  version: number;
  status: string;
  submitted_at: string;
  answers: Record<string, unknown>;
  labels: Record<string, string>;
};
export default function FormsPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { formId } = useParams();
  const moduleKey = location.pathname.split("/")[1] || "pms";
  const base = `/${moduleKey}/forms`;
  const page = location.pathname.split("/")[3] || "list";
  const [forms, setForms] = useState<Form[]>([]);
  const [form, setForm] = useState<Form | null>(null);
  const [draft, setDraft] = useState<Definition>(fresh);
  const [selected, setSelected] = useState("");
  const [tab, setTab] = useState("Build");
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [catalog, setCatalog] = useState<Catalog[]>([]);
  const [projects, setProjects] = useState<{ id: number; name: string }[]>([]);
  const [replies, setReplies] = useState<Reply[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [activeReply, setActiveReply] = useState<Reply | null>(null);
  const draftRef = useRef(draft);
  draftRef.current = draft;
  const savingRef = useRef(false);
  const scopeRef = useRef({ moduleKey, formId });
  scopeRef.current = { moduleKey, formId };
  const repliesSequence = useRef(0);
  const settings = { ...defaultSettings, ...draft.settings };
  const edit = (d: Definition) => {
    setDraft(d);
    setDirty(true);
    setNotice("");
  };
  const configure = (value: Partial<typeof settings>) =>
    edit({ ...draft, settings: { ...settings, ...value } });
  async function loadList() {
    try {
      const r = await api.get(`/forms?module_key=${moduleKey}`);
      if (scopeRef.current.moduleKey === moduleKey) {
        setForms(r.data);
        const legacyId = new URLSearchParams(location.search).get("form");
        const found =
          legacyId &&
          r.data.find((f: Form) => String(f.legacy_entry_id) === legacyId);
        if (found && !formId)
          navigate(`${base}/${found.id}/${found.read_only ? "view" : "edit"}`, {
            replace: true,
          });
      }
    } catch (e) {
      setError(message(e));
    }
  }
  useEffect(() => {
    setError("");
    setNotice("");
    setSearch("");
    setForm(null);
    setDirty(false);
    api
      .get(`/forms/options?module_key=${moduleKey}`)
      .then((r) => setProjects(r.data.projects || []))
      .catch((e) => setError(message(e)));
    api
      .get("/forms/catalog")
      .then((r) => setCatalog(r.data))
      .catch((e) => setError(message(e)));
  }, [moduleKey]);
  useEffect(() => {
    let active = true;
    setNotice("");
    setSearch("");
    setError("");
    setDirty(false);
    setForm(null);
    setOffset(0);
    setActiveReply(null);
    if (formId) {
      api
        .get(`/forms/${formId}`)
        .then((r) => {
          if (!active) return;
          if (r.data.module_key !== moduleKey) {
            setError("Form belongs to another module");
            return;
          }
          setForm(r.data);
          setDraft(r.data.draft);
          setSelected(r.data.draft.fields[0]?.id || "");
          setTab(
            location.pathname.endsWith("/responses") ? "Responses" : "Build",
          );
        })
        .catch((e) => {
          if (active) setError(message(e));
        });
    } else if (page === "new") {
      const d = fresh();
      setDraft(d);
      setSelected(d.fields[0].id);
      setDirty(true);
      setTab("Build");
    }
    return () => {
      active = false;
    };
  }, [formId, page, moduleKey]);
  useEffect(() => {
    if (!dirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    const click = (e: MouseEvent) => {
      const a = (e.target as HTMLElement).closest?.("a");
      if (
        a &&
        a.target !== "_blank" &&
        a.origin === window.location.origin &&
        a.pathname !== window.location.pathname &&
        !window.confirm(
          "You have unsaved changes. Leave this form without saving?",
        )
      ) {
        e.preventDefault();
        e.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", handler);
    document.addEventListener("click", click, true);
    return () => {
      window.removeEventListener("beforeunload", handler);
      document.removeEventListener("click", click, true);
    };
  }, [dirty]);
  const changeTab = (value: string) => {
    setTab(value);
    setError("");
  };
  async function loadReplies() {
    if (!form) return;
    const sequence = ++repliesSequence.current;
    try {
      const r = await api.get(
        `/forms/${form.id}/responses?offset=${offset}&limit=50&q=${encodeURIComponent(search)}`,
      );
      if (
        sequence !== repliesSequence.current ||
        String(scopeRef.current.formId) !== String(form.id)
      )
        return;
      setReplies(r.data.items);
      setTotal(r.data.total);
    } catch (e) {
      setError(message(e));
    }
  }
  useEffect(() => {
    if (!formId && page !== "new") void loadList();
  }, [page, formId, moduleKey]);
  useEffect(() => {
    if (tab !== "Responses") return;
    const timer = window.setTimeout(() => void loadReplies(), 250);
    return () => window.clearTimeout(timer);
  }, [form?.id, tab, offset, search]);
  async function save(publish = false, close = false) {
    if (savingRef.current) return null;
    savingRef.current = true;
    const sentDraft = JSON.stringify(draft);
    setBusy(true);
    setError("");
    try {
      const definition = { ...draft, settings };
      const r = form
        ? await api.put(`/forms/${form.id}`, {
            revision: form.revision,
            definition,
            publish,
            close,
          })
        : await api.post("/forms", { module_key: moduleKey, definition });
      setForm(r.data);
      if (JSON.stringify(draftRef.current) === sentDraft) {
        setDraft(r.data.draft);
        setDirty(false);
      }
      setNotice(
        publish
          ? definition.settings.public
            ? "Published · Public link is ready"
            : "Published · Internal response page is ready"
          : close
            ? "Form closed"
            : "All changes saved",
      );
      if (!form) navigate(`${base}/${r.data.id}/edit`, { replace: true });
      void loadList();
      return r.data as Form;
    } catch (e) {
      setError(message(e));
      return null;
    } finally {
      savingRef.current = false;
      setBusy(false);
    }
  }
  const publicUrl = (f: Form) => `${window.location.origin}/f/${f.slug}`;
  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setNotice("Copied to clipboard");
    } catch {
      setNotice("Select and copy the link below.");
    }
  }
  async function publish() {
    if (!form) {
      await save();
      setNotice("Draft created. Review publishing settings, then publish.");
      return;
    }
    await save(true);
  }
  async function duplicateForm(source: Form) {
    setBusy(true);
    setError("");
    try {
      const definition = {
        ...source.draft,
        name: (source.draft.name + " (copy)").slice(0, 120),
        settings: {
          ...defaultSettings,
          ...source.draft.settings,
          public: false,
        },
      };
      const r = await api.post("/forms", { module_key: moduleKey, definition });
      navigate(`${base}/${r.data.id}/edit`);
      void loadList();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  async function exportResponses() {
    if (!form) return;
    try {
      const r = await api.get(`/forms/${form.id}/export`, {
        responseType: "blob",
      });
      download(r.data, `form-${form.id}-responses.csv`, "text/csv");
    } catch (e) {
      setError(message(e));
    }
  }
  async function downloadFile(id: string) {
    if (!form) return;
    try {
      const r = await api.get(`/forms/${form.id}/files/${id}`, {
        responseType: "blob",
      });
      const header = String(r.headers["content-disposition"] || "");
      const filename = decodeURIComponent(
        header.split("UTF-8''")[1] || "attachment",
      );
      download(r.data, filename, "application/octet-stream");
    } catch (e) {
      setError(message(e));
    }
  }
  const editor = page === "new" || !!formId;
  const matches = (f: Form) =>
    `${page === "published" ? f.published?.name : f.draft.name} ${f.published?.name || ""}`
      .toLowerCase()
      .includes(search.toLowerCase());
  return (
    <div
      className="forms-studio suite-forms"
      style={{ "--form-accent": draft.accent } as CSSProperties}
    >
      <nav className="forms-module-nav" aria-label="Forms pages">
        {[
          ["", "All forms"],
          ["/published", "Published"],
          ["/responses", "View responses"],
          ["/custom-fields", "Custom fields"],
        ].map(([path, label]) => (
          <Link
            key={path}
            aria-current={
              !editor && location.pathname === base + path ? "page" : undefined
            }
            to={base + path}
          >
            {label}
          </Link>
        ))}
        <Link className="form-primary" to={`${base}/new`}>
          <Plus size={16} /> Create form
        </Link>
      </nav>
      <header className="forms-heading">
        <div>
          <div className="forms-eyebrow">
            <Link to={base}>Forms</Link>
            {editor && <> › {draft.name}</>}
          </div>
          <div className="forms-title-row">
            <span className="forms-title-icon">
              <ClipboardList />
            </span>
            <h1>
              {editor
                ? draft.name
                : page === "published"
                  ? "Published forms"
                  : page === "responses"
                    ? "Form responses"
                    : page === "custom-fields"
                      ? "Global custom fields"
                      : "Forms"}
            </h1>
            {editor && (
              <span className="forms-status">
                {form?.published
                  ? form.open
                    ? JSON.stringify(draft) !== JSON.stringify(form.published)
                      ? "Published · Draft changes"
                      : "Published"
                    : "Closed"
                  : "Draft"}
              </span>
            )}
          </div>
          <p>
            {editor
              ? draft.description
              : "Create, publish and manage forms across your BusinessSuite modules."}
          </p>
        </div>
        {editor && (
          <div className="forms-actions">
            <span className="forms-save-state">
              <Check size={16} />
              {dirty ? "Unsaved changes" : "All changes saved"}
            </span>
            <button disabled={busy || !dirty} onClick={() => void save()}>
              Save draft
            </button>
            <button onClick={() => changeTab("Preview")}>
              <Eye size={17} /> Preview
            </button>
            <button
              className="form-primary"
              disabled={busy}
              onClick={() => void publish()}
            >
              <Send size={16} /> Publish
            </button>
          </div>
        )}
      </header>
      {error && (
        <p className="forms-error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="forms-notice" role="status">
          {notice}
        </p>
      )}
      {editor ? (
        <>
          {formId && !form ? (
            <p>Loading form…</p>
          ) : (
            <>
              <nav className="forms-editor-tabs" aria-label="Form editor">
                {[
                  ["Build", LayoutGrid],
                  ["Design", Palette],
                  ["Logic", GitBranch],
                  ["Responses", BarChart3],
                  ["Publish", Send],
                ].map(([label, Icon]) => {
                  const I = Icon as typeof LayoutGrid;
                  return (
                    <button
                      key={String(label)}
                      aria-current={tab === label ? "page" : undefined}
                      onClick={() => changeTab(String(label))}
                    >
                      <I size={17} />
                      {String(label)}
                    </button>
                  );
                })}
              </nav>
              {tab === "Build" && (
                <>
                  <FormBuilder
                    draft={draft}
                    selected={selected}
                    setSelected={setSelected}
                    edit={edit}
                    error={setError}
                    importForm={async (d) => {
                      try {
                        const value = (await api.post("/forms/validate", d))
                          .data as Definition;
                        edit(value);
                        setSelected(value.fields[0]?.id || "");
                      } catch (e) {
                        setError(message(e));
                      }
                    }}
                    share={() => changeTab("Publish")}
                    close={() => void save(false, true)}
                    open={!!form?.open}
                  />
                  <section className="forms-panel forms-global-picker">
                    <h2>Add from global custom fields</h2>
                    <p>
                      Reuse existing field definitions and options. Responses
                      remain in this form; this does not modify CRM or other
                      records.
                    </p>
                    <select
                      aria-label="Add global field"
                      defaultValue=""
                      onChange={(e) => {
                        const f = catalog.find(
                          (f) => String(f.id) === e.target.value,
                        );
                        if (f && draft.fields.length < 60) {
                          const q = {
                            ...question(f.type, f.label),
                            help: f.help,
                            required: f.required,
                            options: f.options,
                            global_field_id: f.id,
                          };
                          edit({ ...draft, fields: [...draft.fields, q] });
                          setSelected(q.id);
                        }
                        e.target.value = "";
                      }}
                    >
                      <option value="">Choose a global field…</option>
                      {catalog.map((f) => (
                        <option value={f.id} key={f.id}>
                          {f.module_name} · {f.label}
                        </option>
                      ))}
                    </select>
                    <Link to={`${base}/custom-fields`}>
                      View custom field reference →
                    </Link>
                  </section>
                </>
              )}
              {tab === "Design" && (
                <div className="forms-design-layout">
                  <section className="forms-panel">
                    <h2>Appearance</h2>
                    <label>
                      Accent color
                      <input
                        type="color"
                        value={draft.accent}
                        onChange={(e) =>
                          edit({ ...draft, accent: e.target.value })
                        }
                      />
                    </label>
                    <label>
                      Font
                      <select
                        value={settings.font}
                        onChange={(e) =>
                          configure({
                            font: e.target.value as typeof settings.font,
                          })
                        }
                      >
                        <option value="system">System</option>
                        <option value="serif">Serif</option>
                        <option value="monospace">Monospace</option>
                      </select>
                    </label>
                    <label>
                      Button corners
                      <input
                        type="range"
                        min={0}
                        max={24}
                        value={settings.button_radius}
                        onChange={(e) =>
                          configure({ button_radius: Number(e.target.value) })
                        }
                      />
                    </label>
                    <label>
                      Layout
                      <select
                        value={settings.layout}
                        onChange={(e) =>
                          configure({
                            layout: e.target.value as typeof settings.layout,
                          })
                        }
                      >
                        <option value="stacked">
                          All questions on one page
                        </option>
                        <option value="pages">
                          Multiple pages (add page breaks)
                        </option>
                      </select>
                    </label>
                    <label>
                      Submit button
                      <input
                        maxLength={60}
                        value={draft.submit_label}
                        onChange={(e) =>
                          edit({ ...draft, submit_label: e.target.value })
                        }
                      />
                    </label>
                    <label>
                      Success message
                      <textarea
                        maxLength={500}
                        value={draft.success_message}
                        onChange={(e) =>
                          edit({ ...draft, success_message: e.target.value })
                        }
                      />
                    </label>
                  </section>
                  <FormResponse
                    key={draft.settings?.layout}
                    definition={draft}
                    disabled={false}
                    submit={async () =>
                      setNotice("Preview complete · no response stored")
                    }
                  />
                </div>
              )}
              {tab === "Logic" && (
                <section className="forms-panel">
                  <h2>Conditional visibility</h2>
                  {moduleKey === "pms" && (
                    <div className="forms-workflow">
                      <h3>Task intake</h3>
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
                        Create a task for each accepted response
                      </label>
                      {draft.workflow.enabled && (
                        <>
                          <label>
                            Project
                            <select
                              value={draft.workflow.project_id ?? ""}
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
                              {draft.fields
                                .filter(
                                  (f) =>
                                    f.type === "text" &&
                                    f.required &&
                                    !f.condition,
                                )
                                .map((f) => (
                                  <option value={f.id} key={f.id}>
                                    {f.label}
                                  </option>
                                ))}
                            </select>
                          </label>
                          <p>
                            The title must be a required, unconditional
                            short-text question. Tasks are created using your
                            current project permissions. A response and its task
                            are saved together.
                          </p>
                        </>
                      )}
                    </div>
                  )}
                  <p>
                    Choose a field, then set “Show this question” and its
                    matching rule in the builder. A rule can reference an
                    earlier question. Hidden answers are discarded on the
                    server.
                  </p>
                  {draft.fields.map((f) => (
                    <button
                      className="forms-logic-row"
                      key={f.id}
                      onClick={() => {
                        setSelected(f.id);
                        changeTab("Build");
                      }}
                    >
                      <strong>{f.label}</strong>
                      <span>
                        {f.condition
                          ? `${draft.fields.find((q) => q.id === f.condition?.field)?.label} ${f.condition.operator.replace(/_/g, " ")} ${f.condition.value}`
                          : "Always visible"}
                      </span>
                    </button>
                  ))}
                </section>
              )}
              {tab === "Preview" && (
                <>
                  <p className="forms-notice">
                    Draft preview · submissions are not stored
                  </p>
                  <FormResponse
                    definition={draft}
                    disabled={false}
                    submit={async () =>
                      setNotice("Preview complete · no response stored")
                    }
                  />
                </>
              )}
              {tab === "Publish" && (
                <div className="forms-design-layout">
                  <section className="forms-panel">
                    <h2>Publish & protect</h2>
                    <label className="form-choice">
                      <input
                        type="checkbox"
                        checked={settings.public}
                        onChange={(e) =>
                          configure({ public: e.target.checked })
                        }
                      />
                      Allow anyone with the public link to respond
                    </label>
                    <p>
                      Public access starts only when you publish. Saved drafts
                      do not change the live form.
                    </p>
                    <label>
                      Spam protection
                      <select
                        value={settings.captcha}
                        onChange={(e) =>
                          configure({
                            captcha: e.target.value as typeof settings.captcha,
                          })
                        }
                      >
                        <option value="builtin">
                          Built-in image security code
                        </option>
                        <option value="turnstile">
                          Cloudflare Turnstile (requires server keys)
                        </option>
                      </select>
                    </label>
                    <p>
                      All public forms also have a honeypot, server rate limits,
                      expiring one-use verification and duplicate-submission
                      protection.
                    </p>
                    <label>
                      Maximum responses
                      <input
                        type="number"
                        min={1}
                        max={100000}
                        placeholder="Unlimited"
                        value={settings.max_responses ?? ""}
                        onChange={(e) =>
                          configure({
                            max_responses: e.target.value
                              ? Number(e.target.value)
                              : null,
                          })
                        }
                      />
                    </label>
                    <label>
                      Close on (your local time)
                      <input
                        type="datetime-local"
                        value={
                          settings.closes_at
                            ? new Date(
                                new Date(settings.closes_at).getTime() -
                                  new Date(
                                    settings.closes_at,
                                  ).getTimezoneOffset() *
                                    60000,
                              )
                                .toISOString()
                                .slice(0, 16)
                            : ""
                        }
                        onChange={(e) =>
                          configure({
                            closes_at: e.target.value
                              ? new Date(e.target.value).toISOString()
                              : null,
                          })
                        }
                      />
                    </label>
                    <button
                      className="form-primary"
                      disabled={busy || !form}
                      onClick={() => void save(true)}
                    >
                      Publish form
                    </button>
                    <button
                      disabled={busy || !form?.open}
                      onClick={() => void save(false, true)}
                    >
                      Close submissions
                    </button>
                  </section>
                  <section className="forms-panel">
                    <h2>Public URL</h2>
                    {form?.published && (
                      <p>
                        <Link to={`${base}/${form.id}/view`}>
                          Open internal response page (sign-in required) →
                        </Link>
                      </p>
                    )}
                    {form?.published?.settings?.public ? (
                      <>
                        <label>
                          Share link
                          <input
                            readOnly
                            value={publicUrl(form)}
                            onFocus={(e) => e.target.select()}
                          />
                        </label>
                        <div className="forms-actions">
                          <button onClick={() => void copy(publicUrl(form))}>
                            <Copy size={16} /> Copy link
                          </button>
                          <a
                            href={publicUrl(form)}
                            target="_blank"
                            rel="noreferrer"
                          >
                            <ExternalLink size={16} /> Open public form
                          </a>
                        </div>
                        <h3>Embed on a website</h3>
                        <textarea
                          aria-label="Embed code"
                          readOnly
                          value={`<iframe src="${publicUrl(form)}" title="${form.published.name.replace(/[<>"&]/g, "")}" width="100%" height="800" style="border:0" loading="lazy"></iframe>`}
                          onFocus={(e) => e.target.select()}
                        />
                        <button
                          onClick={() =>
                            void copy(
                              `<iframe src="${publicUrl(form)}" title="Form" width="100%" height="800" style="border:0" loading="lazy"></iframe>`,
                            )
                          }
                        >
                          Copy embed code
                        </button>
                        <p>
                          {form.open
                            ? "Accepting responses (until the deadline or response limit)."
                            : "Closed. Publish again to reopen."}
                        </p>
                        <p>
                          Public links use your current site domain. A local
                          development URL becomes internet-accessible only after
                          deploying the app.
                        </p>
                      </>
                    ) : (
                      <p>
                        Enable public access and publish to get a shareable URL.
                      </p>
                    )}
                  </section>
                </div>
              )}
              {tab === "Responses" && (
                <section className="forms-panel">
                  <div className="forms-actions">
                    <h2>{total} responses</h2>
                    <button disabled={!form} onClick={() => void loadReplies()}>
                      Refresh
                    </button>
                    <button
                      disabled={!form}
                      onClick={() => void exportResponses()}
                    >
                      Export CSV
                    </button>
                  </div>
                  {!form ? (
                    <p>Save this form before collecting responses.</p>
                  ) : (
                    <>
                      <label>
                        Search responses
                        <input
                          value={search}
                          onChange={(e) => {
                            setSearch(e.target.value);
                            setOffset(0);
                          }}
                          maxLength={200}
                          placeholder="Search all answers…"
                        />
                      </label>
                      {replies.map((r) => (
                        <button
                          className="forms-response-row"
                          key={r.id}
                          onClick={() => setActiveReply(r)}
                        >
                          <strong>Response #{r.id}</strong>
                          <span>
                            {new Date(r.submitted_at).toLocaleString()} · v
                            {r.version} · {r.status}
                          </span>
                        </button>
                      ))}
                      {!replies.length && (
                        <p>
                          No responses yet. Publish your form and share its
                          link.
                        </p>
                      )}
                      <div className="forms-actions">
                        <button
                          disabled={offset === 0}
                          onClick={() => setOffset(Math.max(0, offset - 50))}
                        >
                          Previous
                        </button>
                        <span>
                          {total ? offset + 1 : 0}–
                          {Math.min(offset + 50, total)} of {total}
                        </span>
                        <button
                          disabled={offset + 50 >= total}
                          onClick={() => setOffset(offset + 50)}
                        >
                          Next
                        </button>
                      </div>
                      {activeReply && (
                        <article className="forms-reply-detail">
                          <h3>Response #{activeReply.id}</h3>
                          {activeReply.task_id && (
                            <Link to={`/pms/tasks/${activeReply.task_id}`}>
                              Open created task #{activeReply.task_id} →
                            </Link>
                          )}
                          <label>
                            Review status
                            <select
                              value={activeReply.status}
                              onChange={async (e) => {
                                try {
                                  const r = await api.patch(
                                    `/forms/${form.id}/responses/${activeReply.id}`,
                                    { status: e.target.value },
                                  );
                                  setActiveReply(r.data);
                                  void loadReplies();
                                } catch (err) {
                                  setError(message(err));
                                }
                              }}
                            >
                              {["new", "reviewed", "archived"].map((s) => (
                                <option key={s}>{s}</option>
                              ))}
                            </select>
                          </label>
                          <dl>
                            {Object.entries(activeReply.answers).map(
                              ([key, value]) => (
                                <div key={key}>
                                  <dt>{activeReply.labels[key] || key}</dt>
                                  <dd>
                                    {typeof value === "string" &&
                                    value.startsWith("file:") ? (
                                      <button
                                        onClick={() =>
                                          void downloadFile(value.slice(5))
                                        }
                                      >
                                        Download attachment
                                      </button>
                                    ) : Array.isArray(value) ? (
                                      value.join(", ")
                                    ) : (
                                      String(value)
                                    )}
                                  </dd>
                                </div>
                              ),
                            )}
                          </dl>
                        </article>
                      )}
                    </>
                  )}
                </section>
              )}
            </>
          )}
        </>
      ) : page === "custom-fields" ? (
        <section className="forms-panel">
          <h2>Existing global field definitions</h2>
          <p>
            These fields come from the existing customization module. Add them
            using the builder’s global field picker. Labels and options are
            copied into the form version, with a reference to the original
            field.
          </p>
          <Link to="/admin/customization/fields">
            Manage global fields (requires customization permission) →
          </Link>
          <label>
            Search fields
            <input value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
          <div className="forms-card-grid">
            {catalog
              .filter((f) =>
                `${f.label} ${f.module_name} ${f.api_name}`
                  .toLowerCase()
                  .includes(search.toLowerCase()),
              )
              .map((f) => (
                <article className="forms-panel" key={f.id}>
                  <h3>{f.label}</h3>
                  <p>
                    {f.module_name} · {f.type}
                  </p>
                  <code>{f.api_name}</code>
                  <p>{f.help}</p>
                  {f.options.length > 0 && <p>{f.options.join(" · ")}</p>}
                </article>
              ))}
          </div>
          {!catalog.length && (
            <p>
              No compatible global fields yet. Computed and record lookup fields
              are excluded from anonymous input.
            </p>
          )}
        </section>
      ) : (
        <>
          <div className="forms-list-toolbar">
            <label>
              Search forms
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by name…"
              />
            </label>
            <span>
              {forms.length} forms · {moduleKey.toUpperCase()}
            </span>
          </div>
          <div className="forms-card-grid">
            {forms
              .filter(matches)
              .filter((f) => page !== "responses" || !f.read_only)
              .filter((f) => page !== "published" || !!f.published)
              .map((f) => (
                <article className="forms-panel forms-library-card" key={f.id}>
                  <span className="forms-status">
                    {f.published ? (f.open ? "Published" : "Closed") : "Draft"}
                  </span>
                  <h2>
                    <Link
                      to={`${base}/${f.id}/${f.read_only ? "view" : "edit"}`}
                    >
                      {page === "published" ? f.published?.name : f.draft.name}
                    </Link>
                  </h2>
                  <p>
                    {page === "published"
                      ? f.published?.description
                      : f.draft.description}
                  </p>
                  <p>
                    {f.read_only
                      ? "Internal response page"
                      : `${f.responses} responses`}{" "}
                    · {f.draft.fields.length} fields · v{f.version}
                  </p>
                  <div className="forms-actions">
                    {f.read_only ? (
                      <Link to={`${base}/${f.id}/view`}>Respond to form →</Link>
                    ) : (
                      <>
                        {" "}
                        <Link to={`${base}/${f.id}/edit`}>Edit form</Link>
                        <button
                          disabled={busy}
                          onClick={() => void duplicateForm(f)}
                        >
                          Duplicate
                        </button>
                        <Link to={`${base}/${f.id}/responses`}>
                          View responses
                        </Link>
                      </>
                    )}
                    {f.published?.settings?.public && (
                      <button onClick={() => void copy(publicUrl(f))}>
                        Copy public URL
                      </button>
                    )}
                  </div>
                  {f.published &&
                    !f.published.settings?.public &&
                    !f.read_only && (
                      <p>
                        Internal form · enable public access in Publish to
                        create a public URL.
                      </p>
                    )}
                </article>
              ))}
          </div>
          {!forms
            .filter(matches)
            .filter((f) => page !== "responses" || !f.read_only)
            .filter((f) => page !== "published" || !!f.published).length && (
            <section className="forms-panel forms-empty">
              <ClipboardList size={40} />
              <h2>
                {page === "published"
                  ? "No published forms yet"
                  : "Create your first form"}
              </h2>
              <p>
                Build a form, preview it and publish a public link to collect
                responses.
              </p>
              <Link to={`${base}/new`}>Create form →</Link>
            </section>
          )}
        </>
      )}
    </div>
  );
}
