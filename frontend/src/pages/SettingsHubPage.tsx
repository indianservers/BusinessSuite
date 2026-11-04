import SetupReadiness from "@/components/suite/SetupReadiness";
import SettingsDirectory, { settingsCategory, scopeLabel, type SettingsOption } from "./settings/SettingsDirectory";

import SettingsEditorFrame, { SettingsHistory } from "./settings/SettingsEditorFrame";

import HomepageBannerSettings from "./settings/HomepageBannerSettings";

import { NativeSelect } from "@/components/ui/native-select";

import CompactForm from "@/components/forms/CompactForm";

import CentralSettingsEditor, { centralEditorKeys } from "./settings/CentralSettingsEditor";

import { lazy, Suspense, useEffect, useState } from "react";

import { Link, Navigate, useParams } from "react-router-dom";

import { useQuery, useQueryClient } from "@tanstack/react-query";

import { ArrowLeft, ArrowRight, Building2, Settings, RefreshCw, ShieldCheck } from "lucide-react";

import { api, authApi } from "@/services/api";

import { useAuthStore } from "@/store/authStore";

import { useThemeStore } from "@/store/themeStore";

import "./settings-hub.css";

import BranchSwitcher from "@/components/suite/BranchSwitcher";



const BranchSettings = lazy(() => import("./settings/BranchSettings"));

const UsersAccess = lazy(() => import("@/features/access/UsersAccessPage"));

const SetupMasters = lazy(() => import("@/apps/hrms/pages/settings/SettingsPage"));

type Option = SettingsOption;

type Catalog = {companyId:number;companyName:string;options:Option[]};

const base = "/access/settings";

const masterKeys = new Set(["departments", "designations", "shifts", "holidays", "leaveTypes", "salaryComponents"]);

const errorMessage = (e: any) => typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Could not load settings. Please try again.";



export function SettingsHomeEntry() {

  const { isAuthenticated, isHydrated } = useAuthStore();

  if (!isHydrated || !isAuthenticated) return null;

  return <Link to="/settings" className="settings-home-entry"><span><Settings size={24}/></span><div><strong>Settings</strong><small>Company details, branches, users and permissions</small></div><ArrowRight size={20}/></Link>;

}



