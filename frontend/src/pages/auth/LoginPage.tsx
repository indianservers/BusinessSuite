import CompactForm from "@/components/forms/CompactForm";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff, Loader2, ShieldCheck, Headphones, UsersRound, Layers, Mail, LockKeyhole, LogIn } from "lucide-react";
import { type FirebaseOptions } from "firebase/app";
import { setRememberSession, useAuthStore } from "@/store/authStore";
import { authApi } from "@/services/api";
import { getApiBaseUrl } from "@/config/runtime";
import { loginDestination } from "@/lib/login";
import { modules } from "@/lib/moduleCatalog";
import SuiteBrand from "@/components/suite/SuiteBrand";
import "./suite-login.css";

const schema = z.object({
  email: z.string().trim().email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});
type LoginForm = z.infer<typeof schema>;
type AuthView = "login" | "forgot" | "sent" | "reset";
type AuthResponse = {
  access_token: string;
  refresh_token: string;
  user_id: number;
  email: string;
  role: string | null;
  is_superuser: boolean;
  employee_id?: number;
  mfa_required?: boolean;
  mfa_token?: string;
};
type SsoProvider = {
  id: number;
  name: string;
  domain_hint?: string;
  button_label?: string;
  provider_type: string;
};
function errorMessage(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: unknown } } })
    ?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  const { setTokens, setUser, isAuthenticated, isHydrated } = useAuthStore();
  const params = useMemo(
    () => new URLSearchParams(location.search),
    [location.search],
  );
  const destination = loginDestination(params.get("next"));
  const resetToken = params.get("token");
  const recoveryRequested = params.get("recover") === "1";
  const [view, setView] = useState<AuthView>(resetToken ? "reset" : "login");
  const [remember, setRemember] = useState(
    () => sessionStorage.getItem("suite-social-redirect-provider") === "google"
      ? sessionStorage.getItem("suite-social-redirect-remember") === "true"
      : localStorage.getItem("suite-remember-session") === "true",
  );
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [recoveryEmail, setRecoveryEmail] = useState("");
  const [sentEmail, setSentEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [method, setMethod] = useState<"totp" | "recovery">("totp");
  const [code, setCode] = useState("");
  const [ssoBusy, setSsoBusy] = useState(false);
  const handoffStarted = useRef(false);
  const redirectStarted = useRef(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const errorRef = useRef<HTMLParagraphElement>(null);
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<LoginForm>({ resolver: zodResolver(schema) });
  const email = watch("email");
  const branding = useQuery({
    queryKey: ["login-branding"],
    queryFn: () =>
      authApi.branding().then((r) => r.data as { company_name?: string }),
    staleTime: 60_000,
  });
  const providers = useQuery({
    queryKey: ["sso-providers"],
    queryFn: () => authApi.ssoProviders().then((r) => r.data as SsoProvider[]),
    staleTime: 600_000,
  });
  const firebase = useQuery({
    queryKey: ["firebase-login-config"],
    queryFn: () =>
      authApi
        .firebaseConfig()
        .then(
          (r) =>
            r.data as {
              enabled: boolean;
              modules: string[];
              firebase_config?: FirebaseOptions;
            },
        ),
    staleTime: 300_000,
  });
  const hintedProvider = providers.data?.find(
    (p) =>
      !!p.domain_hint &&
      p.domain_hint.toLowerCase() === email?.split("@")[1]?.toLowerCase(),
  );
  const sortedProviders = [...(providers.data || [])].sort(
    (a, b) =>
      Number(b.id === hintedProvider?.id) - Number(a.id === hintedProvider?.id),
  );
  const selectedModule = modules.find(
    (m) =>
      destination === m.homePath || destination.startsWith(m.homePath + "/"),
  );
  const continuation = `/continue?next=${encodeURIComponent(destination)}`;

  useEffect(() => {
    setView(resetToken ? "reset" : recoveryRequested ? "forgot" : "login");
    setError("");
  }, [resetToken, recoveryRequested]);
  useEffect(() => {
    heading.current?.focus();
  }, [view, mfaToken]);
  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  const finish = useCallback(
    (data: AuthResponse) => {
      if (data.mfa_required && data.mfa_token) {
        setMfaToken(data.mfa_token);
        setError("");
        return;
      }
      setRememberSession(remember);
      qc.clear();
      setTokens(data.access_token, data.refresh_token);
      setUser({
        id: data.user_id,
        email: data.email,
        role: data.role,
        is_superuser: data.is_superuser,
        employee_id: data.employee_id,
      });
      navigate(continuation, { replace: true });
    },
    [remember, qc, setTokens, setUser, navigate, continuation],
  );

  useEffect(() => {
    if (!firebase.data?.firebase_config || redirectStarted.current ||
        sessionStorage.getItem("suite-social-redirect-provider") !== "google") return;
    redirectStarted.current = true;
    setSsoBusy(true);
    import("@/services/firebaseLogin")
      .then(({ completeGoogleRedirect }) => completeGoogleRedirect(firebase.data!.firebase_config!))
      .then((response) => finish(response.data))
      .catch((err: unknown) => setError(errorMessage(err,
        err instanceof Error ? err.message : "Google sign-in could not be completed. Please try again.")))
      .finally(() => setSsoBusy(false));
  }, [firebase.data, finish]);

  useEffect(() => {
    const handoff = new URLSearchParams(location.hash.replace(/^#/, ""));
    const ssoCode = handoff.get("sso_code");
    const providerId = Number(handoff.get("provider"));
    const ssoError = params.get("sso_error");
    if (ssoError) {
      setError(
        "Company sign-in could not be completed. Please try again or contact your administrator.",
      );
      window.history.replaceState(
        {},
        "",
        location.pathname +
          (destination !== "/dashboard"
            ? `?next=${encodeURIComponent(destination)}`
            : ""),
      );
    }
    if (!ssoCode || providerId <= 0 || handoffStarted.current) return;
    handoffStarted.current = true;
    window.history.replaceState({}, "", location.pathname + location.search);
    setSsoBusy(true);
    authApi
      .completeSso(providerId, ssoCode)
      .then((r) => finish(r.data))
      .catch((err) =>
        setError(
          errorMessage(
            err,
            "Company sign-in could not be completed. Please start again.",
          ),
        ),
      )
      .finally(() => setSsoBusy(false));
  }, [
    location.hash,
    location.pathname,
    location.search,
    params,
    destination,
    finish,
  ]);

  function backToLogin() {
    setView("login");
    setError("");
    setMfaToken(null);
    setCode("");
    setNewPassword("");
    setConfirmPassword("");
    navigate(
      `/login${destination !== "/dashboard" ? `?next=${encodeURIComponent(destination)}` : ""}`,
      { replace: true },
    );
  }
  const login = useMutation({
    mutationFn: (data: LoginForm) => authApi.login(data.email, data.password),
    onSuccess: (r) => finish(r.data),
    onError: (err) =>
      setError(
        errorMessage(
          err,
          "Sign-in failed. Check your email and password and try again.",
        ),
      ),
  });
  const verify = useMutation({
    mutationFn: () => authApi.mfaVerify({ mfa_token: mfaToken, code, method }),
    onSuccess: (r) => finish(r.data),
    onError: (err) =>
      setError(
        errorMessage(err, "That code could not be verified. Please try again."),
      ),
  });
  const recovery = useMutation({
    mutationFn: () => authApi.forgotPassword(recoveryEmail),
    onSuccess: () => {
      setSentEmail(recoveryEmail);
      setView("sent");
    },
    onError: (err) =>
      setError(
        errorMessage(err, "Could not send a reset link. Please try again."),
      ),
  });
  const reset = useMutation({
    mutationFn: () => authApi.resetPassword(resetToken!, newPassword),
    onSuccess: () => {
      backToLogin();
      setSuccess("Password reset. Sign in with your new password.");
    },
    onError: (err) =>
      setError(
        errorMessage(
          err,
          "Could not reset the password. Your link may have expired; request a new one.",
        ),
      ),
  });
  async function socialSignIn(provider: "google" | "microsoft") {
    if (!firebase.data?.firebase_config) return;
    setError("");
    setSsoBusy(true);
    try {
      const { socialFirebaseLogin } = await import("@/services/firebaseLogin");
      const response = await socialFirebaseLogin(
        firebase.data.firebase_config,
        undefined,
        provider,
      );
      finish(response.data);
    } catch (err: unknown) {
      const code = (err as { code?: string }).code;
      setError(
        code === "auth/popup-closed-by-user"
          ? "The sign-in popup closed before sign-in completed. Please try again."
          : code === "auth/popup-blocked"
            ? "Allow the sign-in popup, then try again."
            : errorMessage(
                err,
                "Social sign-in could not be completed. Try your password or contact your administrator.",
              ),
      );
    } finally {
      setSsoBusy(false);
    }
  }
  const busy = login.isPending || verify.isPending || ssoBusy;
  const title = mfaToken
    ? "Verify your identity"
    : view === "forgot"
      ? "Recover access"
      : view === "sent"
        ? "Check your inbox"
        : view === "reset"
          ? "Reset password"
          : "Sign in to Business Suite";
  if (isHydrated && isAuthenticated && !resetToken)
    return <Navigate to={continuation} replace />;
  return (
    <div className="suite-login">
      <a className="suite-skip" href="#login-main">
        Skip to sign in
      </a>
      <header>
        <SuiteBrand />
        <Link to="/help"><Headphones size={21} />Help & support</Link>
      </header>
      <main id="login-main" className="suite-login-main">
        <section className="suite-login-intro" aria-labelledby="workspace-title">
          <h2 id="workspace-title">A connected workspace<br/>for your growing business</h2>
          <p>Unify your teams, customers, and workflows with<br className="suite-desktop-break"/> Business Suite &mdash; a secure, enterprise-grade platform<br className="suite-desktop-break"/> for sales, CRM, and business operations.</p>
          <ul className="suite-login-benefits">
            <li><span><UsersRound/></span><div><strong>Manage customers &amp; leads</strong><small>Build stronger relationships and pipeline</small></div></li>
            <li><span><Layers/></span><div><strong>Streamline business workflows</strong><small>From conversations to closed deals</small></div></li>
            <li><span><ShieldCheck/></span><div><strong>Enterprise-grade security</strong><small>Your data, your controls, always protected</small></div></li>
          </ul>
          <img className="suite-login-illustration" src="/images/suite-login-workspace.png" alt="" aria-hidden="true"/>
        </section>
        <section className="suite-login-card" aria-labelledby="login-title">
          <p className="suite-login-company">
            {branding.data?.company_name || "Your connected business workspace"}
          </p>
          <h1 id="login-title" ref={heading} tabIndex={-1}>
            {title}
          </h1>
          <p>
            {mfaToken
              ? method === "totp"
                ? "Enter the code from your authenticator app."
                : "Enter one of your saved recovery codes."
              : view === "login"
                ? "One account for all your authorized applications."
                : view === "forgot"
                  ? "We'll email a link to reset your password."
                  : view === "reset"
                    ? "Choose a new password. Your organization's password policy applies."
                    : `If an account exists for ${sentEmail}, a reset link has been sent. Check your spam folder too.`}
          </p>
          {view === "login" && !mfaToken && selectedModule && (
            <p className="suite-login-context">
              Continue to {selectedModule.name} after signing in.
            </p>
          )}
          {error && (
            <p
              ref={errorRef}
              tabIndex={-1}
              className="suite-login-error"
              id="login-error"
              role="alert"
            >
              {error}
            </p>
          )}
          {success && (
            <p className="suite-login-success" role="status">
              {success}
            </p>
          )}
          {mfaToken ? (
            <CompactForm
              onSubmit={(event) => {
                event.preventDefault();
                setError("");
                verify.mutate();
              }}
              className="suite-form"
            >
              <div className="suite-inline-actions">
                <button
                  type="button"
                  className="suite-secondary"
                  aria-pressed={method === "totp"}
                  onClick={() => {
                    setMethod("totp");
                    setCode("");
                    setError("");
                  }}
                >
                  Authenticator app
                </button>
                <button
                  type="button"
                  className="suite-secondary"
                  aria-pressed={method === "recovery"}
                  onClick={() => {
                    setMethod("recovery");
                    setCode("");
                    setError("");
                  }}
                >
                  Recovery code
                </button>
              </div>
              <label htmlFor="mfa-code">
                {method === "totp" ? "Authentication code" : "Recovery code"}
              </label>
              <input
                id="mfa-code"
                autoComplete="one-time-code"
                inputMode={method === "totp" ? "numeric" : "text"}
                pattern={method === "totp" ? "[0-9]{6}" : undefined}
                maxLength={method === "totp" ? 6 : 14}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                aria-invalid={!!error}
                aria-describedby={error ? "login-error" : undefined}
                required
              />
              <button className="suite-primary" disabled={busy}>
                {verify.isPending ? "Verifying…" : "Verify and continue"}
              </button>
              <button
                className="suite-login-link"
                type="button"
                onClick={backToLogin}
              >
                Back to login
              </button>
            </CompactForm>
          ) : view === "sent" ? (
            <div className="suite-form">
              <button
                className="suite-secondary"
                onClick={() => {
                  setError("");
                  setView("forgot");
                }}
              >
                Try another email
              </button>
              <button className="suite-primary" onClick={backToLogin}>
                Back to login
              </button>
            </div>
          ) : view === "forgot" ? (
            <CompactForm
              className="suite-form"
              onSubmit={(event) => {
                event.preventDefault();
                setError("");
                recovery.mutate();
              }}
            >
              <label htmlFor="recovery-email">Email address</label>
              <input
                id="recovery-email"
                type="email"
                autoComplete="email"
                value={recoveryEmail}
                onChange={(e) => setRecoveryEmail(e.target.value)}
                aria-invalid={!!error}
                aria-describedby={error ? "login-error" : undefined}
                required
              />
              <button className="suite-primary" disabled={recovery.isPending}>
                {recovery.isPending ? "Sending…" : "Send reset link"}
              </button>
              <button
                type="button"
                className="suite-login-link"
                onClick={backToLogin}
              >
                Back to login
              </button>
            </CompactForm>
          ) : view === "reset" ? (
            <CompactForm
              className="suite-form"
              onSubmit={(event) => {
                event.preventDefault();
                setError("");
                if (!resetToken) {
                  setError(
                    "Your reset link is missing. Please request a new link.",
                  );
                  return;
                }
                if (newPassword !== confirmPassword) {
                  setError("Passwords do not match.");
                  return;
                }
                reset.mutate();
              }}
            >
              <label htmlFor="new-password">New password</label>
              <input
                id="new-password"
                type="password"
                autoComplete="new-password"
                minLength={8}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                aria-invalid={!!error}
                aria-describedby={error ? "login-error" : undefined}
                required
              />
              <label htmlFor="confirm-password">Confirm new password</label>
              <input
                id="confirm-password"
                type="password"
                autoComplete="new-password"
                minLength={8}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                aria-invalid={!!error}
                aria-describedby={error ? "login-error" : undefined}
                required
              />
              <button className="suite-primary" disabled={reset.isPending}>
                {reset.isPending ? "Resetting…" : "Reset password"}
              </button>
              <button
                type="button"
                className="suite-login-link"
                onClick={backToLogin}
              >
                Back to login
              </button>
              <button
                type="button"
                className="suite-login-link"
                onClick={() => {
                  navigate("/login?recover=1", { replace: true });
                  setView("forgot");
                  setError("");
                }}
              >
                Request a new reset link
              </button>
            </CompactForm>
          ) : (
            <>
              <CompactForm
                className="suite-form"
                noValidate
                onSubmit={handleSubmit((data) => {
                  setError("");
                  setSuccess("");
                  login.mutate(data);
                })}
              >
                <label htmlFor="email">Email address</label>
                <div className="suite-email-field"><Mail size={20} aria-hidden="true"/><input
                  id="email"
                  type="email"
                  autoComplete="username"
                  placeholder="you@company.com"
                  aria-invalid={!!errors.email}
                  aria-describedby={errors.email ? "email-error" : undefined}
                  {...register("email")}
                /></div>
                {errors.email && (
                  <p
                    id="email-error"
                    className="suite-login-error"
                    role="alert"
                  >
                    {errors.email.message}
                  </p>
                )}
                <label htmlFor="password">Password</label>
                <div className="suite-password-field"><LockKeyhole size={20} aria-hidden="true"/>
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    placeholder="Enter your password"
                    aria-invalid={!!errors.password || !!error}
                    aria-describedby={
                      errors.password
                        ? "password-error"
                        : error
                          ? "login-error"
                          : undefined
                    }
                    {...register("password")}
                  />
                  <button
                    type="button"
                    aria-label={
                      showPassword ? "Hide password" : "Show password"
                    }
                    aria-pressed={showPassword}
                    onClick={() => setShowPassword((value) => !value)}
                  >
                    {showPassword ? <EyeOff size={19} /> : <Eye size={19} />}
                  </button>
                </div>
                {errors.password && (
                  <p
                    id="password-error"
                    className="suite-login-error"
                    role="alert"
                  >
                    {errors.password.message}
                  </p>
                )}
                <label className="suite-login-remember">
                  <input
                    type="checkbox"
                    checked={remember}
                    onChange={(e) => {
                      setRemember(e.target.checked);
                      setRememberSession(e.target.checked);
                    }}
                    aria-describedby="remember-help"
                  />
                  Keep me signed in
                </label>
                <small id="remember-help">
                  Use only on a trusted device. Leave unchecked on shared
                  devices.
                </small>
                <button className="suite-primary" disabled={busy}>
                  {busy ? <Loader2 size={20} className="animate-spin" /> : <LogIn size={22} />}
                  {busy ? "Signing in…" : "Sign in"}
                </button>
                <button
                  type="button"
                  className="suite-login-link"
                  onClick={() => {
                    setRecoveryEmail(email || "");
                    setView("forgot");
                    setError("");
                    setSuccess("");
                  }}
                >
                  Forgot password?
                </button>
              </CompactForm>
              {hintedProvider && (
                <p className="suite-login-context">
                  Your organization uses{" "}
                  {hintedProvider.button_label || hintedProvider.name}.
                </p>
              )}
              {(sortedProviders.length > 0 ||
                (firebase.data?.enabled &&
                  firebase.data.modules.length > 0)) && (
                <div className="suite-login-providers">
                  <p>Or continue with</p>
                  {sortedProviders.map((provider) => (
                    <button
                      key={provider.id}
                      className="suite-secondary"
                      disabled={busy}
                      onClick={() => {
                        setRememberSession(remember);
                        window.location.assign(
                          `${getApiBaseUrl()}/auth/sso/initiate/${provider.id}?next=${encodeURIComponent(`/login?next=${encodeURIComponent(destination)}`)}`,
                        );
                      }}
                    >
                      <ProviderMark provider={provider.provider_type}/>{provider.button_label ||
                        `Continue with ${provider.name}`}
                    </button>
                  ))}
                  {firebase.data?.enabled &&
                    firebase.data.modules.length > 0 &&
                    (["google", "microsoft"] as const)
                      .filter(
                        (provider) =>
                          !sortedProviders.some(
                            (p) =>
                              p.provider_type === provider ||
                              (provider === "microsoft" &&
                                p.provider_type === "azure_ad"),
                          ),
                      )
                      .map((provider) => (
                        <button
                          className="suite-secondary"
                          key={provider}
                          disabled={busy}
                          onClick={() => void socialSignIn(provider)}
                        >
                          <ProviderMark provider={provider}/>Continue with{" "}
                          {provider === "google" ? "Google" : "Microsoft"}
                        </button>
                      ))}
                </div>
              )}
              {(firebase.isPending || providers.isPending) && (
                <p role="status" className="suite-login-note">
                  Checking company sign-in options…
                </p>
              )}
              {(firebase.isError || providers.isError) && (
                <p className="suite-login-note" role="status">
                  Some sign-in options could not be loaded. You can use your
                  password or{" "}
                  <button
                    onClick={() => {
                      void firebase.refetch();
                      void providers.refetch();
                    }}
                  >
                    retry
                  </button>
                  .
                </p>
              )}
            </>
          )}
          <p className="suite-login-note">
            <ShieldCheck size={16} />
            Access follows your organization’s permissions.
          </p>
        </section>
        <footer>
          <Link to="/login?next=%2Fsettings">Company settings</Link>
          <Link to="/help">Help & support</Link>
          <span>© {new Date().getFullYear()} Business Suite</span>
        </footer>
      </main>
    </div>
  );
}

function ProviderMark({provider}:{provider:string}) {
  if(provider==="google")return <svg className="suite-provider-mark" viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285F4" d="M21.6 12.23c0-.71-.06-1.39-.18-2.05H12v3.88h5.38a4.6 4.6 0 0 1-2 3.02v2.51h3.24c1.9-1.75 2.98-4.33 2.98-7.36Z"/><path fill="#34A853" d="M12 22c2.7 0 4.96-.9 6.62-2.41l-3.24-2.51c-.9.6-2.06.96-3.38.96-2.6 0-4.8-1.76-5.59-4.12H3.07v2.59A10 10 0 0 0 12 22Z"/><path fill="#FBBC05" d="M6.41 13.92a6 6 0 0 1 0-3.84V7.49H3.07a10 10 0 0 0 0 9.02l3.34-2.59Z"/><path fill="#EA4335" d="M12 5.96c1.47 0 2.79.51 3.83 1.51l2.87-2.87A9.64 9.64 0 0 0 12 2a10 10 0 0 0-8.93 5.49l3.34 2.59C7.2 7.72 9.4 5.96 12 5.96Z"/></svg>;
  if(["microsoft","azure_ad"].includes(provider))return <svg className="suite-provider-mark" viewBox="0 0 24 24" aria-hidden="true"><path fill="#f25022" d="M1 1h10v10H1z"/><path fill="#7fba00" d="M13 1h10v10H13z"/><path fill="#00a4ef" d="M1 13h10v10H1z"/><path fill="#ffb900" d="M13 13h10v10H13z"/></svg>;
  return <ShieldCheck size={20}/>;
}
