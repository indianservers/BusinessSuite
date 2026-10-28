import { useRefreshableEffect } from "@/lib/page-refresh";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { DatabaseBackup, Download, ShieldCheck } from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { workspaceError } from "./workspaceTypes";

type Workspace = { id: number; name: string; role: string };
type Policy = {
  enabled: boolean;
  interval_hours: number;
  retain_automatic: number;
  last_success_at?: string | null;
};
type Point = {
  id: number;
  name: string;
  automatic: boolean;
  created_at: string;
  tasks: number;
  rows: number;
  checksum: string;
};
type History = {
  id: number;
  title: string;
  task_id: number;
  state: string;
  created_at: string;
  fields: string[];
};
const defaults: Policy = {
  enabled: false,
  interval_hours: 24,
  retain_automatic: 14,
};
const when = (value?: string | null) =>
  value
    ? new Date(
        /Z|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`,
      ).toLocaleString()
    : "No successful automatic backup yet";

export default function RecoveryPage() {
  const [params] = useSearchParams();
  const user = useAuthStore((state) => state.user);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selected, setSelected] = useState(
    Number(params.get("workspace")) || 0,
  );
  const [points, setPoints] = useState<Point[]>([]);
  const selectedRef = useRef(selected);
  selectedRef.current = selected;
  const [history, setHistory] = useState<History[]>([]);
  const [policy, setPolicy] = useState<Policy>(defaults);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [full, setFull] = useState<any>(null);
  const [fullPolicy, setFullPolicy] = useState<Policy>(defaults);
  const [restore, setRestore] = useState<{ point: Point; preview: any } | null>(
    null,
  );
  const [confirmation, setConfirmation] = useState("");
  const workspace = workspaces.find((row) => row.id === selected);
  const manages = workspace?.role === "Owner" || workspace?.role === "Admin";
  const base = `/project-management/workspaces/${selected}/recovery`;
  const load = async () => {
    if (!workspace) return;
    const id = selected;
    const [historyResult, pointResult] = await Promise.all([
      workspace.role !== "Guest"
        ? api.get(`${base}/history`)
        : Promise.resolve(null),
      manages ? api.get(base) : Promise.resolve(null),
    ]);
    if (selectedRef.current !== id) return;
    setHistory(historyResult?.data || []);
    setPoints(pointResult?.data.points || []);
    if (pointResult) {
      setPolicy(pointResult.data.policy);
    }
  };
  const loadFull = async () => {
    const { data } = await api.get("/project-management/data-backups");
    setFull(data);
    setFullPolicy(data.policy);
  };
  useEffect(() => {
    let active = true;
    api
      .get<Workspace[]>("/project-management/workspaces")
      .then(({ data }) => {
        if (!active) return;
        setWorkspaces(data);
        setSelected((current) =>
          data.some((row) => row.id === current) ? current : data[0]?.id || 0,
        );
      })
      .catch(() => setError("Unable to load workspaces."));
    return () => {
      active = false;
    };
  }, []);
  useRefreshableEffect(() => {
    setRestore(null);
    setPoints([]);
    setHistory([]);
    setError("");
    void load().catch((e: any) => setError(workspaceError(e)));
  }, [selected, workspace?.role]);
  useRefreshableEffect(() => {
    if (user?.is_superuser)
      void loadFull().catch((e: any) => setError(workspaceError(e)));
  }, [user?.is_superuser]);
  const action = async (work: () => Promise<void>, message: string) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await work();
      setNotice(message);
    } catch (e: any) {
      setError(workspaceError(e));
    } finally {
      setBusy(false);
    }
  };
  const download = async (url: string, filename: string) => {
    const response = await api.get(url, { responseType: "blob", timeout: 0 });
    const href = URL.createObjectURL(response.data);
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = filename;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(href), 1000);
  };
  const policyForm = (value: Policy, update: (p: Policy) => void) => (
    <div className="flex flex-wrap items-end gap-4">
      <label className="flex items-center gap-2 py-2">
        <input
          type="checkbox"
          checked={value.enabled}
          onChange={(e) => update({ ...value, enabled: e.target.checked })}
        />
        Automatic backups
      </label>
      <label className="text-sm">
        Every (hours)
        <Input
          type="number"
          min={1}
          max={720}
          value={value.interval_hours}
          onChange={(e) =>
            update({ ...value, interval_hours: Number(e.target.value) })
          }
          className="w-28"
        />
      </label>
      <label className="text-sm">
        Keep automatic copies
        <Input
          type="number"
          min={2}
          max={90}
          value={value.retain_automatic}
          onChange={(e) =>
            update({ ...value, retain_automatic: Number(e.target.value) })
          }
          className="w-28"
        />
      </label>
    </div>
  );
  return (
    <main className="mx-auto max-w-5xl space-y-6 p-4 sm:p-6">
      <header>
        <Link
          to={`/pms?workspace=${selected}`}
          className="text-sm text-primary"
        >
          ← Back to workspace
        </Link>
        <h1 className="mt-3 flex items-center gap-3 text-2xl font-semibold">
          <DatabaseBackup />
          Backup & recovery
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Undo task changes, create named savepoints, and protect your business
          data.
        </p>
      </header>
      {error && (
        <div
          role="alert"
          className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-800"
        >
          {error}
        </div>
      )}
      {notice && (
        <div role="status" className="rounded-lg border p-4 text-sm">
          {notice}
        </div>
      )}
      <label className="block text-sm font-medium">
        Workspace
        <select
          aria-label="Recovery workspace"
          className="mt-2 block w-full rounded-md border bg-background p-3"
          value={selected}
          onChange={(e) => {
            setSelected(Number(e.target.value));
            setPoints([]);
            setHistory([]);
          }}
          disabled={busy}
        >
          {workspaces.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name} · {row.role}
            </option>
          ))}
        </select>
      </label>
      {workspace && workspace.role !== "Guest" && (
        <section className="space-y-3 rounded-xl border bg-card p-5">
          <h2 className="text-lg font-semibold">Your task history</h2>
          <p className="text-sm text-muted-foreground">
            Undo/redo task creation, edits and soft-deletion from supported task
            operations. Newer changes by teammates are protected. Financial
            actions, messages, integrations and structural changes use their own
            recovery controls.
          </p>
          <div className="flex gap-2">
            {(["undo", "redo"] as const).map((direction) => (
              <Button
                key={direction}
                variant="outline"
                disabled={
                  busy ||
                  !history.some(
                    (row) =>
                      row.state ===
                      (direction === "undo" ? "applied" : "undone"),
                  )
                }
                onClick={() =>
                  void action(async () => {
                    await api.post(`${base}/actions/${direction}`);
                    await load();
                  }, `Task ${direction} completed.`)
                }
              >
                {direction === "undo" ? "Undo" : "Redo"}
              </Button>
            ))}
          </div>
          <ul className="max-h-64 space-y-2 overflow-auto">
            {history.slice(0, 20).map((row) => (
              <li key={row.id} className="rounded-md border p-3 text-sm">
                <strong>{row.title}</strong>
                <span className="ml-2 text-muted-foreground">
                  {row.state} · {when(row.created_at)}
                </span>
                <p className="mt-1 break-words text-xs text-muted-foreground">
                  {row.fields.join(", ")}
                </p>
              </li>
            ))}
          </ul>
          {!history.length && (
            <p className="text-sm text-muted-foreground">
              Task changes made after this feature is installed will appear
              here.
            </p>
          )}
        </section>
      )}
      {manages && (
        <section className="space-y-4 rounded-xl border bg-card p-5">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <ShieldCheck size={20} />
            Workspace savepoints
          </h2>
          <p className="text-sm text-muted-foreground">
            Downloads contain workspace-owned PMS records. Private chats,
            personal settings, API credentials and invitation tokens are
            excluded. Uploaded file contents are included in full-system
            archives.
          </p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input
              placeholder="Savepoint name, e.g. Before sprint planning"
              aria-label="Savepoint name"
              value={name}
              maxLength={160}
              onChange={(e) => setName(e.target.value)}
            />
            <Button
              disabled={busy || !name.trim()}
              onClick={() =>
                void action(async () => {
                  await api.post(`${base}/savepoints`, { name });
                  setName("");
                  await load();
                }, "Savepoint created.")
              }
            >
              Create savepoint
            </Button>
          </div>
          {policyForm(policy, setPolicy)}
          <Button
            variant="outline"
            disabled={busy}
            onClick={() =>
              void action(async () => {
                await api.put(`${base}/policy`, policy);
              }, "Automatic workspace policy saved. The backup worker must be running.")
            }
          >
            Save workspace schedule
          </Button>
          <p className="text-xs text-muted-foreground">
            {when(policy.last_success_at)}. Automatic policies run through the
            durable backup worker or the scheduled data_recovery.py --due
            command; browser visits are not required. Manual and pre-restore
            savepoints are retained.
          </p>
          <ul className="space-y-3">
            {points.map((point) => (
              <li
                key={point.id}
                className="flex flex-col justify-between gap-3 rounded-lg border p-4 sm:flex-row"
              >
                <div className="min-w-0">
                  <strong className="break-words">{point.name}</strong>
                  <p className="text-xs text-muted-foreground">
                    {point.automatic ? "Automatic" : "Manual"} ·{" "}
                    {when(point.created_at)} · {point.tasks} tasks ·{" "}
                    {point.rows} rows
                  </p>
                  <p
                    className="mt-1 truncate text-xs text-muted-foreground"
                    title={point.checksum}
                  >
                    SHA-256 {point.checksum}
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    onClick={() =>
                      void action(
                        () =>
                          download(
                            `${base}/savepoints/${point.id}/download`,
                            `workspace-${selected}-savepoint-${point.id}.json`,
                          ),
                        "Savepoint downloaded.",
                      )
                    }
                  >
                    <Download size={14} />
                    Export
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    onClick={() =>
                      void action(async () => {
                        const { data } = await api.get(
                          `${base}/savepoints/${point.id}/preview`,
                        );
                        setRestore({ point, preview: data });
                        setConfirmation("");
                      }, "Restore preview ready.")
                    }
                  >
                    Preview restore
                  </Button>
                </div>
              </li>
            ))}
          </ul>
          {!points.length && (
            <p className="text-sm text-muted-foreground">No savepoints yet.</p>
          )}
          {restore && (
            <div
              className="space-y-3 rounded-lg border border-amber-300 p-4"
              role="region"
              aria-label="Restore preview"
            >
              <h3 className="font-semibold">Restore {restore.point.name}</h3>
              <p className="text-sm">
                {restore.preview.changed_tasks} tasks will change.{" "}
                {restore.preview.newer_tasks_kept} newer tasks will be kept.{" "}
                {restore.preview.missing_tasks} saved tasks are missing.
              </p>
              <p className="text-sm text-muted-foreground">
                {restore.preview.scope} A safety savepoint is created before
                restoring.
              </p>
              <label className="block text-sm">
                Type <strong>{workspace.name}</strong> to confirm
                <Input
                  value={confirmation}
                  onChange={(e) => setConfirmation(e.target.value)}
                  aria-label="Confirm workspace name"
                />
              </label>
              <div className="flex gap-2">
                <Button
                  disabled={
                    busy ||
                    confirmation !== workspace.name ||
                    restore.preview.missing_tasks > 0
                  }
                  onClick={() =>
                    void action(async () => {
                      const { data } = await api.post(
                        `${base}/savepoints/${restore.point.id}/restore`,
                        {
                          confirm_name: confirmation,
                          expected_current_hash:
                            restore.preview.expected_current_hash,
                        },
                      );
                      setRestore(null);
                      await load();
                      setConfirmation("");
                      if (!data.safety_savepoint_id)
                        throw new Error("Missing safety savepoint");
                    }, "Task content restored. A safety savepoint was saved.")
                  }
                >
                  Restore task content
                </Button>
                <Button
                  variant="outline"
                  disabled={busy}
                  onClick={() => setRestore(null)}
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </section>
      )}
      {workspace && !manages && (
        <p className="text-sm text-muted-foreground">
          Workspace savepoints and backup schedules are available to workspace
          owners and administrators.
        </p>
      )}
      {user?.is_superuser && (
        <section className="space-y-4 rounded-xl border bg-card p-5">
          <h2 className="text-lg font-semibold">
            Full BusinessSuite backups · system admin
          </h2>
          <p className="text-sm text-muted-foreground">
            All modules and users in the database, plus uploaded files from the
            configured local, S3 or Vercel Blob storage. Restore is performed
            offline into a new directory and empty database. Application
            encryption keys must be stored securely in a separate backup.
          </p>
          <Button
            disabled={busy || !full}
            onClick={() =>
              void action(async () => {
                await api.post("/project-management/data-backups", undefined, {
                  timeout: 0,
                });
                await loadFull();
              }, "Full-system archive created and verified.")
            }
          >
            {busy ? "Working…" : "Back up entire system now"}
          </Button>
          {full && (
            <>
              {policyForm(fullPolicy, setFullPolicy)}
              <Button
                variant="outline"
                disabled={busy}
                onClick={() =>
                  void action(async () => {
                    await api.put(
                      "/project-management/data-backups/policy",
                      fullPolicy,
                    );
                    await loadFull();
                  }, "Full-system backup policy saved.")
                }
              >
                Save full-system schedule
              </Button>
              <p className="text-xs text-muted-foreground">
                {full.scheduler_enabled
                  ? "In-process worker enabled."
                  : "Run the external scheduled worker or enable BUSINESSSUITE_BACKUP_SCHEDULER on a durable server."}{" "}
                {when(fullPolicy.last_success_at)}
              </p>
              <ul className="space-y-2">
                {full.archives.map((archive: any) => (
                  <li
                    className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3 text-sm"
                    key={archive.id}
                  >
                    <div>
                      {when(archive.created_at)} ·{" "}
                      {archive.automatic ? "Automatic" : "Manual"}
                      <p className="text-xs text-muted-foreground">
                        {archive.state === "unreadable"
                          ? "Unreadable archive"
                          : `${archive.file_count} files`}{" "}
                        · {(archive.bytes / 1048576).toFixed(2)} MB ·{" "}
                        {archive.database}
                      </p>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={busy || archive.state === "unreadable"}
                      onClick={() =>
                        void action(
                          () =>
                            download(
                              `/project-management/data-backups/${archive.id}/download`,
                              `businesssuite-${archive.id}.zip`,
                            ),
                          "Full backup downloaded.",
                        )
                      }
                    >
                      Download archive
                    </Button>
                  </li>
                ))}
              </ul>
              <p className="break-words rounded-md bg-muted p-3 font-mono text-xs">
                python scripts/data_recovery.py --restore PATH_TO_ARCHIVE
                --target-directory NEW_OFFLINE_DIRECTORY
              </p>
            </>
          )}
        </section>
      )}
      {busy && (
        <p role="status" className="text-sm text-muted-foreground">
          Working… Please keep this page open.
        </p>
      )}
    </main>
  );
}