export default function SettingsHubPage() {

  const {section} = useParams();

  const {user,isAuthenticated,isHydrated} = useAuthStore();

  const company = sessionStorage.getItem("suite-organization") || user?.access?.companyId;

  const catalog = useQuery({queryKey:["shared-settings", user?.id, company],queryFn:()=>api.get<Catalog>(base).then(r=>r.data),enabled:isHydrated&&isAuthenticated,retry:1,staleTime:0});

  const option = catalog.data?.options.find(o=>o.id===section);

  // Recheck the selected option on the server; stale client grants cannot open it.

  const selected = useQuery({queryKey:["shared-setting",user?.id,company,section],queryFn:()=>api.get<Option>(`${base}/${section}`).then(r=>r.data),enabled:!!section&&!!option,retry:false,staleTime:0});

  useEffect(()=>{if(section){window.scrollTo(0,0);document.getElementById("settings-page-title")?.focus({preventScroll:true});}},[section]);
  useEffect(()=>{document.title=section ? `${option?.title || "Settings"} · Settings` : "Settings";},[section,option?.title]);

  useEffect(()=>{if(section&&option&&selected.isSuccess){const key=`suite-settings:${user?.id}:${company}:recent`;try{const previous=JSON.parse(localStorage.getItem(key)||"[]");localStorage.setItem(key,JSON.stringify([section,...(Array.isArray(previous)?previous:[]).filter(id=>typeof id==="string"&&id!==section)].slice(0,6)));}catch{/* Recent items are optional. */}}},[section,option,selected.isSuccess,user?.id,company]);
  if(!isHydrated) return <main className="settings-hub" role="status">Loading your account…</main>;

  if(!isAuthenticated) return <Navigate to={`/login?next=${encodeURIComponent(section ? `/settings/${section}` : "/settings")}`} replace/>;

  const directoryKey=`suite-settings:${user?.id}:${company}:directory`;

  let directoryQuery="";try{directoryQuery=sessionStorage.getItem(directoryKey)||"";}catch{/* Navigation memory is optional. */}

  const directoryUrl=`/settings${directoryQuery?`?${directoryQuery}`:""}`;

  return <div className="settings-hub">

    <header className="suite-app-bar settings-header"><Link to="/dashboard"><ArrowLeft size={18}/>Home</Link><span><Building2 size={18}/>{catalog.data?.companyName || "Your workspace"}</span><div className="settings-branch-context"><BranchSwitcher/></div><button aria-label="Refresh settings" disabled={catalog.isFetching||selected.isFetching} aria-busy={catalog.isFetching||selected.isFetching} onClick={()=>{void catalog.refetch();if(section&&option)void selected.refetch();}}><RefreshCw size={18}/></button></header>

    <main>

      {section&&option&&<nav aria-label="Breadcrumb" className="settings-breadcrumb"><Link to={directoryUrl}>Settings</Link><span>/</span><Link to={`/settings?category=${encodeURIComponent(settingsCategory(option))}`}>{settingsCategory(option)}</Link><span>/</span><span aria-current="page">{option.title}</span></nav>}

      <div className="settings-heading"><div><p className="settings-eyebrow"><Settings size={16}/>WORKSPACE SETTINGS</p><h1 id="settings-page-title" tabIndex={-1}>{section && option ? option.title : "Settings"}</h1><p>{section&&option?option.description:"One place for your account, company and application preferences."}</p></div><div className="settings-access-note"><ShieldCheck size={20}/>Permissions apply to every change</div></div>

      {section && <Link className="settings-back" to={directoryUrl}><ArrowLeft size={16}/>All settings</Link>}

      {catalog.isPending && <p role="status">Loading your allowed settings…</p>}

      {catalog.isError && <div role="alert" className="settings-panel">{errorMessage(catalog.error)} <button onClick={()=>void catalog.refetch()}>Retry</button></div>}

      {catalog.isSuccess && section && (!option || selected.isError) && <section className="settings-panel" role="alert"><h2>Setting unavailable</h2><p>Your current permissions do not allow this setting in this company.</p><Link to="/settings">Return to allowed settings</Link></section>}

      {!section && catalog.isSuccess && <SetupReadiness embedded />}
      {!section && catalog.isSuccess && <SettingsDirectory options={catalog.data.options} userId={user?.id} companyId={catalog.data.companyId}/>}

      {section && option && selected.isPending && <p role="status">Checking access…</p>}

      {section && option && selected.isSuccess && <SettingsEditorFrame key={`${company}-${section}`} section={section}><div className="settings-section-context"><ShieldCheck size={16}/><span>{scopeLabel(option)}{!option.editable?" · Read only":" · Changes apply within this scope"}</span></div>

        {section === "appearance" ? <HomepageBannerSettings key={String(company)}/> : section === "company-profile" ? <CompanyProfile key={`${catalog.data?.companyId}-${section}`}/> : section==="branches" ? <Suspense fallback={<p role="status">Loading branches...</p>}><BranchSettings/></Suspense> : section==="users" ? <Suspense fallback={<p role="status">Loading users...</p>}><UsersAccess embedded/></Suspense> : section==="account" ? <AccountSettings/> : section==="preferences" ? <Preferences/> : centralEditorKeys.has(section) ? <CentralSettingsEditor key={section} section={section}/> : masterKeys.has(section) ? <Suspense fallback={<p role="status">Loading configuration…</p>}><SetupMasters key={section} section={section as any}/></Suspense> : <section className="settings-panel"><h2>{option.title}</h2><p>{option.description}</p><p>Changes apply within your authorized company, team or project scope.</p><Link className="settings-primary" to={selected.data.destination!}>Open {option.title}<ArrowRight size={17}/></Link></section>}

        {option.historyAvailable?<SettingsHistory section={section}/>:catalog.data?.options.some(o=>o.id==="audit")&&!["account","preferences","audit"].includes(section)?<Link className="settings-history-link" to="/settings/audit">View company change history <ArrowRight size={15}/></Link>:null}

      </SettingsEditorFrame>}

    </main>

  </div>;

}



