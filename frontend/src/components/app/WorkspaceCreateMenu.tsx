import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Bell, CheckSquare, FileText, Folder, Hash, LayoutDashboard, List, MessageSquare, PanelsTopLeft, Paperclip, Sheet, Tag, Timer, Video, Workflow } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import NewMenu, { type NewAction } from "./NewMenu";
const QuickTaskCapture = lazy(() => import("@/apps/project-management/components/QuickTaskCapture"));

/** Reuse the destination's own editor, validation, and authorization. */
export default function WorkspaceCreateMenu({ actions, children }: { actions: NewAction[]; children?: (actions: NewAction[]) => ReactNode }) {
  const location = useLocation(), navigate = useNavigate();
  const user = useAuthStore(s => s.user);
  const [capture, setCapture] = useState<"Sheet" | "Artifact" | "Clip" | null>(null);
  const [quickTask, setQuickTask] = useState<"task" | "subtask" | null>(null);
  useEffect(() => setCapture(null), [location.pathname, location.search]);
  const pms = location.pathname.startsWith("/pms");
  const root = pms ? "/pms" : "/crm";
  const grant = user?.access?.grants.project_management;
  const ownGrant = user?.access?.grants[pms ? "project_management" : "crm"];
  const allowed = (path: string) => (user?.is_superuser || !ownGrant || ownGrant.enabled && ownGrant.actions.includes("create")) && canAccessRoute(path, user?.role, user?.is_superuser) &&
    (!path.startsWith("/pms") || pms || user?.is_superuser || !user?.access?.managed || !!grant?.enabled && grant.actions.includes("create"));
  const go = (path: string) => {
    const target = new URL(path, window.location.origin);
    // Carry workspace context only within the same module.
    if (target.pathname.startsWith(root + "/")) {
      const workspace = new URLSearchParams(location.search).get("workspace");
      if (workspace) target.searchParams.set("workspace", workspace);
    }
    navigate(target.pathname + target.search + target.hash);
  };
  const extra: NewAction[] = [];
  const add = (label: string, description: string, icon: NewAction["icon"], path: string, onSelect?: () => void) => {
    if (!actions.some(a => a.label === label) && allowed(path.split("?")[0])) extra.push({ label, description, icon, menuPaths: [path.split("?")[0]], onSelect: onSelect || (() => go(path)) });
  };
  const taskId = location.pathname.match(/^\/pms\/(?:projects\/\d+\/)?tasks\/(\d+)/)?.[1];
  add("Subtask", taskId ? "Create a child of this task" : "Choose a parent and create a child task", CheckSquare, taskId ? `/pms/tasks/new?parentTaskId=${taskId}&workType=Sub-task` : "/pms/tasks/new", () => setQuickTask("subtask"));
  if (pms && actions.some(action => action.label === "Task")) add("Quick task", "Title, assignee and due date · saved drafts and templates", CheckSquare, "/pms/tasks/new", () => setQuickTask("task"));
  add("List", "Organize work in the list view", List, pms ? "/pms/tasks?layout=list" : "/crm/tasks");
  add("Folder", "Create and organize folders in Files", Folder, `${root}/files`);
  add("Space", "Create or manage a workspace", PanelsTopLeft, `${root}/workspaces`, pms ? actions.find(a => a.label === "Workspace")?.onSelect : undefined);
  add("Document", pms ? "Open the document editor and templates" : "Opens PMS · shared document editor and templates", FileText, "/pms/docs");
  add("Conversation", "Start a conversation in Messages", MessageSquare, `${root}/messages`);
  add("Page", pms ? "Create a page in Notes" : "Opens PMS · create a page in shared Notes", FileText, "/pms/notes?new=1");
  add("Custom Field", "Configure fields for your records", Hash, pms ? "/pms/custom-fields" : "/crm/record-metadata");
  add("Dashboard", "Open dashboards and reporting", LayoutDashboard, pms ? "/pms/dashboards" : "/crm/dashboard");
  add("Tag", pms ? "Manage tags for your work" : "Open CRM records to edit their tags", Tag, pms ? "/pms/tags" : "/crm/records");
  add("Form", "Open a blank form draft", FileText, `${root}/forms/new`);
  add("Reminder", "Open task follow-ups and reminders", Bell, "/pms/tasks-follow-ups");
  add("Time Tracked", pms ? "Record time in PMS time tracking" : "Opens PMS · record time against a task", Timer, "/pms/time-tracking");
  add("View List", "Open and manage saved list views", List, pms ? "/pms/tasks?layout=list" : "/crm/leads?view=table");
  add("Whiteboard", "Arrange task or relationship cards", Workflow, pms ? "/pms/tasks?layout=whiteboard" : "/crm/leads?view=whiteboard");
  for (const [label, icon] of [["Sheet", Sheet], ["Artifact", Paperclip], ["Clip", Video]] as const) {
    add(label, label === "Sheet" ? "Attach a spreadsheet in Files" : label === "Clip" ? "Attach a recorded video in Files" : "Attach a deliverable in Files", icon, `${root}/files`, () => setCapture(label));
  }
  const combined = [...actions, ...extra];
  return <>{children ? children(combined) : <NewMenu actions={combined} />}
    {quickTask && <Suspense fallback={<p role="status">Loading quick task…</p>}><QuickTaskCapture subtask={quickTask === "subtask"} close={() => setQuickTask(null)}/></Suspense>}
    <Dialog open={!!capture} onOpenChange={open => { if (!open) setCapture(null); }}>
      <DialogContent><DialogTitle>{capture === "Sheet" ? "Attach a sheet" : capture === "Clip" ? "Attach a clip" : "Attach an artifact"}</DialogTitle>
        <p className="text-sm text-muted-foreground">{capture === "Sheet" ? "Upload an existing spreadsheet to your workspace Files. A native spreadsheet editor is not available here." : capture === "Clip" ? "Upload an existing video to your workspace Files. Recording is not available here." : "Upload a document, design, or other deliverable to your workspace Files."}</p>
        <Button onClick={() => { setCapture(null); go(`${root}/files`); }}>Open Files</Button>
      </DialogContent>
    </Dialog>
  </>;
}
