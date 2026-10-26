import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, BarChart3, BookOpen, Boxes, BriefcaseBusiness, CalendarDays, PieChart, Check, ChevronDown, CircleHelp, Crosshair, Database, FileText, Folder, Landmark, List, LogIn, Package, Search, ShoppingCart, Store, UserRound, Users, X, type LucideIcon } from "lucide-react";
import { BUSINESS_SUITE_NAME, BUSINESS_SUITE_VERSION, products, type ProductKey } from "@/lib/products";
import { canAccessRoute } from "@/lib/roles";
import { useAuthStore } from "@/store/authStore";
import "./module-index.css";

type ModuleIndexItem = { key: string; name: string; label: string; description: string; icon: LucideIcon; homePath: string; loginPath: string; productKey: ProductKey };
const modules: ModuleIndexItem[] = [
  {
    key: "hrms",
    name: "AI HRMS",
    label: "Human Resource Management",
    description: "Employees, payroll, attendance, leave, recruitment, and self-service.",
    icon: Users,
    homePath: "/hrms",
    loginPath: "/hrms/login",
    productKey: "hrms",
  },
  {
    key: "crm",
    name: "VyaparaCRM",
    label: "Customer Relationship Management",
    description: "Leads, customers, deals, activities, campaigns, quotes, and sales follow-ups.",
    icon: Users,
    homePath: "/crm",
    loginPath: "/crm/login",
    productKey: "crm",
  },
  {
    key: "pms",
    name: "KaryaFlow PMS",
    label: "Project Management Software",
    description: "Projects, tasks, sprints, milestones, reports, workload, risks, and delivery plans.",
    icon: Boxes,
    homePath: "/pms",
    loginPath: "/pms/login",
    productKey: "project_management",
  },
  {
    key: "srm",
    name: "Sales & Inventory Management",
    label: "Sales, Inventory & POS",
    description: "Manage sales orders, POS, products, stock, delivery, billing, invoices, collections, and profitability.",
    icon: Package,
    homePath: "/srm",
    loginPath: "/srm/login",
    productKey: "srm",
  },
  {
    key: "fam",
    name: "Finance & Accounting Management",
    label: "Finance & Accounting",
    description: "Manage financial settings, chart of accounts, ledgers, opening balances, branches, cost centers, and audit-ready books.",
    icon: Landmark,
    homePath: "/fam",
    loginPath: "/fam/login",
    productKey: "fam",
  },
];

