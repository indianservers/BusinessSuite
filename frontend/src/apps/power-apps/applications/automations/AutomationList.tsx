import { GraphProposalPreview } from "./builder/IntelligencePanels";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Archive,
  ArrowRight,
  Check,
  Copy,
  FileClock,
  MoreHorizontal,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Trash2,
  Workflow,
  X,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { powerApi, errorMessage } from "../../api";
import type { Resource, Environment } from "../../registry";
import type { AutomationTemplate } from "./builder/types";
import { studioApi, studioPath } from "./studioApi";
import "./automations.css";
const tabs = [
  ["all", "All Automations"],
  ["mine", "My Automations"],
  ["shared", "Shared Automations"],
  ["drafts", "Drafts"],
  ["published", "Published"],
  ["disabled", "Disabled"],
  ["templates", "Templates"],
];
export function AutomationList({
  environment,
  can,
}: {
  environment: Environment;
  can: (permission: string) => boolean;
}) {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const [view, setView] = useState(() =>
      new URLSearchParams(window.location.search).get("view") === "templates"
        ? "templates"
        : "all",
    ),
    [search, setSearch] = useState(""),
    [query, setQuery] = useState(""),
    [offset, setOffset] = useState(0);
  const [rows, setRows] = useState<Resource[]>([]),
    [total, setTotal] = useState(0),
    [templates, setTemplates] = useState<AutomationTemplate[]>([]);
  const [busy, setBusy] = useState(true),
    [mutating, setMutating] = useState(false),
    [error, setError] = useState(""),
    [refresh, setRefresh] = useState(0);
  const [renaming, setRenaming] = useState<number | null>(null),
    [newName, setNewName] = useState("");
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery(search);
      setOffset(0);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    let live = true;
    setBusy(true);
    setError("");
    (view === "templates"
      ? studioApi.templates().then((items) => {
          if (live) setTemplates(items);
        })
      : studioApi.list(environment, view, query, offset).then((data) => {
          if (live) {
            setRows(data.items || []);
            setTotal(data.total || 0);
          }
        })
    )
      .catch((e) => {
        if (live) setError(errorMessage(e));
      })
      .finally(() => {
        if (live) setBusy(false);
      });
    return () => {
      live = false;
    };
  }, [environment, view, query, offset, refresh]);
  const open = (row: Resource, suffix = "edit") =>
    navigate(
      studioPath(`/power-apps/automations/${row.id}/${suffix}`, environment),
    );
  const action = async (callback: () => Promise<unknown>) => {
    setMutating(true);
    setError("");
    try {
      await callback();
      setRefresh((v) => v + 1);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setMutating(false);
    }
  };
  return (
    <section className="al-workspace">
      <div className="al-intro">
        <span className="al-intro-icon">
          <Workflow size={26} />
        </span>
        <div>
          <h2>Ideas become workflows.</h2>
          <p>Bring your process to life, one connection at a time.</p>
        </div>
        <button onClick={() => navigate(studioPath("/power-apps/automations/executions", environment))}><FileClock size={16} /> Executions</button>
        {can("create") && (
          <button
            className="pa-primary"
            onClick={() =>
              navigate(studioPath("/power-apps/automations/new", environment))
            }
          >
            <Plus size={16} />
            New automation
          </button>
        )}
      </div>
      <div className="al-tabs" role="tablist" aria-label="Automation views">
        {tabs.map(([key, label]) => (
          <button
            key={key}
            role="tab"
            aria-selected={view === key}
            onClick={() => {
              setView(key);
              setOffset(0);
            }}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="al-controls">
        <label>
          <Search size={16} />
          <input
            aria-label="Search automations"
            placeholder={
              view === "templates"
                ? "Search templates..."
                : "Search your automations..."
            }
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <span>
          {view === "templates"
            ? "Versioned starter workflows"
            : `${total} ${total === 1 ? "automation" : "automations"} in ${environment}`}
        </span>
      </div>
      {error && (
        <div className="pa-error" role="alert">
          {error}
          <button onClick={() => setRefresh((v) => v + 1)}>Retry</button>
        </div>
      )}
      {busy ? (
        <p className="al-loading" role="status">
          Loading automations...
        </p>
      ) : view === "templates" ? (
        <div className="al-templates">
          {templates
            .filter((t) =>
              `${t.name} ${t.description}`
                .toLowerCase()
                .includes(query.toLowerCase()),
            )
            .map((template) => (
              <article key={template.id}>
                <span>
                  <Sparkles size={22} />
                </span>
                <small>Template v{template.version}</small>
                <h3>{template.name}</h3>
                <p>{template.description}</p>
                <div className="al-template-path">
                  {template.definition.nodes.length} nodes{" "}
                  <ArrowRight size={12} />
                  {template.definition.edges.length} connections
                </div>
                <em>Requires configuration / Not Executable Yet</em>
                <p className="al-template-adapters">
                  Needs: {template.required_adapters.join(", ")}
                </p>
                <details>
                  <summary>Preview template and prerequisites</summary>
                  <GraphProposalPreview graph={template.definition} />
                  <button
                    disabled={!can("create") || mutating}
                    onClick={() =>
                      void action(async () =>
                        open(
                          await studioApi.useTemplate(environment, template.id),
                        ),
                      )
                    }
                  >
                    Use template
                    <ArrowRight size={14} />
                  </button>
                </details>
              </article>
            ))}
        </div>
      ) : rows.length ? (
        <div className="al-table-wrap">
          <table className="al-table">
            <thead>
              <tr>
                <th>Automation</th>
                <th>Status</th>
                <th>Owner</th>
                <th>Last edited</th>
                <th>
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <div className="al-row-name">
                      <span>
                        <Workflow size={20} />
                      </span>
                      <div>
                        {renaming === row.id ? (
                          <form
                            onSubmit={(event) => {
                              event.preventDefault();
                              void action(async () => {
                                await studioApi.rename(
                                  environment,
                                  row,
                                  newName,
                                );
                                setRenaming(null);
                              });
                            }}
                          >
                            <input
                              autoFocus
                              aria-label="Rename automation"
                              maxLength={180}
                              required
                              value={newName}
                              onChange={(e) => setNewName(e.target.value)}
                            />
                            <button
                              aria-label="Save automation name"
                              disabled={mutating}
                            >
                              <Check size={14} />
                            </button>
                            <button
                              type="button"
                              aria-label="Cancel rename"
                              onClick={() => setRenaming(null)}
                            >
                              <X size={14} />
                            </button>
                          </form>
                        ) : (
                          <button
                            className="al-open-row"
                            onClick={() => open(row)}
                          >
                            {row.name}
                          </button>
                        )}
                        <p>
                          {Array.isArray(row.definition.nodes)
                            ? row.definition.nodes.length
                            : 0}{" "}
                          nodes / v{row.version}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td>
                    <span
                      className={`al-status ${row.archived_at ? "archived" : ""}`}
                    >
                      {row.archived_at ? "Archived draft" : "Draft"}
                    </span>
                  </td>
                  <td className="al-owner">
                    {row.owner_user_id === user?.id
                      ? "You"
                      : row.owner_user_id
                        ? `Member #${row.owner_user_id}`
                        : "Authorized owner"}
                  </td>
                  <td>
                    <time>{new Date(row.updated_at).toLocaleDateString()}</time>
                    <small>
                      {new Date(row.updated_at).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </small>
                  </td>
                  <td>
                    <details className="al-actions">
                      <summary aria-label={`Actions for ${row.name}`}>
                        <MoreHorizontal size={19} />
                      </summary>
                      <div>
                        <button onClick={() => open(row)}>Open workflow</button>
                        <button
                          disabled={!can("edit") || Boolean(row.archived_at)}
                          onClick={() => {
                            setRenaming(row.id);
                            setNewName(row.name);
                          }}
                        >
                          Rename
                        </button>
                        <button
                          disabled={!can("create") || mutating}
                          onClick={() =>
                            void action(async () =>
                              open(
                                await studioApi.duplicate(environment, row.id),
                              ),
                            )
                          }
                        >
                          <Copy size={13} />
                          Duplicate
                        </button>
                        <button onClick={() => open(row, "versions")}>
                          <FileClock size={13} />
                          Version history
                        </button>
                        <button
                          disabled={!can("edit") || mutating}
                          onClick={() =>
                            void action(() =>
                              studioApi.lifecycle(
                                environment,
                                row,
                                !row.archived_at,
                              ),
                            )
                          }
                        >
                          <Archive size={13} />
                          {row.archived_at ? "Unarchive" : "Archive draft"}
                        </button>
                        <button
                          className="pa-delete"
                          disabled={!can("delete") || mutating}
                          onClick={() => {
                            if (
                              window.confirm(
                                `Delete draft "${row.name}" and its snapshots?`,
                              )
                            )
                              void action(() =>
                                powerApi.remove(environment, row),
                              );
                          }}
                        >
                          <Trash2 size={13} />
                          Delete
                        </button>
                      </div>
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="al-empty">
          <span>
            <Workflow size={34} strokeWidth={1.4} />
          </span>
          <h3>
            {view === "published"
              ? "No published automations"
              : view === "disabled"
                ? "No archived drafts"
                : query
                  ? "No automations match your search"
                  : "Make your first connection"}
          </h3>
          <p>
            {view === "published"
              ? "Publish supported workflows from their runtime page."
              : view === "disabled"
                ? "Archived drafts appear here. They cannot be edited or executed."
                : "Start from a blank canvas or make a template your own."}
          </p>
          {can("create") && !["published", "disabled"].includes(view) && (
            <div>
              <button
                className="pa-primary"
                onClick={() =>
                  navigate(
                    studioPath("/power-apps/automations/new", environment),
                  )
                }
              >
                <Plus size={14} />
                Create automation
              </button>
              <button onClick={() => setView("templates")}>
                Explore templates
                <ArrowRight size={14} />
              </button>
            </div>
          )}
        </div>
      )}
      {view !== "templates" && total > 50 && (
        <div className="pa-pagination">
          <button
            disabled={!offset}
            onClick={() => setOffset((v) => Math.max(0, v - 50))}
          >
            Previous
          </button>
          <span>
            {offset + 1}-{Math.min(offset + 50, total)} of {total}
          </span>
          <button
            disabled={offset + 50 >= total}
            onClick={() => setOffset((v) => v + 50)}
          >
            Next
          </button>
        </div>
      )}
      <div className="al-safety">
        <ShieldCheck size={18} />
        <p>
          <strong>Design, publish, monitor.</strong> Drafts, previews and
          templates are isolated to this Power Apps environment. No live emails,
          requests, tasks or approvals are triggered.
        </p>
      </div>
    </section>
  );
}
