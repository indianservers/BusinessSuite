import NavigationShortcuts from "./NavigationShortcuts";
import ModuleSwitcher from "./ModuleSwitcher";
import { Link } from "react-router-dom";
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Folder,
  FileText,
  Home,
  LayoutGrid,
  LogOut,
  Menu,
  Plus,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import MessagingNavLink from "./MessagingNavLink";
import PMSMoreMenu from "./PMSMoreMenu";
export default function WorkspaceNavigation({
  view,
  onView,
  workspaceId,
  projectId,
  collapsed,
  onCollapse,
  onJoin,
  onLogout,
  onClose,
}: {
  view: string;
  onView: (view: "board" | "people" | "calendar") => void;
  workspaceId?: number;
  projectId?: number;
  collapsed: boolean;
  onCollapse: () => void;
  onJoin: () => void;
  onLogout: () => void;
  onClose: () => void;
}) {
  const choose = (value: "board" | "people" | "calendar") => {
    onView(value);
    onClose();
  };
  return (
    <>
      <div className="kf-workspace-brand">
        <span>
          <span className="kf-brand-symbol">
            <Sparkles size={21} />
          </span>
          <span className="kf-brand-name">KaryaFlow</span>
        </span>
        <button
          className="kf-sidebar-collapse"
          onClick={onCollapse}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
        <button
          className="kf-mobile-close"
          onClick={onClose}
          aria-label="Close navigation"
        >
          <X size={18} />
        </button>
      </div>
      <nav className="kf-workspace-global" aria-label="Suite navigation">
        <Link to="/pms/overview" title="Home">
          <Home />
          <span>Home</span>
        </Link>
        <button
          title="Work"
          className={!["people", "calendar"].includes(view) ? "active" : ""}
          onClick={() => choose("board")}
        >
          <Folder />
          <span>Work</span>
        </button>
        <button
          title="People"
          className={view === "people" ? "active" : ""}
          onClick={() => choose("people")}
        >
          <Users />
          <span>People</span>
        </button>
        <Link to="/pms/projects" title="Projects">
          <LayoutGrid />
          <span>Projects</span>
        </Link>
        <Link to="/pms/notes" title="My Notes"><FileText /><span>My Notes</span></Link>
        <button
          title="Calendar"
          className={view === "calendar" ? "active" : ""}
          onClick={() => choose("calendar")}
        >
          <CalendarDays />
          <span>Calendar</span>
        </button>
        <MessagingNavLink
          workspaceId={workspaceId}
          collapsed={collapsed}
          className="kf-workspace-message"
        />
        <NavigationShortcuts
          excludedPaths={["/pms", "/pms/overview", "/pms/workspaces", "/pms/teams", "/pms/projects", "/pms/notes", "/pms/calendar", "/pms/messages"]}
          collapsed={collapsed}
          onNavigate={onClose}
        />
        <PMSMoreMenu
          workspaceId={workspaceId}
          projectId={projectId}
          collapsed={collapsed}
          className="kf-workspace-more"
        />
        <button
          className="kf-nav-account-action"
          title="Join workspace"
          onClick={onJoin}
        >
          <Plus />
          <span>Join workspace</span>
        </button>
        <button
          className="kf-nav-account-action"
          title="Log out"
          onClick={onLogout}
        >
          <LogOut />
          <span>Log out</span>
        </button>
      </nav>
      {!collapsed && (
        <>
          <ModuleSwitcher />
        </>
      )}
    </>
  );
}