const features: Record<string, [LucideIcon, string][]> = {
  hrms: [[UserRound,"People"],[FileText,"Payroll"],[CalendarDays,"Attendance"]],
  crm: [[Crosshair,"Leads"],[BarChart3,"Deals"],[Users,"Customers"]],
  pms: [[Folder,"Projects"],[List,"Tasks"],[Users,"Teams"]],
  srm: [[ShoppingCart,"Orders"],[Database,"Stock"],[Store,"POS"]],
  fam: [[FileText,"Invoices"],[BookOpen,"Ledgers"],[PieChart,"Reports"]],
};
function SuiteMark({ small = false }: { small?: boolean }) {
  return <svg className={small ? "suite-mark small" : "suite-mark"} viewBox="0 0 40 44" fill="none" aria-hidden="true"><defs><linearGradient id={small ? "suite-small" : "suite-main"} x1="7" y1="2" x2="32" y2="39" gradientUnits="userSpaceOnUse"><stop stopColor="#3bbfa3"/><stop offset="1" stopColor="#006b56"/></linearGradient></defs><path d="M14 4c2-4 7-4 10 0l14 24c2 3 1 6-2 8l-12 7c-2 1-5 1-7-1L3 32c-3-2-3-5-1-8L14 4Z" fill={`url(#${small ? "suite-small" : "suite-main"})`}/><path d="m10 28 8-8 6 5 5-10M20 19l9-4-1 9" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/><path d="m6 31 11 4 9-8" stroke="white" strokeOpacity=".3" strokeWidth="2"/></svg>;
}
function WorkspaceArt({ compact = false }: { compact?: boolean }) {
  const icons = [Users,BarChart3,Package,FileText,Landmark];
  return <div className={`suite-art ${compact ? "compact" : ""}`} aria-hidden="true"><div className="suite-orbit orbit-one"/><div className="suite-orbit orbit-two"/>{compact && <div className="suite-art-core"><SuiteMark/></div>}{icons.map((Icon,index)=><span key={index} className={`suite-art-tile tile-${index}`}><Icon strokeWidth={2.5}/></span>)}{[0,1,2,3,4,5].map(i=><i key={i} className={`orbit-dot dot-${i}`}/>)}</div>;
}
export default function ModuleIndexPage() {
  const { isAuthenticated, isHydrated, user } = useAuthStore();
  const [query,setQuery]=useState("");
  const [help,setHelp]=useState<string | null>(null);
  const search=useRef<HTMLInputElement>(null);
  const navigate=useNavigate();
  useEffect(()=>{ const handler=(event:KeyboardEvent)=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="k"){event.preventDefault();search.current?.focus();} if(event.key==="Escape")setHelp(null);};window.addEventListener("keydown",handler);return()=>window.removeEventListener("keydown",handler);},[]);
  const visible=modules.filter(module=>`${module.name} ${module.label} ${module.description} ${features[module.key].map(([,name])=>name).join(" ")}`.toLowerCase().includes(query.toLowerCase().trim()));
  const destination=(module:ModuleIndexItem)=>isHydrated && isAuthenticated && canAccessRoute(module.homePath,user?.role,user?.is_superuser) ? module.homePath : module.loginPath;
  return <div className="suite-launcher">
    <header className="suite-topbar"><div className="suite-topbar-inner">
      <Link to="/" className="suite-brand"><SuiteMark/><strong>{BUSINESS_SUITE_NAME}</strong><span className="suite-version">v{BUSINESS_SUITE_VERSION}</span></Link>
      <label className="suite-workspace-picker"><BriefcaseBusiness size={18}/><select aria-label="Choose application" value="" onChange={event=>{if(event.target.value)navigate(event.target.value);}}><option value="">My Workspace</option>{modules.map(module=><option key={module.key} value={destination(module)}>{module.name}</option>)}</select><ChevronDown size={15}/></label>
      <label className="suite-search"><Search size={19}/><input ref={search} aria-label="Search applications" placeholder="Search applications, help, or anything..." value={query} onChange={event=>setQuery(event.target.value)}/>{query ? <button aria-label="Clear search" onClick={()=>setQuery("")}><X size={16}/></button> : <kbd>Ctrl K</kbd>}</label>
      <button className="suite-help" onClick={()=>setHelp("Help")}><CircleHelp size={19}/><span>Help</span></button>
      <Link to="/login" className="suite-general-login"><LogIn size={18}/>General login</Link>
    </div></header>
    <main className="suite-content">
      <section className="suite-hero"><div className="suite-hero-copy"><p className="suite-eyebrow"><span/>Your connected workspace</p><h1>One workspace. Every part of your business.</h1><p className="suite-hero-description">Open CRM, HRMS, PMS, Sales &amp; Inventory, or FAM from one place. Sign in to the module you want to use.</p></div><WorkspaceArt/></section>
      <section aria-labelledby="suite-applications-title" className="suite-applications"><div className="suite-section-heading"><div><h2 id="suite-applications-title">Explore your applications</h2><span className="suite-module-count">5 connected modules</span></div><p>All your business applications, in one connected workspace.</p></div>
        <div className="suite-module-grid">{visible.map(module=>{const Icon=module.icon;const product=products[module.productKey];return <article key={module.key} className={`suite-module-card suite-${module.key}`}><div className="suite-module-heading"><div className="suite-module-icon"><Icon size={37} strokeWidth={2.4}/></div><div className="suite-module-titles"><div><h3>{module.name}</h3><span className="suite-product-version">{product.shortName} {product.version}</span></div><p>{module.label}</p></div></div><p className="suite-module-description">{module.description}</p><div className="suite-feature-pills">{features[module.key].map(([Feature,name])=><span key={name}><Feature size={19}/>{name}</span>)}</div><Link to={destination(module)} className="suite-open-application" aria-label={`Open ${module.name}`}><span>Open application</span><ArrowRight size={20}/></Link></article>;})}
        {!query && <article className="suite-connected-card"><div><p className="suite-eyebrow"><span/>A connected workspace</p><h3>Built for your<br/>entire business.</h3><p>Five powerful modules. One seamless experience. Work smarter, faster, together.</p><ul>{["Single sign-on experience","Seamless data flow across modules","A unified platform for your growing business"].map(text=><li key={text}><span><Check size={13}/></span>{text}</li>)}</ul></div><WorkspaceArt compact/></article>}
        {!visible.length && <div className="suite-empty"><Search size={30}/><h3>No applications found</h3><p>Try searching for CRM, projects, payroll, sales, or finance.</p><button onClick={()=>setQuery("")}>Show all applications</button></div>}
        </div>
      </section>
    </main>
    <footer className="suite-footer"><div><Link to="/" className="suite-footer-brand"><SuiteMark small/><strong>{BUSINESS_SUITE_NAME}</strong><span className="suite-version">v{BUSINESS_SUITE_VERSION}</span></Link><nav aria-label="Resources">{["Help","Documentation","Support","What's new"].map(item=><button key={item} onClick={()=>setHelp(item)}>{item}</button>)}</nav><p>&copy; {new Date().getFullYear()} Business Suite. All rights reserved.</p></div></footer>
    {help && <div className="suite-help-overlay" onClick={()=>setHelp(null)}><section role="dialog" aria-modal="true" aria-labelledby="suite-help-title" className="suite-help-dialog" onClick={event=>event.stopPropagation()}><button autoFocus aria-label="Close help" onClick={()=>setHelp(null)}><X size={20}/></button><h2 id="suite-help-title">{help}</h2><p>{help==="What's new" ? "Your connected workspace brings HRMS, CRM, PMS, Sales & Inventory, and Finance & Accounting together in one place." : help==="Support" ? "Contact your organization's Super Admin for account access, passwords, and workspace configuration." : "Choose Open application to sign in to a module. Use the search bar to find an application, or My Workspace to switch directly. Your account's assigned permissions determine which modules you can access."}</p><p className="suite-help-version">Business Suite v{BUSINESS_SUITE_VERSION}</p></section></div>}
  </div>;
}
