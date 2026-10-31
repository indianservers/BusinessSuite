import { lazy, Suspense } from "react";
import { useTaskTheme } from "../components/TaskThemeSwitcher";
const Classic = lazy(() => import("./TasksReferencePage"));
const WhatsApp = lazy(() => import("./WhatsAppTasksPage"));
export default function TaskExperiencePage() {
  const { theme } = useTaskTheme();
  return (
    <Suspense fallback={<p role="status">Loading tasks…</p>}>
      {theme === "whatsapp" ? <WhatsApp /> : <Classic />}
    </Suspense>
  );
}
