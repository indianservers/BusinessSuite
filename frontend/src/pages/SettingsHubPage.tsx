import { lazy, Suspense, useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Building2, Settings, RefreshCw, Search, ShieldCheck } from "lucide-react";
import { api, authApi } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { useThemeStore } from "@/store/themeStore";
import "./settings-hub.css";

const SetupMasters = lazy(() => import("@/apps/hrms/pages/settings/SettingsPage"));
type Option = {id:string;title:string;group:string;description:string;destination:string|null;scope:string;editable:boolean};
type Catalog = {companyId:number;companyName:string;options:Option[]};
const base = "/access/settings";
const masterKeys = new Set(["branches", "departments", "designations", "shifts", "holidays", "leaveTypes", "salaryComponents"]);
const errorMessage = (e: any) => typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Could not load settings. Please try again.";

export function SettingsHomeEntry() {
  return <Link to="/settings" className="settings-home-entry"><span><Settings size={24}/></span><div><strong>Settings</strong><small>Your account, company and authorized application settings</small></div><ArrowRight size={20}/></Link>;
}

export default function SettingsHubPage() {
  const {section} = useParams();
  const {user,isAuthenticated,isHydrated} = useAuthStore();
  const [search,setSearch] = useState("");
  const company = sessionStorage.getItem("suite-organization") || user?.access?.companyId;
  const catalog = useQuery({queryKey:["shared-settings", user?.id, company],queryFn:()=>api.get<Catalog>(base).then(r=>r.data),enabled:isHydrated&&isAuthenticated,retry:1,staleTime:0});
  const option = catalog.data?.options.find(o=>o.id===section);
  // Recheck the selected option on the server; stale client grants cannot open it.
  const selected = useQuery({queryKey:["shared-setting",user?.id,company,section],queryFn:()=>api.get<Option>(`${base}/${section}`).then(r=>r.data),enabled:!!section&&!!option,retry:false,staleTime:0});
  useEffect(()=>{document.title=section ? `${option?.title || "Settings"} · Settings` : "Settings";},[section,option?.title]);
  if(!isHydrated) return <main className="settings-hub" role="status">Loading your account…</main>;
  if(!isAuthenticated) return <Navigate to="/login" replace/>;
  const matches=(catalog.data?.options || []).filter(o=>`${o.title} ${o.description} ${o.group}`.toLowerCase().includes(search.toLowerCase()));
  return <div className="settings-hub">
    <header className="settings-header"><Link to="/dashboard"><ArrowLeft size={18}/>Home</Link><span><Building2 size={18}/>{catalog.data?.companyName || "Your workspace"}</span><button aria-label="Refresh settings" onClick={()=>{void catalog.refetch();void selected.refetch();}}><RefreshCw size={18}/></button></header>
    <main>
      <div className="settings-heading"><div><p className="settings-eyebrow"><Settings size={16}/>WORKSPACE SETTINGS</p><h1>{section && option ? option.title : "Settings"}</h1><p>Manage your account and the configuration available to you in this company.</p></div><div className="settings-access-note"><ShieldCheck size={20}/>Permissions apply to every change</div></div>
      {section && <Link className="settings-back" to="/settings"><ArrowLeft size={16}/>All settings</Link>}
      {catalog.isPending && <p role="status">Loading your allowed settings…</p>}
      {catalog.isError && <div role="alert" className="settings-panel">{errorMessage(catalog.error)} <button onClick={()=>void catalog.refetch()}>Retry</button></div>}
      {catalog.isSuccess && section && (!option || selected.isError) && <section className="settings-panel" role="alert"><h2>Setting unavailable</h2><p>Your current permissions do not allow this setting in this company.</p><Link to="/settings">Return to allowed settings</Link></section>}
      {!section && catalog.isSuccess && <>
        <label className="settings-search"><Search size={18}/><input aria-label="Search settings" placeholder="Search your settings…" value={search} onChange={e=>setSearch(e.target.value)}/></label>
        {[...new Set(matches.map(o=>o.group))].map(group=><section className="settings-group" key={group}><h2>{group}</h2><div className="settings-grid">{matches.filter(o=>o.group===group).map(o=><Link className="settings-card" key={o.id} to={`/settings/${o.id}`} data-setting-id={o.id}><Settings size={21}/><div><h3>{o.title}</h3><p>{o.description}</p><small>{o.id==="company-profile"&&!o.editable ? "View company information" : o.scope==="own" ? "Your authorized scope" : o.scope}</small></div><ArrowRight size={17}/></Link>)}</div></section>)}
        {!matches.length && <p role="status">No matching settings.</p>}
      </>}
      {section && option && selected.isPending && <p role="status">Checking access…</p>}
      {section && option && selected.isSuccess && <>
        {section==="company-profile" ? <CompanyProfile key={catalog.data?.companyId}/> : section==="account" ? <AccountSettings/> : section==="preferences" ? <Preferences/> : masterKeys.has(section) ? <Suspense fallback={<p role="status">Loading configuration…</p>}><SetupMasters key={section} section={section as any}/></Suspense> : <section className="settings-panel"><h2>{option.title}</h2><p>{option.description}</p><p>Changes apply within your authorized company, team or project scope.</p><Link className="settings-primary" to={selected.data.destination!}>Open {option.title}<ArrowRight size={17}/></Link></section>}
      </>}
    </main>
  </div>;
}

