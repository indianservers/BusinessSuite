import { PhoneInput } from "@/lib/validation/PhoneInput";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Building2, ShieldCheck, LayoutGrid, UsersRound, Handshake, Layers, ShoppingCart, Database, Zap, ArrowRight, UserRound, Mail, Pencil, UserPlus, Phone } from "lucide-react";
import "./suite-signup.css";

import { Button } from "@/components/ui/button";
import { api } from "@/services/api";
import { errorMessage } from "@/apps/crm/leads/api";

export default function SignupPage() {
  const [modules, setModules] = useState<{key: string; label: string}[]>();
  const [selected, setSelected] = useState<string[]>([]);
  const [kind, setKind] = useState("company");
  const [phone, setPhone] = useState("");
  const [phoneCode, setPhoneCode] = useState("+91");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  const load = () => {
    setError("");
    void api.get("/auth/signup/options").then(r => setModules(r.data.modules))
      .catch(() => setError("Could not load available applications. Please retry."));
  };
  useEffect(load, []);
  return <main className={`trial-page trial-${kind}`}>
    <div className="trial-layout">
      <aside className="trial-intro">
        <Link to="/" className="trial-brand"><span className="trial-logo"><LayoutGrid size={32}/></span><span><strong>Business Suite</strong><small>Your Connected Workspace</small></span></Link>
        <div className="trial-pitch"><h2>{kind === "company" ? <>Run your business<br/>in one connected<br/><em>workspace</em></> : <>One workspace for<br/>your entire business</>}</h2><p>{kind === "company" ? "A unified suite to manage your people, projects, finance, sales, and inventory — all in one place." : "Try Business Suite with a free software trial and experience a connected, simpler way to manage your work—built for individuals and teams."}</p></div>
        <div className="trial-illustration" aria-hidden="true"><div className="trial-orbit"/><div className="trial-dashboard"><div className="trial-dashboard-sidebar"><LayoutGrid size={20}/><i/><i/><i/><i/></div><div className="trial-dashboard-body"><strong><LayoutGrid size={15}/> Business Suite</strong><div className="trial-dashboard-widgets"><div className="trial-chart"><span/><span/><span/><span/><span/></div><div className="trial-donut"/><div className="trial-lines"><i/><i/><i/></div><div className="trial-lines"><i/><i/><i/></div></div></div></div></div>
        <div className="trial-benefits">{[[Zap,"All-in-One Business Suite","HRMS, CRM, Projects, Sales & Inventory, and Finance"],[ShieldCheck,"Secure & Private","Your data is isolated and always protected"],[UsersRound,"Built for Growing Businesses","A scalable workspace for teams of any size"]].map(([Icon,title,description])=>{const BenefitIcon=Icon as typeof Zap;return <div className="trial-benefit" key={String(title)}><span><BenefitIcon size={25}/></span><div><strong>{String(title)}</strong><p>{String(description)}</p></div></div>;})}</div>
      </aside>
    <div className="trial-form-area">
      <div className="trial-signin">Already registered? <Link to="/login">Sign in <ArrowRight size={15}/></Link></div>
      <section className="trial-card"><header className="trial-card-heading"><span className="trial-heading-icon">{kind === "company" ? <Building2 size={30}/> : <UserPlus size={30}/>}</span><div>
        <h1 className="text-2xl font-semibold">Sign up for a software trial</h1>
        <p className="mt-2 text-sm text-slate-600">For companies and individuals. Tell us what you need; our team will review your request before granting access.</p></div></header>
        {sent ? <div role="status" className="mt-6 space-y-4 rounded-xl border border-green-200 bg-green-50 p-5"><h2 className="font-semibold">Request submitted</h2><p>We’ll review your request. If approved, you’ll receive an email invitation to set your password and access your workspace.</p><p className="text-sm">No account access has been granted yet. Your trial duration and applications are confirmed on approval.</p><Button asChild><Link to="/login">Back to sign in</Link></Button></div> : <form className="trial-form" onSubmit={async e => {
          e.preventDefault(); setError("");
          if (!selected.length) { setError("Select at least one application to trial."); return; }
          const form = new FormData(e.currentTarget);
          setBusy(true);
          try {
            await api.post("/auth/signup", {
              applicant_type: kind, name: String(form.get("name") || "").trim(),
              company_name: kind === "company" ? String(form.get("company_name") || "").trim() : null,
              email: String(form.get("email") || "").trim(), phone, phone_country_code: phoneCode,
              requested_modules: selected, notes: String(form.get("notes") || "").trim(),
              source: (new URLSearchParams(window.location.search).get("utm_source") || "website").slice(0, 80),
              campaign: (new URLSearchParams(window.location.search).get("utm_campaign") || "").slice(0, 120),
              consent: form.get("consent") === "on", website: String(form.get("website") || ""),
            });
            setSent(true);
          } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
        }}>
          <fieldset disabled={busy} className="trial-fields">
            <legend className="mb-2 text-sm font-medium">I am signing up as</legend>
            <div className="trial-kind">{[["company", "Company"], ["individual", "Individual"]].map(([value, label]) => <label className={kind===value?"selected":""} key={value}><input type="radio" name="applicant_type" value={value} checked={kind === value} onChange={() => setKind(value)}/>{label}</label>)}</div>
            <div className="trial-contact-grid">
              <label className={`trial-field ${kind === "individual" ? "trial-name-wide" : ""}`}><span><UserRound size={16}/> Your name</span><input className="block w-full rounded-md border p-3" placeholder="Enter your full name" name="name" autoComplete="name" required minLength={2} maxLength={150}/></label>
              {kind === "company" && <label className="trial-field"><span><Building2 size={16}/> Company name</span><input className="block w-full rounded-md border p-3" placeholder="Enter your company name" name="company_name" autoComplete="organization" required maxLength={150}/></label>}
              <label className="trial-field"><span><Mail size={16}/> Email</span><input className="block w-full rounded-md border p-3" placeholder="Enter your work email" name="email" type="email" autoComplete="email" required maxLength={100}/></label>
              <div className="trial-field"><span><Phone size={16}/> Phone</span><PhoneInput placeholder="Enter phone number" label="Phone" name="phone" value={phone} countryCode={phoneCode} onChange={setPhone} onCountryCodeChange={setPhoneCode} required disabled={busy}/></div>
            </div>
            <fieldset className="trial-applications"><legend><LayoutGrid size={19}/> Applications you want to try</legend>
              {!modules && <p role="status" className="text-sm">Loading applications…</p>}
              <div className="trial-app-grid">{modules?.map(m => {const config = /hrms/i.test(m.key)?[UsersRound,"HRMS","Manage people and attendance"]:/crm/i.test(m.key)?[Handshake,"CRM","Manage customers and relationships"]:/project|pms/i.test(m.key)?[Layers,"Projects","Plan, track, and deliver projects"]:/srm|inventory|sales/i.test(m.key)?[ShoppingCart,"Sales & Inventory","Handle sales, orders, and inventory"]:/fam|finance/i.test(m.key)?[Database,"Finance & Accounting","Manage accounts, expenses, and reports"]:[LayoutGrid,m.label,""];const Icon=config[0] as typeof LayoutGrid;return <label key={m.key} className={selected.includes(m.key)?"selected":""}><input type="checkbox" checked={selected.includes(m.key)} onChange={e => setSelected(v => e.target.checked ? [...v, m.key] : v.filter(k => k !== m.key))}/><span className="trial-app-icon"><Icon size={24}/></span><span><strong>{String(config[1])}</strong><small>{String(config[2])}</small></span></label>;})}</div>
            </fieldset>
            <label className="trial-notes"><span><Pencil size={17}/> What would you like to manage? <span className="text-slate-500">(optional)</span></span><textarea className="block min-h-24 w-full rounded-md border p-3" placeholder="e.g., employee management, customer relationships, project tracking, inventory, accounting, etc." name="notes" maxLength={2000}/></label>
            <div className="hidden" aria-hidden="true"><label>Website<input name="website" tabIndex={-1} autoComplete="off"/></label></div>
            <label className="trial-consent"><input className="mt-1" type="checkbox" name="consent" required/><span>I agree to be contacted about this trial request and understand that access requires approval.</span></label>
            {error && <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}{!modules && <Button type="button" variant="link" onClick={load}>Retry</Button>}</div>}
            <Button type="submit" className="trial-submit" disabled={busy || !modules?.length}>{busy ? "Submitting…" : <>Request trial access <ArrowRight size={20}/></>}</Button>
          </fieldset>
        </form>}
      </section>
    </div>
    </div>
  </main>;
}
