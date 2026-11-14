import type { ReactNode } from "react";
import { isSharedTaskWorkspace, hasPmsWorkspaceShell } from "@/lib/task-workspace";
import { Link, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { ChevronDown, Check, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { workspacePageHref } from "@/lib/navigation-workspaces";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import type { WorkspaceView } from "./WorkspaceViewBar";
import "./workspace-surface.css";

const crm: WorkspaceView[] = [
  {id:"templates",label:"Templates",icon:"docs",description:"Reusable sales and document templates",href:"/crm/templates",category:"Collaborate"},
  {id:"dashboard",label:"Overview",icon:"dashboard",description:"Sales priorities and live performance",href:"/crm/dashboard"},
  {id:"leads",label:"Leads",icon:"list",description:"Capture, qualify and build relationships",href:"/crm/leads",color:"#14a89d"},
  {id:"deals",label:"Deals",icon:"table",description:"Every opportunity and next decision",href:"/crm/deals",color:"#8b5cf6"},
  {id:"pipeline",label:"Pipeline",icon:"board",description:"A visual flow from enquiry to close",href:"/crm/pipeline",color:"#648be2"},
  {id:"activities",label:"Activities",icon:"activity",description:"The work behind your relationships",href:"/crm/activities",category:"Collaborate",color:"#4ca7cf"},
  {id:"messages",label:"Channel",icon:"channel",description:"Keep team conversations in context",href:"/crm/messages",category:"Collaborate",color:"#9b72d8"},
  {id:"calendar",label:"Calendar",icon:"calendar",description:"Calls, meetings and commitments",href:"/crm/calendar",category:"Plan",color:"#e6a05b"},
  {id:"gantt",label:"Gantt",icon:"gantt",description:"Plan customer work across time",href:"/crm/gantt",category:"Plan",color:"#eb8477"},
  {id:"forecasting",label:"Forecast",icon:"dashboard",description:"Weighted revenue and closing horizons",href:"/crm/forecasting",category:"Explore",color:"#9270ce"},
  {id:"contacts",label:"Contacts",icon:"team",description:"Contacts and relationship context",href:"/crm/contacts",category:"Explore",color:"#47a49b"},
  {id:"companies",label:"Companies",icon:"gallery",description:"Your connected customer directory",href:"/crm/companies",category:"Explore",color:"#6d99c2"},
  {id:"files",label:"Files",description:"Documents and sales collateral",href:"/crm/files",category:"Collaborate",color:"#718eaf"},
  {id:"webforms",label:"Forms",icon:"form",description:"Turn inbound enquiries into action",href:"/crm/webforms",category:"Collaborate",color:"#9271ce"},
  {id:"reports",label:"Reports",icon:"dashboard",description:"Inspect outcomes and conversion",href:"/crm/reports",category:"Explore",color:"#bb78a7"},
];
const pms: WorkspaceView[] = [
  {id:"projects",label:"Projects",icon:"gallery",description:"Your portfolio and delivery health",href:"/pms/projects"},
  {id:"tasks",label:"Tasks",icon:"list",description:"The everyday execution workspace",href:"/pms/tasks",color:"#8b5cf6"},
  {id:"dashboards",label:"Dashboards",icon:"dashboard",description:"Actionable views of team performance",href:"/pms/dashboards",category:"Explore",color:"#9f71cf"},
  {id:"work-hub",label:"Work pipeline",icon:"board",description:"Move work through delivery stages",href:"/pms/work-hub",color:"#6b8de3"},
  {id:"team-communication",label:"Channel",icon:"channel",description:"Project conversations with your team",href:"/pms/team-communication",category:"Collaborate",color:"#8b5cf6"},
  {id:"gantt",label:"Gantt",description:"Dependencies and delivery schedules",href:"/pms/gantt",category:"Plan",color:"#e98279"},
  {id:"calendar",label:"Calendar",description:"Deadlines, events and planning",href:"/pms/calendar",category:"Plan",color:"#e2a15d"},
  {id:"workload",label:"Workload",description:"Availability and team capacity",href:"/pms/workload",category:"Plan",color:"#2fa594"},
  {id:"roadmap",label:"Roadmap",icon:"timeline",description:"Initiatives and the bigger picture",href:"/pms/roadmap",category:"Plan",color:"#d4a14f"},
  {id:"docs",label:"Docs",description:"Briefs, decisions and shared knowledge",href:"/pms/docs",category:"Collaborate",color:"#489cdd"},
  {id:"files",label:"Files",description:"Project assets and deliverables",href:"/pms/files",category:"Collaborate",color:"#7c9cba"},
  {id:"forms",label:"Forms",icon:"form",description:"Requests, feedback and structured intake",href:"/pms/forms",category:"Collaborate",color:"#9674d4"},
  {id:"teams",label:"Team",description:"People, roles and collaboration",href:"/pms/teams",category:"Explore",color:"#4ba79d"},
  {id:"workflow-schemes",label:"Project workflows",description:"Status transitions, required fields and approval routes",href:"/pms/workflow-schemes",category:"Plan"},
  {id:"transition-approvals",label:"Transition approvals",description:"Review pending project status changes",href:"/pms/transition-approvals",category:"Plan"},
];
const primaryWorkspaces = {
  crm:["dashboard","leads","deals","pipeline","activities","messages"],
  pms:["projects","tasks","dashboards","work-hub","team-communication"],
};

export default function ModuleWorkspaceFrame({module,children}:{module:"crm"|"pms";children:ReactNode}) {
  const {pathname,search}=useLocation();const user=useAuthStore(state=>state.user);
  const [open,setOpen]=useState(false);
  // Reuse the old module view-bar preference key so existing pins survive.
  let branch="";try{branch=sessionStorage.getItem("suite-branch")||"";}catch{/* Storage is optional. */}
  const preferenceKey=`suite:workspace-views:v1:${user?.id}:${user?.access?.companyId}:${branch}:${module}-navigation`;
  const [pinned,setPinned]=useState<string[]>(primaryWorkspaces[module]);
  const [ready,setReady]=useState("");
  useEffect(()=>{
    try{
      const saved=JSON.parse(localStorage.getItem(preferenceKey)||"null");
      setPinned(Array.isArray(saved)&&saved.every(id=>typeof id==="string")?[...new Set<string>(saved)]:primaryWorkspaces[module]);
    }catch{setPinned(primaryWorkspaces[module]);}
    setReady(preferenceKey);
  },[preferenceKey,module]);
  useEffect(()=>{if(ready===preferenceKey)try{localStorage.setItem(preferenceKey,JSON.stringify(pinned));}catch{/* Navigation works without storage. */}},[preferenceKey,ready,pinned]);
  useEffect(()=>setOpen(false),[pathname,search]);
  // Task execution already owns its full-screen shell and view catalogue.
  if(isSharedTaskWorkspace(pathname,search) || (module==="pms" && (hasPmsWorkspaceShell(pathname,search) || /^\/pms\/tasks(?:\/|$)/.test(pathname))))return <>{children}</>;
  const all=module==="crm"?crm:pms;
  const active=all.filter(view=>pathname===view.href||pathname.startsWith(`${view.href}/`)).sort((a,b)=>b.href!.length-a.href!.length)[0]?.id || (pathname===`/${module}`?module==="crm"?"dashboard":"projects":pathname.split("/")[2]);
  const views=all.filter(view=>canAccessRoute(view.href!,user?.role,user?.is_superuser));
  return <div className={`ws-premium-surface ws-${module}`}>
    <nav className="ws-workspace-navigation" aria-label={module==="crm"?"CRM pages":"PMS pages"}>
      <Link className="ws-directory-link" to={`/${module}/workspaces`}>Workspaces</Link>
      <span>{module==="crm"?"CRM":"Projects"}{views.find(view=>view.id===active)?.label && <> / {views.find(view=>view.id===active)!.label}</>}</span>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild><Button variant="ghost" size="sm">Explore pages<ChevronDown size={14} aria-hidden="true"/></Button></PopoverTrigger>
        <PopoverContent align="end" className="ws-workspace-catalog" aria-label="Explore module pages">
          {(["Work","Plan","Collaborate","Explore"] as const).map(category=>{
            const entries=views.filter(view=>(view.category||"Work")===category).sort((a,b)=>Number(pinned.includes(b.id))-Number(pinned.includes(a.id)));
            return entries.length>0 && <section key={category}><h2>{category}</h2>{entries.map(view=><div className="ws-workspace-option" key={view.id}><Link to={workspacePageHref(view.href!,search)} onClick={()=>setOpen(false)} aria-current={active===view.id?"page":undefined}>
              <span><strong>{view.label}</strong><small>{view.description}</small></span>{active===view.id&&<Check size={15} aria-hidden="true"/>}
            </Link><button type="button" aria-label={`${pinned.includes(view.id)?"Unpin":"Pin"} ${view.label} page`} aria-pressed={pinned.includes(view.id)} onClick={()=>setPinned(current=>current.includes(view.id)?current.filter(id=>id!==view.id):[...current,view.id])}><Star size={15} aria-hidden="true"/></button></div>)}</section>;
          })}
          <p className="ws-workspace-hint">Pinned pages appear first in each category.</p>
        </PopoverContent>
      </Popover>
    </nav>
    <div className="ws-page-content">{children}</div>
  </div>;
}
