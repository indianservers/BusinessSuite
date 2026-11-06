import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import { LayoutDashboard, Users, Building2, ClipboardList, Mail, BarChart3, Settings, Wallet, Activity, UserCog, LogOut, Search, Star } from "lucide-react";
import { platformApi as api, platformTokenKey } from "@/services/platform-api";
import { OwnerContext, useData, useOwner, message, Loading, Alert, Badge, date, type Data } from "./shared";
import Signups from "./Signups";
import Customers from "./Customers";
import Reports from "./Reports";
import Databases from "./Databases";
import { Team, Records, Plans, SettingsPage, Operations, Profile, Audit } from "./Workspaces";
import "./platform.css";
const pages = [
    ["overview", "Overview", LayoutDashboard, "reports.read"], ["signups", "Signups", Users, "signup.read"],
    ["customers", "Clients", Building2, "tenant.read"], ["plans", "Plans & billing", Wallet, "billing.read"],
    ["team", "Team", UserCog, "staff.manage"], ["tasks", "Tasks", ClipboardList, ""],
    ["databases", "Company databases", Building2, "settings.manage"],
    ["communications", "Communications", Mail, "signup.review"], ["reports", "Reports", BarChart3, "reports.read"],
    ["operations", "Operations", Activity, "tools.manage"], ["audit", "Activity log", Activity, "audit.read"],
    ["settings", "Settings", Settings, "settings.manage"], ["profile", "My account", UserCog, ""]
] as const;
function Login() {
    const navigate = useNavigate();
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);
    const [reset, setReset] = useState(false);
    const [notice, setNotice] = useState("");
    return <div className="po-login"><section className="po-panel"><p className="po-muted">INDIAN SERVERS</p><h1>Platform Owner Portal</h1><p>Manage ERP enquiries, customer subscriptions and your operator team.</p><form className="po-form" onSubmit={async (e) => { e.preventDefault(); setBusy(true); setError(""); const f = new FormData(e.currentTarget); try {
        if (reset) {
            const { data } = await api.post("/platform/password-reset", { email: f.get("email") });
            setNotice(data.message);
        }
        else {
            const { data } = await api.post("/auth/platform/login", { email: f.get("email"), password: f.get("password") });
            sessionStorage.setItem(platformTokenKey, data.access_token);
            navigate("/platform", { replace: true });
        }
    }
    catch (err) {
        setError(message(err));
    }
    finally {
        setBusy(false);
    } }}>
    <label>Platform email<input name="email" type="email" autoComplete="username" required/></label>{!reset && <label>Password<input name="password" type="password" autoComplete="current-password" required/></label>}<Alert error={error}/>{notice && <div role="status" className="po-notice">{notice}</div>}<button className="po-primary" disabled={busy}>{busy ? "Please wait…" : reset ? "Prepare reset link" : "Sign in as platform owner"}</button><button type="button" onClick={() => { setReset(!reset); setError(""); setNotice(""); }}>{reset ? "Back to sign in" : "Forgot password?"}</button></form><small>Independent Indian Servers operator accounts. Client App Super Admin credentials do not grant access here.</small></section></div>;
}
function PublicLink() {
    const { token } = useParams();
    const result = useData<Data>(`/platform/public/${token}`);
    const [error, setError] = useState("");
    const [done, setDone] = useState("");
    const [busy, setBusy] = useState(false);
    const r = result.data;
    async function act(action: string, values: Data = {}) { setBusy(true); setError(""); try {
        const { data } = await api.post(`/platform/public/${token}`, { action, values });
        setDone(data.message);
    }
    catch (e) {
        setError(message(e));
    }
    finally {
        setBusy(false);
    } }
    return <main className="po-public"><p>INDIAN SERVERS · PRIVATE LINK</p><section className="po-panel"><Loading busy={result.busy} error={result.error}/>{r && <><h1>{r.title}</h1><p>{r.applicant || r.customer || r.email}</p><small>Expires {date(r.expires_at)}</small>{r.message && <div className="po-notice">{r.message}</div>}{done ? <div role="status" className="po-notice">{done}</div> : <>
    {r.kind === "tracking" && <><p>Status: <Badge>{r.status}</Badge></p>{["pending", "under_review", "awaiting_applicant"].includes(r.status) && <button disabled={busy} onClick={() => { if (window.confirm("Withdraw this trial request?"))
                void act("withdraw"); }}>Withdraw application</button>}</>}
    {r.kind === "correction" && <form className="po-form" onSubmit={e => { e.preventDefault(); const f = new FormData(e.currentTarget); void act("correct", Object.fromEntries(f.entries())); }}>{Object.entries(r.fields as Data).map(([key, value]) => <label key={key}>{key.split("_").join(" ")}<input name={key} defaultValue={value || ""} type={key === "email" ? "email" : "text"} required={key !== "company_name" && key !== "notes"}/></label>)}<button disabled={busy} className="po-primary">Save corrections</button></form>}
    {["staff_invitation", "password_reset"].includes(r.kind) && <form className="po-form" onSubmit={e => { e.preventDefault(); const f = new FormData(e.currentTarget); if (f.get("password") !== f.get("confirm")) {
                setError("Passwords do not match");
                return;
            } void act("activate", { password: f.get("password") }); }}><label>New password<input type="password" name="password" minLength={12} maxLength={72} autoComplete="new-password" required/></label><label>Confirm password<input type="password" name="confirm" minLength={12} maxLength={72} autoComplete="new-password" required/></label><button className="po-primary" disabled={busy}>Save password</button></form>}
    {["transfer_consent", "support_consent"].includes(r.kind) && <div className="po-actions"><button className="po-primary" disabled={busy} onClick={() => void act("approve")}>Confirm request</button>{r.kind === "support_consent" && <button disabled={busy} onClick={() => void act("decline")}>Decline</button>}</div>}</>}<Alert error={error}/></>}</section></main>;
}
function Shell() {
    const location = useLocation();
    const navigate = useNavigate();
    const owner = useData<Data>("/platform/me");
    const [search, setSearch] = useState("");
    const [matches, setMatches] = useState<Data>();
    const [error, setError] = useState("");
    useEffect(() => { if (search.trim().length < 2) {
        setMatches(undefined);
        return;
    } const controller = new AbortController(); const timer = setTimeout(() => api.get("/platform/search", { params: { q: search }, signal: controller.signal }).then(r => setMatches(r.data)).catch(() => { }), 250); return () => { clearTimeout(timer); controller.abort(); }; }, [search]);
    useEffect(() => { let last = Date.now(); const activity = () => { last = Date.now(); }; const timer = setInterval(() => { const minutes = owner.data?.settings?.idle_minutes || 60; if (Date.now() - last > minutes * 60000) {
        sessionStorage.removeItem(platformTokenKey);
        window.location.assign("/platform/login");
    } }, 30000); window.addEventListener("pointerdown", activity); window.addEventListener("keydown", activity); return () => { clearInterval(timer); window.removeEventListener("pointerdown", activity); window.removeEventListener("keydown", activity); }; }, [owner.data?.settings?.idle_minutes]);
    if (!sessionStorage.getItem(platformTokenKey))
        return <Navigate to="/platform/login" replace/>;
    if (!owner.data)
        return <main className="po-content"><Loading busy={owner.busy} error={owner.error}/><button onClick={owner.refresh}>Retry</button></main>;
    const me = owner.data;
    const visible = pages.filter(p => !p[3] || me.permissions.includes(p[3])).sort((a, b) => Number((me.preferences.favorites || []).includes(b[0])) - Number((me.preferences.favorites || []).includes(a[0])));
    const first = visible[0]?.[0] || "profile";
    return <OwnerContext.Provider value={{ me, refresh: owner.refresh }}><div className={"po-shell" + (me.preferences.compact_rows ? " po-compact" : "")}><aside className="po-nav"><div className="po-brand"><strong>Indian Servers</strong><span>Platform Owner</span></div><nav>{visible.map(([path, label, Icon]) => <div className="po-nav-row" key={path}><NavLink to={`/platform/${path}`} onClick={() => setMatches(undefined)}><Icon size={17}/>{label}</NavLink><button aria-label={`Favorite ${label}`} title={`Favorite ${label}`} onClick={async () => { const old = me.preferences.favorites || []; try {
        await api.patch("/platform/profile", { action: "preferences", reason: "Navigation favorite changed", values: { favorites: old.includes(path) ? old.filter((p: string) => p !== path) : [...old, path] } });
        owner.refresh();
    }
    catch (err) {
        setError(message(err));
    } }}><Star size={12} fill={(me.preferences.favorites || []).includes(path) ? "currentColor" : "none"}/></button></div>)}</nav><footer>{me.name}<br />{me.email}<br /><Badge>{me.role}</Badge><br /><button onClick={async () => { try {
        await api.post("/platform/sessions/revoke", { action: "all", reason: "Owner signed out", values: { id: me.session_id } });
    }
    finally {
        sessionStorage.removeItem(platformTokenKey);
        window.location.assign("/platform/login");
    } }}><LogOut size={14}/>Sign out</button></footer></aside><div className="po-main"><header className="po-topbar"><div className="po-actions"><Search size={17}/><input aria-label="Search owner portal" placeholder="Search signups and customers…" value={search} onChange={e => setSearch(e.target.value)}/></div><small>{me.name} · Local owner workspace</small><button onClick={() => navigate("/platform/profile")}>My account</button></header><main className="po-content"><Alert error={error}/>{matches && <section className="po-panel"><h2>Search results</h2>{[...(matches.signups || []).map((r: Data) => ({ ...r, type: "signup" })), ...(matches.customers || []).map((r: Data) => ({ ...r, type: "customer" }))].map((r: Data) => <p key={r.type + r.id}><button onClick={() => { navigate(`/platform/${r.type === "signup" ? "signups" : "customers"}?selected=${r.id}`); setSearch(""); }}>{r.name} · {r.status}</button></p>)}</section>}<Routes><Route index element={<Navigate to={me.preferences?.default_page && visible.some(p => p[0] === me.preferences.default_page) ? `/platform/${me.preferences.default_page}` : `/platform/${first}`} replace/>}/><Route path="overview" element={<Reports overview/>}/><Route path="reports" element={<Reports />}/><Route path="signups" element={<Signups />}/><Route path="signup-requests" element={<Navigate to="/platform/signups" replace/>}/><Route path="customers" element={<Customers />}/><Route path="databases" element={<Databases />}/><Route path="team" element={<Team />}/><Route path="plans" element={<Plans />}/><Route path="tasks" element={<Records key="tasks" workspace="tasks"/>}/><Route path="communications" element={<Records key="communications" workspace="communications"/>}/><Route path="operations" element={<Operations />}/><Route path="audit" element={<Audit />}/><Route path="settings" element={<SettingsPage />}/><Route path="profile" element={<Profile />}/><Route path="*" element={<Navigate to="/platform" replace/>}/></Routes></main></div></div></OwnerContext.Provider>;
}
export default function PlatformApp() { return <div className="po-root"><Routes><Route path="/platform/login" element={<Login />}/><Route path="/platform/public/:token" element={<PublicLink />}/><Route path="/platform/*" element={<Shell />}/></Routes></div>; }