const fields: [string,string,string?][] = [["name","Company name"],["legal_name","Legal name"],["website","Website"],["email","Company email","email"],["phone","Phone"],["address","Address"],["city","City"],["state","State"],["country","Country"],["pincode","Postal code"],["logo_url","Logo URL","url"],["registration_number","Registration number"],["cin_number","CIN"],["pan_number","PAN"],["tan_number","TAN"],["gstin","GSTIN"],["default_timezone","Default timezone"],["default_currency","Default currency"],["working_days_per_week","Working days per week","number"],["fiscal_year_start_month","Financial year start month","number"]];
function CompanyProfile() {
  const qc=useQueryClient();const [form,setForm]=useState<Record<string,any>>({});const [message,setMessage]=useState("");const [saving,setSaving]=useState(false);
  const user=useAuthStore(s=>s.user);
  const company=sessionStorage.getItem("suite-organization") || user?.access?.companyId;
  const profile=useQuery({queryKey:["shared-company-profile",user?.id,company],queryFn:()=>api.get(base+"/company-profile").then(r=>r.data),retry:false});
  useEffect(()=>{if(profile.data) setForm(profile.data.profile);},[profile.data]);
  if(profile.isPending) return <p role="status">Loading company profile…</p>;
  if(profile.isError) return <p role="alert">{errorMessage(profile.error)}</p>;
  return <form className="settings-panel" onSubmit={async e=>{e.preventDefault();setSaving(true);setMessage("");try{await api.patch(base+"/company-profile",form);await qc.invalidateQueries({queryKey:["shared-settings"]});await qc.invalidateQueries({queryKey:["login-branding"]});setMessage("Company profile saved.");}catch(err){setMessage(errorMessage(err));}finally{setSaving(false);}}}>
    <p>{profile.data.editable ? "Updates are saved to this company’s shared database record." : "Company information is read-only for your account."}</p>
    <div className="settings-form-grid">{fields.filter(([key])=>key in form).map(([key,label,type])=><label key={key}>{label}<input name={key} type={type||"text"} value={form[key]??""} disabled={!profile.data.editable} required={key==="name"} min={type==="number"?1:undefined} max={key==="working_days_per_week"?7:key==="fiscal_year_start_month"?12:undefined} onChange={e=>setForm({...form,[key]:type==="number"?Number(e.target.value):e.target.value})}/></label>)}</div>
    {profile.data.editable&&<button className="settings-primary" disabled={saving}>{saving?"Saving…":"Save company profile"}</button>} {message&&<p role="status">{message}</p>}
  </form>;
}

function AccountSettings() {
  const user=useAuthStore(s=>s.user);const [current,setCurrent]=useState("");const [password,setPassword]=useState("");const [confirm,setConfirm]=useState("");const [message,setMessage]=useState("");const [busy,setBusy]=useState(false);
  const sessions=useQuery({queryKey:["my-settings-sessions",user?.id],queryFn:()=>authApi.mySessions().then(r=>r.data),retry:false});
  return <div className="settings-stack"><section className="settings-panel"><h2>Your account</h2><p>{user?.name || user?.email}</p><p>{user?.email}</p><p>Role: {user?.primary_role || user?.role || "Assigned access"}</p></section><form className="settings-panel" onSubmit={async e=>{e.preventDefault();if(password!==confirm){setMessage("Passwords do not match.");return;}setBusy(true);try{await authApi.changePassword(current,password);setCurrent("");setPassword("");setConfirm("");setMessage("Password changed.");}catch(err){setMessage(errorMessage(err));}finally{setBusy(false);}}}><h2>Password</h2><p>Your company’s password policy applies. For Google sign-in, manage your Google account security with Google.</p><div className="settings-form-grid"><label>Current password<input type="password" autoComplete="current-password" required value={current} onChange={e=>setCurrent(e.target.value)}/></label><label>New password<input type="password" autoComplete="new-password" required minLength={8} value={password} onChange={e=>setPassword(e.target.value)}/></label><label>Confirm new password<input type="password" autoComplete="new-password" required value={confirm} onChange={e=>setConfirm(e.target.value)}/></label></div><button className="settings-primary" disabled={busy}>Change password</button>{message&&<p role="status">{message}</p>}</form><section className="settings-panel"><h2>Your sessions</h2>{sessions.isPending?<p role="status">Loading sessions…</p>:sessions.isError?<p role="alert">{errorMessage(sessions.error)}</p>:<><ul>{sessions.data?.filter((s:any)=>s.status?.toLowerCase()==="active").map((s:any)=><li key={s.id}>{s.device_name || "Browser session"} · {s.ip_address || "IP unavailable"}</li>)}</ul><button type="button" disabled={busy} onClick={async()=>{setBusy(true);try{await authApi.revokeOtherSessions();await sessions.refetch();setMessage("Other sessions revoked.");}catch(err){setMessage(errorMessage(err));}finally{setBusy(false);}}}>Sign out other sessions</button></>}</section></div>;
}

function Preferences() {
  const {theme,setTheme,density,setDensity}=useThemeStore();
  return <section className="settings-panel"><h2>Appearance</h2><p>Your display preferences apply across the apps on this browser.</p><div className="settings-form-grid"><label>Theme<select value={theme} onChange={e=>setTheme(e.target.value as "light"|"dark"|"system")}><option value="light">Light</option><option value="dark">Dark</option><option value="system">System</option></select></label><label>Display density<select value={density} onChange={e=>setDensity(e.target.value as "comfortable"|"compact")}><option value="comfortable">Comfortable</option><option value="compact">Compact</option></select></label></div></section>;
}
