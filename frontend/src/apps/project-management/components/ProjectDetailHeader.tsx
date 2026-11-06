import { useEffect, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation, useParams } from "react-router-dom";
import { Building2, CalendarDays, ClipboardList, Files, Flag, LayoutDashboard, ListChecks, MessageSquare, ShieldAlert, Users, Wallet } from "lucide-react";
import { RichTextContent } from "@/components/rich-text/RichTextContent";
import { formatDate } from "@/lib/utils";
import { projectsAPI, filesAPI } from "../services/api";
import { api } from "@/services/api";
import type { PMSProject } from "../types";
import { useCommunicationScope } from "@/shared/communication/scope";
import { workspaceError } from "../pages/workspaceTypes";
import "./ProjectDetail.css";
import "./ProjectTabs.css";

export function ProjectDetailHeader({ project, taskCount, memberCount, riskCount, fileCount }: { project: PMSProject; taskCount?: number; memberCount?: number; riskCount?: number; fileCount?: number }) {
  const location = useLocation(), base = `/pms/projects/${project.id}`;
  const tabs = [
    { label: "Overview", suffix: "", icon: LayoutDashboard },
    { label: "Tasks", suffix: "/board", icon: ListChecks, count: taskCount },
    { label: "Timeline", suffix: "/timeline", icon: CalendarDays },
    { label: "Team", suffix: "/members", icon: Users, count: memberCount },
    { label: "Files", suffix: "/files", icon: Files, count: fileCount },
    { label: "Finance", suffix: "/billing", icon: Wallet },
    { label: "Notes", suffix: "/notes", icon: MessageSquare },
    { label: "Risks", suffix: "/risks", icon: ShieldAlert, count: riskCount },
  ];
  return <>
    <header className="pd-hero"><div className="pd-project-icon"><ClipboardList size={30} /></div><div className="pd-hero-text"><h1>{project.name}</h1><RichTextContent value={project.description || "Project workspace overview"} /><div className="pd-pills"><span className="pd-pill pd-green"><Flag size={13} />{project.status}</span>{(project.client_name || project.client_id) && <span className="pd-pill"><Building2 size={13} />{project.client_name || `Client #${project.client_id}`}</span>}<span className="pd-pill pd-pink"><CalendarDays size={13} />Due: {formatDate(project.due_date || null)}</span><span className="pd-pill pd-orange"><Flag size={13} />{project.priority || "Normal"} Priority</span></div></div><div className="pd-hero-art" aria-hidden="true"><div className="pd-art-window"><span /><span /><span /><div className="pd-art-layout"><i /><i /><i /><i /></div></div><div className="pd-art-phone"><ListChecks size={24} /></div></div></header>
    <nav className="pd-tabs" aria-label="Project views">{tabs.map(({ label, suffix, icon: Icon, count }) => { const active = suffix ? location.pathname === base + suffix || (suffix === "/timeline" && location.pathname === base + "/gantt") : location.pathname === base; return <Link key={label} to={base + suffix} aria-current={active ? "page" : undefined}><Icon size={17} />{label}{count !== undefined && <span>{count}</span>}</Link>; })}</nav>
  </>;
}

/** Retain the project identity and tabs while navigating existing project tools. */
export function ProjectDetailFrame({ children }: { children: ReactNode }) {
  const { projectId } = useParams();
  const id = Number(projectId);
  const scope = useCommunicationScope();
  const location = useLocation();
  const view = location.pathname.split("/").pop() || "overview";
  useEffect(() => { document.getElementById("suite-main")?.scrollTo({ top: 0, left: 0, behavior: "auto" }); }, [location.pathname]);
  const views: Record<string, { title: string; description: string; icon: typeof ListChecks }> = {
    board: { title: "Tasks & delivery", description: "Plan work, assign owners, and keep every task moving.", icon: ListChecks },
    timeline: { title: "Project timeline", description: "See the delivery plan, dependencies, and upcoming dates.", icon: CalendarDays },
    gantt: { title: "Project timeline", description: "See the delivery plan, dependencies, and upcoming dates.", icon: CalendarDays },
    members: { title: "Project team", description: "The people, roles, and invitations behind this project.", icon: Users },
    files: { title: "Project files", description: "Keep designs, documents, and deliverables together.", icon: Files },
    billing: { title: "Project finance", description: "Track billing, invoices, and the project’s commercial details.", icon: Wallet },
    notes: { title: "Project notes", description: "Capture decisions, meeting notes, and the next steps.", icon: MessageSquare },
    risks: { title: "Risks & mitigation", description: "Spot delivery risks early and keep mitigation plans visible.", icon: ShieldAlert },
  };
  const active = views[view];
  const project = useQuery({ queryKey: ["project-detail-frame", scope, id], enabled: id > 0, queryFn: () => projectsAPI.get(id) });
  const dashboard = useQuery({ queryKey: ["project-detail-tab-counts", scope, id], enabled: !!project.data, queryFn: () => projectsAPI.getDashboard(id) });
  const members = useQuery({ queryKey: ["project-detail-tab-members", scope, id], enabled: !!project.data, queryFn: async () => (await api.get<unknown[]>(`/project-management/projects/${id}/members`)).data });
  const files = useQuery({ queryKey: ["project-detail-tab-files", scope, id], enabled: !!project.data, queryFn: () => filesAPI.list({ project_id: id }) });
  if (project.isPending) return <p role="status">Loading project…</p>;
  if (project.isError) return <p role="alert">{workspaceError(project.error)} <button className="underline" onClick={() => void project.refetch()}>Retry</button></p>;
  return <div className="pd-page pd-tab-page" data-project-page data-project-view={view}>
    <ProjectDetailHeader project={project.data} taskCount={dashboard.data?.metrics.total_tasks} memberCount={members.data?.length} fileCount={files.data?.length} riskCount={dashboard.data?.metrics.high_risks} />
    {active && <header className="pd-view-intro"><span className="pd-view-icon"><active.icon size={22} /></span><div><h2>{active.title}</h2><p>{active.description}</p></div><Link to={`/pms/team-communication?project=${id}`}><MessageSquare size={16} /><span>Discuss with team</span></Link></header>}
    <div className="pd-tool-content">{children}</div>
  </div>;
}
