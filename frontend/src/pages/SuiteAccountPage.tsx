import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import { authApi } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { modules } from "@/lib/moduleCatalog";
import { canAccessRoute } from "@/lib/roles";
import SuitePageShell from "@/components/suite/SuitePageShell";

export default function SuiteAccountPage() {
  const user = useAuthStore((s) => s.user);
  const location = useLocation();
  const security = useRef<HTMLElement>(null);
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    if (location.hash === "#security") security.current?.focus();
  }, [location.hash]);
  const changePassword = useMutation({
    mutationFn: () => authApi.changePassword(current, password),
    onSuccess: () => {
      setCurrent("");
      setPassword("");
      setConfirm("");
      setMessage("Your password has been changed.");
      setError("");
    },
    onError: (err: unknown) =>
      setError(
        (err as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail || "Could not change your password. Please try again.",
      ),
  });
  const profiles = modules.filter(
    (m) =>
      m.key !== "power_apps" &&
      canAccessRoute(`${m.homePath}/profile`, user?.role, user?.is_superuser),
  );
  return (
    <SuitePageShell>
      <h1>My account</h1>
      <section className="suite-panel">
        <h2>Profile</h2>
        <dl className="suite-details">
          <dt>Name</dt>
          <dd>{user?.name || "Not provided"}</dd>
          <dt>Email</dt>
          <dd>{user?.email}</dd>
          <dt>Organization</dt>
          <dd>{user?.access?.companyName || "Your workspace"}</dd>
        </dl>
        <div className="suite-inline-actions">
          {profiles.map((m) => (
            <Link
              key={m.key}
              className="suite-secondary"
              to={`${m.homePath}/profile`}
            >
              {m.name} profile
            </Link>
          ))}
        </div>
      </section>
      <section
        className="suite-panel"
        id="security"
        ref={security}
        tabIndex={-1}
      >
        <h2>Account settings</h2>
        <p>
          Change your password. Your organization’s password policy applies.
        </p>
        <form
          className="suite-form"
          onSubmit={(event) => {
            event.preventDefault();
            setError("");
            setMessage("");
            if (password !== confirm) {
              setError("Passwords do not match.");
              return;
            }
            changePassword.mutate();
          }}
        >
          <label>
            Current password
            <input
              type="password"
              autoComplete="current-password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              required
            />
          </label>
          <label>
            New password
            <input
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
            />
          </label>
          <label>
            Confirm new password
            <input
              type="password"
              autoComplete="new-password"
              aria-describedby={error ? "account-error" : undefined}
              aria-invalid={!!error}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              minLength={8}
              required
            />
          </label>
          {error && (
            <p id="account-error" className="suite-error" role="alert">
              {error}
            </p>
          )}
          {message && <p role="status">{message}</p>}
          <button className="suite-primary" disabled={changePassword.isPending}>
            {changePassword.isPending ? "Saving…" : "Change password"}
          </button>
        </form>
      </section>
    </SuitePageShell>
  );
}
