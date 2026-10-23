import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Keyboard } from "lucide-react";
import { Button } from "@/components/ui/button";
import * as Dialog from "@radix-ui/react-dialog";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";

export default function KeyboardShortcuts() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const user = useAuthStore(s => s.user);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.repeat || event.defaultPrevented || (event.target as HTMLElement)?.closest("input, textarea, select, [contenteditable=true], [role=dialog], [role=menu]")) return;
      if (event.key === "?" && !event.ctrlKey && !event.metaKey) setOpen(true);
      if (event.key === "Escape") setOpen(false);
      const go = (path: string) => { if (canAccessRoute(path, user?.role, user?.is_superuser)) navigate(path); };
      if (event.altKey && event.key.toLowerCase() === "h") {
        event.preventDefault();
        if (window.location.pathname.startsWith("/crm")) go("/crm");
        else if (window.location.pathname.startsWith("/hrms")) go("/hrms");
        else if (window.location.pathname.startsWith("/pms")) go("/pms");
        else go("/dashboard");
      }
      if (event.altKey && event.key.toLowerCase() === "a") {
        event.preventDefault();
        if (window.location.pathname.startsWith("/crm")) go("/crm/tickets");
        else if (window.location.pathname.startsWith("/hrms")) go("/hrms/leave-requests");
        else if (window.location.pathname.startsWith("/pms")) go("/pms/enterprise-engine");
        else go("/approvals");
      }
      if (event.altKey && event.key.toLowerCase() === "r") {
        event.preventDefault();
        if (window.location.pathname.startsWith("/crm")) go("/crm/reports");
        else if (window.location.pathname.startsWith("/hrms")) go("/hrms/reports");
        else if (window.location.pathname.startsWith("/pms")) go("/pms/reports");
        else go("/reports");
      }
      if (event.key.toLowerCase() === "n" && !event.ctrlKey && !event.metaKey && !event.altKey) {
        if (window.location.pathname.startsWith("/crm")) go("/crm/leads");
        if (window.location.pathname.startsWith("/hrms")) go("/hrms/employees/new");
        if (window.location.pathname.startsWith("/pms")) go("/pms/projects/new");
      }
      if (!event.ctrlKey && !event.metaKey && !event.altKey && event.key.toLowerCase() === "c" && window.location.pathname.startsWith("/pms")) go("/pms/projects/new");
      if (event.key === "/" && window.location.pathname.startsWith("/pms")) {
        event.preventDefault();
        go("/pms/issue-navigator-pro");
      }
      if (!event.ctrlKey && !event.metaKey && !event.altKey && event.key.toLowerCase() === "a" && window.location.pathname.startsWith("/pms")) go("/pms/enterprise-engine");
      if (!event.ctrlKey && !event.metaKey && !event.altKey && event.key.toLowerCase() === "m" && window.location.pathname.startsWith("/pms")) go("/pms/backlog-grooming");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate, user?.role, user?.is_superuser]);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild><Button variant="ghost" size="icon" title="Keyboard shortcuts" aria-label="Keyboard shortcuts">
        <Keyboard className="h-5 w-5" />
      </Button></Dialog.Trigger>
      <Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 max-h-[90dvh] w-[calc(100%_-_2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-lg border bg-background p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <Dialog.Title className="text-lg font-semibold">Keyboard Shortcuts</Dialog.Title><Dialog.Description className="sr-only">Navigation shortcuts do not run while typing or using a dialog.</Dialog.Description>
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
          </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
