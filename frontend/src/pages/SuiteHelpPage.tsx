import { Link } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import SuitePageShell from "@/components/suite/SuitePageShell";

export default function SuiteHelpPage() {
  const authenticated = useAuthStore((s) => s.isAuthenticated);
  return (
    <SuitePageShell>
      <h1>Help & support</h1>
      <p>Find your way around Business Suite.</p>
      <section className="suite-panel">
        <h2>Sign in and recover access</h2>
        <p>
          Use your organization’s email and password, or an available company
          sign-in provider. If you cannot sign in, use “Forgot password?” to
          request a reset link.
        </p>
        <Link
          className="suite-secondary"
          to={authenticated ? "/account#security" : "/login"}
        >
          {authenticated ? "Account settings" : "Go to sign in"}
        </Link>
      </section>
      <section className="suite-panel">
        <h2>Find your work</h2>
        <p>
          Choose an application from the dashboard. Pin favorites, return to
          recent pages, or use Ctrl+K (⌘K on Mac) to search applications and
          authorized pages. Inside an application, use “Find a page” to filter
          its navigation.
        </p>
        <Link
          className="suite-secondary"
          to={authenticated ? "/dashboard" : "/"}
        >
          Explore applications
        </Link>
      </section>
      <section className="suite-panel">
        <h2>Companies and permissions</h2>
        <p>
          The company selector changes your active workspace. Applications,
          favorites, recent pages, and notifications follow that company.
          Contact your organization’s administrator to request access or correct
          your account details.
        </p>
      </section>
    </SuitePageShell>
  );
}
