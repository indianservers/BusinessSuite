import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { LockKeyhole, Building2, X } from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { workspaceError } from "./workspaceTypes";
import "./DashboardsPage.css";
type Dashboard = {
  id: number;
  workspace_id: number;
  owner_id: number;
  name: string;
  description: string;
  visibility: "private" | "organization";
  revision: number;
  deleted_at: string | null;
  updated_at: string;
};
const base = "/project-management";
export default function DashboardsPage() {
  const { user } = useAuthStore();
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [filter, setFilter] = useState("All");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("updated");
  const [editor, setEditor] = useState<Dashboard | "new" | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [visibility, setVisibility] = useState<"private" | "organization">(
    "private",
  );
  const [workspace, setWorkspace] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [deleting, setDeleting] = useState<Dashboard | null>(null);
  const key = ["pms-dashboards", user?.id];
  const list = useQuery({
    queryKey: key,
    queryFn: async () =>
      (await api.get<Dashboard[]>(`${base}/dashboards`)).data,
  });
  const workspaces = useQuery({
    queryKey: ["dashboard-workspaces", user?.id],
    queryFn: async () =>
      (
        await api.get<{ id: number; name: string; role: string }[]>(
          `${base}/workspaces`,
        )
      ).data,
  });
  const rows = list.data || [];
  const active = rows.find(
    (d) => String(d.id) === params.get("dashboard") && !d.deleted_at,
  );
  const metrics = useQuery({
    queryKey: ["dashboard-metrics", user?.id, active?.workspace_id],
    enabled: !!active,
    queryFn: async () =>
      (
        await api.get<{
          projects: { id: number; workspace_id: number }[];
          tasks: {
            id: number;
            project_id: number;
            title: string;
            status: string;
            due_date: string | null;
          }[];
        }>(`${base}/planner`)
      ).data,
  });
  const ids = new Set(
    (metrics.data?.projects || [])
      .filter((p) => p.workspace_id === active?.workspace_id)
      .map((p) => p.id),
  );
  const tasks = (metrics.data?.tasks || []).filter((t) =>
    ids.has(t.project_id),
  );
  const done = (s: string) =>
    ["Done", "Completed", "Closed", "Resolved"].includes(s);
  const now = new Date();
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  const shown = rows
    .filter(
      (d) =>
        (filter === "Trash" ? !!d.deleted_at : !d.deleted_at) &&
        (filter !== "Mine" || d.owner_id === user?.id) &&
        (filter !== "Organization" || d.visibility === "organization") &&
        (filter !== "Private" || d.visibility === "private") &&
        `${d.name} ${d.description}`
          .toLowerCase()
          .includes(search.toLowerCase()),
    )
    .sort((a, b) =>
      sort === "name"
        ? a.name.localeCompare(b.name)
        : b.updated_at.localeCompare(a.updated_at),
    );
  function edit(d?: Dashboard, duplicate = false) {
    setError("");
    setEditor(d && !duplicate ? d : "new");
    setName(d ? `${d.name}${duplicate ? " (copy)" : ""}` : "");
    setDescription(d?.description || "");
    setVisibility(duplicate ? "private" : d?.visibility || "private");
    setWorkspace(
      String(
        d?.workspace_id ||
          workspaces.data?.find((w) => w.role !== "Guest")?.id ||
          "",
      ),
    );
  }
  async function mutate(action: () => Promise<unknown>) {
    if (pending) return;
    setPending(true);
    setError("");
    try {
      await action();
      await qc.invalidateQueries({ queryKey: key });
      setEditor(null);
      setDeleting(null);
    } catch (e) {
      setError(workspaceError(e));
    } finally {
      setPending(false);
    }
  }
  return (
    <div className="dash-library">
      <header>
        <div>
          <h1>Dashboards</h1>
          <p>
            Private insights or shared with your organization. Never public on
            the internet.
          </p>
        </div>
        <button
          disabled={
            pending || !workspaces.data?.some((w) => w.role !== "Guest")
          }
          onClick={() => edit()}
        >
          + New dashboard
        </button>
      </header>
      {error && (
        <p role="alert" className="dash-error">
          {error}
        </p>
      )}
      {list.isError && (
        <p role="alert">
          {workspaceError(list.error)}{" "}
          <button onClick={() => list.refetch()}>Retry</button>
        </p>
      )}
      {workspaces.isError && (
        <p role="alert">
          Could not load workspaces.{" "}
          <button onClick={() => workspaces.refetch()}>Retry</button>
        </p>
      )}
      <nav aria-label="Dashboard views">
        {["All", "Mine", "Organization", "Private", "Trash"].map((f) => (
          <button
            key={f}
            aria-pressed={filter === f}
            onClick={() => {
              setFilter(f);
              setParams({});
            }}
          >
            {f}
          </button>
        ))}
      </nav>
      {active ? (
        <section>
          <button onClick={() => setParams({})}>← All dashboards</button>
          <h2>{active.name}</h2>
          <p>{active.description}</p>
          <p>
            {active.visibility === "private"
              ? "Private — only you"
              : "Organization — signed-in organization members"}
          </p>
          <small>
            Live metrics show only projects you personally have permission to
            view in this dashboard’s workspace.
          </small>
          {metrics.isPending ? (
            <p role="status">Loading metrics…</p>
          ) : metrics.isError ? (
            <p role="alert">
              Could not load metrics.{" "}
              <button onClick={() => metrics.refetch()}>Retry</button>
            </p>
          ) : (
            <>
              <div className="dash-metrics">
                {[
                  ["Projects", ids.size],
                  ["Tasks", tasks.length],
                  ["Completed", tasks.filter((t) => done(t.status)).length],
                  [
                    "Overdue",
                    tasks.filter(
                      (t) =>
                        t.due_date && t.due_date < today && !done(t.status),
                    ).length,
                  ],
                ].map(([label, count]) => (
                  <article key={label}>
                    <strong>{count}</strong>
                    <span>{label}</span>
                  </article>
                ))}
              </div>
              <h3>Open tasks</h3>
              {!tasks.filter((t) => !done(t.status)).length && (
                <p>No open tasks visible to your account.</p>
              )}
              {tasks
                .filter((t) => !done(t.status))
                .map((t) => (
                  <p key={t.id}>
                    {t.title} · {t.status}
                    {t.due_date ? ` · ${t.due_date}` : ""}
                  </p>
                ))}
            </>
          )}
        </section>
      ) : params.has("dashboard") && !list.isPending ? (
        <p role="alert">
          This dashboard is unavailable, private, or in Trash.{" "}
          <button onClick={() => setParams({})}>Back to dashboards</button>
        </p>
      ) : (
        <>
          <div className="dash-controls">
            <input
              aria-label="Search dashboards"
              placeholder="Search dashboards…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <select
              aria-label="Sort dashboards"
              value={sort}
              onChange={(e) => setSort(e.target.value)}
            >
              <option value="updated">Recently updated</option>
              <option value="name">Name</option>
            </select>
          </div>
          {list.isPending ? (
            <p role="status">Loading dashboards…</p>
          ) : !shown.length ? (
            <p>No dashboards match this view.</p>
          ) : (
            <div className="dash-table">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Visibility</th>
                    <th>Owner</th>
                    <th>Updated</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((d) => (
                    <tr key={d.id}>
                      <td>
                        {d.deleted_at ? (
                          d.name
                        ) : (
                          <button
                            onClick={() =>
                              setParams({ dashboard: String(d.id) })
                            }
                          >
                            {d.name}
                          </button>
                        )}
                        <small>{d.description}</small>
                      </td>
                      <td>
                        {d.visibility === "private" ? (
                          <LockKeyhole size={14} />
                        ) : (
                          <Building2 size={14} />
                        )}{" "}
                        {d.visibility === "private"
                          ? "Private"
                          : "Organization"}
                      </td>
                      <td>
                        {d.owner_id === user?.id
                          ? "You"
                          : "Organization member"}
                      </td>
                      <td>{new Date(d.updated_at).toLocaleString()}</td>
                      <td>
                        {d.owner_id === user?.id &&
                          (d.deleted_at ? (
                            <button
                              disabled={pending}
                              onClick={() =>
                                void mutate(() =>
                                  api.post(
                                    `${base}/dashboards/${d.id}/restore`,
                                    { revision: d.revision },
                                  ),
                                )
                              }
                            >
                              Restore
                            </button>
                          ) : (
                            <>
                              <button onClick={() => edit(d)}>
                                Edit & sharing
                              </button>
                              <button onClick={() => edit(d, true)}>
                                Duplicate
                              </button>
                              <button
                                onClick={() => {
                                  setError("");
                                  setDeleting(d);
                                }}
                              >
                                Delete
                              </button>
                            </>
                          ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
      <p>
        <Link to="/pms/portfolio">Open portfolio reports ↗</Link>
      </p>
      <Dialog.Root
        open={!!editor}
        onOpenChange={(v) => {
          if (!v && !pending) setEditor(null);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="dash-overlay" />
          <Dialog.Content className="dash-dialog">
            <Dialog.Title>
              {editor === "new" ? "New dashboard" : "Edit dashboard"}
            </Dialog.Title>
            <Dialog.Description>
              Sharing applies to the dashboard. Project permissions still apply
              to its metrics.
            </Dialog.Description>
            <button
              className="dash-close"
              aria-label="Close dashboard editor"
              disabled={pending}
              onClick={() => setEditor(null)}
            >
              <X size={18} />
            </button>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void mutate(() =>
                  editor && editor !== "new"
                    ? api.put(`${base}/dashboards/${editor.id}`, {
                        name: name.trim(),
                        description,
                        visibility,
                        revision: editor.revision,
                      })
                    : api.post(`${base}/dashboards`, {
                        name: name.trim(),
                        description,
                        visibility,
                        workspace_id: Number(workspace),
                      }),
                );
              }}
            >
              <label>
                Name
                <input
                  required
                  maxLength={120}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
              <label>
                Description
                <textarea
                  maxLength={2000}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </label>
              {editor === "new" && (
                <label>
                  Workspace
                  <select
                    required
                    value={workspace}
                    onChange={(e) => setWorkspace(e.target.value)}
                  >
                    <option value="">Choose workspace</option>
                    {workspaces.data
                      ?.filter((w) => w.role !== "Guest")
                      .map((w) => (
                        <option key={w.id} value={w.id}>
                          {w.name}
                        </option>
                      ))}
                  </select>
                </label>
              )}
              <label>
                Visibility
                <select
                  value={visibility}
                  onChange={(e) =>
                    setVisibility(e.target.value as typeof visibility)
                  }
                >
                  <option value="private">Private — only me</option>
                  <option value="organization">
                    Organization — everyone in my organization
                  </option>
                </select>
              </label>
              <p>No anonymous links or external sharing.</p>
              {error && <p role="alert">{error}</p>}
              <footer>
                <button
                  type="button"
                  disabled={pending}
                  onClick={() => setEditor(null)}
                >
                  Cancel
                </button>
                <button disabled={pending || !name.trim() || !workspace}>
                  {pending ? "Saving…" : "Save dashboard"}
                </button>
              </footer>
            </form>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <Dialog.Root
        open={!!deleting}
        onOpenChange={(v) => {
          if (!v && !pending) setDeleting(null);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="dash-overlay" />
          <Dialog.Content className="dash-dialog">
            <Dialog.Title>Move dashboard to Trash?</Dialog.Title>
            <Dialog.Description>
              “{deleting?.name}” will disappear for other viewers. You can
              restore it from Trash. Tasks and projects stay unchanged.
            </Dialog.Description>
            {error && <p role="alert">{error}</p>}
            <footer>
              <button disabled={pending} onClick={() => setDeleting(null)}>
                Cancel
              </button>
              <button
                disabled={pending}
                onClick={() =>
                  deleting &&
                  void mutate(() =>
                    api.post(`${base}/dashboards/${deleting.id}/trash`, {
                      revision: deleting.revision,
                    }),
                  )
                }
              >
                Move to Trash
              </button>
            </footer>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
