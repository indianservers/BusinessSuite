import { type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import SuiteHeader from "./SuiteHeader";
import "@/pages/module-dashboard.css";

export default function SuitePageShell({ children }: { children: ReactNode }) {
  const authenticated = useAuthStore((s) => s.isAuthenticated);
  return (
    <div className="module-dashboard suite-page-shell">
      <a className="suite-skip" href="#suite-main">
        Skip to content
      </a>
      <SuiteHeader />
      <main className="suite-page" id="suite-main" tabIndex={-1}>
        <Link
          className="suite-back"
          aria-label={
            authenticated ? "All applications" : "Explore applications"
          }
          to={authenticated ? "/dashboard" : "/"}
        >
          ← {authenticated ? "All applications" : "Explore applications"}
        </Link>
        {children}
      </main>
    </div>
  );
}
