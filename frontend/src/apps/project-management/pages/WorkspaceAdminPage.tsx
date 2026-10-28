import { useRefreshableEffect } from "@/lib/page-refresh";
import { useEffect, useState } from "react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { workspaceError } from "./workspaceTypes";

type Row = {
  id: number;
  name: string;
  owners: string[];
  deleted_at: string | null;
};
export default function WorkspaceAdminPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [previewHash, setPreviewHash] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const base = "/project-management/admin/workspaces";
  const load = async () => {
    const { data } = await api.get(base);
    setRows(data.items);
    setPreviewHash(data.preview_hash);
  };
  useRefreshableEffect(() => {
    void load().catch((e) => setError(workspaceError(e)));
  }, []);
  const act = async (work: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await work();
      await load();
      setConfirmation("");
    } catch (e) {
      setError(workspaceError(e));
    } finally {
      setBusy(false);
    }
  };
  const count = rows.filter((row) => !row.deleted_at).length;
  return (
    <main className="mx-auto max-w-4xl space-y-5 p-4 sm:p-6">
      <h1 className="text-2xl font-semibold">Workspace reset & restore</h1>
      <p className="text-sm text-muted-foreground">
        Admin only. Includes workspaces created by admins and users in your
        organization. Reset soft-deletes the workspace from active views and
        blocks access until restored. Projects, tasks, files, messages, members
        and financial records are preserved.
      </p>
      {error && (
        <p
          role="alert"
          className="rounded-lg border border-red-300 p-4 text-sm"
        >
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="rounded-lg border p-4 text-sm">
          {notice}
        </p>
      )}
      <section className="space-y-3 rounded-xl border bg-card p-5">
        <h2 className="text-lg font-semibold">
          Reset all {count} active workspaces
        </h2>
        <p className="text-sm">
          Review the workspaces below, then type{" "}
          <strong>RESET ALL WORKSPACES</strong>. All creators are included;
          other organizations are excluded.
        </p>
        <label className="block text-sm">
          Confirm reset
          <Input
            value={confirmation}
            onChange={(e) => setConfirmation(e.target.value)}
            disabled={busy}
            autoComplete="off"
          />
        </label>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="destructive"
            disabled={
              busy ||
              !count ||
              !previewHash ||
              confirmation !== "RESET ALL WORKSPACES"
            }
            onClick={() =>
              void act(async () => {
                const { data } = await api.post(`${base}/reset-all`, {
                  confirmation,
                  preview_hash: previewHash,
                });
                setNotice(
                  `${data.soft_deleted} workspaces soft-deleted. They can be restored below.`,
                );
              })
            }
          >
            Reset all workspaces
          </Button>
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => void act(load)}
          >
            Refresh preview
          </Button>
        </div>
      </section>
      <ul className="space-y-3">
        {rows.map((row) => (
          <li
            className="flex flex-col justify-between gap-3 rounded-xl border p-4 sm:flex-row"
            key={row.id}
          >
            <div className="min-w-0">
              <strong className="break-words">{row.name}</strong>
              <p className="break-words text-xs text-muted-foreground">
                Owner: {row.owners.join(", ") || "No current owner"}
              </p>
              <p className="text-sm">
                {row.deleted_at ? "Soft-deleted" : "Active"}
              </p>
            </div>
            {row.deleted_at && (
              <Button
                variant="outline"
                disabled={busy}
                onClick={() =>
                  void act(async () => {
                    await api.post(`${base}/${row.id}/restore`);
                    setNotice(
                      `${row.name} restored with its existing data and memberships.`,
                    );
                  })
                }
              >
                Restore {row.name}
              </Button>
            )}
          </li>
        ))}
      </ul>
      {!rows.length && !error && (
        <p className="text-sm text-muted-foreground">
          No workspaces in your organization.
        </p>
      )}
    </main>
  );
}
