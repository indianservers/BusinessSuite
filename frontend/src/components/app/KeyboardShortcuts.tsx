import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Keyboard } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function KeyboardShortcuts() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "?" && !event.ctrlKey && !event.metaKey) setOpen(true);
      if (event.key === "Escape") setOpen(false);
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
      if (event.altKey && event.key.toLowerCase() === "h") {
        event.preventDefault();
        if (window.location.pathname.startsWith("/crm")) navigate("/crm");
        else if (window.location.pathname.startsWith("/hrms")) navigate("/hrms");
        else if (window.location.pathname.startsWith("/pms")) navigate("/pms");
        else navigate("/dashboard");
      }
      if (event.altKey && event.key.toLowerCase() === "a") {
        event.preventDefault();
        if (window.location.pathname.startsWith("/crm")) navigate("/crm/tickets");
        else if (window.location.pathname.startsWith("/hrms")) navigate("/hrms/leave-requests");
        else if (window.location.pathname.startsWith("/pms")) navigate("/pms/enterprise-engine");
        else navigate("/approvals");
      }
      if (event.altKey && event.key.toLowerCase() === "r") {
        event.preventDefault();
        if (window.location.pathname.startsWith("/crm")) navigate("/crm/reports");
        else if (window.location.pathname.startsWith("/hrms")) navigate("/hrms/reports");
        else if (window.location.pathname.startsWith("/pms")) navigate("/pms/reports");
        else navigate("/reports");
      }
      if (event.key.toLowerCase() === "n" && !event.ctrlKey && !event.metaKey && !event.altKey) {
        if (window.location.pathname.startsWith("/crm")) navigate("/crm/leads");
        if (window.location.pathname.startsWith("/hrms")) navigate("/hrms/employees/new");
        if (window.location.pathname.startsWith("/pms")) navigate("/pms/projects/new");
      }
      if (event.key.toLowerCase() === "c" && window.location.pathname.startsWith("/pms")) navigate("/pms/projects/new");
      if (event.key === "/" && window.location.pathname.startsWith("/pms")) {
        event.preventDefault();
        navigate("/pms/issue-navigator-pro");
      }
      if (event.key.toLowerCase() === "a" && window.location.pathname.startsWith("/pms")) navigate("/pms/enterprise-engine");
      if (event.key.toLowerCase() === "m" && window.location.pathname.startsWith("/pms")) navigate("/pms/backlog-grooming");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate]);
  return (
    <>
      <Button variant="ghost" size="icon" title="Keyboard shortcuts" aria-label="Keyboard shortcuts" onClick={() => setOpen(true)}>
        <Keyboard className="h-5 w-5" />
      </Button>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setOpen(false)}>
          <div className="w-full max-w-md rounded-lg border bg-background p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Keyboard Shortcuts</h2>
              <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>Close</Button>
            </div>
            <div className="space-y-3 text-sm">
              {[
                ["Cmd/Ctrl + K", "Global search"],
                ["?", "Open this help"],
                ["Esc", "Close dialogs"],
                ["Alt + H", "Go dashboard"],
                ["Alt + A", "Open approvals or assigned work"],
                ["Alt + R", "Open reports"],
                ["N", "Create in current module"],
                ["PMS: C", "Create project/work item"],
                ["PMS: /", "Open issue navigator"],
                ["PMS: A", "Assign/open enterprise engine"],
                ["PMS: M", "Move/groom backlog"],
              ].map(([key, desc]) => (
                <div key={key} className="flex items-center justify-between rounded-md border p-3">
                  <span>{desc}</span>
                  <kbd className="rounded bg-muted px-2 py-1 text-xs font-semibold">{key}</kbd>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
