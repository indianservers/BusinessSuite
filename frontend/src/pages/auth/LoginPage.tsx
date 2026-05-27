import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { useMutation, useQuery } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { CheckCircle2, Eye, EyeOff, Loader2, LockKeyhole, ShieldCheck, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuthStore } from "@/store/authStore";
import { authApi } from "@/services/api";
import { toast } from "@/hooks/use-toast";
import { getApiBaseUrl } from "@/config/runtime";
import { getDefaultPathForUser } from "@/lib/products";

const loginSchema = z.object({
  email: z.string().email("Valid email required"),
  password: z.string().min(1, "Password required"),
});

type LoginForm = z.infer<typeof loginSchema>;

const moduleLogins = {
  hrms: {
    product: "AI HRMS",
    authModule: "hrms",
    tagline: "Human Resource Management",
    description: "Enter your HRMS credentials",
    afterLogin: "/hrms",
    accent: "blue",
    demoLogins: [
      { label: "HRMS Admin", email: "admin@aihrms.com", password: "Admin@123456", description: "HRMS configuration and system access" },
      { label: "HR Manager", email: "hr@aihrms.com", password: "HR@123456", description: "Employees, leave, payroll, recruitment, HR operations" },
      { label: "Manager", email: "manager@aihrms.com", password: "Manager@123456", description: "Team leave, attendance, performance, reports" },
      { label: "Employee", email: "employee@aihrms.com", password: "Employee@123456", description: "Self-service attendance, leave, payslip, helpdesk" },
    ],
  },
  crm: {
    product: "VyaparaCRM",
    authModule: "crm",
    tagline: "Customer Relationship Management",
    description: "Enter your CRM credentials",
    afterLogin: "/crm",
    accent: "emerald",
    demoLogins: [
      { label: "CRM Admin", email: "admin@vyaparacrm.com", password: "Password@123", description: "CRM users, settings, reports, automation" },
      { label: "Sales Manager", email: "manager@vyaparacrm.com", password: "Password@123", description: "Pipeline, deals, forecasts, sales team" },
      { label: "Sales Executive", email: "executive@vyaparacrm.com", password: "Password@123", description: "Leads, contacts, activities, assigned deals" },
      { label: "Support Agent", email: "support@vyaparacrm.com", password: "Password@123", description: "Customer records and support tickets" },
      { label: "Marketing", email: "marketing@vyaparacrm.com", password: "Password@123", description: "Campaigns, imports, segments, performance" },
    ],
  },
  project_management: {
    product: "KaryaFlow",
    authModule: "project_management",
    tagline: "Project Management Software",
    description: "Enter your PMS credentials",
    afterLogin: "/pms",
    accent: "violet",
    demoLogins: [
      { label: "PMS Admin", email: "admin@karyaflow.com", password: "Password@123", description: "Project settings, users, workflows, reports" },
      { label: "Project Manager", email: "manager@karyaflow.com", password: "Password@123", description: "Projects, tasks, milestones, approvals" },
      { label: "Team Member", email: "member@karyaflow.com", password: "Password@123", description: "Assigned work, board updates, files, time logs" },
      { label: "Client", email: "client@karyaflow.com", password: "Password@123", description: "Client portal, deliverables, approvals" },
    ],
  },
} as const;

