import { api } from "@/services/api";
import { useQuery } from "@tanstack/react-query";
import { milestonesAPI, activityAPI, filesAPI } from "../services/api";
import ProjectOverview from "../components/ProjectOverview";
import CatalogAssociations from "@/shared/catalog/CatalogLinesEditor";
import AddExistingPeopleDialog from "../components/people/AddExistingPeopleDialog";
import { usePageRefresh } from "@/lib/page-refresh";
import { RecordCustomFields } from "../components/CustomFields";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { projectsAPI, tasksAPI } from "../services/api";
import { useProjectStore, useTaskStore } from "../store";
import type { DashboardData, PMSTask } from "../types";

export default function ProjectDashboard() {
  const { projectId } = useParams<{ projectId: string }>();
  const id = Number(projectId || 0);
  const mobileMembers=useQuery({queryKey:["mobile-project-members",id],queryFn:()=>api.get<{user_id:number;name?:string;email?:string}[]>(`/project-management/projects/${id}/members`).then(r=>r.data),enabled:!!id});
  const mobileMilestones=useQuery({queryKey:["mobile-project-milestones",id],queryFn:()=>milestonesAPI.list(id),enabled:!!id});
  const projectFiles=useQuery({queryKey:["project-overview-files",id],queryFn:()=>filesAPI.list({project_id:id}),enabled:!!id});
  const recentActivity=useQuery({queryKey:["project-overview-activity",id],queryFn:()=>activityAPI.list(id,{limit:4}),enabled:!!id});
  const [moreOpen,setMoreOpen]=useState(false);
  const { selectedProject, setSelectedProject } = useProjectStore();
  const { tasks, setTasks } = useTaskStore();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [addingPeople, setAddingPeople] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error,setError] = useState("");
  const loadedProjectId = useRef<number>();
  const [retryVersion,setRetryVersion] = useState(0);

  useEffect(() => {
    let active=true;
    document.getElementById("suite-main")?.scrollTo({top:0,left:0,behavior:"auto"});
    setLoading(true);setError("");
    if(loadedProjectId.current!==id){setSelectedProject(null);setDashboard(null);setTasks([]);loadedProjectId.current=id;}
    if(!id){setLoading(false);setError("Choose a valid project.");return;}
    Promise.all([projectsAPI.get(id),projectsAPI.getDashboard(id),tasksAPI.list(id)])
      .then(([project,dashboardData,taskData])=>{if(!active)return;setSelectedProject(project);setDashboard(dashboardData);setTasks(taskData);})
      .catch(err=>{if(!active)return;if([401,403,404].includes(err?.response?.status)){setSelectedProject(null);setDashboard(null);setTasks([]);}setError(typeof err?.response?.data?.detail==="string"?err.response.data.detail:"Unable to load this project. Check your access and try again.");})
      .finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[id,setSelectedProject,setTasks,retryVersion]);

  usePageRefresh(() => setRetryVersion(value => value + 1));

  const project = selectedProject || dashboard?.project;

  if (loading && !dashboard) return <div className="skeleton h-72 rounded-lg" />;
  if (!project) return <div role="alert" className="rounded-xl border bg-card p-6 space-y-3"><h1 className="text-xl font-semibold">Project unavailable</h1><p className="text-sm text-muted-foreground">{error || "Project not found."}</p><div className="flex gap-3"><Button variant="outline" onClick={()=>setRetryVersion(version=>version+1)}>Retry</Button><Button asChild><Link to="/pms/projects">Back to projects</Link></Button></div></div>;

  return <div aria-busy={loading}>
    {error && <p role="alert" className="mb-4 rounded border border-destructive/30 p-3 text-sm">{error}</p>}
    <AddExistingPeopleDialog open={addingPeople} onClose={() => setAddingPeople(false)} projectId={id} workspaceId={project.workspace_id} />
    <ProjectOverview project={project} fileCount={projectFiles.data?.length} dashboard={dashboard} tasks={tasks} members={mobileMembers.data || []} milestones={mobileMilestones.data || []} activity={recentActivity.data || []} membersError={mobileMembers.isError} milestonesError={mobileMilestones.isError} activityError={recentActivity.isError} onAddMember={() => setAddingPeople(true)} onMore={() => { setMoreOpen(true); setTimeout(() => document.getElementById("project-more-details")?.scrollIntoView({behavior:"smooth",block:"start"}),0); }} />
    <details id="project-more-details" className="pd-extra" open={moreOpen} onToggle={event=>setMoreOpen(event.currentTarget.open)}>
      <summary>Project actions</summary>
      <div className="pd-extra-content">
        <div className="pd-actions-menu"><button disabled={!project.can_manage_members && !project.can_edit_project} onClick={() => setAddingPeople(true)}>Add existing person</button><Link to={`/pms/projects/${id}/members`}>Manage project members</Link>{project.can_edit_project && <Link to={`/pms/projects/${id}/edit`}>Edit project</Link>}<Link to={`/pms/projects/${id}/billing`}>Billing & invoices</Link><Link to={`/pms/projects/${id}/milestones`}>Milestones</Link><Link to={`/pms/projects/${id}/risks`}>Risks</Link><Link to={`/pms/projects/${id}/notes`}>My Notes</Link></div>
        <CatalogAssociations source="pms" target="project" id={id}/>
        <RecordCustomFields entity="project" id={id}/>
        {project.srm_links && <Card><CardHeader><CardTitle>SRM Engagement Link</CardTitle></CardHeader><CardContent className="grid gap-3 md:grid-cols-4"><LinkedSummary label="Engagement" value={textValue(project.srm_links.engagement?.engagement_number || project.srm_links.engagement?.name)} /><LinkedSummary label="Sales Order" value={textValue(project.srm_links.sales_order?.order_number || project.srm_links.sales_order?.title)} /><LinkedSummary label="Contract" value={textValue(project.srm_links.contract?.contract_number || project.srm_links.contract?.title)} /><LinkedSummary label="Billing Plan" value={textValue(project.srm_links.billing_plan?.name || project.srm_links.billing_plan?.billing_type)} /></CardContent></Card>}
      </div>
    </details>
  </div>;
}

function LinkedSummary({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border bg-muted/30 p-3 text-sm"><p className="text-xs uppercase text-muted-foreground">{label}</p><p className="mt-1 truncate font-medium">{value || "Not linked"}</p></div>;
}

function textValue(value: unknown) {
  if (value === null || value === undefined) return "";
  return String(value);
}