const fields: [string,string,string?][] = [["name","Company name"],["legal_name","Legal name"],["website","Website"],["email","Company email","email"],["phone","Phone"],["address","Address"],["city","City"],["state","State"],["country","Country"],["pincode","Postal code"],["logo_url","Logo URL","url"],["registration_number","Registration number"],["cin_number","CIN"],["pan_number","PAN"],["tan_number","TAN"],["gstin","GSTIN"],["default_timezone","Default timezone"],["default_currency","Default currency"],["working_days_per_week","Working days per week","number"],["fiscal_year_start_month","Financial year start month","number"]];

const fieldHints:Record<string,string>={name:"Use your business trading name.",email:"Example: accounts@company.com",website:"Example: https://company.com",country:"Country where your company is registered.",default_currency:"Three uppercase letters, e.g. INR, USD or AED.",default_timezone:"IANA timezone, e.g. Asia/Kolkata or UTC.",fiscal_year_start_month:"1 = January, 4 = April; choose a month from 1 to 12.",working_days_per_week:"Choose a number from 1 to 7.",gstin:"Indian GSTIN: 15 uppercase letters and digits.",pan_number:"Indian PAN: five letters, four digits, one letter.",logo_url:"Use a publicly accessible HTTPS image URL."};

function validateCompanyField(key:string,value:unknown){

 const text=String(value??"").trim();

 if(["name","email","country","default_currency","default_timezone","fiscal_year_start_month"].includes(key)&&!text)return "This field is required.";

 if(!text)return "";

 if(key==="name"&&text.length>150)return "Use 150 characters or fewer.";

 if(key==="email"&&!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text))return "Enter a valid company email address.";

 if(key==="default_currency"&&!/^[A-Z]{3}$/.test(text))return "Use a three-letter uppercase currency code, e.g. INR.";

 if(key==="default_timezone"){try{new Intl.DateTimeFormat("en",{timeZone:text});}catch{return "Enter a valid IANA timezone, e.g. Asia/Kolkata.";}}

 if(["fiscal_year_start_month","working_days_per_week"].includes(key)){const max=key==="working_days_per_week"?7:12;if(!Number.isInteger(Number(text))||Number(text)<1||Number(text)>max)return `Enter a whole number from 1 to ${max}.`;}

 if(["website","logo_url"].includes(key)){try{const url=new URL(text);if(key==="logo_url"?url.protocol!=="https:":!["http:","https:"].includes(url.protocol))return "Enter a valid web URL (HTTPS for logos).";}catch{return "Enter a full URL, e.g. https://company.com.";}}

 if(key==="gstin"&&!/^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9]$/.test(text))return "Enter a valid 15-character GSTIN.";

 if(key==="pan_number"&&!/^[A-Z]{5}[0-9]{4}[A-Z]$/.test(text))return "Use the PAN format ABCDE1234F.";

 return "";

}

