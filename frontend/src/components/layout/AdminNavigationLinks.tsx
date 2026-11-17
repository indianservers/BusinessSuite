import { Settings, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { cn } from "@/lib/utils";

export default function AdminNavigationLinks({ collapsed = false, onNavigate }: {
  collapsed?: boolean; onNavigate: () => void;
}) {
  const user = useAuthStore(state => state.user);
  if (!user?.is_superuser && !user?.access?.isAccessAdmin) return null;
  return <nav aria-label="Administration" className="shrink-0">
    {[
      { to: "/company-admin", label: "Company Admin", icon: Settings },
      { to: "/admin/access", label: "Users & Access", icon: Users },
    ].map(({ to, label, icon: Icon }) => <Link key={to} to={to} onClick={onNavigate}
      className={cn("nav-link min-h-9 text-xs", collapsed && "justify-center")}
      aria-label={label} title={label}>
      <Icon size={17} />{!collapsed && label}
    </Link>)}
  </nav>;
}
