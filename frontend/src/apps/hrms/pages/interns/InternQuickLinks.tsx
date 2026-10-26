import { Link, useLocation } from "react-router-dom";
import { ClipboardList, Users, Layers } from "lucide-react";

const links = [
  { to: "/hrms/interns/applications", label: "Signups & Approvals", description: "Review new signups and approve or reject applications", Icon: ClipboardList },
  { to: "/hrms/interns/list", label: "All Interns", description: "Find interns, open profiles and manage batch enrollment", Icon: Users },
  { to: "/hrms/interns/batches", label: "Batches", description: "Create batches and organize interns into groups", Icon: Layers },
];

export default function InternQuickLinks() {
  const { pathname } = useLocation();
  return <nav aria-label="Intern quick access" className="grid gap-3 sm:grid-cols-3">
    {links.map(({ to, label, description, Icon }) => {
      const active = pathname === to || (to.endsWith("applications") && pathname === "/hrms/interns-hub/applications");
      return <Link key={to} to={to} aria-current={active ? "page" : undefined}
        className={`flex items-start gap-3 rounded-xl border p-4 transition-colors hover:border-primary hover:bg-primary/5 ${active ? "border-primary bg-primary/5" : "bg-card"}`}>
        <Icon aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
        <span><strong className="block text-sm">{label}</strong><span className="mt-1 block text-xs text-muted-foreground">{description}</span></span>
      </Link>;
    })}
  </nav>;
}
