import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  NavLink,
  Link,
  Navigate,
  Route,
  Routes,
  useNavigate,
  useLocation,
} from "react-router-dom";
import {
  GraduationCap,
  LayoutDashboard,
  SquareCheck,
  ClipboardList,
  Upload,
  FileText,
  BarChart3,
  Star,
  BookOpen,
  Trophy,
  CalendarDays,
  UserRound,
  CircleHelp,
  LogOut,
  Search,
  Bell,
  Menu,
  X,
  ChevronRight,
  ArrowRight,
  LockKeyhole,
  Sparkles,
  ExternalLink,
  AlertCircle,
} from "lucide-react";
import { hub, request, send, token, setToken } from "./api";
import { Context, Data, Logo, Avatar } from "./ui";
import {
  Dashboard,
  Tasks,
  TaskDetail,
  SubmitWork,
  DailyReport,
  Reviews,
} from "./WorkPages";
import {
  Analytics,
  Learning,
  Course,
  Leaderboard,
  Attendance,
} from "./GrowthPages";
import { Profile, Certificates, Support } from "./AccountPages";
import "./style.css";
import { hrmsLoginUrl } from "./config";
import { ApplicationPage, ApplicationStatus } from "./ApplicationPage";
const nav = [
  ["/", "Dashboard", LayoutDashboard],
  ["/tasks", "My Tasks", SquareCheck],
  ["/task", "Task Details", ClipboardList],
  ["/submit", "Submit Work", Upload],
  ["/report", "Daily Report", FileText],
  ["/analytics", "Analytics", BarChart3],
  ["/reviews", "Reviews", Star],
  ["/learning", "Learning", BookOpen],
  ["/leaderboard", "Leaderboard", Trophy],
  ["/attendance", "Attendance", CalendarDays],
  ["/profile", "Profile", UserRound],
  ["/certificates", "Certificates", GraduationCap],
  ["/support", "Help & Support", CircleHelp],
] as const;
function Login({ onLogin }: { onLogin: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfa, setMfa] = useState("");
  const [code, setCode] = useState("");
  const [method, setMethod] = useState("totp");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div className="login">
      <div className="login-story">
        <Logo />
        <div>
          <span className="eyebrow">YOUR NEXT CHAPTER STARTS HERE</span>
          <h1>
            Small steps.
            <br />
            Big possibilities.
          </h1>
          <p>
            Learn something new. Build something meaningful.
            <br />
            Make your internship count.
          </p>
          <div className="login-art">
            <GraduationCap size={150} />
            <Sparkles size={50} />
            <Trophy size={100} />
          </div>
        </div>
        <small>Learn ・ Grow ・ Build</small>
      </div>
      <main className="login-form">
        <div className="mobile-logo">
          <Logo />
        </div>
        <div className="login-card">
          <span className="icon-small">
            <GraduationCap size={26} />
          </span>
          <h1>{mfa ? "One more step" : "Welcome to Interns Hub"}</h1>
          <p>
            {mfa
              ? "Verify your account to continue."
              : "Your internship journey, all in one place."}
          </p>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              try {
                const result = await request(
                  mfa ? "/auth/mfa/verify" : "/auth/login",
                  send(
                    "POST",
                    mfa
                      ? { mfa_token: mfa, code, method }
                      : { email, password, module: "interns_hub" },
                  ),
                );
                if (result.mfa_required) {
                  setMfa(result.mfa_token);
                  return;
                }
                setToken(result.access_token, result.refresh_token);
                onLogin();
              } catch (error) {
                setError((error as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            {mfa ? (
              <>
                <label>
                  Verification method
                  <select
                    value={method}
                    onChange={(e) => setMethod(e.target.value)}
                  >
                    <option value="totp">Authenticator code</option>
                    <option value="recovery">Recovery code</option>
                  </select>
                </label>
                <label>
                  Verification code
                  <input
                    autoComplete="one-time-code"
                    required
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                  />
                </label>
              </>
            ) : (
              <>
                <label>
                  Work email
                  <input
                    type="email"
                    autoComplete="username"
                    placeholder="you@company.com"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </label>
                <label>
                  Password
                  <input
                    type="password"
                    autoComplete="current-password"
                    placeholder="Enter your password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </label>
              </>
            )}
            {error && (
              <p className="error" role="alert">
                <AlertCircle size={16} />
                {error}
              </p>
            )}
            <button disabled={busy} className="button full">
              {busy
                ? "Signing in…"
                : mfa
                  ? "Verify & Sign In"
                  : "Sign In to Interns Hub"}
              <ArrowRight size={18} />
            </button>
          </form>
          <p className="login-note">
            <LockKeyhole size={15} />
            For active interns with an HRMS-linked account.
          </p>
          <p className="muted">
            New here? <Link to="/apply">Apply for an internship</Link> ·{" "}
            <Link to="/application-status">Check application status</Link>
          </p>
          <div className="login-divider" />
          <p className="muted">Need access? Contact your HRMS administrator.</p>
          <a
            className="admin-login"
            href={
              import.meta.env.VITE_HRMS_URL ||
              "http://localhost:5173/hrms/login"
            }
          >
            HRMS Admin Login <ExternalLink size={14} />
          </a>
        </div>
      </main>
    </div>
  );
}
function Portal({ logout }: { logout: () => void }) {
  const [data, setData] = useState<Data>();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [menu, setMenu] = useState(false);
  const [search, setSearch] = useState("");
  const navigate = useNavigate();
  const location = useLocation();
  async function refresh() {
    const keys = [
      "me",
      "overview",
      "tasks",
      "submissions",
      "reports",
      "attendance",
      "learning",
      "leaderboard",
      "certificates",
      "support",
    ];
    const values = await Promise.all(keys.map((key) => hub(`/${key}`)));
    setData(Object.fromEntries(keys.map((key, i) => [key, values[i]])) as Data);
  }
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    let cancelled = false;
    const refreshVisible = async () => {
      const keys = location.pathname === '/certificates' ? ['certificates', 'overview'] : location.pathname === '/reviews' ? ['submissions', 'overview'] : ['tasks', 'submissions', 'overview'];
      try {
        const values = await Promise.all(keys.map(key => hub('/' + key)));
        if (!cancelled) setData(previous => previous ? {...previous, ...Object.fromEntries(keys.map((key,i)=>[key,values[i]]))} as Data : previous);
      } catch { /* The existing session-expiry handler handles revoked access. */ }
    };
    if (data) refreshVisible();
    window.addEventListener('focus', refreshVisible);
    return () => { cancelled = true; window.removeEventListener('focus', refreshVisible); };
  }, [location.pathname]);
  useEffect(() => {
    setMenu(false);
    window.scrollTo(0, 0);
    document.title = `${nav.find((n) => n[0] === location.pathname)?.[1] || "InternHub"} · Interns Hub`;
  }, [location.pathname]);
  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(""), 5000);
    return () => clearTimeout(t);
  }, [notice]);
  async function act(work: () => Promise<any>, message: string) {
    setBusy(true);
    try {
      await work();
      await refresh();
      setNotice(message);
      return true;
    } catch (e) {
      setNotice((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }
  if (error)
    return (
      <div className="fatal">
        <Logo />
        <h1>Unable to open InternHub</h1>
        <p role="alert">{error}</p>
        <button className="button" onClick={logout}>
          Back to Sign In
        </button>
        <button
          className="button outline"
          onClick={() => {
            setError("");
            refresh().catch((e) => setError(e.message));
          }}
        >
          Try Again
        </button>
      </div>
    );
  if (!data)
    return (
      <div className="loading">
        <Logo />
        <span className="spinner" />
        <p>Connecting to your internship…</p>
      </div>
    );
  const name = `${data.me.first_name} ${data.me.last_name}`;
  return (
    <Context.Provider value={{ data, refresh, act, busy }}>
      <div className="app">
        {menu && (
          <button
            className="scrim"
            aria-label="Close menu"
            onClick={() => setMenu(false)}
          />
        )}
        <aside className={menu ? "sidebar open" : "sidebar"}>
          <Logo />
          <button
            className="close-menu"
            aria-label="Close navigation"
            onClick={() => setMenu(false)}
          >
            <X />
          </button>
          <nav aria-label="Main navigation">
            {nav.map(([to, label, Icon]) => (
              <NavLink key={to} to={to} end={to === "/"}>
                <Icon size={21} />
                <span>{label}</span>
              </NavLink>
            ))}
          </nav>
          <button
            className="logout"
            onClick={async () => {
              await hub("/logout", send("POST")).catch(() => {});
              logout();
            }}
          >
            <LogOut size={21} />
            Logout
          </button>
        </aside>
        <div className="workspace">
          <header className="topbar">
            <button
              className="menu-button"
              aria-label="Open navigation"
              onClick={() => setMenu(true)}
            >
              <Menu />
            </button>
            <form
              className="search"
              onSubmit={(e) => {
                e.preventDefault();
                navigate(`/tasks?q=${encodeURIComponent(search)}`);
              }}
            >
              <Search size={20} />
              <input
                aria-label="Search tasks and resources"
                placeholder="Search tasks, resources, or anything…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <kbd>↵</kbd>
            </form>
            <button
              className="notification"
              aria-label="View reviews and notifications"
              onClick={() => navigate("/reviews")}
            >
              <Bell size={22} />
              {data.submissions.some((s) => s.feedback) && <span />}
            </button>
            <Link className="top-profile" to="/profile">
              <Avatar name={name} photo={data.me.profile_photo_url} />
              <div>
                <b>{name}</b>
                <small>Intern</small>
              </div>
              <ChevronRight size={16} />
            </Link>
          </header>
          <main className="content">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/tasks" element={<Tasks />} />
              <Route path="/task" element={<TaskDetail />} />
              <Route path="/tasks/:id" element={<TaskDetail />} />
              <Route path="/submit" element={<SubmitWork />} />
              <Route path="/submit/:id" element={<SubmitWork />} />
              <Route path="/report" element={<DailyReport />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/reviews" element={<Reviews />} />
              <Route path="/learning" element={<Learning />} />
              <Route path="/learning/:id" element={<Course />} />
              <Route path="/leaderboard" element={<Leaderboard />} />
              <Route path="/attendance" element={<Attendance />} />
              <Route path="/profile" element={<Profile />} />
              <Route path="/certificates" element={<Certificates />} />
              <Route path="/support" element={<Support />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
        {notice && (
          <div className="toast" role="status">
            {notice}
            <button
              aria-label="Dismiss notification"
              onClick={() => setNotice("")}
            >
              <X size={16} />
            </button>
          </div>
        )}
      </div>
    </Context.Provider>
  );
}
function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const [authenticated, setAuthenticated] = useState(!!token());
  useEffect(() => {
    if (location.pathname === "/login")
      document.title = "Intern Login · Interns Hub";
    if (location.pathname === "/application-status")
      document.title = "Application Status · Interns Hub";
  }, [location.pathname]);
  function logout() {
    setToken(null);
    setAuthenticated(false);
  }
  useEffect(() => {
    window.addEventListener("internhub:expired", logout);
    return () => window.removeEventListener("internhub:expired", logout);
  }, []);
  if (location.pathname === "/apply") return <ApplicationPage />;
  if (location.pathname === "/application-status") return <ApplicationStatus />;
  return authenticated ? (
    <Portal logout={logout} />
  ) : (
    <Routes>
      <Route
        path="/login"
        element={
          <Login
            onLogin={() => {
              setAuthenticated(true);
              navigate("/");
            }}
          />
        }
      />
      <Route path="*" element={<Navigate to="/apply" replace />} />
    </Routes>
  );
}
createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <App />
  </BrowserRouter>,
);
