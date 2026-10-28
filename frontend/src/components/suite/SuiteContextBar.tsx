import { Link, useLocation } from "react-router-dom";
import { LayoutGrid } from "lucide-react";
import GlobalSearch from "@/components/app/GlobalSearch";
import ModuleSwitcher from "@/components/layout/ModuleSwitcher";
import SuiteProfileMenu from "./SuiteProfileMenu";
import SuiteNotificationBell from "./SuiteNotificationBell";
import "./suite.css";

export default function SuiteContextBar() {
  const { pathname } = useLocation();
  return (
    <nav className="suite-context-bar" aria-label="Business Suite navigation">
      <div>
        <Link
          className="suite-home"
          to="/dashboard"
          aria-label="All applications"
        >
          <LayoutGrid size={18} />
          <span>All applications</span>
        </Link>
        <ModuleSwitcher />
      </div>
      <div className="suite-context-actions">
        {!pathname.startsWith("/pms") && <GlobalSearch />}
        <SuiteNotificationBell />
        <SuiteProfileMenu />
      </div>
    </nav>
  );
}
