import { Link } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import SuiteBrand from "./SuiteBrand";
import SuiteProfileMenu from "./SuiteProfileMenu";
import SuiteNotificationBell from "./SuiteNotificationBell";
import GlobalSearch from "@/components/app/GlobalSearch";
import CompanySwitcher from "./CompanySwitcher";

export default function SuiteHeader() {
  const authenticated = useAuthStore((s) => s.isAuthenticated);
  return (
    <header className="suite-header">
      <SuiteBrand
        to={authenticated ? "/dashboard" : "/"}
        subtitle={
          authenticated ? "APPLICATION DASHBOARD" : "YOUR CONNECTED WORKSPACE"
        }
      />
      <nav aria-label="Suite navigation">
        {authenticated ? (
          <>
            <div className="suite-header-search">
              <GlobalSearch />
            </div>
            <CompanySwitcher />
            <SuiteNotificationBell />
            <SuiteProfileMenu />
          </>
        ) : (
          <>
            <Link to="/help">Help</Link>
            <Link className="suite-primary" to="/login">
              Sign in
            </Link>
          </>
        )}
      </nav>
    </header>
  );
}
