import type { ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import WorkspaceViewBar, { type WorkspaceView } from "./WorkspaceViewBar";
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
  {id:"contacts",label:"People",icon:"team",description:"Contacts and relationship context",href:"/crm/contacts",category:"Explore",color:"#47a49b"},
  {id:"companies",label:"Companies",icon:"gallery",description:"Your connected customer directory",href:"/crm/companies",category:"Explore",color:"#6d99c2"},
  {id:"files",label:"Files",description:"Documents and sales collateral",href:"/crm/files",category:"Collaborate",color:"#718eaf"},
  {id:"webforms",label:"Forms",icon:"form",description:"Turn inbound enquiries into action",href:"/crm/webforms",category:"Collaborate",color:"#9271ce"},
  {id:"reports",label:"Reports",icon:"dashboard",description:"Inspect outcomes and conversion",href:"/crm/reports",category:"Explore",color:"#bb78a7"},
];
const pms: WorkspaceView[] = [
  {id:"projects",label:"Projects",icon:"gallery",description:"Your portfolio and delivery health",href:"/pms/projects"},
  {id:"tasks",label:"Tasks",icon:"list",description:"The everyday execution workspace",href:"/pms/tasks",color:"#8b5cf6"},
  {id:"dashboards",label:"Dashboards",icon:"dashboard",description:"Actionable views of team performance",href:"/pms/dashboards",category:"Explore",color:"#9f71cf"},
  {id:"work-hub",label:"Pipeline",icon:"board",description:"Move work through delivery stages",href:"/pms/work-hub",color:"#6b8de3"},
  {id:"team-communication",label:"Channel",icon:"channel",description:"Project conversations with your team",href:"/pms/team-communication",category:"Collaborate",color:"#8b5cf6"},
  {id:"gantt",label:"Gantt",description:"Dependencies and delivery schedules",href:"/pms/gantt",category:"Plan",color:"#e98279"},
  {id:"calendar",label:"Calendar",description:"Deadlines, events and planning",href:"/pms/calendar",category:"Plan",color:"#e2a15d"},
  {id:"workload",label:"Workload",description:"Availability and team capacity",href:"/pms/workload",category:"Plan",color:"#2fa594"},
  {id:"roadmap",label:"Roadmap",icon:"timeline",description:"Initiatives and the bigger picture",href:"/pms/roadmap",category:"Plan",color:"#d4a14f"},
  {id:"docs",label:"Docs",description:"Briefs, decisions and shared knowledge",href:"/pms/docs",category:"Collaborate",color:"#489cdd"},
  {id:"files",label:"Files",description:"Project assets and deliverables",href:"/pms/files",category:"Collaborate",color:"#7c9cba"},
  {id:"forms",label:"Forms",icon:"form",description:"Requests, feedback and structured intake",href:"/pms/forms",category:"Collaborate",color:"#9674d4"},
  {id:"teams",label:"Team",description:"People, roles and collaboration",href:"/pms/teams",category:"Explore",color:"#4ba79d"},
];

export default function ModuleWorkspaceFrame({module,children}:{module:"crm"|"pms";children:ReactNode}) {
  const {pathname}=useLocation();const navigate=useNavigate();const user=useAuthStore(state=>state.user);
  // Task execution already owns its full-screen shell and view catalogue.
  if(module==="pms" && /^\/pms\/tasks(?:\/|$)/.test(pathname))return <>{children}</>;
  const all=module==="crm"?crm:pms;
  const active=all.find(view=>view.href===pathname)?.id || (pathname===`/${module}`?module==="crm"?"dashboard":"projects":pathname.split("/")[2]);
  const views=all.filter(view=>canAccessRoute(view.href!,user?.role,user?.is_superuser));
  return <div className={`ws-premium-surface ws-${module}`}><WorkspaceViewBar label={module==="crm"?"CRM workspaces":"PMS workspaces"} scope={`${module}-navigation`} active={active} views={views} primary={module==="crm"?["dashboard","leads","deals","pipeline","activities","messages"]:["projects","tasks","dashboards","work-hub","team-communication"]} onChange={id=>{const view=views.find(view=>view.id===id);if(view?.href)navigate(view.href);}}/><div className="ws-page-content">{children}</div></div>;
}
