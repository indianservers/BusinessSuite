import AddExistingPeopleDialog from "../components/people/AddExistingPeopleDialog";
import { usePageRefresh } from "@/lib/page-refresh";
import { RecordCustomFields } from "../components/CustomFields";
import { ConversationLauncher } from "@/shared/communication";
import { RichTextContent } from "@/components/rich-text/RichTextContent";
import SecondaryDetails from "@/components/app/SecondaryDetails";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, BarChart3, CheckCircle2, Clock, Kanban, ListChecks, Milestone, ShieldAlert, Timer } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import AskAiButton from "@/components/ai-agents/AskAiButton";
import { formatCurrency, formatDate, statusColor } from "@/lib/utils";
import { projectsAPI, tasksAPI } from "../services/api";
import { useProjectStore, useTaskStore } from "../store";
import type { DashboardData, PMSTask } from "../types";

export default function ProjectDashboard() {
  const { projectId } = useParams<{ projectId: string }>();
  const id = Number(projectId || 0);
  const { selectedProject, setSelectedProject } = useProjectStore();
  const { tasks, setTasks } = useTaskStore();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [addingPeople, setAddingPeople] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error,setError] = useState("");
  const [retryVersion,setRetryVersion] = useState(0);

  useEffect(() => {
    let active=true;
    setLoading(true);setError("");setSelectedProject(null);setDashboard(null);setTasks([]);
    if(!id){setLoading(false);setError("Choose a valid project.");return;}
    Promise.all([projectsAPI.get(id),projectsAPI.getDashboard(id),tasksAPI.list(id)])
      .then(([project,dashboardData,taskData])=>{if(!active)return;setSelectedProject(project);setDashboard(dashboardData);setTasks(taskData);})
      .catch(err=>{if(active)setError(typeof err?.response?.data?.detail==="string"?err.response.data.detail:"Unable to load this project. Check your access and try again.");})
      .finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[id,setSelectedProject,setTasks,retryVersion]);

  usePageRefresh(() => setRetryVersion(value => value + 1));

  const project = selectedProject || dashboard?.project;
  const taskChart=Object.entries(dashboard?.status_counts||{}).map(([status,tasks])=>({status,tasks}));
  const overdue = tasks.filter(isOverdue);

  if (loading) return <div className="skeleton h-72 rounded-lg" />;
  if (error || !project) return <div role="alert" className="rounded-xl border bg-card p-6 space-y-3"><h1 className="text-xl font-semibold">Project unavailable</h1><p className="text-sm text-muted-foreground">{error || "Project not found."}</p><div className="flex gap-3"><Button variant="outline" onClick={()=>setRetryVersion(version=>version+1)}>Retry</Button><Button asChild><Link to="/pms/projects">Back to projects</Link></Button></div></div>;

  return (
    <div className="space-y-6">
      <AddExistingPeopleDialog open={addingPeople} onClose={() => setAddingPeople(false)} projectId={id} workspaceId={project.workspace_id} />
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="page-title">{project.name}</h1><ConversationLauncher module="PMS" workspaceId={project.workspace_id} context={{type:"project",id}}/>
            <Badge className={statusColor(project.status)}>{project.status}</Badge>
          </div>
          <div className="page-description"><RichTextContent value={project.description || "Project workspace overview"}/></div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button disabled={!project.can_manage_members && !project.can_edit_project} onClick={() => setAddingPeople(true)}>Add existing person</Button><Button asChild variant="outline"><Link to={`/pms/projects/${id}/members`}>Manage project members</Link></Button>
          {project.can_edit_project && <Button asChild variant="outline"><Link to={`/pms/projects/${id}/edit`}>Edit project</Link></Button>}
          <AskAiButton
            module="PMS"
            relatedEntityType="project"
            relatedEntityId={id}
            defaultAgentCode="pms_project_status"
            defaultPrompt="Summarize this project status with delays, blockers, and risks."
          />
          <Button asChild variant="outline"><Link to={`/pms/projects/${id}/billing`}>Billing & invoices</Link></Button>
          <Button asChild variant="outline"><Link to={`/pms/projects/${id}/milestones`}><Milestone className="h-4 w-4" />Milestones</Link></Button>
          <Button asChild variant="outline"><Link to={`/pms/projects/${id}/risks`}><ShieldAlert className="h-4 w-4" />Risks</Link></Button>
          <Button asChild variant="outline"><Link to={`/pms/projects/${id}/notes`}>My Notes</Link></Button>
          <Button asChild><Link to={`/pms/projects/${id}/board`}><Kanban className="h-4 w-4" />Open board</Link></Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <Metric icon={ListChecks} label="Total tasks" value={dashboard?.metrics.total_tasks ?? "Unavailable"} />
        <Metric icon={CheckCircle2} label="Completed" value={dashboard?.metrics.completed_tasks ?? "Unavailable"} />
        <Metric icon={Clock} label="Overdue" value={dashboard?.metrics.overdue_tasks ?? "Unavailable"} tone="text-red-600" />
        <Metric icon={AlertTriangle} label="High risks" value={dashboard?.metrics.high_risks ?? "Unavailable"} tone="text-amber-600" />
        <Metric icon={Timer} label="Progress" value={`${project.progress_percent}%`} />
      </div>

      <p className="text-xs text-muted-foreground">Unique live task records, including subtasks. {dashboard?.assignment_count} individual assignments. The status chart includes the full permitted project; task previews below may be paginated.</p>
      <RecordCustomFields entity="project" id={id}/>
      <SecondaryDetails title="Task status and project details">
      <div className="grid gap-4 xl:grid-cols-[1.4fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><BarChart3 className="h-5 w-5" />Task status</CardTitle>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={taskChart}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="status" tickLine={false} axisLine={false} />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
                <Tooltip />
                <Bar dataKey="tasks" fill="hsl(var(--primary))" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Project summary</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <Summary label="Key" value={project.project_key} />
            <Summary label="Priority" value={project.priority} />
            <Summary label="Health" value={project.health} />
            <Summary label="Start" value={formatDate(project.start_date || null)} />
            <Summary label="Due" value={formatDate(project.due_date || null)} />
            <Summary label="Budget" value={formatCurrency(Number(project.budget_amount || 0))} />
          </CardContent>
        </Card>
      </div>

      </SecondaryDetails>

      {project.srm_links ? (
        <Card>
          <CardHeader>
            <CardTitle>SRM Engagement Link</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-4">
            <LinkedSummary label="Engagement" value={textValue(project.srm_links.engagement?.engagement_number || project.srm_links.engagement?.name)} />
            <LinkedSummary label="Sales Order" value={textValue(project.srm_links.sales_order?.order_number || project.srm_links.sales_order?.title)} />
            <LinkedSummary label="Contract" value={textValue(project.srm_links.contract?.contract_number || project.srm_links.contract?.title)} />
            <LinkedSummary label="Billing Plan" value={textValue(project.srm_links.billing_plan?.name || project.srm_links.billing_plan?.billing_type)} />
          </CardContent>
        </Card>
      ) : null}

    </div>
  );
}

function isOverdue(task: PMSTask) {
  return Boolean(task.due_date && new Date(task.due_date) < new Date() && task.status !== "Done");
}

function Metric({ icon: Icon, label, value, tone }: { icon: typeof ListChecks; label: string; value: string | number; tone?: string }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className="rounded-lg bg-primary/10 p-3 text-primary"><Icon className="h-5 w-5" /></div>
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className={`text-2xl font-semibold ${tone || ""}`}>{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function Summary({ label, value }: { label: string; value: string }) {
  return <div className="flex items-center justify-between border-b pb-2 last:border-0"><span className="text-muted-foreground">{label}</span><span className="font-medium">{value}</span></div>;
}

function LinkedSummary({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border bg-muted/30 p-3 text-sm"><p className="text-xs uppercase text-muted-foreground">{label}</p><p className="mt-1 truncate font-medium">{value || "Not linked"}</p></div>;
}

function textValue(value: unknown) {
  if (value === null || value === undefined) return "";
  return String(value);
}

