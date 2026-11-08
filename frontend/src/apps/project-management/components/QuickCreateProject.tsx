import { useAuthStore } from "@/store/authStore";
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
  initialStatus = "Active",
  initialWorkspace,
}: {
  open: boolean;
  initialStatus?: PMSProject["status"];
  initialWorkspace?: number;
  onClose: () => void;
  onCreated: (project: PMSProject) => void;
}) {
  const user = useAuthStore(s => s.user);
  const draftKey = `pms-project-create:${user?.access?.companyId}:${user?.id}`;
  const [status, setStatus] = useState<PMSProject["status"]>(initialStatus);
  const [another, setAnother] = useState(false);
  const [template, setTemplate] = useState("");
  const [workspaces, setWorkspaces] = useState<
    { id: number; name: string; role: string }[]
  >([]);
  const [loadingWorkspaces, setLoadingWorkspaces] = useState(false);
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
    let draft: {name?:string;description?:string;due?:string;priority?:ProjectPriority;workspace?:string;status?:PMSProject["status"];template?:string;another?:boolean} = {};
    try { draft=JSON.parse(sessionStorage.getItem(draftKey)||"{}"); } catch {}
    setStatus(draft.status||initialStatus);
    setTemplate(draft.template||"");setAnother(!!draft.another);
    setName(draft.name || "");
    setDescription(draft.description || "");
    setDue(draft.due || "");
    setPriority(draft.priority || "Medium");
    setError("");
    projectKey.current = `P${crypto.randomUUID().replace(/-/g, "").slice(0, 9).toUpperCase()}`;
    let active = true;
    setLoadingWorkspaces(true);
    void api
      .get<typeof workspaces>("/project-management/workspaces")
      .then(({ data }) => {
        if (active) {
          const allowed = data.filter((w) => ["Owner","Admin"].includes(w.role));
          setWorkspaces(allowed);
          setWorkspace(allowed.some(w => w.id === initialWorkspace) ? String(initialWorkspace) : allowed.some(w => String(w.id) === draft.workspace) ? draft.workspace! : String(allowed[0]?.id || ""));
        }
      })
      .catch((e) => {
        if (active) setError(workspaceError(e));
      })
      .finally(() => {
        if (active) setLoadingWorkspaces(false);
      });
    return () => {
      active = false;
    };
  }, [open, draftKey, initialStatus, initialWorkspace]);
  useEffect(() => { if (open) try {sessionStorage.setItem(draftKey,JSON.stringify({name,description,due,priority,workspace,status,template,another}));} catch {} },[open,draftKey,name,description,due,priority,workspace,status,template,another]);
  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v && !busy) onClose();
      }}
    >
      <DialogContent className="suite-project-create-dialog">
        <DialogTitle>New project</DialogTitle>
        <p className="text-sm text-muted-foreground">
          Start with a name and workspace. Add the details as your plan takes
          shape.
        </p>
        <form
          className="suite-dialog-form"
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
                status,
                priority,
                due_date: due || undefined,
                description: description || undefined,
              });
              sessionStorage.removeItem(draftKey);
              onCreated(p);
              setName("");setDescription("");setDue("");setPriority("Medium");setTemplate("");
              projectKey.current = `P${crypto.randomUUID().replace(/-/g, "").slice(0, 9).toUpperCase()}`;
              if (!another) onClose();
            } catch (e) {
              setError(workspaceError(e));
            } finally {
              setBusy(false);
              working.current = false;
            }
          }}
        >
          <fieldset disabled={busy} className="space-y-4">
            <label className="block text-sm">Status<NativeSelect aria-label="New project status" value={status} onChange={e => setStatus(e.target.value as PMSProject["status"])}>{["Draft","Planned","Active","On Hold","Completed","Cancelled","Archived"].map(value => <option key={value}>{value}</option>)}</NativeSelect></label>
          <label className="grid gap-2 text-sm">Project brief template<NativeSelect aria-label="Project brief template" value={template} onChange={e => {const value=e.target.value;setTemplate(value);setDescription(value === "delivery" ? "Goal:\nScope:\nDeliverables:\nAcceptance criteria:\nRisks:" : value === "launch" ? "Launch objective:\nAudience:\nReadiness checklist:\nSuccess metrics:" : value === "internal" ? "Problem:\nProposed improvement:\nOwner responsibilities:\nDefinition of done:" : "");}}><option value="">Blank brief</option><option value="delivery">Client delivery brief</option><option value="launch">Product launch brief</option><option value="internal">Internal improvement brief</option></NativeSelect></label>
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
                aria-label="Project workspace"
                loading={loadingWorkspaces}
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
                    aria-label="New project priority"
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
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={another} onChange={e => setAnother(e.target.checked)}/>Create another after saving</label>
            <p className="text-xs text-muted-foreground">Unfinished details are kept in this browser session.</p>
          </fieldset>
            <footer className="flex justify-between gap-2">
              <Button type="button" variant="ghost" asChild>
                <Link
                  to={`/pms/projects/new${workspace ? `?workspace_id=${workspace}` : ""}`}
                >
                  Full project form
                </Link>
              </Button>
              <Button
                type="submit"
                data-save-action
                disabled={
                  !name.trim() || !workspace || busy || loadingWorkspaces
                }
              >
                {busy ? "Creating…" : "Create project"}
              </Button>
            </footer>
        </form>
      </DialogContent>
    </Dialog>
  );
}