function CompanyProfile({ defaultsOnly = false }: { defaultsOnly?: boolean }) {

 const qc=useQueryClient();const [form,setForm]=useState<Record<string,any>>({}),[message,setMessage]=useState(""),[failed,setFailed]=useState(false),[saving,setSaving]=useState(false),[validation,setValidation]=useState<Record<string,string>>({});

 const user=useAuthStore(s=>s.user);const company=sessionStorage.getItem("suite-organization")||user?.access?.companyId;

 const profile=useQuery({queryKey:["shared-company-profile",user?.id,company],queryFn:()=>api.get(base+"/company-profile").then(r=>r.data),retry:false});

 useEffect(()=>{if(profile.data)setForm(previous=>Object.keys(previous).length?previous:profile.data.profile);},[profile.data]);

 if(profile.isPending)return <p role="status">Loading company profile…</p>;

 if(profile.isError)return <p role="alert">{errorMessage(profile.error)} <button onClick={()=>void profile.refetch()}>Retry</button></p>;

 const isDefault=(key:string)=>["default_timezone","default_currency","working_days_per_week","fiscal_year_start_month"].includes(key);

 const visibleFields=fields.filter(([key])=>key in form&&isDefault(key)===defaultsOnly);

 const dirty=visibleFields.some(([key])=>String(form[key]??"")!==String(profile.data.profile[key]??""));

 const essential=new Set(["name","email","country","default_timezone","default_currency","fiscal_year_start_month"]);

 const renderField=([key,label,type]:[string,string,string?])=><div key={key} className="settings-field"><label htmlFor={`company-${key}`}>{label}{essential.has(key)?" *":""}</label><input id={`company-${key}`} name={key} type={type||"text"} value={form[key]??""} disabled={!profile.data.editable||saving} required={essential.has(key)} aria-invalid={!!validation[key]} aria-describedby={validation[key]?`company-${key}-error`:fieldHints[key]?`company-${key}-hint`:undefined} min={type==="number"?1:undefined} max={key==="working_days_per_week"?7:key==="fiscal_year_start_month"?12:undefined} onBlur={()=>setValidation(previous=>({...previous,[key]:validateCompanyField(key,form[key])}))} onChange={e=>{const value=type==="number"&&e.target.value!==""?Number(e.target.value):e.target.value;setForm(previous=>({...previous,[key]:value}));setMessage("");setValidation(previous=>({...previous,[key]:validateCompanyField(key,value)}));}}/>{validation[key]?<small id={`company-${key}-error`} className="settings-field-error" role="alert">{validation[key]}</small>:fieldHints[key]&&<small id={`company-${key}-hint`} className="settings-field-hint">{fieldHints[key]}</small>}</div>;

 return <CompactForm compactTabs={false} className="settings-panel" noValidate onSubmit={async e=>{e.preventDefault();if(saving||!dirty||!profile.data.editable)return;const errors=Object.fromEntries(visibleFields.map(([key])=>[key,validateCompanyField(key,form[key])]));setValidation(errors);const first=Object.keys(errors).find(key=>errors[key]);if(first){document.getElementById(`company-${first}`)?.focus();setFailed(true);setMessage("Review the highlighted fields before saving.");return;}setSaving(true);setMessage("");setFailed(false);try{const payload=Object.fromEntries(visibleFields.map(([key])=>[key,typeof form[key]==="string"?form[key].trim():form[key]]));await api.patch(base+"/company-profile",payload);setForm(previous=>({...previous,...payload}));await Promise.all([qc.invalidateQueries({queryKey:["shared-settings"]}),qc.invalidateQueries({queryKey:["login-branding"]}),qc.invalidateQueries({queryKey:["shared-company-profile"]}),qc.invalidateQueries({queryKey:["companies"]}),qc.invalidateQueries({queryKey:["settings-history"]})]);setMessage("Changes saved. They apply immediately across Business Suite.");}catch(err){setFailed(true);setMessage(errorMessage(err));}finally{setSaving(false);}}}>

 <p className="mb-3 text-sm">Fields marked <span className="text-destructive">*</span> are mandatory before creating or updating business records.</p>
 {visibleFields.some(([key])=>essential.has(key)&&validateCompanyField(key,form[key]))&&<div role="status" className="mb-4 rounded-lg border border-amber-500/40 p-3 text-sm"><strong>Missing or invalid mandatory fields</strong><ul className="mt-2 list-disc pl-5">{visibleFields.filter(([key])=>essential.has(key)&&validateCompanyField(key,form[key])).map(([key,label])=><li key={key}><a className="underline" href={`#company-${key}`}>{label} *</a>: {validateCompanyField(key,form[key])}</li>)}</ul></div>}
 <p>{profile.data.editable?"Changes update the shared company record used throughout Business Suite.":"You can view this company information. Editing requires company configuration access."}</p><div className="settings-form-grid">{visibleFields.filter(([key])=>defaultsOnly||essential.has(key)).map(renderField)}</div>

 {!defaultsOnly&&<details className="my-4"><summary>More company details</summary><div className="settings-form-grid">{visibleFields.filter(([key])=>!essential.has(key)).map(renderField)}</div></details>}

 {profile.data.editable&&<button type="submit" className="settings-primary" disabled={saving||!dirty}>{saving?"Saving…":"Save company profile"}</button>}{message&&<p role={failed?"alert":"status"} className={failed?"settings-message error":"settings-message success"}>{message}</p>}

 </CompactForm>;

}