const loginThemes = {
  hrms: {
    page: "from-slate-900 via-blue-950 to-slate-900",
    glow: "from-blue-900/20",
    logo: "bg-blue-600 shadow-blue-500/25",
    text: "text-blue-200",
    textSoft: "text-blue-200/70",
    textMuted: "text-blue-200/60",
    button: "bg-blue-600 hover:bg-blue-500 shadow-blue-500/25",
    ring: "focus-visible:ring-blue-400",
  },
  crm: {
    page: "from-emerald-950 via-teal-950 to-slate-950",
    glow: "from-emerald-700/20",
    logo: "bg-emerald-600 shadow-emerald-500/25",
    text: "text-emerald-100",
    textSoft: "text-emerald-100/70",
    textMuted: "text-emerald-100/60",
    button: "bg-emerald-600 hover:bg-emerald-500 shadow-emerald-500/25",
    ring: "focus-visible:ring-emerald-400",
  },
  project_management: {
    page: "from-violet-950 via-indigo-950 to-slate-950",
    glow: "from-violet-700/20",
    logo: "bg-violet-600 shadow-violet-500/25",
    text: "text-violet-100",
    textSoft: "text-violet-100/70",
    textMuted: "text-violet-100/60",
    button: "bg-violet-600 hover:bg-violet-500 shadow-violet-500/25",
    ring: "focus-visible:ring-violet-400",
  },
} as const;

