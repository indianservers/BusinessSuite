import { Link } from "react-router-dom";
import { lazy, Suspense } from "react";
import { useTaskTheme } from "../components/TaskThemeSwitcher";
const Classic = lazy(() => import("./TasksReferencePage"));
const WhatsApp = lazy(() => import("./WhatsAppTasksPage"));
export default function TaskExperiencePage() {
  const { theme } = useTaskTheme();
  return (
    <><nav className="flex flex-wrap gap-4 px-4 py-3 border-b text-sm" aria-label="Task workspaces"><Link to="/pms/tasks">Tasks</Link><Link className="text-primary underline" to="/pms/tasks-follow-ups">Tasks & Follow-ups</Link><Link to="/pms/follow-ups">Customer follow-ups</Link></nav><Suspense fallback={<p role="status">Loading tasks…</p>}>
      {theme === "whatsapp" ? <WhatsApp /> : <Classic />}
    </Suspense></>
  );
}
