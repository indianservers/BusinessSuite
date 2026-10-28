import { useRefreshableEffect } from "@/lib/page-refresh";
import { useEffect, useState } from "react";
import { CheckCircle2, FileText, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate, statusColor } from "@/lib/utils";
import { filesAPI, milestonesAPI, projectsAPI } from "../services/api";
import type { PMSFileAsset, PMSMilestone, PMSProject } from "../types";

export default function ClientPortalPage() {
  const [projects, setProjects] = useState<PMSProject[]>([]);
  const [milestones, setMilestones] = useState<PMSMilestone[]>([]);
  const [files, setFiles] = useState<PMSFileAsset[]>([]);

  useRefreshableEffect(() => {
    projectsAPI.list().then(async (items) => {
      const visible = items.filter((project) => project.is_client_visible || project.status !== "Archived");
      setProjects(visible);
      const milestoneGroups = await Promise.all(visible.map((project) => milestonesAPI.list(project.id).catch(() => [])));
      const fileGroups = await Promise.all(visible.map((project) => filesAPI.list({ project_id: project.id }).catch(() => [])));
      setMilestones(milestoneGroups.flat());
      setFiles(fileGroups.flat().filter((file) => file.visibility === "Client Visible"));
    });
  }, []);

  const approve = async (milestone: PMSMilestone) => {
    const updated = await milestonesAPI.approve(milestone.id);
    setMilestones((items) => items.map((item) => item.id === milestone.id ? updated : item));
  };

  const reject = async (milestone: PMSMilestone) => {
    const updated = await milestonesAPI.reject(milestone.id, "Client requested changes from portal.");
    setMilestones((items) => items.map((item) => item.id === milestone.id ? updated : item));
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Client portal</h1>
        <p className="page-description">Client-safe project progress, approvals, and shared deliverables.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <Metric label="Visible projects" value={projects.length} />
        <Metric label="Approval items" value={milestones.filter((item) => item.client_approval_status === "Pending").length} />
        <Metric label="Shared files" value={files.length} />
      </div>
      <Card>
        <CardHeader><CardTitle>Milestone approvals</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {milestones.map((milestone) => (
            <div key={milestone.id} className="flex flex-col gap-3 rounded-lg border p-4 md:flex-row md:items-center md:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="font-semibold">{milestone.name}</h2>
                  <Badge className={statusColor(milestone.client_approval_status)}>{milestone.client_approval_status}</Badge>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">Due {formatDate(milestone.due_date || null)} - {milestone.progress_percent}% complete</p>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => reject(milestone)}><XCircle className="h-4 w-4" />Reject</Button>
                <Button size="sm" onClick={() => approve(milestone)}><CheckCircle2 className="h-4 w-4" />Approve</Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Shared files</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {files.map((file) => <div key={file.id} className="rounded-lg border p-3 text-sm"><FileText className="mb-2 h-4 w-4 text-primary" /><p className="font-medium">{file.original_name}</p><p className="text-muted-foreground">{formatDate(file.created_at)}</p></div>)}
        </CardContent>
      </Card>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return <Card><CardContent className="p-5"><p className="text-sm text-muted-foreground">{label}</p><p className="mt-2 text-3xl font-semibold">{value}</p></CardContent></Card>;
}