function AccountSettings() {

  const user=useAuthStore(s=>s.user);const [current,setCurrent]=useState("");const [password,setPassword]=useState("");const [confirm,setConfirm]=useState("");const [message,setMessage]=useState("");const [busy,setBusy]=useState(false);

  const sessions=useQuery({queryKey:["my-settings-sessions",user?.id],queryFn:()=>authApi.mySessions().then(r=>r.data),retry:false});

  return <div className="settings-stack"><section className="settings-panel"><h2>Your account</h2><p>{user?.name || user?.email}</p><p>{user?.email}</p><p>Role: {user?.primary_role || user?.role || "Assigned access"}</p></section><CompactForm className="settings-panel" onSubmit={async e=>{e.preventDefault();if(password!==confirm){setMessage("Passwords do not match.");return;}setBusy(true);try{await authApi.changePassword(current,password);setCurrent("");setPassword("");setConfirm("");setMessage("Password changed.");}catch(err){setMessage(errorMessage(err));}finally{setBusy(false);}}}><h2>Password</h2><p>Your company’s password policy applies. For Google sign-in, manage your Google account security with Google.</p><div className="settings-form-grid"><label>Current password<input type="password" autoComplete="current-password" required value={current} onChange={e=>setCurrent(e.target.value)}/></label><label>New password<input type="password" autoComplete="new-password" required minLength={8} value={password} onChange={e=>setPassword(e.target.value)}/></label><label>Confirm new password<input type="password" autoComplete="new-password" required value={confirm} onChange={e=>setConfirm(e.target.value)}/></label></div>{confirm&&password!==confirm&&<p className="settings-field-error" role="alert">Passwords do not match.</p>}<button type="submit" className="settings-primary" disabled={busy||!current||password.length<8||!confirm||password!==confirm}>Change password</button>{message&&<p role="status">{message}</p>}</CompactForm><section className="settings-panel"><h2>Your sessions</h2>{sessions.isPending?<p role="status">Loading sessions…</p>:sessions.isError?<p role="alert">{errorMessage(sessions.error)}</p>:<><ul>{sessions.data?.filter((s:any)=>s.status?.toLowerCase()==="active").map((s:any)=><li key={s.id}>{s.device_name || "Browser session"} · {s.ip_address || "IP unavailable"}</li>)}</ul><button type="button" disabled={busy} onClick={async()=>{setBusy(true);try{await authApi.revokeOtherSessions();await sessions.refetch();setMessage("Other sessions revoked.");}catch(err){setMessage(errorMessage(err));}finally{setBusy(false);}}}>Sign out other sessions</button></>}</section></div>;

}



function Preferences() {

  const {theme,setTheme,density,setDensity}=useThemeStore();

  return <section className="settings-panel"><h2>Appearance</h2><p>Your display preferences apply across the apps on this browser.</p><div className="settings-form-grid"><label>Theme<NativeSelect value={theme} onChange={e=>setTheme(e.target.value as "light"|"dark"|"system")}><option value="light">Light</option><option value="dark">Dark</option><option value="system">System</option></NativeSelect></label><label>Display density<NativeSelect value={density} onChange={e=>setDensity(e.target.value as "comfortable"|"compact")}><option value="comfortable">Comfortable</option><option value="compact">Compact</option></NativeSelect></label></div></section>;

}
