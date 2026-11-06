import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { api } from "@/services/api";
import { projectsAPI } from "../services/api";
import { workspaceError } from "../pages/workspaceTypes";
import type { PMSProject, ProjectPriority } from "../types";

export default function QuickCreateProject({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (project: PMSProject) => void;
}) {
  const [workspaces, setWorkspaces] = useState<
    { id: number; name: string; role: string }[]
  >([]);
  const [workspace, setWorkspace] = useState("");
  const [name, setName] = useState(""),
    [priority, setPriority] = useState<ProjectPriority>("Medium");
  const [due, setDue] = useState(""),
    [description, setDescription] = useState("");
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const working = useRef(false),
    projectKey = useRef("");
  useEffect(() => {
    if (!open) return;
    setName("");
    setDescription("");
    setDue("");
    setPriority("Medium");
    setError("");
    projectKey.current = `P${crypto.randomUUID().replace(/-/g, "").slice(0, 9).toUpperCase()}`;
    let active = true;
    void api
      .get<typeof workspaces>("/project-management/workspaces")
      .then(({ data }) => {
        if (active) {
          const allowed = data.filter((w) => w.role === "Admin");
          setWorkspaces(allowed);
          setWorkspace(String(allowed[0]?.id || ""));
        }
      })
      .catch((e) => {
        if (active) setError(workspaceError(e));
      });
    return () => {
      active = false;
    };
  }, [open]);
  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v && !busy) onClose();
      }}
    >
      <DialogContent>
        <DialogTitle>New project</DialogTitle>
        <p className="text-sm text-muted-foreground">
          Start with a name and workspace. Add the details as your plan takes
          shape.
        </p>
        <form
          className="space-y-4"
          onSubmit={async (e) => {
            e.preventDefault();
            if (working.current) return;
            working.current = true;
            setBusy(true);
            setError("");
            try {
              const p = await projectsAPI.create({
                name: name.trim(),
                workspace_id: Number(workspace),
                project_key: projectKey.current,
                status: "Active",
                priority,
                due_date: due || undefined,
                description: description || undefined,
              });
              onCreated(p);
              onClose();
            } catch (e) {
              setError(workspaceError(e));
            } finally {
              setBusy(false);
              working.current = false;
            }
          }}
        >
          <fieldset disabled={busy} className="space-y-4">
            <label className="grid gap-2 text-sm">
              Project name
              <Input
                autoFocus
                required
                maxLength={180}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="What are you working on?"
              />
            </label>
            <label className="grid gap-2 text-sm">
              Workspace
              <NativeSelect
                required
                className="rounded-md border bg-background p-2"
                value={workspace}
                onChange={(e) => setWorkspace(e.target.value)}
              >
                <option value="">Choose workspace</option>
                {workspaces.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
              </NativeSelect>
            </label>
            <details>
              <summary className="cursor-pointer text-sm text-primary">
                Optional details
              </summary>
              <div className="grid gap-3 pt-3">
                <label className="grid gap-1 text-sm">
                  Priority
                  <NativeSelect
                    className="rounded-md border bg-background p-2"
                    value={priority}
                    onChange={(e) =>
                      setPriority(e.target.value as ProjectPriority)
                    }
                  >
                    {["Low", "Medium", "High", "Critical"].map((p) => (
                      <option key={p}>{p}</option>
                    ))}
                  </NativeSelect>
                </label>
                <label className="grid gap-1 text-sm">
                  Due date
                  <Input
                    type="date"
                    value={due}
                    onChange={(e) => setDue(e.target.value)}
                  />
                </label>
                <label className="grid gap-1 text-sm">
                  Description
                  <textarea
                    className="rounded-md border bg-background p-2"
                    maxLength={20000}
                    rows={3}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                </label>
              </div>
            </details>
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
            <div className="flex justify-between gap-2">
              <Button type="button" variant="ghost" asChild>
                <Link
                  to={`/pms/projects/new${workspace ? `?workspace_id=${workspace}` : ""}`}
                >
                  Full project form
                </Link>
              </Button>
              <Button
                type="submit"
                disabled={!name.trim() || !workspace || busy}
              >
                {busy ? "Creating…" : "Create project"}
              </Button>
            </div>
          </fieldset>
        </form>
      </DialogContent>
    </Dialog>
  );
}