function getLoginModule(pathname: string): keyof typeof moduleLogins {
  if (pathname.startsWith("/crm")) return "crm";
  if (pathname.startsWith("/pms")) return "project_management";
  return "hrms";
}

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const loginModule = getLoginModule(location.pathname);
  const loginConfig = moduleLogins[loginModule];
  const loginTheme = loginThemes[loginModule];
  const { setTokens, setUser } = useAuthStore();
  const [showPassword, setShowPassword] = useState(false);
  const [loginPhase, setLoginPhase] = useState<"credentials" | "mfa">("credentials");
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [mfaMethod, setMfaMethod] = useState<"totp" | "recovery">("totp");
  const [mfaCode, setMfaCode] = useState("");
  const [inlineError, setInlineError] = useState("");

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) });
  const emailValue = watch("email");
  const apiBaseUrl = getApiBaseUrl();

  const getPostLoginPath = useCallback((role?: string | null, isSuperuser = false) => (
    loginModule === "hrms" ? getDefaultPathForUser(role, isSuperuser) : loginConfig.afterLogin
  ), [loginConfig.afterLogin, loginModule]);

  const { data: ssoProviders } = useQuery({
    queryKey: ["sso-providers"],
    queryFn: () => authApi.ssoProviders().then((r) => r.data as SsoProvider[]),
    staleTime: 10 * 60 * 1000,
  });
  const hintedProvider = useMemo(() => {
    const domain = emailValue?.split("@")[1]?.toLowerCase();
    if (!domain) return null;
    return (ssoProviders || []).find((provider) => provider.domain_hint?.toLowerCase() === domain) || null;
  }, [emailValue, ssoProviders]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const accessToken = params.get("access_token");
    const refreshToken = params.get("refresh_token");
    const ssoError = params.get("sso_error");
    if (accessToken && refreshToken) {
      window.history.replaceState({}, "", window.location.pathname);
      setTokens(accessToken, refreshToken);
      authApi.me().then((res) => {
        const roleName = res.data.role?.name || null;
        setUser({
          id: res.data.id,
          email: res.data.email,
          role: roleName,
          is_superuser: res.data.is_superuser,
          employee_id: res.data.employee_id,
        });
        navigate(getPostLoginPath(roleName, res.data.is_superuser));
      });
    }
    if (ssoError) {
      window.history.replaceState({}, "", window.location.pathname);
      setInlineError(ssoError.replace(/_/g, " "));
    }
  }, [getPostLoginPath, navigate, setTokens, setUser]);

  const onSubmit = async (data: LoginForm) => {
    try {
      const res = await authApi.login(data.email, data.password, loginConfig.authModule);
      if (res.data.mfa_required) {
        setMfaToken(res.data.mfa_token);
        setLoginPhase("mfa");
        setInlineError("");
        return;
      }
      const { access_token, refresh_token, user_id, email, role, is_superuser, employee_id } = res.data;

      setTokens(access_token, refresh_token);
      setUser({ id: user_id, email, role, is_superuser, employee_id });

      toast({ title: "Welcome back!", variant: "default" });
      navigate(getPostLoginPath(role, is_superuser));
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Invalid credentials";
      toast({ title: "Login failed", description: message, variant: "destructive" });
    }
  };

  const verifyMfa = useMutation({
    mutationFn: () => authApi.mfaVerify({ mfa_token: mfaToken, code: mfaCode, method: mfaMethod }),
    onSuccess: (res) => {
      const { access_token, refresh_token, user_id, email, role, is_superuser, employee_id } = res.data;
      setTokens(access_token, refresh_token);
      setUser({ id: user_id, email, role, is_superuser, employee_id });
      navigate(getPostLoginPath(role, is_superuser));
    },
    onError: (err: unknown) => {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Incorrect code";
      setInlineError(message);
    },
  });

  const ssoUrl = (provider: SsoProvider) => `${apiBaseUrl}/auth/sso/initiate/${provider.id}?next=${encodeURIComponent(location.pathname)}`;

  return (
    <div className={`min-h-screen flex items-center justify-center bg-gradient-to-br ${loginTheme.page} p-4`}>
      {/* Background pattern */}
      <div className={`absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] ${loginTheme.glow} via-transparent to-transparent`} />

      <div className="relative w-full max-w-md space-y-6">
        {/* Logo */}
        <div className="text-center space-y-2">
          <div className={`inline-flex h-16 w-16 items-center justify-center rounded-2xl shadow-lg ${loginTheme.logo} mx-auto`}>
            <Sparkles className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white">{loginConfig.product}</h1>
          <p className={`${loginTheme.textSoft} text-sm`}>{loginConfig.tagline}</p>
        </div>

        {/* Card */}
        <Card className="border-white/10 bg-white/5 backdrop-blur-xl shadow-2xl">
          <CardHeader className="space-y-1 pb-4">
            <CardTitle className="text-white text-xl">Sign in</CardTitle>
            <CardDescription className={loginTheme.textMuted}>
              {loginConfig.description}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loginPhase === "mfa" ? (
              <div className="space-y-4">
                <div className="flex items-center gap-3 rounded-lg border border-blue-500/20 bg-blue-500/10 p-3">
                  <LockKeyhole className="h-5 w-5 text-blue-200" />
                  <div>
                    <p className="text-sm font-semibold text-white">Two-Factor Authentication</p>
                    <p className="text-xs text-blue-200/60">Enter the code from your authenticator app</p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <Button type="button" variant={mfaMethod === "totp" ? "default" : "outline"} onClick={() => setMfaMethod("totp")}>Authenticator App</Button>
                  <Button type="button" variant={mfaMethod === "recovery" ? "default" : "outline"} onClick={() => setMfaMethod("recovery")}>Recovery Code</Button>
                </div>
                <Input
                  value={mfaCode}
                  onChange={(e) => setMfaCode(e.target.value)}
                  maxLength={mfaMethod === "totp" ? 6 : 14}
                  placeholder={mfaMethod === "totp" ? "123456" : "XXXX-XXXX-XXXX"}
                  className="bg-white/10 border-white/20 text-white placeholder:text-white/30"
                />
                {inlineError && <p className="text-xs text-red-400">{inlineError}</p>}
                <Button className={`h-11 w-full text-white ${loginTheme.button}`} disabled={!mfaToken || !mfaCode || verifyMfa.isPending} onClick={() => verifyMfa.mutate()}>
                  {verifyMfa.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Verify
                </Button>
                <button type="button" className="w-full text-xs text-blue-200/70 hover:text-white" onClick={() => { setLoginPhase("credentials"); setMfaToken(null); setMfaCode(""); }}>
                  Back to login
                </button>
              </div>
            ) : (
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email" className={loginTheme.text}>
                  Email address
                </Label>
                <Input
                  id="email"
                  type="email"
                  placeholder={loginConfig.demoLogins[0].email}
                  className={`bg-white/10 border-white/20 text-white placeholder:text-white/30 ${loginTheme.ring}`}
                  {...register("email")}
                />
                {errors.email && (
                  <p className="text-xs text-red-400">{errors.email.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className={loginTheme.text}>
                  Password
                </Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="Enter your password"
                    className={`bg-white/10 border-white/20 text-white placeholder:text-white/30 ${loginTheme.ring} pr-10`}
                    {...register("password")}
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-white/50 hover:text-white"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.password && (
                  <p className="text-xs text-red-400">{errors.password.message}</p>
                )}
              </div>

              <Button
                type="submit"
                className={`w-full text-white font-semibold shadow-lg ${loginTheme.button} h-11`}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : null}
                {isSubmitting ? "Signing in..." : "Sign in"}
              </Button>
              {hintedProvider && (
                <div className="rounded-lg border border-blue-500/20 bg-blue-500/10 p-3 text-xs text-blue-100">
                  Your organization uses SSO. Sign in with {hintedProvider.button_label || hintedProvider.name} instead.
                  <Button type="button" variant="outline" size="sm" className="mt-2 w-full" onClick={() => { window.location.href = ssoUrl(hintedProvider); }}>Continue with SSO</Button>
                </div>
              )}
            </form>
            )}

            {loginPhase === "credentials" && !!ssoProviders?.length && (
              <div className="mt-4 space-y-3">
                <div className="flex items-center gap-3 text-xs text-blue-200/50"><span className="h-px flex-1 bg-white/10" />or continue with<span className="h-px flex-1 bg-white/10" /></div>
                {ssoProviders.map((provider) => (
                  <Button key={provider.id} type="button" variant="outline" className="w-full border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => { window.location.href = ssoUrl(provider); }}>
                    <ProviderIcon icon={provider.button_icon} />
                    {provider.button_label || `Sign in with ${provider.name}`}
                  </Button>
                ))}
              </div>
            )}
            {inlineError && loginPhase === "credentials" && <p className="mt-3 text-xs text-red-400">{inlineError}</p>}

            <div className="mt-4 space-y-2 rounded-lg border border-blue-500/20 bg-blue-500/10 p-3">
              <p className="text-xs font-medium text-blue-200/80">Role logins</p>
              {loginConfig.demoLogins.map((login) => (
                <button
                  key={login.email}
                  type="button"
                  className="w-full rounded-md border border-white/10 bg-white/5 p-2 text-left transition hover:bg-white/10"
                  onClick={() => {
                    setValue("email", login.email, { shouldValidate: true });
                    setValue("password", login.password, { shouldValidate: true });
                  }}
                >
                  <span className="flex items-center justify-between gap-3">
                    <span className="text-xs font-semibold text-white">{login.label}</span>
                    <span className="text-[11px] text-blue-200/60">{login.email}</span>
                  </span>
                  <span className="mt-1 flex items-center gap-1 text-[11px] text-emerald-200/80">
                    <CheckCircle2 className="h-3 w-3" />
                    Credentials auto-filled
                  </span>
                  <span className="mt-1 block text-[11px] text-blue-200/45">{login.description}</span>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        <p className="text-center text-blue-200/40 text-xs">
          &copy; {new Date().getFullYear()} {loginConfig.product}. All rights reserved.
        </p>
      </div>
    </div>
  );
}

interface SsoProvider {
  id: number;
  name: string;
  provider_type: string;
  button_label?: string;
  button_icon?: string;
  domain_hint?: string;
}

function ProviderIcon({ icon }: { icon?: string }) {
  if (icon === "google") {
    return <span className="mr-2 inline-flex h-4 w-4 items-center justify-center rounded bg-white text-xs font-bold text-blue-600">G</span>;
  }
  if (icon === "microsoft") {
    return <span className="mr-2 grid h-4 w-4 grid-cols-2 gap-0.5"><i className="bg-red-500" /><i className="bg-green-500" /><i className="bg-blue-500" /><i className="bg-yellow-500" /></span>;
  }
  return <ShieldCheck className="mr-2 h-4 w-4" />;
}
