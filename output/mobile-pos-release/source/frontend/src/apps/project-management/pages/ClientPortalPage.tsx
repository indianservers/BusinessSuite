import {useMobileContext} from "@/components/mobile/useMobileContext";
import {syncScope} from "@/shared/record-sync/store";
import {useClientPortalSources} from "./useClientPortalSources";
import {useMobile} from "@/components/mobile/useMobile";
import {workspaceError} from "./workspaceTypes";
import "./client-portal-mobile.css";
import { useRefreshableEffect } from "@/lib/page-refresh";
import { useEffect, useRef, useState } from "react";
import { CheckCircle2, FileText, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate, statusColor } from "@/lib/utils";
import { filesAPI, milestonesAPI, projectsAPI } from "../services/api";
import type { PMSFileAsset, PMSMilestone, PMSProject } from "../types";

export default function ClientPortalPage() {
  const phone=useMobile(480),scope=useMobileContext();
  if(phone&&scope!==syncScope())return <p role="status">Updating client portal context…</p>;
  return <ClientPortalContent key={phone?scope:"desktop"}/>;
}

function ClientPortalContent() {
  const phone=useMobile(480),mounted=useRef(true),inFlight=useRef(new Set<number>());
  const ownerScope=useRef(syncScope());
  const owns=()=>mounted.current&&ownerScope.current===syncScope();
  const [pending,setPending]=useState<number[]>([]),[actionErrors,setActionErrors]=useState<Record<number,string>>({});
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  async function control(milestone:PMSMilestone,action:'approve'|'reject'){
    if(!owns()||inFlight.current.has(milestone.id))return;
    inFlight.current.add(milestone.id);setPending([...inFlight.current]);setActionErrors(values=>({...values,[milestone.id]:''}));
    try{const updated=action==='approve'?await milestonesAPI.approve(milestone.id):await milestonesAPI.reject(milestone.id,'Client requested changes from portal.');if(owns())sources.commitMilestone(updated);}
    catch(error){if(owns())setActionErrors(values=>({...values,[milestone.id]:workspaceError(error)}));}
    finally{inFlight.current.delete(milestone.id);if(owns())setPending([...inFlight.current]);}
  }
  const sources=useClientPortalSources(phone);
  const [desktopProjects, setProjects] = useState<PMSProject[]>([]);
  const [desktopMilestones, setDesktopMilestones] = useState<PMSMilestone[]>([]);
  const [desktopFiles, setFiles] = useState<PMSFileAsset[]>([]);

  const projects=phone?sources.projects:desktopProjects, milestones=phone?sources.milestones:desktopMilestones, files=phone?sources.files:desktopFiles;
  const setMilestones=phone?sources.setMilestones:setDesktopMilestones;

  useRefreshableEffect(() => {
    if(phone)return;
    projectsAPI.list().then(async (items) => {
      const visible = items.filter((project) => project.is_client_visible || project.status !== "Archived");
      setProjects(visible);
      const milestoneGroups = await Promise.all(visible.map((project) => milestonesAPI.list(project.id).catch(() => [])));
      const fileGroups = await Promise.all(visible.map((project) => filesAPI.list({ project_id: project.id }).catch(() => [])));
      setDesktopMilestones(milestoneGroups.flat());
      setFiles(fileGroups.flat().filter((file) => file.visibility === "Client Visible"));
    });
  }, [phone]);

  const approve = async (milestone: PMSMilestone) => {
    if(phone){await control(milestone,'approve');return;}
    const updated = await milestonesAPI.approve(milestone.id);
    setMilestones((items) => items.map((item) => item.id === milestone.id ? updated : item));
  };

  const reject = async (milestone: PMSMilestone) => {
    if(phone){await control(milestone,'reject');return;}
    const updated = await milestonesAPI.reject(milestone.id, "Client requested changes from portal.");
    setMilestones((items) => items.map((item) => item.id === milestone.id ? updated : item));
  };

  return (
    <div className="pms-client-portal space-y-6">
      <div>
        <h1 className="page-title">Client portal</h1>
        <p className="page-description">Client-safe project progress, approvals, and shared deliverables.</p>
      </div>
      <div className="pms-portal-metrics grid gap-4 md:grid-cols-3">
        <Metric label="Visible projects" value={phone&&sources.phase.projects!=="ready"?"—":projects.length} />
        <Metric label="Approval items" value={phone&&(sources.phase.projects!=="ready"||sources.phase.milestones!=="ready")?"—":milestones.filter((item) => item.client_approval_status === "Pending").length} />
        <Metric label="Shared files" value={phone&&(sources.phase.projects!=="ready"||sources.phase.files!=="ready")?"—":files.length} />
      </div>
      {phone&&<SourceState phase={sources.phase.projects} error={sources.errors.projects} label="projects" empty={!projects.length} retry={()=>sources.retry("projects")}/>}
      <Card>
        <CardHeader className="pms-portal-card-heading"><CardTitle>Milestone approvals</CardTitle></CardHeader>
        <CardContent className="pms-portal-approvals space-y-3">
          {phone&&sources.phase.projects==="ready"&&<SourceState phase={sources.phase.milestones} error={sources.errors.milestones} label="milestone approvals" empty={!milestones.length} retry={()=>sources.retry("milestones")}/>}
          {milestones.map((milestone) => (
            <div key={milestone.id} data-milestone-id={phone?milestone.id:undefined} aria-busy={phone?pending.includes(milestone.id):undefined} className="pms-portal-approval flex flex-col gap-3 rounded-lg border p-4 md:flex-row md:items-center md:justify-between">
              <div>
                <div className="pms-portal-approval-heading flex items-center gap-2">
                  <h2 className="font-semibold">{milestone.name}</h2>
                  <Badge className={statusColor(milestone.client_approval_status)}>{milestone.client_approval_status}</Badge>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">Due {formatDate(milestone.due_date || null)} - {milestone.progress_percent}% complete</p>
              </div>
              <div className="pms-portal-approval-actions flex gap-2">
                <Button size="sm" variant="outline" disabled={phone&&pending.includes(milestone.id)} onClick={() => reject(milestone)}><XCircle className="h-4 w-4" />Reject</Button>
                <Button size="sm" disabled={phone&&pending.includes(milestone.id)} onClick={() => approve(milestone)}><CheckCircle2 className="h-4 w-4" />Approve</Button>
              </div>
              {phone&&pending.includes(milestone.id)&&<p role="status">Updating approval…</p>}
              {phone&&actionErrors[milestone.id]&&<p role="alert" className="text-destructive">{actionErrors[milestone.id]}</p>}
            </div>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pms-portal-card-heading"><CardTitle>Shared files</CardTitle></CardHeader>
        <CardContent className="pms-portal-files grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {phone&&sources.phase.projects==="ready"&&<SourceState phase={sources.phase.files} error={sources.errors.files} label="shared files" empty={!files.length} retry={()=>sources.retry("files")}/>}
          {files.map((file) => <div key={file.id} className="pms-portal-file rounded-lg border p-3 text-sm"><FileText className="mb-2 h-4 w-4 text-primary" /><p className="font-medium">{file.original_name}</p><p className="text-muted-foreground">{formatDate(file.created_at)}</p></div>)}
        </CardContent>
      </Card>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return <Card><CardContent className="pms-portal-metric p-5"><p className="text-sm text-muted-foreground">{label}</p><p className="mt-2 text-3xl font-semibold">{value}</p></CardContent></Card>;
}


function SourceState({phase,error,label,empty,retry}:{phase:"loading"|"ready"|"error";error:string;label:string;empty:boolean;retry:()=>void}){
  if(phase==="loading")return <p role="status">Loading {label}…</p>;
  if(phase==="error")return <div className="pms-portal-source-error" role="alert"><p>Could not load all {label}. {error}</p><Button variant="outline" onClick={retry}>Retry {label}</Button></div>;
  return empty?<p role="status">No {label} available.</p>:null;
}
