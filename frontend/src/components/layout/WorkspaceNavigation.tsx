import { useCompanyBranding } from "@/features/access/useCompanyBranding";
import { assetUrl } from "@/lib/utils";
import ModuleSwitcher from "./ModuleSwitcher";
import { useLocation } from "react-router-dom";
import { ChevronLeft, ChevronRight, LogOut, Plus, Sparkles, X } from "lucide-react";
import PMSNavigationMenu from "./PMSNavigationMenu";
export default function WorkspaceNavigation({
  workspaceId,
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
  const companyBrand = useCompanyBranding(useLocation().pathname);
  return (
    <>
      <div className="kf-workspace-brand">
        <span>
          <span className="kf-brand-symbol">
            {companyBrand.logo ? <img src={assetUrl(companyBrand.logo)} alt={companyBrand.name || "Company logo"} style={{width:32,height:32,objectFit:"contain",borderRadius:8}} /> : <Sparkles size={21} />}
          </span>
          <span className="kf-brand-name" title={companyBrand.name || "KaryaFlow"} style={{maxWidth:150,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{companyBrand.name || "KaryaFlow"}</span>
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
        <PMSNavigationMenu workspaceId={workspaceId} collapsed={collapsed} onNavigate={onClose} />
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
